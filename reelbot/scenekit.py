"""Scene kit: compile a short scene description into a rigged, animatable SVG.

A scene's `art` is a small dict, e.g.

    {"bg": "kitchen", "fx": ["rain"], "shot": "wide",
     "cast": ["amma:cook", "kid:eat,hold=dosa"],
     "props": ["table:dosa"]}

- bg:    kitchen, interior, veranda, lane, yard, school, classroom, night_room, paddy,
         temple, bus_stop, beach, hospital_free_room (alias interior)
- fx:    rain, night, sunset, festive
- shot:  wide (default) or close (first cast member, chest-up)
- cast:  "<character>:<tokens>", left to right. Tokens (comma separated):
         poses  idle walk point wave hold eat cook jump hug pray read phone sleep umbrella sit
         faces  happy sad surprised talk neutral
         hold=<prop>   dosa letter book phone bag flower plate laddu tiffin gift money toy lamp umbrella kite
         wet           one soaked shoulder (rain stories)
- props: table[:food], stove, hanging_umbrella, bicycle[:red|blue|green], photo:<character>,
         nilavilakku, kerosene_lamp, radio, tv, kite, pookkalam, gift, bus, mango_tree, chair,
         clock, sweets, books, tiffin, empty_bicycle (faded outline)

Everything is drawn in the flat Kerala "kutti kaalam" style and tagged with data-anim so
reelbot.animate can move it (blink, talk, breathe, walk, wave, rain, wheels, flames...).
"""

from __future__ import annotations

import math
import random
import re

W, H = 1080, 1920
GROUND = 1690
SKIN_OLD, SKIN = "#8a5a3a", "#94603e"
INK = "#3a2a1a"

DEFS = """<defs>
<radialGradient id="wall" cx="0.5" cy="0.45" r="0.75"><stop offset="0" stop-color="#d9e2cf"/><stop offset="1" stop-color="#9fb08f"/></radialGradient>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9a4f37"/><stop offset="1" stop-color="#6e3324"/></linearGradient>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8e9e94"/><stop offset="1" stop-color="#c3cdb9"/></linearGradient>
<linearGradient id="clear" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a9d3e0"/><stop offset="1" stop-color="#e3efe6"/></linearGradient>
<linearGradient id="mud" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9b7a55"/><stop offset="1" stop-color="#6d5238"/></linearGradient>
<linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f9bb3"/><stop offset="1" stop-color="#2f6f86"/></linearGradient>
<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffd27a" stop-opacity="0.85"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>
<radialGradient id="skin" cx="0.38" cy="0.32" r="0.75"><stop offset="0" stop-color="#c98a5c"/><stop offset="0.55" stop-color="#a66b45"/><stop offset="1" stop-color="#6e4129"/></radialGradient>
<radialGradient id="skinOld" cx="0.38" cy="0.32" r="0.75"><stop offset="0" stop-color="#bd8259"/><stop offset="0.55" stop-color="#99633f"/><stop offset="1" stop-color="#633a24"/></radialGradient>
<linearGradient id="shade" x1="0" y1="0" x2="1" y2="0.25"><stop offset="0" stop-color="#ffffff" stop-opacity="0.22"/><stop offset="0.35" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.65" stop-color="#000000" stop-opacity="0.05"/><stop offset="1" stop-color="#000000" stop-opacity="0.42"/></linearGradient>
<linearGradient id="fold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000000" stop-opacity="0.18"/><stop offset="0.3" stop-color="#000000" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity="0.25"/></linearGradient>
<radialGradient id="blush" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#e8665c" stop-opacity="0.55"/><stop offset="1" stop-color="#e8665c" stop-opacity="0"/></radialGradient>
<radialGradient id="contact" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#000000" stop-opacity="0.45"/><stop offset="1" stop-color="#000000" stop-opacity="0"/></radialGradient>
<radialGradient id="iris" cx="0.4" cy="0.35" r="0.7"><stop offset="0" stop-color="#7a4a26"/><stop offset="1" stop-color="#2a170b"/></radialGradient>
<radialGradient id="vignette" cx="0.5" cy="0.46" r="0.72"><stop offset="0.5" stop-color="#000000" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity="0.62"/></radialGradient>
<radialGradient id="lamplight" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffb347" stop-opacity="0.55"/><stop offset="0.45" stop-color="#ff9a2e" stop-opacity="0.22"/><stop offset="1" stop-color="#ff8a1e" stop-opacity="0"/></radialGradient>
<radialGradient id="moonglow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fdf6d8" stop-opacity="0.75"/><stop offset="0.3" stop-color="#cfe0ff" stop-opacity="0.25"/><stop offset="1" stop-color="#cfe0ff" stop-opacity="0"/></radialGradient>
<radialGradient id="firefly" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff9b0" stop-opacity="1"/><stop offset="0.35" stop-color="#e8f56a" stop-opacity="0.6"/><stop offset="1" stop-color="#e8f56a" stop-opacity="0"/></radialGradient>
</defs>"""

_SHAPE = re.compile(r'<(?:path|rect|circle|ellipse)\b[^>]*/>')


def shaded(svg: str, grad: str = "shade") -> str:
    """Draw `svg`, then a copy of each filled shape painted with a light/shadow gradient (soft 3D look)."""
    over = []
    for el in _SHAPE.findall(svg):
        m = re.search(r'fill="([^"]*)"', el)
        if not m or m.group(1) == "none" or 'opacity="0' in el:
            continue
        el = re.sub(r'\s(?:stroke|stroke-width|opacity)="[^"]*"', "", el)
        over.append(el.replace(m.group(0), f'fill="url(#{grad})"'))
    return svg + "".join(over)


def g(anim: str, inner: str, **attrs) -> str:
    a = "".join(f' data-{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<g data-anim="{anim}"{a}>{inner}</g>'


# --------------------------------------------------------------------------- weather
def rain_lines(seed=1, n=170, opacity=0.45, x0=0, x1=W, y0=0, y1=H):
    r = random.Random(seed)
    lines = []
    for _ in range(n):
        x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        ln = r.uniform(40, 90)
        lines.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x - ln * 0.18:.0f}" y2="{y + ln:.0f}"/>')
    return f'<g stroke="#eef4f1" stroke-width="4" stroke-linecap="round" opacity="{opacity}">{"".join(lines)}</g>'


def rain_layer(seed, n=200, opacity=0.45, x0=0, x1=W):
    return g("rain", rain_lines(seed=seed, n=n, opacity=opacity, x0=x0, x1=x1), speed=1500)


def birds():
    b = '<path d="M0 0 q14 -14 28 0 q14 -14 28 0" stroke="#3a3a3a" stroke-width="5" fill="none"/>'
    return g("drift", "".join(f'<g transform="translate({x},{y})">{b}</g>' for x, y in ((120, 200), (220, 250), (700, 160))), speed=30)


def stars(seed=3):
    r = random.Random(seed)
    return "".join(f'<circle cx="{r.uniform(0, W):.0f}" cy="{r.uniform(0, 700):.0f}" r="{r.uniform(2, 5):.1f}" fill="#fff8d6" opacity="{r.uniform(.5, 1):.2f}"/>' for _ in range(45))


# --------------------------------------------------------------------------- scenery bits
def coconut(x, base, s=1.0, opacity=0.75):
    fronds = "".join(
        f'<path d="M0 -600 Q{dx * 0.5} {-660 + dy * 0.3} {dx} {-600 + dy}" stroke="#4f6b45" stroke-width="26" fill="none" stroke-linecap="round"/>'
        for dx, dy in ((-220, 60), (-180, -60), (200, 50), (170, -70), (0, -130), (-60, 140), (90, 150)))
    inner = f'<path d="M-14 0 Q-30 -300 0 -600 L16 -600 Q-6 -300 14 0Z" fill="#6e5a43"/>{fronds}'
    return f'<g transform="translate({x},{base}) scale({s})" opacity="{opacity}">{g("swing", inner, pivot="0,0", amp=1.2, period=4)}</g>'


def house(x, y, s=1.0):
    return (f'<g transform="translate({x},{y}) scale({s})">'
            '<rect x="-320" y="-560" width="640" height="560" fill="#e9dfc4"/><path d="M-370 -540 L0 -790 L370 -540Z" fill="#9a4a32"/>'
            '<rect x="-70" y="-320" width="140" height="320" fill="#5a3a22"/>'
            '<rect x="-260" y="-360" width="130" height="150" fill="#5a3a22"/><rect x="130" y="-360" width="130" height="150" fill="#5a3a22"/>'
            '<rect x="-350" y="0" width="700" height="40" fill="#b9a57f"/></g>')


