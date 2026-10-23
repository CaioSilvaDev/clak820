"""Dados de consumo: limites (state.json, vindo do statusLine) e tokens de hoje (logs JSONL)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import data_dir

STATE_FILE = "state.json"


def claude_projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "projects"


# ---- state.json (escrito pelo statusline) --------------------------------


def read_state(path: Path | None = None) -> dict:
    path = path or data_dir() / STATE_FILE
    for _ in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            time.sleep(0.05)  # arquivo sendo trocado neste instante
    return {}


def write_state(state: dict, path: Path | None = None) -> None:
    path = path or data_dir() / STATE_FILE
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: outro processo lendo o arquivo
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)


@dataclass(frozen=True)
class Window:
    pct: float
    resets_at: float  # epoch em segundos


def five_hour(state: dict, now: float | None = None) -> Window | None:
    """Janela de 5h; se o reset já passou, a janela zerou."""
    now = now or time.time()
    w = (state.get("rate_limits") or {}).get("five_hour")
    if not w or w.get("used_percentage") is None:
        return None
    resets_at = float(w.get("resets_at") or 0)
    if resets_at and resets_at <= now:
        return Window(0.0, 0.0)
    return Window(float(w["used_percentage"]), resets_at)


# ---- tokens de hoje (logs ~/.claude/projects/**/*.jsonl) -----------------


def _local_date(ts: str) -> date | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date()
    except (ValueError, AttributeError):
        return None


class TokenCounter:
    """Soma incremental dos tokens do dia: só lê o que foi acrescentado aos arquivos."""

    def __init__(self, root: Path | None = None):
        self.root = root or claude_projects_dir()
        self.day: date | None = None
        self.offsets: dict[Path, int] = {}
        self.seen: set[str] = set()
        self.total = 0
        self.output = 0
        self.last_activity = 0.0  # mtime do log mais recente

    def _reset(self, day: date) -> None:
        self.day = day
        self.offsets.clear()
        self.seen.clear()
        self.total = self.output = 0

    def update(self, today: date | None = None) -> int:
        today = today or date.today()
        if today != self.day:
            self._reset(today)
        start_of_day = datetime.combine(today, datetime.min.time()).timestamp()
        if not self.root.exists():
            return self.total
        for path in self.root.rglob("*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            self.last_activity = max(self.last_activity, st.st_mtime)
            if st.st_mtime < start_of_day:
                continue
            off = self.offsets.get(path, 0)
            if st.st_size < off:  # arquivo reescrito
                off = 0
            if st.st_size == off:
                continue
            self.offsets[path] = self._read(path, off, today)
        return self.total

    def _read(self, path: Path, off: int, today: date) -> int:
        try:
            with open(path, "rb") as f:
                f.seek(off)
                chunk = f.read()
        except OSError:
            return off
        end = chunk.rfind(b"\n")
        if end < 0:  # nenhuma linha completa ainda
            return off
        for raw in chunk[: end + 1].splitlines():
            if b'"usage"' not in raw:
                continue
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            self._add(entry, today)
        return off + end + 1

    def _add(self, entry: dict, today: date) -> None:
        msg = entry.get("message")
        if not isinstance(msg, dict):
            return
        usage = msg.get("usage")
        if not isinstance(usage, dict) or _local_date(entry.get("timestamp", "")) != today:
            return
        key = f"{msg.get('id')}:{entry.get('requestId')}"
        if msg.get("id") and key in self.seen:
            return
        self.seen.add(key)
        out = int(usage.get("output_tokens") or 0)
        self.output += out
        self.total += out + sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )


def fmt_tokens(n: int) -> str:
    """12345678 -> '12.3M' (3 dígitos significativos, muda pouco)."""
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= div:
            v = n / div
            return f"{v:.2f}{suf}" if v < 10 else f"{v:.1f}{suf}" if v < 100 else f"{v:.0f}{suf}"
    return str(n)
