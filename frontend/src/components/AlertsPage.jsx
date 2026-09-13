import { useCallback, useEffect, useState } from "react";
import { BellRing, AlertTriangle } from "lucide-react";
import { listAlerts } from "../api.js";
import { useAlerts } from "../alertsStore.jsx";
import AlertCard from "./AlertCard.jsx";
import MatchModal from "./MatchModal.jsx";

const FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "confirmed", label: "Confirmed" },
  { value: "dismissed", label: "Dismissed" },
  { value: "all", label: "All" },
];

export default function AlertsPage() {
  const { liveAlerts, setPending, markReviewed } = useAlerts();
  const [filter, setFilter] = useState("pending");
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [active, setActive] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const data = await listAlerts(filter, 100);
      setAlerts(data);
      setStatus("ready");
      // Keep the nav badge honest whenever we've just fetched the pending set.
      if (filter === "pending") setPending(data.length);
    } catch (err) {
      setError(err.message || "Could not load alerts");
      setStatus("error");
    }
  }, [filter, setPending]);

  useEffect(() => {
    load();
  }, [load]);

  // When a new alert streams in over WebSocket, refresh the current view if it
  // would belong here (pending/all).
  useEffect(() => {
    if (liveAlerts.length === 0) return;
    if (filter === "pending" || filter === "all") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveAlerts.length]);

  function handleReviewed(updated) {
    // A pending alert just left the pending set: keep the nav badge honest.
    markReviewed(updated.id);
    // Remove from the current list if it no longer matches the filter.
    setAlerts((prev) =>
      prev
        .map((a) => (a.id === updated.id ? updated : a))
        .filter((a) => filter === "all" || a.status === filter)
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Alerts</h1>
          <p>
            Every proposed match, past and present. Confirming or dismissing an alert is recorded in
            the audit log with your officer identity and a timestamp.
          </p>
        </div>
      </div>

      <div className="toolbar" role="tablist" aria-label="Filter alerts by status">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            role="tab"
            aria-selected={filter === f.value}
            className={`chip ${filter === f.value ? "active" : ""}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {status === "loading" && (
        <div className="state">
          <div className="spinner" aria-hidden="true" />
          <p>Loading alerts…</p>
        </div>
      )}

      {status === "error" && (
        <div className="state state--error" role="alert">
          <AlertTriangle size={36} aria-hidden="true" />
          <h3>Couldn&apos;t load alerts</h3>
          <p>{error}</p>
          <button className="btn" onClick={load}>
            Try again
          </button>
        </div>
      )}

      {status === "ready" && alerts.length === 0 && (
        <div className="state">
          <BellRing size={38} aria-hidden="true" />
          <h3>No {filter === "all" ? "" : filter} alerts</h3>
          <p>
            {filter === "pending"
              ? "Nothing is waiting for review right now."
              : "Nothing here yet."}
          </p>
        </div>
      )}

      {status === "ready" && alerts.length > 0 && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
          {alerts.map((a) => (
            <AlertCard key={a.id} alert={a} onOpen={setActive} />
          ))}
        </div>
      )}

      {active && (
        <MatchModal
          alert={active}
          onClose={() => setActive(null)}
          onReviewed={handleReviewed}
        />
      )}
    </div>
  );
}