def windows(rain=False, night=False):
    out, clips = "", ""
    pane = "#26324a" if night else "#5f7268"
    for x in (40, 840):
        bars = "".join(f'<rect x="{x + 30 + i * 40}" y="840" width="10" height="290"/>' for i in range(4))
        inside = f'<rect x="{x + 20}" y="840" width="180" height="290" fill="{pane}"/>'
        if rain:
            clips += f'<clipPath id="cw{x}"><rect x="{x + 20}" y="840" width="180" height="290"/></clipPath>'
            inside += f'<g clip-path="url(#cw{x})">{rain_layer(x, n=70, opacity=0.7, x0=x + 10, x1=x + 220)}</g>'
        out += f'<rect x="{x}" y="820" width="220" height="330" rx="8" fill="#5a3a22"/>{inside}<g fill="#8a6a4a">{bars}</g>'
    return (f"<defs>{clips}</defs>" if clips else "") + out


def floor():
    return f'<rect y="1500" width="{W}" height="420" fill="url(#floor)"/><rect y="1500" width="{W}" height="24" fill="#5c2a1d"/>'


def rafters():
    return (f'<rect width="{W}" height="560" fill="#7b5235"/>'
            f'<g fill="#5f3e26">{"".join(f"<rect y=\"{60 + i * 70}\" width=\"{W}\" height=\"16\"/>" for i in range(7))}</g>'
            f'<rect y="540" width="{W}" height="30" fill="#4b2f1c"/>')


def fan():
    blades = "".join(f'<rect x="370" y="-14" width="340" height="28" rx="14" fill="#7a7f86" transform="rotate({a} 540 0)"/>' for a in (0, 120, 240))
    return (f'<rect x="525" y="0" width="30" height="170" fill="#5c6168"/>'
            f'<g transform="translate(0,170)">{g("spin", blades, pivot="540,0", period=1.4)}<circle cx="540" cy="0" r="34" fill="#5c6168"/></g>')


# --------------------------------------------------------------------------- backgrounds
def bg_interior(fx):
    return f'<rect width="{W}" height="{H}" fill="url(#wall)"/>{rafters()}{windows("rain" in fx, "night" in fx)}{floor()}'


def bg_night_room(fx):
    return (f'<rect width="{W}" height="{H}" fill="#cbb994"/>{rafters()}{windows("rain" in fx, True)}'
            f'<rect y="1500" width="{W}" height="420" fill="#4a2a22"/>')


def bg_kitchen(fx):
    tiles = "".join(f'<rect x="{x}" y="{y}" width="88" height="88" fill="{"#e9efe9" if (x // 90 + y // 90) % 2 else "#dfe7e1"}"/>'
                    for x in range(0, W, 90) for y in range(900, 1300, 90))
    shelf = ('<rect x="560" y="430" width="440" height="22" fill="#6b4529"/>'
             '<g fill="#c9ced3"><rect x="590" y="350" width="70" height="80" rx="8"/><rect x="690" y="330" width="90" height="100" rx="10"/>'
             '<ellipse cx="860" cy="410" rx="60" ry="22"/><rect x="930" y="360" width="50" height="70" rx="6"/></g>')
    sky = "#26324a" if "night" in fx else "#bfe0c8"
    win = (f'<rect x="90" y="330" width="330" height="400" rx="10" fill="#5a3a22"/><rect x="110" y="350" width="290" height="360" fill="{sky}"/>'
           + coconut(250, 760, 0.45)
           + '<g fill="#8a6a4a"><rect x="250" y="350" width="10" height="360"/><rect x="110" y="525" width="290" height="10"/></g>')
    if "rain" in fx:
        win += f'<defs><clipPath id="kw"><rect x="110" y="350" width="290" height="360"/></clipPath></defs><g clip-path="url(#kw)">{rain_layer(11, n=60, opacity=.7, x0=100, x1=420)}</g>'
    return f'<rect width="{W}" height="{H}" fill="#f0dcae"/>{tiles}{win}{shelf}{fan()}{floor()}'


def bg_veranda(fx):
    trees = "".join(coconut(x, 1150, s) for x, s in ((120, 0.9), (420, 1.1), (900, 0.8)))
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{trees}<rect y="1150" width="{W}" height="400" fill="#6f8a5a"/>'
            + (rain_layer(7, n=260, opacity=0.55) if "rain" in fx else birds())
            + f'<rect width="{W}" height="420" fill="#7b5235"/><g fill="#5f3e26">{"".join(f"<rect y=\"{40 + i * 64}\" width=\"{W}\" height=\"14\"/>" for i in range(6))}</g>'
            f'<rect y="400" width="{W}" height="36" fill="#4b2f1c"/>'
            f'<rect x="0" y="1380" width="{W}" height="140" fill="#c9b79a"/><rect x="0" y="1380" width="{W}" height="18" fill="#a8946f"/>'
            f'<rect y="1520" width="{W}" height="400" fill="url(#floor)"/>'
            f'<rect x="900" y="430" width="70" height="1100" fill="#6b4529"/><rect x="40" y="430" width="70" height="1100" fill="#6b4529"/>')


def bg_lane(fx):
    trees = "".join(coconut(x, 1120, s) for x, s in ((70, 1.1), (300, 0.8), (820, 0.9), (1010, 1.2)))
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    small_house = ('<g opacity="0.8"><rect x="560" y="900" width="300" height="220" fill="#c9c3a8"/>'
                   '<path d="M530 910 L710 780 L890 910Z" fill="#9a4a32"/><rect x="680" y="990" width="60" height="130" fill="#5a3a22"/></g>')
    puddles = ('<ellipse cx="300" cy="1700" rx="120" ry="22" fill="#a9c0c4" opacity="0.7"/>'
               '<ellipse cx="820" cy="1560" rx="90" ry="16" fill="#a9c0c4" opacity="0.7"/>') if "rain" in fx else ""
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{"" if "rain" in fx else birds()}{small_house}{trees}'
            f'<rect y="1100" width="{W}" height="820" fill="#6f8a5a"/>'
            f'<path d="M420 1100 L660 1100 L1080 1920 L0 1920Z" fill="url(#mud)"/>{puddles}')


def bg_yard(fx):
    trees = "".join(coconut(x, 1100, s) for x, s in ((90, 1.0), (980, 1.1)))
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{"" if "rain" in fx else birds()}{house(550, 1100)}{trees}'
            f'<rect y="1140" width="{W}" height="780" fill="#c9a77a"/>'
            '<g fill="#b8956a" opacity="0.6"><ellipse cx="200" cy="1500" rx="90" ry="14"/><ellipse cx="820" cy="1760" rx="120" ry="16"/></g>')


def bg_school(fx):
    gate = ('<rect x="80" y="700" width="60" height="560" fill="#7a7f86"/><rect x="940" y="700" width="60" height="560" fill="#7a7f86"/>'
            '<rect x="80" y="660" width="920" height="70" rx="12" fill="#2f6b4f"/>'
            '<rect x="0" y="420" width="1080" height="240" fill="#f2e6c9"/><path d="M-20 440 L540 260 L1100 440Z" fill="#9a4a32"/>'
            '<g fill="#5a3a22"><rect x="120" y="470" width="110" height="130"/><rect x="320" y="470" width="110" height="130"/>'
            '<rect x="650" y="470" width="110" height="130"/><rect x="850" y="470" width="110" height="130"/></g>')
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    return f'<rect width="{W}" height="{H}" fill="{sky}"/>{birds()}{gate}<rect y="1240" width="{W}" height="680" fill="#c9a77a"/>'


def bg_classroom(fx):
    desks = "".join(f'<rect x="{x}" y="1380" width="230" height="40" rx="6" fill="#7b4a2c"/><rect x="{x + 20}" y="1420" width="20" height="120" fill="#5f3e26"/><rect x="{x + 190}" y="1420" width="20" height="120" fill="#5f3e26"/>'
                    for x in (40, 420, 800))
    return (f'<rect width="{W}" height="{H}" fill="#e8dcb8"/>'
            '<rect x="140" y="380" width="800" height="440" rx="10" fill="#5a3a22"/><rect x="165" y="405" width="750" height="390" fill="#2f4a3a"/>'
            '<path d="M230 520 q60 -40 120 0 t120 0" stroke="#e8e8e0" stroke-width="7" fill="none" opacity="0.8"/>'
            '<path d="M560 600 h220 M560 650 h160" stroke="#e8e8e0" stroke-width="7" opacity="0.7"/>'
            f'{windows("rain" in fx)}{floor()}{desks}')


def bg_paddy(fx):
    rows = "".join(f'<path d="M0 {y} Q540 {y - 30} 1080 {y}" stroke="#7fb35a" stroke-width="16" fill="none" opacity="0.7"/>' for y in range(1180, 1900, 70))
    hills = '<path d="M0 1000 Q250 820 520 980 T1080 940 L1080 1120 L0 1120Z" fill="#7d9c84"/>'
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{"" if "rain" in fx else birds()}{hills}'
            + "".join(coconut(x, 1110, s, 0.85) for x, s in ((150, 0.7), (880, 0.8)))
            + f'<rect y="1100" width="{W}" height="820" fill="#9cc96b"/>{g("swing", rows, pivot="540,1900", amp=0.6, period=3)}'
            '<path d="M380 1920 L470 1100 L560 1100 L700 1920Z" fill="#a98a5c"/>')


