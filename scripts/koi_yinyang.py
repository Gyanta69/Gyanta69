#!/usr/bin/env python3
"""Render two ASCII koi circling as a yin-yang, as a self-contained animated SVG.

GitHub READMEs can't run JavaScript, but they do play CSS animations inside
SVG images. Frames are rasterised to a grid of grey glyphs (top-down koi
shaded by the light, translucent fins, wakes on a rippling ocean) and played
as two crossfading flipbooks: the koi at 24 fps and the slower ocean at 8.

    python3 scripts/koi_yinyang.py                      # writes assets/koi-yinyang.svg
    python3 scripts/koi_yinyang.py --preview 30 out.svg # koi frame 30, static
"""
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

COLS, ROWS = 120, 58  # the pond is the top 50 rows, the name sits below
FONT = 15
CW, CH = 9, 16  # character cell in px
ASPECT = CW / CH  # converts columns into row-sized world units
W, H = COLS * CW, ROWS * CH

KOI_FRAMES = 288
WATER_FRAMES = 96  # must divide KOI_FRAMES
DURATION = 12.0  # one full turn of the yin-yang
BEATS = 12  # tail beats per turn, an integer so the loop is seamless

R = 21.0  # yin-yang radius, in rows
CX, CY = COLS / 2, 25
SPAN = math.radians(150)  # how far round the circle each koi's body reaches
LIGHT = (-0.45, -0.55, 0.7)

BODY_GLYPHS = "=+*#%@"  # dark to bright
EDGE_GLYPHS = ".:;'"
FIN_GLYPHS = ".:'`~"
RIDGE_GLYPHS = "@8%"

