# SBI Mutual Fund FAQ Chatbot

A RAG-based chatbot that answers factual questions about three SBI Mutual Fund schemes using verified data from official documents.

## Scope

| Scheme | Type | Benchmark |
|--------|------|-----------|
| SBI Large Cap Fund | Open-ended large cap equity | BSE 100 (TRI) |
| SBI Flexicap Fund | Open-ended dynamic equity | BSE 500 (TRI) |
| SBI ELSS Tax Saver Fund | ELSS with 3-year lock-in | BSE 500 (TRI) |

**Topics covered:** Expense ratio, exit load, minimum SIP/lump sum, lock-in period, riskometer, benchmark, scheme category, statement download (CAS).

**Data sources:** 19 verified URLs — SBI MF scheme pages, KIM/SID/Factsheet PDFs, AMFI knowledge pages, SEBI circulars, CAMS CAS portal.

## Architecture

```
User Query → Guardrails → Embed (OpenAI) → ANN Search (Qdrant)
           → Rerank (cross-encoder) → Generate (Groq / Llama 3.1 8B)
           → Factual Answer + Source Citation
```

| Component | Technology |
|-----------|-----------|
| Embeddings | OpenAI `text-embedding-3-small` (768 dims) |
| Vector DB | Qdrant (in-memory, rebuilt on startup) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | Llama 3.1 8B via Groq API |
| UI | Streamlit |
| Deployment | Streamlit Community Cloud |

## Setup

### Prerequisites

- Python 3.10+
- OpenAI API key ([get one](https://platform.openai.com/api-keys))
- Groq API key ([get one](https://console.groq.com/keys))

### Install

```bash
git clone <repo-url>
cd RAG_GRoww
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your real API keys
```

## How to Run

### 1. Build the vector store

```bash
python ingest.py
```

This reads `extracted_facts.json`, chunks and embeds all 68 facts, and saves the vectors to `vector_store/mf_faq.json`. Expected output:

```
Total facts loaded:    68
Total chunks created:  68
Collection:            mf_faq
Embedding model:       text-embedding-3-small
Output:                vector_store/
```

### 2. Run the Streamlit app locally

```bash
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push the repo to GitHub (ensure `.env` is in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch, and `app.py` as the main file
4. Under **Advanced settings → Secrets**, add:
   ```toml
   OPENAI_API_KEY = "sk-..."
   GROQ_API_KEY = "gsk_..."
   ```
5. Click **Deploy** — the app will install dependencies from `requirements.txt` and start

> **Note:** The vector store is rebuilt in-memory on each cold start from `extracted_facts.json`. This adds ~10–15 seconds to startup but avoids committing large binary files.

## Automated Updates

This repository includes a GitHub Actions workflow (`.github/workflows/monthly_kb_update.yml`) that runs automatically on the 1st of every month to keep the scheme information current without manual intervention:
1. Runs `extract_pdf_text.py` to download the latest KIM, SID, and factsheets for the 3 allowed mutual funds.
2. Extracts updated text content into `pdf_extracts/`.
3. Commits and pushes any changes to the repository automatically.

## Environment Variables


| Variable | Used by | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | `ingest.py`, `retriever.py` | Embed facts and queries with `text-embedding-3-small` |
| `GROQ_API_KEY` | `generator.py` | Call Llama 3.1 8B for answer generation |

## Project Structure

```
RAG_GRoww/
├── .env.example              # API key template
├── .gitignore
├── README.md
├── architecture.md           # Detailed system architecture
├── requirements.txt          # Pinned dependencies
│
├── extracted_facts.json      # 68 structured facts (input data)
├── knowledge_base.md         # 24 consolidated KB entries
├── url_registry.md           # 19 verified source URLs
│
├── ingest.py                 # Ingestion: chunk → embed → store
├── retriever.py              # Retrieval: search → filter → rerank
├── generator.py              # Generation: context → LLM → answer
│
├── pdf_extracts/             # Raw text from 9 PDFs
└── vector_store/             # Created by ingest.py (gitignored)
```

## Known Limits

| Limit | Detail |
|-------|--------|
| **3 schemes only** | SBI Large Cap, Flexicap, and ELSS Tax Saver. No other AMC or scheme is covered. |
| **Static data** | Facts are from Jan/Feb 2026 documents. TER and NAV change frequently — answers may become stale. |
| **AMFI riskometer page** | JS-rendered data portal with no descriptive content. Riskometer definition uses a manual fallback fact sourced from the SEBI circular. |
| **MFCentral CAS** | URL 20 (mfcentral.com) is login-gated — not included in the knowledge base. |
| **No performance data** | The chatbot intentionally excludes NAV, returns, and performance comparisons per guardrail rules. |
| **In-memory vector store** | Qdrant runs in `:memory:` mode. Cold starts rebuild the index (~10–15s). Not suitable for large-scale production. |
| **No conversation memory** | Each query is independent — no multi-turn context. |
