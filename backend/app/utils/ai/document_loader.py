"""Turn an uploaded file into searchable, plan-tagged LangChain chunks.

Supports PDF (via PyPDFLoader) and plain text / markdown. Every chunk carries
``plan_id`` / ``document_id`` / ``filename`` / ``page`` metadata so the chat can
cite its sources and so retrieval stays scoped to a single plan.
"""

import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Chunk size/overlap follow the langchain-rag skill guidance (1000 / 200).
_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

_PDF_TYPES = {"application/pdf"}
_TEXT_TYPES = {"text/plain", "text/markdown"}
_TEXT_EXTS = {".txt", ".md", ".markdown"}


def is_supported(filename: str, content_type: str | None) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    if content_type in _PDF_TYPES or ext == ".pdf":
        return True
    return content_type in _TEXT_TYPES or ext in _TEXT_EXTS


def _load_raw(file_bytes: bytes, filename: str, content_type: str | None) -> list[Document]:
    ext = os.path.splitext(filename)[1].lower()
    is_pdf = content_type in _PDF_TYPES or ext == ".pdf"

    if is_pdf:
        # PyPDFLoader needs a real path; clean the temp file up afterwards.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            return PyPDFLoader(tmp_path).load()
        finally:
            os.unlink(tmp_path)

    text = file_bytes.decode("utf-8", errors="replace")
    return [Document(page_content=text, metadata={})]


def load_and_split(
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    plan_id: int,
    document_id: int,
) -> list[Document]:
    """Load, split, and stamp a document's chunks with plan/source metadata."""
    chunks = _splitter.split_documents(_load_raw(file_bytes, filename, content_type))
    for chunk in chunks:
        chunk.metadata.update(
            {
                "plan_id": plan_id,
                "document_id": document_id,
                "filename": filename,
                # PyPDFLoader sets a 0-based "page"; default to 0 for text files.
                "page": chunk.metadata.get("page", 0),
            }
        )
    return chunks
