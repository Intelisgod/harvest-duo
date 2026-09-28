"""Item & tool icons (28x28 hotbar art) plus the held-tool / held-item renderers.

Owner: "UI & Rendering" chat. When a new item or tool is added, give it an icon
in ``item_icon`` / ``tool_icon`` here. Pricing/behaviour lives in the relevant
gameplay system, not in this art module.
"""
import math
import pygame
from ..crops import CROPS
from ..fishing import FISH
from .. import loot, cooking
from ._base import (_cache, _surf, _ic, _lt, _dk, _I, IC, WOOD, STEEL,
                    CAN_BLUE, GOLD_HILT, CROP_FORM, FISH_LOOK)


def fish_icon(color=(120, 170, 210)):
    key = ("fish", color)
    if key in _cache:
        return _cache[key]
    s = _surf((24, 16))
    dk = _dk(color, 0.78)
    dk2 = _dk(color, 0.6)
    lt = _lt(color, 1.16)
    # tail (behind body) with a darker inner notch for depth
    pygame.draw.polygon(s, dk, [(15, 8), (24, 2), (24, 14)])
    pygame.draw.polygon(s, dk2, [(18, 8), (24, 5), (24, 11)])
    # fins tucked behind the body so only the tips show
    pygame.draw.polygon(s, dk, [(6, 3), (12, 0), (13, 4)])       # dorsal fin
    pygame.draw.polygon(s, dk, [(7, 12), (12, 12), (9, 16)])     # pelvic fin
    # body with back-shade + belly highlight (soft rounded shading)
    pygame.draw.ellipse(s, color, (0, 2, 18, 12))
    pygame.draw.ellipse(s, dk, (1, 3, 16, 5))                    # darker back
    pygame.draw.ellipse(s, lt, (2, 8, 14, 5))                    # lit belly
    pygame.draw.line(s, dk, (8, 4), (6, 12), 1)                  # gill slit
    # eye near the head (fish faces left)
    pygame.draw.circle(s, (250, 250, 252), (4, 6), 2)
    pygame.draw.circle(s, (28, 26, 34), (4, 6), 1)
    _cache[key] = s
    return s


def tool_icon(name):
    key = ("ticon", name)
    if key in _cache:
        return _cache[key]
    s = _ic()
    if name == "hoe":
        pygame.draw.line(s, WOOD, (6, 23), (20, 7), 3)
        pygame.draw.line(s, STEEL, (19, 5), (25, 9), 4)
    elif name == "watering_can":
        pygame.draw.rect(s, (70, 140, 200), (6, 12, 13, 11), border_radius=2)
        pygame.draw.line(s, (70, 140, 200), (18, 13), (25, 8), 3)   # spout
        pygame.draw.line(s, (70, 140, 200), (8, 12), (12, 7), 3)    # handle
        pygame.draw.circle(s, (150, 200, 235), (25, 8), 2)
    elif name == "pickaxe":
        pygame.draw.line(s, WOOD, (14, 6), (14, 24), 3)
        pygame.draw.line(s, STEEL, (5, 9), (23, 7), 3)
        pygame.draw.line(s, STEEL, (5, 9), (8, 6), 3)
        pygame.draw.line(s, STEEL, (23, 7), (20, 5), 3)
    elif name == "axe":
        pygame.draw.line(s, WOOD, (10, 24), (18, 6), 3)
        pygame.draw.polygon(s, STEEL, [(16, 4), (25, 8), (20, 14), (14, 9)])
    elif name == "sword":
        pygame.draw.line(s, STEEL, (7, 22), (20, 7), 4)
        pygame.draw.circle(s, (230, 220, 120), (21, 6), 2)
        pygame.draw.line(s, (120, 90, 60), (4, 24), (9, 19), 4)     # hilt
        pygame.draw.line(s, (200, 170, 90), (6, 17), (12, 23), 3)   # guard
    elif name == "fishing_rod":
        pygame.draw.line(s, WOOD, (5, 24), (22, 5), 2)
        pygame.draw.line(s, (220, 220, 220), (22, 5), (22, 18), 1)  # line
        pygame.draw.circle(s, (220, 220, 220), (22, 19), 2, 1)      # hook
    else:
        pygame.draw.rect(s, (180, 180, 180), (6, 6, 16, 16), border_radius=3)
    _cache[key] = s
    return s


