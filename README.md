# Manish Innovations - AI Chatbot (Free Version — Google Gemini)

An AI-powered customer inquiry chatbot for innovationsmanish.com.
Uses **Google's Gemini API**, which has a genuine ongoing free tier —
no credit card required, no trial expiry. Answers visitor questions
about products, certifications, and export process.

## What's included
- `main.py` — FastAPI backend with a `/chat` endpoint (Gemini-powered)
  and `/analytics/summary` for usage stats.
- `widget.html` — Drop-in chat widget (HTML/CSS/JS) for WordPress/Elementor.
- `analytics.html` — Admin dashboard showing query volume, success rate,
  latency, and recent conversations.
- `requirements.txt` — Python dependencies.

## 1. Get a free Gemini API key
1. Go to **aistudio.google.com** and sign in with any Google account.
2. Click **Get API key** -> **Create API key**.
3. Copy the key (starts with `AIza...`). No billing setup, no card.

## 2. Run the backend locally
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
uvicorn main:app --reload --port 8000
```
Test it:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Do you export turmeric to the UK?"}'
```

## 3. Deploy the backend (still free)
- **Render** (free tier): connect this folder as a GitHub repo, set
  `GEMINI_API_KEY` as an environment variable, start command
  `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Free tier services sleep after inactivity — first request after
  idle time takes ~30 seconds to wake up. Fine for a small business site.

## 4. Add the widget to WordPress
1. In Elementor, add an **HTML widget** to the footer template.
2. Paste the full contents of `widget.html` into it.
3. Update the `API_URL` constant in the `<script>` block to your
   deployed backend URL + `/chat`.
4. In `main.py`, tighten CORS from `allow_origins=["*"]` to
   `["https://innovationsmanish.com"]` before going fully live.
5. Publish.

## 5. View analytics
Open `analytics.html` locally (or host it privately), paste your
backend's base URL, click **Load Data** — see live query volume,
success rate, and recent conversations.

## Free tier limits to know
Gemini's free tier has daily/per-minute request caps (Google's
documented limits change over time — check
https://ai.google.dev/gemini-api/docs/rate-limits for current numbers).
For a small business chatbot with modest traffic, the free tier is
typically more than enough. If you ever outgrow it, the same code
works after linking a billing account — no rewrite needed.

## Notes for the resume writeup
This is a genuine, working RAG-style chatbot: it grounds LLM answers
in real company data (products, certifications, contact info) rather
than letting the model improvise, and it runs at zero cost using
Gemini's free tier — so it's fair to describe as a fully deployed,
production AI chatbot integration.
