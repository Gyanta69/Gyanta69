#!/usr/bin/env python3
"""Render "Himalayan Sakura", a short animated ASCII anime, as one SVG.

GitHub READMEs can't run JavaScript, but they do play CSS animations inside
SVG images. Each scene's landscape is drawn once as coloured ASCII; the
traveler, petals, clouds, stars and subtitles move with CSS keyframes on a
shared story timeline.

    python3 scripts/himalayan_sakura.py                      # writes assets/himalayan-sakura.svg
    python3 scripts/himalayan_sakura.py --preview 14 out.svg # same film frozen at t=14s
"""
import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

COLS, ROWS = 96, 42
FONT = 16
CW, CH = FONT * 0.6, 17  # character cell in px
ASPECT = CW / CH  # converts columns into row-sized world units
BAR = 56  # letterbox bar height
W = COLS * CW
H = ROWS * CH + 2 * BAR
T = 36.0  # one loop of the whole story, in seconds

RAMP = " .:-=+*#%@"
SAKURA = ["#ffb7c5", "#ff8fab", "#fb6f92", "#ffc8dd", "#ffe5ec", "#ff5d8f"]
FLAGS = ["#1e90ff", "#f8f9fa", "#e63946", "#2a9d8f", "#ffd166"]  # Tibetan prayer flag order

SCENES = [(0.0, 12.5), (11.5, 24.5), (23.5, 36.0)]
EPISODES = [
    "EP.01  -  DAWN AT THE FOOT OF THE HIMALAYA",
    "EP.02  -  ABOVE THE SEA OF CLOUDS",
    "EP.03  -  THE SUMMIT",
]
SUBTITLES = [
    (0.8, 5.8, "Every summit begins at the foot of a mountain."),
    (6.2, 11.6, "Under the sakura, a traveler sets out for the peaks."),
    (12.8, 17.8, "The trail climbs. The world falls away below."),
    (18.2, 23.6, "Through the clouds, one step at a time."),
    (24.8, 29.8, "At the top, the stars feel close enough to touch."),
    (30.2, 35.6, "~ keep climbing ~"),
]

TITLE_FONT = {
    "P": ["####.", "#...#", "####.", "#....", "#...."],
    "R": ["####.", "#...#", "####.", "#..#.", "#...#"],
    "A": [".###.", "#...#", "#####", "#...#", "#...#"],
    "G": [".####", "#....", "#..##", "#...#", ".###."],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#.."],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#"],
    "K": ["#...#", "#..#.", "###..", "#..#.", "#...#"],
    "H": ["#...#", "#...#", "#####", "#...#", "#...#"],
    "D": ["####.", "#...#", "#...#", "#...#", "####."],
    " ": [".....", ".....", ".....", ".....", "....."],
}

