# Deployment guide (free tier)

Default plan: **Neon** (serverless Postgres with pgvector) + **Hugging Face
Spaces** (backend, Docker, CPU) + **Vercel** (static React frontend). All three
have usable free tiers.

The three pieces are independent: deploy the database first, then the backend
(which needs the database), then the frontend (which needs the backend URL), and
finally tell the backend the frontend's URL for CORS.

---

## 1. Database — Neon

1. Create an account at [neon.tech](https://neon.tech) and a new project.
2. In the **SQL editor**, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   then paste and run the contents of [`../db/init.sql`](../db/init.sql).
3. Copy the **pooled** connection string (the host ends in `-pooler`).
4. Change the scheme from `postgresql://` to `postgresql+asyncpg://` for the
   async SQLAlchemy driver. This becomes your `DATABASE_URL`.

Example:
```
postgresql+asyncpg://user:pass@ep-xxxx-pooler.eu-central-1.aws.neon.tech/lfr
```

pgvector is available on all Neon plans, including free.

---

## 2. Backend — Hugging Face Spaces (Docker)

1. Create a new Space: **SDK = Docker**, **Hardware = CPU basic (free)**.
2. The container must listen on **port 7860**. The backend `Dockerfile` already
   defaults its `CMD` to `--port 7860`, and the Space README sets
   `app_port: 7860`, so nothing extra is needed.
3. Put a `README.md` with the required frontmatter at the root of what you push.
   A ready-to-use one is in
   [`huggingface-space-README.md`](huggingface-space-README.md) — copy it to
   `README.md` next to the backend `Dockerfile`.
4. Set the Space **secrets** (Settings → Variables and secrets):
   - `DATABASE_URL` — from Neon (step 1).
   - `FRONTEND_ORIGIN` — your Vercel URL (fill in after step 3; you can set a
     placeholder now and update it later).
   - Optionally the pipeline tuning vars from [`../.env.example`](../.env.example).
5. Push the **`backend/`** directory to the Space git remote. The Space builds
   the image and boots.

Pushing just the backend directory (the Space's root is the backend), for
example:
```bash
# from a checkout of this repo
cd backend
cp ../deploy/huggingface-space-README.md README.md
git init && git add . && git commit -m "Deploy LFR backend"
git remote add space https://huggingface.co/spaces/<user>/lfr-prototype
git push --force space main
```

**Storage note:** `data/` (reference crops and alert captures) is *ephemeral* on
Spaces — that's acceptable for a prototype because Postgres is the source of
truth. Thumbnails persist for the session. For durable images, add HF Persistent
Storage and point `DATA_DIR` at it.

**Sleep note:** free Spaces sleep after extended idle and wake on the next
request (the first request is slow). Fine for a demo; hit the URL a minute
before you present.

---

## 3. Frontend — Vercel

1. Import the repository into [Vercel](https://vercel.com) and set the **root
   directory** to `frontend/`. Vercel detects Vite automatically
   (build `npm run build`, output `dist`).
2. Set an environment variable:
   ```
   VITE_API_BASE = https://<user>-lfr-prototype.hf.space
   ```
   (your Space's URL). Vite inlines this at build time, so redeploy after
   changing it.
3. Deploy. Note the resulting Vercel URL.
4. Back on the Space, set `FRONTEND_ORIGIN` to that Vercel URL and restart the
   Space so CORS allows the frontend.

---

## 4. Verify

- Open the Vercel URL. The Watchlist page should load (empty).
- Enroll a person with a consented photo. If the request succeeds, the backend
  reached Neon and the models loaded.
- Upload an image of that person on the Live Monitor page and confirm an alert
  appears over WebSocket.

If enrollment fails with a CORS error, `FRONTEND_ORIGIN` on the Space doesn't
match the Vercel URL. If it fails with a database error, re-check `DATABASE_URL`
(scheme must be `postgresql+asyncpg://`, host must be the pooled one).

---

## Fallback if HF Docker free tier isn't available

- **Render** (free web service): deploy the backend as a Docker service. Expect
  cold starts and tight memory; use Neon for the database regardless. Set the
  same env vars; Render provides `$PORT`, so run
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Local demo + tunnel:** for the defense itself, running `docker compose up`
  on a laptop and exposing the backend with a Cloudflare Tunnel or ngrok, with
  the Vercel frontend pointed at the tunnel URL, is often more reliable than a
  free tier waking from sleep. Point `VITE_API_BASE` at the tunnel URL and set
  `FRONTEND_ORIGIN` to the Vercel URL.
- **Fly.io** with 256 MB is too tight for InsightFace; skip it.