def bg_temple(fx):
    gopuram = ('<rect x="330" y="640" width="420" height="420" fill="#d9c49a"/><path d="M300 660 L540 460 L780 660Z" fill="#9a4a32"/>'
               '<path d="M340 470 L540 330 L740 470Z" fill="#b5652e"/><rect x="480" y="820" width="120" height="240" fill="#5a3a22"/>')
    steps = "".join(f'<rect x="{-20 + i * 30}" y="{1100 + i * 40}" width="{1120 - i * 60}" height="40" fill="{"#b9ab90" if i % 2 else "#a99b80"}"/>' for i in range(6))
    pond = f'<rect y="1340" width="{W}" height="580" fill="url(#sea)"/>' + g("drift", "".join(f'<path d="M{x} {y} q30 -12 60 0" stroke="#bfe3ee" stroke-width="5" fill="none"/>' for x, y in ((100, 1450), (400, 1560), (760, 1480), (250, 1720), (650, 1800))), speed=18)
    sky = "#2a2f4a" if "night" in fx else "url(#clear)"
    return f'<rect width="{W}" height="{H}" fill="{sky}"/>{coconut(140, 1100, 0.9)}{coconut(960, 1100, 1.0)}{gopuram}{steps}{pond}'


def bg_bus_stop(fx):
    shelter = ('<rect x="560" y="900" width="440" height="40" fill="#2f6b4f"/><rect x="580" y="940" width="24" height="560" fill="#7a7f86"/>'
               '<rect x="960" y="940" width="24" height="560" fill="#7a7f86"/><rect x="620" y="1260" width="320" height="30" fill="#8a5a3a"/>')
    sky = "url(#sky)" if "rain" in fx else "url(#clear)"
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{"" if "rain" in fx else birds()}{coconut(150, 1150, 1.0)}{coconut(450, 1150, 0.8)}'
            f'<rect y="1150" width="{W}" height="300" fill="#6f8a5a"/><rect y="1450" width="{W}" height="200" fill="#55595e"/>'
            '<g fill="#e8e3d3">' + "".join(f'<rect x="{x}" y="1540" width="90" height="14"/>' for x in range(0, W, 180)) + '</g>'
            f'<rect y="1650" width="{W}" height="270" fill="#c9a77a"/>{shelter}')


def bg_beach(fx):
    waves = g("drift", "".join(f'<path d="M{x} {y} q40 -20 80 0 t80 0" stroke="#e7f4f6" stroke-width="7" fill="none"/>' for x in range(-200, 1100, 260) for y in (1220, 1320, 1420)), speed=40)
    sky = "#f4b88a" if "sunset" in fx else "url(#clear)"
    sun = '<circle cx="760" cy="1060" r="110" fill="#f6d36b" opacity="0.9"/>' if "sunset" in fx else ""
    return (f'<rect width="{W}" height="{H}" fill="{sky}"/>{sun}<rect y="1100" width="{W}" height="420" fill="url(#sea)"/>{waves}'
            f'<rect y="1500" width="{W}" height="420" fill="#e8cf9a"/>{coconut(80, 1520, 1.2)}')


BACKGROUNDS = {
    "interior": bg_interior, "night_room": bg_night_room, "kitchen": bg_kitchen, "veranda": bg_veranda,
    "lane": bg_lane, "yard": bg_yard, "school": bg_school, "classroom": bg_classroom, "paddy": bg_paddy,
    "temple": bg_temple, "bus_stop": bg_bus_stop, "beach": bg_beach,
}
OUTDOOR = {"veranda", "lane", "yard", "school", "paddy", "temple", "bus_stop", "beach"}


# --------------------------------------------------------------------------- held props (local coords around the hand)
def hand_prop(name: str) -> str:
    if name == "dosa":
        return '<ellipse cx="0" cy="0" rx="46" ry="16" fill="#e2a849" transform="rotate(-20)"/>'
    if name == "burnt_dosa":
        return '<ellipse cx="0" cy="0" rx="46" ry="16" fill="#4a2c17" transform="rotate(-20)"/>'
    if name == "letter":
        return '<g transform="rotate(-8)"><rect x="-45" y="-60" width="90" height="70" fill="#f4f1e6" stroke="#c9c2a8" stroke-width="3"/><path d="M-45 -60 L0 -20 L45 -60" stroke="#c9c2a8" stroke-width="3" fill="none"/></g>'
    if name == "book":
        return '<g><rect x="-60" y="-70" width="120" height="85" rx="4" fill="#c0392b"/><rect x="-55" y="-66" width="52" height="77" fill="#f4f1e6"/><rect x="3" y="-66" width="52" height="77" fill="#f4f1e6"/></g>'
    if name == "phone":
        return '<rect x="-18" y="-40" width="36" height="66" rx="8" fill="#2b2b2b"/><rect x="-13" y="-34" width="26" height="50" rx="4" fill="#6fa8c8"/>'
    if name == "bag":
        return '<rect x="-40" y="0" width="80" height="90" rx="14" fill="#c0392b"/><path d="M-20 0 q20 -30 40 0" stroke="#7a1f16" stroke-width="8" fill="none"/>'
    if name == "flower":
        return '<g><path d="M0 0 L0 -70" stroke="#4f8a45" stroke-width="7"/>' + "".join(f'<circle cx="{12 * math.cos(a):.0f}" cy="{-80 + 12 * math.sin(a):.0f}" r="12" fill="#f2a516"/>' for a in [i * math.pi / 3 for i in range(6)]) + '<circle cx="0" cy="-80" r="9" fill="#d23c3c"/></g>'
    if name == "plate":
        return '<ellipse cx="0" cy="0" rx="70" ry="18" fill="#f4f4f0"/><ellipse cx="0" cy="-6" rx="45" ry="12" fill="#f2f0e0"/>'
    if name == "laddu":
        return '<g fill="#f2a516"><circle cx="-14" cy="-6" r="16"/><circle cx="14" cy="-6" r="16"/><circle cx="0" cy="-26" r="16"/></g>'
    if name == "tiffin":
        return '<g><rect x="-36" y="-80" width="72" height="90" rx="10" fill="#c9ced3"/><path d="M-36 -50 h72 M-36 -20 h72" stroke="#9aa0a6" stroke-width="5"/><path d="M-20 -80 q20 -30 40 0" stroke="#9aa0a6" stroke-width="6" fill="none"/></g>'
    if name == "gift":
        return '<g><rect x="-50" y="-80" width="100" height="80" fill="#d23c3c"/><rect x="-8" y="-80" width="16" height="80" fill="#f2c84b"/><path d="M0 -80 l-30 -24 l0 24z M0 -80 l30 -24 l0 24z" fill="#f2c84b"/></g>'
    if name == "money":
        return '<g transform="rotate(-10)"><rect x="-50" y="-30" width="100" height="50" rx="4" fill="#9ccc9a"/><circle cx="0" cy="-5" r="14" fill="#7aa978"/></g>'
    if name == "toy":
        return '<g><rect x="-45" y="-40" width="90" height="40" rx="10" fill="#2d7dd2"/><circle cx="-25" cy="5" r="14" fill="#2b2b2b"/><circle cx="25" cy="5" r="14" fill="#2b2b2b"/></g>'
    if name == "lamp":
        return '<g><rect x="-26" y="-20" width="52" height="30" rx="8" fill="#c9952b"/>' + g("float", '<path d="M0 -70 q18 26 0 50 q-18 -24 0 -50z" fill="#f6a623"/>', amp=4, period=0.5) + '</g>'
    if name == "kite":
        return '<path d="M0 0 L0 -300" stroke="#eee" stroke-width="3"/>'
    if name == "spatula":
        return ('<g><path d="M0 0 L60 -110" stroke="#6b4529" stroke-width="14" stroke-linecap="round"/>'
                '<rect x="50" y="-150" width="60" height="50" rx="6" fill="#b9bec4" transform="rotate(30 80 -125)"/></g>')
    return ""


# --------------------------------------------------------------------------- people
CHARACTERS = {
    #           build    age    top        bottom/dress  hair
    "appooppan": dict(build="man", old=True, top="#f1e7c9", bottom="mundu", hair="old_man"),
    "achan": dict(build="man", top="#e8e3d3", bottom="trousers", hair="man"),
    "grownup": dict(build="man", top="#8fc1e3", bottom="trousers", hair="man"),
    "uncle": dict(build="man", top="#f0b968", bottom="trousers", hair="man"),
    "ammachi": dict(build="woman", old=True, top="#f3ecd8", hair="old_woman", border="#d4a537"),
    "amma": dict(build="woman", top="#9c3d54", hair="woman", dots="#f3d9e0"),
    "teacher": dict(build="woman", top="#3f6fa8", hair="woman", border="#e8c35a"),
    "chechi": dict(build="woman", top="#4f9d69", hair="braid", teen=True),
    "kid": dict(build="boy", top="#f2c84b", bottom="#3f6fa8"),
    "friend": dict(build="boy", top="#5cb85c", bottom="#7a5a3a"),
    "girl": dict(build="girl", top="#f2a7c3"),
}
ALIASES = {"father": "grownup", "daughter": "girl", "son": "kid", "boy": "kid", "mother": "amma",
           "grandfather": "appooppan", "grandmother": "ammachi", "sister": "chechi", "dad": "achan"}


