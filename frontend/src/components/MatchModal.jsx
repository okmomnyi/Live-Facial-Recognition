import { useState } from "react";
import { X, Check, Ban } from "lucide-react";
import { assetUrl, reviewAlert } from "../api.js";

const CATEGORY_LABEL = { wanted: "Wanted", missing: "Missing", escaped: "Escaped", poi: "POI" };

// Side-by-side review of a proposed match. The officer is the decision-maker;
// the UI stays deliberately neutral (no green/red "correct" signalling on the
// confidence bar) so it doesn't nudge the call.
export default function MatchModal({ alert, onClose, onReviewed }) {
  const [busy, setBusy] = useState(null); // 'confirm' | 'dismiss' | null
  const [error, setError] = useState(null);

  const pct = Math.round((alert.confidence || 0) * 100);
  const isPending = alert.status === "pending";

  async function review(action) {
    setBusy(action);
    setError(null);
    try {
      const updated = await reviewAlert(alert.id, action);
      onReviewed && onReviewed(updated);
      onClose();
    } catch (err) {
      setError(err.message || "Review failed");
      setBusy(null);
    }
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="Review match">
        <header className="modal__header">
          <div>
            <h2>{alert.person_name}</h2>
            <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: 6, alignItems: "center" }}>
              <span className={`badge badge--${alert.person_category}`}>
                {CATEGORY_LABEL[alert.person_category] || alert.person_category}
              </span>
              <span className="alert-card__sub">
                {alert.camera_name || "Unknown camera"} ·{" "}
                {new Date(alert.created_at).toLocaleString()}
              </span>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <div className="modal__body">
          <div className="compare">
            <figure>
              <figcaption>Watchlist reference</figcaption>
              <img
                src={assetUrl(alert.ref_image_path)}
                alt={`Enrolled reference photo of ${alert.person_name}`}
              />
            </figure>
            <figure>
              <figcaption>Checkpoint capture</figcaption>
              <img
                src={assetUrl(alert.capture_path)}
                alt={`Face captured at ${alert.camera_name || "the checkpoint"}`}
              />
            </figure>
          </div>

          <div className="confidence">
            <div className="confidence__value">{pct}%</div>
            <div
              className="confidence__bar"
              role="meter"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Match confidence"
            >
              <div className="confidence__fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="confidence__note">
              Cosine similarity of face embeddings. This is a proposal — you decide.
            </div>
          </div>

          {error && (
            <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>
              {error}
            </div>
          )}

          {!isPending && (
            <div className="banner">
              Already {alert.status}
              {alert.reviewed_by ? ` by ${alert.reviewed_by}` : ""}
              {alert.reviewed_at ? ` on ${new Date(alert.reviewed_at).toLocaleString()}` : ""}.
            </div>
          )}
        </div>

        {isPending && (
          <footer className="modal__footer">
            <button
              className="btn btn--ghost"
              onClick={() => review("dismiss")}
              disabled={busy !== null}
            >
              <Ban size={17} aria-hidden="true" />
              {busy === "dismiss" ? "Dismissing…" : "Dismiss"}
            </button>
            <button
              className="btn btn--primary"
              onClick={() => review("confirm")}
              disabled={busy !== null}
            >
              <Check size={17} aria-hidden="true" />
              {busy === "confirm" ? "Confirming…" : "Confirm match"}
            </button>
          </footer>
        )}
      </div>
    </div>
  );
}