# Traveler sprites, facing right: (line, {char: colour}, default colour) per row.
STRAW, SKIN, SCARF, JACKET, PACK, LEGS = "#f4d58d", "#ffd7ba", "#ff3c5f", "#3fc1ff", "#ff9f1c", "#dfe3f5"
HAT = ("   _/^\\_", {}, STRAW)
BODY = ("   /[#]\\", {"#": PACK}, JACKET)
WALK_A = [HAT, (" ~~(^.^)", {"~": SCARF}, SKIN), BODY, ("    / \\", {}, LEGS)]
WALK_B = [HAT, (" ~-(^.^)", {"~": SCARF, "-": SCARF}, SKIN), BODY, ("    |\\", {}, LEGS)]
STAND = [HAT, ("  ~(^o^)", {"~": SCARF}, SKIN), BODY, ("    | |", {}, LEGS)]
SIT = [HAT, ("  ~(*.*)", {"~": SCARF, "*": "#fff3b0"}, SKIN), ("   /[#]\\_", {"#": PACK, "_": LEGS}, JACKET), ("   (__)__", {}, LEGS)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(v):
    length = math.sqrt(dot(v, v))
    return tuple(x / length for x in v)


class Grid:
    def __init__(self, cols=COLS, rows=ROWS):
        self.cols, self.rows = cols, rows
        self.cells = [[None] * cols for _ in range(rows)]

    def put(self, c, r, ch, color):
        c, r = int(round(c)), int(round(r))
        if 0 <= c < self.cols and 0 <= r < self.rows and ch != " ":
            self.cells[r][c] = (ch, color)

    def svg(self, x0=0.0, y0=0.0):
        out = []
        for r, row in enumerate(self.cells):
            spans, c = [], 0
            while c < self.cols:
                if row[c] is None:
                    c += 1
                    continue
                start, color = c, row[c][1]
                while c < self.cols and row[c] is not None and row[c][1] == color:
                    c += 1
                text = escape("".join(cell[0] for cell in row[start:c]))
                spans.append(f'<tspan x="{x0 + start * CW:.1f}" fill="{color}">{text}</tspan>')
            if spans:
                out.append(f'<text y="{y0 + r * CH + FONT * 0.8:.1f}">{"".join(spans)}</text>')
        return "".join(out)


def sprite(rows):
    g = Grid(max(len(line) for line, _, _ in rows), len(rows))
    for r, (line, colors, default) in enumerate(rows):
        for c, ch in enumerate(line):
            g.put(c, r, ch, colors.get(ch, default))
    return g.svg()


class Film:
    """Collects CSS keyframes; every animation runs on an infinite loop."""

    def __init__(self, preview=None):
        self.preview = preview
        self.css = []

    def keyframes(self, body):
        name = f"k{len(self.css)}"
        self.css.append(f"@keyframes {name}{{{body}}}")
        return name

    def anim(self, name, dur, delay=0.0, timing="linear"):
        return f"animation:{name} {dur:.2f}s {timing} infinite;animation-delay:{delay - (self.preview or 0):.2f}s"

    def timeline(self, stops):
        """stops: [(seconds, css declarations)] across the story loop."""
        stops = [(0.0, stops[0][1])] + stops + [(T, stops[-1][1])]
        return self.anim(self.keyframes("".join(f"{t / T * 100:.3f}%{{{decl}}}" for t, decl in stops)), T)

    def window(self, start, end, fade=0.6):
        return self.timeline([(start, "opacity:0"), (start + fade, "opacity:1"), (end - fade, "opacity:1"), (end, "opacity:0")])

    def path(self, points):
        """points: [(seconds, x_px, y_px)] for a translate along the story."""
        return self.timeline([(t, f"transform:translate({x:.1f}px,{y:.1f}px)") for t, x, y in points])


def px(col, row):
    return col * CW, BAR + row * CH


# --------------------------------------------------------------------------- scenery


def smooth_noise(rng, n, passes=2):
    v = [rng.uniform(-1, 1) for _ in range(n)]
    for _ in range(passes):
        v = [(v[max(i - 1, 0)] + 2 * v[i] + v[min(i + 1, n - 1)]) / 4 for i in range(n)]
    return v


def mountain_range(rng, base, peaks, palette, snow_h=99.0, jag=0.9, cap=None, light=1, depth=4, sparse=0.32):
    """Silhouette polygon plus ASCII texture. Returns (svg, tops)."""
    fill, rock_lit, rock_dark, snow_lit, snow_dark = palette
    noise = smooth_noise(rng, COLS + 2)
    tops = []
    for c in range(COLS + 2):
        h = max(ph * (1 - abs(c - pc) / pw) for pc, ph, pw in peaks)
        if cap is not None:
            h = min(h, cap)
        tops.append(base - max(h, 0) - jag * noise[c])

    g = Grid()
    for c in range(COLS):
        top = round(tops[c])
        left, right = round(tops[max(c - 1, 0)]), round(tops[c + 1])
        lit = (tops[c + 1] - tops[max(c - 1, 0)]) * light >= 0
        for r in range(max(top, 0), min(ROWS, top + depth + int(base - top) // 2)):
            snowy = base - r > snow_h + noise[c] * 1.5
            if r == top:
                if left > top and right > top:
                    ch = "^"
                elif right < top:
                    ch = "/"
                elif left < top:
                    ch = "\\"
                else:
                    ch = "_" if snowy else "-"
                g.put(c, r, ch, snow_lit if snowy else rock_lit)
            elif snowy:
                g.put(c, r, rng.choice(":*=+'" if lit else ".:,'"), snow_lit if lit else snow_dark)
            elif rng.random() < sparse * (1.0 if r - top < depth else 0.5):
                g.put(c, r, rng.choice(";:=-" if lit else ".,'`"), rock_lit if lit else rock_dark)

    pts = [(0, BAR + ROWS * CH), (0, BAR + (tops[0] + 0.55) * CH)] + [(c * CW + CW / 2, BAR + (tops[c] + 0.55) * CH) for c in range(COLS + 1)] + [(W, BAR + ROWS * CH)]
    poly = f'<polygon fill="{fill}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>'
    return poly + g.svg(), tops


def meadow(rng, tops_base, palette):
    fill, grass = palette
    noise = smooth_noise(rng, COLS + 2, 3)
    tops = [tops_base + 1.2 * math.sin(c / 9) + noise[c] for c in range(COLS + 2)]
    g = Grid()
    for c in range(COLS):
        top = round(tops[c])
        for r in range(top, ROWS):
            p = 0.9 if r == top else 0.35
            if rng.random() < p:
                g.put(c, r, rng.choice("\"',v`" if r == top else ".,'`"), rng.choice(grass))
        if rng.random() < 0.18:
            g.put(c, top - 1 if rng.random() < 0.5 else top, rng.choice("*o@"), rng.choice(SAKURA[:3] + ["#ffd166", "#ffffff"]))
    pts = [(0, BAR + ROWS * CH), (0, BAR + (tops[0] + 0.5) * CH)] + [(c * CW + CW / 2, BAR + (tops[c] + 0.5) * CH) for c in range(COLS + 1)] + [(W, BAR + ROWS * CH)]
    return f'<polygon fill="{fill}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>' + g.svg(), tops


def cloud_strip(film, rng, base, amp, palette, dur, opacity):
    """A seamless band of clouds, two periods wide, scrolling left forever."""
    fill, edge, inner = palette
    phases = [rng.uniform(0, math.pi) for _ in range(3)]

    def top(c):
        return base - amp * (0.45 * abs(math.sin(math.pi * c * 4 / COLS + phases[0]))
                             + 0.35 * abs(math.sin(math.pi * c * 7 / COLS + phases[1]))
                             + 0.2 * abs(math.sin(math.pi * c * 11 / COLS + phases[2])))

    tops = [top(c) for c in range(COLS + 1)]
    g = Grid()
    for c in range(COLS):
        t = round(tops[c])
        nxt = tops[c + 1] - tops[c]
        g.put(c, t, "(" if nxt < -0.25 else (")" if nxt > 0.25 else "~"), edge)
        for r in range(t + 1, ROWS):
            if rng.random() < 0.45 - 0.05 * (r - t):
                g.put(c, r, rng.choice("o.:'"), inner)
    pts = [(0, BAR + ROWS * CH)] + [(c * CW, BAR + (tops[c] + 0.5) * CH) for c in range(COLS + 1)] + [(W, BAR + ROWS * CH)]
    poly = f'<polygon fill="{fill}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>'
    body = poly + g.svg()
    name = film.keyframes(f"from{{transform:translateX(0)}}to{{transform:translateX(-{W:.1f}px)}}")
    return (f'<g opacity="{opacity}" style="{film.anim(name, dur)}">{body}'
            f'<g transform="translate({W:.1f},0)">{body}</g></g>')


def sakura_tree(rng, col, base, length, depth=5, spread=0.55):
    """Recursive trunk and branches with blossom clouds on the tips."""
    g = Grid()
    trunk = ["#5a3825", "#8b5e3c", "#b07d56"]
    blooms = []

    def stroke(dx, dy):
        if abs(dx) < 0.38:
            return "|"
        if abs(dy) < 0.38:
            return "_"
        return "/" if (dx > 0) == (dy < 0) else "\\"

    def branch(x, y, ang, ln, d):
        dx, dy = math.cos(ang), math.sin(ang)
        steps = max(2, int(ln * 1.4))
        width = max(1, 3 - d)
        for _ in range(steps):
            x += dx * ln / steps / ASPECT
            y += dy * ln / steps
            for k in range(width):
                g.put(x + k - width // 2, y, stroke(dx, dy), trunk[min(k, 2)] if width > 1 else trunk[1])
            if d >= depth - 2 and rng.random() < 0.25:
                blooms.append((x, y, rng.uniform(1.0, 1.8)))
        if d == depth:
            blooms.append((x, y, rng.uniform(1.8, 2.8)))
            return
        for _ in range(2 if d < 1 else rng.choice((2, 2, 3))):
            branch(x, y, ang + rng.uniform(-spread, spread) - (0.15 if d == 0 else 0), ln * rng.uniform(0.62, 0.8), d + 1)

    branch(col, base, -math.pi / 2, length, 0)
    for bx, by, rad in blooms:
        rx = rad / ASPECT
        for r in range(int(by - rad) - 1, int(by + rad) + 2):
            for c in range(int(bx - rx) - 1, int(bx + rx) + 2):
                d = math.hypot((c - bx) / rx, (r - by) / rad)
                if d < 1 and rng.random() < 0.98 - 0.35 * d:
                    shade = SAKURA[4] if r < by - rad * 0.4 else rng.choice(SAKURA[:4])
                    g.put(c, r, rng.choice("@@@**o&%"), shade)
    xs = [b[0] for b in blooms]
    ys = [b[1] for b in blooms]
    (x0, y0), (x1, y1) = px(min(xs), min(ys)), px(max(xs), max(ys))
    halo = (f'<ellipse cx="{(x0 + x1) / 2:.0f}" cy="{(y0 + y1) / 2:.0f}" rx="{(x1 - x0) / 2 + 40:.0f}" '
            f'ry="{(y1 - y0) / 2 + 40:.0f}" fill="url(#bloom)"/>')
    return halo + g.svg(), (min(xs), min(ys), max(xs), max(ys))


def orb(radius, light, colors, craters=()):
    """Shaded ASCII sphere centred on the local origin (sun or moon)."""
    cols, rows = int(2 * radius / ASPECT) + 3, int(2 * radius) + 3
    g = Grid(cols, rows)
    cx, cy = cols / 2, rows / 2
    for r in range(rows):
        for c in range(cols):
            x, y = (c + 0.5 - cx) * ASPECT, r + 0.5 - cy
            d2 = x * x + y * y
            if d2 >= radius * radius:
                continue
            n = (x / radius, y / radius, math.sqrt(radius * radius - d2) / radius)
            v = 0.3 + 0.7 * max(0.0, dot(n, light))
            for kx, ky, kr in craters:
                if math.hypot(n[0] - kx, n[1] - ky) < kr:
                    v *= 0.7
            g.put(c, r, RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))], colors[0] if v > 0.62 else colors[1])
    return f'<g transform="translate({-cols * CW / 2:.1f},{-rows * CH / 2:.1f})">{g.svg()}</g>'


GLOW_IDS = iter(range(10**6))


def glow(cx, cy, r, color, opacity):
    gid = f"glow{next(GLOW_IDS)}"
    return (f'<radialGradient id="{gid}"><stop offset="0" stop-color="{color}" stop-opacity="{opacity}"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="url(#{gid})"/>')


def sky(sid, stops):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return (f'<linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1">{s}</linearGradient>'
            f'<rect x="0" y="{BAR}" width="{W:.1f}" height="{ROWS * CH}" fill="url(#{sid})"/>')


def petals(film, rng, n, area, motion, durs, palette=SAKURA):
    """Falling or wind-blown petals spawned inside area=(c0, r0, c1, r1)."""
    variants = []
    for _ in range(4):
        dx, dy, sway = motion(rng)
        stops = []
        for i in range(9):
            s = i / 8
            x = dx * s + sway * math.sin(s * math.tau * 1.5)
            op = 0 if i in (0, 8) else 1
            stops.append(f"{s * 100:.1f}%{{transform:translate({x:.0f}px,{dy * s:.0f}px) rotate({rng.choice((1, -1)) * 300 * s:.0f}deg);opacity:{op}}}")
        variants.append(film.keyframes("".join(stops)))
    out = []
    shapes = "*`,*'*"
    for _ in range(n):
        x, y = px(rng.uniform(area[0], area[2]), rng.uniform(area[1], area[3]))
        dur = rng.uniform(*durs)
        out.append(f'<text class="pt" x="{x:.0f}" y="{y:.0f}" fill="{rng.choice(palette)}" '
                   f'style="{film.anim(rng.choice(variants), dur, -rng.uniform(0, dur))}">{rng.choice(shapes)}</text>')
    return "".join(out)


def prayer_flags(film, rng, x1, y1, x2, y2, sag, n):
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + sag
    out = [f'<path d="M{x1:.0f} {y1:.0f}Q{mx:.0f} {my:.0f} {x2:.0f} {y2:.0f}" stroke="#c8b8a0" stroke-width="1" fill="none"/>']
    flutter = film.keyframes("0%,100%{transform:rotate(-8deg)}50%{transform:rotate(10deg)}")
    for i in range(n):
        t = (i + 0.5) / n
        x = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t * t * x2
        y = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t * t * y2
        out.append(f'<rect class="fl" x="{x - 4:.1f}" y="{y:.1f}" width="8" height="11" fill="{FLAGS[i % 5]}" '
                   f'style="{film.anim(flutter, rng.uniform(0.9, 1.6), -rng.uniform(0, 1.5), "ease-in-out")}"/>')
    return "".join(out)


def traveler_walk(film, points, end_sprite=None, walk_until=None):
    """A walking traveler moving along points; optionally stops and stands."""
    a = film.keyframes("0%{opacity:1}50%{opacity:0}")
    b = film.keyframes("0%{opacity:0}50%{opacity:1}")
    walk = (f'<g style="{film.anim(a, 0.5, timing="step-end")}">{sprite(WALK_A)}</g>'
            f'<g style="{film.anim(b, 0.5, timing="step-end")}">{sprite(WALK_B)}</g>')
    if end_sprite:
        walk = (f'<g style="{film.timeline([(walk_until, "opacity:1"), (walk_until + 0.01, "opacity:0")])}">{walk}</g>'
                f'<g style="{film.timeline([(walk_until, "opacity:0"), (walk_until + 0.01, "opacity:1")])}">{sprite(end_sprite)}</g>')
    return f'<g style="{film.path(points)}">{walk}</g>'


# --------------------------------------------------------------------------- scenes


def scene_dawn(film, rng):
    out = [sky("sky1", [(0, "#1b1340"), (0.35, "#4a2472"), (0.62, "#b23a72"), (0.8, "#ff7b54"), (1, "#ffc66d")])]
    stars = Grid()
    for _ in range(26):
        stars.put(rng.randrange(COLS), rng.randrange(10), rng.choice(".+*."), "#d9c8ff")
    out.append(f'<g opacity=".7">{stars.svg(0, BAR)}</g>')

    sx0, sy0 = px(64, 30)
    sx1, sy1 = px(64, 9)
    sun = glow(0, 0, 150, "#ffd27a", 0.85) + orb(3.4, norm((0, 0, 1)), ["#fff4c2", "#ffc65c"])
    out.append(f'<g style="{film.path([(0, sx0, sy0), (12.5, sx1, sy1)])}">{sun}</g>')

    far, _ = mountain_range(rng, 31, [(6, 10, 12), (22, 15, 15), (40, 19, 17), (57, 14, 12), (74, 21, 18), (92, 12, 12)],
                            ["#5d4a8f", "#b79ad8", "#7e66b0", "#ffd6e5", "#d7a6c9"], snow_h=9)
    mid, _ = mountain_range(rng, 35, [(14, 9, 13), (34, 7, 10), (58, 10, 14), (84, 8, 12)],
                            ["#3b2d6b", "#8f73c9", "#5c4a96", "#f4b6d2", "#b88bbf"], snow_h=6)
    ground, _ = meadow(rng, 38.5, ["#1f3b3a", ["#3c8f6e", "#2f6f5a", "#58b48a"]])
    tree, (c0, r0, c1, r1) = sakura_tree(rng, 17, 39, 7.5, depth=5)
    out += [far, mid, ground, tree]

    walker_y = px(0, 34.6)[1]
    out.append(traveler_walk(film, [(0.6, -10 * CW, walker_y), (8.5, 30 * CW, walker_y)], STAND, 8.5))
    out.append(petals(film, rng, 55, (c0, r0, c1, r1),
                      lambda r: (r.uniform(150, 380), r.uniform(220, 360), r.uniform(15, 40)), (6, 11)))
    return "".join(out)


def scene_clouds(film, rng):
    out = [sky("sky2", [(0, "#1e5bd8"), (0.5, "#4fa3ff"), (0.85, "#a8e0ff"), (1, "#e8f8ff")])]
    sx, sy = px(84, 5)
    out.append(f'<g transform="translate({sx:.0f},{sy:.0f})">{glow(0, 0, 110, "#fffbe0", 0.9)}{orb(2.2, norm((0, 0, 1)), ["#ffffff", "#fff3b0"])}</g>')

    far, _ = mountain_range(rng, 26, [(12, 10, 14), (30, 14, 14), (52, 21, 18), (70, 15, 13), (90, 11, 12)],
                            ["#7da2d6", "#e3eeff", "#a9c2ea", "#ffffff", "#cfe0ff"], snow_h=8)
    out.append(far)
    out.append(cloud_strip(film, rng, 27, 4, ["#f4fbff", "#ffffff", "#b9d9f5"], 48, 0.95))

    ridge, tops = mountain_range(rng, 44, [(88, 24, 60)], ["#2f4f74", "#7fa8d8", "#46698f", "#ffffff", "#bcd4f0"],
                                 snow_h=17, jag=0.35, light=1)
    out.append(ridge)
    pole_x, pole_top = px(88, tops[88] - 7)
    rope_end = px(66, tops[66] - 6.5)
    out.append(f'<line x1="{pole_x:.0f}" y1="{pole_top:.0f}" x2="{pole_x:.0f}" y2="{px(0, tops[88])[1]:.0f}" stroke="#d9c7a7" stroke-width="2"/>')
    out.append(prayer_flags(film, rng, pole_x, pole_top + 2, rope_end[0], rope_end[1], 18, 11))

    path = [(12.4 + (c - 40) / 42 * 11.0, c * CW, px(0, tops[c] - 3.6)[1]) for c in range(40, 83, 3)]
    out.append(traveler_walk(film, path))

    birds_a = film.keyframes("0%{opacity:1}50%{opacity:0}")
    birds_b = film.keyframes("0%{opacity:0}50%{opacity:1}")
    flock = ""
    for i, (bc, br) in enumerate([(0, 0), (4, 1), (8, -1), (11, 2), (15, 0.5)]):
        x, y = bc * CW, br * CH
        d = -0.12 * i
        flock += (f'<text x="{x:.0f}" y="{y:.0f}" fill="#1d3557" style="{film.anim(birds_a, 0.6, d, "step-end")}">\\v/</text>'
                  f'<text x="{x:.0f}" y="{y:.0f}" fill="#1d3557" style="{film.anim(birds_b, 0.6, d, "step-end")}">_v_</text>')
    out.append(f'<g style="{film.path([(12.0, -20 * CW, px(0, 9)[1]), (24.0, 100 * CW, px(0, 5)[1])])}">{flock}</g>')

    out.append(cloud_strip(film, rng, 42, 6, ["#ffffff", "#ffffff", "#cfe6ff"], 26, 0.92))
    out.append(petals(film, rng, 34, (-12, 4, 30, 34),
                      lambda r: (r.uniform(700, 1050), r.uniform(-40, 140), r.uniform(20, 50)), (4.5, 8)))
    return "".join(out)


def scene_summit(film, rng):
    out = [sky("sky3", [(0, "#050616"), (0.45, "#120f3a"), (0.8, "#2a1b5e"), (1, "#4a2a6e")])]
    milky = Grid()
    for c in range(COLS):
        centre = 3 + c * 0.24
        for r in range(ROWS):
            d = abs(r - centre) / 4.5
            if d < 1 and rng.random() < 0.5 * (1 - d):
                milky.put(c, r, rng.choice(".,`:'"), rng.choice(["#7b6cd9", "#b38df0", "#5a77d6", "#e0a8ff"]))
    out.append(f'<g opacity=".55">{milky.svg(0, BAR)}</g>')

    twinkle = film.keyframes("0%,100%{opacity:.15}50%{opacity:1}")
    for _ in range(80):
        x, y = px(rng.uniform(0, COLS), rng.uniform(0, 28))
        dur = rng.uniform(1.5, 4)
        out.append(f'<text x="{x:.0f}" y="{y:.0f}" fill="{rng.choice(["#ffffff", "#fff3b0", "#cdd8ff", "#ffc8dd"])}" '
                   f'style="{film.anim(twinkle, dur, -rng.uniform(0, dur), "ease-in-out")}">{rng.choice("*+.*")}</text>')

    star_trail = "".join(f'<text x="{i * 2 * CW:.0f}" y="{-i * 0.45 * CH:.0f}" fill="#fff6d5" opacity="{1 - i / 8:.2f}">{ch}</text>'
                         for i, ch in enumerate("*=~~--.."))
    sx0, sy0 = px(64, 3)
    out.append(f'<g style="{film.timeline([(26.4, "opacity:0"), (26.5, "opacity:1"), (27.4, "opacity:1"), (27.5, "opacity:0")])}">'
               f'<g style="{film.path([(26.4, sx0, sy0), (27.5, sx0 - 26 * CW, sy0 + 10 * CH)])}">{star_trail}</g></g>')

    mx, my = px(80, 14)
    out.append(f'<g transform="translate({mx:.0f},{my:.0f})">{glow(0, 0, 130, "#cfd8ff", 0.55)}'
               f'{orb(4.2, norm((-0.6, -0.2, 0.75)), ["#fff7d6", "#c9c3a6"], [(-0.3, -0.2, 0.18), (0.25, 0.35, 0.14), (0.4, -0.35, 0.1)])}</g>')

    far, _ = mountain_range(rng, 33, [(10, 7, 12), (30, 9, 12), (60, 8, 14), (85, 10, 13)],
                            ["#232a5c", "#6a73b8", "#3a4280", "#c9d4ff", "#8f9bd9"], snow_h=6)
    out.append(far)
    out.append(cloud_strip(film, rng, 35, 3, ["#3d4a8a", "#9fb0ff", "#6f7fcf"], 70, 0.75))
    summit, tops = mountain_range(rng, 46, [(36, 25, 30), (72, 14, 22)], ["#1a1840", "#5a60b0", "#2e3170", "#e6ecff", "#9aa6e0"],
                                  snow_h=19, jag=0.4, cap=21)
    out.append(summit)

    tree, (c0, r0, c1, r1) = sakura_tree(rng, 32, tops[32] + 0.5, 4.2, depth=4)
    out.append(tree)
    fx1, fy1 = px(31, r0 + 5)
    fx2, fy2 = px(9, tops[9] - 2)
    out.append(prayer_flags(film, rng, fx1, fy1, fx2, fy2, 26, 13))
    sx, sy = px(34, tops[38] - 3.5)
    out.append(f'<g transform="translate({sx:.0f},{sy:.0f})">{sprite(SIT)}</g>')

    out.append(petals(film, rng, 26, (c0, r0, c1, r1),
                      lambda r: (r.uniform(120, 300), r.uniform(160, 300), r.uniform(20, 40)), (8, 13)))
    floats = [film.keyframes("".join(f"{p}%{{transform:translate({rng.uniform(-30, 30):.0f}px,{rng.uniform(-24, 24):.0f}px);opacity:{o}}}"
                                     for p, o in ((0, 0.2), (25, 1), (50, 0.4), (75, 1), (100, 0.2)))) for _ in range(4)]
    for _ in range(22):
        x, y = px(rng.uniform(8, 66), rng.uniform(12, 32))
        dur = rng.uniform(3, 6)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2.2" fill="#e4ff7a" filter="url(#glow)" '
                   f'style="{film.anim(rng.choice(floats), dur, -rng.uniform(0, dur), "ease-in-out")}"/>')

    pixels = []
    word = "PRAGYAN KHADKA"
    width = len(word) * 6 - 1
    left = (COLS - width) // 2
    ramp = ["#ffc8dd", "#ffafcc", "#ff8fab", "#f472b6", "#d17bf0", "#a78bfa", "#7cc4fa", "#4cc9f0"]
    for i, letter in enumerate(word):
        for r, line in enumerate(TITLE_FONT[letter]):
            for k, bit in enumerate(line):
                if bit == "#":
                    c = left + i * 6 + k
                    x, y = px(c, 1.2 + r * 0.8)
                    pixels.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CW - 1:.1f}" height="{CH * 0.8 - 1:.1f}" '
                                  f'fill="{ramp[min(7, (c - left) * 8 // width)]}"/>')
    out.append(f'<g class="w fin" filter="url(#glow)" style="{film.window(30.0, 35.8, 1.2)}">{"".join(pixels)}</g>')
    return "".join(out)


