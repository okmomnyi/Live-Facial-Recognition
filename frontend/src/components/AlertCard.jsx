import { assetUrl } from "../api.js";

const CATEGORY_LABEL = { wanted: "Wanted", missing: "Missing", escaped: "Escaped", poi: "POI" };
const STATUS_LABEL = { pending: "Pending review", confirmed: "Confirmed", dismissed: "Dismissed" };

function timeAgo(iso) {
  const then = new Date(iso).getTime();
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function AlertCard({ alert, onOpen, isNew }) {
  const pct = Math.round((alert.confidence || 0) * 100);
  return (
    <button
      type="button"
      className={`alert-card ${isNew ? "alert-card--new" : ""}`}
      onClick={() => onOpen(alert)}
    >
      <img
        className="alert-card__thumb"
        src={assetUrl(alert.capture_path)}
        alt={`Capture matched to ${alert.person_name}`}
        loading="lazy"
      />
      <div className="alert-card__info">
        <div className="alert-card__row">
          <span className="alert-card__name">{alert.person_name}</span>
          <span className="alert-card__conf">{pct}%</span>
        </div>
        <div className="alert-card__row">
          <span className={`badge badge--${alert.person_category}`}>
            {CATEGORY_LABEL[alert.person_category] || alert.person_category}
          </span>
          <span className={`badge badge--${alert.status}`}>
            {STATUS_LABEL[alert.status] || alert.status}
          </span>
        </div>
        <div className="alert-card__sub">
          {alert.camera_name || "Unknown camera"} · {timeAgo(alert.created_at)}
        </div>
      </div>
    </button>
  );
}
