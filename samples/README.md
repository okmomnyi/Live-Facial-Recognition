# Sample data — consent and demo notes

This folder holds the demo assets you add yourself. **No face images are
committed to this repository.** The folder ships empty apart from this note.

## Consent first — this is not optional

Only use photographs and video of people who have **explicitly agreed** to be
enrolled and recognised for this demo. Face templates are biometric data. Tell
each person plainly:

- what you are capturing (reference photos and/or a short video),
- that it will be turned into a face embedding and stored in a local database,
- that it is for an academic prototype demo only, and
- that you will delete their data on request and after the demo.

Do not enroll anyone who has not agreed. Do not use scraped, public, or
third-party photos of people who have not consented.

## This demo uses no real government or law-enforcement data

The watchlist, the "checkpoints", and every record are fabricated for the demo.
The system carries no connection to any real police, immigration, or government
database, and must not be represented as one. The pretrained face models are
open-source and were trained by their original authors on public datasets; this
project only *uses* them for inference.

## Suggested demo script

1. Recruit 3–5 friends who consent.
2. Take **2 reference photos each** — clear, front-facing, well-lit, one face
   per photo. Enroll them on the Watchlist page (pick a category per person).
3. Record a short **10–30 second video** of one or two of them walking past a
   phone camera at normal pace, roughly checkpoint distance (1–3 m).
4. On the Live Monitor page, pick a checkpoint, upload the video, and press
   Process. Expect **1–2 alerts per enrolled subject** who appears in the clip.
5. Open an alert, compare the reference and the capture side by side, then
   Confirm or Dismiss. Check the Alerts page and confirm the status updated.

## Tips for a clean demo

- Good, even lighting beats everything else. Avoid strong backlight.
- If a reference photo is rejected on enroll, the per-image status will say why
  (no face / too small / too blurry / more than one face). Retake it.
- If the video raises no alerts, the faces may be too small or too fast. Move
  closer to the camera or slow the walk.
- Delete enrolled people from the Watchlist page when the demo is over.
