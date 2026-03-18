from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SummaryExtractionError(Exception):
    pass


class TldrService:
    def __init__(self, output_filename: str = "final_summary.json") -> None:
        self.output_filename = output_filename

    def extract(self, result_dir: Path) -> tuple[str | None, str]:
        summary_path = self.find_summary_file(result_dir)
        if summary_path is None:
            raise SummaryExtractionError(
                f"Nisam pronašao {self.output_filename} u {result_dir}."
            )
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        title = self._pick_first(payload, "post_title", "title")
        tldr = self._pick_first(payload, "tldr_comment", "reader_summary", "final_summary")
        if not tldr:
            raise SummaryExtractionError("Sažetak je generiran, ali nedostaje TL;DR tekst.")
        return title, str(tldr).strip()

    def find_summary_file(self, result_dir: Path) -> Path | None:
        direct_path = result_dir / self.output_filename
        if direct_path.exists():
            return direct_path
        for path in result_dir.rglob(self.output_filename):
            return path
        return None

    def _pick_first(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
