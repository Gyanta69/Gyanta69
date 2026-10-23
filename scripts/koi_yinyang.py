#!/usr/bin/env python3
"""Render two ASCII koi circling as a yin-yang, as a self-contained animated SVG.

GitHub READMEs can't run JavaScript, but they do play CSS animations inside
SVG images. Each frame is rasterised to a grid of coloured glyphs (top-down
koi shaded by the light, translucent fins, a glowing wake on a dotted pond)
and the frames are flipped with CSS keyframes.

    python3 scripts/koi_yinyang.py                      # writes assets/koi-yinyang.svg
    python3 scripts/koi_yinyang.py --preview 30 out.svg # only frame 30, static
"""
import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

COLS, ROWS = 120, 50
FONT = 15
CW, CH = 9, 16  # character cell in px
ASPECT = CW / CH  # converts columns into row-sized world units
W, H = COLS * CW, ROWS * CH

FRAMES = 120
DURATION = 12.0  # one full turn of the yin-yang
BEATS = 12  # tail beats per turn, an integer so the loop is seamless

R = 21.0  # yin-yang radius, in rows
CX, CY = COLS / 2, ROWS / 2
SPAN = math.radians(150)  # how far round the circle each koi's body reaches
LIGHT = (-0.45, -0.55, 0.7)

BODY_GLYPHS = "=+*#%@"  # dark to bright
EDGE_GLYPHS = ".:;'"
FIN_GLYPHS = ".:'`~"
RIDGE_GLYPHS = "@8%"

KOI = [
    {   # yang: white kohaku with red patches and a dark spot on its head
        "head": math.pi / 2,
        "skin": ["#9aa6b6", "#cfd7e2", "#ffffff"],
        "patch": ["#a8231c", "#e83a2c", "#ff6a55"],
        "fin": ["#b8c3d1", "#ff9a8a"],
        "spot": ("@", "#1b1e26"),
        "eye": ("o", "#1b1e26"),
        "wake": "#6ee6ff",
        "seed": 1.7,
    },
    {   # yin: black koi with gold patches and a white spot on its head
        "head": -math.pi / 2,
        "skin": ["#4a5265", "#768099", "#aab4cb"],
        "patch": ["#b8730c", "#f0a020", "#ffd060"],
        "fin": ["#8a94ab", "#f0b850"],
        "spot": ("@", "#ffffff"),
        "eye": ("o", "#ffffff"),
        "wake": "#ffb627",
        "seed": 4.2,
    },
]


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def half_width(s):
    """Top-down koi half-width (rows) from snout (s=0) to the tail root (s=0.78)."""
    if s < 0.1:
        return 0.15 * R * math.sin(s / 0.1 * math.pi / 2) ** 0.55
    if s < 0.26:
        return 0.15 * R + 0.025 * R * smoothstep(0.1, 0.26, s)
    return 0.03 * R + 0.145 * R * max(0.0, 1 - (s - 0.26) / 0.52) ** 1.3


def tail_width(s):
    """Fan-shaped butterfly tail beyond the peduncle, forked at the end."""
    k = (s - 0.76) / 0.24
    return 0.03 * R + 0.19 * R * math.sin(min(k, 1) * math.pi * 0.6)


def pattern(koi, s, v):
    """Smooth pseudo-random skin markings in body coordinates."""
    z = koi["seed"]
    n = (math.sin(s * 11 + z) * math.sin(v * 2.4 + z * 1.3)
         + 0.7 * math.sin(s * 23 - v * 3 + z * 2.1)
         + 0.4 * math.sin(s * 41 + v * 5 + z))
    return n > 0.35 and s > 0.16


def to_cell(x, y):
    return x / ASPECT + CX, y + CY


