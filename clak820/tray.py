"""App da bandeja do Windows: roda o daemon e mostra o consumo perto do relógio.

Na primeira execução configura sozinho o statusLine do Claude Code e a
inicialização com o Windows, sem precisar de terminal.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

from . import __version__, data_dir, installer
from .daemon import Daemon, acquire_lock, load_config, log, setup_logging
from .render import CLAUDE, TRACK, color_for

REPO_URL = "https://github.com/CaioSilvaDev/clak820"
TITLE = "clak820"

MB_YESNO, MB_ICONINFO, MB_ICONWARN, IDYES = 0x04, 0x40, 0x30, 6

KB_TEXT = {
    "cabo": "Teclado: cabo ✓",
    "bluetooth": "Teclado: Bluetooth (sem tela)",
    "2.4ghz": "Teclado: 2.4 GHz (sem tela)",
    "ausente": "Teclado: não encontrado",
}


def message_box(text: str, flags: int = MB_ICONINFO) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, TITLE, flags)


def tray_icon(pct: int | None) -> Image.Image:
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [20, 20, s - 20, s - 20]
    d.arc(box, 0, 360, fill=TRACK + (255,), width=44)
    if pct:
        d.arc(box, -90, -90 + 360 * min(pct, 100) / 100, fill=color_for(pct) + (255,), width=44)
    r = 34
    d.ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], fill=CLAUDE + (255,))
    return img.resize((64, 64), Image.LANCZOS)


def first_run_setup() -> str | None:
    """Configura statusLine e autostart. Retorna uma mensagem para notificar, se houver."""
    flag = data_dir() / "setup.done"
    try:
        installer.configure_statusline()
    except installer.ForeignStatusLine:
        answer = message_box(
            "Você já tem outro statusLine configurado no Claude Code.\n\n"
            "Substituir pelo do clak820? (um backup é salvo)\n"
            "Sem ele, a tela não recebe os limites de uso.",
            MB_YESNO | MB_ICONWARN,
        )
        if answer == IDYES:
            installer.configure_statusline(force=True)
    if flag.exists():
        return None
    installer.set_autostart(True)
    flag.write_text(__version__)
    return "Tudo pronto! Use o Claude Code normalmente: a tela do teclado atualiza sozinha (no cabo)."


class TrayApp:
    def __init__(self) -> None:
        self.daemon = Daemon(load_config(), on_change=self.refresh)
        self.icon = pystray.Icon(TITLE, tray_icon(None), TITLE, menu=self.menu())
        self._last_pct: object = object()

    # ---- textos dinâmicos ------------------------------------------------

    def usage_text(self, _item=None) -> str:
        p = self.daemon.panel_now
        if p is None or p.pct is None:
            return "5h: aguardando o Claude Code"
        return f"5h: {p.pct}%  ·  reset {p.reset}"

    def tokens_text(self, _item=None) -> str:
        p = self.daemon.panel_now
        return f"Hoje: {p.tokens if p else '…'} tokens"

    def kb_text(self, _item=None) -> str:
        return KB_TEXT.get(self.daemon.kb_mode, "Teclado: ?")

    def menu(self) -> pystray.Menu:
        Item = pystray.MenuItem
        return pystray.Menu(
            Item(self.usage_text, None, enabled=False),
            Item(self.tokens_text, None, enabled=False),
            Item(self.kb_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Atualizar tela agora", lambda: self.daemon.refresh_now(), default=True),
            Item(
                "Pausar (mostrar relógio)",
                lambda: self.daemon.set_paused(not self.daemon.paused),
                checked=lambda _i: self.daemon.paused,
            ),
            Item(
                "Iniciar com o Windows",
                self.toggle_autostart,
                checked=lambda _i: installer.autostart_value() is not None,
            ),
            Item("Abrir pasta de logs", lambda: os.startfile(data_dir())),
            Item(f"Sobre o clak820 {__version__}", lambda: webbrowser.open(REPO_URL)),
            pystray.Menu.SEPARATOR,
            Item("Sair", self.quit),
        )

    # ---- ações -----------------------------------------------------------

    def toggle_autostart(self) -> None:
        installer.set_autostart(installer.autostart_value() is None)

    def refresh(self, daemon: Daemon) -> None:
        p = daemon.panel_now
        pct = None if p is None else p.pct
        if pct != self._last_pct:
            self._last_pct = pct
            self.icon.icon = tray_icon(pct)
        self.icon.title = f"clak820 — {self.usage_text()}"[:127]
        self.icon.update_menu()

    def quit(self) -> None:
        self.daemon.stop.set()
        self.daemon.wake.set()
        self.icon.stop()

    def setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        try:
            note = first_run_setup()
        except Exception:
            log.exception("falha na configuração inicial")
            note = "Não consegui configurar o Claude Code automaticamente. Veja o log."
        if note:
            icon.notify(note, TITLE)
        threading.Thread(target=self.daemon.run, name="daemon", daemon=True).start()

    def run(self) -> None:
        self.icon.run(setup=self.setup)


def main() -> int:
    setup_logging()
    lock = acquire_lock()
    if lock is None:
        message_box("O clak820 já está rodando.\nProcure o ícone na bandeja, perto do relógio.")
        return 1
    try:
        TrayApp().run()
    except Exception:
        logging.getLogger("clak820").exception("erro fatal na bandeja")
        message_box("O clak820 encontrou um erro e vai fechar.\nVeja o log em:\n" + str(data_dir()), MB_ICONWARN)
        return 1
    return 0