def _draw_crop(s, crop):
    col = CROPS[crop]["color"]
    lt, dk = _lt(col), _dk(col)
    form = CROP_FORM.get(crop, "fruit")
    if form == "root":
        pygame.draw.polygon(s, col, [(14, 8), (21, 15), (14, 25), (7, 15)])
        pygame.draw.line(s, dk, (14, 11), (14, 23), 1)
        for lx in (10, 14, 18):
            pygame.draw.line(s, (96, 168, 86), (lx, 8), (14, 2), 2)
    elif form == "gourd":
        pygame.draw.ellipse(s, col, (5, 9, 18, 15))
        for rx in (10, 14, 18):
            pygame.draw.line(s, dk, (rx, 10), (rx, 23), 1)
        pygame.draw.rect(s, (96, 132, 64), (12, 5, 4, 5), border_radius=1)
    elif form == "berry":
        for bx, by in [(11, 14), (17, 14), (14, 18)]:
            pygame.draw.circle(s, col, (bx, by), 4)
            pygame.draw.circle(s, lt, (bx - 1, by - 1), 1)
        pygame.draw.line(s, (90, 160, 70), (14, 11), (14, 6), 1)
    elif form == "pod":
        pygame.draw.arc(s, col, (5, 5, 18, 18), 0.3, 2.5, 4)
        pygame.draw.arc(s, lt, (7, 7, 14, 14), 0.3, 2.5, 1)
    elif form == "cob":
        pygame.draw.ellipse(s, col, (10, 6, 8, 18))
        for yy in range(9, 22, 3):
            pygame.draw.circle(s, lt, (13, yy), 1)
            pygame.draw.circle(s, lt, (15, yy), 1)
        pygame.draw.polygon(s, (108, 168, 78), [(10, 7), (5, 3), (12, 9)])
    elif form == "flower":
        for ang in range(0, 360, 60):
            a = math.radians(ang)
            pygame.draw.circle(s, col, (int(14 + math.cos(a) * 5), int(13 + math.sin(a) * 5)), 3)
        pygame.draw.circle(s, (250, 220, 120), (14, 13), 2)
        pygame.draw.line(s, (90, 160, 70), (14, 18), (14, 24), 2)
    else:  # fruit
        pygame.draw.line(s, (70, 120, 60), (14, 24), (14, 13), 2)
        pygame.draw.circle(s, col, (14, 13), 7)
        pygame.draw.circle(s, lt, (12, 11), 2)
        pygame.draw.ellipse(s, (96, 168, 86), (15, 7, 7, 5))


