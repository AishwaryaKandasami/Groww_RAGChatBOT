"""
generator.py — RAG Generation Layer (Groq + Llama 3.1 8B)
===========================================================
Purpose : Given a user query and retrieved context chunks, call
          the Llama 3.1 8B model via Groq to produce a factual,
          sourced answer.

Inputs  : User query + list of retrieved chunk dicts from retriever.py
Outputs : Dict with answer, source_url, source_label, date_fetched, intent
Env vars: GROQ_API_KEY
"""

import os

from dotenv import load_dotenv
from groq import Groq

# ── Config ────────────────────────────────────────────────────────
GROQ_MODEL       = "llama-3.1-8b-instant"
MAX_CONTEXT_CHARS = 3200     # ≈ 800 tokens at ~4 chars/token
TEMPERATURE       = 0.0      # factual — no creativity
MAX_TOKENS        = 200
TOP_P             = 1.0

# ── System prompt — pasted verbatim per spec ──────────────────────
SYSTEM_PROMPT = """You are a factual assistant for SBI Mutual Fund schemes.
Answer using ONLY the context provided below.
Rules:
- Maximum 3 sentences. Never exceed this.
- Never give investment advice or compare fund performance.
- Never recommend buying, selling, or switching funds.
- End every answer with: Source: [url from context]
- End every answer with: Last updated: [date_fetched from context]
- If context does not contain the answer respond with exactly:
  "I don't have verified information on this. Please visit sbimf.com or amfiindia.com for the most current details."
- Never use bullet points. Plain prose only.
- Do not start your answer with "I"."""

# Fallback answer used when no context is available
NO_CONTEXT_ANSWER = (
    "I don't have verified information on this. "
    "Please visit sbimf.com or amfiindia.com for the most current details."
)

# Module-level singleton
_groq_client: Groq | None = None


# ── Initialisation ────────────────────────────────────────────────

def _get_groq() -> Groq:
    """Return (and cache) a Groq client."""
    global _groq_client
    if _groq_client is None:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ── Core generation function ─────────────────────────────────────

def generate(query: str, retrieved_chunks: list[dict]) -> dict:
    """Generate a factual answer using Groq (Llama 3.1 8B).

    Args:
        query:            The user's natural language question.
        retrieved_chunks: List of dicts from retriever.retrieve(),
                          each with chunk_text, source_url, scheme,
                          topic, date_fetched, rerank_score.

    Returns:
        Dict with keys: answer, source_url, source_label,
        date_fetched, intent.
    """
    # ── Handle empty context ─────────────────────────────────────
    if not retrieved_chunks:
        return {
            "answer":       NO_CONTEXT_ANSWER,
            "source_url":   "",
            "source_label": "",
            "date_fetched": "",
            "intent":       "factual",
        }

    # ── Build context string ─────────────────────────────────────
    # Sort by rerank_score descending so best chunk is first
    sorted_chunks = sorted(
        retrieved_chunks,
        key=lambda c: c.get("rerank_score", 0),
        reverse=True,
    )

    best_chunk = sorted_chunks[0]
    best_source_url  = best_chunk["source_url"]
    best_date        = best_chunk["date_fetched"]

    # Concatenate chunk texts, truncating to stay within context budget
    context_parts: list[str] = []
    total_len = 0
    for chunk in sorted_chunks:
        text = chunk["chunk_text"]
        if total_len + len(text) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_len
            if remaining > 50:
                context_parts.append(text[:remaining] + "…")
            break
        context_parts.append(text)
        total_len += len(text)

    context_body = "\n\n".join(context_parts)

    # Append source + date for the LLM to quote
    context_string = (
        f"{context_body}\n\n"
        f"Source URL: {best_source_url}\n"
        f"Last updated: {best_date}"
    )

    # ── Build user prompt ────────────────────────────────────────
    user_prompt = (
        f"Context:\n{context_string}\n\n"
        f"Question: {query}"
    )

    # ── Call Groq API ────────────────────────────────────────────
    client = _get_groq()

    chat_response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )

    answer_text = chat_response.choices[0].message.content.strip()

    # ── Derive a readable source label ───────────────────────────
    source_label = _make_source_label(best_source_url)

    return {
        "answer":       answer_text,
        "source_url":   best_source_url,
        "source_label": source_label,
        "date_fetched": best_date,
        "intent":       "factual",
    }


def _make_source_label(url: str) -> str:
    """Create a human-readable label from a source URL."""
    if "sbimf.com" in url:
        if "scheme-details" in url or "sbimf-scheme-details" in url:
            return "SBI MF — Scheme Overview"
        if "kim" in url.lower():
            return "SBI MF — Key Information Memorandum"
        if "sid" in url.lower():
            return "SBI MF — Scheme Information Document"
        if "factsheet" in url.lower():
            return "SBI MF — Factsheet"
        return "SBI Mutual Fund"
    if "amfiindia.com" in url:
        return "AMFI India"
    if "sebi.gov.in" in url:
        return "SEBI Circular"
    if "camsonline.com" in url:
        return "CAMS Online"
    return url