# --------------------------------------------------------------------------- film


def build(preview=None):
    film = Film(preview)
    rng = random.Random(69)
    scenes = [scene_dawn(film, rng), scene_clouds(film, rng), scene_summit(film, rng)]
    body = []
    for i, (scene, (start, end)) in enumerate(zip(scenes, SCENES)):
        fade = 0.8 if i == 0 else 1.0
        body.append(f'<g class="sc" clip-path="url(#view)" style="{film.window(start, end, fade)}">{scene}</g>')

    for i, label in enumerate(EPISODES):
        start, end = SCENES[i]
        body.append(f'<text class="w ep" x="{W / 2:.0f}" y="{BAR / 2 + 6:.0f}" text-anchor="middle" '
                    f'style="{film.window(start + 0.3, end - 0.3)}">{escape(label)}</text>')
    for start, end, line in SUBTITLES:
        body.append(f'<text class="w sub" x="{W / 2:.0f}" y="{H - BAR / 2 + 6:.0f}" text-anchor="middle" '
                    f'style="{film.window(start, end, 0.4)}">{escape(line)}</text>')

    paused = "*{animation-play-state:paused!important}" if preview is not None else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} {H}" width="{W:.0f}" height="{H}" role="img" aria-label="Himalayan Sakura: an animated ASCII anime short about a traveler climbing from a sakura tree at dawn, through a sea of clouds, to a starlit summit">