def _draw_eel(s, col, glow=None):
    """A long sinuous eel body (head at the left) for eels -- not fish-shaped."""
    dk = _dk(col, 0.72)
    lt = _lt(col, 1.2)
    pts = [(4 + i * 2.6, 14 + math.sin(i * 0.95) * 5) for i in range(9)]
    for i in range(len(pts) - 1):
        pygame.draw.line(s, col, pts[i], pts[i + 1], max(2, 7 - i))          # tapering body
    for i in range(len(pts) // 2):
        pygame.draw.line(s, lt, pts[i], pts[i + 1], max(1, 5 - i))           # belly sheen
    for i in range(1, len(pts) - 1, 2):                                      # dorsal fringe
        px, py = pts[i]
        pygame.draw.line(s, dk, (px, py - 3), (px, py - 6), 1)
    hx, hy = int(pts[0][0]), int(pts[0][1])
    pygame.draw.circle(s, col, (hx, hy), 5)                                  # head
    pygame.draw.circle(s, dk, (hx, hy), 5, 1)
    pygame.draw.line(s, dk, (hx - 4, hy + 2), (hx + 1, hy + 2), 1)           # mouth
    pygame.draw.circle(s, (20, 20, 24), (hx - 1, hy - 2), 1)                 # eye
    if glow:
        pygame.draw.circle(s, glow, (hx - 1, hy - 2), 2)
        pygame.draw.circle(s, (240, 240, 255), (hx - 1, hy - 2), 1)


def _draw_fish_item(s, fish):
    col = FISH_LOOK.get(fish, (120, 175, 215))
    if fish == "pufferfish":
        pygame.draw.circle(s, col, (14, 15), 8)
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            pygame.draw.line(s, _dk(col), (14, 15),
                             (int(14 + math.cos(a) * 11), int(15 + math.sin(a) * 11)), 1)
        pygame.draw.circle(s, col, (14, 15), 7)
        pygame.draw.circle(s, (20, 20, 24), (11, 14), 1)
        return
    if fish in ("swordfish", "golden_swordfish"):
        # streamlined body, forked tail, long pointed bill
        pygame.draw.ellipse(s, col, (8, 10, 14, 9))
        pygame.draw.polygon(s, col, [(20, 14), (27, 9), (27, 20)])       # forked tail
        pygame.draw.polygon(s, _dk(col), [(12, 10), (16, 4), (17, 10)])  # dorsal fin
        pygame.draw.line(s, _lt(col), (9, 14), (1, 11), 2)               # sword bill
        pygame.draw.circle(s, (24, 24, 28), (12, 14), 1)                 # eye
        if fish == "golden_swordfish":
            pygame.draw.line(s, (255, 244, 196), (10, 12), (15, 12), 1)  # glint
        return
    if fish == "halibut":
        # flatfish: wide flat oval, both eyes on the up-side, speckled
        pygame.draw.ellipse(s, col, (3, 11, 22, 9))
        pygame.draw.polygon(s, _dk(col), [(24, 12), (27, 15), (24, 19)])     # tail fan
        for px, py in [(8, 13), (13, 12), (17, 14), (11, 16), (19, 17)]:
            pygame.draw.circle(s, _dk(col), (px, py), 1)                     # speckles
        pygame.draw.circle(s, (28, 28, 32), (8, 13), 1)                      # eyes (both on top)
        pygame.draw.circle(s, (28, 28, 32), (11, 13), 1)
        return
    if fish == "coelacanth":
        # chunky body, lobed fins, three-lobed tail, pale flecks
        pygame.draw.ellipse(s, col, (4, 9, 18, 12))
        pygame.draw.polygon(s, col, [(20, 12), (27, 8), (26, 15), (27, 22), (20, 18)])  # tri-lobe tail
        pygame.draw.ellipse(s, _dk(col), (9, 18, 7, 5))     # lobed pectoral fin
        pygame.draw.ellipse(s, _dk(col), (11, 6, 7, 4))     # dorsal lobe
        for px, py in [(8, 12), (13, 11), (16, 15), (11, 16)]:
            pygame.draw.circle(s, _lt(col, 1.5), (px, py), 1)   # pale flecks
        pygame.draw.circle(s, (235, 235, 240), (8, 13), 1)
        pygame.draw.circle(s, (20, 20, 24), (8, 13), 1)
        return
    if fish == "kraken_spawn":
        # squid-like mantle with curling tentacles + big pale eyes
        pygame.draw.ellipse(s, col, (8, 2, 12, 13))                   # mantle (head up)
        pygame.draw.polygon(s, _dk(col), [(8, 4), (14, 0), (20, 4)])  # fin crown
        for i, bx in enumerate((8, 11, 14, 17, 20)):                  # curling tentacles
            curl = 2 if i % 2 == 0 else -2
            pygame.draw.lines(s, _lt(col), False,
                              [(bx, 14), (bx + curl, 19), (bx - curl, 24)], 2)
        pygame.draw.circle(s, (236, 224, 170), (12, 9), 2)           # eyes
        pygame.draw.circle(s, (236, 224, 170), (17, 9), 2)
        pygame.draw.circle(s, (20, 14, 30), (12, 9), 1)
        pygame.draw.circle(s, (20, 14, 30), (17, 9), 1)
        return
    if fish == "maelstrom_ray":
        # manta ray from above: wide wings, whip tail, cephalic head fins
        pygame.draw.polygon(s, col, [(2, 17), (14, 7), (26, 17), (14, 21)])  # diamond wings
        pygame.draw.polygon(s, _dk(col), [(12, 8), (14, 4), (16, 8)])        # head fins
        pygame.draw.line(s, _dk(col), (14, 20), (14, 27), 1)                 # whip tail
        pygame.draw.circle(s, (28, 28, 34), (12, 11), 1)                     # eyes
        pygame.draw.circle(s, (28, 28, 34), (16, 11), 1)
        return
    if fish in ("eel", "void_eel"):
        _draw_eel(s, col, glow=(150, 90, 230) if fish == "void_eel" else None)
        return
    if fish == "the_leviathan":
        # a breaching sea serpent: thick coiling body, back spines, horned/fanged head
        dk = _dk(col, 0.7)
        pts = [(4 + i * 2.7, 16 + math.sin(i * 0.8 + 0.4) * 5) for i in range(9)]
        for i in range(len(pts) - 1):
            pygame.draw.line(s, col, pts[i], pts[i + 1], max(3, 9 - i))
        for i in range(1, 7):                                                # back spines
            px, py = pts[i]
            pygame.draw.polygon(s, dk, [(px - 2, py - 3), (px + 2, py - 3),
                                        (px, py - 3 - (7 - i))])
        tx, ty = int(pts[-1][0]), int(pts[-1][1])                            # tail fluke
        pygame.draw.polygon(s, dk, [(tx, ty), (tx + 5, ty - 5), (tx + 6, ty + 1), (tx + 4, ty + 5)])
        hx, hy = int(pts[0][0]), int(pts[0][1])                              # horned, fanged head
        pygame.draw.circle(s, col, (hx, hy), 6)
        pygame.draw.circle(s, dk, (hx, hy), 6, 1)
        pygame.draw.line(s, dk, (hx - 1, hy - 5), (hx - 4, hy - 11), 2)      # horns
        pygame.draw.line(s, dk, (hx + 2, hy - 5), (hx + 3, hy - 11), 2)
        pygame.draw.line(s, dk, (hx - 5, hy + 3), (hx + 2, hy + 3), 1)       # jaw
        for fxx in (hx - 4, hx - 1, hx + 1):                                 # fangs
            pygame.draw.polygon(s, (240, 240, 235), [(fxx, hy + 3), (fxx + 2, hy + 3), (fxx + 1, hy + 6)])
        pygame.draw.circle(s, (255, 230, 120), (hx - 1, hy - 1), 2)          # glowing eye
        pygame.draw.circle(s, (180, 40, 40), (hx - 1, hy - 1), 1)
        return
    if fish == "unseeing_maw":
        # an eldritch toothed maw with a blind, pupil-less eye -- clearly not a fish
        cx, cy = 14, 15
        dk = _dk(col, 0.6)
        pygame.draw.circle(s, col, (cx, cy), 10)                             # flesh ring
        pygame.draw.circle(s, dk, (cx, cy), 10, 1)
        for ang in range(0, 360, 30):                                        # ring of fangs
            a = math.radians(ang)
            ox, oy = cx + math.cos(a) * 9, cy + math.sin(a) * 9
            ix, iy = cx + math.cos(a) * 5, cy + math.sin(a) * 5
            perp = a + math.pi / 2
            bx, by = math.cos(perp) * 2, math.sin(perp) * 2
            pygame.draw.polygon(s, (240, 236, 228),
                                [(ox + bx, oy + by), (ox - bx, oy - by), (ix, iy)])
        pygame.draw.circle(s, (22, 12, 30), (cx, cy), 5)                     # void gullet
        pygame.draw.circle(s, (200, 190, 214), (cx, cy), 3)                  # blind pale eye
        pygame.draw.line(s, (60, 30, 70), (cx - 2, cy - 2), (cx + 2, cy + 2), 1)  # unseeing slash
        return
    s.blit(fish_icon(col), (2, 6))
    if fish == "mackerel":      # tiger stripes
        for sx in range(7, 19, 3):
            pygame.draw.line(s, _dk(col, 0.7), (sx, 9), (sx, 17), 1)
    elif fish == "abyssal_tuna":  # bioluminescent eye (over the baked eye)
        pygame.draw.circle(s, (120, 240, 230), (6, 12), 2)
        pygame.draw.circle(s, (220, 255, 250), (6, 12), 1)
    elif fish == "catfish":     # whiskers
        pygame.draw.line(s, (60, 50, 40), (6, 15), (2, 13), 1)
        pygame.draw.line(s, (60, 50, 40), (6, 16), (2, 18), 1)


def _draw_food(s, food):
    look = {
        "fried_egg": ("plate", (252, 250, 244), (250, 205, 80)),
        "milk_tea": ("cup", (214, 180, 138), None),
        "veg_stew": ("bowl", (120, 172, 92), (90, 140, 70)),
        "fish_dinner": ("plate", (236, 236, 242), (150, 172, 202)),
        "pumpkin_soup": ("bowl", (236, 150, 58), (210, 120, 40)),
        "fruit_salad": ("bowl", (222, 120, 162), (240, 200, 90)),
        "roast_meat": ("plate", (236, 236, 242), (176, 92, 72)),
        "cheese": ("plate", (244, 214, 110), (224, 188, 84)),
        "veggie_omelette": ("plate", (250, 224, 130), (210, 90, 80)),
        "corn_soup": ("bowl", (240, 208, 110), (250, 235, 150)),
        "steak_plate": ("plate", (236, 236, 242), (150, 84, 64)),
        "pumpkin_pie": ("plate", (228, 150, 70), (244, 222, 170)),
        "egg_custard": ("bowl", (250, 232, 150), (240, 208, 96)),
        "goat_cheese": ("plate", (244, 234, 200), (220, 206, 150)),
    }
    # registry-safe: a dish without bespoke art still draws a generic plate
    kind, base, top = look.get(food, ("plate", (236, 236, 242), (170, 172, 178)))
    if kind == "cup":
        pygame.draw.rect(s, (240, 240, 245), (9, 7, 10, 16), border_radius=2)
        pygame.draw.rect(s, base, (10, 9, 8, 6))
        pygame.draw.arc(s, (240, 240, 245), (16, 10, 7, 9), -1.2, 1.2, 2)  # handle
        return
    if kind == "bowl":
        pygame.draw.ellipse(s, (228, 228, 234), (5, 12, 18, 11))
        pygame.draw.ellipse(s, base, (7, 13, 14, 7))
        if top:
            pygame.draw.circle(s, top, (12, 15), 2)
            pygame.draw.circle(s, top, (17, 16), 2)
        return
    # plate
    pygame.draw.ellipse(s, base, (5, 13, 18, 9))
    pygame.draw.ellipse(s, _dk(base, 0.9), (5, 13, 18, 9), 1)
    if top:
        pygame.draw.circle(s, top, (14, 15), 4)
        pygame.draw.circle(s, _lt(top), (12, 13), 1)


def _draw_mist_mat(s, item_id):
    """Mist City salvage materials (Chat 1 registered them in loot.MATERIALS).
    Base colours come straight from loot.color() so art stays in sync with data:
    rusty browns for scrap, sickly neon for the mutated finds."""
    col = loot.color(item_id) or (150, 150, 150)
    dk = _dk(col, 0.68)
    lt = _lt(col, 1.25)
    if item_id == "scrap_iron":
        plate = [(6, 9), (22, 7), (23, 19), (9, 22)]                  # bent sheet
        pygame.draw.polygon(s, (124, 126, 134), plate)                # bare steel
        pygame.draw.polygon(s, (84, 86, 94), plate, 1)
        pygame.draw.polygon(s, col, [(8, 10), (16, 9), (14, 16), (9, 17)])   # rust bloom
        pygame.draw.polygon(s, dk, [(17, 13), (22, 12), (21, 18), (17, 17)])
        pygame.draw.circle(s, (60, 60, 66), (11, 20), 1)              # rivet holes
        pygame.draw.circle(s, (60, 60, 66), (20, 9), 1)
    elif item_id == "wire":
        for i in range(4):                                            # coiled loops
            pygame.draw.ellipse(s, col, (7, 8 + i * 3, 14, 7), 2)
        pygame.draw.ellipse(s, lt, (7, 8, 14, 7), 1)                  # top sheen
        pygame.draw.line(s, col, (20, 12), (25, 7), 2)                # sprung end
        pygame.draw.circle(s, lt, (25, 7), 1)
    elif item_id == "old_coin":
        pygame.draw.circle(s, col, (14, 15), 9)
        pygame.draw.circle(s, dk, (14, 15), 9, 2)                     # tarnished rim
        pygame.draw.circle(s, dk, (14, 15), 5, 1)                     # worn emblem ring
        pygame.draw.line(s, lt, (10, 11), (13, 9), 1)                 # last of the shine
        pygame.draw.line(s, (96, 78, 44), (9, 19), (19, 21), 1)       # scratches
        pygame.draw.line(s, (96, 78, 44), (16, 8), (21, 13), 1)
    elif item_id == "gear_scrap":
        cx, cy = 14, 15
        for ang in range(0, 360, 45):                                 # teeth
            a = math.radians(ang)
            tx = int(cx + math.cos(a) * 9)
            ty = int(cy + math.sin(a) * 9)
            pygame.draw.rect(s, dk, (tx - 2, ty - 2, 5, 5))
        pygame.draw.circle(s, col, (cx, cy), 8)
        pygame.draw.circle(s, dk, (cx, cy), 8, 1)
        pygame.draw.polygon(s, (0, 0, 0, 0), [(cx, cy), (cx + 13, cy - 8),
                                              (cx + 13, cy + 2)])     # broken-off chunk
        pygame.draw.line(s, dk, (cx, cy), (cx + 9, cy - 6), 1)        # fracture edge
        pygame.draw.line(s, dk, (cx, cy), (cx + 11, cy + 1), 1)
        pygame.draw.circle(s, (0, 0, 0, 0), (cx, cy), 3)              # axle hole
        pygame.draw.circle(s, dk, (cx, cy), 3, 1)
    elif item_id == "old_battery":
        pygame.draw.rect(s, (74, 78, 90), (9, 8, 10, 16), border_radius=2)   # casing
        pygame.draw.rect(s, (104, 108, 120), (9, 8, 10, 5))                  # top band
        pygame.draw.rect(s, (186, 190, 198), (12, 5, 4, 3))                  # + terminal
        pygame.draw.line(s, (210, 214, 222), (12, 11), (16, 11), 1)          # + mark
        pygame.draw.line(s, (210, 214, 222), (14, 9), (14, 13), 1)
        pygame.draw.circle(s, col, (11, 23), 3)                              # acid crust
        pygame.draw.circle(s, lt, (16, 24), 2)
        pygame.draw.circle(s, col, (19, 21), 2)
        pygame.draw.circle(s, lt, (10, 22), 1)
    elif item_id == "mutant_herb":
        glow = pygame.Surface((IC, IC), pygame.SRCALPHA)              # neon aura
        pygame.draw.circle(glow, col + (70,), (14, 14), 11)
        s.blit(glow, (0, 0))
        pygame.draw.line(s, _dk(col, 0.55), (14, 24), (14, 9), 2)     # stem
        pygame.draw.ellipse(s, col, (6, 10, 9, 5))                    # leaves
        pygame.draw.ellipse(s, col, (13, 13, 9, 5))
        pygame.draw.ellipse(s, col, (6, 17, 9, 5))
        pygame.draw.ellipse(s, dk, (13, 13, 9, 5), 1)
        pygame.draw.circle(s, lt, (14, 7), 2)                         # glowing bud
        pygame.draw.circle(s, (235, 255, 238), (14, 7), 1)
    elif item_id == "tainted_crystal":
        glow = pygame.Surface((IC, IC), pygame.SRCALPHA)              # magenta aura
        pygame.draw.circle(glow, col + (70,), (14, 15), 12)
        s.blit(glow, (0, 0))
        shard = [(14, 3), (19, 12), (17, 23), (11, 23), (9, 12)]
        pygame.draw.polygon(s, col, shard)                            # main shard
        pygame.draw.polygon(s, dk, shard, 1)
        pygame.draw.polygon(s, lt, [(14, 3), (16, 11), (14, 20)])     # lit facet
        pygame.draw.polygon(s, col, [(7, 14), (10, 18), (7, 23)])     # side shards
        pygame.draw.polygon(s, col, [(21, 15), (23, 23), (18, 21)])
        pygame.draw.circle(s, (255, 232, 252), (13, 7), 1)            # sparkle


# Extension registry: any module may register an icon painter for a new item id
# instead of growing the if/elif chain below. painter(surface) draws onto a fresh
# transparent IC x IC (28x28) surface. Registered painters win over the chain.
ITEM_PAINTERS = {}


def register_item_icon(item_id, painter):
    ITEM_PAINTERS[item_id] = painter
    _cache.pop(("iicon", item_id), None)


def item_icon(item_id):
    key = ("iicon", item_id)
    if key in _cache:
        return _cache[key]
    s = _ic()
    if item_id in ITEM_PAINTERS:
        ITEM_PAINTERS[item_id](s)
    elif item_id.startswith("seed:"):
        crop = item_id.split(":", 1)[1]
        ccol = CROPS.get(crop, {}).get("color", (150, 180, 90))
        pygame.draw.rect(s, (198, 172, 122), (6, 7, 16, 16), border_radius=3)
        pygame.draw.polygon(s, (236, 222, 182), [(6, 7), (22, 7), (14, 13)])      # folded flap
        pygame.draw.rect(s, (120, 96, 56), (6, 7, 16, 16), 2, border_radius=3)
        pygame.draw.circle(s, ccol, (14, 18), 4)                                  # seed shows crop colour
        pygame.draw.line(s, (80, 140, 64), (14, 14), (14, 18), 1)
    elif item_id in CROPS:
        _draw_crop(s, item_id)
    elif item_id in FISH:
        _draw_fish_item(s, item_id)
    elif item_id in ("copper", "iron", "gold_ore", "iridium_ore"):
        glint, gl_lt = {
            "copper":      ((202, 116, 62),  (238, 168, 110)),
            "iron":        ((176, 182, 196), (226, 230, 238)),
            "gold_ore":    ((240, 198, 70),  (255, 238, 156)),
            "iridium_ore": ((176, 120, 235), (218, 182, 250)),
        }[item_id]
        rock = (98, 98, 110)
        chunk = [(7, 14), (11, 7), (19, 7), (23, 15), (18, 22), (10, 22)]
        pygame.draw.polygon(s, rock, chunk)                       # rough stone matrix
        pygame.draw.polygon(s, _dk(rock, 0.78), chunk, 1)
        pygame.draw.line(s, _lt(rock, 1.2), (11, 8), (18, 8), 1)  # top facet sheen
        if item_id == "iridium_ore":                              # embedded crystals
            for cxx, cyy in [(12, 13), (18, 12), (14, 19)]:
                pygame.draw.polygon(s, glint, [(cxx, cyy - 3), (cxx + 3, cyy),
                                               (cxx, cyy + 3), (cxx - 3, cyy)])
                pygame.draw.line(s, gl_lt, (cxx, cyy - 3), (cxx - 1, cyy), 1)
        else:                                                     # ore nuggets
            for cxx, cyy, r in [(12, 12, 3), (18, 16, 3), (13, 19, 2)]:
                pygame.draw.circle(s, glint, (cxx, cyy), r)
                pygame.draw.circle(s, gl_lt, (cxx - 1, cyy - 1), 1)
        if item_id == "gold_ore":
            pygame.draw.circle(s, (255, 250, 214), (10, 9), 1)    # sparkle
    elif item_id == "stone":
        pygame.draw.circle(s, (120, 120, 132), (14, 15), 9)
        pygame.draw.circle(s, (150, 150, 162), (11, 12), 3)
    elif item_id == "wood":
        pygame.draw.rect(s, WOOD, (5, 9, 18, 11), border_radius=3)
        pygame.draw.circle(s, (110, 75, 45), (8, 14), 3)
        pygame.draw.circle(s, (160, 115, 70), (8, 14), 1)
    elif item_id == "slime_goo":
        pygame.draw.ellipse(s, (96, 200, 120), (5, 11, 18, 13))
        pygame.draw.ellipse(s, (140, 230, 150), (8, 12, 7, 5))
        pygame.draw.circle(s, (30, 60, 40), (12, 18), 1)
        pygame.draw.circle(s, (30, 60, 40), (17, 18), 1)
    elif item_id == "bat_wing":
        mem, strut = (140, 110, 168), (92, 70, 120)
        pts = [(7, 9), (23, 12), (19, 16), (22, 19), (16, 18), (18, 23), (12, 19), (9, 22)]
        pygame.draw.polygon(s, mem, pts)                          # scalloped membrane
        pygame.draw.polygon(s, strut, pts, 1)
        for tip in [(23, 12), (22, 19), (18, 23)]:                # radiating finger bones
            pygame.draw.line(s, strut, (8, 10), tip, 1)
    elif item_id == "bone":
        pygame.draw.line(s, (238, 232, 214), (8, 20), (20, 8), 4)
        for cx, cy in [(8, 20), (20, 8)]:
            pygame.draw.circle(s, (238, 232, 214), (cx, cy), 3)
            pygame.draw.circle(s, (238, 232, 214), (cx + 2, cy + 2), 3)
    elif item_id == "essence":
        pygame.draw.circle(s, (180, 120, 220), (14, 14), 8)
        pygame.draw.circle(s, (225, 190, 245), (14, 14), 4)
        for px, py in [(6, 6), (22, 8), (8, 22)]:
            pygame.draw.circle(s, (210, 170, 240), (px, py), 1)
    elif item_id == "void_essence":
        pygame.draw.circle(s, (70, 44, 110), (14, 14), 8)
        pygame.draw.circle(s, (150, 90, 210), (14, 14), 4)
        pygame.draw.circle(s, (210, 170, 245), (12, 12), 1)
    elif item_id == "egg":
        pygame.draw.ellipse(s, (250, 246, 232), (8, 5, 12, 17))
        pygame.draw.ellipse(s, (224, 214, 192), (8, 5, 12, 17), 1)
        pygame.draw.ellipse(s, (255, 255, 250), (11, 8, 4, 5))
    elif item_id == "milk":
        pygame.draw.rect(s, (246, 246, 250), (9, 6, 10, 17), border_radius=2)
        pygame.draw.rect(s, (120, 170, 215), (9, 6, 10, 5), border_radius=2)
        pygame.draw.rect(s, (90, 96, 110), (9, 6, 10, 17), 1, border_radius=2)
    elif item_id == "duck_egg":
        pygame.draw.ellipse(s, (226, 240, 226), (8, 5, 13, 17))      # pale-green duck egg
        pygame.draw.ellipse(s, (188, 210, 188), (8, 5, 13, 17), 1)
        pygame.draw.ellipse(s, (246, 252, 246), (11, 8, 4, 5))
    elif item_id == "wool":
        for px, py in ((11, 13), (16, 11), (13, 17), (18, 16), (14, 14)):
            pygame.draw.circle(s, (248, 248, 252), (px, py), 5)
        pygame.draw.circle(s, (206, 206, 218), (14, 14), 8, 1)       # soft outline
    elif item_id == "goat_milk":
        pygame.draw.rect(s, (248, 248, 250), (9, 6, 10, 17), border_radius=2)
        pygame.draw.rect(s, (176, 150, 108), (9, 6, 10, 5), border_radius=2)   # tan cap
        pygame.draw.rect(s, (90, 96, 110), (9, 6, 10, 17), 1, border_radius=2)
    elif item_id == "sprinkler":
        pygame.draw.rect(s, (120, 130, 140), (8, 16, 14, 8), border_radius=2)
        pygame.draw.circle(s, (152, 164, 174), (14, 14), 4)
        pygame.draw.circle(s, (92, 102, 112), (14, 14), 4, 1)
        for ddx in (-5, 5):
            pygame.draw.circle(s, (150, 200, 235), (14 + ddx, 9), 1)
    elif item_id == "sprinkler2":
        # premium: brass body + droplets fanned to the diagonals (3x3 reach)
        pygame.draw.rect(s, (168, 134, 70), (8, 16, 14, 8), border_radius=2)
        pygame.draw.circle(s, (212, 178, 96), (14, 14), 4)
        pygame.draw.circle(s, (110, 86, 40), (14, 14), 4, 1)
        pygame.draw.circle(s, (250, 246, 230), (14, 14), 1)
        for ddx, ddy in ((-5, 0), (5, 0), (-4, -4), (4, -4), (0, -5)):
            pygame.draw.circle(s, (150, 200, 235), (14 + ddx, 9 + ddy), 1)
    elif cooking.is_food(item_id):     # registry-driven: any cooking.FOODS dish
        _draw_food(s, item_id)
    elif item_id == "meat":
        pygame.draw.ellipse(s, (196, 96, 86), (6, 9, 16, 12))
        pygame.draw.ellipse(s, (222, 140, 132), (9, 11, 7, 5))
        pygame.draw.rect(s, (238, 232, 214), (4, 13, 4, 4), border_radius=1)   # bone end
    elif item_id == "hide":
        pygame.draw.polygon(s, (158, 120, 86), [(8, 6), (20, 8), (22, 18), (10, 22), (6, 14)])
        pygame.draw.polygon(s, (120, 90, 62), [(8, 6), (20, 8), (22, 18), (10, 22), (6, 14)], 1)
    elif item_id == "pelt":
        pygame.draw.ellipse(s, (134, 112, 96), (6, 7, 16, 15))
        for fx in (10, 14, 18):
            pygame.draw.line(s, (104, 86, 72), (fx, 9), (fx, 20), 1)
    elif item_id == "fish_trophy":
        gold, dk = (240, 205, 90), (190, 150, 60)
        pygame.draw.polygon(s, gold, [(9, 6), (19, 6), (18, 13), (10, 13)])      # cup bowl
        pygame.draw.arc(s, gold, (4, 5, 7, 9), 1.4, 4.2, 2)                      # left handle
        pygame.draw.arc(s, gold, (17, 5, 7, 9), -1.2, 1.6, 2)                    # right handle
        pygame.draw.rect(s, dk, (13, 13, 2, 5))                                  # stem
        pygame.draw.rect(s, gold, (9, 18, 10, 3), border_radius=1)              # base
        pygame.draw.circle(s, (255, 235, 170), (14, 9), 2)                       # shine + tiny fish
    elif item_id in ("scrap_iron", "wire", "old_coin", "gear_scrap",
                     "old_battery", "mutant_herb", "tainted_crystal"):
        _draw_mist_mat(s, item_id)                                               # Mist City salvage
    else:
        pygame.draw.rect(s, (170, 170, 170), (7, 7, 14, 14), border_radius=3)
    _cache[key] = s
    return s


def hotbar_icon(entry):
    kind, name = entry
    return tool_icon(name) if kind == "tool" else item_icon(name)


def draw_tool(surf, name, gx, gy, dx, dy, head=None):
    """Draw the tool live, oriented along (dx, dy): the wooden HANDLE starts at the
    grip (gx, gy, in the hand) and the working HEAD is at the far end. This keeps
    the handle in the hands and the head facing the strike direction for every angle.
    `head` (optional RGB) tints the metal head to show the tool's upgrade tier."""
    px, py = -dy, dx                          # perpendicular to the tool
    steel = head or STEEL

    def P(t, s=0.0):
        return (gx + dx * t + px * s, gy + dy * t + py * s)

    if name == "hoe":
        pygame.draw.line(surf, WOOD, _I(P(0)), _I(P(16)), 3)
        b = P(16)
        pygame.draw.line(surf, steel, _I((b[0] + px * 6, b[1] + py * 6)),
                         _I((b[0] - px * 2 + dx * 3, b[1] - py * 2 + dy * 3)), 5)
    elif name == "pickaxe":
        pygame.draw.line(surf, WOOD, _I(P(0)), _I(P(15)), 3)
        h = P(15)
        pygame.draw.line(surf, steel, _I((h[0] + px * 7, h[1] + py * 7)),
                         _I((h[0] - px * 7, h[1] - py * 7)), 3)
    elif name == "axe":
        pygame.draw.line(surf, WOOD, _I(P(0)), _I(P(18)), 3)
        h = P(17)
        pygame.draw.polygon(surf, steel, [
            _I((h[0] + px, h[1] + py)),
            _I((h[0] + px * 7 + dx * 3, h[1] + py * 7 + dy * 3)),
            _I((h[0] + px * 7 + dx * 7, h[1] + py * 7 + dy * 7)),
            _I((h[0] + dx * 6, h[1] + dy * 6))])
    elif name == "sword":
        pygame.draw.line(surf, steel, _I(P(2)), _I(P(21)), 4)
        g = P(2)
        pygame.draw.line(surf, GOLD_HILT, _I((g[0] + px * 5, g[1] + py * 5)),
                         _I((g[0] - px * 5, g[1] - py * 5)), 3)
    elif name == "fishing_rod":
        pygame.draw.line(surf, WOOD, _I(P(0)), _I(P(22)), 2)
        pygame.draw.line(surf, (215, 215, 220), _I(P(22)), _I(P(22, 6)), 1)
    else:
        pygame.draw.line(surf, WOOD, _I(P(0)), _I(P(18)), 3)


def draw_can(surf, gx, gy, fx, fy, tilt):
    """Watering can held in one hand; the spout points the facing way (fx,fy) and
    water pours toward the tile in front. tilt (0..1) tips it forward to pour."""
    pygame.draw.rect(surf, CAN_BLUE, (int(gx - 6), int(gy - 2), 12, 13), border_radius=3)
    pygame.draw.arc(surf, CAN_BLUE, (int(gx - 6), int(gy - 7), 12, 10), 0.2, 2.9, 3)
    # spout tip in the facing direction (with a little downward droop)
    sx = gx + fx * 10
    sy = gy + fy * 9 + (5 if fy >= 0 else -1)
    pygame.draw.line(surf, CAN_BLUE, (int(gx + fx * 3), int(gy + 1)), (int(sx), int(sy)), 4)
    if tilt > 0.35:
        for i in range(3):
            wx = sx + fx * (3 + i * 3)
            wy = sy + (3 + i * 2 if fy == 0 else (3 + i * 3 if fy > 0 else 0))
            pygame.draw.circle(surf, (150, 200, 235), (int(wx), int(wy)), 1)


def draw_held_item(surf, name, cx, cy, scale=0.72, tilt=0.0):
    """Render any inventory item's icon as a held object, centered at (cx, cy),
    optionally scaled (for bite-shrink) and tilted (radians, for drink/toss).
    Reuses the hotbar icon art so every item is holdable with zero new sprites."""
    ico = item_icon(name)
    w = max(2, int(IC * scale))
    if w != IC:
        ico = pygame.transform.smoothscale(ico, (w, w))
    if tilt:
        ico = pygame.transform.rotate(ico, math.degrees(tilt))
    surf.blit(ico, ico.get_rect(center=(int(cx), int(cy))))
