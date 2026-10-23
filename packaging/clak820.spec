# PyInstaller: uma pasta com dois executáveis que compartilham as mesmas DLLs.
#   clak820.exe      app da bandeja, sem janela (o que o usuário abre)
#   clak820-cli.exe  linha de comando (statusline do Claude Code, install, status, ...)
# Build:  pyinstaller packaging/clak820.spec --noconfirm

from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "assets" / "icon.ico")
EXCLUDES = [
    "tkinter", "unittest", "pytest", "numpy", "ssl", "_ssl", "charset_normalizer",
    "requests", "urllib3", "PIL.ImageQt", "PIL.ImageTk", "PIL._avif", "PIL._webp",
]
COMMON = dict(pathex=[str(ROOT)], hiddenimports=["hid", "pystray._win32"], excludes=EXCLUDES)

cli = Analysis([str(ROOT / "packaging" / "cli_entry.py")], **COMMON)
tray = Analysis([str(ROOT / "packaging" / "tray_entry.py")], **COMMON)

cli_exe = EXE(
    PYZ(cli.pure),
    cli.scripts,
    exclude_binaries=True,
    name="clak820-cli",
    console=True,
    icon=ICON,
)
tray_exe = EXE(
    PYZ(tray.pure),
    tray.scripts,
    exclude_binaries=True,
    name="clak820",
    console=False,
    icon=ICON,
)

COLLECT(
    cli_exe, cli.binaries, cli.datas,
    tray_exe, tray.binaries, tray.datas,
    name="clak820",
)
