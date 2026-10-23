"""CLI: clak820 <comando>  (ou python -m clak820 <comando>)"""

from __future__ import annotations

import argparse
import sys
import time

from PIL import Image


def cmd_probe(_a) -> int:
    from .device import list_interfaces
    from . import protocol as p

    devs = list_interfaces()
    if not devs:
        print("Nenhum dispositivo AJAZZ/SONiX (VID 0C45) encontrado.")
        return 1
    for d in devs:
        tag = {p.CONFIG_USAGE_PAGE: "  <- controle", p.DATA_USAGE_PAGE: "  <- tela"}.get(
            d["usage_page"], ""
        )
        print(
            f"PID {d['product_id']:04x}  iface {d['interface_number']}  "
            f"usage_page {d['usage_page']:04x}  usage {d['usage']:04x}{tag}"
        )
    return 0


def cmd_clock(_a) -> int:
    from .device import Keyboard

    with Keyboard() as kb:
        kb.set_clock()
    print("Relógio sincronizado.")
    return 0


def _demo_panel():
    from .render import Panel

    return Panel(pct=42, reset="21:30", tokens="12.3M")


def _live_panel():
    from .daemon import Daemon, load_config
    from .usage import read_state

    d = Daemon(load_config())
    d.counter.update()
    return d.panel(read_state(), time.time())


def cmd_render(a) -> int:
    from .render import render

    panel = _demo_panel() if a.demo else _live_panel()
    img = render(panel)
    img.save(a.out)
    if a.scale > 1:
        img.resize((img.width * a.scale, img.height * a.scale), Image.NEAREST).save(a.out)
    print(f"{panel} -> {a.out}")
    return 0


def cmd_upload(a) -> int:
    from .device import upload_image_frames
    from .render import render, to_frame

    if a.image:
        img = Image.open(a.image)
    else:
        img = render(_demo_panel() if a.demo else _live_panel())
    arg = upload_image_frames([to_frame(img)], a.arg, print if a.verbose else None)
    print(f"Imagem enviada (arg={arg}).")
    return 0


def cmd_statusline(_a) -> int:
    from .statusline import main

    return main()


def cmd_run(a) -> int:
    from .daemon import main

    return main(a.verbose)


def cmd_tray(_a) -> int:
    from .tray import main

    return main()


def cmd_install(a) -> int:
    from .installer import install

    install(force=a.force, autostart=not a.no_autostart)
    return 0


def cmd_uninstall(_a) -> int:
    from .installer import uninstall

    uninstall()
    return 0


def cmd_start(_a) -> int:
    from .installer import start_daemon

    print("clak820 iniciado." if start_daemon() else "O clak820 já está rodando.")
    return 0


def cmd_stop(_a) -> int:
    from .installer import stop_daemon

    print("clak820 parado." if stop_daemon() else "O clak820 não estava rodando.")
    return 0


def cmd_status(_a) -> int:
    from .installer import status

    status()
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    from . import __version__

    ap = argparse.ArgumentParser(
        prog="clak820-cli",
        description="Consumo do Claude Code na tela do AJAZZ AK820 Pro.",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="comando")
    i = sub.add_parser("install", help="configura tudo e liga o daemon (recomendado)")
    i.add_argument("--force", action="store_true", help="substitui um statusLine existente")
    i.add_argument("--no-autostart", action="store_true", help="não iniciar com o Windows")
    i.set_defaults(fn=cmd_install)
    sub.add_parser("uninstall", help="desfaz o install").set_defaults(fn=cmd_uninstall)
    sub.add_parser("status", help="mostra o estado do daemon e do teclado").set_defaults(
        fn=cmd_status
    )
    sub.add_parser("start", help="abre o app da bandeja em segundo plano").set_defaults(
        fn=cmd_start
    )
    sub.add_parser("stop", help="fecha o app da bandeja / daemon").set_defaults(fn=cmd_stop)
    sub.add_parser("tray", help="roda o app da bandeja").set_defaults(fn=cmd_tray)
    sub.add_parser("probe", help="lista as interfaces HID do teclado (só leitura)").set_defaults(
        fn=cmd_probe
    )
    sub.add_parser("clock", help="acerta a hora e volta ao relógio nativo").set_defaults(
        fn=cmd_clock
    )
    r = sub.add_parser("render", help="gera o painel como PNG (não envia)")
    r.add_argument("--demo", action="store_true", help="usa dados de exemplo")
    r.add_argument("--out", default="preview.png")
    r.add_argument("--scale", type=int, default=1, help="amplia o PNG para visualizar")
    r.set_defaults(fn=cmd_render)
    u = sub.add_parser("upload", help="envia uma imagem (ou o painel) para a tela")
    u.add_argument("image", nargs="?", help="arquivo de imagem; sem ele envia o painel")
    u.add_argument("--demo", action="store_true", help="painel com dados de exemplo")
    u.add_argument("--arg", type=int, default=None, help="argumento do comando de tela (1 ou 3)")
    u.add_argument("-v", "--verbose", action="store_true")
    u.set_defaults(fn=cmd_upload)
    sub.add_parser("statusline", help="uso interno: statusLine do Claude Code").set_defaults(
        fn=cmd_statusline
    )
    rn = sub.add_parser("run", help="roda o daemon neste terminal (para depurar)")
    rn.add_argument("-v", "--verbose", action="store_true")
    rn.set_defaults(fn=cmd_run)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except RuntimeError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
