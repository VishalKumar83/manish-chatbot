"""
Manish Innovations - AI Customer Inquiry Chatbot Backend
-----------------------------------------------------------
A lightweight FastAPI service that powers a website chat widget.
It answers visitor questions about products, certifications, and
export process using a simple retrieval-augmented approach:
we inject the company's product/knowledge context into the LLM
prompt so answers stay grounded in real business info.

Uses Google's Gemini API — see https://aistudio.google.com

Run locally:
    pip install -r requirements.txt
    export GEMINI_API_KEY=your_key_here
    uvicorn main:app --reload --port 8000

Deploy anywhere that runs Python (Render, Railway, a VPS, etc.)
and point the widget's API_URL at the deployed endpoint.
"""

import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

app = FastAPI(title="Manish Innovations Chatbot API")

# ---------------------------------------------------------------------
# Logging DB — every conversation turn gets stored so we can build
# analytics (query volume, common topics, latency, failures) on top
# of real usage data once the bot is live.
# ---------------------------------------------------------------------
DB_PATH = os.environ.get("CHATBOT_DB_PATH", "chatbot_logs.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_hint TEXT,
            user_message TEXT NOT NULL,
            bot_reply TEXT,
            latency_ms INTEGER,
            success INTEGER NOT NULL DEFAULT 1,
            error_detail TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()

# Allow the WordPress site (and local testing) to call this API.
# In production, replace "*" with "https://innovationsmanish.com"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --- FIX: gemini-2.5-flash was retired by Google; updated to the
# current production Flash model (GA as of July 2026). If this ever
# 502s again with a "model not found" style error in the logs, check
# https://ai.google.dev/gemini-api/docs/models for the current name. ---
MODEL_NAME = "gemini-3.6-flash"

# ---------------------------------------------------------------------
# Company knowledge base (this is the "retrieval" context).
# In a fuller version, this could be pulled from a vector DB built
# from the actual product pages instead of being hardcoded.
# ---------------------------------------------------------------------
COMPANY_CONTEXT = """
You are the AI customer assistant for Manish Innovations, an agriculture
products exporter based in Jamshedpur, Jharkhand, India.

COMPANY FACTS:
- Contact: +91 7050506999, sales@innovationsmanish.com
- Address: H No -199, Road-D, Sonari West Layout, Jamshedpur - 831011
- Certifications: Central License for Exporting Agro Commodities,
  APEDA certified, Spice Board of India certified, GMP (Good
  Manufacturing Practice), Import Export Certificate, ISO 9001:2015.

PRODUCT CATEGORIES:
1. Spices - black pepper, turmeric, cumin, red chilli, cashew,
   walnuts, raisins, pistachios, saffron, cardamom, cloves, and
   other rare/exotic spices.
2. Powders & Dehydrated Products (e.g. banana powder, turmeric powder)
3. Nuts, Dry Fruits & Snacks
4. Pulses, Grains & Seeds
5. Edible Oils
6. Eco-Friendly Products

RULES FOR YOUR ANSWERS:
- Be concise, friendly, and professional - like a helpful export
  sales representative.
- If a visitor asks about pricing, MOQ (minimum order quantity),
  or shipping timelines, explain that exact figures depend on the
  order, and direct them to contact sales@innovationsmanish.com or
  +91 7050506999 for a quote.
- If asked about something outside agri-export products/services,
  politely redirect to what the company offers.
- Never invent certifications, prices, or claims not listed above.
- Keep answers under ~120 words unless the visitor asks for detail.
"""

SYSTEM_PROMPT = COMPANY_CONTEXT


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    session_hint: Optional[str] = None  # e.g. a browser-generated random ID, no PII


class ChatResponse(BaseModel):
    reply: str


def log_turn(session_hint, user_message, bot_reply, latency_ms, success, error_detail=None):
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO conversation_logs
               (timestamp, session_hint, user_message, bot_reply, latency_ms, success, error_detail)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                session_hint,
                user_message,
                bot_reply,
                latency_ms,
                1 if success else 0,
                error_detail,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        # Logging should never break the chat response itself
        pass


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Manish Innovations chatbot API"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Gemini uses "user"/"model" roles (not "assistant") and a "contents" list
    # of {role, parts: [{text}]} objects, with system instructions passed
    # separately via GenerateContentConfig.
    contents = []
    for m in (req.history or []):
        role = "model" if m.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": req.message}]})

    start = time.time()
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=400,
            ),
        )
        reply_text = response.text or ""
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        log_turn(req.session_hint, req.message, None, latency_ms, success=False, error_detail=str(e))
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}")

    latency_ms = int((time.time() - start) * 1000)
    log_turn(req.session_hint, req.message, reply_text, latency_ms, success=True)

    return ChatResponse(reply=reply_text)


# ---------------------------------------------------------------------
# Analytics endpoints — power the admin dashboard (analytics.html).
# In production, put these behind basic auth or an admin-only route.
# ---------------------------------------------------------------------
@app.get("/analytics/summary")
def analytics_summary():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) c FROM conversation_logs").fetchone()["c"]
    successes = conn.execute(
        "SELECT COUNT(*) c FROM conversation_logs WHERE success = 1"
    ).fetchone()["c"]
    avg_latency = conn.execute(
        "SELECT AVG(latency_ms) a FROM conversation_logs WHERE success = 1"
    ).fetchone()["a"]
    by_day = conn.execute(
        """SELECT substr(timestamp, 1, 10) as day, COUNT(*) as count
           FROM conversation_logs GROUP BY day ORDER BY day"""
    ).fetchall()
    recent = conn.execute(
        """SELECT timestamp, user_message, bot_reply, success
           FROM conversation_logs ORDER BY id DESC LIMIT 20"""
    ).fetchall()
    conn.close()

    return {
        "total_queries": total,
        "successful_queries": successes,
        "failed_queries": total - successes,
        "success_rate": round(successes / total, 3) if total else None,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
        "queries_by_day": [dict(r) for r in by_day],
        "recent_conversations": [dict(r) for r in recent],
    }

   
