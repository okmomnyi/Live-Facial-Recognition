import { NavLink } from "react-router-dom";
import { ScanFace, Users, MonitorPlay, BellRing, Cctv } from "lucide-react";
import { useAlerts } from "../alertsStore.jsx";

const WS_LABEL = {
  open: ["live", "Live feed connected"],
  connecting: ["", "Connecting to live feed"],
  reconnecting: ["", "Reconnecting to live feed"],
  closed: ["down", "Live feed disconnected"],
};

export default function NavBar() {
  const { wsStatus, pendingCount } = useAlerts();
  const [dotClass, wsTitle] = WS_LABEL[wsStatus] || ["", "Live feed"];

  return (
    <nav className="navbar" aria-label="Primary">
      <div className="navbar__brand">
        <ScanFace size={26} aria-hidden="true" />
        <span>
          LFR Console
          <small>Watchlist Matching</small>
        </span>
      </div>

      <div className="navbar__links">
        <NavLink to="/" className="navbar__link" end>
          <Users size={18} aria-hidden="true" />
          <span className="label">Watchlist</span>
        </NavLink>
        <NavLink to="/monitor" className="navbar__link">
          <MonitorPlay size={18} aria-hidden="true" />
          <span className="label">Live Monitor</span>
        </NavLink>
        <NavLink to="/wall" className="navbar__link">
          <Cctv size={18} aria-hidden="true" />
          <span className="label">Camera Wall</span>
        </NavLink>
        <NavLink to="/alerts" className="navbar__link">
          <BellRing size={18} aria-hidden="true" />
          <span className="label">Alerts</span>
          {pendingCount > 0 && (
            <span className="navbar__badge" aria-label={`${pendingCount} pending`}>
              {pendingCount}
            </span>
          )}
        </NavLink>
      </div>

      <div className="navbar__ws" title={wsTitle}>
        <span className={`dot ${dotClass}`} aria-hidden="true" />
        <span>{wsStatus === "open" ? "Live" : "Offline"}</span>
        <span className="sr-only">{wsTitle}</span>
      </div>
    </nav>
  );
}
