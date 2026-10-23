"""install / uninstall / start / stop / status no Windows.

- statusLine em ~/.claude/settings.json (com backup)
- inicialização automática pela chave Run do registro (HKCU, sem admin)
- daemon rodando em segundo plano, sem janela
"""

from __future__ import annotations

import json
import msvcrt
import os
import shutil
import signal
import subprocess
import sys
import winreg
from pathlib import Path

from . import data_dir

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "clak820"
MARK = "clak820"  # identifica um statusLine nosso

DETACHED = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def claude_settings_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "settings.json"


# ---- comandos que o Windows / Claude Code vão executar --------------------


# No executável há dois programas lado a lado:
#   clak820.exe      app da bandeja (sem janela) — o que o usuário abre
#   clak820-cli.exe  linha de comando — usada pelo statusLine do Claude Code
GUI_EXE = "clak820.exe"
CLI_EXE = "clak820-cli.exe"


def statusline_command() -> str:
    if frozen():
        return f'"{Path(sys.executable).with_name(CLI_EXE).as_posix()}" statusline'
    return "python -m clak820 statusline"


def daemon_argv() -> list[str]:
    """Comando que inicia o app da bandeja (autostart e `start`)."""
    if frozen():
        return [str(Path(sys.executable).with_name(GUI_EXE))]
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return [str(pythonw if pythonw.exists() else sys.executable), "-m", "clak820", "tray"]


# ---- settings.json ------------------------------------------------------


class ForeignStatusLine(RuntimeError):
    """Já existe um statusLine que não é do clak820."""


def apply_statusline(settings: dict, command: str | None, force: bool = False) -> dict:
    """Retorna settings com o nosso statusLine (command=None remove o nosso)."""
    current = settings.get("statusLine")
    ours = isinstance(current, dict) and MARK in str(current.get("command", ""))
    out = dict(settings)
    if command is None:
        if ours:
            out.pop("statusLine")
        return out
    if current and not ours and not force:
        raise ForeignStatusLine(
            "Você já tem outro statusLine configurado no Claude Code. "
            "Use --force para substituir (um backup é salvo)."
        )
    out["statusLine"] = {"type": "command", "command": command}
    return out


def configure_statusline(force: bool = False) -> Path:
    return _edit_settings(statusline_command(), force)


def _edit_settings(command: str | None, force: bool = False) -> Path:
    path = claude_settings_path()
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    new = apply_statusline(settings, command, force)
    if new != settings:
        if path.exists():
            shutil.copy2(path, path.with_name("settings.json.bak-clak820"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# ---- inicialização automática -------------------------------------------


def _quote(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv)


def set_autostart(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, _quote(daemon_argv()))
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def autostart_value() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, RUN_NAME)[0]
    except FileNotFoundError:
        return None


# ---- daemon -------------------------------------------------------------


def daemon_running() -> bool:
    """O daemon segura um lock em daemon.lock enquanto roda."""
    try:
        f = open(data_dir() / "daemon.lock", "a+")
    except OSError:
        return True
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        return False
    except OSError:
        return True
    finally:
        f.close()


def start_daemon() -> bool:
    if daemon_running():
        return False
    subprocess.Popen(
        daemon_argv(),
        creationflags=DETACHED,
        close_fds=True,
        cwd=str(data_dir()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def stop_daemon() -> bool:
    pid_file = data_dir() / "daemon.pid"
    if not daemon_running():
        pid_file.unlink(missing_ok=True)
        return False
    try:
        os.kill(int(pid_file.read_text()), signal.SIGTERM)
    except (OSError, ValueError):
        return False
    pid_file.unlink(missing_ok=True)
    return True


# ---- comandos -----------------------------------------------------------


def install(force: bool = False, autostart: bool = True) -> None:
    path = configure_statusline(force)
    print(f"✓ statusLine configurado em {path}")
    if autostart:
        set_autostart(True)
        print("✓ inicia junto com o Windows")
    if start_daemon():
        print("✓ clak820 iniciado (ícone na bandeja)")
    else:
        print("• clak820 já estava rodando")
    print("Pronto! Use o Claude Code normalmente; a tela atualiza sozinha (teclado no cabo).")


def uninstall() -> None:
    stop_daemon()
    set_autostart(False)
    _edit_settings(None)
    # Uma reinstalação deve refazer a configuração inicial (autostart etc.).
    (data_dir() / "setup.done").unlink(missing_ok=True)
    print("✓ daemon parado, inicialização automática e statusLine removidos")
    print(f"Seus dados continuam em {data_dir()} (pode apagar se quiser).")


def status() -> None:
    from .device import list_interfaces
    from . import protocol as p

    settings = claude_settings_path()
    cmd = ""
    if settings.exists():
        try:
            cmd = str((json.loads(settings.read_text(encoding="utf-8")).get("statusLine") or {}).get("command", ""))
        except ValueError:
            pass
    pids = {d["product_id"] for d in list_interfaces()}
    mode = (
        "cabo (tela disponível)" if pids & set(p.WIRED_PIDS)
        else "Bluetooth (sem tela)" if p.BLUETOOTH_PID in pids
        else "2.4 GHz (sem tela)" if p.RECEIVER_PID in pids
        else "não encontrado"
    )
    print(f"daemon:      {'rodando' if daemon_running() else 'parado'}")
    print(f"statusLine:  {'ok' if MARK in cmd else 'não configurado'}")
    print(f"autostart:   {'sim' if autostart_value() else 'não'}")
    print(f"teclado:     {mode}")
    print(f"dados/log:   {data_dir()}")
