#!/usr/bin/env python3
"""Render an animated ASCII ringed planet as a self-contained SVG.

GitHub READMEs can't run JavaScript, but they do play CSS animations inside
SVG images. Every frame is pre-rendered as ASCII and the frames are flipped
with CSS keyframes.

    python3 scripts/ascii_planet.py            # writes assets/ascii-planet.svg
"""
import math
import random
from pathlib import Path
from xml.sax.saxutils import escape

COLS, ROWS = 120, 38
FRAMES = 90
DURATION = 9.0  # seconds per loop

FONT_SIZE = 12
CELL_W = FONT_SIZE * 0.6  # monospace advance width
CELL_H = 14
ASPECT = CELL_W / CELL_H  # converts columns into row-sized world units

PAD = 24
TITLE_H = 36
FOOTER_H = 40

R_PLANET = 11.5
RING_IN, RING_GAP, RING_GAP_END, RING_OUT = 1.3, 1.72, 1.8, 2.15
MOON_ORBIT, MOON_R = 2.4 * R_PLANET, 2.3

RAMP = " .:-=+*#%@"


def norm(v):
    length = math.sqrt(sum(c * c for c in v))
    return tuple(c / length for c in v)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


# Screen space: x to the right, y down, z toward the viewer.
LIGHT = norm((-0.55, -0.4, 0.75))


def shade(v):
    v = max(0.0, min(0.999, v))
    return RAMP[int(v * len(RAMP))]


def ring_density(d):
    """Ring brightness by radius (in planet radii), with a Cassini-style gap."""
    if d < RING_IN or d > RING_OUT or RING_GAP < d < RING_GAP_END:
        return 0.0
    bands = 0.7 + 0.2 * math.sin(d * 30) + 0.1 * math.sin(d * 77)
    edge = min(d - RING_IN, RING_OUT - d) / 0.12
    return max(0.0, bands) * min(1.0, edge)


def make_stars(rng):
    stars = []
    while len(stars) < 140:
        c, r = rng.randrange(COLS), rng.randrange(ROWS)
        stars.append((c, r, rng.random() * math.tau, rng.choice((1, 2, 3))))
    return stars


def render_frame(i, stars):
    t = i / FRAMES  # 0..1 loop phase, every motion below is periodic in t
    tilt = 0.38 + 0.14 * math.sin(math.tau * t)  # rings slowly open and close
    roll = -0.32 + 0.05 * math.cos(math.tau * t)
    world = mat_mul(rot_z(roll), rot_x(tilt))  # planet frame -> screen
    to_planet = transpose(world)
    ring_n = apply(world, (0, 1, 0))
    spin = math.tau * t

    moon_a = math.tau * t + 1.2
    moon_p = (MOON_ORBIT * math.cos(moon_a), MOON_ORBIT * 0.1 * math.sin(moon_a), MOON_ORBIT * math.sin(moon_a))
    mx, my, mz = apply(world, moon_p)

    grid = [[(" ", None)] * COLS for _ in range(ROWS)]

    for c, r, phase, kind in stars:
        tw = math.sin(math.tau * t * kind + phase)
        ch = "." if tw < 0.2 else ("+" if tw < 0.85 else "*")
        grid[r][c] = (ch, "s")

    # shooting star during the first quarter of the loop
    if t < 0.22:
        k = t / 0.22
        hx, hy = 6 + k * 46, 2 + k * 9
        for j in range(9):
            px, py = round(hx - j * 2.2), round(hy - j * 0.43)
            if 0 <= px < COLS and 0 <= py < ROWS:
                grid[py][px] = ("@*=-:.. ."[j], "h")

    cx, cy = COLS / 2, ROWS / 2
    for r in range(ROWS):
        y = r - cy + 0.5
        for c in range(COLS):
            x = (c - cx + 0.5) * ASPECT
            best_z, cell = -1e9, None

            # planet
            h2 = R_PLANET * R_PLANET - x * x - y * y
            if h2 > 0:
                z = math.sqrt(h2)
                n = (x / R_PLANET, y / R_PLANET, z / R_PLANET)
                q = apply(rot_y(-spin), apply(to_planet, n))
                lat, lon = math.asin(max(-1, min(1, q[1]))), math.atan2(q[0], q[2])
                bands = 0.5 + 0.5 * math.sin(lat * 11 + 0.7 * math.sin(lon * 3 + lat * 5))
                storm = math.exp(-(((lat - 0.45) / 0.16) ** 2 + ((math.sin((lon - 1.0) / 2)) / 0.14) ** 2))
                light = max(0.0, dot(n, LIGHT))
                # shadow cast by the rings onto the planet
                sp = (x, y, z)
                denom = dot(ring_n, LIGHT)
                if abs(denom) > 1e-6:
                    s = -dot(ring_n, sp) / denom
                    if s > 0:
                        hit = tuple(sp[k] + s * LIGHT[k] for k in range(3))
                        if ring_density(math.sqrt(dot(hit, hit)) / R_PLANET) > 0.3:
                            light *= 0.4
                v = max(0.12, light * (0.45 + 0.4 * bands + 0.35 * storm))
                best_z, cell = z, (shade(v), "p")

            # rings: orthographic ray hits the ring plane
            if abs(ring_n[2]) > 1e-3:
                z = -(ring_n[0] * x + ring_n[1] * y) / ring_n[2]
                p = (x, y, z)
                d = math.sqrt(dot(p, p)) / R_PLANET
                dens = ring_density(d)
                if dens > 0 and z > best_z:
                    rp = apply(to_planet, p)
                    turns = 2 if d < RING_GAP else 1  # inner ring orbits faster
                    ang = math.atan2(rp[0], rp[2]) - math.tau * t * turns
                    grain = 0.85 + 0.15 * math.sin(ang * 9 + d * 20)
                    b = dot(p, LIGHT)
                    disc = b * b - (dot(p, p) - R_PLANET * R_PLANET)
                    shadowed = disc > 0 and -b > 0
                    v = max(0.12, dens * grain * (0.3 if shadowed else 0.9))
                    best_z, cell = z, (shade(v), "r")

            # moon
            dx, dy = x - mx, y - my
            m2 = MOON_R * MOON_R - dx * dx - dy * dy
            if m2 > 0:
                z = mz + math.sqrt(m2)
                if z > best_z:
                    n = (dx / MOON_R, dy / MOON_R, math.sqrt(m2) / MOON_R)
                    crater = 0.25 * math.exp(-((n[0] + 0.3) ** 2 + (n[1] - 0.2) ** 2) / 0.05)
                    v = max(0.0, dot(n, LIGHT)) * (0.95 - crater) + 0.05
                    best_z, cell = z, (shade(v), "m")

            if cell and cell[0] != " ":
                grid[r][c] = cell
            elif cell:
                grid[r][c] = (" ", None)  # dark side hides the stars behind it
    return grid


