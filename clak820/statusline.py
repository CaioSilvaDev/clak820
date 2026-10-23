"""Comando de statusLine do Claude Code.

O Claude Code envia um JSON no stdin a cada atualização. Guardamos os limites
(5h / 7 dias) em state.json para o daemon e imprimimos uma linha curta.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime

from .usage import read_state, write_state


def _hhmm(epoch: float | None) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M") if epoch else "--:--"


def merge(prev: dict, data: dict, now: float) -> dict:
    """Novo estado: limites atuais; se ausentes nesta chamada, mantém os anteriores ainda válidos."""
    limits = dict(prev.get("rate_limits") or {})
    for name, w in (data.get("rate_limits") or {}).items():
        if isinstance(w, dict):
            limits[name] = w
    limits = {
        k: w for k, w in limits.items() if not w.get("resets_at") or float(w["resets_at"]) > now
    }
    model = (data.get("model") or {}).get("display_name") or prev.get("model")
    return {"rate_limits": limits, "model": model, "updated_at": now}


def line(state: dict) -> str:
    parts = [state.get("model") or "Claude"]
    five = (state.get("rate_limits") or {}).get("five_hour")
    if five and five.get("used_percentage") is not None:
        parts.append(f"5h {five['used_percentage']:.0f}% (reset {_hhmm(five.get('resets_at'))})")
    week = (state.get("rate_limits") or {}).get("seven_day")
    if week and week.get("used_percentage") is not None:
        parts.append(f"sem {week['used_percentage']:.0f}%")
    return " · ".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace") or "{}")
    except ValueError:
        data = {}
    try:
        state = merge(read_state(), data, time.time())
        write_state(state)
        print(line(state))
    except Exception as e:  # o statusLine nunca deve quebrar o Claude Code
        print(f"clak820: {e}")
    return 0
