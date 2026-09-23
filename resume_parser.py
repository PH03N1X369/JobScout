"""Extract plain text from an uploaded resume (PDF, DOCX, TXT/MD)."""

import io
import os
import zipfile
from xml.etree import ElementTree

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_PDF_PAGES = 10
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ResumeParseError(ValueError):
    pass


def extract_text(filename, data):
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ResumeParseError("Unsupported file type. Upload a PDF, DOCX, or TXT file.")
    try:
        if ext == ".pdf":
            text = _pdf_text(data)
        elif ext == ".docx":
            text = _docx_text(data)
        else:
            text = _plain_text(data)
    except ResumeParseError:
        raise
    except Exception as exc:  # corrupt or password-protected files
        raise ResumeParseError(f"Could not read this file ({exc.__class__.__name__}).") from exc

    text = text.strip()
    if len(text) < 30:
        raise ResumeParseError(
            "Couldn't find any text in this resume. If it's a scanned PDF, "
            "try a text-based PDF or DOCX instead."
        )
    return text


def _pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ResumeParseError("This PDF is password-protected.") from exc
    # Resumes are short; capping pages keeps a huge or hostile PDF from tying up the server.
    return "\n".join(page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES])


def _docx_text(data):
    # A .docx is a zip; the body lives in word/document.xml. Walking every <w:p>
    # in document order also picks up text inside tables, which many resume
    # templates use for their skills and experience sections.
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        root = ElementTree.fromstring(zf.read("word/document.xml"))
    lines = []
    for para in root.iter(f"{_W}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{_W}tab", f"{_W}br"):
                parts.append(" ")
        lines.append("".join(parts))
    return "\n".join(lines)


def _plain_text(data):
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")
