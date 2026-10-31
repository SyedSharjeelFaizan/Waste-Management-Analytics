"""Minimal, dependency-free PDF writer (A4, Helvetica) used for the summary report.

It supports exactly what the report needs: a header band, headings, wrapped paragraphs,
bullet lists, striped tables with automatic page breaks and horizontal bar charts drawn as
vector rectangles from the real data. Content streams are written uncompressed so the text
can be checked in tests. Text is limited to Latin-1 (other characters are replaced).
"""
from datetime import datetime

PAGE_W, PAGE_H = 595.28, 841.89
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 46.0, 46.0, 52.0
CONTENT_W = PAGE_W - 2 * MARGIN_X

FOREST = (0.059, 0.239, 0.165)
GREEN = (0.122, 0.420, 0.271)
INK = (0.118, 0.169, 0.141)
MUTED = (0.40, 0.46, 0.43)
LINE = (0.84, 0.88, 0.86)
STRIPE = (0.955, 0.972, 0.963)
WHITE = (1, 1, 1)

# Helvetica advance widths (1/1000 em) for ASCII 32..126
_W = ([278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278]
      + [556] * 10
      + [278, 278, 584, 584, 584, 556, 1015]
      + [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722,
         667, 611, 722, 667, 944, 667, 667, 611]
      + [278, 278, 278, 469, 556, 333]
      + [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333,
         500, 278, 556, 500, 722, 500, 500, 500]
      + [334, 260, 334, 584])
assert len(_W) == 95

