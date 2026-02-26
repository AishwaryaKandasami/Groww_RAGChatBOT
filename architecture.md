# RAG-Based Mutual Fund FAQ Chatbot — Technical Architecture

**Platform:** Groww (consumer fintech)  
**Schemes:** SBI Large Cap Fund · SBI Flexi Cap Fund · SBI Long Term Equity Fund (ELSS)  
**Sources:** sbimf.com · amfiindia.com · sebi.gov.in · camsonline.com · mfcentral.com

---

## 1. SYSTEM DIAGRAM

### Online Serving Path

```
┌────────┐  natural-language   ┌───────────┐  JSON query     ┌──────────────┐
│  User   │ ──── question ───► │  React UI │ ── + session ──►│  FastAPI      │
│(Groww)  │                    │ (Next.js) │    metadata     │  API Gateway  │
└────────┘                    └───────────┘                 └──────┬───────┘
                                                                   │
                                                      raw query text
                                                                   ▼
                                                          ┌────────────────┐
                                                          │  GUARDRAIL     │
                                                          │  (Pre-Filter)  │
                                                          │  ── advisory?  │
                                                          │  ── PII scan?  │
                                                          └───────┬────────┘
                                                                  │
                                                    cleaned query (or BLOCK)
                                                                  ▼
                                              ┌───────────────────────────────┐
                                              │     RETRIEVAL ENGINE          │
                                              │  1. embed query (same model)  │
                                              │  2. ANN search top-k=5       │
                                              │  3. re-rank by relevance     │
                                              └──────────────┬────────────────┘
                                                             │
                                                  ranked doc chunks + scores
                                                             ▼
                                              ┌───────────────────────────────┐
                                              │     GENERATION (LLM)          │
                                              │  prompt = system_instructions │
                                              │         + retrieved_chunks    │
                                              │         + user_query          │
                                              │  output: ≤3 sentences + cite  │
                                              └──────────────┬────────────────┘
                                                             │
                                                   answer + source citation
                                                             ▼
                                                    ┌────────────────┐
                                                    │  GUARDRAIL     │
                                                    │  (Post-Filter) │
                                                    │  ── hallucin.? │
                                                    │  ── advice?    │
                                                    └───────┬────────┘
                                                            │
                                                  validated response JSON
                                                            ▼
                                                    ┌───────────┐       ┌────────┐
                                                    │  React UI │ ─────►│  User  │
                                                    │ (Next.js) │  card │(Groww) │
                                                    └───────────┘       └────────┘
```

### Offline Ingestion Pipeline

```
┌──────────────┐  raw HTML/PDF   ┌──────────────┐  clean text    ┌──────────────┐
│  DATA        │ ──────────────► │  PARSER /    │ ────────────► │  CHUNKER     │
│  SOURCES     │                 │  SCRAPER     │               │  (recursive  │
│  (5 sites)   │                 │  (Scrapy +   │               │   char-split │
│              │                 │   pdfplumber)│               │   500 chars) │
└──────────────┘                 └──────────────┘               └──────┬───────┘
                                                                       │
                                                            text chunks + metadata
                                                                       ▼
                                                              ┌────────────────┐
                                                              │  EMBEDDING     │
                                                              │  MODEL         │
                                                              │  (OpenAI       │
                                                              │  text-embed-   │
                                                              │  3-small)      │
                                                              └───────┬────────┘
                                                                      │
                                                          768-d vectors + metadata
                                                                      ▼
                                                              ┌────────────────┐
                                                              │  VECTOR DB     │
                                                              │  (Qdrant)      │
                                                              │  collection:   │
                                                              │  mf_docs       │
                                                              └────────────────┘

Trigger: GitHub Actions cron — 1st of every month
```

---

## 2. LAYER BREAKDOWN

### Ingestion Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Scrapes the 5 authorised sources, converts HTML/PDF to clean text, chunks it, and loads into vector DB |
| **Tech**   | **Scrapy** (web crawl) + **pdfplumber** (PDF parse) + **LangChain RecursiveCharacterTextSplitter** |
| **Why**    | Scrapy handles JavaScript-light public pages efficiently with built-in politeness; pdfplumber extracts tabular scheme data (TER tables, KIM docs) that PyPDF2 mangles; LangChain splitter preserves sentence boundaries — critical when a single sentence contains both expense ratio *and* exit load |

### Embedding Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Converts text chunks and user queries into dense vectors for semantic search |
| **Tech**   | **OpenAI text-embedding-3-small** (768 dims) |
| **Why**    | Best cost-to-quality ratio for short financial text; 768-dim keeps Qdrant index lean (~15K chunks for 3 schemes); same model used at ingest and query time eliminates vector-space mismatch; OpenAI API is already available if using GPT for generation |

