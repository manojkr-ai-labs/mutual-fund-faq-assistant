# Mutual Fund FAQ Assistant — web UI

Next.js 16 + Tailwind CSS frontend for Phase 6. It talks to the FastAPI `POST /api/ask` endpoint through a same-origin proxy.

## Run locally

1. Start the API from the repo root:

```bash
python -m app
```

2. In `web/`:

```bash
npm install
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000).

Optional: set `ASK_API_ORIGIN` (default `http://127.0.0.1:8000`) if the API is not on port 8000.

History stays in the tab. Do not enter PAN, Aadhaar, email, phone, or folio.