def eyes_svg(cx, cy, r, mode):
    ex = r * 0.38
    if mode == "open":
        big = 1.0 if r > 110 else 1.3
        rx, ry, ir = r * 0.17 * big, r * 0.16 * big, r * 0.125 * big
        one = lambda x: (f'<ellipse cx="{x}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#fbf6ee"/>'
                         f'<circle cx="{x + 2}" cy="{cy + 2}" r="{ir:.1f}" fill="url(#iris)"/>'
                         f'<circle cx="{x + 2}" cy="{cy + 2}" r="{ir * 0.5:.1f}" fill="#120a05"/>'
                         f'<circle cx="{x - ir * 0.35:.1f}" cy="{cy - ir * 0.4:.1f}" r="{ir * 0.38:.1f}" fill="#ffffff"/>'
                         f'<circle cx="{x + ir * 0.45:.1f}" cy="{cy + ir * 0.45:.1f}" r="{ir * 0.14:.1f}" fill="#ffffff" opacity="0.8"/>'
                         f'<path d="M{x - rx * 1.1:.1f} {cy - ry * 0.25:.1f} Q{x} {cy - ry * 1.45:.1f} {x + rx * 1.1:.1f} {cy - ry * 0.25:.1f}" fill="none" stroke="#1d120b" stroke-width="6" stroke-linecap="round"/>')
        return g("blink", one(cx - ex) + one(cx + ex), pivot=f"{cx},{cy}")
    bend = 16 if mode == "closed" else -12
    off = 0 if mode == "closed" else 6
    return (f'<g fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round">'
            f'<path d="M{cx - ex - 18} {cy + off} Q{cx - ex} {cy + off + bend} {cx - ex + 18} {cy + off}"/>'
            f'<path d="M{cx + ex - 18} {cy + off} Q{cx + ex} {cy + off + bend} {cx + ex + 18} {cy + off}"/></g>')


def mouth_svg(cx, my, mode):
    if mode == "talk":
        return g("talk", f'<ellipse cx="{cx}" cy="{my + 18}" rx="24" ry="22" fill="#5a1f1a"/><ellipse cx="{cx}" cy="{my + 30}" rx="13" ry="8" fill="#d9776f"/>', pivot=f"{cx},{my - 4}")
    if mode == "o":
        return f'<ellipse cx="{cx}" cy="{my + 8}" rx="15" ry="18" fill="#5a1f1a"/>'
    if mode == "flat":
        return f'<path d="M{cx - 24} {my + 8} Q{cx} {my + 2} {cx + 24} {my + 8}" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
    return f'<path d="M{cx - 28} {my} Q{cx} {my + 26} {cx + 28} {my}" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'


def limb(x0, y0, x1, y1, skin, sleeve, bend, amp, period, phase=0.0, extra=""):
    mx, my = (x0 + x1) / 2 + bend, (y0 + y1) / 2
    inner = (f'<path d="M{x0} {y0} Q{mx} {my} {x1} {y1}" stroke="{skin}" stroke-width="44" fill="none" stroke-linecap="round"/>'
             f'<path d="M{x0} {y0} L{x0 + (x1 - x0) * 0.25} {y0 + (y1 - y0) * 0.25}" stroke="{sleeve}" stroke-width="60" stroke-linecap="round"/>{extra}')
    return g("swing", inner, pivot=f"{x0},{y0}", amp=amp, period=period, phase=phase)


class Actor:
    def __init__(self, spec: str):
        name, _, tokens = spec.partition(":")
        self.name = ALIASES.get(name.strip(), name.strip())
        if self.name not in CHARACTERS:
            raise ValueError(f"unknown character {name!r}")
        self.tokens = [t.strip() for t in tokens.split(",") if t.strip()]
        self.hold = next((t.split("=", 1)[1] for t in self.tokens if t.startswith("hold=")), None)
        self.poses = {t for t in self.tokens if "=" not in t}

    @property
    def child(self):
        return CHARACTERS[self.name]["build"] in ("boy", "girl")