### Retrieval Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Embeds the user query, performs ANN search, re-ranks top results |
| **Tech**   | **Qdrant** (vector DB, self-hosted Docker) + **cosine similarity** + **cross-encoder re-ranker** (ms-marco-MiniLM-L-6-v2) |
| **Why**    | Qdrant runs locally with zero licence cost, supports payload filtering (filter by `scheme_name` before ANN), and has native Python SDK; cross-encoder re-rank on just 5 candidates is cheap (~20ms) and dramatically boosts precision for near-duplicate financial phrasing ("exit load" vs "redemption charge") |

### Guardrails Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Pre-filter blocks advisory/PII queries; post-filter validates answer is grounded and non-advisory |
| **Tech**   | **Rule-based classifier** (regex + keyword list) for pre-filter + **NLI-based grounding check** (a lightweight entailment model or LLM self-check) for post-filter |
| **Why**    | Regex is deterministic and fast (<1ms) for catching "should I invest", "which is better", PAN/Aadhaar patterns; NLI grounding check ensures every claim in the answer can be traced to a retrieved chunk — mandatory for SEBI compliance; no external guardrail service needed, keeps latency under control |

### Generation Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Produces a ≤3-sentence answer with exactly one source citation, grounded only in retrieved chunks |
| **Tech**   | **GPT-4o-mini** via OpenAI API |
| **Why**    | GPT-4o-mini follows structured prompts reliably (sentence cap, citation format), costs ~$0.15/1M input tokens (budget-friendly for FAQ volume), supports JSON mode for consistent response schema, and handles financial terminology without fine-tuning |

### UI Layer

| Aspect     | Detail |
|------------|--------|
| **What**   | Chat interface embedded in Groww, renders answer cards with source links |
| **Tech**   | **Next.js** (React) with a chat widget component |
| **Why**    | Groww's web stack is React-based; Next.js gives SSR for SEO on FAQ pages, built-in API routes as BFF (backend-for-frontend) if needed, and fast hydration for the chat widget; a single-page chat component keeps scope minimal |

---

## 3. DATA FLOW — 2 TRACES

### Trace 1: Factual Query — *"What is the exit load on SBI Large Cap?"*

```
Step  Component           Action                                    Data Passed Forward
────  ──────────────────  ────────────────────────────────────────  ──────────────────────────────────────
 1    React UI            User types question, sends POST           { "query": "What is the exit load
                          /api/chat                                   on SBI Large Cap?" }

 2    FastAPI Gateway      Receives request, forwards to             raw query string
                          pre-filter guardrail

 3    Pre-Filter           Regex scan: no advisory pattern           query string (PASS)
      Guardrail            ("should I", "which is better")
                          PII scan: no PAN/Aadhaar pattern

 4    Embedding            Encode query → 768-d vector              query_vector: float[768]

 5    Qdrant               ANN search, cosine similarity,            top-5 chunks:
      (Retrieval)          payload filter: scheme="SBI Large Cap"    [{ text: "Exit load: 1% if
                          returns top-5 chunks                        redeemed before 1 year...",
                                                                      source: "sbimf.com/sbi-
                                                                      large-cap", score: 0.91 }, ...]

 6    Cross-Encoder        Re-rank 5 chunks by query relevance      top-3 reranked chunks
      Re-Ranker

 7    GPT-4o-mini          Prompt:                                   generated answer:
      (Generation)         SYSTEM: "Answer in ≤3 sentences.          "The exit load on SBI Large Cap
                           Cite one source. Use ONLY the             Fund is 1% if units are redeemed
                           provided context."                        within 1 year of allotment. After
                           CONTEXT: [top-3 chunks]                   1 year, there is no exit load.
                           QUERY: "What is the exit load..."         (Source: sbimf.com/sbi-large-cap)"

 8    Post-Filter          NLI grounding check: every claim          response JSON (PASS)
      Guardrail            in answer exists in context chunks ✓
                          Advisory check: no opinion detected ✓

 9    FastAPI Gateway      Wraps in response schema                  { "answer": "...",
                                                                      "source_url": "sbimf.com/...",
                                                                      "grounded": true }

10    React UI             Renders answer card with clickable        User sees answer + source link
                          source link
```

### Trace 2: Blocked Query — *"Should I invest in SBI Large Cap or Flexi Cap?"*

