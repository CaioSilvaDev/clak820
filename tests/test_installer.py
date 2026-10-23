import pytest

from clak820 import device
from clak820.installer import apply_statusline

OURS = "python -m clak820 statusline"


def test_statusline_added_and_removed():
    s = apply_statusline({"theme": "dark"}, OURS)
    assert s == {"theme": "dark", "statusLine": {"type": "command", "command": OURS}}
    assert apply_statusline(s, None) == {"theme": "dark"}


def test_foreign_statusline_is_protected():
    other = {"statusLine": {"type": "command", "command": "my-script.sh"}}
    with pytest.raises(RuntimeError):
        apply_statusline(other, OURS)
    assert apply_statusline(other, OURS, force=True)["statusLine"]["command"] == OURS
    assert apply_statusline(other, None) == other  # uninstall não mexe no dos outros


@pytest.mark.parametrize(
    "pid, words",
    [(0xFEFE, "Bluetooth"), (0xFDFD, "2.4 GHz"), (None, "não encontrado")],
)
def test_wireless_messages(monkeypatch, pid, words):
    devs = [] if pid is None else [
        {"product_id": pid, "usage_page": 1, "interface_number": -1, "path": b"x"}
    ]
    monkeypatch.setattr(device, "list_interfaces", lambda: devs)
    with pytest.raises(device.DeviceError, match=words):
        device.Keyboard().__enter__()
