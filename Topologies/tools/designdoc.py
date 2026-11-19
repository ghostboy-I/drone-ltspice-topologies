"""Tiny PDF document builder for the topology design notes (matplotlib only, no LaTeX needed).

Usage:
    doc = Doc("Title", "subtitle")
    doc.h("1. Heading"); doc.p("Text with inline math like $V = IR$.")
    doc.eq(r"\\Delta I = \\frac{V D (1-D)}{L f}", note="ripple")
    doc.table(["Col A", "Col B"], [["1", "2"]], widths=[0.5, 0.5])
    doc.img("plot.png", width=6.5); doc.figure(draw_fn, height=2.0)
    doc.save("out.pdf")
"""
import re, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages

PAGE_W, PAGE_H = 8.5, 11.0
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 0.9, 0.8, 0.8
TEXT_W = PAGE_W - 2 * MARGIN_X
INK, INK2, RULE, ACCENT = "#0b0b0b", "#52514e", "#d6d5d0", "#2a78d6"
plt.rcParams["mathtext.fontset"] = "dejavuserif"


class Doc:
    def __init__(self, title, subtitle=""):
        self.blocks = [("title", title, subtitle)]

    # ---- content API ------------------------------------------------------
    def h(self, text): self.blocks.append(("h", text))
    def p(self, text, size=10): self.blocks.append(("p", text, size))
    def bullets(self, items): [self.blocks.append(("p", "•  " + it, 10)) for it in items]
    def eq(self, tex, note="", size=13): self.blocks.append(("eq", tex, note, size))
    def table(self, header, rows, widths=None): self.blocks.append(("table", header, rows, widths))
    def img(self, path, width=TEXT_W): self.blocks.append(("img", path, width))
    def figure(self, fn, height): self.blocks.append(("fig", fn, height))
    def pagebreak(self): self.blocks.append(("break",))
    def sheet(self, path, caption=""):
        """A full landscape page holding one large image (schematic sheets), embedded at its native resolution."""
        self.blocks.append(("sheet", path, caption))

    # ---- layout -----------------------------------------------------------
    @staticmethod
    def _wrap(text, size):
        chars = int(TEXT_W / (size * 0.0072))           # empirical avg glyph width for DejaVu Sans
        protected = re.sub(r"\$[^$]*\$", lambda m: m.group(0).replace(" ", " "), text)
        lines = textwrap.wrap(protected, chars, subsequent_indent="    " if text.startswith("•") else "")
        return [l.replace(" ", " ") for l in lines] or [""]

    def _height(self, b):
        k = b[0]
        if k == "title": return 0.95
        if k == "h": return 0.42
        if k == "p": return len(self._wrap(b[1], b[2])) * b[2] / 72 * 1.45 + 0.08
        if k == "eq": return b[3] / 72 * 2.6 + (0.18 if b[2] else 0)
        if k == "table": return 0.26 * (len(b[2]) + 1) + 0.15
        if k == "img":
            im = mpimg.imread(b[1]); return b[2] * im.shape[0] / im.shape[1] + 0.12
        if k == "fig": return b[2] + 0.1
        return 0

    def save(self, path):
        pages, cur, y = [], [], 0.0
        avail = PAGE_H - MARGIN_TOP - MARGIN_BOT
        for i, b in enumerate(self.blocks):
            if b[0] == "break":
                pages.append(cur); cur, y = [], 0.0; continue
            if b[0] == "sheet":
                if cur: pages.append(cur)
                pages.append(b); cur, y = [], 0.0; continue
            hgt = self._height(b)
            # keep headings with the next block: break early if a heading lands near the bottom
            nxt = self.blocks[i + 1] if i + 1 < len(self.blocks) else None
            keep = 0 if not (b[0] == "h" and nxt and nxt[0] != "break") else (self._height(nxt) if nxt[0] in ("img", "fig", "table", "eq") else min(self._height(nxt), 0.8))
            if cur and y + hgt + keep > avail:   # never strand a heading at the bottom of a page
                pages.append(cur); cur, y = [], 0.0
            cur.append((b, y, hgt)); y += hgt
        if cur: pages.append(cur)
        title = self.blocks[0][1]
        with PdfPages(path) as pdf:
            for n, page in enumerate(pages, 1):
                if isinstance(page, tuple):
                    self._sheet_page(pdf, page, title, n, len(pages)); continue
                fig = plt.figure(figsize=(PAGE_W, PAGE_H)); fig.patch.set_facecolor("white")
                for b, y, hgt in page:
                    self._draw(fig, b, PAGE_H - MARGIN_TOP - y, hgt)
                fig.text(MARGIN_X / PAGE_W, 0.4 / PAGE_H, title, color=INK2, fontsize=8)
                fig.text(1 - MARGIN_X / PAGE_W, 0.4 / PAGE_H, f"{n} / {len(pages)}", color=INK2, fontsize=8, ha="right")
                pdf.savefig(fig); plt.close(fig)
        return len(pages)

    @staticmethod
    def _sheet_page(pdf, b, title, n, npages):
        W, H, m = PAGE_H, PAGE_W, 0.45                   # landscape
        fig = plt.figure(figsize=(W, H)); fig.patch.set_facecolor("white")
        im = mpimg.imread(b[1]); top = H - m - (0.35 if b[2] else 0); bot = 0.6
        aw, ah = W - 2 * m, top - bot; ar = im.shape[0] / im.shape[1]
        w, h = (aw, aw * ar) if aw * ar <= ah else (ah / ar, ah)
        ax = fig.add_axes([(W - w) / 2 / W, (bot + (ah - h) / 2) / H, w / W, h / H])
        ax.imshow(im, interpolation="none"); ax.axis("off")
        if b[2]: fig.text(m / W, (H - m - 0.2) / H, b[2], fontsize=11, weight="bold", color=INK)
        fig.text(m / W, 0.3 / H, title, color=INK2, fontsize=8)
        fig.text(1 - m / W, 0.3 / H, f"{n} / {npages}", color=INK2, fontsize=8, ha="right")
        pdf.savefig(fig); plt.close(fig)

    def _draw(self, fig, b, top, hgt):
        X = lambda inch: inch / PAGE_W
        Y = lambda inch: inch / PAGE_H
        k = b[0]
        if k == "title":
            fig.text(X(MARGIN_X), Y(top - 0.35), b[1], fontsize=18, weight="bold", color=INK)
            fig.text(X(MARGIN_X), Y(top - 0.68), b[2], fontsize=9, color=INK2)
            fig.add_artist(plt.Line2D([X(MARGIN_X), X(PAGE_W - MARGIN_X)], [Y(top - 0.85)] * 2, color=ACCENT, lw=1.5))
        elif k == "h":
            fig.text(X(MARGIN_X), Y(top - 0.3), b[1], fontsize=12.5, weight="bold", color=INK)
        elif k == "p":
            lh = b[2] / 72 * 1.45
            for i, line in enumerate(self._wrap(b[1], b[2])):
                fig.text(X(MARGIN_X), Y(top - (i + 0.85) * lh), line, fontsize=b[2], color=INK)
        elif k == "eq":
            fig.text(0.5, Y(top - b[3] / 72 * 1.5), "$" + b[1] + "$", fontsize=b[3], ha="center", va="center", color=INK)
            if b[2]:
                fig.text(0.5, Y(top - b[3] / 72 * 2.6 - 0.05), b[2], fontsize=8.5, ha="center", color=INK2, style="italic")
        elif k == "table":
            header, rows, widths = b[1], b[2], b[3] or [1 / len(b[1])] * len(b[1])
            xs = [MARGIN_X]
            for w in widths[:-1]: xs.append(xs[-1] + w * TEXT_W)
            for r, row in enumerate([header] + rows):
                yy = top - 0.2 - 0.26 * r
                for x, cell in zip(xs, row):
                    fig.text(X(x + 0.04), Y(yy), cell, fontsize=9, color=INK, weight="bold" if r == 0 else "normal")
                if r == 0 or r == len(rows):
                    fig.add_artist(plt.Line2D([X(MARGIN_X), X(PAGE_W - MARGIN_X)], [Y(yy - 0.09)] * 2, color=RULE, lw=0.8))
        elif k == "img":
            im = mpimg.imread(b[1]); w = b[2]; h = w * im.shape[0] / im.shape[1]
            ax = fig.add_axes([X(MARGIN_X + (TEXT_W - w) / 2), Y(top - h), X(w), Y(h)]); ax.imshow(im, interpolation="none"); ax.axis("off")
        elif k == "fig":
            ax = fig.add_axes([X(MARGIN_X), Y(top - b[2]), X(TEXT_W), Y(b[2])]); ax.axis("off"); b[1](ax)