def person(actor: Actor, x: float, y: float, s: float, toward: int, seed: int = 0) -> str:
    c = CHARACTERS[actor.name]
    p = actor.poses
    build, old = c["build"], c.get("old", False)
    adult = build in ("man", "woman")
    teen = c.get("teen", False)
    skin = SKIN_OLD if old else SKIN
    top = c["top"]
    walk = "walk" in p

    # face
    eyes = "open"
    mouth = "smile"
    if "happy" in p or "sleep" in p or "pray" in p:
        eyes = "closed"
    if "sad" in p:
        eyes, mouth = "sad", "flat"
    if "surprised" in p:
        mouth = "o"
    if "talk" in p:
        mouth = "talk"
        if "happy" not in p and "sad" not in p:
            eyes = "open"

    if adult:
        hip, sh_y, head_cy, hr, neck, sh_x = -320, -610, -790, 125, -680, 120
    else:
        hip, sh_y, head_cy, hr, neck, sh_x = -200, -380, -505, 100, -430, 75
    if build == "woman":
        sh_x = 110

    # ---- legs / lower body
    lsw = 14 if walk else 0
    if build == "man":
        if c["bottom"] == "mundu":
            legs = (shaded(shaded('<path d="M-120 -320 L120 -320 L130 -10 L-130 -10Z" fill="#f4f1e8"/>'), "fold")
                    + g("swing", '<ellipse cx="-60" cy="0" rx="60" ry="20" fill="#3a2a1a"/>', pivot="-60,-60", amp=12 if walk else 0, period=1.0)
                    + g("swing", '<ellipse cx="60" cy="0" rx="60" ry="20" fill="#3a2a1a"/>', pivot="60,-60", amp=12 if walk else 0, period=1.0, phase=0.5))
        else:
            legs = "".join(g("swing", f'<rect x="{lx - 50}" y="-330" width="100" height="320" rx="20" fill="#4a4f57"/><ellipse cx="{lx}" cy="0" rx="60" ry="20" fill="#3a2a1a"/>',
                             pivot=f"{lx},-320", amp=lsw, period=1.0, phase=ph) for lx, ph in ((-60, 0), (60, 0.5)))
        torso = (f'<path d="M-135 -640 Q0 -680 135 -640 L125 -300 L-125 -300Z" fill="{top}"/>'
                 '<path d="M-40 -660 L0 -610 L40 -660" fill="none" stroke="#000000" stroke-opacity="0.13" stroke-width="10"/>')
    elif build == "woman":
        dress = f'<path d="M-125 -320 L125 -320 L150 -12 L-150 -12Z" fill="{top}"/>'
        if c.get("dots"):
            dress += "".join(f'<circle cx="{dx}" cy="{dy}" r="6" fill="{c["dots"]}" opacity="0.8"/>' for dx, dy in
                             ((-80, -250), (-20, -180), (50, -260), (90, -120), (-60, -90), (10, -60), (70, -30), (-100, -40)))
        if c.get("border"):
            dress += f'<path d="M-150 -40 L150 -40" stroke="{c["border"]}" stroke-width="22"/>'
        if teen:
            dress += '<path d="M-100 -320 L-120 -12 M100 -320 L120 -12" stroke="#2f6b4f" stroke-width="10" opacity="0.4"/>'
        legs = shaded(shaded(dress), "fold") + "".join(g("swing", f'<ellipse cx="{lx}" cy="0" rx="50" ry="17" fill="#3a2a1a"/>', pivot=f"{lx},-60", amp=12 if walk else 0, period=1.0, phase=ph)
                               for lx, ph in ((-55, 0), (55, 0.5)))
        torso = f'<path d="M-125 -640 Q0 -675 125 -640 L120 -300 L-120 -300Z" fill="{top}"/>'
        if c.get("border"):  # saree pallu over the shoulder
            torso += f'<path d="M-110 -640 L110 -330" stroke="{c["border"]}" stroke-width="26" opacity="0.9"/>'
    else:
        girl = build == "girl"
        legs = "".join(g("swing", f'<rect x="{lx - 19}" y="-200" width="38" height="200" fill="{skin}"/><ellipse cx="{lx}" cy="0" rx="40" ry="14" fill="#3a2a1a"/>',
                         pivot=f"{lx},-190", amp=18 if walk else 0, period=1.0, phase=ph) for lx, ph in ((-36, 0), (36, 0.5)))
        if girl:
            torso = f'<path d="M-80 -400 Q0 -425 80 -400 L120 -150 L-120 -150Z" fill="{top}"/><path d="M-118 -165 L118 -165 L120 -150 L-120 -150Z" fill="#000000" opacity="0.13"/>'
        else:
            torso = (f'<path d="M-85 -400 Q0 -425 85 -400 L80 -230 L-80 -230Z" fill="{top}"/>'
                     f'<rect x="-82" y="-240" width="164" height="80" rx="10" fill="{c["bottom"]}"/>')
        if "bag" in actor.tokens or walk:
            bc = "#8a5ab8" if girl else "#c0392b"
            torso = f'<rect x="-110" y="-390" width="60" height="150" rx="16" fill="{bc}"/>' + torso + f'<path d="M-60 -400 L40 -230" stroke="{bc}" stroke-width="12"/>'

    wet = ""
    if "wet" in actor.tokens and adult:
        wet = ('<path d="M-40 -655 Q-120 -660 -135 -640 L-125 -300 L-60 -300Z" fill="#2b4f6a" opacity="0.38"/>'
               + g("rain", '<g fill="#bfe0f2"><circle cx="-110" cy="-280" r="9"/><circle cx="-130" cy="-220" r="8"/><circle cx="-150" cy="-160" r="6"/></g>', speed=90))

    # ---- arms from pose (hand targets in local coords)
    k = 1.0 if adult else 0.66
    down_l, down_r = (-sh_x - 30, hip - 10), (sh_x + 30, hip - 10)
    lh, rh = down_l, down_r
    l_amp = r_amp = 3
    period = 3.0
    l_extra = r_extra = ""
    front = (int(40 * k), int(sh_y + 50 * k))
    mouth_pos = (int(55 * k), int(head_cy + 100 * k))
    held = actor.hold
    if walk:
        l_amp = r_amp = 12
        period = 1.0
    if "point" in p:
        side = toward or 1
        target = (side * (sh_x + 240 * k), sh_y + 60 * k)
        if side < 0:
            lh, l_amp, period = target, 8, 0.8
        else:
            rh, r_amp, period = target, 8, 0.8
    if "wave" in p:
        rh, r_amp, period = (sh_x + 90 * k, sh_y - 230 * k), 22, 0.6
    if "jump" in p:
        lh, rh, l_amp, r_amp, period = (-sh_x - 60 * k, sh_y - 200 * k), (sh_x + 60 * k, sh_y - 200 * k), 16, 16, 0.6
    if "hug" in p:
        side = toward or 1
        lh = (side * (sh_x + 40 * k) - 60 * k, sh_y + 80 * k)
        rh = (side * (sh_x + 140 * k), sh_y + 80 * k)
        l_amp = r_amp = 2
    if "pray" in p:
        lh, rh = (-8, sh_y + 60 * k), (8, sh_y + 60 * k)
        l_amp = r_amp = 1
    if "cook" in p:
        rh, r_amp, period = (150 * k, hip - 40 * k), 14, 1.2
        held = held or "spatula"
    if "eat" in p:
        rh, r_amp, period = mouth_pos, 5, 1.8
    if "hold" in p or ("hold" not in p and held and "eat" not in p and "cook" not in p and "phone" not in p and "read" not in p and "umbrella" not in p):
        rh, r_amp = front, 3
    if "read" in p:
        lh, rh = (-30 * k, sh_y + 60 * k), (30 * k, sh_y + 60 * k)
        l_amp = r_amp = 1
        held = held or "book"
    if "phone" in p:
        rh, r_amp = (int(sh_x - 10 * k), int(head_cy + 30 * k)), 1
        held = held or "phone"
    if "umbrella" in p:
        rh, r_amp = (160 * k, sh_y - 30 * k), 1
    if held and held not in ("kite",):
        r_extra = f'<g transform="translate({rh[0]:.0f},{rh[1]:.0f})">{hand_prop(held)}</g>'
    arms = (limb(-sh_x, sh_y, lh[0], lh[1], skin, top, -35, l_amp, period, 0.0, l_extra)
            + limb(sh_x, sh_y, rh[0], rh[1], skin, top, 35, r_amp, period, 0.5, r_extra))

    # ---- head
    hair_col = "#efefea" if old else "#1f1712"
    face_grad = "skinOld" if old else "skin"
    head = (f'<circle cx="0" cy="{head_cy}" r="{hr}" fill="url(#{face_grad})"/>'
            f'<ellipse cx="0" cy="{head_cy + hr * 0.98:.0f}" rx="{hr * 0.55:.0f}" ry="{hr * 0.16:.0f}" fill="#000000" opacity="0.08"/>')
    hair = c.get("hair", "")
    if hair == "old_man":
        head += ('<path d="M-125 -800 Q-130 -880 -80 -900 Q-110 -850 -105 -780Z" fill="#efefea"/>'
                 '<path d="M125 -800 Q130 -880 80 -900 Q110 -850 105 -780Z" fill="#efefea"/>')
    elif hair == "man":
        head += '<path d="M-128 -790 Q-130 -930 0 -925 Q130 -930 128 -790 Q100 -880 0 -880 Q-100 -880 -128 -790Z" fill="#1f1712"/>'
    elif hair in ("woman", "old_woman", "braid"):
        head += (f'<circle cx="0" cy="-925" r="{0 if hair == "braid" else 62}" fill="{hair_col}"/>'
                 f'<path d="M-130 -760 Q-140 -935 0 -930 Q140 -935 130 -760 Q118 -860 0 -870 Q-118 -860 -130 -760Z" fill="{hair_col}"/>'
                 f'<circle cx="0" cy="-845" r="10" fill="#c0392b"/>'
                 '<circle cx="-127" cy="-752" r="10" fill="#e0b13a"/><circle cx="127" cy="-752" r="10" fill="#e0b13a"/>')
        if hair == "braid":
            head += g("swing", '<path d="M110 -800 Q170 -650 130 -470" stroke="#1f1712" stroke-width="34" fill="none" stroke-linecap="round"/><circle cx="130" cy="-465" r="16" fill="#f2c84b"/>', pivot="110,-800", amp=3, period=2.5)
    elif build == "girl":
        head += ('<path d="M-104 -500 Q-110 -620 0 -615 Q110 -620 104 -500 Q80 -570 0 -572 Q-80 -570 -104 -500Z" fill="#1f1712"/>'
                 '<circle cx="-115" cy="-560" r="34" fill="#1f1712"/><circle cx="115" cy="-560" r="34" fill="#1f1712"/>'
                 '<circle cx="-92" cy="-580" r="13" fill="#d23c3c"/><circle cx="92" cy="-580" r="13" fill="#d23c3c"/>')
    else:
        head += '<path d="M-104 -505 Q-110 -615 0 -612 Q110 -615 104 -505 Q90 -575 0 -575 Q-90 -575 -104 -505Z" fill="#1f1712"/>'
    ear_y = head_cy + 10
    head += f'<circle cx="{-hr - 1}" cy="{ear_y}" r="{hr * 0.15}" fill="{skin}"/><circle cx="{hr + 1}" cy="{ear_y}" r="{hr * 0.15}" fill="{skin}"/>'
    hl = "#ffffff" if old else "#6a5a52"
    head += (f'<path d="M{-hr * 0.55:.0f} {head_cy - hr * 0.86:.0f} Q0 {head_cy - hr * 1.08:.0f} {hr * 0.45:.0f} {head_cy - hr * 0.9:.0f}" '
             f'fill="none" stroke="{hl}" stroke-width="{hr * 0.09:.0f}" stroke-linecap="round" opacity="0.35"/>')
    ey = head_cy + (0 if adult else 5)
    head += eyes_svg(0, ey, hr, eyes)
    if old:
        ex = hr * 0.38
        head += (f'<g fill="none" stroke="{INK}" stroke-width="7"><circle cx="{-ex}" cy="{ey}" r="{hr * 0.27}"/>'
                 f'<circle cx="{ex}" cy="{ey}" r="{hr * 0.27}"/><path d="M{-ex + hr * 0.27} {ey} H{ex - hr * 0.27}"/></g>')
    exb = hr * 0.38
    lift_in, lift_out = (12, -4) if "sad" in p else (12, 12) if mouth == "o" else (0, 0)
    brow_col = "#d8d4cc" if old else "#1d120b"
    for sx in (-1, 1):
        inner_y = ey - hr * 0.40 - lift_in
        outer_y = ey - hr * 0.36 - lift_out
        head += (f'<path d="M{sx * (exb - hr * 0.2):.0f} {inner_y:.0f} Q{sx * exb:.0f} {ey - hr * 0.52 - lift_in:.0f} {sx * (exb + hr * 0.22):.0f} {outer_y:.0f}" '
                 f'fill="none" stroke="{brow_col}" stroke-width="{hr * 0.05:.0f}" stroke-linecap="round"/>')
    head += (f'<path d="M{-hr * 0.05:.0f} {ey + hr * 0.18:.0f} Q{hr * 0.1:.0f} {ey + hr * 0.3:.0f} {-hr * 0.06:.0f} {ey + hr * 0.36:.0f}" '
             f'fill="none" stroke="#5a3320" stroke-width="5" stroke-linecap="round" opacity="0.6"/>')
    head += (f'<ellipse cx="{-hr * 0.58}" cy="{ey + hr * 0.36}" rx="{hr * 0.24:.0f}" ry="{hr * 0.15:.0f}" fill="url(#blush)"/>'
             f'<ellipse cx="{hr * 0.58}" cy="{ey + hr * 0.36}" rx="{hr * 0.24:.0f}" ry="{hr * 0.15:.0f}" fill="url(#blush)"/>')
    if "sad" in p and "cry" in actor.tokens:
        head += g("rain", f'<circle cx="{-hr * 0.38}" cy="{ey + 30}" r="7" fill="#bfe0f2"/>', speed=60)
    my = ey + hr * 0.5
    head += mouth_svg(0, my, mouth)
    if build == "man":
        col = "#efefea" if old else "#2b1d14"
        head += f'<path d="M-50 {my - 4} Q0 {my - 34} 50 {my - 4} Q0 {my - 14} -50 {my - 4}Z" fill="{col}"/>'
    neck_svg = f'<rect x="-28" y="{neck - 25}" width="56" height="60" fill="{skin}"/>'
    head_amp = 1.2 if "sleep" in p else 2.5
    head_g = g("swing", neck_svg + head, pivot=f"0,{neck + 30}", amp=head_amp, period=4.0, phase=(seed % 7) / 7)

    shadow = f'<ellipse cx="0" cy="6" rx="{190 if adult else 130}" ry="{34 if adult else 26}" fill="url(#contact)"/>'
    body = legs + shaded(torso) + wet + arms + head_g
    breathe = g("breathe", body, pivot="0,0", amp=2.2 if "sleep" in p else 1.3)
    scale = s * (0.88 if teen else 1.0)
    inner = f'<g transform="translate({x:.0f},{y:.0f}) scale({scale:.3f})">{shadow}{breathe}</g>'
    if walk:
        inner = g("bob", inner, amp=9, period=0.5)
    if "jump" in p:
        inner = g("bob", inner, amp=45, period=0.6)
    return inner


