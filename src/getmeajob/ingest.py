from __future__ import annotations

from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix == ".docx":
        doc = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)

    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")


def extract_job_text_from_url(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    parts: list[str] = []

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if title:
        parts.append(title)

    headings = [
        element.get_text(" ", strip=True)
        for element in soup.find_all(["h1", "h2", "h3"])
    ]
    body = [
        element.get_text(" ", strip=True)
        for element in soup.find_all(["p", "li"])
    ]

    parts.extend(text for text in headings if text)
    parts.extend(text for text in body if text)

    combined = "\n".join(parts).strip()
    if not combined:
        raise ValueError("No readable text found at URL.")

    return combined
