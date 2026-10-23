"""Formato dos bytes do firmware original do AK820 Pro (sem I/O, testável sem teclado).

Baseado na engenharia reversa da comunidade, principalmente deddroid/ak820-rs
(derivado do DeviceDriver.exe oficial) e imgunjan/ak820-linux-studio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

VID = 0x0C45  # SONiX, fabricante do MCU
WIRED_PIDS = (0x8009, 0x800A)
RECEIVER_PID = 0xFDFD  # receptor 2.4 GHz: sem comando de tela
BLUETOOTH_PID = 0xFEFE  # Bluetooth: sem interface de configuração

CONFIG_USAGE_PAGE = 0xFF13  # feature reports de 64 bytes (comandos)
DATA_USAGE_PAGE = 0xFF68  # output reports de 4096 bytes (imagem da tela)
CONFIG_INTERFACE = 3  # fallback quando o backend não informa usage page
DATA_INTERFACE = 2

PACKET = 64
SCREEN_BLOCK = 4096

SIZE = 128
FRAME_BYTES = SIZE * SIZE * 2
HEADER = 256
MAX_FRAMES = 140


class Cmd:
    BEGIN = 0x18
    COMMIT = 0x02
    SAVE = 0xF0  # não usar na tela: corrompe a imagem
    CLOCK = 0x28
    SCREEN = 0x72


def control(command: int, arg: int = 0, count: int = 0) -> bytes:
    """Pacote de controle: [0]=04 [1]=cmd [2]=arg [8..10]=count (LE)."""
    p = bytearray(PACKET)
    p[0] = 0x04
    p[1] = command
    p[2] = arg
    p[8:10] = count.to_bytes(2, "little")
    return bytes(p)


def clock_packet(t: datetime) -> bytes:
    """Pacote de data/hora (números simples, não BCD)."""
    if not 2000 <= t.year <= 2255:
        raise ValueError("ano fora do intervalo suportado")
    p = bytearray(PACKET)
    p[1] = 0x01
    p[2] = 0x5A
    p[3] = t.year - 2000
    p[4:9] = bytes((t.month, t.day, t.hour, t.minute, t.second))
    p[10] = 0x04
    p[62] = 0xAA
    p[63] = 0x55
    return bytes(p)


def rgb565(rgb: bytes) -> bytes:
    """Converte pixels RGB888 (3 bytes/pixel) em RGB565 little-endian."""
    if len(rgb) % 3:
        raise ValueError("tamanho RGB inválido")
    out = bytearray(len(rgb) // 3 * 2)
    j = 0
    for i in range(0, len(rgb), 3):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out[j] = v & 0xFF
        out[j + 1] = v >> 8
        j += 2
    return bytes(out)


@dataclass
class Frame:
    rgb565: bytes
    duration_ms: int = 0  # 0 = imagem estática


def screen_blocks(frames: list[Frame]) -> list[bytes]:
    """Header de 256 bytes + frames, com padding 0xFF em blocos de 4096 bytes."""
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"esperado 1 a {MAX_FRAMES} frames")
    data = bytearray(b"\xff" * HEADER)
    data[0] = len(frames)
    for i, f in enumerate(frames):
        if len(f.rgb565) != FRAME_BYTES:
            raise ValueError(f"cada frame precisa de {FRAME_BYTES} bytes RGB565")
        data[1 + i] = max(1, min(255, f.duration_ms // 2))
    for f in frames:
        data += f.rgb565
    data += b"\xff" * ((-len(data)) % SCREEN_BLOCK)
    return [bytes(data[i : i + SCREEN_BLOCK]) for i in range(0, len(data), SCREEN_BLOCK)]
