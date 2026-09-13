import { useState } from "react";
import { Trash2, UserRound } from "lucide-react";
import { assetUrl } from "../api.js";

const CATEGORY_LABEL = {
  wanted: "Wanted",
  missing: "Missing",
  escaped: "Escaped",
  poi: "POI",
};

export default function PersonCard({ person, onDelete }) {
  const [deleting, setDeleting] = useState(false);
  const [imgError, setImgError] = useState(false);
  const thumb = person.thumbnail_path ? assetUrl(person.thumbnail_path) : null;

  async function handleDelete() {
    if (!window.confirm(`Remove ${person.name} from the watchlist? This cannot be undone.`)) {
      return;
    }
    setDeleting(true);
    try {
      await onDelete(person.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <article className="card person-card">
      {thumb && !imgError ? (
        <img
          className="person-card__thumb"
          src={thumb}
          alt={`Reference photograph of ${person.name}`}
          loading="lazy"
          onError={() => setImgError(true)}
        />
      ) : (
        <div className="person-card__thumb person-card__thumb--empty" aria-hidden="true">
          <UserRound size={40} />
        </div>
      )}

      <div className="person-card__body">
        <div className="person-card__name">{person.name}</div>
        <div className="person-card__meta">
          {person.ref_count} reference{person.ref_count === 1 ? "" : "s"}
          {person.notes ? ` · ${person.notes}` : ""}
        </div>
        <div className="person-card__foot">
          <span className={`badge badge--${person.category}`}>
            {CATEGORY_LABEL[person.category] || person.category}
          </span>
          <button
            type="button"
            className="btn btn--danger btn--sm"
            onClick={handleDelete}
            disabled={deleting}
            aria-label={`Remove ${person.name}`}
          >
            <Trash2 size={15} aria-hidden="true" />
            {deleting ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </article>
  );
}
