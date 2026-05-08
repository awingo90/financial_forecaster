"""Thin client around the Obsidian Local REST API plugin.

Falls back to direct filesystem writes when the plugin isn't reachable, so the
system stays usable on a fresh install before the user configures the plugin.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
from loguru import logger

from .config import settings


class ObsidianClient:
    def __init__(self) -> None:
        self.base = settings.obsidian_api_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.obsidian_api_key}"}
        self.vault = Path(settings.vault_path).expanduser()

    # ------------------------------------------------------------------ helpers
    def _fs_write(self, rel_path: str, content: str, append: bool = False) -> Path:
        target = self.vault / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        logger.info(f"vault write (fs): {target}")
        return target

    def _api_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base}/", headers=self.headers, timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------ public
    def write_note(self, rel_path: str, content: str) -> str:
        """Create or overwrite a note. Returns absolute path or vault-relative URI."""
        if settings.obsidian_api_key and self._api_available():
            url = f"{self.base}/vault/{rel_path}"
            r = httpx.put(url, headers=self.headers, content=content.encode("utf-8"), timeout=10.0)
            r.raise_for_status()
            logger.info(f"vault write (api): {rel_path}")
            return rel_path
        return str(self._fs_write(rel_path, content, append=False))

    def append_note(self, rel_path: str, content: str) -> str:
        if settings.obsidian_api_key and self._api_available():
            url = f"{self.base}/vault/{rel_path}"
            r = httpx.post(url, headers={**self.headers, "Content-Type": "text/markdown"},
                           content=content.encode("utf-8"), timeout=10.0)
            r.raise_for_status()
            return rel_path
        return str(self._fs_write(rel_path, content, append=True))

    def read_note(self, rel_path: str) -> str:
        if settings.obsidian_api_key and self._api_available():
            url = f"{self.base}/vault/{rel_path}"
            r = httpx.get(url, headers=self.headers, timeout=10.0)
            r.raise_for_status()
            return r.text
        target = self.vault / rel_path
        return target.read_text(encoding="utf-8") if target.exists() else ""

    def append_to_memory(self, agent: str, summary: str, run_id: str) -> None:
        rel = f"Agents/Memory/{agent.lower()}.md"
        line = f"\n- {datetime.utcnow().isoformat(timespec='seconds')}Z `{run_id[:8]}` {summary}\n"
        self.append_note(rel, line)

    def write_run_log(self, agent: str, run_id: str, payload: str) -> str:
        rel = f"Agents/Logs/{agent}-{run_id}.json"
        return self.write_note(rel, payload)


obsidian = ObsidianClient()