NAME = "PRAGYAN KHADKA"
TAGLINE = "A R T   ·   W E B   M O T I O N   ·   T E C H"
NAME_TOP = 49
FONT_3X5 = {  # each pixel is drawn two columns wide
    "P": ["###", "#.#", "###", "#..", "#.."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "N": ["#.#", "###", "###", "#.#", "#.#"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    " ": ["...", "...", "...", "...", "..."],
}

KOI = [
    {   # yang: a white koi with black markings and a black spot on its head
        "head": math.pi / 2,
        "skin": ["#a0a0a0", "#d6d6d6", "#ffffff"],
        "patch": ["#2e2e2e", "#404040", "#555555"],
        "fin": ["#b5b5b5", "#e6e6e6"],
        "edge": "#ffffff",
        "spot": ("@", "#121212"),
        "eye": ("o", "#121212"),
        "wake": "#f0f0f0",
        "seed": 1.7,
    },
    {   # yin: a black koi with white markings and a white spot on its head
        "head": -math.pi / 2,
        "skin": ["#3c3c3c", "#575757", "#747474"],
        "patch": ["#bcbcbc", "#e2e2e2", "#ffffff"],
        "fin": ["#6e6e6e", "#9a9a9a"],
        "edge": "#cfcfcf",
        "spot": ("@", "#ffffff"),
        "eye": ("o", "#ffffff"),
        "wake": "#9a9a9a",
        "seed": 4.2,
    },
]

# Raindrops on the ocean: (x, y) in rows from the centre, and when in the
# loop each one lands. Each drop repeats three times per turn.
DROPS = [(-27, -17, 0.0), (28, 16, 0.33), (-25, 17, 0.66), (29, -18, 0.5)]


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
        level = 2 if b > 0.6 else 1
        marked = pattern(koi, s, v)
        if abs(s - 0.06) < 0.022 and 0.35 < abs(v) < 0.8:
            grid[r][c] = (*koi["eye"], 3)
        elif math.hypot((s - 0.16) / 0.055, v / 0.4) < 1:
            grid[r][c] = (*koi["spot"], 3)
        elif count < 5 or abs(v) > 0.92:
            grid[r][c] = (EDGE_GLYPHS[(c + r) % len(EDGE_GLYPHS)], koi["edge"], 2)
        elif 0.3 < s < 0.62 and abs(v) < 0.1:
            grid[r][c] = (RIDGE_GLYPHS[(c + r) % len(RIDGE_GLYPHS)], (koi["patch"] if marked else koi["skin"])[max(0, level - 1)], 2)
        else:
            palette = koi["patch"] if marked else koi["skin"]
            glyph = BODY_GLYPHS[min(len(BODY_GLYPHS) - 1, int(b * len(BODY_GLYPHS)))]
            grid[r][c] = (glyph, palette[level], 2)


def water(grid, t, turn):
    """Grey rippling ocean: a swell, rings spreading from the centre and from
    raindrops. The disc is bright water on the yang half and dark on yin."""
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] is not None:
                continue
            x, y = (c + 0.5 - CX) * ASPECT, r + 0.5 - CY
            d = math.hypot(x, y)
            if abs(d - R) < 0.45:
                grid[r][c] = (":", "#8c8c8c", 0)
                continue
            h = 0.2 * math.sin(0.42 * x + 0.25 * y - math.tau * 2 * t)
            h += 0.4 * math.sin(0.75 * d - math.tau * 4 * t) * math.exp(-max(0.0, d - R) / 14)
            for dx, dy, lands in DROPS:
                age = (3 * t - lands) % 1
                ring = math.hypot(x - dx, y - dy) - age * 26
                h += 1.5 * (1 - age) ** 0.7 * math.exp(-ring * ring / 3.5) * math.cos(ring * 1.4)
            if d < R:
                lx, ly = rotate(x, y, -turn)
                light = (lx > 0 or math.hypot(lx, ly - R / 2) < R / 2) and math.hypot(lx, ly + R / 2) >= R / 2
                if math.hypot(lx, ly - R / 2) < R / 7:
                    light = False
                elif math.hypot(lx, ly + R / 2) < R / 7:
                    light = True
                color = "#b4b4b4" if light else "#262626"
                h += 0.35 if light else -0.2  # bright water is busier, dark water calmer
            else:
                color = "#565656"
            glyph = "~" if h > 0.75 else ("-" if h > 0.35 else ("." if h > -0.05 else " "))
            grid[r][c] = (glyph, color, 0)


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
                grid[r][c] = (glyph, koi["wake"], 0)


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


def koi_frame(i):
    t = i / KOI_FRAMES
    grid = [[None] * COLS for _ in range(ROWS)]
    for koi in KOI:
        render_koi(grid, koi, math.tau * t, math.tau * BEATS * t)
    return grid


def footer():
    """The name in big shaded ASCII letters with the tagline under it."""
    grid = [[None] * COLS for _ in range(ROWS)]
    width = len(NAME) * 8 - 2
    left = (COLS - width) // 2
    shades = [("@", "#ffffff"), ("@", "#f0f0f0"), ("@", "#d9d9d9"), ("@", "#bfbfbf"), ("@", "#a6a6a6")]
    for i, letter in enumerate(NAME):
        for r, line in enumerate(FONT_3X5[letter]):
            for k, bit in enumerate(line):
                if bit == "#":
                    for half in (0, 1):
                        grid[NAME_TOP + r][left + i * 8 + 2 * k + half] = (*shades[r], 3)
    start = (COLS - len(TAGLINE)) // 2
    for k, ch in enumerate(TAGLINE):
        grid[NAME_TOP + 6][start + k] = (ch, "#9a9a9a", 3)
    mask = {(c + dc, r + dr) for r in range(NAME_TOP, NAME_TOP + 5) for c in range(left, left + width) if grid[r][c]
            for dc in (-1, 0, 1) for dr in (-1, 0, 1)}
    mask |= {(c, NAME_TOP + 6) for c in range(start - 2, start + len(TAGLINE) + 2)}
    return grid, mask


def water_frame(j, koi_grids, mask):
    """Ocean frame j, leaving a hole wherever the koi are while it is on screen."""
    t = j / WATER_FRAMES
    ratio = KOI_FRAMES // WATER_FRAMES
    grid = [[None] * COLS for _ in range(ROWS)]
    for k in range(ratio * (j - 1), ratio * (j + 1) + 1):
        for r, row in enumerate(koi_grids[k % KOI_FRAMES]):
            for c, cell in enumerate(row):
                if cell is not None:
                    grid[r][c] = True
    for c, r in mask:
        if 0 <= c < COLS and 0 <= r < ROWS:
            grid[r][c] = True
    for koi in KOI:  # wakes trail slowly, so they ride on the ocean layer
        wake(grid, koi, math.tau * t, ())
    water(grid, t, math.tau * t)
    return [[cell if cell is not True else None for cell in row] for row in grid]


def flipbook(name, bodies):
    """Each frame fades in on top of the one before, which is then dropped.

    Unchanged glyphs never dim mid-fade. The first frame gets an extra copy
    at the end of the document so the loop also fades in on top.
    """
    n = len(bodies)
    step = DURATION / n
    p1, p2 = 100 / n, 200 / n
    css = (f".{name}{{opacity:0;animation:{name} {DURATION}s linear infinite}}"
           f"@keyframes {name}{{0%{{opacity:0}}{p1:.4f}%{{opacity:1}}{p2:.4f}%{{opacity:1}}{p2 + 0.001:.4f}%{{opacity:0}}100%{{opacity:0}}}}"
           f"@keyframes {name}w{{0%{{opacity:0}}{p1:.4f}%{{opacity:1}}{p1 + 0.001:.4f}%{{opacity:0}}100%{{opacity:0}}}}")
    groups = [f'<g class="{name}{f" {name}0" if i == 0 else ""}" style="animation-delay:{(i - 1) * step:.3f}s">{body}</g>'
              for i, body in enumerate(bodies)]
    groups.append(f'<g class="{name}" style="animation-name:{name}w;animation-delay:{-step:.3f}s">{bodies[0]}</g>')
    return css, "".join(groups)


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

    ratio = KOI_FRAMES // WATER_FRAMES
    name_grid, mask = footer()
    name_svg = rows_svg(name_grid, classes)
    if only_frame is not None:
        j = round(only_frame / ratio) % WATER_FRAMES
        needed = {k % KOI_FRAMES for k in range(ratio * (j - 1), ratio * (j + 1) + 1)} | {only_frame}
        koi_grids = {k: koi_frame(k) for k in needed}
        water_svg = rows_svg(water_frame(j, koi_grids, mask), classes)
        koi_svg = rows_svg(koi_grids[only_frame], classes)
        css, layers = "", f"<g>{water_svg}</g>{name_svg}<g>{koi_svg}</g>"
    else:
        koi_grids = [koi_frame(i) for i in range(KOI_FRAMES)]
        water_css, water_layer = flipbook("w", [rows_svg(water_frame(j, koi_grids, mask), classes) for j in range(WATER_FRAMES)])
        koi_css, koi_layer = flipbook("k", [rows_svg(grid, classes) for grid in koi_grids])
        css = (water_css + koi_css
               + "@media (prefers-reduced-motion:reduce){.w,.k{animation:none}.w0,.k0{opacity:1}}")
        layers = water_layer + name_svg + koi_layer

    palette = "".join(f".{name}{{fill:{color}}}" for color, name in names.items())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Two ASCII koi, one white and one black, circling each other as a yin-yang on a rippling ocean, above the name Pragyan Khadka: Art, Web Motion, Tech">
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT}px;white-space:pre}}
{palette}.oa{{opacity:.95}}.ob{{opacity:.6}}.oc{{opacity:.3}}
{css}
</style>
<rect width="{W}" height="{H}" fill="#050505"/>
{layers}
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
