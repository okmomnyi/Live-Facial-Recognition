# LFR Prototype — Live Facial Recognition for Watchlist Matching

A working end-to-end prototype of a checkpoint-style face-matching system.
An operator enrolls people onto a watchlist with reference photos; a processing
service detects faces in uploaded images or video, computes embeddings, and
searches the watchlist; matches above a configurable threshold surface to an
officer dashboard over WebSocket for **human review**. Every enrollment and
every review decision is audit-logged.

> **Research prototype for academic evaluation only.** It uses pretrained,
> open-source face models on consented sample data and contains no government or
> law-enforcement records. Nothing is dispatched automatically: every match is a
> proposal an officer must confirm or dismiss. Read
> [`samples/README.md`](samples/README.md) for the consent and data-handling
> rules before enrolling anyone.

---

## What's in the box

| Layer      | Technology |
|------------|------------|
| Frontend   | React 18 + Vite (JavaScript), plain CSS, `react-router-dom`, `lucide-react` icons |
| Backend    | Python 3.11, FastAPI, Uvicorn |
| Database   | Postgres 16 + pgvector (cosine similarity search) |
| Face models| InsightFace `buffalo_sc` (SCRFD-500MF detector + MobileFaceNet), ONNX Runtime on CPU |
| Realtime   | Native WebSocket (`/ws/alerts`) |
| Dev/deploy | Docker Compose locally; Neon + Hugging Face Spaces + Vercel for free-tier hosting |

There is **no model training**. The pretrained models turn each face into a
512-dimensional embedding; enrollment stores it, matching does a cosine-similarity
search. "Real-time" here means end-to-end alert latency under ~2 seconds on CPU
for a checkpoint's walking-pace load, not 30 fps video.

---

## Prerequisites

- **Docker** and **Docker Compose** (Docker Desktop on Mac/Windows includes both).
- **Node 20+** and npm (for the frontend dev server).
- ~1 GB free disk for the Postgres image, Python deps, and the ~30 MB face models
  (downloaded automatically on first use and cached in a Docker volume).

No GPU is required.

---

## Run it locally (clone to running in under 10 minutes)

```bash
# 1. Configure. The defaults in .env.example work out of the box for local dev.
cp .env.example .env

# 2. Start Postgres (with pgvector) + the FastAPI backend.
#    Use `docker compose` (v2+); `docker-compose` with a hyphen is the older alias
#    and may not exist on newer Docker installs.
docker compose up --build
#    - db comes up on localhost:5432 and runs db/init.sql on first start
#    - backend comes up on http://localhost:8000
#    - the InsightFace models download on the first request that needs them
#      (first enroll/process call takes a few extra seconds; cached after that)

# 3. In a second terminal, start the frontend dev server.
cd frontend
npm install
npm run dev
#    - opens http://localhost:5173
```

Then open **http://localhost:5173** and:

1. **Watchlist** → *Enroll person*: add someone with 1–2 consented reference
   photos. Each photo's per-image status shows whether a usable embedding was
   extracted.
2. **Live Monitor**: pick a checkpoint, upload a still image or a short video of
   an enrolled person, and press *Process*. Matches stream into the live feed on
   the right.
3. **Alerts**: click an alert to see the reference and the capture side by side,
   then *Confirm* or *Dismiss*. The Alerts page and the audit log both update.

### Verifying the face models load

The backend downloads and runs the models on first use. To check inference in
isolation without the UI:

```bash
# No argument: runs on a synthetic image. It detects 0 faces, but reaching that
# point proves the model downloaded and inference ran. A good pre-demo warmup.
docker compose exec backend python scripts/smoke_face.py

# Optional: point it at any image reachable inside the container to see real
# detections (e.g. a consented reference already saved by an enrollment):
docker compose exec backend python scripts/smoke_face.py /data/references/<file>.png
```

### Frontend API base URL

The frontend talks to `VITE_API_BASE`, which defaults to
`http://localhost:8000`. Override it per deploy (see below) with a `.env` file in
`frontend/` or a Vercel environment variable:

```
VITE_API_BASE=https://your-backend-host
```

---

## Configuration

All backend tuning is via environment variables (see
[`.env.example`](.env.example)). The ones you're most likely to touch:

| Variable | Default | Meaning |
|----------|---------|---------|
| `MATCH_THRESHOLD` | `0.42` | Cosine similarity at or above which a face counts as a match. Higher = fewer false accepts, more false rejects. |
| `DET_THRESHOLD` | `0.5` | Minimum detector confidence to keep a face. |
| `MIN_FACE_SIZE` | `80` | Minimum face box size (px) to consider. |
| `FRAME_SKIP` | `5` | Process every Nth video frame. |
| `CONSENSUS_FRAMES` | `3` | Matches of the same person on the same track needed before a video alert fires. |
| `CONSENSUS_WINDOW_SECONDS` | `5` | Window those consensus frames must fall within. |
| `ALERT_COOLDOWN_SECONDS` | `30` | Suppress repeat alerts for the same (person, camera) pair. |

