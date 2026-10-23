"""Loop principal: mantém a tela do teclado em dia com o consumo do Claude Code.

- Ativo (houve atividade há pouco): envia o painel quando algo muda,
  no máximo a cada `min_interval_s` (cada envio grava na flash do teclado).
- Ocioso: acerta o relógio uma vez e a tela volta ao relógio nativo.
"""

from __future__ import annotations

import json
import logging
import msvcrt
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from logging.handlers import RotatingFileHandler

from . import data_dir
from .device import DeviceError, Keyboard, upload_image_frames
from .render import Panel, render, to_frame
from .usage import TokenCounter, fmt_tokens, five_hour, read_state

DEFAULTS = {
    "min_interval_s": 300,  # intervalo mínimo entre envios de imagem
    "idle_after_s": 1200,  # sem atividade por este tempo → relógio nativo
    "tick_s": 15,
    "screen_arg": None,  # None = descobre sozinho (1 ou 3)
}

log = logging.getLogger("clak820")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads((data_dir() / "config.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


class Daemon:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.counter = TokenCounter()
        self.path = data_dir() / "daemon.json"
        try:
            self.mem = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.mem = {}
        self.mem.setdefault("mode", None)  # "panel" | "clock"
        self.mem.setdefault("last_upload", 0.0)
        self.mem.setdefault("last_panel", None)
        if cfg.get("screen_arg") is not None:
            self.mem["screen_arg"] = cfg["screen_arg"]
        self.last_error: str | None = None

    def device_ok(self) -> None:
        if self.last_error is not None:
            log.info("teclado conectado via cabo")
            self.last_error = None

    def save(self) -> None:
        self.path.write_text(json.dumps(self.mem), encoding="utf-8")

    def panel(self, state: dict, now: float) -> Panel:
        w = five_hour(state, now)
        return Panel(
            pct=None if w is None else int(round(w.pct)),
            reset=datetime.fromtimestamp(w.resets_at).strftime("%H:%M")
            if w and w.resets_at
            else "--:--",
            tokens=fmt_tokens(self.counter.total),
        )

    def tick(self) -> None:
        now = time.time()
        self.counter.update()
        state = read_state()
        last_activity = max(float(state.get("updated_at") or 0), self.counter.last_activity)
        active = now - last_activity < self.cfg["idle_after_s"]

        if active:
            panel = self.panel(state, now)
            changed = asdict(panel) != self.mem["last_panel"]
            entering = self.mem["mode"] != "panel"
            waited = now - self.mem["last_upload"] >= self.cfg["min_interval_s"]
            if entering or (changed and waited):
                log.info("enviando painel %s", panel)
                arg = upload_image_frames(
                    [to_frame(render(panel))], self.mem.get("screen_arg"), log.debug
                )
                self.device_ok()
                self.mem.update(
                    mode="panel", last_upload=now, last_panel=asdict(panel), screen_arg=arg
                )
                self.save()
        elif self.mem["mode"] != "clock":
            log.info("ocioso: voltando ao relógio nativo")
            with Keyboard() as kb:
                kb.set_clock()
            self.device_ok()
            self.mem["mode"] = "clock"
            self.save()

    def run(self) -> None:
        log.info("daemon iniciado (config %s)", self.cfg)
        while True:
            try:
                self.tick()
            except DeviceError as e:
                if str(e) != self.last_error:  # avisa só quando muda, sem lotar o log
                    log.warning("teclado indisponível: %s", e)
                    self.last_error = str(e)
            except Exception:
                log.exception("erro inesperado")
            time.sleep(self.cfg["tick_s"])


def setup_logging(verbose: bool = False) -> None:
    handler = RotatingFileHandler(
        data_dir() / "daemon.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)


def main(verbose: bool = False) -> int:
    setup_logging(verbose)
    lock = open(data_dir() / "daemon.lock", "w")
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print("O daemon já está rodando.")
        return 1
    (data_dir() / "daemon.pid").write_text(str(os.getpid()))
    if sys.stderr is not None:  # pythonw.exe não tem console
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        log.addHandler(console)
    Daemon(load_config()).run()
    return 0
