"""
Scrape Cummins Document Library for X15, B6.7, and ISB engine PDFs;
extract text with PyMuPDF, chunk into 500-word blocks with 50-word overlap;
insert into MongoDB Manuals collection.
"""

import hashlib
import os
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import pymongo
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
MANUALS_COLLECTION = "manuals"

ENGINE_KEYWORDS = ("X15", "B6.7", "ISB")
CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 50

# Pages to scrape for PDF links (Cummins document library / MART)
SCRAPE_BASE_URLS = [
    "https://www.cummins.com/parts/manuals-and-technical-documents",
    "https://mart.cummins.com/imagelibrary/externallist.aspx",
    "https://www.cummins.com/engines/products/x15",
    "https://www.cummins.com/engines/products/isb67",
    "https://www.cummins.com/engines/products/b67",
]

# Optional: seed PDF URLs if scraping returns few results (e.g. JS-rendered or login-required pages)
SEED_PDF_URLS = os.environ.get("CUMMINS_SEED_PDF_URLS", "").strip().split()
if not SEED_PDF_URLS:
    SEED_PDF_URLS = [
        "https://mart.cummins.com/imagelibrary/data/assetfiles/0063393.pdf",
        "https://mart.cummins.com/imagelibrary/data/assetfiles/0064235.pdf",
        "https://mart.cummins.com/imagelibrary/data/assetfiles/0032369.pdf",
    ]

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _normalize_engine_model(url: str, link_text: str) -> str | None:
    """Return engine model (X15, B6.7, ISB) from URL or link text, else None."""
    combined = f" {url} {link_text} ".upper()
    if "X15" in combined:
        return "X15"
    if "B6.7" in combined or "B67" in combined:
        return "B6.7"
    if "ISB" in combined or "ISB6" in combined or "ISB5" in combined:
        return "ISB"
    return None


def _infer_section(text_chunk: str) -> str:
    """Infer section from chunk content (e.g. Maintenance Procedures, Operation)."""
    chunk_lower = (text_chunk or "")[:800].lower()
    if "maintenance" in chunk_lower and ("procedure" in chunk_lower or "schedule" in chunk_lower):
        return "Maintenance Procedures"
    if "maintenance" in chunk_lower:
        return "Maintenance"
    if "operation" in chunk_lower and ("instruction" in chunk_lower or "manual" in chunk_lower):
        return "Operation and Instructions"
    if "operation" in chunk_lower:
        return "Operation"
    if "safety" in chunk_lower or "warning" in chunk_lower or "caution" in chunk_lower:
        return "Safety and Warnings"
    if "specification" in chunk_lower or "specifications" in chunk_lower:
        return "Specifications"
    if "troubleshoot" in chunk_lower or "diagnostic" in chunk_lower:
        return "Troubleshooting"
    if "parts" in chunk_lower or "part number" in chunk_lower:
        return "Parts"
    if "warranty" in chunk_lower:
        return "Warranty"
    return "General"


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into chunks of chunk_size words with overlap words between consecutive chunks."""
    if not text or not text.strip():
        return []
    words = text.split()
    if len(words) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def discover_pdf_urls() -> list[tuple[str, str]]:
    """Scrape base URLs for PDF links containing X15, B6.7, or ISB. Returns list of (url, engine_model)."""
    seen = set()
    results: list[tuple[str, str]] = []

    for base_url in SCRAPE_BASE_URLS:
        try:
            resp = requests.get(base_url, headers=REQUEST_HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                text = (a.get_text() or "").strip()
                if not href.lower().endswith(".pdf"):
                    continue
                full_url = urljoin(base_url, href)
                if full_url in seen:
                    continue
                engine = _normalize_engine_model(full_url, text)
                if engine:
                    seen.add(full_url)
                    results.append((full_url, engine))
            time.sleep(0.5)
        except Exception as e:
            print(f"  Scrape warning for {base_url}: {e}")

    for url in SEED_PDF_URLS:
        url = url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        engine = _normalize_engine_model(url, "")
        if not engine:
            if "x15" in url.lower() or "X15" in url:
                engine = "X15"
            elif "b6.7" in url.lower() or "b67" in url.lower():
                engine = "B6.7"
            elif "isb" in url.lower():
                engine = "ISB"
            else:
                engine = "X15"
        results.append((url, engine))

    return results


def extract_text_from_pdf(pdf_bytes: bytes) -> list[tuple[str, int]]:
    """Extract text per page. Returns list of (page_text, page_number) with 1-based page numbers."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required. Install with: pip install pymupdf")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        text = page.get_text()
        pages.append((text, i + 1))
    doc.close()
    return pages


def build_manual_documents(
    pdf_url: str,
    engine_model: str,
    pages: list[tuple[str, int]],
    version: str = "1.0",
) -> list[dict[str, Any]]:
    """Build MongoDB documents for each chunk. Schema: manualId, engineModel, section, content, pageNumber, metadata."""
    url_hash = hashlib.sha256(pdf_url.encode()).hexdigest()[:12]
    docs = []
    chunk_global_idx = 0
    for page_text, page_num in pages:
        chunks = _chunk_text(page_text, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
        for chunk in chunks:
            if not chunk.strip():
                continue
            section = _infer_section(chunk)
            manual_id = f"{engine_model}_{url_hash}_p{page_num}_c{chunk_global_idx}"
            docs.append({
                "manualId": manual_id,
                "engineModel": engine_model,
                "section": section,
                "content": chunk.strip(),
                "pageNumber": page_num,
                "metadata": {"url": pdf_url, "version": version},
            })
            chunk_global_idx += 1
    return docs


def load_manuals_into_mongodb() -> None:
    """Discover PDFs, extract text, chunk, and insert into Manuals collection."""
    if fitz is None:
        print("ERROR: PyMuPDF is required. Run: pip install pymupdf")
        return
    if "<db_password>" in MONGODB_URI:
        print("ERROR: Set MONGODB_PASSWORD in environment or replace <db_password> in MONGODB_URI.")
        return

    print("Discovering PDF URLs (scraping + seed)...")
    pdf_list = discover_pdf_urls()
    print(f"Found {len(pdf_list)} PDF(s) to process.")

    all_docs: list[dict[str, Any]] = []
    for pdf_url, engine_model in pdf_list:
        try:
            resp = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
            resp.raise_for_status()
            pdf_bytes = resp.content
        except Exception as e:
            print(f"  Skip (download failed): {pdf_url} -> {e}")
            continue
        try:
            pages = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            print(f"  Skip (PDF extract failed): {pdf_url} -> {e}")
            continue
        version = "1.0"
        docs = build_manual_documents(pdf_url, engine_model, pages, version)
        all_docs.extend(docs)
        print(f"  {pdf_url} -> {len(pages)} page(s), {len(docs)} chunk(s)")
        time.sleep(0.3)

    if not all_docs:
        print("No documents to insert.")
        return

    client: MongoClient = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    coll = db[MANUALS_COLLECTION]

    clear_first = os.environ.get("CLEAR_MANUALS", "0").strip().lower() in ("1", "true", "yes")
    if clear_first:
        coll.delete_many({})
        print("Cleared existing Manuals collection.")

    coll.insert_many(all_docs)
    print(f"Inserted {len(all_docs)} document(s) into {MANUALS_COLLECTION}.")
    client.close()


if __name__ == "__main__":
    load_manuals_into_mongodb()
