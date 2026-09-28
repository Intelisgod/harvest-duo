"""Landing a hooked fish: size, records, XP, bonus gold, trophy, treasure, fanfare.

Owner: "Fishing & Foraging" chat.
Related modules: fishing.py (FISH_DATA, tiers, sizes, reel mechanic), critters.py.
(The cast/hook/reel state machine lives in fishing.py; this mixin handles what
happens when a fish is successfully landed, plus a few hooks:)

  * ``_on_update_fishing_buff`` -- feeds each angler's ``p.buff("fishing")`` into
    their FishingState (faster bites, wider bite/reel windows) and animates the
    treasure chests.
  * ``fish_records`` -- {fish_id: {"n": count, "big": cm, "by": name}} (saved) --
    drives "NEW RECORD!" moments and the Collection journal tab.
  * treasure -- ~5% of catches (+skill/luck/fishing buffs) drag up a little sea
    chest that flies to the angler and pops open: gold + a random ore/gem/relic
    from the ``treasure_pool()`` whitelist (never keepsakes or boss drops).
  * hot spots -- 1-2 bubbling patches of castable water per area per day
    (deterministic, no save needed): casting into one bites ~30% faster with
    better rare odds. Rain also makes fish bite a little faster.
  * a bouncing "!" bubble over the angler when a fish bites.
  * fishing side by side (co-op "In Sync") nudges sizes up + treasure odds.
"""
import math
import random

import pygame

from .. import fishing
from .. import loot
from .. import forage_art as FA
from ..progress import XP as SKILL_XP
from ..settings import TILE

_CHEST_FLY = 0.55          # seconds: arc from the water to the angler
_CHEST_OPEN = 0.95         # lid pops at this time
_CHEST_END = 2.6           # animation over (loot was granted at the catch)


def treasure_pool():
    """Items a fished-up chest may hold: the mine ores, the collectible gems and the
    ancient relics -- an explicit whitelist, never "any relic-category item", so
    story keepsakes (Twin Heart Locket), Mist City boss drops (City Key, Cursed
    Gear) and trophies registered later by other domains can't wash up here.
    Returns [(item_id, material_dict)] for ids present in ``loot.MATERIALS``."""
    ids = list(dict.fromkeys(list(loot.ROCK_ORE_ITEM.values())
                             + list(loot.GEMS) + list(loot.RELICS)))
    return [(k, loot.MATERIALS[k]) for k in ids
            if k in loot.MATERIALS and loot.MATERIALS[k].get("sell", 0) >= 50]


