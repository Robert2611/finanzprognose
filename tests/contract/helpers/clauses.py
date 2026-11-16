"""Clause IDs from contracts/TRACEABILITY.md (ranges like ``FE-CORE-001..018`` are expanded)."""
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_ROW = re.compile(r"^\|\s*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3})(?:\.\.(\d{3}))?\s*\|", re.M)


@lru_cache(maxsize=1)
def known_ids() -> dict[str, str]:
    """Return {clause_id: section heading} for every clause in TRACEABILITY.md."""
    text = (ROOT / "contracts" / "TRACEABILITY.md").read_text(encoding="utf-8")
    ids: dict[str, str] = {}
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = _ROW.match(line)
        if not m:
            continue
        first, last = m.group(1), m.group(2)
        if last is None:
            ids[first] = section
        else:
            prefix, start = first[:-3], int(first[-3:])
            for n in range(start, int(last) + 1):
                ids[f"{prefix}{n:03d}"] = section
    return ids
