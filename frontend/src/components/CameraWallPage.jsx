import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { QrCode, RefreshCw, Cctv, X } from "lucide-react";
import { useAlerts } from "../alertsStore.jsx";
import { createMesh } from "../webrtc.js";
import { assetUrl } from "../api.js";
import MatchModal from "./MatchModal.jsx";

const ALERT_HIGHLIGHT_MS = 20000; // a tile stays "hot" for 20s after a match

function useRoom() {
  const [room] = useState(() => {
    try {
      const saved = localStorage.getItem("lfr_wall_room");
      if (saved) return saved;
    } catch { /* ignore */ }
    const id = "room_" + Math.random().toString(36).slice(2, 8);
    try { localStorage.setItem("lfr_wall_room", id); } catch { /* ignore */ }
    return id;
  });
  return room;
}

function Tile({ name, stream, hot, alert, onOpenAlert }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && stream) ref.current.srcObject = stream;
  }, [stream]);
  return (
    <div className={`wall-tile ${hot ? "wall-tile--hot" : ""}`}>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video ref={ref} autoPlay playsInline muted />
      <div className="wall-tile__bar">
        <span className="wall-tile__name">{name}</span>
        {hot && alert && (
          <button
            className="wall-tile__alert"
            onClick={() => onOpenAlert(alert)}
            title="Review match"
          >
            {alert.person_name} · {Math.round((alert.confidence || 0) * 100)}%
          </button>
        )}
      </div>
    </div>
  );
}

export default function CameraWallPage() {
  const room = useRoom();
  const { liveAlerts, markReviewed } = useAlerts();
  const [tiles, setTiles] = useState([]); // [{peerId, name}]
  const [qr, setQr] = useState(null);
  const [status, setStatus] = useState("connecting");
  const [active, setActive] = useState(null);
  const streams = useRef(new Map());
  const meshRef = useRef(null);

  const stationUrl = `${window.location.origin}/station?room=${room}`;

  useEffect(() => {
    QRCode.toDataURL(stationUrl, { margin: 1, width: 240 }).then(setQr).catch(() => setQr(null));
  }, [stationUrl]);

  const onRemoteStream = useCallback((peerId, stream, name) => {
    streams.current.set(peerId, stream);
    setTiles((prev) => {
      if (prev.some((t) => t.peerId === peerId)) {
        return prev.map((t) => (t.peerId === peerId ? { ...t, name: name || t.name } : t));
      }
      return [...prev, { peerId, name: name || peerId }];
    });
  }, []);

  const onPeerLeft = useCallback((peerId) => {
    streams.current.delete(peerId);
    setTiles((prev) => prev.filter((t) => t.peerId !== peerId));
  }, []);

  useEffect(() => {
    const mesh = createMesh({
      room,
      role: "viewer",
      name: "operator",
      onRemoteStream,
      onPeerLeft,
      onStatus: setStatus,
    });
    meshRef.current = mesh;
    return () => mesh.close();
  }, [room, onRemoteStream, onPeerLeft]);

  // Most-recent alert per camera name, for tile highlighting ("trail" the target).
  const now = Date.now();
  const latestByCamera = {};
  for (const a of liveAlerts) {
    const t = new Date(a.created_at).getTime();
    if (!latestByCamera[a.camera_name] || t > new Date(latestByCamera[a.camera_name].created_at).getTime()) {
      latestByCamera[a.camera_name] = a;
    }
  }

  function newRoom() {
    const id = "room_" + Math.random().toString(36).slice(2, 8);
    try { localStorage.setItem("lfr_wall_room", id); } catch { /* ignore */ }
    window.location.reload();
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Cctv size={24} aria-hidden="true" /> Camera Wall
          </h1>
          <p>
            Live video from every connected phone. When a watchlist match fires, that
            camera lights up so you can follow the target across cameras. Scan the code
            with a phone to add it as a camera.
          </p>
        </div>
        <div className="navbar__ws" title="Signaling link">
          <span className={`dot ${status === "open" ? "live" : "down"}`} aria-hidden="true" />
          {status === "open" ? "Wall online" : "Connecting…"}
        </div>
      </div>

      <div className="wall-layout">
        <aside className="card wall-add">
          <h2 style={{ fontSize: "var(--fs-md)", display: "flex", alignItems: "center", gap: 6 }}>
            <QrCode size={18} aria-hidden="true" /> Add a camera
          </h2>
          {qr ? (
            <img src={qr} alt="QR code to add this device as a camera" width={200} height={200} />
          ) : (
            <div className="state" style={{ padding: "var(--sp-5)" }}><div className="spinner" /></div>
          )}
          <p className="hint" style={{ wordBreak: "break-all" }}>
            Scan with a phone camera, or open:<br />
            <a href={stationUrl}>{stationUrl}</a>
          </p>
          <button className="btn btn--ghost btn--sm" onClick={newRoom} title="Start a fresh wall">
            <RefreshCw size={14} aria-hidden="true" /> New room
          </button>
        </aside>

        <div className="wall-main">
          {tiles.length === 0 ? (
            <div className="state" style={{ padding: "var(--sp-8) var(--sp-4)" }}>
              <Cctv size={40} aria-hidden="true" />
              <h3>No cameras connected</h3>
              <p>Scan the QR code with a phone to add it as a live camera.</p>
            </div>
          ) : (
            <div className="wall-grid">
              {tiles.map((t) => {
                const alert = latestByCamera[t.name];
                const hot = !!alert && now - new Date(alert.created_at).getTime() < ALERT_HIGHLIGHT_MS;
                return (
                  <Tile
                    key={t.peerId}
                    name={t.name}
                    stream={streams.current.get(t.peerId)}
                    hot={hot}
                    alert={alert}
                    onOpenAlert={setActive}
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>

      {active && (
        <MatchModal alert={active} onClose={() => setActive(null)} onReviewed={(u) => markReviewed(u.id)} />
      )}
    </div>
  );
}