# --------------------------------------------------------------------------- scene props
def umbrella_open(cx, cy, r=330, tilt=0, handle=470):
    ribs = "".join(f'<path d="M0 0 Q{dx * 0.6} {-r * 0.5} {dx} 0" fill="none" stroke="#3a3a3a" stroke-width="6"/>' for dx in (-r * 0.5, r * 0.5))
    scallop = "".join(f'<path d="M{-r + i * r / 2} 0 Q{-r + i * r / 2 + r / 4} 34 {-r + (i + 1) * r / 2} 0" fill="#1c1c1c"/>' for i in range(4))
    inner = (f'<g transform="translate({cx},{cy}) rotate({tilt})">'
             f'<line x1="0" y1="-{r * 0.15}" x2="0" y2="{handle}" stroke="#2b2b2b" stroke-width="12"/>'
             f'<path d="M0 {handle} q0 40 -36 40" stroke="#6b4529" stroke-width="16" fill="none" stroke-linecap="round"/>'
             f'<path d="M{-r} 0 A{r} {r * 0.82} 0 0 1 {r} 0Z" fill="#1c1c1c"/>{scallop}{ribs}'
             f'<circle cx="0" cy="{-r * 0.82}" r="10" fill="#2b2b2b"/></g>')
    hx = cx - handle * math.sin(math.radians(tilt))
    hy = cy + handle * math.cos(math.radians(tilt))
    return g("swing", inner, pivot=f"{hx:.0f},{hy:.0f}", amp=2.5, period=1.0)


def umbrella_closed(x, y, s=1.0):
    inner = (f'<g transform="translate({x},{y}) scale({s})">'
             '<path d="M0 0 q-50 0 -50 -50 q0 -30 30 -30" stroke="#6b4529" stroke-width="16" fill="none" stroke-linecap="round"/>'
             '<line x1="0" y1="0" x2="0" y2="560" stroke="#2b2b2b" stroke-width="10"/>'
             '<path d="M0 60 Q58 120 34 470 L0 560 L-34 470 Q-58 120 0 60Z" fill="#1c1c1c"/>'
             '<path d="M-30 300 Q0 320 30 300" stroke="#444" stroke-width="8" fill="none"/></g>')
    return g("swing", inner, pivot=f"{x},{y - 60 * s}", amp=2.0, period=2.8)


def wheel(cx, cy, r, spin_period):
    spokes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(a):.1f}" y2="{cy + r * math.sin(a):.1f}" stroke="#9aa0a6" stroke-width="4"/>'
                     for a in [i * math.pi / 6 for i in range(12)])
    inner = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1c1c1c" stroke-width="16"/>{spokes}<circle cx="{cx}" cy="{cy}" r="12" fill="#555"/>'
    return g("spin", inner, pivot=f"{cx},{cy}", period=spin_period) if spin_period else inner


def bicycle(x, y, s=1.0, color="#1f1f1f", spin=None, old=True, bow=False):
    r, rx, fx = 110, -190, 190
    hy = -r
    frame = (f'<g stroke="{color}" stroke-width="16" stroke-linecap="round" fill="none">'
             f'<path d="M{rx} {hy} L-20 {hy - 20} L-60 -270 Z"/><path d="M-20 {hy - 20} L130 -280 L-60 -270"/><path d="M130 -280 L{fx} {hy}"/>'
             '<path d="M130 -280 L115 -330"/></g>'
             '<path d="M95 -340 Q120 -350 150 -335" stroke="#2b2b2b" stroke-width="14" fill="none" stroke-linecap="round"/>'
             '<ellipse cx="-70" cy="-290" rx="48" ry="14" fill="#3a2a1a"/>'
             f'<circle cx="-20" cy="{hy - 20}" r="22" fill="#444"/><circle cx="150" cy="-352" r="11" fill="#d4d7da"/>')
    if old:
        frame += '<path d="M-60 -270 L-200 -260" stroke="#555" stroke-width="10"/><g fill="#8a5a3a" opacity="0.55"><circle cx="40" cy="-175" r="9"/><circle cx="-110" cy="-185" r="7"/></g>'
    if bow:
        frame += '<g fill="#f2c84b"><path d="M120 -330 l-50 -30 l0 60z"/><path d="M120 -330 l50 -30 l0 60z"/><circle cx="120" cy="-330" r="14"/></g>'
    return f'<g transform="translate({x},{y}) scale({s})">{wheel(rx, hy, r, spin)}{wheel(fx, hy, r, spin)}{frame}</g>'


def table(food=None):
    out = ('<rect x="40" y="1290" width="1000" height="60" rx="12" fill="#7b4a2c"/>'
           '<rect x="80" y="1350" width="40" height="200" fill="#5f3e26"/><rect x="960" y="1350" width="40" height="200" fill="#5f3e26"/>')
    for x in (330, 760):
        out += f'<ellipse cx="{x}" cy="1290" rx="130" ry="30" fill="#f4f4f0"/><ellipse cx="{x}" cy="1286" rx="100" ry="20" fill="#e3e3dc"/>'
        if food == "dosa":
            out += "".join(f'<ellipse cx="{x}" cy="{1280 - i * 10}" rx="95" ry="20" fill="#e2a849" stroke="#000000" stroke-opacity="0.1" stroke-width="3"/>' for i in range(3))
        elif food == "burnt":
            out += f'<ellipse cx="{x}" cy="1280" rx="95" ry="20" fill="{"#4a2c17" if x == 330 else "#e2a849"}"/>'
        elif food == "rice":
            out += f'<ellipse cx="{x}" cy="1278" rx="80" ry="22" fill="#f7f3e6"/><ellipse cx="{x + 40}" cy="1276" rx="30" ry="12" fill="#e0a43a"/>'
        elif food == "sweets":
            out += "".join(f'<circle cx="{x + dx}" cy="{1268 + dy}" r="18" fill="#f2a516"/>' for dx, dy in ((-30, 0), (0, 0), (30, 0), (-15, -24), (15, -24)))
        elif food == "sadya":
            out += f'<path d="M{x - 110} 1290 Q{x} 1250 {x + 110} 1290 Q{x} 1300 {x - 110} 1290Z" fill="#4f9d45"/><ellipse cx="{x}" cy="1278" rx="40" ry="14" fill="#f7f3e6"/>'
    return out


