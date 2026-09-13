import { useState } from "react";
import { Radio, Inbox } from "lucide-react";
import { useAlerts } from "../alertsStore.jsx";
import UploadPanel from "./UploadPanel.jsx";
import AlertCard from "./AlertCard.jsx";
import MatchModal from "./MatchModal.jsx";

export default function LiveMonitorPage() {
  const { liveAlerts, wsStatus, markReviewed } = useAlerts();
  const [active, setActive] = useState(null);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Live Monitor</h1>
          <p>
            Feed processing on the left; matches stream in on the right as the pipeline finds them.
            Click an alert to review the reference and capture side by side.
          </p>
        </div>
      </div>

      <div className="monitor">
        <UploadPanel />

        <section className="card alert-feed" aria-label="Live alerts">
          <div className="alert-feed__head">
            <h2 style={{ fontSize: "var(--fs-md)" }}>Live alerts</h2>
            <span className="navbar__ws" title="Live feed status">
              <Radio size={14} aria-hidden="true" />
              <span className={`dot ${wsStatus === "open" ? "live" : "down"}`} aria-hidden="true" />
              {wsStatus === "open" ? "Connected" : "Offline"}
            </span>
          </div>

          {liveAlerts.length === 0 ? (
            <div className="state" style={{ padding: "var(--sp-6) var(--sp-4)" }}>
              <Inbox size={32} aria-hidden="true" />
              <p style={{ margin: 0 }}>
                No alerts yet this session. Process a feed containing an enrolled face to see matches
                appear here in real time.
              </p>
            </div>
          ) : (
            liveAlerts.map((a) => (
              <AlertCard key={a.id} alert={a} isNew={a._new} onOpen={setActive} />
            ))
          )}
        </section>
      </div>

      {active && (
        <MatchModal
          alert={active}
          onClose={() => setActive(null)}
          onReviewed={(updated) => markReviewed(updated.id)}
        />
      )}
    </div>
  );
}