```
Step  Component           Action                                    Data Passed Forward
────  ──────────────────  ────────────────────────────────────────  ──────────────────────────────────────
 1    React UI            User types question, sends POST           { "query": "Should I invest in
                          /api/chat                                   SBI Large Cap or Flexi Cap?" }

 2    FastAPI Gateway      Receives request, forwards to             raw query string
                          pre-filter guardrail

 3    Pre-Filter           Regex match: "should I invest" →          BLOCKED
      Guardrail            triggers ADVISORY pattern
                          Action: reject immediately

 4    FastAPI Gateway      Returns canned refusal                    { "answer": "I can only provide
                          (NO retrieval, NO LLM call)                 factual information about mutual
                                                                      fund schemes. For investment
                                                                      advice, please consult a
                                                                      SEBI-registered advisor.",
                                                                      "blocked": true,
                                                                      "block_reason": "advisory_query" }

 5    React UI             Renders refusal card with                 User sees polite refusal +
                          "consult advisor" message                  advisor link

         ┌──────────────────────────────────────────────────────┐
         │  NOTE: Steps 4–8 of the normal path are SKIPPED.    │
         │  No embedding, no vector search, no LLM call.       │
         │  Latency: <50ms.  Cost: $0.                         │
         └──────────────────────────────────────────────────────┘
```

---

## 4. CORE DATA SCHEMAS

### Document Chunk (stored in Qdrant)

```json
{
  "id":            "uuid-v4",
  "text":          "Exit load: 1% if redeemed before 1 year of allotment...",
  "embedding":     [0.012, -0.034, ...],       // 768 floats (stored by Qdrant, not in payload)
  "scheme_name":   "SBI Large Cap Fund",       // payload filter key
  "source_url":    "https://sbimf.com/sbi-large-cap-fund",
  "source_site":   "sbimf.com",                // one of 5 authorised domains
  "doc_type":      "scheme_info",              // enum: scheme_info | kim | sai | factsheet | regulation
  "section":       "Exit Load",                // section heading from source doc
  "ingested_at":   "2026-02-01T00:00:00Z",    // ISO-8601, used for freshness checks
  "chunk_index":   3                           // position within parent document
}
```

### Bot Response (sent to UI)

```json
{
  "answer":        "The exit load on SBI Large Cap Fund is 1% if redeemed within 1 year. After 1 year, no exit load is applicable. (Source: sbimf.com/sbi-large-cap-fund)",
  "source_url":    "https://sbimf.com/sbi-large-cap-fund",
  "grounded":      true,
  "blocked":       false,
  "block_reason":  null,
  "latency_ms":    420,
  "timestamp":     "2026-02-25T13:31:00Z"
}
```

---

## 5. TOP 5 RISKS

| # | Risk | Mitigation | Owner |
|---|------|-----------|-------|
| 1 | **Stale data** — TER/riskometer changes mid-month, chatbot serves outdated facts | Monthly cron re-ingestion + `ingested_at` field; add a "data as of" disclaimer to every response | **Ingestion Pipeline** |
| 2 | **Hallucination** — LLM fabricates a number (e.g., wrong expense ratio) | Post-generation NLI grounding check; if any claim fails entailment against context, return "I don't have enough information" instead | **Guardrails (Post-Filter)** |
| 3 | **Advisory leakage** — LLM subtly gives investment advice despite system prompt | Dual-layer defence: regex pre-filter blocks obvious patterns; post-filter scans LLM output for comparative/recommendation language | **Guardrails (Pre + Post)** |
| 4 | **PII exposure** — User pastes PAN/Aadhaar number in query, gets logged | Pre-filter regex detects PII patterns and rejects query *before* it reaches embedding or LLM; no raw queries are persisted to disk | **Guardrails (Pre-Filter)** |
| 5 | **Source attribution error** — Answer cites wrong URL or a non-authorised source | `source_url` is carried as chunk metadata from ingestion through retrieval; generation prompt hard-pins citation to the top-ranked chunk's `source_url` field, never asks LLM to generate a URL | **Retrieval + Generation** |

---

## SINGLE BIGGEST ARCHITECTURAL RISK

> **Hallucination of financial numbers.**
>
> A wrong expense ratio or exit load percentage could mislead investors and
> create regulatory liability under SEBI's Mutual Fund Regulations. 
>
> **Mitigation stack:**
> 1. System prompt: *"Use ONLY the provided context. If the answer is not
>    in the context, say 'I don't have this information.'"*
> 2. Low temperature (0.0) on GPT-4o-mini to minimize creative generation.
> 3. Post-generation NLI grounding check: every factual claim in the answer
>    must be entailed by at least one retrieved chunk.
> 4. If grounding check fails → suppress the answer, return safe fallback.
> 5. Monthly data refresh ensures the context itself stays current.
>
> **Owner:** Guardrails (Post-Filter) + Generation Layer jointly.