_REPLACE = {"≤": "<=", "≥": ">=", "→": "->", "±": "+/-", "–": "-", "—": "-", "−": "-",
            "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "♻": "", "•": "-", "▲": "^", "▼": "v"}


def clean(text: str) -> str:
    """Make text safe for the Latin-1 PDF fonts."""
    s = str(text)
    for k, v in _REPLACE.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def text_width(text: str, size: float, bold: bool = False) -> float:
    total = 0
    for ch in clean(text):
        o = ord(ch)
        total += _W[o - 32] if 32 <= o <= 126 else 556
    return total / 1000.0 * size * (1.06 if bold else 1.0)


def _esc(text: str) -> str:
    return clean(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap(text: str, size: float, width: float, bold: bool = False) -> list:
    lines, cur = [], ""
    for word in clean(text).split():
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, bold) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def fit(text: str, size: float, width: float, bold: bool = False) -> str:
    """Truncate with '...' so the text fits in `width`."""
    s = clean(text)
    if text_width(s, size, bold) <= width:
        return s
    while s and text_width(s + "...", size, bold) > width:
        s = s[:-1]
    return s + "..."


class PDFDocument:
    def __init__(self, title: str, footer: str):
        self.title, self.footer = clean(title), clean(footer)
        self.pages: list = []
        self.new_page()

    # ------------------------------------------------------------ layout helpers
    def new_page(self) -> None:
        self.ops: list = []
        self.pages.append(self.ops)
        self.y = MARGIN_TOP

    def ensure(self, height: float) -> None:
        if self.y + height > PAGE_H - MARGIN_BOTTOM:
            self.new_page()

    def space(self, h: float) -> None:
        self.y += h

    # ------------------------------------------------------------ primitives (top-down y)
    def _color(self, c, stroke=False) -> str:
        return "%.3f %.3f %.3f %s" % (c[0], c[1], c[2], "RG" if stroke else "rg")

    def text(self, x, y_baseline, s, size=10, bold=False, color=INK) -> None:
        self.ops.append("BT %s /%s %.1f Tf %.2f %.2f Td (%s) Tj ET" % (
            self._color(color), "F2" if bold else "F1", size, x, PAGE_H - y_baseline, _esc(s)))

    def rect(self, x, y_top, w, h, fill) -> None:
        self.ops.append("%s %.2f %.2f %.2f %.2f re f" % (self._color(fill), x, PAGE_H - y_top - h, w, h))

    def line(self, x1, y1, x2, y2, color=LINE, width=0.6) -> None:
        self.ops.append("%s %.2f w %.2f %.2f m %.2f %.2f l S" % (
            self._color(color, True), width, x1, PAGE_H - y1, x2, PAGE_H - y2))

    # ------------------------------------------------------------ blocks
    def header_band(self, title: str, subtitle: str) -> None:
        self.rect(0, 0, PAGE_W, 92, FOREST)
        self.rect(0, 92, PAGE_W, 3, GREEN)
        self.text(MARGIN_X, 44, title, 19, True, WHITE)
        self.text(MARGIN_X, 66, subtitle, 10, False, (0.84, 0.92, 0.87))
        self.y = 116

    def heading(self, text: str, size: float = 13) -> None:
        self.ensure(size + 30)
        self.space(8)
        self.text(MARGIN_X, self.y + size, text, size, True, FOREST)
        self.line(MARGIN_X, self.y + size + 5, PAGE_W - MARGIN_X, self.y + size + 5, GREEN, 1.0)
        self.y += size + 14

    def paragraph(self, text: str, size: float = 9.5, color=INK, bold=False, indent: float = 0) -> None:
        lines = wrap(text, size, CONTENT_W - indent, bold)
        lead = size * 1.4
        for ln in lines:
            self.ensure(lead)
            self.text(MARGIN_X + indent, self.y + size, ln, size, bold, color)
            self.y += lead
        self.y += 3

    def bullets(self, items, size: float = 9.5) -> None:
        for it in items:
            lines = wrap(it, size, CONTENT_W - 14)
            lead = size * 1.4
            for i, ln in enumerate(lines):
                self.ensure(lead)
                if i == 0:
                    self.text(MARGIN_X + 3, self.y + size, "-", size, True, GREEN)
                self.text(MARGIN_X + 14, self.y + size, ln, size)
                self.y += lead
            self.y += 2

    def table(self, headers, rows, widths, aligns=None, size: float = 8.5) -> None:
        aligns = aligns or ["l"] * len(headers)
        scale = CONTENT_W / sum(widths) if sum(widths) > CONTENT_W else 1.0
        widths = [w * scale for w in widths]
        rh = size + 7

        def header():
            self.ensure(rh * 2)
            self.rect(MARGIN_X, self.y, sum(widths), rh, FOREST)
            x = MARGIN_X
            for h, w, a in zip(headers, widths, aligns):
                s = fit(h, size, w - 8, True)
                tx = x + 4 if a == "l" else x + w - 4 - text_width(s, size, True)
                self.text(tx, self.y + size + 2.5, s, size, True, WHITE)
                x += w
            self.y += rh

        header()
        for i, row in enumerate(rows):
            if self.y + rh > PAGE_H - MARGIN_BOTTOM:
                self.new_page()
                header()
            if i % 2 == 0:
                self.rect(MARGIN_X, self.y, sum(widths), rh, STRIPE)
            x = MARGIN_X
            for cell, w, a in zip(row, widths, aligns):
                s = fit(cell, size, w - 8)
                tx = x + 4 if a == "l" else x + w - 4 - text_width(s, size)
                self.text(tx, self.y + size + 2.5, s, size)
                x += w
            self.y += rh
        self.line(MARGIN_X, self.y, MARGIN_X + sum(widths), self.y)
        self.y += 8

    def bar_chart(self, rows, vmax: float, legend, label_w: float = 92, bar_h: float = 7.5) -> None:
        """rows = [(label, [(value, (r, g, b)), ...]), ...]; legend = [(name, color), ...]."""
        row_h = bar_h * max(len(r[1]) for r in rows) + 7
        total = len(rows) * row_h + 40
        self.ensure(min(total, 300))
        x0, plot_w = MARGIN_X + label_w, CONTENT_W - label_w - 36
        lx = x0
        for name, col in legend:
            self.rect(lx, self.y + 1, 8, 8, col)
            self.text(lx + 12, self.y + 8.5, name, 8, False, MUTED)
            lx += 22 + text_width(name, 8)
        self.y += 16
        top = self.y
        for i, (label, bars) in enumerate(rows):
            if self.y + row_h > PAGE_H - MARGIN_BOTTOM:
                self.new_page()
                top = self.y
            self.text(MARGIN_X, self.y + bar_h + 2, fit(label, 8.5, label_w - 6), 8.5)
            for j, (val, col) in enumerate(bars):
                by = self.y + j * bar_h
                w = 0 if val is None or val != val else max(0.0, min(val, vmax)) / vmax * plot_w
                self.rect(x0, by, w, bar_h - 1.2, col)
                lab = "n/a" if val is None or val != val else "%.1f" % val
                self.text(x0 + w + 3, by + bar_h - 1.4, lab, 6.5, False, MUTED)
            self.y += row_h
        for tick in (0, 25, 50, 75, 100) if vmax == 100 else ():
            gx = x0 + tick / vmax * plot_w
            self.line(gx, top - 2, gx, self.y, (0.90, 0.93, 0.91), 0.4)
            self.text(gx - 6, self.y + 9, str(tick), 6.5, False, MUTED)
        self.y += 18

    # ------------------------------------------------------------ output
    def to_bytes(self) -> bytes:
        n = len(self.pages)
        stamp = datetime.now().strftime("%d %b %Y, %H:%M")
        contents = []
        for i, ops in enumerate(self.pages, 1):
            foot = list(ops)
            foot.append("%s 0.5 w %.2f %.2f m %.2f %.2f l S" % (
                self._color(LINE, True), MARGIN_X, 38, PAGE_W - MARGIN_X, 38))
            foot.append("BT %s /F1 7.5 Tf %.2f 26 Td (%s) Tj ET" % (
                self._color(MUTED), MARGIN_X, _esc(self.footer + "  |  generated " + stamp)))
            label = "Page %d of %d" % (i, n)
            foot.append("BT %s /F1 7.5 Tf %.2f 26 Td (%s) Tj ET" % (
                self._color(MUTED), PAGE_W - MARGIN_X - text_width(label, 7.5), label))
            contents.append("\n".join(foot).encode("latin-1"))

        objs = {}
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        kids = " ".join("%d 0 R" % (6 + 2 * i) for i in range(n))
        objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n)).encode()
        objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        objs[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        objs[5] = ("<< /Title (%s) /Creator (Waste Management Analytics System) >>" % _esc(self.title)).encode("latin-1")
        for i, body in enumerate(contents):
            p, c = 6 + 2 * i, 7 + 2 * i
            objs[p] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
                       "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % (PAGE_W, PAGE_H, c)).encode()
            objs[c] = b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream"

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = {}
        for num in sorted(objs):
            offsets[num] = len(out)
            out += b"%d 0 obj\n" % num + objs[num] + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for num in sorted(objs):
            out += b"%010d 00000 n \n" % offsets[num]
        out += b"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
        return bytes(out)
