import { useEffect, useRef, useState } from "react";
import { Upload, Play, ImageIcon, Film } from "lucide-react";
import { listCameras, processImage, processVideo } from "../api.js";

const REJECT_LABEL = {
  too_small: "too small",
  too_blurry: "too blurry",
  low_det_score: "low detection score",
  no_embedding: "no embedding",
  empty_bbox: "invalid crop",
  cooldown_suppressed: "suppressed (cooldown)",
  no_consensus: "awaiting consensus",
};

// Left half of the Live Monitor: choose a checkpoint + a still or video and run
// it through the pipeline. Matches surface in the live feed (right half) over
// WebSocket; this panel reports the run summary.
export default function UploadPanel() {
  const [cameras, setCameras] = useState([]);
  const [cameraId, setCameraId] = useState("");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [kind, setKind] = useState(null); // 'image' | 'video'
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    listCameras()
      .then((cams) => {
        setCameras(cams);
        if (cams.length) setCameraId(String(cams[0].id));
      })
      .catch(() => setCameras([])); // camera list is non-critical; leave empty
  }, []);

  useEffect(() => {
    return () => previewUrl && URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  function choose(f) {
    if (!f) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const isVideo = f.type.startsWith("video/");
    const isImage = f.type.startsWith("image/");
    if (!isVideo && !isImage) {
      setError("Please choose an image or video file.");
      return;
    }
    setError(null);
    setResult(null);
    setFile(f);
    setKind(isVideo ? "video" : "image");
    setPreviewUrl(URL.createObjectURL(f));
  }

  async function run() {
    if (!file || running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const camArg = cameraId === "" ? undefined : cameraId;
      const res = kind === "video" ? await processVideo(file, camArg) : await processImage(file, camArg);
      setResult(res);
    } catch (err) {
      setError(err.message || "Processing failed");
    } finally {
      setRunning(false);
    }
  }

  const rejectedEntries = result ? Object.entries(result.rejected || {}) : [];

  return (
    <section className="card upload-panel" aria-label="Process a feed">
      <div>
        <h2>Simulated feed</h2>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)", margin: "var(--sp-2) 0 0" }}>
          Upload a still image or a short video to run through the checkpoint pipeline.
        </p>
      </div>

      <div className="field" style={{ margin: 0 }}>
        <label htmlFor="camera">Checkpoint</label>
        <select id="camera" value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
          {cameras.length === 0 && <option value="">No cameras configured</option>}
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.location ? ` — ${c.location}` : ""}
            </option>
          ))}
        </select>
      </div>

      <div
        className="dropzone"
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          choose(e.dataTransfer.files?.[0]);
        }}
      >
        <Upload size={22} aria-hidden="true" style={{ marginBottom: 6 }} />
        <div>{file ? file.name : "Click to choose an image or video"}</div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,video/*"
          onChange={(e) => choose(e.target.files?.[0])}
        />
      </div>

      <div className="upload-canvas-wrap">
        {!previewUrl && (
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ImageIcon size={18} aria-hidden="true" /> Preview appears here
          </span>
        )}
        {previewUrl && kind === "image" && (
          <img src={previewUrl} alt="Selected still for processing" />
        )}
        {previewUrl && kind === "video" && (
          <video src={previewUrl} controls muted playsInline />
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)" }}>
        <button className="btn btn--primary" onClick={run} disabled={!file || running}>
          {kind === "video" ? <Film size={17} aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}
          {running ? "Processing…" : "Process"}
        </button>
        {running && (
          <div className="progress" style={{ flex: 1 }}>
            <div className="progress__track">
              <div className="progress__fill" style={{ width: "100%", opacity: 0.5 }} />
            </div>
            <span>Running pipeline…</span>
          </div>
        )}
      </div>

      {error && (
        <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)", margin: 0 }}>
          {error}
        </div>
      )}

      {result && (
        <div className="banner" style={{ margin: 0 }}>
          <strong>{result.frames_processed}</strong> frame{result.frames_processed === 1 ? "" : "s"} processed ·{" "}
          <strong>{result.faces_detected}</strong> face{result.faces_detected === 1 ? "" : "s"} detected ·{" "}
          <strong>{result.matches?.length || 0}</strong> alert{(result.matches?.length || 0) === 1 ? "" : "s"} raised.
          {rejectedEntries.length > 0 && (
            <div style={{ marginTop: 6, color: "var(--text-faint)", fontSize: "var(--fs-xs)" }}>
              Rejected:{" "}
              {rejectedEntries.map(([r, n], i) => (
                <span key={r}>
                  {i > 0 ? ", " : ""}
                  {REJECT_LABEL[r] || r} ({n})
                </span>
              ))}
            </div>
          )}
          {result.matches?.length === 0 && (
            <div style={{ marginTop: 6, color: "var(--text-faint)", fontSize: "var(--fs-xs)" }}>
              No watchlist matches above threshold. If you expected one, enroll the person first or
              try a clearer capture.
            </div>
          )}
        </div>
      )}
    </section>
  );
}