def rotate(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def spine(koi, s, phase):
    """Point and unit tangent of the spine in the unrotated frame."""
    def point(u):
        a = koi["head"] - u * SPAN
        rho = R * (0.47 + 0.33 * u ** 1.1)
        wiggle = 0.07 * R * u ** 1.6 * math.sin(math.tau * (1.3 * u) - phase)
        rho += wiggle
        return rho * math.cos(a), rho * math.sin(a)

    x0, y0 = point(s)
    x1, y1 = point(s + 1e-3)
    tx, ty = x0 - x1, y0 - y1  # pointing towards the head
    length = math.hypot(tx, ty)
    return x0, y0, tx / length, ty / length


def render_koi(grid, koi, turn, phase):
    """Splat body, fins and markings of one koi into grid cells."""
    samples = {}

    def splat(x, y, kind, s, v):
        x, y = rotate(x, y, turn)
        c, r = to_cell(x, y)
        key = (int(c), int(r))
        prev = samples.get(key)
        if prev is None:
            samples[key] = [kind, s, v, 1]
            return
        prev[3] += 1
        if kind == "body" and (prev[0] != "body" or abs(v) < abs(prev[2])):
            prev[0], prev[1], prev[2] = kind, s, v

    def paddle(s0, side, length, width, angle):
        """A rounded fin hinged on the body edge, swept back by angle."""
        x, y, tx, ty = spine(koi, s0, phase)
        nx, ny = -ty, tx
        bx, by = x + nx * side * half_width(s0) * 0.85, y + ny * side * half_width(s0) * 0.85
        ux = nx * side * math.cos(angle) - tx * math.sin(angle)
        uy = ny * side * math.cos(angle) - ty * math.sin(angle)
        vx, vy = -uy, ux
        for i in range(30):
            f = i / 29
            span = width * math.sin(math.pi * (0.15 + 0.85 * f)) ** 0.7
            for j in range(-10, 11):
                g = j / 10
                splat(bx + ux * f * length + vx * g * span, by + uy * f * length + vy * g * span, "fin", f, g)

    for i in range(600):
        s = i / 599
        x, y, tx, ty = spine(koi, s, phase)
        nx, ny = -ty, tx
        if s <= 0.79:
            w = half_width(s)
            for j in range(-20, 21):
                v = j / 20
                splat(x + nx * v * w, y + ny * v * w, "body", s, v)
        if s >= 0.76:
            w = tail_width(s)
            notch = 0.6 * smoothstep(0.9, 1.0, s)
            for j in range(-20, 21):
                v = j / 20
                if abs(v) >= notch:
                    splat(x + nx * v * w, y + ny * v * w, "fin", (s - 0.76) / 0.24, v)

    flap = 0.35 * math.sin(phase * 0.5)
    for side in (-1, 1):
        paddle(0.2, side, 0.21 * R, 0.07 * R, 0.95 + flap * side)
        paddle(0.5, side, 0.1 * R, 0.04 * R, 1.05 - flap * side * 0.5)
        x, y, tx, ty = spine(koi, 0.0, phase)
        nx, ny = -ty, tx
        for k in range(10):  # barbels at the mouth
            f = k / 9
            splat(x + tx * 0.3 + nx * side * (0.6 + f * 1.4) - tx * f * 0.8, y + ty * 0.3 + ny * side * (0.6 + f * 1.4) - ty * f * 0.8, "fin", 1.0, side)

    for (c, r), (kind, s, v, count) in samples.items():
        if not (0 <= c < COLS and 0 <= r < ROWS):
            continue
        if kind == "fin":
            if s > 0.8 or count < 3:
                grid[r][c] = ("'" if s > 0.8 else ".", koi["fin"][0], "c")
            else:
                grid[r][c] = (":`'."[(c + 2 * r) % 4], koi["fin"][1] if s < 0.45 else koi["fin"][0], "b")
            continue
        # cylinder shading across the body, in screen space
        x, y, tx, ty = spine(koi, s, phase)
        nx, ny = rotate(-ty, tx, turn)
        nz = math.sqrt(max(0.0, 1 - v * v))
        light = max(0.0, nx * v * LIGHT[0] + ny * v * LIGHT[1] + nz * LIGHT[2])
        b = 0.3 + 0.7 * light
        level = min(2, int(b * 3))
        marked = pattern(koi, s, v)
        if abs(s - 0.06) < 0.022 and 0.35 < abs(v) < 0.8:
            grid[r][c] = (*koi["eye"], 3)
        elif math.hypot((s - 0.16) / 0.055, v / 0.4) < 1:
            grid[r][c] = (*koi["spot"], 3)
        elif count < 5 or abs(v) > 0.92:
            grid[r][c] = (EDGE_GLYPHS[(c + r) % len(EDGE_GLYPHS)], koi["skin"][2], 2)
        elif 0.3 < s < 0.62 and abs(v) < 0.1:
            grid[r][c] = (RIDGE_GLYPHS[(c + r) % len(RIDGE_GLYPHS)], (koi["patch"] if marked else koi["skin"])[max(0, level - 1)], 2)
        else:
            palette = koi["patch"] if marked else koi["skin"]
            glyph = BODY_GLYPHS[min(len(BODY_GLYPHS) - 1, int(b * len(BODY_GLYPHS)))]
            grid[r][c] = (glyph, palette[level], 2)


def yinyang(grid, turn, blocked):
    """Dotted yin-yang disc in the rotating frame, kept clear of the koi."""
    for r in range(ROWS):
        for c in range(COLS):
            x, y = (c + 0.5 - CX) * ASPECT, r + 0.5 - CY
            if math.hypot(x, y) >= R - 0.5 or grid[r][c] is not None or (c, r) in blocked:
                continue
            lx, ly = rotate(x, y, -turn)
            light = (lx > 0 or math.hypot(lx, ly - R / 2) < R / 2) and math.hypot(lx, ly + R / 2) >= R / 2
            if math.hypot(lx, ly - R / 2) < R / 7:
                light = False
            elif math.hypot(lx, ly + R / 2) < R / 7:
                light = True
            if light and (c + r) % 2 == 0:
                grid[r][c] = (":", "#4f86b3", 0)


def wake(grid, koi, turn, blocked):
    """A glowing wake on the outer ring, fading behind each tail."""
    tail = koi["head"] - SPAN + turn
    for r in range(ROWS):
        for c in range(COLS):
            x, y = (c + 0.5 - CX) * ASPECT, r + 0.5 - CY
            d = math.hypot(x, y)
            if not (0.7 * R < d < 1.08 * R):
                continue
            behind = (tail - math.atan2(y, x)) % math.tau
            if behind > 2.2:
                continue
            fade = (1 - behind / 2.2) ** 1.6 * math.exp(-((d - 0.84 * R) / (0.1 * R)) ** 2)
            if fade > 0.12 and grid[r][c] is None and (c, r) not in blocked:
                glyph = "*" if fade > 0.75 else (":" if fade > 0.4 else ".")
                grid[r][c] = (glyph, koi["wake"], "a" if fade > 0.4 else "c")


def pond():
    """Static dotted water, the yin-yang rim, lily pads and lotus flowers."""
    rng = random.Random(69)
    grid = [[None] * COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            x, y = (c + 0.5 - CX) * ASPECT, r + 0.5 - CY
            d = math.hypot(x, y)
            if d < R - 0.5:
                continue
            if abs(d - 1.0 * R) < 0.45:
                grid[r][c] = (":", "#1f4a63")
            elif (c + r) % 2 == 0:
                tint = rng.choice(["#13203a"] * 12 + ["#1d3a3a", "#3a1d40", "#22285a"])
                grid[r][c] = (".", "#1b3550" if d < R else tint)

    def put(c, r, glyph, color):
        if 0 <= r < ROWS and 0 <= c < COLS:
            grid[r][c] = (glyph, color)

    def lily(cc, rr, rad, notch_at, lotus):
        for r in range(int(rr - rad) - 1, int(rr + rad) + 2):
            for c in range(int(cc - rad / ASPECT) - 1, int(cc + rad / ASPECT) + 2):
                x, y = (c + 0.5 - cc) * ASPECT, r + 0.5 - rr
                d, a = math.hypot(x, y), math.atan2(y, x)
                if d < rad and abs((a - notch_at + math.pi) % math.tau - math.pi) > 0.32:
                    if d > rad - 0.7:
                        put(c, r, "o", "#2f8f4e")
                    elif abs(math.sin(a * 4)) < 0.16:
                        put(c, r, ":", "#7ddc8f")
                    else:
                        put(c, r, "#" if d < rad * 0.6 else "=", "#3cb563" if (c + r) % 2 else "#2f9e55")
        if lotus:
            for r in range(int(rr - 4), int(rr + 5)):
                for c in range(int(cc - 8), int(cc + 9)):
                    x, y = (c + 0.5 - cc) * ASPECT, r + 0.5 - rr
                    d, a = math.hypot(x, y), math.atan2(y, x)
                    outer = 3.4 * (0.5 + 0.5 * abs(math.cos(a * 2.5)))
                    inner = 2.2 * (0.5 + 0.5 * abs(math.cos(a * 2.5 + 0.6)))
                    if d < 0.8:
                        put(c, r, "@", "#ffd166")
                    elif d < inner:
                        put(c, r, "*", "#ffe0ec")
                    elif d < outer:
                        put(c, r, "%" if d < outer - 0.6 else "'", "#ff8fb8" if d < outer - 0.6 else "#ff5d95")

    lily(13, 8, 4.5, 0.8, True)
    lily(24, 42, 3.2, 2.5, False)
    lily(104, 40, 5, -2.2, True)
    lily(110, 9, 3, 1.9, False)
    return grid


def rows_svg(grid, classes):
    out = []
    for r, row in enumerate(grid):
        spans, c = [], 0
        while c < COLS:
            if row[c] is None:
                c += 1
                continue
            start, key = c, row[c][1:]
            chars = []
            while c < COLS:
                if row[c] is not None and row[c][1:] == key:
                    chars.append(row[c][0])
                elif row[c] is None and c + 1 < COLS and row[c + 1] is not None and row[c + 1][1:] == key:
                    chars.append(" ")  # bridge one-cell gaps so dotted runs stay in one span
                else:
                    break
                c += 1
            text = escape("".join(chars))
            spans.append(f'<tspan x="{start * CW}" class="{classes(key)}">{text}</tspan>')
        if spans:
            out.append(f'<text y="{r * CH + 12}">{"".join(spans)}</text>')
    return "".join(out)


def build(only_frame=None):
    names = {}

    def classes(key):
        color = key[0]
        if color not in names:
            names[color] = f"c{len(names)}"
        cls = names[color]
        if len(key) > 1 and key[1] in ("a", "b", "c"):
            cls += f" o{key[1]}"
        return cls

    background = rows_svg([[(cell[0], cell[1]) if cell else None for cell in row] for row in pond()], classes)

    frames = []
    step = DURATION / FRAMES
    for i in range(FRAMES):
        if only_frame is not None and i != only_frame:
            continue
        t = i / FRAMES
        turn = math.tau * t
        phase = math.tau * BEATS * t
        grid = [[None] * COLS for _ in range(ROWS)]
        for koi in KOI:
            render_koi(grid, koi, turn, phase)
        for koi in KOI:
            wake(grid, koi, turn, ())
        yinyang(grid, turn, ())
        body = rows_svg(grid, classes)
        if only_frame is not None:
            frames.append(f"<g>{body}</g>")
        else:
            frames.append(f'<g class="f{" f0" if i == 0 else ""}" style="animation-delay:{i * step:.2f}s">{body}</g>')

    palette = "".join(f".{name}{{fill:{color}}}" for color, name in names.items())
    animation = "" if only_frame is not None else (
        f".f{{opacity:0;animation:fr {DURATION}s step-end infinite}}"
        f"@keyframes fr{{0%{{opacity:1}}{100 / FRAMES:.4f}%{{opacity:0}}100%{{opacity:0}}}}"
        "@media (prefers-reduced-motion:reduce){.f{animation:none}.f0{opacity:1}}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Two ASCII koi, one white and red, one black and gold, circling each other as a yin-yang in a dotted pond">
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT}px;white-space:pre}}
{palette}.oa{{opacity:.95}}.ob{{opacity:.6}}.oc{{opacity:.3}}
{animation}
</style>
<rect width="{W}" height="{H}" fill="#05070d"/>
{background}
{"".join(frames)}
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--preview":
        out, svg = Path(sys.argv[3]), build(int(sys.argv[2]))
    else:
        out, svg = Path(__file__).resolve().parent.parent / "assets" / "koi-yinyang.svg", build()
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