<defs>
<clipPath id="view"><rect x="0" y="{BAR}" width="{W:.1f}" height="{ROWS * CH}"/></clipPath>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<radialGradient id="bloom"><stop offset="0" stop-color="#ff8fab" stop-opacity=".35"/><stop offset="1" stop-color="#ff8fab" stop-opacity="0"/></radialGradient>
<radialGradient id="vignette" cx=".5" cy=".5" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
</defs>
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT}px;white-space:pre}}
.sc,.w{{opacity:0}}
.pt,.fl{{transform-box:fill-box;transform-origin:50% 0}}
.pt{{transform-origin:center}}
.ep{{fill:#ffafcc;font-size:13px;letter-spacing:3px}}
.sub{{fill:#fff;font-size:18px}}
{"".join(film.css)}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.sc{{opacity:1}}.fin{{opacity:1}}}}
{paused}
</style>
<rect width="{W:.1f}" height="{H}" fill="#000"/>
{"".join(body)}
<rect x="0" y="{BAR}" width="{W:.1f}" height="{ROWS * CH}" fill="url(#vignette)" pointer-events="none"/>
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--preview":
        out, svg = Path(sys.argv[3]), build(float(sys.argv[2]))
    else:
        out, svg = Path(__file__).resolve().parent.parent / "assets" / "himalayan-sakura.svg", build()
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
