// REST helpers. Base URL comes from VITE_API_BASE (dev: http://localhost:8000).
// Every call surfaces real errors so the UI can show a genuine error state.

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Resolve a server-relative asset path (e.g. "/data/references/x.png") to an
// absolute URL against the backend, which serves the static /data mount.
export function assetUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function handle(res) {
  if (res.status === 204) return null;
  const text = await res.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  if (!res.ok) {
    const message = body?.detail || `Request failed (${res.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return body;
}

function req(path, options = {}) {
  return fetch(`${API_BASE}${path}`, options).then(handle);
}

// ------------------------------- Persons ---------------------------------

export const listPersons = () => req("/api/persons");
export const getPerson = (id) => req(`/api/persons/${id}`);
export const deletePerson = (id) => req(`/api/persons/${id}`, { method: "DELETE" });

export function enrollPerson({ name, category, notes, images }) {
  const form = new FormData();
  form.append("name", name);
  form.append("category", category);
  if (notes) form.append("notes", notes);
  for (const file of images) form.append("images", file);
  return req("/api/enroll", { method: "POST", body: form });
}

// ------------------------------- Cameras ---------------------------------

export const listCameras = () => req("/api/cameras");

// ------------------------------ Processing -------------------------------

export function processImage(file, cameraId) {
  const form = new FormData();
  form.append("image", file);
  if (cameraId != null && cameraId !== "") form.append("camera_id", String(cameraId));
  return req("/api/process/image", { method: "POST", body: form });
}

export function processVideo(file, cameraId) {
  const form = new FormData();
  form.append("video", file);
  if (cameraId != null && cameraId !== "") form.append("camera_id", String(cameraId));
  return req("/api/process/video", { method: "POST", body: form });
}

// -------------------------------- Alerts ---------------------------------

export const listAlerts = (status = "all", limit = 50) =>
  req(`/api/alerts?status=${encodeURIComponent(status)}&limit=${limit}`);

export const reviewAlert = (id, action, reviewer = "officer") =>
  req(`/api/alerts/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reviewer }),
  });
