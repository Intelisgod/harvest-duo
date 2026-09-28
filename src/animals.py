"""Farm livestock: chickens & cows that wander by the coop and give produce daily."""
import math
import random
import pygame
from .settings import TILE
from . import critters

ANIMALS = {
    "chicken": {"label": "Chicken", "cost": 500,  "produce": "egg",       "color": (246, 244, 236), "size": 11},
    "duck":    {"label": "Duck",    "cost": 700,  "produce": "duck_egg",  "color": (250, 246, 224), "size": 11},
    "sheep":   {"label": "Sheep",   "cost": 900,  "produce": "wool",      "color": (246, 246, 250), "size": 14},
    "cow":     {"label": "Cow",     "cost": 1200, "produce": "milk",      "color": (238, 230, 220), "size": 16},
    "goat":    {"label": "Goat",    "cost": 1400, "produce": "goat_milk", "color": (224, 208, 180), "size": 14},
}
# the sprite shape each animal uses (defaults to its own kind in critters._FARM)
PRODUCE_SELL = {"egg": 50, "duck_egg": 70, "wool": 80, "milk": 90, "goat_milk": 130}

# affection: friend points 0..250 -> 0..5 hearts. Petting once a day is the main
# way to raise it; happy animals sometimes give a "large" (double) produce.
MAX_FRIEND = 250
PET_GAIN = 15            # friend points for the first pet of the day
PET_BOTH_BONUS = 6       # extra when the OTHER player pets it too the same day
LARGE_CHANCE_PER_HEART = 0.06   # 5 hearts -> 30% chance of double produce


