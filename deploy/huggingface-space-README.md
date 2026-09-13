---
title: LFR Prototype
emoji: 👁️
colorFrom: gray
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# LFR Prototype — backend

FastAPI backend for the Live Facial Recognition watchlist-matching prototype.
Research prototype for academic evaluation only; contains no government or
law-enforcement data, and every match requires human review.

This Space runs the contents of the repository's `backend/` directory as a
Docker container listening on port 7860. See the project repository for the
full system (frontend, database schema, and deployment guide).

## Required Space secrets

Set these under **Settings → Variables and secrets**:

- `DATABASE_URL` — the Neon pooled connection string, with the scheme changed to
  `postgresql+asyncpg://` (for example
  `postgresql+asyncpg://user:pass@ep-xxx-pooler.region.aws.neon.tech/db`).
- `FRONTEND_ORIGIN` — the deployed frontend origin (your Vercel URL), so CORS
  allows it.
- Optionally any pipeline tuning vars from `.env.example`
  (`MATCH_THRESHOLD`, `DET_THRESHOLD`, etc.). Defaults are sensible.

> Copy this file to `README.md` at the root of what you push to the Space (i.e.
> alongside the backend `Dockerfile`). Hugging Face reads the frontmatter above
> to configure the Space.
