import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Video, VideoOff, ScanFace, Wifi, WifiOff } from "lucide-react";
import { listCameras, createCamera, processImage } from "../api.js";
import { createMesh } from "../webrtc.js";

// Opened on a phone (via the QR on the Camera Wall). The phone becomes a named
// camera: it publishes smooth video over WebRTC to the wall AND posts frames to
// the backend for recognition. Query: ?room=<id>&name=<optional label>
export default function StationPage() {
  const [params] = useSearchParams();
  const room = params.get("room") || "default";

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const meshRef = useRef(null);
  const timerRef = useRef(null);
  const canvasRef = useRef(null);
  const inFlightRef = useRef(false);

  const [name, setName] = useState(params.get("name") || "");
  const [cameras, setCameras] = useState([]);
  const [live, setLive] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ sent: 0, alerts: 0 });
  const cameraIdRef = useRef(null);
  const secure = window.isSecureContext;

  useEffect(() => {
    listCameras().then(setCameras).catch(() => setCameras([]));
  }, []);

  const suggested = name || `Camera ${Math.floor(Math.random() * 90 + 10)}`;

  const captureLoop = useCallback(async () => {
    if (inFlightRef.current) return;
    const v = videoRef.current;
    const c = canvasRef.current;
    if (!v || !c || v.videoWidth === 0) return;
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.85));
    if (!blob) return;
    inFlightRef.current = true;
    try {
      const res = await processImage(
        new File([blob], "frame.jpg", { type: "image/jpeg" }),
        cameraIdRef.current ?? undefined
      );
      setStats((s) => ({ sent: s.sent + 1, alerts: s.alerts + (res.matches?.length || 0) }));
    } catch {
      /* transient; keep going */
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  async function goLive() {
    setError(null);
    const label = (name || suggested).trim();
    try {
      // Reuse an existing camera with this name, else create one.
      let cam = cameras.find((c) => c.name === label);
      if (!cam) cam = await createCamera({ name: label, location: "Mobile station" });
      cameraIdRef.current = cam.id;
      setName(label);

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      meshRef.current = createMesh({
        room,
        role: "publisher",
        name: label,
        localStream: stream,
        onStatus: setStatus,
      });
      timerRef.current = setInterval(captureLoop, 2000);
      setLive(true);
    } catch (err) {
      const map = {
        NotAllowedError: "Camera permission denied. Allow access and retry.",
        NotFoundError: "No camera found on this device.",
        NotReadableError: "Camera is in use by another app.",
      };
      setError(map[err.name] || err.message || "Could not start camera");
    }
  }

  function stop() {
    clearInterval(timerRef.current);
    timerRef.current = null;
    if (meshRef.current) { meshRef.current.close(); meshRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    if (videoRef.current) videoRef.current.srcObject = null;
    setLive(false);
    setStatus("idle");
  }

  useEffect(() => () => stop(), []); // cleanup on unmount

  if (!secure) {
    return (
      <div className="page" style={{ maxWidth: 520 }}>
        <div className="banner banner--warn">
          The camera station needs a secure (HTTPS) connection. Open the deployed
          https:// link, not a plain http:// address.
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 640 }}>
      <div className="page-header">
        <div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ScanFace size={24} aria-hidden="true" /> Camera station
          </h1>
          <p>
            This device becomes a live checkpoint camera on the operator&apos;s wall
            (room <code>{room}</code>). Keep this page open and the screen on.
          </p>
        </div>
      </div>

      {error && (
        <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>
          {error}
        </div>
      )}

      {!live && (
        <div className="card" style={{ padding: "var(--sp-5)" }}>
          <div className="field">
            <label htmlFor="st-name">Camera name</label>
            <input
              id="st-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={suggested}
            />
            <span className="hint">Shown on the operator&apos;s wall. Reuses a checkpoint if the name matches.</span>
          </div>
          <button className="btn btn--primary" onClick={goLive}>
            <Video size={18} aria-hidden="true" /> Go live
          </button>
        </div>
      )}

      <div className="upload-canvas-wrap" style={{ marginTop: "var(--sp-4)" }}>
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} playsInline muted style={{ display: live ? "block" : "none" }} />
        {!live && <span>Preview appears here when live</span>}
        <canvas ref={canvasRef} style={{ display: "none" }} />
      </div>

      {live && (
        <>
          <div className="banner" style={{ marginTop: "var(--sp-4)", display: "flex", alignItems: "center", gap: 8 }}>
            {status === "open" ? <Wifi size={16} /> : <WifiOff size={16} />}
            Publishing as <strong>&nbsp;{name}&nbsp;</strong> · link {status} ·{" "}
            {stats.sent} frames analysed · {stats.alerts} alert{stats.alerts === 1 ? "" : "s"}
          </div>
          <button className="btn" onClick={stop} style={{ marginTop: "var(--sp-3)" }}>
            <VideoOff size={17} aria-hidden="true" /> Stop camera
          </button>
        </>
      )}
    </div>
  );
}
