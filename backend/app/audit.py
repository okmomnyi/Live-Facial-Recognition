"""Audit logging helper. Every meaningful action (enrollment, alert creation,
alert review, deletion) writes one row here with actor, action, subject, detail."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog


async def log_action(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: int | None = None,
    detail: dict | None = None,
    commit: bool = True,
) -> AuditLog:
    """Insert an audit_log row. Caller controls whether to commit (so it can be
    part of a larger transaction)."""
    entry = AuditLog(
        actor=actor,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        detail=detail,
    )
    session.add(entry)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return entry