class FishingMixin:
    """Resolve a successful catch into inventory, XP, gold and feedback."""

    # ------------------------------------------------------------ state
    def _on_reset_fishing_records(self):
        self.fish_records = {}       # fish_id -> {"n": int, "big": cm, "by": angler}
        self.fish_treasures = 0      # lifetime treasure chests fished up
        self.fish_chests = []        # live chest animations (cosmetic)
        self.fish_spots = []         # today's bubbling hot spots [(gx, gy)] in this area
        self._spot_fx_t = 0.0
        self._cast_prev = {0: "idle", 1: "idle"}

    # ------------------------------------------------------------ hot spots
    def _on_area_enter_fishing_spots(self):
        self._fish_roll_spots()

    def _on_new_day_fishing_spots(self):
        self._fish_roll_spots()

    def _fish_roll_spots(self):
        """Pick today's bubbling spots: castable water (next to walkable ground),
        deterministic per day + area so a reload or re-entry keeps them."""
        area = self.world.area
        self.fish_spots = []
        if area.name in ("home", "mine", "coop", "temple"):
            return
        cands = []
        for gy in range(area.h):
            for gx in range(area.w):
                if not area.is_water(gx, gy):
                    continue
                if any(not area.is_solid(gx + dx, gy + dy)
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    cands.append((gx, gy))
        if not cands:
            return
        t = self.time
        rng = random.Random(f"spots-{t.year}-{t.season_idx}-{t.day}-{area.name}")
        self.fish_spots = rng.sample(cands, min(2 if len(cands) > 40 else 1, len(cands)))

    def _fish_in_spot(self, p):
        if not self.fish_spots:
            return False
        tx, ty = p.target_tile()
        return any(abs(tx - sx) <= 1 and abs(ty - sy) <= 1 for sx, sy in self.fish_spots)

    def _world_sprites_fishing_spots(self):
        if not self.fish_spots:
            return ()
        fr = _spot_frame(int(self.anim_t * 5) % 3)
        out = []
        for (sx, sy) in self.fish_spots:
            x = sx * TILE + TILE / 2 - fr.get_width() / 2 - self.cam.x
            y = sy * TILE + TILE / 2 - fr.get_height() / 2 - self.cam.y
            out.append((sy * TILE - TILE, fr, (x, y)))
        return out

    def _on_save_fishing_records(self):
        recs = {}
        for fid, r in self.fish_records.items():
            recs[fid] = {"n": int(r.get("n", 0)), "big": int(r.get("big", 0)),
                         "by": str(r.get("by", ""))}
        return {"fish_records": recs, "fish_treasures": int(self.fish_treasures)}

    def _on_load_fishing_records(self, d):
        self.fish_records = {}
        if "fish_records" not in d:
            # a save from before records existed: credit the fish already in the
            # players' bags so the Collection page doesn't start from zero
            for p in getattr(self, "players", ()):
                inv = getattr(p, "inv", None)
                for fid in fishing.FISH_DATA:
                    n = inv.count(fid) if inv else 0
                    if n > 0:
                        r = self.fish_records.setdefault(fid, {"n": 0, "big": 0, "by": ""})
                        r["n"] += int(n)
        raw = d.get("fish_records") or {}
        if isinstance(raw, dict):
            for fid, r in raw.items():
                if not isinstance(r, dict):
                    continue
                try:
                    self.fish_records[str(fid)] = {"n": int(r.get("n", 0)), "big": int(r.get("big", 0)),
                                                   "by": str(r.get("by", ""))}
                except (TypeError, ValueError):
                    continue
        try:
            self.fish_treasures = int(d.get("fish_treasures", 0) or 0)
        except (TypeError, ValueError):
            self.fish_treasures = 0

    def _on_area_enter_fishing_chests(self):
        self.fish_chests = []        # loot was already granted; just drop the show

    # ------------------------------------------------------------ per frame
    def _on_update_fishing_buff(self, dt):
        rain = 0.15 if getattr(self, "weather", "") in ("rain", "storm") else 0.0   # fish bite in the rain
        for i, p in enumerate(self.players):
            st = self.fishing.get(i)
            if st is None:
                continue
            st.bonus = (p.buff("fishing") if hasattr(p, "buff") else 0.0) + rain
            st.hotspot = self._fish_in_spot(p)
            if st.state == "casting" and self._cast_prev.get(i) == "idle" and st.hotspot:
                bx, by = p.x + p.fx * TILE, p.y + p.fy * TILE
                self._popup(bx, by - 18, "Hot spot!", (160, 230, 255))
                self.parts.bubble(bx, by, n=8)
            if st.state == "bite" and self._cast_prev.get(i) != "bite":
                self.audio.play("bite")                  # no-op until Core adds the SFX
                self.parts.splash(p.x + p.fx * TILE, p.y + p.fy * TILE, n=6)
            self._cast_prev[i] = st.state
        if self.fish_spots:                              # the spots fizz and ripple
            self._spot_fx_t -= dt
            if self._spot_fx_t <= 0:
                self._spot_fx_t = 0.4
                for (sx, sy) in self.fish_spots:
                    wx = sx * TILE + TILE / 2 + random.uniform(-10, 10)
                    wy = sy * TILE + TILE / 2 + random.uniform(-6, 6)
                    if -40 < wx - self.cam.x < 1320 and -40 < wy - self.cam.y < 760:
                        self.parts.bubble(wx, wy, n=2, color=(214, 240, 255))
                        if random.random() < 0.3:
                            self.parts.ripple(wx, wy)
        if self.fish_chests:
            for c in self.fish_chests:
                c["t"] += dt
                if not c["opened"] and c["t"] >= _CHEST_OPEN:
                    c["opened"] = True
                    self._fish_chest_open(c)
                elif not c["landed"] and c["t"] >= _CHEST_FLY:
                    c["landed"] = True
                    self.parts.dust(c["x1"], c["y1"] + 6, n=6, color=(200, 180, 140))
                    self.add_shake(1.5)
            self.fish_chests = [c for c in self.fish_chests if c["t"] < _CHEST_END]

    # ------------------------------------------------------------ landing
    def _land_fish(self, p, caught, cx, cy):
        """Grant a caught fish plus tier-scaled XP, bonus gold and trophy loot,
        roll its size (records!) and maybe a treasure chest."""
        import random as _r
        tier = fishing.tier_of(caught)
        color = fishing.TIER_COLOR.get(tier, (150, 200, 240))
        name = fishing.display_name(caught)
        idx = self.players.index(p)
        fort = self.fortune.get(idx)
        everyday = tier in ("common", "uncommon")
        # bad luck can make an everyday catch slip off the hook (specials are safe)
        if fort == "unlucky" and everyday and _r.random() < 0.35:
            self.parts.sparkle(cx, cy, n=5, color=(150, 110, 180))
            self._popup(cx, cy - 8, "slipped!", (180, 130, 210))
            self.fishing[idx].message = f"Bad luck -- the {name} slipped off the hook!"
            return
        # quantity bonus only for the everyday fish (specials are always single)
        if everyday:
            dbl = min(0.5, p.skills.fishing_skill * 0.05)
            if fort == "lucky":
                dbl = max(dbl, 0.6)                 # good luck = bumper haul
            qty = 2 if _r.random() < dbl else 1
        else:
            qty = 1
        p.inv.add(caught, qty)
        # base + tier XP
        self._grant_xp(p, "fishing", SKILL_XP["fish"] + fishing.TIER_XP_BONUS.get(tier, 0))
        # bonus gold on the spot
        gbonus = fishing.TIER_GOLD_BONUS.get(tier, 0)
        if gbonus:
            self.gold += gbonus
        # ---- size + records ----
        skill = p.skills.fishing_skill
        luck = p.buff("luck") if hasattr(p, "buff") else 0.0
        fbuf = p.buff("fishing") if hasattr(p, "buff") else 0.0
        together = bool(getattr(self, "in_sync", False))     # fishing side by side
        size = fishing.roll_size(caught, skill, fbuf + luck * 0.5 + (0.2 if together else 0.0))
        if together and hasattr(self.parts, "heart_float"):
            self.parts.heart_float(p.x, p.y - 34)
        rec = self.fish_records.get(caught)
        first = not rec or rec.get("n", 0) <= 0
        prev_big = int(rec.get("big", 0)) if rec else 0
        rec = self.fish_records.setdefault(caught, {"n": 0, "big": 0, "by": ""})
        rec["n"] = int(rec.get("n", 0)) + qty
        record = size > prev_big
        if record:
            rec["big"] = size
            rec["by"] = p.name
        adj = fishing.size_label(caught, size)
        wb = 0
        if fishing.size_frac(caught, size) >= 0.85:          # a whopper sells a bit better
            wb = max(5, int(fishing.FISH.get(caught, 30) * 0.2))
            self.gold += wb
        # one size line + one gold line (they used to be 3-4 stacked popups)
        if record and not first:
            self._popup(cx, cy - 30, f"NEW RECORD!  {size} cm", (255, 226, 120))
        else:
            self._popup(cx, cy - 30, f"{size} cm" + (f" - {adj}" if adj else ""), _lift(color))
        if gbonus or wb:
            self._popup(cx, cy - 8, f"+{gbonus + wb}g" + ("  whopper!" if wb else ""), (255, 220, 120))
        st = self.fishing[idx]
        # feedback scaled by how special the catch is
        if fishing.is_special(caught):                 # legendary / leviathan
            p.inv.add("fish_trophy", 1)                # mountable trophy / brag item
            self.parts.sparkle(cx, cy, color=color)
            self.parts.sparkle(cx, cy - 6, color=(255, 255, 255))
            self.add_shake(5)
            self.audio.play("catch")
            verb = "LEVIATHAN" if tier == "leviathan" else "LEGENDARY"
            self.fishing_banner = (f"{verb}!  {name}  {size} cm", color, 3.0)
            self.ui.log(f"{verb} CATCH! Landed the {name} ({size} cm)! +{gbonus}g, trophy earned!")
        else:
            self.parts.sparkle(cx, cy, color=color)
            self.audio.play("catch")
            if qty > 1:
                st.message = f"Big haul! {name} x{qty}  ({size} cm)"
            else:
                st.message = f"Landed {name}!  {size} cm" + (f" -- {adj}" if adj else "")
        # ---- collection moments ----
        toast = getattr(self, "toast", None)
        if first:
            if toast:
                toast("New Fish!", f"{name} -- {size} cm", icon=caught, color=color)
        elif record:                                   # (its popup is the size line above)
            self.ui.log(f"{p.name} set a new {name} record: {size} cm!")
            # the big fanfare once a species has a little history (early records
            # come thick and fast -- a popup is enough for those)
            if rec["n"] - qty >= 3:
                burst = getattr(self.parts, "star_burst", None)
                if burst:
                    burst(cx, cy - 10, color=(255, 226, 120))
                else:
                    self.parts.sparkle(cx, cy - 10, n=14, color=(255, 226, 120))
                self.audio.play("achievement")
                if toast:
                    toast("NEW RECORD!", f"{name} -- {size} cm (was {prev_big} cm)",
                          icon=caught, color=(255, 214, 110))
            else:
                self.parts.sparkle(cx, cy - 10, n=8, color=(255, 226, 120))
        self.emit("fish_caught", p=p, fish=caught, size=size, qty=qty, record=record)
        if first and hasattr(self, "_coll_check_milestones"):
            self._coll_check_milestones()
        # ---- treasure! ----
        if _r.random() < fishing.treasure_chance(skill, luck + (0.25 if together else 0.0), fbuf):
            self._fish_treasure(p, cx, cy)

    # ------------------------------------------------------------ treasure
    def _fish_treasure_item(self, rng=random):
        """A random valuable from the treasure whitelist (ores / gems / ancient relics)."""
        pool = treasure_pool()
        if not pool:
            return "copper", 2
        weights = [1.0 / max(1.0, v["sell"]) ** 0.7 for _, v in pool]   # pricier = rarer
        k, v = rng.choices(pool, weights=weights, k=1)[0]
        qty = rng.randint(1, 3) if v["sell"] < 150 else 1
        return k, qty

    def _fish_treasure(self, p, cx, cy, force=False):
        """Grant the chest's loot now and start the little opening show."""
        skill = p.skills.fishing_skill
        gold = random.randint(30, 80) + skill * 8
        item, qty = self._fish_treasure_item()
        self.gold += gold
        p.inv.add(item, qty)
        self.fish_treasures += 1
        side = 1 if cx >= p.x else -1
        self.fish_chests.append({
            "x0": cx, "y0": cy, "x1": p.x + side * 30, "y1": p.y + 8, "t": 0.0,
            "gold": gold, "item": item, "qty": qty, "landed": False, "opened": False,
            "who": p.name})
        self.parts.splash(cx, cy, n=12)
        self.audio.play("splash_big")
        self.ui.log(f"{p.name} fished up a treasure chest!")

    def _fish_chest_open(self, c):
        x, y = c["x1"], c["y1"] - 10
        coins = getattr(self.parts, "coin_burst", None)
        if coins:
            coins(x, y, n=10)
        self.parts.sparkle(x, y, n=16, color=(255, 226, 120))
        self.parts.sparkle(x, y - 4, n=6, color=(255, 255, 255))
        self.audio.play("unlock")
        self.audio.play("coin")
        lab = loot.label(c["item"])
        # one line for the whole chest (gold + item used to stack on each other)
        self._popup(x, y - 30, f"+{c['gold']}g  +{lab}" + (f" x{c['qty']}" if c["qty"] > 1 else ""),
                    (255, 220, 120))
        toast = getattr(self, "toast", None)
        if toast:
            toast("Treasure!", f"+{c['gold']}g and {lab}" + (f" x{c['qty']}" if c["qty"] > 1 else ""),
                  icon=c["item"], color=(255, 214, 110))

    def _draw_world_fishing_bite(self):
        """A bouncing '!' over the angler's head the moment a fish bites."""
        for i, p in enumerate(self.players):
            st = self.fishing.get(i)
            if st is None or st.state != "bite":
                continue
            special = bool(st.fish) and fishing.is_special(st.fish)
            spr = _bite_bubble(special)
            bounce = abs(math.sin(self.anim_t * 12)) * 5
            self.screen.blit(spr, (int(p.x - spr.get_width() / 2 - self.cam.x),
                                   int(p.y - TILE * 1.95 - bounce - self.cam.y)))

    def _draw_world_fishing_chests(self):
        if not self.fish_chests:
            return
        cam = self.cam
        scr = self.screen
        for c in self.fish_chests:
            t = c["t"]
            if t < _CHEST_FLY:                               # arcing out of the water
                k = t / _CHEST_FLY
                x = c["x0"] + (c["x1"] - c["x0"]) * k
                y = c["y0"] + (c["y1"] - c["y0"]) * k - math.sin(k * math.pi) * 56
                spr = pygame.transform.rotate(FA.chest(False), math.sin(k * 7) * 18)
            elif t < _CHEST_OPEN:                            # landed: squash + wobble
                k = (t - _CHEST_FLY) / (_CHEST_OPEN - _CHEST_FLY)
                x, y = c["x1"], c["y1"]
                sq = 1.0 + math.sin(k * math.pi * 3) * 0.12 * (1 - k)
                base = FA.chest(False)
                spr = pygame.transform.smoothscale(
                    base, (int(base.get_width() * sq), int(base.get_height() / sq)))
            else:                                            # open, loot floats up
                k = (t - _CHEST_OPEN) / (_CHEST_END - _CHEST_OPEN)
                x, y = c["x1"], c["y1"]
                spr = FA.chest(True)
                if k > 0.7:
                    spr = spr.copy()
                    spr.set_alpha(int(255 * (1 - (k - 0.7) / 0.3)))
                ic = _item_icon(c["item"])
                if ic is not None:
                    rise = 34 * min(1.0, k * 2.2)
                    ic = ic.copy() if k > 0.6 else ic
                    if k > 0.6:
                        ic.set_alpha(int(255 * max(0.0, 1 - (k - 0.6) / 0.4)))
                    scr.blit(ic, (int(x - 14 - cam.x), int(y - 30 - rise - cam.y)))
            scr.blit(FA.ground_shadow(), (int(c["x1"] - 11 - cam.x), int(c["y1"] + 6 - cam.y)))
            scr.blit(spr, (int(x - spr.get_width() / 2 - cam.x), int(y - spr.get_height() + 8 - cam.y)))


_SPOT = {}
_BITE = {}


def _bite_bubble(special=False):
    """Little speech bubble with a '!' (gold rim for legendary bites)."""
    if special not in _BITE:
        s = pygame.Surface((22, 26), pygame.SRCALPHA)
        rim = (236, 176, 60) if special else (90, 70, 100)
        pygame.draw.polygon(s, (255, 255, 255), [(8, 19), (14, 19), (11, 25)])
        pygame.draw.circle(s, (255, 255, 255), (11, 11), 10)
        pygame.draw.circle(s, rim, (11, 11), 10, 2)
        pygame.draw.line(s, rim, (8, 20), (11, 25), 2)
        pygame.draw.line(s, rim, (14, 20), (11, 25), 2)
        pygame.draw.polygon(s, (255, 255, 255), [(9, 18), (13, 18), (11, 22)])   # seamless tail join
        mark = (230, 80, 70) if not special else (220, 140, 30)
        pygame.draw.rect(s, mark, (9, 4, 5, 10), border_radius=2)
        pygame.draw.circle(s, mark, (11, 17), 2)
        _BITE[special] = s
    return _BITE[special]


def _spot_frame(i):
    """Fizzing patch of bubbles on the water (3 cached frames)."""
    if i not in _SPOT:
        s = pygame.Surface((52, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (40, 70, 120, 60), (2, 6, 48, 20))            # dark shoal below
        pygame.draw.ellipse(s, (226, 246, 255, 80), (6, 7, 40, 16), 2)       # foam ring
        rnd = random.Random(i * 7 + 3)
        for _ in range(10):
            x, y = rnd.randint(9, 43), rnd.randint(8, 22)
            r = rnd.choice((1, 2, 2, 3))
            pygame.draw.circle(s, (240, 252, 255, 230), (x, y), r, 1)
            pygame.draw.circle(s, (255, 255, 255, 240), (x - 1, y - 1), 1)
        _SPOT[i] = s
    return _SPOT[i]


def _lift(c):
    return tuple(min(255, int(v * 0.7 + 90)) for v in c[:3])


def _item_icon(item_id):
    try:
        from .. import assets
        return assets.item_icon(item_id)
    except Exception:
        return None
