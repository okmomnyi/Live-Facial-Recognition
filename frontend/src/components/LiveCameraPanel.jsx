import { useCallback, useEffect, useRef, useState } from "react";
import { Video, VideoOff, Camera, RefreshCw } from "lucide-react";
import { listCameras, processImage } from "../api.js";

// Turns the device's own camera (phone front/back, laptop webcam, or any
// connected camera) into a live checkpoint feed by grabbing a frame every
// interval and POSTing it to the existing /api/process/image endpoint. Matches
// surface in the shared live-alerts feed over WebSocket. Requires HTTPS + camera
// permission (both satisfied on the deployed site).
export default function LiveCameraPanel() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const inFlightRef = useRef(false);

  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState("");
  const [cameras, setCameras] = useState([]);
  const [cameraId, setCameraId] = useState("");
  const [intervalMs, setIntervalMs] = useState(2000);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ sent: 0, faces: 0, alerts: 0 });
  const [lastAt, setLastAt] = useState(null);

  const secure = window.isSecureContext;

  useEffect(() => {
    listCameras()
      .then((c) => {
        setCameras(c);
        if (c.length) setCameraId(String(c[0].id));
      })
      .catch(() => setCameras([]));
  }, []);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startStream = useCallback(async (preferredId) => {
    setError(null);
    stopStream();
    const constraints = {
      video: preferredId
        ? { deviceId: { exact: preferredId } }
        : { facingMode: "environment" }, // back camera on phones by default
      audio: false,
    };
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      // Labels are only populated after permission is granted.
      const all = await navigator.mediaDevices.enumerateDevices();
      const cams = all.filter((d) => d.kind === "videoinput");
      setDevices(cams);
      const active = stream.getVideoTracks()[0]?.getSettings?.().deviceId;
      if (active) setDeviceId(active);
      return true;
    } catch (err) {
      const map = {
        NotAllowedError: "Camera permission denied. Allow camera access and try again.",
        NotFoundError: "No camera found on this device.",
        NotReadableError: "The camera is in use by another app.",
        SecurityError: "Camera requires a secure (HTTPS) connection.",
      };
      setError(map[err.name] || `Could not start camera: ${err.message}`);
      return false;
    }
  }, [stopStream]);

  const captureAndSend = useCallback(async () => {
    if (inFlightRef.current) return; // don't overlap requests
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
    if (!blob) return;
    const file = new File([blob], "frame.jpg", { type: "image/jpeg" });
    inFlightRef.current = true;
    try {
      const res = await processImage(file, cameraId === "" ? undefined : cameraId);
      setStats((s) => ({
        sent: s.sent + 1,
        faces: s.faces + (res.faces_detected || 0),
        alerts: s.alerts + (res.matches?.length || 0),
      }));
      setLastAt(new Date());
    } catch (err) {
      setError(err.message || "Frame send failed");
    } finally {
      inFlightRef.current = false;
    }
  }, [cameraId]);

  async function start() {
    const ok = await startStream(deviceId || undefined);
    if (!ok) return;
    setStats({ sent: 0, faces: 0, alerts: 0 });
    setRunning(true);
  }

  function stop() {
    setRunning(false);
    clearInterval(timerRef.current);
    timerRef.current = null;
    stopStream();
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  // Drive the capture loop while running.
  useEffect(() => {
    if (!running) return;
    timerRef.current = setInterval(captureAndSend, intervalMs);
    return () => clearInterval(timerRef.current);
  }, [running, intervalMs, captureAndSend]);

  // Cleanup on unmount.
  useEffect(() => () => stop(), []); // eslint-disable-line react-hooks/exhaustive-deps

  async function switchDevice(id) {
    setDeviceId(id);
    if (running) await startStream(id);
  }

  if (!secure) {
    return (
      <section className="card upload-panel" aria-label="Live camera">
        <div className="banner banner--warn">
          Live camera needs a secure (HTTPS) connection. Open the deployed site
          (https://…) rather than an http:// address.
        </div>
      </section>
    );
  }

  return (
    <section className="card upload-panel" aria-label="Live camera">
      <div>
        <h2>Live camera</h2>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)", margin: "var(--sp-2) 0 0" }}>
          Use this device&apos;s camera as a checkpoint feed. Frames are sent to the pipeline every
          interval; matches appear in the alerts feed.
        </p>
      </div>

      <div style={{ display: "flex", gap: "var(--sp-3)", flexWrap: "wrap" }}>
        <div className="field" style={{ margin: 0, flex: "1 1 150px" }}>
          <label htmlFor="lc-checkpoint">Checkpoint</label>
          <select id="lc-checkpoint" value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
            {cameras.length === 0 && <option value="">No cameras configured</option>}
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ margin: 0, flex: "1 1 150px" }}>
          <label htmlFor="lc-device">Camera device</label>
          <select
            id="lc-device"
            value={deviceId}
            onChange={(e) => switchDevice(e.target.value)}
            disabled={devices.length === 0}
          >
            {devices.length === 0 && <option value="">Start to detect cameras</option>}
            {devices.map((d, i) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Camera ${i + 1}`}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ margin: 0, flex: "0 1 130px" }}>
          <label htmlFor="lc-interval">Every</label>
          <select id="lc-interval" value={intervalMs} onChange={(e) => setIntervalMs(Number(e.target.value))}>
            <option value={1000}>1 second</option>
            <option value={2000}>2 seconds</option>
            <option value={3000}>3 seconds</option>
            <option value={5000}>5 seconds</option>
          </select>
        </div>
      </div>

      <div className="upload-canvas-wrap">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} playsInline muted style={{ display: running ? "block" : "none" }} />
        {!running && (
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Camera size={18} aria-hidden="true" /> Camera preview appears here
          </span>
        )}
        <canvas ref={canvasRef} style={{ display: "none" }} />
      </div>

      {error && (
        <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)", margin: 0 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)", flexWrap: "wrap" }}>
        {!running ? (
          <button className="btn btn--primary" onClick={start}>
            <Video size={17} aria-hidden="true" /> Start live capture
          </button>
        ) : (
          <button className="btn" onClick={stop}>
            <VideoOff size={17} aria-hidden="true" /> Stop
          </button>
        )}
        {running && (
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => startStream(deviceId || undefined)}
            title="Restart the camera stream"
          >
            <RefreshCw size={15} aria-hidden="true" /> Refresh
          </button>
        )}
      </div>

      {(running || stats.sent > 0) && (
        <div className="banner" style={{ margin: 0 }}>
          <strong>{stats.sent}</strong> frame{stats.sent === 1 ? "" : "s"} sent ·{" "}
          <strong>{stats.faces}</strong> face{stats.faces === 1 ? "" : "s"} detected ·{" "}
          <strong>{stats.alerts}</strong> alert{stats.alerts === 1 ? "" : "s"} raised
          {lastAt ? ` · last ${lastAt.toLocaleTimeString()}` : ""}
          {running && (
            <div style={{ marginTop: 4, color: "var(--text-faint)", fontSize: "var(--fs-xs)" }}>
              Capturing live. Matches stream into the alerts feed on the right.
            </div>
          )}
        </div>
      )}
    </section>
  );
}
