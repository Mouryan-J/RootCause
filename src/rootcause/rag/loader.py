"""Load runbook and postmortem documents from the data directory."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).parents[3] / "data"


@dataclass
class Document:
    doc_id: str
    title: str
    content: str
    source: str  # "runbook" | "postmortem"
    metadata: dict = field(default_factory=dict)


def _extract_metadata(text: str) -> dict:
    """Pull **Key:** Value pairs from markdown bold-label lines."""
    meta: dict = {}
    for line in text.splitlines():
        m = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
    return meta


def _doc_id_from_path(path: Path) -> str:
    # "RB-001-postgres-high-connection-count.md" -> "RB-001"
    # "PM-042-amazon.md" -> "PM-042"
    parts = path.stem.split("-")
    return f"{parts[0]}-{parts[1]}".upper()


def load_corpus() -> list[Document]:
    docs: list[Document] = []

    for source, subdir in [("runbook", "runbooks"), ("postmortem", "postmortems")]:
        subdir_path = DATA_DIR / subdir
        if not subdir_path.exists():
            continue
        for md_file in sorted(subdir_path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            doc_id = _doc_id_from_path(md_file)
            title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
            title = title_match.group(1) if title_match else doc_id
            docs.append(
                Document(
                    doc_id=doc_id,
                    title=title,
                    content=text,
                    source=source,
                    metadata=_extract_metadata(text),
                )
            )

    return docs
