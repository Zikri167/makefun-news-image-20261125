"""Procedural front-page renderer for news-image-20261125.

Stdlib only. Draws a 1024x1024 newspaper front page for Wednesday
25 November 2026 and writes it as a deterministic PNG: fixed palette,
fixed geometry, zlib level 9, no timestamps, no randomness, so two runs
produce byte-identical output.
"""
import base64
import struct
import zlib

from fontdata import FONTS

W, H = 1024, 1024
PAPER = (247, 243, 232)
INK = (20, 20, 20)
RED = (163, 18, 18)
BLUE = (29, 78, 137)
GRAY = (110, 105, 95)
LIGHT = (233, 227, 212)
MID = (200, 192, 172)


class Canvas:
    def __init__(self, w=W, h=H, bg=PAPER):
        self.w, self.h = w, h
        self.buf = bytearray(bg * (w * h))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(c)

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + (x1 - x0) * 3] = bytes(c) * (x1 - x0)

    def hline(self, x, y, w, c, t=1):
        for k in range(t):
            self.rect(x, y + k, w, 1, c)

    def vline(self, x, y, h, c, t=1):
        for k in range(t):
            self.rect(x + k, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            for a in range(t):
                for b in range(t):
                    self.px(x + a, y + b, c)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for k in range(t):
            rr = r - k
            if rr <= 0:
                break
            for a in range(360):
                import math
                x = cx + int(rr * math.cos(math.radians(a)))
                y = cy + int(rr * math.sin(math.radians(a)))
                self.px(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for dy in range(-ry, ry + 1):
            dx = int(rx * (1 - (dy * dy) / (ry * ry)) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def poly(self, pts, c):
        # Scanline fill, even-odd rule.
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), y, max(1, int(xs[k + 1]) - int(xs[k])), 1, c)

    # ---- text ----
    def _glyph(self, font, ch):
        f = FONTS[font]
        g = f["chars"].get(ch)
        if g is None:
            g = f["chars"]["?"]
        return f, g

    def text_w(self, font, s):
        f = FONTS[font]
        total = 0
        for ch in s:
            g = f["chars"].get(ch, f["chars"]["?"])
            total += g[0]
        return total

    def text(self, font, x, y_baseline, s, c=INK):
        """Draw s with its baseline at y_baseline. Returns width drawn."""
        f = FONTS[font]
        cx = x
        for ch in s:
            g = f["chars"].get(ch, f["chars"]["?"])
            adv, w, h, y0, b64 = g
            if w and h:
                bits = base64.b64decode(b64)
                top = y_baseline - f["ascent"] + y0
                bi = 0
                for yy in range(h):
                    for xx in range(w):
                        byte = bits[bi >> 3]
                        if byte & (0x80 >> (bi & 7)):
                            self.px(cx + xx, top + yy, c)
                        bi += 1
            cx += adv
        return cx - x

    def text_center(self, font, cx, y_baseline, s, c=INK):
        w = self.text_w(font, s)
        return self.text(font, cx - w // 2, y_baseline, s, c)

    def wrap(self, font, s, width):
        lines, cur = [], ""
        for word in s.split(" "):
            trial = (cur + " " + word).strip()
            if self.text_w(font, trial) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def para(self, font, x, y_baseline, s, width, leading, c=INK):
        y = y_baseline
        for ln in self.wrap(font, s, width):
            self.text(font, x, y, ln, c)
            y += leading
        return y


def write_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * cv.w * 3:(y + 1) * cv.w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---- pictograms (flat vector shapes) ----

def draw_ship(cv, x, y, w, h):
    # Cargo ship on waves, with a red target ring over it.
    hull_y = y + int(h * 0.62)
    cv.poly([(x, hull_y), (x + w, hull_y),
             (x + int(w * 0.88), hull_y + int(h * 0.22)),
             (x + int(w * 0.12), hull_y + int(h * 0.22))], INK)
    cv.rect(x + int(w * 0.18), hull_y - int(h * 0.30), int(w * 0.42), int(h * 0.30), INK)
    cv.rect(x + int(w * 0.24), hull_y - int(h * 0.46), int(w * 0.20), int(h * 0.16), RED)
    cv.rect(x + int(w * 0.68), hull_y - int(h * 0.52), int(w * 0.05), int(h * 0.52), INK)
    cv.line(x + int(w * 0.68), hull_y - int(h * 0.52), x + int(w * 0.86), hull_y - int(h * 0.40), INK, 2)
    # containers
    for i, cx in enumerate((0.30, 0.42, 0.54)):
        cv.rect(x + int(w * cx), hull_y - int(h * 0.14), int(w * 0.10), int(h * 0.14),
                BLUE if i % 2 else GRAY)
    # smoke (just above the funnel)
    for dx, dy, r in ((0.68, -0.50, 7), (0.73, -0.56, 9), (0.78, -0.60, 7)):
        cv.circle(x + int(w * dx), y + int(h * (0.62 + dy)), r, GRAY)
    # waves
    for wy in (0.90, 0.97):
        for wx in (0.05, 0.35, 0.65):
            cv.hline(x + int(w * wx), y + int(h * wy), int(w * 0.22), BLUE, 3)
    # red target ring
    cv.ring(x + int(w * 0.55), y + int(h * 0.42), int(h * 0.34), RED, 3)
    cv.hline(x + int(w * 0.55) - 8, y + int(h * 0.42), 17, RED, 2)
    cv.vline(x + int(w * 0.55), y + int(h * 0.42) - 8, 17, RED, 2)


def draw_tower(cv, x, y, w, h):
    tx = x + int(w * 0.30)
    tw = int(w * 0.40)
    cv.rect(tx, y + int(h * 0.12), tw, int(h * 0.88), INK)
    cv.rect(tx + tw // 2 - 2, y, 4, int(h * 0.12), INK)
    cv.circle(tx + tw // 2, y + 4, 4, RED)
    for r in range(6):
        for c in range(3):
            cv.rect(tx + 8 + c * (tw // 3), y + int(h * 0.20) + r * int(h * 0.11),
                    tw // 3 - 12, int(h * 0.06), BLUE)
    # impact burst, red star
    bx, by = tx + tw // 2, y + int(h * 0.42)
    pts = []
    import math
    for k in range(16):
        ang = math.pi * k / 8
        rr = 26 if k % 2 == 0 else 10
        pts.append((bx + int(rr * math.cos(ang)), by + int(rr * math.sin(ang))))
    cv.poly(pts, RED)
    cv.circle(bx, by, 7, PAPER)
    # falling debris
    for dx, dy in ((-34, 30), (30, 44), (-20, 58), (38, 18)):
        cv.rect(bx + dx, by + dy, 5, 5, GRAY)


def draw_turkey(cv, x, y, w, h, fleeing=False):
    import math
    cx, cy = x + w // 2, y + int(h * 0.58)
    # tail fan
    for k in range(-2, 3):
        ang = -math.pi / 2 + k * 0.42
        ex = cx + int(52 * math.cos(ang))
        ey = cy - 6 + int(52 * math.sin(ang))
        cv.line(cx, cy - 4, ex, ey, RED if k % 2 == 0 else INK, 5)
    # body
    cv.ellipse(cx, cy + 8, 30, 24, INK)
    # head + beak + eye
    cv.circle(cx + 24, cy - 22, 11, INK)
    cv.circle(cx + 27, cy - 24, 2, PAPER)
    cv.poly([(cx + 33, cy - 24), (cx + 44, cy - 20), (cx + 33, cy - 16)], RED)
    # legs
    cv.vline(cx - 8, cy + 30, 12, INK, 2)
    cv.vline(cx + 8, cy + 30, 12, INK, 2)
    if fleeing:
        for i in range(4):
            cv.circle(x + w - 14 - i * 12, y + h - 12 - i * 4, 2, GRAY)


def draw_bars(cv, x, y, w, h):
    base = y + h - 14
    vals = (0.35, 0.62, 1.0)
    bw = int(w * 0.20)
    for i, v in enumerate(vals):
        bh = int((h - 30) * v)
        bx = x + int(w * 0.12) + i * int(w * 0.32)
        cv.rect(bx, base - bh, bw, bh, RED if i == 2 else GRAY)
    cv.hline(x, base, w, INK, 2)
    cv.text("body", x + int(w * 0.12), y + 16, "700,000+", RED)


def draw_huawei(cv, x, y, w, h):
    # building + circuit lines + padlock
    cv.rect(x, y + int(h * 0.30), int(w * 0.55), int(h * 0.70), INK)
    for r in range(4):
        for c in range(3):
            cv.rect(x + 10 + c * 22, y + int(h * 0.38) + r * 16, 12, 9, BLUE)
    cv.line(x + int(w * 0.55), y + int(h * 0.30), x + w, y + 8, BLUE, 2)
    cv.line(x + w, y + 8, x + w - 14, y + int(h * 0.30), BLUE, 2)
    cv.circle(x + w - 14, y + int(h * 0.30), 4, BLUE)
    # padlock
    lx, ly = x + int(w * 0.72), y + int(h * 0.55)
    cv.ring(lx + 14, ly, 12, RED, 3)
    cv.rect(lx, ly, 28, 24, RED)
    cv.circle(lx + 14, ly + 12, 4, PAPER)


# ---- layout ----

def panel_rule(cv, y):
    cv.hline(28, y, 968, INK, 2)


def render(path):
    cv = Canvas()
    # double outer frame
    cv.rect(0, 0, W, 4, INK)
    cv.rect(0, H - 4, W, 4, INK)
    cv.rect(0, 0, 4, H, INK)
    cv.rect(W - 4, 0, 4, H, INK)
    cv.rect(10, 10, W - 20, 2, INK)
    cv.rect(10, H - 12, W - 20, 2, INK)

    # ---- masthead ----
    cv.text_center("masthead", W // 2, 78, "THE WORLD IN ONE DAY", INK)
    cv.hline(28, 92, 968, INK, 2)
    cv.text_center("headline", W // 2, 122, "WEDNESDAY, 25 NOVEMBER 2026", RED)
    cv.text_center("label", W // 2, 146,
                   "THE DAY'S WORLD NEWS  \u2014  IN ONE IMAGE", GRAY)
    panel_rule(cv, 156)

    # ---- lead: Ukraine ship strike ----
    y = 170
    cv.text("label", 28, y + 14, "UKRAINE WAR  \u00b7  GULF OF FINLAND", RED)
    cv.text("headline", 28, y + 62, "Ukraine confirms strike", INK)
    cv.text("headline", 28, y + 104, "on Russian ship", INK)
    cv.para("deck", 28, y + 140,
            "Zelenskiy says the Sparta II carried weapons and was a "
            "legitimate target. Norway, a close ally, urges caution.",
            600, 26)
    draw_ship(cv, 660, y + 6, 320, 190)
    cv.text("body", 28, y + 216, "Reuters  \u00b7  Bloomberg  \u2014  Kyiv / Oslo", GRAY)
    panel_rule(cv, 396)

    # ---- three panels ----
    pxs = (28, 356, 684)
    panels = [
        ("MIDDLE EAST  \u00b7  RIYADH", "Houthis strike Riyadh tower",
         "PIF Tower hit again \u2014 11 wounded, the second attack in a week.",
         draw_tower),
        ("USA  \u00b7  THANKSGIVING", "Trump pardons the turkeys",
         "Freedom and Feathers spared; Feathers fled into the bushes.",
         draw_turkey),
        ("UKRAINE WAR  \u00b7  TOLL", "700,000 Russian troops killed",
         "New analysis puts Russia's war dead past 700,000.",
         draw_bars),
    ]
    for (x, (kick, head, deck, pic)) in zip(pxs, panels):
        if x > 28:
            cv.vline(x - 16, 412, 244, MID, 1)
        cv.text("label", x, 424, kick, RED)
        pic(cv, x, 436, 312, 88)
        yy = cv.para("subhead", x, 552, head, 312, 29)
        cv.para("body", x, yy + 10, deck, 312, 21)
    panel_rule(cv, 668)

    # ---- Huawei strip ----
    y = 684
    cv.text("label", 28, y + 14, "TECH  \u00b7  TRADE SECRETS", RED)
    cv.text("subhead", 28, y + 52, "Huawei convicted of stealing", INK)
    cv.text("subhead", 28, y + 82, "trade secrets", INK)
    cv.text("deck", 28, y + 118,
            "US jury finds the Chinese telecom giant guilty.", INK)
    draw_huawei(cv, 700, y + 8, 280, 130)
    panel_rule(cv, 812)

    # ---- IN BRIEF ----
    y = 818
    cv.text("label", 28, y + 14, "IN BRIEF", RED)
    cv.hline(120, y + 8, 876, INK, 1)
    briefs = [
        "CIA and ODNI hit by cyber breach; unclassified data taken",
        "Sarkozy corruption case ordered to trial in France",
        "Swedish parliament votes on Kristersson as prime minister",
        "Fort Hood gunman seeks stay of execution set for next week",
        "England beat Australia by 8 wickets in the 2nd T20I",
        "NATO vows space defence amid Russian satellite reports",
        "South Korea education minister quits over exam scandal",
    ]
    yy = y + 38
    for b in briefs:
        cv.rect(28, yy - 11, 8, 8, RED)
        cv.text("body", 46, yy, b, INK)
        yy += 18
    panel_rule(cv, 974)

    # ---- footer ----
    cv.text_center("body", W // 2, 992,
                   "Sources: Reuters  \u00b7  Bloomberg  \u00b7  RFE/RL  \u00b7  AP  \u00b7  BBC   \u2014   Early edition",
                   GRAY)
    return write_png(cv, path)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "entry.png"
    n = render(out)
    print(f"wrote {out} {n} bytes")
