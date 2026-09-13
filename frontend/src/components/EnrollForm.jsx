import { useRef, useState } from "react";
import { X, Upload, CheckCircle2, XCircle } from "lucide-react";
import { enrollPerson } from "../api.js";

const CATEGORIES = [
  { value: "wanted", label: "Wanted" },
  { value: "missing", label: "Missing person" },
  { value: "escaped", label: "Escaped" },
  { value: "poi", label: "Person of interest" },
];

const REJECT_REASON = {
  no_face: "No face detected",
  multiple_faces: "More than one face in the photo",
  too_small: "Face too small",
  too_blurry: "Photo too blurry",
  low_det_score: "Low-quality detection",
  low_quality: "Failed the quality gate",
};

export default function EnrollForm({ onClose, onEnrolled }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("poi");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // enroll response for per-image status
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const pickFiles = (fileList) => {
    const imgs = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => [...prev, ...imgs]);
  };

  const canSubmit = name.trim() && files.length > 0 && !submitting;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await enrollPerson({ name: name.trim(), category, notes: notes.trim(), images: files });
      setResult(res);
      onEnrolled && onEnrolled(res.person);
    } catch (err) {
      setError(err.message || "Enrollment failed");
    } finally {
      setSubmitting(false);
    }
  }

  // After a successful enroll we show the per-image breakdown, then let the
  // officer close or enroll another.
  if (result) {
    const okCount = result.images.filter((i) => i.status === "ok").length;
    return (
      <Backdrop onClose={onClose}>
        <header className="modal__header">
          <h2>Enrolled {result.person.name}</h2>
          <CloseButton onClose={onClose} />
        </header>
        <div className="modal__body">
          <p style={{ color: "var(--text-muted)", marginTop: 0 }}>
            {okCount} of {result.images.length} photo{result.images.length === 1 ? "" : "s"} produced
            a usable reference embedding.
          </p>
          <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "var(--sp-2)" }}>
            {result.images.map((img, i) => (
              <li
                key={i}
                style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)", fontSize: "var(--fs-sm)" }}
              >
                {img.status === "ok" ? (
                  <CheckCircle2 size={18} style={{ color: "var(--accent)" }} aria-hidden="true" />
                ) : (
                  <XCircle size={18} style={{ color: "var(--danger)" }} aria-hidden="true" />
                )}
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {img.filename}
                </span>
                <span style={{ color: "var(--text-faint)" }}>
                  {img.status === "ok"
                    ? `quality ${(img.quality ?? 0).toFixed(2)}`
                    : REJECT_REASON[img.reason] || img.reason || "rejected"}
                </span>
              </li>
            ))}
          </ul>
          {okCount === 0 && (
            <div className="banner banner--warn" style={{ marginTop: "var(--sp-4)" }}>
              No usable references were extracted. The person was created but has no embeddings, so
              they won&apos;t match. Try clearer, front-facing photos with a single visible face.
            </div>
          )}
        </div>
        <footer className="modal__footer">
          <button className="btn btn--primary" onClick={onClose}>
            Done
          </button>
        </footer>
      </Backdrop>
    );
  }

  return (
    <Backdrop onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <header className="modal__header">
          <h2>Enroll person of interest</h2>
          <CloseButton onClose={onClose} />
        </header>
        <div className="modal__body">
          {error && (
            <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>
              {error}
            </div>
          )}

          <div className="field">
            <label htmlFor="enroll-name">Full name</label>
            <input
              id="enroll-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Jane Doe"
              required
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="enroll-category">Category</label>
            <select id="enroll-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="enroll-notes">Notes (optional)</label>
            <textarea
              id="enroll-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Case reference, distinguishing details, source of the photo…"
            />
          </div>

          <div className="field">
            <label>Reference photographs</label>
            <span className="hint">
              One clear, front-facing face per photo. Two or more angles improves matching.
            </span>
            <div
              className={`dropzone ${dragging ? "dropzone--active" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  inputRef.current?.click();
                }
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pickFiles(e.dataTransfer.files);
              }}
            >
              <Upload size={22} aria-hidden="true" style={{ marginBottom: 6 }} />
              <div>Click to choose photos, or drag them here</div>
              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => pickFiles(e.target.files)}
              />
            </div>
            {files.length > 0 && (
              <ul style={{ listStyle: "none", padding: 0, marginTop: "var(--sp-2)", display: "grid", gap: 4 }}>
                {files.map((f, i) => (
                  <li
                    key={i}
                    style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}
                  >
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      style={{ padding: "0 6px", border: "none" }}
                      onClick={() => setFiles(files.filter((_, j) => j !== i))}
                      aria-label={`Remove ${f.name}`}
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <footer className="modal__footer">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
            {submitting ? "Enrolling…" : `Enroll${files.length ? ` (${files.length})` : ""}`}
          </button>
        </footer>
      </form>
    </Backdrop>
  );
}

function Backdrop({ children, onClose }) {
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true">
        {children}
      </div>
    </div>
  );
}

function CloseButton({ onClose }) {
  return (
    <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} aria-label="Close">
      <X size={18} />
    </button>
  );
}
