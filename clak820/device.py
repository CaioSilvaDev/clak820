"""Transporte USB HID (cabo): comandos na interface 0xFF13, imagem na 0xFF68."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

import hid

from . import protocol as p

PAUSE = 0.035  # o driver oficial espera 35 ms antes e depois de cada comando
ACK_TIMEOUT_MS = 3000


class DeviceError(RuntimeError):
    pass


def list_interfaces() -> list[dict]:
    return sorted(
        (d for d in hid.enumerate(p.VID, 0)),
        key=lambda d: (d["product_id"], d["interface_number"], d["usage_page"]),
    )


def _find(devs: list[dict], usage_page: int, interface: int) -> dict | None:
    cands = [d for d in devs if d["product_id"] in p.WIRED_PIDS]
    for d in cands:
        if d["usage_page"] == usage_page:
            return d
    for d in cands:  # alguns backends não informam usage page
        if d["usage_page"] == 0 and d["interface_number"] == interface:
            return d
    return None


class Keyboard:
    def __init__(self, log: Callable[[str], None] | None = None):
        self.log = log or (lambda _msg: None)
        self.config: hid.device | None = None
        self.data: hid.device | None = None
        self.pid = 0

    # ---- abrir / fechar ------------------------------------------------

    def __enter__(self) -> "Keyboard":
        devs = list_interfaces()
        cfg = _find(devs, p.CONFIG_USAGE_PAGE, p.CONFIG_INTERFACE)
        if cfg is None:
            pids = {d["product_id"] for d in devs}
            if p.BLUETOOTH_PID in pids:
                raise DeviceError("teclado em Bluetooth: a tela só é atualizada no modo com fio")
            if p.RECEIVER_PID in pids:
                raise DeviceError("teclado em 2.4 GHz: a tela só é atualizada no modo com fio")
            if devs:
                raise DeviceError(
                    "Teclado encontrado, mas sem a interface de configuração (0xFF13). "
                    "Use o cabo USB no modo com fio."
                )
            raise DeviceError("AK820 Pro não encontrado. Conecte o cabo USB e use o modo com fio.")
        self.pid = cfg["product_id"]
        self.config = hid.device()
        self.config.open_path(cfg["path"])
        data = _find(devs, p.DATA_USAGE_PAGE, p.DATA_INTERFACE)
        if data is not None:
            self.data = hid.device()
            self.data.open_path(data["path"])
        return self

    def __exit__(self, *_exc) -> None:
        for dev in (self.config, self.data):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        self.config = self.data = None

    # ---- primitivas ----------------------------------------------------

    def _feature(self, packet: bytes) -> None:
        assert self.config is not None
        time.sleep(PAUSE)
        n = self.config.send_feature_report(b"\x00" + packet)  # report ID 0 na frente
        if n < 0:
            raise DeviceError("falha ao enviar comando ao teclado")

    def command(self, packet: bytes) -> bytes | None:
        """Envia um comando e faz a leitura de confirmação que o teclado espera."""
        self._feature(packet)
        time.sleep(PAUSE)
        try:
            reply = bytes(self.config.get_feature_report(0, p.PACKET + 1))
        except (OSError, ValueError):
            return None  # a resposta é só um "ok"; seguimos sem ela
        return reply

    # ---- funções -------------------------------------------------------

    def set_clock(self, t: datetime | None = None) -> None:
        """Acerta o relógio. Também faz a tela voltar a mostrar o relógio nativo."""
        t = t or datetime.now()
        self.command(p.control(p.Cmd.BEGIN, 0, 1))
        self.command(p.control(p.Cmd.CLOCK, 0, 1))
        self.command(p.clock_packet(t))
        self.command(p.control(p.Cmd.COMMIT, 0, 0))
        time.sleep(0.1)

    def upload_screen(
        self,
        blocks: list[bytes],
        arg: int = 1,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Envia a imagem (blocos de 4096 bytes) para a tela."""
        if self.data is None:
            raise DeviceError("Interface de dados da tela (0xFF68) não encontrada.")
        n = len(blocks)
        self.command(p.control(p.Cmd.BEGIN, 0, 0))
        self.command(p.control(p.Cmd.SCREEN, arg, n))
        for i, blk in enumerate(blocks):
            if self.data.write(b"\x00" + blk) < 0:
                raise DeviceError(f"falha ao enviar bloco {i + 1}/{n}")
            ack = self.data.read(p.PACKET, ACK_TIMEOUT_MS)
            if not ack:
                raise DeviceError(f"sem confirmação do bloco {i + 1}/{n}")
            self.log(f"bloco {i + 1}/{n} ack={bytes(ack[:3]).hex(' ')}")
            if progress:
                progress(i + 1, n)
        # Só COMMIT: SAVE corromperia a imagem.
        self.command(p.control(p.Cmd.COMMIT, 0, 0))
        time.sleep(0.1)


def upload_image_frames(
    frames: list[p.Frame], arg: int | None = None, log: Callable[[str], None] | None = None
) -> int:
    """Abre o teclado e envia a imagem. Retorna o `arg` que funcionou.

    O ak820-rs usa arg=1 e o ak820-linux-studio arg=3; se um não confirmar, tenta o outro.
    """
    blocks = p.screen_blocks(frames)
    order = [arg] if arg is not None else [1, 3]
    last: Exception | None = None
    for a in order:
        try:
            with Keyboard(log) as kb:
                kb.upload_screen(blocks, arg=a)
            return a
        except DeviceError as e:
            last = e
            if log:
                log(f"envio com arg={a} falhou: {e}")
            time.sleep(0.5)
    raise DeviceError(str(last))
