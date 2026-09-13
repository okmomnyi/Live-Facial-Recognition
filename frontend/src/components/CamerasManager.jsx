import { useEffect, useState } from "react";
import { X, Plus, Trash2, Cctv } from "lucide-react";
import { listCameras, createCamera, deleteCamera } from "../api.js";

// Modal to view, add, and remove checkpoint cameras. Delete is FK-safe on the
// backend (409 if a camera still has alerts) — we surface that message.
export default function CamerasManager({ onClose, onChanged }) {
  const [cameras, setCameras] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setStatus("loading");
    try {
      setCameras(await listCameras());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e) {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await createCamera({ name: name.trim(), location: location.trim() });
      setName("");
      setLocation("");
      await load();
      onChanged && onChanged();
    } catch (err) {
      setError(err.message || "Could not add camera");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id) {
    if (!window.confirm("Remove this checkpoint camera?")) return;
    setBusyId(id);
    setError(null);
    try {
      await deleteCamera(id);
      await load();
      onChanged && onChanged();
    } catch (err) {
      // FK-safe backend returns 409 with a readable message.
      setError(err.message || "Could not remove camera");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Manage cameras" style={{ maxWidth: 560 }}>
        <header className="modal__header">
          <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Cctv size={20} aria-hidden="true" /> Checkpoint cameras
          </h2>
          <button className="btn btn--ghost btn--sm" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <div className="modal__body">
          {error && (
            <div className="banner" role="alert" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>
              {error}
            </div>
          )}

          <form onSubmit={add} style={{ display: "flex", gap: "var(--sp-2)", alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field" style={{ margin: 0, flex: "1 1 160px" }}>
              <label htmlFor="cam-name">Name</label>
              <input id="cam-name" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. My Phone" />
            </div>
            <div className="field" style={{ margin: 0, flex: "1 1 160px" }}>
              <label htmlFor="cam-loc">Location (optional)</label>
              <input id="cam-loc" type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Front gate" />
            </div>
            <button type="submit" className="btn btn--primary" disabled={!name.trim() || saving}>
              <Plus size={16} aria-hidden="true" />
              {saving ? "Adding…" : "Add"}
            </button>
          </form>

          <div style={{ marginTop: "var(--sp-5)" }}>
            {status === "loading" && (
              <div className="state" style={{ padding: "var(--sp-5)" }}>
                <div className="spinner" aria-hidden="true" />
              </div>
            )}
            {status === "ready" && cameras.length === 0 && (
              <p style={{ color: "var(--text-faint)" }}>No cameras yet. Add one above.</p>
            )}
            {status === "ready" &&
              cameras.map((c) => (
                <div
                  key={c.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "var(--sp-3) 0",
                    borderTop: "1px solid var(--border)",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{c.name}</div>
                    <div className="alert-card__sub">
                      {c.location || "No location"} · {c.source_type}
                    </div>
                  </div>
                  <button
                    className="btn btn--danger btn--sm"
                    onClick={() => remove(c.id)}
                    disabled={busyId === c.id}
                    aria-label={`Remove ${c.name}`}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                    {busyId === c.id ? "…" : "Remove"}
                  </button>
                </div>
              ))}
          </div>
        </div>

        <footer className="modal__footer">
          <button className="btn" onClick={onClose}>
            Done
          </button>
        </footer>
      </div>
    </div>
  );
}
