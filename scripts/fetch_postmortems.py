"""
Fetch postmortems from danluu/post-mortems and save as normalized
markdown files in data/postmortems/.

Run:  uv run python scripts/fetch_postmortems.py
"""
import asyncio
import re
from pathlib import Path

import httpx

README_URL = "https://raw.githubusercontent.com/danluu/post-mortems/master/README.md"
OUT_DIR = Path(__file__).parent.parent / "data" / "postmortems"

SKIP_SECTIONS = {
    "Other lists of postmortems",
    "Analysis",
    "Contributors",
    "Table of Contents",
}


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:40]


def parse_entries(readme: str) -> list[dict]:
    entries = []
    sections = re.split(r"\n## ", readme)

    for section in sections[1:]:
        lines = section.split("\n", 1)
        category = lines[0].strip()
        if category in SKIP_SECTIONS:
            continue
        body = lines[1] if len(lines) > 1 else ""

        for para in re.split(r"\n\n+", body):
            para = para.strip()
            match = re.match(r"\[([^\]]+)\]\(([^)]+)\)\.?\s*(.+)", para, re.DOTALL)
            if not match:
                continue
            company = match.group(1).strip()
            url = match.group(2).strip()
            description = re.sub(r"\s+", " ", match.group(3)).strip()
            entries.append(
                {
                    "company": company,
                    "url": url,
                    "category": category,
                    "description": description,
                }
            )

    return entries


def write_postmortem(entry: dict, idx: int, out_dir: Path) -> Path:
    pm_id = f"PM-{idx:03d}"
    slug = slugify(entry["company"])
    path = out_dir / f"{pm_id}-{slug}.md"
    path.write_text(
        f"# {pm_id} — {entry['company']}\n\n"
        f"**Company:** {entry['company']}  \n"
        f"**Category:** {entry['category']}  \n"
        f"**Source:** {entry['url']}\n\n"
        f"## Incident Summary\n\n"
        f"{entry['description']}\n",
        encoding="utf-8",
    )
    return path


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching danluu/post-mortems README...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(README_URL)
        resp.raise_for_status()

    entries = parse_entries(resp.text)
    print(f"Parsed {len(entries)} entries")

    for idx, entry in enumerate(entries, start=1):
        write_postmortem(entry, idx, OUT_DIR)

    print(f"Saved {len(entries)} files to {OUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
