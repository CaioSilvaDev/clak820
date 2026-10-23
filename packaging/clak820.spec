# PyInstaller: uma pasta com dois executáveis que compartilham as mesmas DLLs.
#   clak820.exe         linha de comando (install, status, statusline, ...)
#   clak820-daemon.exe  daemon sem janela (inicia com o Windows)
# Build:  pyinstaller packaging/clak820.spec --noconfirm

from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "assets" / "icon.ico")
EXCLUDES = [
    "tkinter", "unittest", "pytest", "numpy", "ssl", "_ssl", "charset_normalizer",
    "requests", "urllib3", "PIL.ImageQt", "PIL.ImageTk", "PIL._avif", "PIL._webp",
]
COMMON = dict(pathex=[str(ROOT)], hiddenimports=["hid"], excludes=EXCLUDES)

cli = Analysis([str(ROOT / "packaging" / "cli_entry.py")], **COMMON)
daemon = Analysis([str(ROOT / "packaging" / "daemon_entry.py")], **COMMON)

cli_exe = EXE(
    PYZ(cli.pure),
    cli.scripts,
    exclude_binaries=True,
    name="clak820",
    console=True,
    icon=ICON,
)
daemon_exe = EXE(
    PYZ(daemon.pure),
    daemon.scripts,
    exclude_binaries=True,
    name="clak820-daemon",
    console=False,
    icon=ICON,
)

COLLECT(
    cli_exe, cli.binaries, cli.datas,
    daemon_exe, daemon.binaries, daemon.datas,
    name="clak820",
)