Tune `MATCH_THRESHOLD` with the evaluation harness below rather than by guessing.

---

## Project layout

```
lfr-prototype/
├── db/init.sql            # database schema (source of truth)
├── docker-compose.yml
├── backend/               # FastAPI app, face pipeline, tests, eval harness
│   └── app/               # routes, services (face_service, pipeline, tracker), models
│   └── eval/evaluate.py   # threshold sweep + bias audit
├── frontend/              # React + Vite dashboard
│   └── src/components/    # Watchlist, Live Monitor, Alerts, Match review
├── samples/               # your consented demo assets (empty in git)
└── data/                  # runtime: reference crops + alert captures (gitignored)
```

---

## How matching works (the short version)

1. **Enroll**: detect the single face in each reference photo, pass a quality
   gate (size, detector score, blur), compute its 512-d L2-normalized embedding,
   and store it in `refs.embedding` (a pgvector column).
2. **Process**: detect faces in each frame, quality-gate them, embed, and run a
   cosine-similarity search against the watchlist
   (`1 - (embedding <=> query)` in pgvector).
3. **Consensus & cooldown** (video): a light IoU tracker links a face across
   processed frames; an alert fires only after the same person matches the same
   track across several frames, then that (person, camera) pair goes on cooldown.
4. **Review**: the alert is saved, broadcast over WebSocket, and shown to the
   officer, who confirms or dismisses it. The decision is audit-logged.

---

## Testing

```bash
# Backend tests (run inside the backend container or a local venv with deps).
# This stays fast and offline; model-dependent tests are skipped by default.
docker compose exec backend pytest -q

# To also run the tests that load the real InsightFace model (needs the model
# downloaded / internet on first run):
docker compose exec backend env RUN_MODEL_TESTS=1 pytest -q
```

### Evaluation harness (threshold tuning + bias audit)

`backend/eval/evaluate.py` sweeps the similarity threshold and reports precision,
recall, FAR (false accept rate), FRR (false reject rate), and the best-F1
threshold. With a `skin_tone` column in the manifest it also reports FAR/FRR per
bin — the groundwork for a bias audit.

```bash
# Wiring check with synthetic embeddings (no images or models needed):
python backend/eval/evaluate.py --self-test

# Real evaluation against your own consented image pairs:
python backend/eval/evaluate.py --manifest path/to/manifest.csv
```

See [`backend/eval/toy_manifest.example.csv`](backend/eval/toy_manifest.example.csv)
for the manifest format.

---

## Deployment (free tier)

Default plan: **Neon** (Postgres) + **Hugging Face Spaces** (backend) +
**Vercel** (frontend). Full step-by-step instructions, including the fallback if
HF's Docker free tier isn't available, are in
[`deploy/README.md`](deploy/README.md). A ready-to-copy Space README with the
required frontmatter is in
[`deploy/huggingface-space-README.md`](deploy/huggingface-space-README.md).

Quick outline:

1. **Neon**: create a project, run `CREATE EXTENSION IF NOT EXISTS vector;` then
   `db/init.sql` in the SQL editor. Use the pooled connection string as
   `DATABASE_URL`, with the scheme changed to `postgresql+asyncpg://`.
2. **Hugging Face Space** (Docker SDK, CPU basic): push `backend/`, set the
   Space secrets (`DATABASE_URL`, `FRONTEND_ORIGIN`, pipeline vars). The
   container listens on port 7860.
3. **Vercel**: import `frontend/`, set `VITE_API_BASE` to the Space URL, deploy.
   Update `FRONTEND_ORIGIN` on the Space to the Vercel URL so CORS matches.

---

## Limitations and scope

This is an MVP prototype. Deliberately **not** built (hooks/TODOs left in place):

- Real live RTSP camera ingestion (upload/video only for now).
- Authentication and role-based access (a single hardcoded "officer" identity;
  the code marks where auth would plug in).
- Persistent alert/reference image storage on ephemeral hosts (Postgres is the
  source of truth; captured crops are session-scoped on Spaces).
- A full bias-audit dashboard (the evaluation harness lays the groundwork).

Face recognition carries real risks of misidentification, and error rates can
differ across demographic groups. That is exactly why this system keeps a human
in the loop for every decision and ships an evaluation harness for measuring
FAR/FRR — including per-group — before anyone relies on a threshold.