class Animal:
    def __init__(self, kind, gx, gy, friend=0, has_produce=True):
        a = ANIMALS[kind]
        self.kind = kind
        self.label = a["label"]
        self.produce = a["produce"]
        self.color = a["color"]
        self.size = a["size"]
        self.shape = a.get("shape", kind)
        self.x = gx * TILE + TILE / 2
        self.y = gy * TILE + TILE / 2
        self.home = (self.x, self.y)
        self.friend = friend
        self.has_produce = has_produce
        self.petted_by = []          # player indices who petted it today (reset each morning)
        self.heart_t = 0.0           # >0: show the affection hearts row above it
        self.dirname = "left"
        self.anim_t = 0.0
        self.idle_t = 0.0
        self.moving = False
        self._t = random.random() * 3
        self.vx, self.vy = 0, 0

    def rect(self):
        s = self.size
        return pygame.Rect(self.x - s, self.y - s, s * 2, s * 2)

    @property
    def hearts(self):
        return max(0, min(5, self.friend // 50))

    @property
    def petted(self):
        return bool(self.petted_by)

    @petted.setter
    def petted(self, v):
        self.petted_by = [0] if v else []

    def pet(self, who=0):
        """Pet the animal. The first pet of the day raises affection ("first");
        the other player petting it the same day adds a small bonus ("both").
        Returns None when it no longer counts today."""
        self.heart_t = 2.4
        if who in self.petted_by:
            return None
        self.petted_by.append(who)
        if len(self.petted_by) == 1:
            self.friend = min(MAX_FRIEND, self.friend + PET_GAIN)
            return "first"
        self.friend = min(MAX_FRIEND, self.friend + PET_BOTH_BONUS)
        return "both"

    def produce_qty(self, rng=random):
        """1, or 2 ("large" produce) with a chance that grows with affection."""
        return 2 if rng.random() < self.hearts * LARGE_CHANCE_PER_HEART else 1

    def update(self, dt, area):
        if self.heart_t > 0:
            self.heart_t -= dt
        self.idle_t += dt
        self._t -= dt
        if self._t <= 0:
            self._t = random.uniform(2, 5)
            if random.random() < 0.5:
                self.vx, self.vy = 0, 0
            else:
                ang = random.uniform(0, 6.28)
                self.vx, self.vy = math.cos(ang) * 18, math.sin(ang) * 18
        self.moving = bool(self.vx or self.vy)
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        if abs(nx - self.home[0]) < 110 and abs(ny - self.home[1]) < 90 \
                and not area.is_solid(int(nx // TILE), int(ny // TILE)):
            self.x, self.y = nx, ny
        else:
            self.vx, self.vy = -self.vx, -self.vy
        if self.vx:
            self.dirname = "right" if self.vx > 0 else "left"

    def draw(self, surf, cam):
        cx = self.x - cam.x
        cy = self.y - cam.y
        s = self.size
        flip = -1 if self.dirname == "left" else 1
        bob = 0 if not self.moving else int(math.sin(self.anim_t) * 1)
        if self.heart_t > 1.8:                   # happy little hop right after a pet
            bob -= int(abs(math.sin((2.4 - self.heart_t) * 10)) * 4)
        surf.blit(_shadow(int(s * 1.7)), (cx - s * 0.85, cy + s * 0.5))
        critters.farm_animal(surf, cx, cy + bob, s, flip, self.shape, self.color)
        if self.has_produce:
            iy = int(cy - s - 10 + math.sin(self.idle_t * 3) * 2)
            pygame.draw.circle(surf, (255, 245, 210), (int(cx), iy), 5)
            pygame.draw.circle(surf, (210, 170, 70), (int(cx), iy), 5, 1)
        if self.heart_t > 0:                     # affection row: drawn on top by
            pass                                 # FarmMixin._draw_world_farm_hearts
        elif self.hearts > 0:
            hx = int(cx + s + 2)
            hy = int(cy - s)
            pygame.draw.circle(surf, (230, 90, 110), (hx - 2, hy), 2)
            pygame.draw.circle(surf, (230, 90, 110), (hx + 2, hy), 2)
            pygame.draw.polygon(surf, (230, 90, 110), [(hx - 4, hy + 1), (hx + 4, hy + 1), (hx, hy + 5)])

    def to_dict(self):
        return {"kind": self.kind, "gx": int(self.home[0] // TILE), "gy": int(self.home[1] // TILE),
                "friend": self.friend, "has_produce": self.has_produce,
                "petted_by": sorted(int(i) for i in self.petted_by)}


_heart_cache = {}


def _heart_icon(full):
    key = bool(full)
    if key not in _heart_cache:
        s = pygame.Surface((9, 8), pygame.SRCALPHA)
        col = (236, 88, 118) if full else (120, 96, 110)
        pygame.draw.circle(s, col, (2, 2), 2)
        pygame.draw.circle(s, col, (6, 2), 2)
        pygame.draw.polygon(s, col, [(0, 3), (8, 3), (4, 7)])
        if full:
            s.set_at((2, 1), (255, 200, 214))
        _heart_cache[key] = s
    return _heart_cache[key]


def draw_heart_row(surf, cx, y, friend, alpha=1.0, parchment=False):
    """5 little hearts on a soft pill centred at cx: full per 50 friend points,
    a half heart for the next one once it is half way there.  ``parchment``:
    a cream pill for the (cream) journal page instead of the dark world one.
    Returns the rect drawn (callers reserve it so floating texts avoid it)."""
    halves = max(0, min(10, int(friend) // 25))
    key = ("row", halves, bool(parchment))
    row = _heart_cache.get(key)
    if row is None:
        row = pygame.Surface((5 * 10 + 6, 12), pygame.SRCALPHA)
        if parchment:
            from . import ui_kit as K
            pygame.draw.rect(row, K.WELL, row.get_rect(), border_radius=6)
            pygame.draw.rect(row, K.WELL_LINE, row.get_rect(), 1, border_radius=6)
        else:
            pygame.draw.rect(row, (40, 30, 44, 180), row.get_rect(), border_radius=6)
        for i in range(5):
            x = 4 + i * 10
            n = halves - i * 2
            if n >= 2:
                row.blit(_heart_icon(True), (x, 2))
            else:
                row.blit(_heart_icon(False), (x, 2))
                if n == 1:                           # half heart: left half filled
                    row.blit(_heart_icon(True), (x, 2), pygame.Rect(0, 0, 5, 8))
        _heart_cache[key] = row
    if alpha < 1.0:
        row = row.copy()
        row.set_alpha(int(255 * alpha))
    r = row.get_rect(topleft=(cx - row.get_width() // 2, y))
    surf.blit(row, r.topleft)
    return r


_shadow_cache = {}


def _shadow(w):
    if w not in _shadow_cache:
        s = pygame.Surface((w, max(4, w // 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 80), s.get_rect())
        _shadow_cache[w] = s
    return _shadow_cache[w]
