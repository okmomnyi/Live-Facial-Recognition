"""Watchlist person routes: list, get, delete."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..config import settings
from ..db import get_session
from ..models import Person, Ref
from ..schemas import PersonOut

router = APIRouter(prefix="/api/persons", tags=["persons"])


async def _persons_with_counts(session: AsyncSession, person_id: int | None = None):
    # Two correlated scalar subqueries over refs, one for the count and one for
    # the first (lowest-id) ref's image_path (the card thumbnail). We correlate
    # Person explicitly so SQLAlchemy keeps `refs` in each subquery's FROM
    # instead of auto-correlating it out (which would raise "no FROM clauses").
    # Avoiding an outer join + GROUP BY also sidesteps that interaction entirely.
    ref_count = (
        select(func.count(Ref.id))
        .where(Ref.person_id == Person.id)
        .correlate(Person)
        .scalar_subquery()
    )
    thumbnail = (
        select(Ref.image_path)
        .where(Ref.person_id == Person.id)
        .order_by(Ref.id)
        .limit(1)
        .correlate(Person)
        .scalar_subquery()
    )
    stmt = select(
        Person, ref_count.label("ref_count"), thumbnail.label("thumb")
    ).order_by(Person.created_at.desc())
    if person_id is not None:
        stmt = stmt.where(Person.id == person_id)
    rows = (await session.execute(stmt)).all()
    return [
        PersonOut(
            id=p.id,
            name=p.name,
            category=p.category,
            notes=p.notes,
            created_at=p.created_at,
            ref_count=count,
            thumbnail_path=thumb,
        )
        for p, count, thumb in rows
    ]


@router.get("", response_model=list[PersonOut])
async def list_persons(session: AsyncSession = Depends(get_session)) -> list[PersonOut]:
    return await _persons_with_counts(session)


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: int, session: AsyncSession = Depends(get_session)
) -> PersonOut:
    people = await _persons_with_counts(session, person_id)
    if not people:
        raise HTTPException(status_code=404, detail="Person not found")
    return people[0]


# Returns an explicit empty Response (annotated `-> Response`) so FastAPI never
# builds a response body for the 204. This is correct on current FastAPI and
# also avoids the "Status code 204 must not have a response body" assertion that
# older FastAPI versions raise for a `-> None` annotation on a 204 route.
@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: int, session: AsyncSession = Depends(get_session)
) -> Response:
    # Fetch ref image paths so we can clean up files after the cascade delete.
    ref_paths = (
        await session.execute(
            select(Ref.image_path).where(Ref.person_id == person_id)
        )
    ).scalars().all()

    result = await session.execute(delete(Person).where(Person.id == person_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Person not found")

    await log_action(
        session,
        actor="officer",
        action="person_deleted",
        subject_type="person",
        subject_id=person_id,
        detail={"ref_count": len(ref_paths)},
        commit=False,
    )
    await session.commit()

    # Best-effort file cleanup (DB is the source of truth; files are derived).
    for path in ref_paths:
        try:
            # Stored as e.g. "/data/references/uuid.png"; map to disk under DATA_DIR.
            disk = Path(settings.data_dir) / Path(path).relative_to(settings.data_dir)
            disk.unlink(missing_ok=True)
        except (ValueError, OSError):
            continue

    return Response(status_code=status.HTTP_204_NO_CONTENT)
