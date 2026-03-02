"""
Extract text from all PDF documents in the URL registry.
Downloads PDFs and extracts text using pdfplumber, focusing on
sections relevant to: expense_ratio, exit_load, min_sip, lock_in,
riskometer, benchmark, statement_download.
"""

import os
import requests
import pdfplumber
import json
import re

# All PDF URLs from the verified registry
PDFS = [
    {
        "id": 4,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/kim---sbi-large-cap-fund-(formerly-known-as-bluechip-fund).pdf",
        "doc_type": "kim_pdf",
        "scheme": "SBI Large Cap"
    },
    {
        "id": 5,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/kim---sbi-flexicap-fund.pdf?sfvrsn=485868a8_0",
        "doc_type": "kim_pdf",
        "scheme": "SBI Flexi Cap"
    },
    {
        "id": 6,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/kim---sbi-elss-tax-saver-fund-(formerly-known-as-sbi-long-term-equity-fund).pdf",
        "doc_type": "kim_pdf",
        "scheme": "SBI ELSS"
    },
    {
        "id": 7,
        "url": "https://www.sbimf.com/docs/default-source/scheme-factsheets/sbi-largecap-fund-factsheet-february-2026.pdf",
        "doc_type": "factsheet_pdf",
        "scheme": "SBI Large Cap"
    },
    {
        "id": 8,
        "url": "https://www.sbimf.com/docs/default-source/scheme-factsheets/sbi-flexicap-fund-factsheet-february-2026.pdf?sfvrsn=1e77f738_2",
        "doc_type": "factsheet_pdf",
        "scheme": "SBI Flexi Cap"
    },
    {
        "id": 9,
        "url": "https://www.sbimf.com/docs/default-source/scheme-factsheets/sbi-elss-tax-saver-fund-factsheet-february-2026.pdf?sfvrsn=97ae2ce2_2",
        "doc_type": "factsheet_pdf",
        "scheme": "SBI ELSS"
    },
    {
        "id": 10,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/sid---sbi-large-cap-fund-(formerly-known-as-bluechip-fund).pdf",
        "doc_type": "sid_pdf",
        "scheme": "SBI Large Cap"
    },
    {
        "id": 11,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/sid---sbi-flexicap-fund.pdf?sfvrsn=61aca6fd_0",
        "doc_type": "sid_pdf",
        "scheme": "SBI Flexi Cap"
    },
    {
        "id": 12,
        "url": "https://www.sbimf.com/docs/default-source/sif-forms/sid---sbi-elss-tax-saver-fund.pdf",
        "doc_type": "sid_pdf",
        "scheme": "SBI ELSS"
    },
]

# Keywords to identify relevant sections in PDFs
SECTION_KEYWORDS = [
    "expense ratio", "total expense ratio", "ter ",
    "exit load", "redemption",
    "minimum", "sip", "systematic investment",
    "lock-in", "lock in", "lockin",
    "riskometer", "risk-o-meter", "risk level", "very high", "moderately high",
    "benchmark", "nifty", "s&p bse",
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "pdf_extracts")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_pdf(url, filename):
    """Download a PDF from URL to local file."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded {filename} ({len(resp.content):,} bytes)")
    return filepath


def extract_relevant_text(pdf_path, doc_type):
    """
    Extract text from PDF, focusing on pages with relevant keywords.
    For KIM/factsheet (short docs), extract all pages.
    For SID (long docs), extract only pages with keyword matches.
    """
    all_text = []
    relevant_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            if doc_type in ("kim_pdf", "factsheet_pdf"):
                # Short docs — extract everything
                if text.strip():
                    all_text.append(f"--- PAGE {i+1} ---\n{text}")
            else:
                # SID PDFs are long — only extract relevant pages
                text_lower = text.lower()
                if any(kw in text_lower for kw in SECTION_KEYWORDS):
                    all_text.append(f"--- PAGE {i+1} ---\n{text}")
                    relevant_pages.append(i + 1)

    if doc_type == "sid_pdf":
        print(f"  Relevant pages: {relevant_pages[:20]}{'...' if len(relevant_pages) > 20 else ''}")

    return "\n\n".join(all_text)


def process_all():
    """Download and extract text from all PDFs."""
    results = {}

    for pdf_info in PDFS:
        pid = pdf_info["id"]
        scheme = pdf_info["scheme"]
        doc_type = pdf_info["doc_type"]
        url = pdf_info["url"]
        filename = f"id{pid}_{doc_type}_{scheme.replace(' ', '_').lower()}.pdf"

        print(f"\n[ID {pid}] {doc_type} — {scheme}")
        try:
            filepath = download_pdf(url, filename)
            text = extract_relevant_text(filepath, doc_type)

            # Save extracted text
            txt_path = os.path.join(OUTPUT_DIR, filename.replace(".pdf", ".txt"))
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

            results[pid] = {
                "id": pid,
                "doc_type": doc_type,
                "scheme": scheme,
                "url": url,
                "text_file": txt_path,
                "text_length": len(text),
                "status": "OK"
            }
            print(f"  Extracted {len(text):,} chars → {txt_path}")

        except Exception as e:
            results[pid] = {
                "id": pid,
                "doc_type": doc_type,
                "scheme": scheme,
                "url": url,
                "status": f"ERROR: {e}"
            }
            print(f"  ERROR: {e}")

    # Save summary
    summary_path = os.path.join(OUTPUT_DIR, "_extraction_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Summary saved to {summary_path}")


if __name__ == "__main__":
    process_all()