def frame_svg(grid, x0, y0):
    out = []
    for r, row in enumerate(grid):
        spans, c = [], 0
        while c < COLS:
            ch, cls = row[c]
            if ch == " ":
                c += 1
                continue
            start = c
            while c < COLS and row[c][0] != " " and row[c][1] == cls:
                c += 1
            text = escape("".join(cell[0] for cell in row[start:c]))
            spans.append(f'<tspan x="{x0 + start * CELL_W:.1f}" class="{cls}">{text}</tspan>')
        if spans:
            out.append(f'<text y="{y0 + r * CELL_H + FONT_SIZE:.0f}">{"".join(spans)}</text>')
    return "".join(out)


def build():
    rng = random.Random(69)
    stars = make_stars(rng)
    width = round(COLS * CELL_W + 2 * PAD)
    height = round(ROWS * CELL_H + TITLE_H + FOOTER_H + PAD)
    x0, y0 = PAD, TITLE_H + PAD / 2
    step = DURATION / FRAMES

    frames = []
    for i in range(FRAMES):
        body = frame_svg(render_frame(i, stars), x0, y0)
        frames.append(f'<g class="f{" f0" if i == 0 else ""}" style="animation-delay:{i * step:.2f}s">{body}</g>')

    footer_y = height - FOOTER_H / 2 + 5
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Animated ASCII ringed planet with an orbiting moon">
<defs>
<linearGradient id="gp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#00ffff"/><stop offset=".55" stop-color="#3b82f6"/><stop offset="1" stop-color="#a855f7"/></linearGradient>
<linearGradient id="gr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f472b6"/><stop offset=".5" stop-color="#fbbf24"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
</defs>
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT_SIZE}px;white-space:pre}}
.p{{fill:url(#gp)}}.r{{fill:url(#gr)}}.m{{fill:#e2e8f0}}.s{{fill:#64748b}}.h{{fill:#fde68a}}
.f{{opacity:0;animation:fr {DURATION}s step-end infinite}}
@keyframes fr{{0%{{opacity:1}}{100 / FRAMES:.4f}%{{opacity:0}}100%{{opacity:0}}}}
.cur{{animation:bl 1s step-end infinite}}@keyframes bl{{50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{.f,.cur{{animation:none}}.f0{{opacity:1}}}}
</style>
<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>
<path d="M.5 12.5a12 12 0 0 1 12-12h{width - 25}a12 12 0 0 1 12 12v{TITLE_H - 12}h-{width - 1}z" fill="#161b22"/>
<circle cx="22" cy="{TITLE_H / 2}" r="6" fill="#ff5f57"/><circle cx="42" cy="{TITLE_H / 2}" r="6" fill="#febc2e"/><circle cx="62" cy="{TITLE_H / 2}" r="6" fill="#28c840"/>
<text x="{width / 2}" y="{TITLE_H / 2 + 4}" text-anchor="middle" fill="#8b949e">gyanta69@cloud: ~/orbit</text>
{"".join(frames)}
<text x="{PAD}" y="{footer_y}" fill="#8b949e"><tspan fill="#28c840">➜</tspan> <tspan fill="#00ffff">~/orbit</tspan> ./launch --pilot "Pragyan Khadka" --mode multi-cloud<tspan class="cur" fill="#00ffff">█</tspan></text>
</svg>
"""


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "ascii-planet.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
