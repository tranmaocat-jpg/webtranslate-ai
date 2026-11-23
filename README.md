# WebTranslate AI — MVP

URL-based website translator with Vietnamese interface. It tries to preserve HTML structure, CSS, images and links while translating text nodes.

## Deploy to Render (free tier)

1. Open the Blueprint deploy URL: https://render.com/deploy?repo=https://github.com/tranmaocat-jpg/webtranslate-ai
2. Sign in/connect GitHub and deploy the Blueprint.
3. Render reads render.yaml; choose Apply / Deploy.
4. When finished, open the generated onrender.com URL. Free web services sleep after inactivity.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Self-host translation engine

```bash
docker compose up --build
```

Online deploy defaults to MyMemory (anonymous quota is limited, often around 5,000 chars/day; provider terms/limits can change). Choose a source language explicitly. Set LIBRETRANSLATE_URL to your own LibreTranslate-compatible endpoint for self-hosting; optional LIBRETRANSLATE_KEY supported.

## Limitations / safety

- Does not execute original site JavaScript; removes scripts, iframe, object and embed. Interactive pages may not work.
- CSS/images may load from original base URL but complex CSS asset rewriting can fail.
- URL validation checks global IPs and redirect destinations. Production needs DNS pinning and outbound egress controls to harden SSRF/DNS rebinding.
- Do not use this public demo for private/authenticated websites. Translation service has quotas/rate limits.
