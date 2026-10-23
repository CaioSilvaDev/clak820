import json
from datetime import date, datetime, timezone

from clak820.render import Panel, render, to_frame
from clak820.statusline import line, merge
from clak820.usage import TokenCounter, five_hour, fmt_tokens


def _entry(ts, msg_id, req, out, inp=0, cache_read=0):
    return json.dumps(
        {
            "timestamp": ts,
            "requestId": req,
            "message": {
                "id": msg_id,
                "usage": {
                    "input_tokens": inp,
                    "output_tokens": out,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": cache_read,
                },
            },
        }
    )


def test_token_counter_dedupes_and_filters_day(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    old = "2000-01-01T00:00:00Z"
    f = tmp_path / "proj" / "s.jsonl"
    f.parent.mkdir()
    f.write_text(
        "\n".join(
            [
                _entry(now, "m1", "r1", 10, 5, 100),
                _entry(now, "m1", "r1", 10, 5, 100),  # duplicada
                _entry(old, "m0", "r0", 999),  # outro dia
                '{"type":"user"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    c = TokenCounter(tmp_path)
    assert c.update(date.today()) == 115
    assert c.output == 10
    # Linha nova acrescentada é lida de forma incremental; linha incompleta espera.
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(_entry(now, "m2", "r2", 1) + "\n" + _entry(now, "m3", "r3", 7)[:20])
    assert c.update(date.today()) == 116


def test_fmt_tokens():
    assert fmt_tokens(999) == "999"
    assert fmt_tokens(1234) == "1.23k"
    assert fmt_tokens(12_345_678) == "12.3M"
    assert fmt_tokens(123_456_789) == "123M"


def test_statusline_merge_keeps_previous_limits():
    data = {
        "model": {"display_name": "Opus"},
        "rate_limits": {"five_hour": {"used_percentage": 23.5, "resets_at": 2_000}},
    }
    s = merge({}, data, now=1_000)
    assert s["rate_limits"]["five_hour"]["used_percentage"] == 23.5
    s2 = merge(s, {"model": {"display_name": "Opus"}}, now=1_500)
    assert s2["rate_limits"]["five_hour"]["used_percentage"] == 23.5
    assert merge(s, {}, now=2_500)["rate_limits"] == {}  # janela expirou
    assert "5h 24%" in line(s) or "5h 23%" in line(s)


def test_five_hour_reset_passed():
    st = {"rate_limits": {"five_hour": {"used_percentage": 80, "resets_at": 100}}}
    assert five_hour(st, now=50).pct == 80
    assert five_hour(st, now=150).pct == 0
    assert five_hour({}, now=0) is None


def test_render_size_and_frame():
    for pct in (None, 0, 42, 100):
        img = render(Panel(pct, "21:30", "12.3M"))
        assert img.size == (128, 128)
        assert len(to_frame(img).rgb565) == 128 * 128 * 2