def stove():
    flames = g("float", '<g fill="#f2932b" opacity="0.85"><path d="M240 1300 l12 -22 l12 22z"/><path d="M290 1300 l12 -26 l12 26z"/><path d="M340 1300 l12 -22 l12 22z"/></g>', amp=3, period=0.4)
    steam = g("float", g("swing", "".join(f'<circle cx="{300 + dx}" cy="{1230 - dy}" r="{r}" fill="#ffffff" opacity="{op}"/>' for dx, dy, r, op in ((0, 30, 26, .45), (-20, 90, 32, .35), (15, 160, 38, .25))), pivot="300,1230", amp=6, period=2.2), amp=18, period=2.5)
    return ('<rect x="0" y="1330" width="640" height="320" fill="#8a5a3a"/><rect x="0" y="1310" width="640" height="40" fill="#6b4529"/>'
            '<rect x="40" y="1380" width="250" height="220" rx="8" fill="#7a4d31"/><rect x="330" y="1380" width="250" height="220" rx="8" fill="#7a4d31"/>'
            '<rect x="90" y="1270" width="420" height="50" rx="10" fill="#2f3237"/><ellipse cx="300" cy="1262" rx="150" ry="34" fill="#1c1c1c"/>'
            f'<ellipse cx="300" cy="1255" rx="118" ry="24" fill="#e2a849"/>{flames}{steam}')


def nilavilakku(x=880, y=1500, s=1.0):
    flame = g("float", '<path d="M0 -330 q22 32 0 62 q-22 -30 0 -62z" fill="#f6a623"/>', amp=5, period=0.45)
    return (f'<g transform="translate({x},{y}) scale({s})"><circle cx="0" cy="-300" r="120" fill="url(#glow)"/>'
            '<path d="M-90 0 L90 0 L60 -40 L-60 -40Z" fill="#c9952b"/><rect x="-12" y="-260" width="24" height="220" fill="#d9a83a"/>'
            f'<path d="M-70 -270 Q0 -230 70 -270 L50 -250 L-50 -250Z" fill="#c9952b"/>{flame}</g>')


def stool(x, y, w=200):
    return (f'<rect x="{x - w / 2}" y="{y}" width="{w}" height="26" rx="6" fill="#7b4a2c"/>'
            f'<rect x="{x - w / 2 + 15}" y="{y + 26}" width="18" height="{1560 - y}" fill="#5f3e26"/><rect x="{x + w / 2 - 33}" y="{y + 26}" width="18" height="{1560 - y}" fill="#5f3e26"/>')


def kerosene_lamp(x=960, y=1330):
    flame = g("float", '<path d="M0 -120 q14 20 0 40 q-14 -20 0 -40z" fill="#f6a623"/>', amp=3, period=0.5)
    return (stool(x, y, 160) + f'<g transform="translate({x},{y})"><circle cx="0" cy="-100" r="200" fill="url(#glow)"/>'
            '<path d="M-50 0 L50 0 L40 -60 L-40 -60Z" fill="#7a5a2a"/><path d="M-30 -60 Q-50 -140 0 -160 Q50 -140 30 -60Z" fill="#f4f1e6" opacity="0.5"/>'
            f'{flame}</g>')


def radio(x=930, y=1300):
    notes = g("float", '<g fill="#3a2a1a"><circle cx="40" cy="-200" r="10"/><path d="M48 -200 v-50" stroke="#3a2a1a" stroke-width="5"/><circle cx="-40" cy="-240" r="10"/><path d="M-32 -240 v-50" stroke="#3a2a1a" stroke-width="5"/></g>', amp=14, period=1.2)
    return (stool(x, y, 240) + f'<g transform="translate({x},{y})"><rect x="-110" y="-150" width="220" height="150" rx="16" fill="#7a4a2a"/>'
            '<circle cx="-45" cy="-75" r="45" fill="#3a2a1a"/><rect x="20" y="-120" width="70" height="20" fill="#f2e6c9"/>'
            f'<circle cx="55" cy="-55" r="16" fill="#d9a83a"/><path d="M-90 -150 L-130 -260" stroke="#555" stroke-width="6"/>{notes}</g>')


def tv(x=760, y=1330):
    return (f'<g transform="translate({x},{y})"><rect x="-170" y="-260" width="340" height="250" rx="20" fill="#5a3a22"/>'
            '<rect x="-140" y="-230" width="230" height="190" rx="14" fill="#7fb3c9"/>'
            + g("float", '<rect x="-120" y="-200" width="180" height="120" fill="#a9d3e0" opacity="0.6"/>', amp=4, period=0.8)
            + '<circle cx="125" cy="-190" r="12" fill="#d9a83a"/><circle cx="125" cy="-140" r="12" fill="#d9a83a"/>'
            '<path d="M-60 -260 L-110 -360 M60 -260 L110 -360" stroke="#555" stroke-width="6"/><rect x="-200" y="-10" width="400" height="30" fill="#6b4529"/></g>')


def kite(x=780, y=420):
    tail = "".join(f'<path d="M{-6 + i * 4} {130 + i * 40} l20 10 l-20 10z" fill="#f2c84b"/>' for i in range(4))
    k = f'<path d="M0 0 L90 110 L0 230 L-90 110Z" fill="#d23c3c"/><path d="M0 0 L0 230 M-90 110 L90 110" stroke="#7a1f16" stroke-width="5"/>{tail}'
    return g("swing", g("float", f'<g transform="translate({x},{y})">{k}</g>', amp=25, period=2.4), pivot=f"{x},{y + 900}", amp=4, period=3)


