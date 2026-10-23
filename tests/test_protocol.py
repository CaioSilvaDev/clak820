from datetime import datetime

from clak820 import protocol as p


def test_control_layout():
    pkt = p.control(p.Cmd.SCREEN, 1, 9)
    assert len(pkt) == 64
    assert pkt[:3] == bytes([0x04, 0x72, 0x01])
    assert pkt[8:10] == bytes([9, 0])
    assert pkt[3:8] == bytes(5) and pkt[10:] == bytes(54)


def test_clock_packet():
    pkt = p.clock_packet(datetime(2026, 5, 16, 14, 30, 45))
    assert pkt[:11] == bytes.fromhex("00015a1a05100e1e2d0004")
    assert pkt[62:] == b"\xaa\x55"
    assert len(pkt) == 64


def test_rgb565_little_endian():
    assert p.rgb565(bytes([255, 0, 0])) == bytes([0x00, 0xF8])
    assert p.rgb565(bytes([0, 0, 255])) == bytes([0x1F, 0x00])
    assert p.rgb565(bytes([0, 255, 0])) == bytes([0xE0, 0x07])


def test_still_image_is_nine_blocks():
    blocks = p.screen_blocks([p.Frame(bytes(p.FRAME_BYTES))])
    assert len(blocks) == 9
    assert all(len(b) == 4096 for b in blocks)
    assert blocks[0][:3] == bytes([1, 1, 0xFF])
    assert blocks[-1][-1] == 0xFF


def test_animation_header():
    f = lambda: p.Frame(bytes(p.FRAME_BYTES), 100)  # noqa: E731
    blocks = p.screen_blocks([f(), f()])
    assert len(blocks) == 17
    assert blocks[0][:4] == bytes([2, 50, 50, 0xFF])
