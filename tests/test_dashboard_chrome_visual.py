import struct
import zlib
from pathlib import Path

from scripts.verify_dashboard_chrome_visual import extract_visible_text, inspect_png


def test_inspect_png_detects_basic_png_dimensions(tmp_path):
    png = tmp_path / "two_pixel.png"
    _write_png_rgb(
        png,
        width=2,
        height=1,
        rows=[
            [(255, 0, 0), (0, 128, 255)],
        ],
    )

    report = inspect_png(Path(png))

    assert report["width"] == 2
    assert report["height"] == 1
    assert report["unique_sample_count"] == 2


def test_extract_visible_text_ignores_scripts_styles_and_head():
    html = """
    <html>
      <head><title>Alpha Dashboard</title><style>.x { content: 'Run Paper Cycle'; }</style></head>
      <body>
        <h1>Alpha 控制台</h1>
        <div>模拟权益</div>
        <script>const oldText = 'Approval Queue';</script>
      </body>
    </html>
    """

    text = extract_visible_text(html)

    assert "Alpha 控制台" in text
    assert "模拟权益" in text
    assert "Alpha Dashboard" not in text
    assert "Run Paper Cycle" not in text
    assert "Approval Queue" not in text


def _write_png_rgb(path: Path, *, width: int, height: int, rows: list[list[tuple[int, int, int]]]) -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    raw_rows = bytearray()
    for row in rows:
        assert len(row) == width
        raw_rows.append(0)
        for red, green, blue in row:
            raw_rows.extend((red, green, blue))
    assert len(rows) == height
    path.write_bytes(
        signature
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw_rows)))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    import binascii

    body = chunk_type + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)