def pookkalam(x=540, y=1640):
    rings = "".join(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{rx * 0.32:.0f}" fill="{c}"/>' for rx, c in ((300, "#f2a516"), (240, "#d23c3c"), (180, "#f5f2e8"), (120, "#8a5ab8"), (60, "#f2c84b")))
    return rings


def gift(x=800, y=1680):
    return (f'<g transform="translate({x},{y})"><rect x="-90" y="-150" width="180" height="150" fill="#d23c3c"/>'
            '<rect x="-14" y="-150" width="28" height="150" fill="#f2c84b"/><path d="M0 -150 l-50 -40 l0 40z M0 -150 l50 -40 l0 40z" fill="#f2c84b"/></g>')


def bus(x=540, y=1600, moving=True):
    body = (f'<g transform="translate({x},{y})"><rect x="-420" y="-380" width="840" height="320" rx="30" fill="#d9452b"/>'
            '<rect x="-420" y="-160" width="840" height="40" fill="#f2c84b"/>'
            + "".join(f'<rect x="{-380 + i * 150}" y="-340" width="120" height="120" rx="10" fill="#bfe0f2"/>' for i in range(5))
            + f'</g>{wheel(x - 260, y - 60, 70, 0.6 if moving else None)}{wheel(x + 260, y - 60, 70, 0.6 if moving else None)}')
    return g("move", body, dx=-260 if moving else 0, dy=0)


def mango_tree(x=860, y=1500):
    leaves = "".join(f'<circle cx="{x + dx}" cy="{y - 700 + dy}" r="{r}" fill="#4f7a45"/>' for dx, dy, r in ((-150, 60, 170), (120, 40, 180), (0, -90, 200), (-40, 120, 160)))
    mangoes = "".join(f'<ellipse cx="{x + dx}" cy="{y - 650 + dy}" rx="18" ry="26" fill="#f2b33a"/>' for dx, dy in ((-120, 120), (60, 150), (150, 60), (-30, 10)))
    return f'<rect x="{x - 40}" y="{y - 600}" width="80" height="600" fill="#6b4a2c"/>' + g("swing", leaves + mangoes, pivot=f"{x},{y - 500}", amp=1.5, period=3.5)


def chair(x=800, y=1690):
    return (f'<g transform="translate({x},{y})"><rect x="-120" y="-330" width="240" height="30" fill="#7b4a2c"/><rect x="-120" y="-640" width="30" height="640" fill="#6b4529"/>'
            '<rect x="90" y="-330" width="30" height="330" fill="#6b4529"/><rect x="-120" y="-640" width="240" height="30" fill="#7b4a2c"/>'
            '<path d="M-100 -600 L100 -340" stroke="#c9b48a" stroke-width="10"/><path d="M100 -600 L-100 -340" stroke="#c9b48a" stroke-width="10"/></g>')


def clock(x=200, y=700):
    hand = g("spin", f'<path d="M{x} {y} L{x} {y - 34}" stroke="{INK}" stroke-width="6"/>', pivot=f"{x},{y}", period=8)
    return f'<circle cx="{x}" cy="{y}" r="52" fill="#f3efe4" stroke="#5a3a22" stroke-width="8"/>{hand}<path d="M{x} {y} H{x + 24}" stroke="{INK}" stroke-width="6"/>'


def books(x=860, y=1290):
    return "".join(f'<rect x="{x - 90 + i * 8}" y="{y - 30 - i * 26}" width="180" height="26" rx="4" fill="{c}"/>' for i, c in enumerate(("#2d7dd2", "#d23c3c", "#27ae60", "#f2c84b")))


def tiffin(x=860, y=1290):
    return f'<g transform="translate({x},{y})">{hand_prop("tiffin")}</g>'


def photo(who: str, x=820, y=640, garland=False):
    act = Actor(who)
    pic = f'<svg x="{x - 105}" y="{y - 145}" width="210" height="270" viewBox="-330 -1030 660 850">{person(act, 0, 0, 1.0, 0)}</svg>'
    out = (f'<rect x="{x - 130}" y="{y - 170}" width="260" height="320" rx="10" fill="#5a3a22"/>'
           f'<rect x="{x - 105}" y="{y - 145}" width="210" height="270" fill="#e8dcc0"/>{pic}')
    if garland:
        out += "".join(f'<circle cx="{x - 128 + i * 12.8:.0f}" cy="{y - 165 + 300 * math.sin(math.pi * i / 20):.0f}" r="15" fill="{"#f2a516" if i % 2 else "#f5f2e8"}"/>' for i in range(21))
    return out


def prop(spec: str) -> tuple[str, str]:
    """Returns (svg, layer) where layer is 'back' (behind people) or 'front'."""
    name, _, arg = spec.partition(":")
    if name == "table":
        return table(arg or None), "front"
    if name == "stove":
        return stove(), "front"
    if name == "hanging_umbrella":
        return umbrella_closed(980, 1080, 0.7), "back"
    if name in ("bicycle", "bicycle_parked"):
        color = {"red": "#d23c3c", "blue": "#2d7dd2", "green": "#27ae60"}.get(arg, "#1f1f1f")
        return bicycle(860, 1650, 0.9, color=color, old=arg in ("", "old"), bow=arg == "red"), "back"
    if name == "empty_bicycle":
        return f'<g opacity="0.18">{bicycle(560, 1560, 1.25)}</g>', "back"
    if name == "photo":
        who, _, garl = arg.partition("+")
        return photo(who or "appooppan", garland=garl == "garland"), "back"
    if name == "nilavilakku":
        return nilavilakku(), "back"
    if name == "kerosene_lamp":
        return kerosene_lamp(), "back"
    if name == "radio":
        return radio(), "back"
    if name == "tv":
        return tv(), "back"
    if name == "kite":
        return kite(), "back"
    if name == "pookkalam":
        return pookkalam(), "back"
    if name == "gift":
        return gift(), "front"
    if name == "bus":
        return bus(), "back"
    if name == "mango_tree":
        return mango_tree(), "back"
    if name == "chair":
        return chair(), "back"
    if name == "clock":
        return clock(), "back"
    if name == "books":
        return books(), "front"
    if name == "tiffin":
        return tiffin(), "front"
    if name == "sweets":
        return table("sweets"), "front"
    raise ValueError(f"unknown prop {spec!r}")


# --------------------------------------------------------------------------- night atmosphere
def moon(seed=0):
    x = 780 if seed % 2 else 300
    return (f'<circle cx="{x}" cy="330" r="330" fill="url(#moonglow)"/>'
            f'<circle cx="{x}" cy="330" r="78" fill="#fbf3d0"/><circle cx="{x + 22}" cy="312" r="16" fill="#e9dfb5" opacity="0.6"/>'
            f'<circle cx="{x - 26}" cy="352" r="11" fill="#e9dfb5" opacity="0.5"/>')


def dust(seed, cx, cy, n=22):
    r = random.Random(seed + 7)
    return "".join(g("float", f'<circle cx="{cx + r.uniform(-450, 450):.0f}" cy="{cy + r.uniform(-650, 350):.0f}" r="{r.uniform(2, 5):.1f}" fill="#ffe2a8" opacity="{r.uniform(.3, .7):.2f}"/>',
                     amp=f"{r.uniform(10, 25):.0f}", period=f"{r.uniform(3, 6):.1f}", phase=f"{r.random():.2f}") for _ in range(n))


def fireflies(seed=0, n=14):
    r = random.Random(seed + 99)
    return "".join(g("float", f'<circle cx="{r.uniform(60, W - 60):.0f}" cy="{r.uniform(900, 1700):.0f}" r="{r.uniform(10, 18):.0f}" fill="url(#firefly)"/>',
                     amp=f"{r.uniform(12, 30):.0f}", period=f"{r.uniform(2, 4):.1f}", phase=f"{r.random():.2f}") for _ in range(n))


# --------------------------------------------------------------------------- compose
def layout(n: int) -> list[float]:
    return {0: [], 1: [540], 2: [330, 760], 3: [230, 540, 860], 4: [170, 410, 670, 910]}.get(n, [540] * n)


def compile_scene(art: dict, seed: int = 0) -> str:
    fx = set(art.get("fx", []))
    bg_name = art.get("bg", "interior")
    if bg_name not in BACKGROUNDS:
        raise ValueError(f"unknown background {bg_name!r}")
    body = BACKGROUNDS[bg_name](fx)
    if "rain" in fx and bg_name in ("lane", "school", "paddy", "bus_stop", "yard", "temple"):
        body += rain_layer(seed + 2)
    back, front = "", ""
    for spec in art.get("props", []):
        svg, layer = prop(spec)
        if layer == "back":
            back += svg
        else:
            front += svg

    actors = [Actor(a) for a in art.get("cast", [])]
    people = ""
    if art.get("shot") == "close" and actors:
        a = actors[0]
        s = 1.45 if not a.child else 2.2
        y = 2250 if not a.child else 2170
        people = person(a, 540, y, s, 0, seed)
    else:
        xs = art.get("xs") or layout(len(actors))
        if "stove" in art.get("props", []) and actors and "cook" in actors[0].poses and not art.get("xs"):
            xs = [330] + [760 + 150 * i for i in range(len(actors) - 1)]
        crowd = len(actors) >= 3
        walkers = all("walk" in a.poses for a in actors) and actors
        umbrella = ""
        for i, (a, x) in enumerate(zip(actors, xs)):
            toward = 0
            if len(actors) > 1:
                toward = 1 if x < 540 else -1
            s = (0.8 if crowd else 0.92) if not a.child else (0.92 if crowd else 1.0)
            people += person(a, x, GROUND - (0 if not a.child else 20), s, toward, seed + i)
            if "umbrella" in a.poses:
                # umbrella held up in the right hand, leaning over the person to the right
                if a.child:
                    hand_x, hand_y = x + 106 * s, GROUND - 20 - 405 * s
                else:
                    hand_x, hand_y = x + 160 * s, GROUND - 640 * s
                umbrella = umbrella_open(hand_x + 114, hand_y - 456, tilt=14)
        people += umbrella
        if walkers:
            people = g("move", people, dx=140, dy=0)
    body += back + people + front
    if "night" in fx and bg_name in OUTDOOR:
        body = body.replace('fill="url(#clear)"', 'fill="#2a2f4a"', 1) + stars(seed)
    props = [sp.split(":")[0] for sp in art.get("props", [])]
    lamps = [(880, 1200)] * ("nilavilakku" in props) + [(960, 1230)] * ("kerosene_lamp" in props)
    if lamps and bg_name not in OUTDOOR:
        fx.add("night")  # a lit lamp indoors means evening: use the lamplight mood
    if "night" in fx:
        if lamps:  # darkness everywhere except a pool of lamplight
            lx, ly = lamps[0]
            body += (f'<defs><radialGradient id="dark{seed}" gradientUnits="userSpaceOnUse" cx="{lx}" cy="{ly}" r="1150">'
                     '<stop offset="0" stop-color="#05060f" stop-opacity="0"/><stop offset="0.35" stop-color="#05060f" stop-opacity="0.25"/>'
                     '<stop offset="1" stop-color="#05060f" stop-opacity="0.88"/></radialGradient></defs>'
                     f'<rect width="{W}" height="{H}" fill="url(#dark{seed})"/>' + dust(seed, lx, ly))
        else:
            body += f'<rect width="{W}" height="{H}" fill="#0d1230" opacity="{0.5 if bg_name not in OUTDOOR else 0.36}"/>'
        if bg_name in OUTDOOR:
            body += moon(seed) + fireflies(seed)
    for lx, ly in lamps:
        r = 900 if "night" in fx else 650
        body += g("flicker", f'<circle cx="{lx}" cy="{ly}" r="{r}" fill="url(#lamplight)"/>', amp=0.12, period=0.37)
    if not lamps and bg_name not in OUTDOOR and "night" not in fx:
        body += f'<rect width="{W}" height="{H}" fill="#ffb060" opacity="0.07"/>'
    if "sunset" in fx and bg_name != "beach":
        body += f'<rect width="{W}" height="{H}" fill="#f4a261" opacity="0.18"/>'
    if "festive" in fx:
        r = random.Random(seed)
        body += g("rain", "".join(f'<rect x="{r.uniform(0, W):.0f}" y="{r.uniform(0, H):.0f}" width="12" height="12" fill="{r.choice(["#f2a516", "#d23c3c", "#f2c84b", "#8a5ab8"])}" transform="rotate(30)"/>' for _ in range(50)), speed=160)
    vignette = f'<rect width="{W}" height="{H}" fill="url(#vignette)" data-fixed="1"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{DEFS}{body}{vignette}</svg>'
