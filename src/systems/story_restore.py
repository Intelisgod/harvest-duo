"""Story domain (Chat 4) part 2: Valley Restoration bundles + festival games.

Mixed into StoryMixin (systems/story_system.py), so every hook here is found by
the hook bus exactly like the ones in story_system.

  * RestorationMixin   -- the town restoration board (area.restoration_board,
    placed by World; a runtime fallback spot is used until it lands) opens the
    custom state "restoration": 7 bundles whose slots are derived from the live
    item registries. Completing all of them raises a golden statue in town.
  * FestivalGamesMixin -- Spring Flower Festival "Egg Hunt" (60 s, 18 eggs, P1 vs
    P2 score) at the festival stall, and Winter "Lantern Night" on the beach
    (both players release a lantern together -> floating lights).
"""
import math
import random
import pygame
from ..settings import (TILE, SCREEN_W, SCREEN_H, WHITE, GOLD, P1_KEYS, P2_KEYS,
                        AREA_TOWN, AREA_BEACH)
from .. import story_art as ART
from .. import story_data as SD
from .. import festival
from .. import ui_kit as K


def speaker_tag(surf, name, topleft, maxw=220):
    """The wooden speaker name tag shared by the dialogue box (UI.draw_dialogue)
    and the heart-event text box: shadowed wooden pill, sheen strip, cream name
    centred in a font that fits ``maxw``.  Returns its rect."""
    tf = K.fit_font(name, maxw, (17, 16, 15, 14), bold=True)
    name = K.ellipsize(tf, name, maxw)
    tag = pygame.Rect(topleft[0], topleft[1], tf.size(name)[0] + 32, 30)
    K.pill(surf, tag.move(0, 2), (60, 36, 28), alpha=90)                  # soft shadow
    K.pill(surf, tag, K.WOOD, K.WOOD_DK)
    pygame.draw.rect(surf, (168, 120, 84), (tag.x + 10, tag.y + 4, tag.w - 20, 2),
                     border_radius=1)                                      # sheen
    K.blit_text(surf, tf, name, K.CREAM_HI, tag.center)
    return tag


def _continue_text():
    """The standard continue line, from the real action keys (follows rebinding;
    reads exactly ui_kit.CONTINUE_HINT with the default keys)."""
    from ..ui import key_label
    return f"{key_label(P1_KEYS['action'])} / {key_label(P2_KEYS['action'])}  -  continue"


# ============================================================== bundle defs
def _qty_for(value):
    if value <= 50:
        return 5
    if value <= 120:
        return 3
    return 1


def bundle_defs():
    """Bundle definitions derived from the registries RIGHT NOW (only ids that
    exist). Progress is keyed by item id, so a registry change never corrupts a
    save -- a vanished slot simply stops being shown."""
    from .. import loot
    from ..crops import CROPS
    from ..fishing import FISH, FISH_DATA
    try:
        from ..cooking import FOODS
    except Exception:
        FOODS = {}
    M = loot.MATERIALS

    def season_slots(season):
        cs = sorted((c for c, d in CROPS.items() if d.get("season") == season),
                    key=lambda c: CROPS[c]["sell"])
        return [(c, _qty_for(CROPS[c]["sell"])) for c in cs[:4]]

    def pick(ids, n):
        return [i for i in ids if SD.item_exists(i)][:n]

    fish = pick(["sardine", "carp", "tuna", "bass", "catfish", "halibut"], 4)
    if len(fish) < 4:
        fish = (fish + sorted(FISH, key=lambda f: FISH[f]))[:4]
    angler = [(f, 2 if FISH.get(f, 0) <= 60 else 1) for f in fish]

    miner = [(i, q) for i, q in (("copper", 10), ("iron", 5), ("gold_ore", 3)) if i in M]
    gems = sorted((k for k, v in M.items() if v.get("cat") in ("gem", "gems")),
                  key=lambda k: M[k]["sell"])
    if gems:
        miner.append((gems[0], 1))
    elif "essence" in M:
        miner.append(("essence", 3))

    forage = sorted((k for k, v in M.items() if v.get("cat") in ("forage", "flower")),
                    key=lambda k: M[k]["sell"])[:4]
    forager = [(k, 3) for k in forage] if len(forage) >= 3 else \
        [(i, q) for i, q in (("wood", 20), ("hide", 2), ("meat", 2), ("pelt", 1)) if i in M]

    chef = [(f, 1) for f in ("veg_stew", "fish_dinner", "fruit_salad", "pumpkin_soup")
            if f in FOODS]

    together = [(i, q) for i, q in (("wood", 10), ("stone", 10), ("copper", 3),
                                     ("parsnip", 3)) if SD.item_exists(i)]
    defs = [
        {"id": "spring", "name": "Spring Harvest", "color": (150, 214, 120),
         "desc": "Fresh spring crops to wake the valley's fields.",
         "slots": season_slots("Spring"),
         "reward": {"gold": 300, "items": [("sprinkler2", 4)]}},
        {"id": "summer", "name": "Summer Bounty", "color": (246, 196, 90),
         "desc": "Sun-ripe produce for the town market.",
         "slots": season_slots("Summer"),
         "reward": {"gold": 400, "items": [("seed:melon", 6)]}},
        {"id": "angler", "name": "Angler's Catch", "color": (110, 170, 230),
         "desc": "Fish from pond and sea to restore the old pier.",
         "slots": angler, "reward": {"gold": 500, "items": [("fish_dinner", 3)]}},
        {"id": "miner", "name": "Miner's Haul", "color": (196, 150, 110),
         "desc": "Ores and gems to rebuild the forge.",
         "slots": miner, "reward": {"gold": 600, "items": [("iridium_ore", 2)]}},
        {"id": "forager", "name": "Forager's Basket", "color": (130, 190, 140),
         "desc": "Gifts of the wild to replant the meadow.",
         "slots": forager, "reward": {"gold": 400, "items": [("fruit_salad", 2),
                                                             ("seed:crocus", 5)]}},
        {"id": "chef", "name": "Chef's Table", "color": (236, 150, 120),
         "desc": "Home-cooked dishes for the valley feast.",
         "slots": chef, "reward": {"gold": 500, "items": [("pumpkin_pie", 3)]}},
        {"id": "together", "name": "Together", "color": (240, 140, 170),
         "desc": "EACH farmer must bring their share -- side by side.",
         "slots": together, "together": True,
         "reward": {"gold": 1000, "items": [("twin_locket", 1)]}},
    ]
    return [d for d in defs if d["slots"]]


GRAND_GOLD = 2000

# what each completed bundle restores in the world: (area, prop kind, nominal tile)
RESTORE_DECOR = {
    "spring": [(AREA_TOWN, "restore_planter", (12, 12)), (AREA_TOWN, "restore_planter", (26, 13))],
    "summer": [(AREA_TOWN, "restore_fruitcart", (13, 15))],
    "angler": [(AREA_BEACH, "restore_fishrack", (23, 17))],
    "miner": [(AREA_TOWN, "restore_lamp", (2, 27)), (AREA_TOWN, "restore_lamp", (5, 27))],
    "forager": [(AREA_TOWN, "restore_birdbath", (28, 15))],
    "chef": [(AREA_TOWN, "restore_picnic", (23, 21))],
    "together": [(AREA_TOWN, "restore_heart_arch", (20, 3))],
}
DECOR_WALKABLE = {"restore_heart_arch"}          # you stroll under the arch
DECOR_NAMES = {"spring": "flower planters bloom on the square",
               "summer": "a fruit cart opens in town",
               "angler": "a fish-drying rack returns to the pier",
               "miner": "lamps light the mine entrance",
               "forager": "a bird bath sparkles in town",
               "chef": "a picnic table appears by the pond",
               "together": "a heart arch now welcomes you from the farm road"}


class RestorationMixin:
    """Valley Restoration: bundles at the town board (state "restoration")."""

    def _on_reset_story_restore(self):
        self.story_bundles = {}          # bundle id -> {item or "item|pidx": qty}
        self.story_bundles_done = set()  # bundle ids completed
        self.story_restored = False      # grand celebration happened
        self._rs = {"sel": 0, "slot": 0, "msg": "", "flash": 0.0, "fx": [], "t": 0.0}
        self._story_celebrate = 0.0
        self._story_defs = None

    def _on_save_story_restore(self):
        return {"story_bundles": {k: dict(sorted(v.items()))
                                  for k, v in sorted(self.story_bundles.items())},
                "story_bundles_done": sorted(self.story_bundles_done),
                "story_restored": bool(self.story_restored)}

    def _on_load_story_restore(self, d):
        raw = d.get("story_bundles", {}) or {}
        self.story_bundles = {str(k): {str(i): int(q) for i, q in (v or {}).items()}
                              for k, v in raw.items() if isinstance(v, dict)}
        self.story_bundles_done = set(d.get("story_bundles_done", []) or [])
        self.story_restored = bool(d.get("story_restored", False))
        self._story_defs = None
        self._story_place_decor()
        self._story_place_statue()

    def _story_bundles(self):
        if self._story_defs is None:
            self._story_defs = bundle_defs()
        return self._story_defs

    # ---- where the board is (World's attr, or a runtime fallback) ----
    def _story_board(self):
        town = self.world.areas.get(AREA_TOWN)
        if town is None:
            return None
        rb = getattr(town, "restoration_board", None)
        if rb:
            return tuple(rb)
        # World hasn't placed it yet: a runtime fallback beside the quest hall
        fb = getattr(town, "_story_board_fallback", None)
        if fb is None:
            cands = [(28, 9), (29, 9), (27, 10), (18, 9), (15, 9)]
            fb = next((c for c in cands if not town.is_solid(*c)
                       and c != getattr(town, "festival_stall", None)
                       and c != getattr(town, "quest_board", None)), (28, 9))
            town._story_board_fallback = fb
            if not any(k == "restoration_board" for k, *_ in town.props):
                town.props = list(town.props) + [("restoration_board", fb[0], fb[1])]
            town.solid_extra.add(fb)
        return fb

    def _story_place_statue(self):
        """The golden statue (all bundles done) lives in town; the world is
        rebuilt on reset/load so it is re-added here (idempotent)."""
        if not getattr(self, "story_restored", False):
            return
        town = self.world.areas.get(AREA_TOWN)
        if town is None or any(k == "golden_statue" for k, *_ in town.props):
            return
        b = self._story_board() or (20, 16)
        spot = None
        for dx, dy in ((2, 0), (-2, 0), (3, 1), (-3, 1), (0, 3), (4, 0), (-4, 0)):
            c = (b[0] + dx, b[1] + dy)
            if self._story_free(town, *c) and c != getattr(town, "festival_stall", None):
                spot = c
                break
        spot = spot or (19, 17)
        town.props = list(town.props) + [("golden_statue", spot[0], spot[1])]
        town.solid_extra.add(spot)
        town._story_statue = spot

    def _story_place_decor(self):
        """Each completed bundle visibly restores a corner of the valley
        (planters, fruit cart, mine lamps, bird bath, picnic table, pier fish
        rack, a heart arch at the farm road). Derived from story_bundles_done,
        so it is re-added after every reset/load (idempotent per area)."""
        for bid in sorted(self.story_bundles_done):
            for area_name, kind, tile in RESTORE_DECOR.get(bid, ()):
                a = self.world.areas.get(area_name)
                if a is None:
                    continue
                placed = a.__dict__.setdefault("_story_decor", set())
                if (kind, tile) in placed:
                    continue
                placed.add((kind, tile))
                spot = self._story_decor_spot(a, kind, tile)
                if spot is None:
                    continue
                a.props = list(a.props) + [(kind, spot[0], spot[1])]
                if kind not in DECOR_WALKABLE:
                    a.solid_extra.add(spot)

    def _story_decor_spot(self, a, kind, tile):
        if kind in DECOR_WALKABLE:                    # the arch: exact spot, 2 tiles wide
            ok = all(not a.is_solid(tile[0] + dx, tile[1]) for dx in (0, 1))
            return tile if ok else None
        taken = {(gx, gy) for _k, gx, gy in a.props}
        taken |= {(gx, gy) for _n, gx, gy in getattr(a, "npc_spawns", ())}
        for attr in ("quest_board", "shop", "restoration_board", "donation_box"):
            v = getattr(a, attr, None)
            if v:
                taken.add(tuple(v))
        fs = getattr(a, "festival_stall", None)
        tx, ty = tile
        for r in range(0, 4):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    c = (tx + dx, ty + dy)
                    if c in taken or not self._story_free(a, *c):
                        continue
                    if fs and abs(c[0] - fs[0]) <= 3 and abs(c[1] - fs[1]) <= 2:
                        continue
                    return c
        return None

    def _on_area_enter_story_restore(self):
        self._story_place_decor()
        if self.world.current == AREA_TOWN:
            self._story_board()
            self._story_place_statue()

    def _interact_early_30_story_board(self, idx, p):
        if self.world.current != AREA_TOWN:
            return False
        b = self._story_board()
        if not b:
            return False
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        if abs(pgx - b[0]) <= 1 and abs(pgy - b[1]) <= 1:
            self._story_open_restoration(idx)
            return True
        return False

    def _story_open_restoration(self, idx=0):
        self._story_defs = None                 # re-derive (new registry items)
        self.story_board_intro = True           # found it: no "board is up" hint needed
        self._rs.update({"msg": "Bring goods to restore the valley!", "fx": [], "t": 0.0,
                         "who": idx})
        self.state = "restoration"
        self.audio.play("page")
        self.audio.play("ui_select")

    # ---- progress helpers ----
    def _story_have(self, b, item, pidx=None):
        prog = self.story_bundles.get(b["id"], {})
        if pidx is None:
            return int(prog.get(item, 0))
        return int(prog.get(f"{item}|{pidx}", 0))

    def _story_slot_done(self, b, item, qty):
        if b.get("together"):
            return all(self._story_have(b, item, i) >= qty for i in range(2))
        return self._story_have(b, item) >= qty

    def _story_bundle_frac(self, b):
        tot = got = 0
        for item, qty in b["slots"]:
            if b.get("together"):
                tot += qty * 2
                got += sum(min(qty, self._story_have(b, item, i)) for i in range(2))
            else:
                tot += qty
                got += min(qty, self._story_have(b, item))
        return 1.0 if b["id"] in self.story_bundles_done else (got / tot if tot else 0.0)

    def _story_deposit(self, pidx, all_slots=False):
        bs = self._story_bundles()
        if not bs:
            return
        rs = self._rs
        b = bs[rs["sel"] % len(bs)]
        if b["id"] in self.story_bundles_done:
            rs["msg"] = f"{b['name']} is already complete!"
            self.audio.play("ui_move")
            return
        slots = list(range(len(b["slots"]))) if all_slots else [rs["slot"] % len(b["slots"])]
        moved = 0
        last = None
        p = self.players[pidx] if pidx < len(self.players) else self.players[0]
        for si in slots:
            item, qty = b["slots"][si]
            prog = self.story_bundles.setdefault(b["id"], {})
            if b.get("together"):
                key = f"{item}|{pidx}"
                need = qty - int(prog.get(key, 0))
                take = min(need, p.inv.count(item)) if need > 0 else 0
                if take > 0:
                    p.inv.remove(item, take)
            else:
                key = item
                need = qty - int(prog.get(key, 0))
                take = min(need, self._count_all(item)) if need > 0 else 0
                if take > 0:
                    take = self._remove_all(item, take)
            if take > 0:
                prog[key] = int(prog.get(key, 0)) + take
                moved += take
                last = (item, take, si)
        lbl = self._story_label
        if moved:
            item, take, si = last
            who = p.name if b.get("together") else "You"
            rs["msg"] = (f"{who} added {lbl(item)} x{take}!" if len(slots) == 1 or moved == take
                         else f"Added {moved} items to {b['name']}!")
            rs["flash"] = 0.5
            rs["flash_slot"] = si
            self.audio.play("coin")
            self.audio.play("harvest")
            self._story_ui_burst(SCREEN_W // 2 + 170, SCREEN_H // 2, 14, b["color"])
            if all(self._story_slot_done(b, it, q) for it, q in b["slots"]):
                self._story_complete_bundle(b)
        else:
            item, qty = b["slots"][slots[0]]
            if all_slots:
                rs["msg"] = "Nothing to add right now -- check what's still needed."
            elif self._story_slot_done(b, item, qty) or (
                    b.get("together") and self._story_have(b, item, pidx) >= qty):
                rs["msg"] = f"{p.name if b.get('together') else 'This slot'} is done here!"
            else:
                src = f"{p.name} has" if b.get("together") else "You have"
                rs["msg"] = f"{src} no {lbl(item)}. {self._story_where_hint(item)}"
            self.audio.play("error")
            self.audio.play("ui_move")

    def _story_where_hint(self, item):
        from .. import quests
        try:
            return "Find: " + quests.where(item)
        except Exception:
            return ""

    def _story_complete_bundle(self, b):
        self.story_bundles_done.add(b["id"])
        rw = b.get("reward", {})
        gold = int(rw.get("gold", 0))
        got = []
        for item, qty in rw.get("items", []):
            if SD.item_exists(item) or item == "sprinkler2":
                if b.get("together") and item == "twin_locket":
                    for pl in self.players:             # one keepsake each
                        pl.inv.add(item, qty)
                    got.append(f"{self._story_label(item)} x{qty} each")
                    continue
                self.players[self._rs.get("who", 0) % len(self.players)].inv.add(item, qty)
                got.append(f"{self._story_label(item)} x{qty}")
            else:
                gold += 80 * qty
        self.gold += gold
        self._rs["msg"] = f"{b['name']} complete! +{gold}g " + (", ".join(got))
        self.toast(f"Bundle complete: {b['name']}", ", ".join([f"+{gold}g"] + got),
                   icon=(rw.get("items") or [(None,)])[0][0], color=b["color"], seconds=4.5)
        self.audio.play("achievement")
        self.audio.play("levelup")
        for _ in range(4):
            self._story_ui_burst(random.randint(300, SCREEN_W - 300),
                                 random.randint(160, 420), 26, None)
        self.emit("bundle_done", name=b["name"])
        self._story_celebrate = max(self._story_celebrate, 3.0)
        self._story_place_decor()
        if b["id"] in DECOR_NAMES:
            self.ui.log(f"Restored: {DECOR_NAMES[b['id']]}!")
        if not self.story_restored and all(x["id"] in self.story_bundles_done
                                           for x in self._story_bundles()):
            self.story_restored = True
            self.gold += GRAND_GOLD
            self._story_place_statue()
            self._story_celebrate = 10.0
            self.toast("The valley is restored!",
                       f"A golden statue rises in town. +{GRAND_GOLD}g",
                       icon=None, color=(255, 214, 110), seconds=7.0)
            self.ui.log(f"Valley Restoration complete! +{GRAND_GOLD}g -- see the golden statue!")
            self.emit("bundle_done", name="Valley Restored")

    # ---- screen-space confetti for the board UI ----
    def _story_ui_burst(self, x, y, n, color):
        fx = self._rs["fx"]
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(90, 300)
            c = color or random.choice([(255, 150, 170), (255, 220, 120), (150, 210, 255),
                                        (170, 235, 160), (210, 170, 255)])
            fx.append([x, y, math.cos(a) * sp, math.sin(a) * sp - 120, random.uniform(0.7, 1.4),
                       c, random.randint(3, 6)])
        del fx[:-240]

    # ---- world celebration (confetti / fireworks around the board) ----
    def _on_update_story_restore(self, dt):
        if self._story_celebrate > 0:
            self._story_celebrate -= dt
            if self.world.current == AREA_TOWN and random.random() < dt * 14:
                b = self._story_board() or (20, 12)
                x = b[0] * TILE + random.uniform(-4, 4) * TILE
                y = b[1] * TILE - random.uniform(1, 4) * TILE
                self.parts.confetti(x, y, n=6)
                if random.random() < 0.3:                   # little fireworks
                    col = random.choice([(255, 214, 110), (255, 150, 180), (150, 210, 255),
                                         (190, 240, 160)])
                    sb = getattr(self.parts, "star_burst", None)
                    if sb:
                        sb(x, y - TILE, color=col, n=14)
                    else:
                        self.parts.sparkle(x, y, n=18, color=col)
                    rg = getattr(self.parts, "ring", None)
                    if rg:
                        rg(x, y - TILE, color=col, radius=14)
                    if random.random() < 0.35:
                        self.audio.play("pop")
        # gentle hint sparkle on the board when a player is near
        if self.world.current == AREA_TOWN and random.random() < dt * 2.0:
            b = self._story_board()
            if b:
                wx, wy = b[0] * TILE + TILE / 2, b[1] * TILE
                if any(abs(p.x - wx) + abs(p.y - wy) < TILE * 2.2 for p in self.players):
                    self.parts.sparkle(wx, wy - TILE * 0.6, n=3, color=(255, 222, 130))
            st = getattr(self.world.areas.get(AREA_TOWN), "_story_statue", None)
            if st and random.random() < 0.5:
                self.parts.sparkle(st[0] * TILE + TILE / 2 + random.uniform(-14, 14),
                                   st[1] * TILE - TILE * random.uniform(0.2, 1.3), n=2,
                                   color=(255, 230, 140))

    def _lights_story_statue(self):
        if self.world.current != AREA_TOWN:
            return []
        out = []
        st = getattr(self.world.area, "_story_statue", None)
        if st:
            out.append((st[0] * TILE + TILE / 2, st[1] * TILE - TILE * 0.4, 110, (255, 214, 130)))
        b = self._story_board()
        if b:
            out.append((b[0] * TILE + TILE / 2, b[1] * TILE - TILE * 0.8, 50, (255, 226, 160)))
        for k, gx, gy in self.world.area.props:
            if k == "restore_lamp":
                out.append((gx * TILE + TILE / 2, gy * TILE - TILE * 0.55, 96, (255, 212, 140)))
        return out

    # ---- custom state "restoration" ----
    def _state_event_restoration(self, e):
        if e.type != pygame.KEYDOWN:
            return
        rs = self._rs
        bs = self._story_bundles()
        k = e.key
        if k == pygame.K_ESCAPE:
            self.state = "play"
            self.audio.play("ui_move")
            return
        if not bs:
            if self._story_is_action(k):
                self.state = "play"
            return
        if k in (P1_KEYS["up"], P2_KEYS["up"]):
            rs["sel"] = (rs["sel"] - 1) % len(bs)
            rs["slot"] = 0
            self.audio.play("ui_move")
        elif k in (P1_KEYS["down"], P2_KEYS["down"]):
            rs["sel"] = (rs["sel"] + 1) % len(bs)
            rs["slot"] = 0
            self.audio.play("ui_move")
        elif k in (P1_KEYS["left"], P2_KEYS["left"]):
            rs["slot"] = (rs["slot"] - 1) % max(1, len(bs[rs["sel"] % len(bs)]["slots"]))
            self.audio.play("ui_move")
        elif k in (P1_KEYS["right"], P2_KEYS["right"]):
            rs["slot"] = (rs["slot"] + 1) % max(1, len(bs[rs["sel"] % len(bs)]["slots"]))
            self.audio.play("ui_move")
        elif k == P1_KEYS["action"]:
            self._story_deposit(0)
        elif k == P2_KEYS["action"]:
            self._story_deposit(1 if len(self.players) > 1 else 0)
        elif k == pygame.K_TAB:
            self._story_deposit(self._rs.get("who", 0), all_slots=True)

    def _state_update_restoration(self, dt):
        rs = self._rs
        rs["t"] += dt
        rs["flash"] = max(0.0, rs.get("flash", 0.0) - dt)
        for f in rs["fx"]:
            f[0] += f[2] * dt
            f[1] += f[3] * dt
            f[3] += 420 * dt
            f[4] -= dt
        rs["fx"] = [f for f in rs["fx"] if f[4] > 0]

    def _state_draw_restoration(self):
        from .. import assets
        from ..ui import key_label
        scr = self.screen
        scr.blit(ART.dim(170), (0, 0))
        rs = self._rs
        bs = self._story_bundles()
        f_big, f, f_s, f_t = self.ui.big, self.ui.font, self.ui.small, self.ui.tiny
        pw, ph = 1060, 604
        px, py = (SCREEN_W - pw) // 2, (SCREEN_H - ph) // 2 + 8
        K.modal(scr, (px, py, pw, ph), "Valley Restoration")
        done_n = len([b for b in bs if b["id"] in self.story_bundles_done])
        sub = f"{done_n}/{len(bs)} bundles restored" + (
            "  -  the valley shines again!" if self.story_restored else "")
        hy = py + 44                                   # sub-title row (under the ribbon)
        K.blit_text(scr, K.font(15, True), sub, K.INK_SOFT, (px + 30, hy), align="left")
        gtxt = f"{int(self.gold):,}g"
        gr = K.blit_text(scr, K.font(18, True), gtxt, K.GOLD_TXT, (px + pw - 30, hy), align="right")
        pygame.draw.circle(scr, (236, 186, 70), (gr.x - 12, hy), 7)
        pygame.draw.circle(scr, K.GOLD_TXT, (gr.x - 12, hy), 7, 2)
        if not bs:
            K.blit_text(scr, f, "No bundles available.", K.INK, (px + pw // 2, py + ph // 2))
            return
        sel = rs["sel"] % len(bs)
        # ---- left: bundle list ----
        lx, ly = px + 24, py + 70
        rh = min(62, (ph - 150) // len(bs))
        for i, b in enumerate(bs):
            r = pygame.Rect(lx, ly + i * rh, 330, rh - 6)
            on = i == sel
            done = b["id"] in self.story_bundles_done
            if on:
                K.row_cursor(scr, r, rs["t"])
            else:
                K.well(scr, r, radius=10)
            cx, cy = r.x + 30, r.centery
            pygame.draw.circle(scr, b["color"], (cx, cy), 11)
            pygame.draw.circle(scr, K.WOOD, (cx, cy), 11, 2)
            if done:
                pygame.draw.lines(scr, (54, 104, 44), False,
                                  [(cx - 6, cy), (cx - 1, cy + 5), (cx + 7, cy - 6)], 3)
            K.blit_text(scr, f, b["name"], K.INK, (r.x + 52, r.y + 17), align="left")
            fr = self._story_bundle_frac(b)
            bar = pygame.Rect(r.x + 52, r.bottom - 17, 258, 8)
            pygame.draw.rect(scr, (226, 206, 174), bar, border_radius=4)
            if fr > 0:
                pygame.draw.rect(scr, b["color"], (bar.x, bar.y, max(6, int(bar.w * fr)), bar.h),
                                 border_radius=4)
        # ---- right: slots of the selected bundle ----
        b = bs[sel]
        rx, ry = px + 376, py + 70
        rw = pw - 400
        head = pygame.Rect(rx, ry, rw, 70)
        pygame.draw.rect(scr, _mix(b["color"], K.CREAM, 0.45), head, border_radius=10)
        pygame.draw.rect(scr, _mix(b["color"], K.WOOD_DK, 0.45), head, 2, border_radius=10)
        K.blit_text(scr, K.fit_font(b["name"], rw - 36, (28, 26, 24), bold=True), b["name"],
                    K.INK, (rx + 18, ry + 24), align="left")
        K.blit_text(scr, f_s, b["desc"], K.INK_SOFT, (rx + 20, ry + 52), align="left")
        n = len(b["slots"])
        cw = (rw - (n - 1) * 12) // max(1, n)
        cw = min(cw, 160)
        sx0 = rx + (rw - (n * cw + (n - 1) * 12)) // 2        # slots centred under the header
        sy = ry + 84
        slot_sel = rs["slot"] % max(1, n)
        for si, (item, qty) in enumerate(b["slots"]):
            r = pygame.Rect(sx0 + si * (cw + 12), sy, cw, 210)
            done = self._story_slot_done(b, item, qty)
            on = si == slot_sel
            if done and not on:
                pygame.draw.rect(scr, (226, 236, 196), r, border_radius=10)
                pygame.draw.rect(scr, (150, 186, 120), r, 2, border_radius=10)
            else:
                K.well(scr, r, hot=on, radius=10)
            if rs.get("flash", 0) > 0 and rs.get("flash_slot") == si and on:
                # the flash is a soft glow + rim: the ink text on top stays legible
                a = int(150 * rs["flash"] / 0.5)
                fl = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(fl, (255, 236, 160, a), fl.get_rect(), border_radius=10)
                scr.blit(fl, r.topleft)
            if on:
                pygame.draw.rect(scr, K.GOLD_RIM, r, 3, border_radius=10)
            try:
                ic = assets.item_icon(item)
                big = pygame.transform.scale(ic, (56, 56))
                bob = int(math.sin(rs["t"] * 3 + si) * 3) if on else 0
                scr.blit(big, (r.centerx - 28, r.y + 14 + bob))
            except Exception:
                pass
            name = self._story_label(item)
            for j, ln in enumerate(_wrap_simple(f_s, name, cw - 12)[:2]):
                K.blit_text(scr, f_s, ln, K.INK, (r.centerx, r.y + 86 + j * 17))
            if b.get("together"):
                for pi in range(2):
                    h = min(qty, self._story_have(b, item, pi))
                    nm = self.players[pi].name if pi < len(self.players) else f"P{pi + 1}"
                    self._story_bar(scr, r.x + 12, r.y + 120 + pi * 34, cw - 24, h, qty,
                                    b["color"], f"{nm[:8]}", f_t)
            else:
                h = min(qty, self._story_have(b, item))
                self._story_bar(scr, r.x + 12, r.y + 128, cw - 24, h, qty, b["color"],
                                "", f_t)
                inv = self._count_all(item)
                K.blit_text(scr, f_t, f"in bags: {inv}",
                            K.SPROUT if inv > 0 and not done else K.INK_SOFT,
                            (r.centerx, r.y + 170))
            if done:
                K.blit_text(scr, K.font(15, True), "DONE", (54, 116, 44), (r.centerx, r.y + 192))
        # reward line (everything centred on one line)
        rw_ = b.get("reward", {})
        ry2 = sy + 222
        lc = ry2 + 14
        xx = K.blit_text(scr, K.font(14, True), "Reward:", K.INK_SOFT, (rx + 4, lc),
                         align="left").right + 14
        if rw_.get("gold"):
            xx = K.blit_text(scr, K.font(18, True), f"{rw_['gold']:,}g", K.GOLD_TXT, (xx, lc),
                             align="left").right + 16
        for item, qty in rw_.get("items", []):
            try:
                ic = assets.item_icon(item)
                scr.blit(ic, (xx, lc - ic.get_height() // 2))
                xx += ic.get_width() + 4
            except Exception:
                xx += 30
            xx = K.blit_text(scr, f_s, f"x{qty}", K.INK, (xx, lc), align="left").right + 16
        if b["id"] in self.story_bundles_done:
            K.blit_text(scr, f_s, "(claimed)", K.SPROUT, (xx, lc), align="left")
        # message
        msg = K.ellipsize(f, rs.get("msg", ""), rw - 8)
        K.blit_text(scr, f, msg, K.INK, (rx + 4, ry2 + 50), align="left")
        # what this bundle restores in the valley (a little preview card):
        # sprite + text as one group, centred both ways
        deco = RESTORE_DECOR.get(b["id"])
        if deco:
            card = pygame.Rect(rx, ry2 + 72, rw, 104)
            K.well(scr, card, radius=10)
            done = b["id"] in self.story_bundles_done
            lab = "Restored:" if done else "Restores:"
            line = DECOR_NAMES.get(b["id"], "").capitalize()
            lf = K.font(14, True)
            tw = max(lf.size(lab)[0], f.size(line)[0])
            im = None
            spr = ART.DECOR_PAINTERS.get(deco[0][1])
            if spr:
                im = spr()
                sc = min(1.0, 86 / max(im.get_height(), 1), 140 / max(im.get_width(), 1))
                if sc < 1.0:
                    im = pygame.transform.smoothscale(
                        im, (int(im.get_width() * sc), int(im.get_height() * sc)))
            gw = tw + ((im.get_width() + 28) if im else 0)
            gx = card.centerx - min(gw, card.w - 40) // 2
            if im:
                scr.blit(im, (gx, card.centery - im.get_height() // 2))
                gx += im.get_width() + 28
            K.blit_text(scr, lf, lab, K.INK_SOFT, (gx, card.centery - 12), align="left")
            K.blit_text(scr, f, K.ellipsize(f, line, card.right - 16 - gx),
                        (54, 116, 44) if done else K.INK, (gx, card.centery + 12), align="left")
        hint1 = (f"{key_label(P1_KEYS['up'])}/{key_label(P1_KEYS['down'])} bundle     "
                 f"{key_label(P1_KEYS['left'])}/{key_label(P1_KEYS['right'])} slot     "
                 f"{key_label(P1_KEYS['action'])} P1 add     {key_label(P2_KEYS['action'])} P2 add     "
                 f"TAB add all     ESC close")
        K.blit_text(scr, K.font(13, True), hint1, K.INK_SOFT, (px + pw // 2, py + ph - 26))
        # confetti on top
        for x, y, _, _, life, c, sz in rs["fx"]:
            pygame.draw.rect(scr, c, (int(x), int(y), sz, sz))

    def _story_bar(self, scr, x, y, w, have, need, col, label, font):
        pygame.draw.rect(scr, (226, 206, 174), (x, y, w, 12), border_radius=5)
        if need:
            fw = int(w * min(1.0, have / need))
            if fw > 0:
                pygame.draw.rect(scr, col, (x, y, max(6, fw), 12), border_radius=5)
        pygame.draw.rect(scr, K.WELL_LINE, (x, y, w, 12), 1, border_radius=5)
        K.blit_text(scr, font, f"{label + ' ' if label else ''}{have}/{need}", K.INK,
                    (x + w // 2, y + 22))

    # ---- journal tab ----
    def _journal_tab_45_story_restoration(self):
        return {"title": "Bundles", "draw": self._story_draw_restore_tab}

    def _story_draw_restore_tab(self, surf, rect):
        from .. import assets
        rect = pygame.Rect(rect)
        f, f_s, f_t = self.ui.font, self.ui.small, self.ui.tiny
        bs = self._story_bundles()
        done_n = len([b for b in bs if b["id"] in self.story_bundles_done])
        head = ("The valley is restored! Visit the golden statue in town."
                if self.story_restored else
                f"{done_n}/{len(bs)} bundles complete -- bring goods to the board in town.")
        K.blit_text(surf, K.fit_font(head, rect.w - 12, (18, 17, 16, 15), bold=True), head,
                    (126, 82, 14) if self.story_restored else K.INK,       # a real page header
                    (rect.x + 6, rect.y + 12), align="left")
        n = max(1, len(bs))
        rh = min(64, (rect.h - 34) // n)
        done_col = (54, 116, 44)
        name_w = 300                              # left block: dot, name, progress bar
        for i, b in enumerate(bs):
            row = pygame.Rect(rect.x, rect.y + 32 + i * rh, rect.w, rh - 8)
            done = b["id"] in self.story_bundles_done
            K.well(surf, row, radius=10)
            cy = row.centery
            pygame.draw.circle(surf, b["color"], (row.x + 22, cy), 10)
            pygame.draw.circle(surf, K.WOOD, (row.x + 22, cy), 10, 2)
            if done:
                pygame.draw.lines(surf, done_col, False,
                                  [(row.x + 17, cy), (row.x + 21, cy + 4), (row.x + 28, cy - 5)], 3)
            nr = K.blit_text(surf, f_s, b["name"], K.INK, (row.x + 42, cy - 8), align="left")
            if done:
                K.blit_text(surf, f_t, "DONE", done_col, (nr.right + 10, cy - 8), align="left")
            fr = self._story_bundle_frac(b)
            bar = pygame.Rect(row.x + 42, cy + 6, name_w - 60, 8)
            pygame.draw.rect(surf, (226, 206, 174), bar, border_radius=4)
            if fr > 0:
                pygame.draw.rect(surf, b["color"], (bar.x, bar.y, max(6, int(bar.w * fr)), 8),
                                 border_radius=4)
            # slots spread evenly across the rest of the row
            pygame.draw.line(surf, K.WELL_LINE, (row.x + name_w, row.y + 8),
                             (row.x + name_w, row.bottom - 8), 1)
            sx0 = row.x + name_w + 10
            cell = (row.right - 10 - sx0) // max(4, len(b["slots"]))
            for si, (item, qty) in enumerate(b["slots"]):
                ok = self._story_slot_done(b, item, qty)
                lab = f"x{qty}" + (" each" if b.get("together") else "")
                lw = f_t.size(lab)[0]
                ccx = sx0 + si * cell + cell // 2
                gx = ccx - (28 + 6 + lw) // 2
                try:
                    ic = assets.item_icon(item)
                    if not ok:
                        ic = ic.copy()
                        ic.set_alpha(120)
                    surf.blit(ic, (gx + 14 - ic.get_width() // 2, cy - ic.get_height() // 2))
                except Exception:
                    pass
                K.blit_text(surf, f_t, lab, done_col if ok else K.INK_SOFT, (gx + 34, cy),
                            align="left")


# ============================================================== festival games
EGG_TIME = 60.0
EGG_COUNT = 18


class FestivalGamesMixin:
    """Spring Egg Hunt + Winter Lantern Night."""

    def _on_reset_story_fest(self):
        self.story_potlucks = set()      # years the Luau potluck was judged
        self._potluck = {}               # player idx -> item in today's pot
        self.story_fairs = set()         # years the Harvest Fair was judged
        self._fair = {}                  # player idx -> entered item
        self.story_egg_hunts = set()     # years the egg hunt was played
        self.story_lantern_nights = set()
        self._egg = None                 # running hunt
        self._egg_result = None          # results screen data
        self._lanterns = []              # floating lanterns [x, y, vx, phase, life]
        self._lantern_ready = [-9.0, -9.0]

    def _on_save_story_fest(self):
        d = {"story_potlucks": sorted(self.story_potlucks),
             "story_fairs": sorted(self.story_fairs),
             "story_egg_hunts": sorted(self.story_egg_hunts),
             "story_lantern_nights": sorted(self.story_lantern_nights)}
        if self._potluck or self._fair:
            # an entry waiting for the partner's: kept for the rest of the
            # festival day (refunded at dawn / on a load from another day)
            t = self.time
            d["story_fest_pending"] = {
                "day": f"{t.year}|{t.season_idx}|{t.day}",
                "pot": {str(i): it for i, it in sorted(self._potluck.items())},
                "fair": {str(i): it for i, it in sorted(self._fair.items())}}
        return d

    def _on_load_story_fest(self, d):
        self.story_potlucks = set(str(x) for x in (d.get("story_potlucks", []) or []))
        self._potluck = {}
        self.story_fairs = set(str(x) for x in (d.get("story_fairs", []) or []))
        self._fair = {}
        self.story_egg_hunts = set(str(x) for x in (d.get("story_egg_hunts", []) or []))
        self.story_lantern_nights = set(str(x) for x in (d.get("story_lantern_nights", []) or []))
        self._egg = None
        self._lanterns = []
        self._lantern_ready = [-9.0, -9.0]
        pend = d.get("story_fest_pending") or {}
        if isinstance(pend, dict):
            n = len(self.players)
            for key, book in (("pot", self._potluck), ("fair", self._fair)):
                for i, item in (pend.get(key) or {}).items():
                    try:
                        i = int(i)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= i < n and isinstance(item, str) and item:
                        book[i] = item
            t = self.time
            if pend.get("day") != f"{t.year}|{t.season_idx}|{t.day}":
                # saved on another day: hand it back
                self._story_fest_refund("saved on an earlier day")

    def _on_new_day_story_fest(self):
        """The potluck / fair are one-day events: a lone entry goes home."""
        self._story_fest_refund("the festival day ended")
        self._egg = None
        self._lantern_ready = [-9.0, -9.0]

    def _story_fest_refund(self, why=""):
        for book, event in ((self._potluck, "Luau pot ingredient"),
                            (self._fair, "Harvest Fair entry")):
            for i, item in sorted(book.items()):
                if 0 <= i < len(self.players):
                    p = self.players[i]
                    p.inv.add(item, 1)
                    ui = getattr(self, "ui", None)
                    if ui is not None:
                        ui.log(f"{p.name}: your {event} ({self._story_label(item)}) "
                               f"was returned" + (f" - {why}." if why else "."))
            book.clear()

    def _story_stall(self):
        a = self.world.area
        return getattr(a, "festival_stall", None) or (20, 12)

    # ---- start ----
    def _interact_early_35_story_festival(self, idx, p):
        a = self.world.area
        if self._egg is not None:
            return self._story_egg_grab(idx, p)
        if not festival.is_festival_day(self.time):
            return False
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        if a.name == AREA_TOWN and self.time.season_idx == 0:
            fb = self._story_stall()
            if abs(pgx - fb[0]) <= 1 and abs(pgy - fb[1]) <= 1:
                if str(self.time.year) not in self.story_egg_hunts:
                    self._story_egg_start()
                    return True
            return False
        if a.name == AREA_TOWN and self.time.season_idx in (1, 2):
            fb = self._story_stall()
            if abs(pgx - fb[0]) <= 1 and abs(pgy - fb[1]) <= 1:
                if self.time.season_idx == 1:
                    return self._story_potluck_add(idx, p)
                return self._story_fair_enter(idx, p)
            return False
        if a.name == AREA_BEACH and self.time.season_idx == 3:
            if self._story_npc_near(p) is not None:
                return False              # talking to / gifting the gathered villagers
            ls = self._story_lantern_spot()
            if abs(pgx - ls[0]) <= 1 and abs(pgy - ls[1]) <= 1:
                return self._story_lantern_press(idx, p)
        return False

    # ---- Summer Luau: the potluck pot (each farmer adds one ingredient) ----
    def _story_potluck_add(self, idx, p):
        """Holding a crop / fish / dish at the Luau stall drops it into the
        shared pot. When both farmers have added theirs, Fah tastes the soup:
        better (and tastier-to-her) ingredients = bigger prize. Pressing with
        an empty hand falls through to the classic festival gift."""
        yk = str(self.time.year)
        if yk in self.story_potlucks:
            return False
        entry = p.inv.selected_entry() if p.inv else None
        if not (entry and entry[0] == "item" and not str(entry[1]).startswith("seed:")):
            if not self._potluck:
                self._popup(p.x, p.y - 20, "Hold an ingredient to add it to the pot!",
                            (255, 214, 150))
            return False
        pot = self._potluck
        if idx in pot:
            self._popup(p.x, p.y - 20, "Waiting for your partner's ingredient...",
                        (255, 214, 150))
            return True
        item = entry[1]
        p.inv.remove(item, 1)
        pot[idx] = item
        fb = self._story_stall()
        wx, wy = fb[0] * TILE + TILE / 2, fb[1] * TILE
        self.parts.splash(wx, wy, n=10) if hasattr(self.parts, "splash") else None
        self.parts.sparkle(wx, wy - 10, n=10, color=(255, 200, 120))
        self.audio.play("splash")
        self._popup(wx, wy - 24, f"+ {self._story_label(item)}", (255, 226, 160))
        if len(pot) >= min(2, len(self.players)):
            self._story_potluck_judge()
        else:
            self.ui.log(f"{p.name} added {self._story_label(item)} to the Luau pot. "
                        "Now the other farmer adds one!")
        return True

    # ---- Fall Harvest Fair: "Best in Show" (P1 vs P2) ----
    def _story_fair_score(self, item):
        from ..systems.shop_system import sell_value
        try:
            v = int(sell_value(item))
        except Exception:
            v = 0
        from ..crops import CROPS
        bonus = 1.25 if item in CROPS else 1.0       # it IS a harvest fair
        return int(v * bonus)

    def _story_fair_enter(self, idx, p):
        """Each farmer enters one item (held) into the fair; Elya judges by
        value (crops get a harvest bonus). Winner gets a ribbon prize."""
        yk = str(self.time.year)
        if yk in self.story_fairs:
            return False
        entry = p.inv.selected_entry() if p.inv else None
        if not (entry and entry[0] == "item" and not str(entry[1]).startswith("seed:")):
            if not self._fair:
                self._popup(p.x, p.y - 20, "Hold your best produce to enter the fair!",
                            (255, 214, 150))
            return False
        if idx in self._fair:
            self._popup(p.x, p.y - 20, "Entered! Waiting for your partner...", (255, 214, 150))
            return True
        item = entry[1]
        p.inv.remove(item, 1)
        self._fair[idx] = item
        fb = self._story_stall()
        wx, wy = fb[0] * TILE + TILE / 2, fb[1] * TILE
        self.parts.sparkle(wx, wy - 10, n=12, color=(255, 200, 120))
        self.audio.play("ui_select")
        self._popup(wx, wy - 24, p.name + ": " + self._story_label(item), (255, 226, 160))
        if len(self._fair) >= min(2, len(self.players)):
            self._story_fair_judge()
        return True

    def _story_fair_judge(self):
        entries, self._fair = self._fair, {}
        self.story_fairs.add(str(self.time.year))
        scores = {i: self._story_fair_score(it) for i, it in entries.items()}
        best = max(scores.values()) if scores else 0
        winners = sorted(i for i, v in scores.items() if v == best)
        prize = 300 + min(700, best)
        self.gold += prize
        parts = []
        for i in sorted(entries):
            nm = self.players[i].name if i < len(self.players) else "P" + str(i + 1)
            parts.append(nm + " - " + self._story_label(entries[i]) + " (" + str(scores[i]) + " pts)")
            if i < len(self.players):
                self.players[i].inv.add(entries[i], 1)          # entries come back home
        wn = " & ".join(self.players[i].name for i in winners if i < len(self.players))
        head = "A tie! Both win Best in Show!" if len(winners) > 1 else wn + " wins Best in Show!"
        self.dialogue_text = ("Elya: What a harvest! " + ", ".join(parts) + ". " + head
                              + " Prize: +" + str(prize) + "g")
        self.state = "dialogue"
        self.toast("Harvest Fair: Best in Show", wn + "  +" + str(prize) + "g",
                   color=(236, 170, 90), seconds=5.0)
        self.audio.play("achievement")
        fb = self._story_stall()
        for _ in range(4):
            self.parts.confetti(fb[0] * TILE + random.uniform(-40, 40), fb[1] * TILE - 40, n=10)
        for i in winners:
            if i < len(self.players):
                self.emit("festival_won", p=self.players[i], name="harvest_fair")

    def _story_potluck_judge(self):
        from ..systems.shop_system import sell_value
        pot, self._potluck = self._potluck, {}
        self.story_potlucks.add(str(self.time.year))
        score = 0
        for item in pot.values():
            try:
                v = int(sell_value(item))
            except Exception:
                v = 0
            score += min(400, v)
            t = SD.taste("Fah", item)
            score += {"love": 220, "like": 90, "neutral": 0, "dislike": -120}[t]
        if score >= 500:
            tier, gold, pts, line = ("Legendary", 800, 40,
                                     "Fah: WOW! This is the best soup in Luau history!")
        elif score >= 250:
            tier, gold, pts, line = ("Delicious", 450, 25,
                                     "Fah: Mmm! Rich and sweet -- everyone's going back for seconds!")
        elif score >= 80:
            tier, gold, pts, line = ("Tasty", 250, 10, "Fah: Not bad at all! A cozy little soup.")
        else:
            tier, gold, pts, line = ("Interesting", 80, 0,
                                     "Fah: ...Hm! It's... certainly memorable. Heh.")
        self.gold += gold
        for name in SD.VILLAGERS:
            if pts and name in self.world.friend:           # only villagers you've met
                self.world.friend[name] = min(500, int(self.world.friend.get(name, 0)) + pts)
        fb = self._story_stall()
        wx, wy = fb[0] * TILE + TILE / 2, fb[1] * TILE
        for _ in range(5):
            self.parts.confetti(wx + random.uniform(-50, 50), wy - 50, n=10)
        self.audio.play("achievement")
        self.dialogue_text = (f"{line}  Soup rating: {tier}! +{gold}g"
                              + (f", everyone's friendship +{pts}" if pts else ""))
        self.state = "dialogue"
        self.toast(f"Luau Potluck: {tier}!", f"+{gold}g" + (" - the whole valley is happy"
                                                            if pts else ""),
                   color=(250, 196, 110), seconds=5.0)
        if pts >= 25:
            for i in sorted(pot):
                if i < len(self.players):
                    self.emit("festival_won", p=self.players[i], name="luau_potluck")

    def _story_lantern_spot(self):
        """Foot of the beach pier (the lifebuoy post), where lanterns are let go."""
        a = self.world.area
        lb = next(((gx, gy) for k, gx, gy in getattr(a, "props", ()) if k == "lifebuoy"), None)
        return (lb[0] + 1, lb[1]) if lb else (20, 17)

    def _story_egg_start(self):
        a = self.world.area
        rng = random.Random(self.time.year * 97 + 13)
        fb = self._story_stall()
        cands = [(x, y) for y in range(3, a.h - 3) for x in range(3, a.w - 3)
                 if self._story_free(a, x, y) and abs(x - fb[0]) + abs(y - fb[1]) > 2]
        rng.shuffle(cands)
        picked = []
        for c in cands:
            if all(abs(c[0] - o[0]) + abs(c[1] - o[1]) >= 3 for o in picked):
                picked.append(c)
            if len(picked) >= EGG_COUNT:
                break
        eggs = []
        for i, (gx, gy) in enumerate(picked):
            eggs.append({"x": gx * TILE + TILE / 2 + rng.uniform(-8, 8),
                         "y": gy * TILE + TILE / 2 + rng.uniform(-6, 6),
                         "c": i % len(ART.EGG_COLORS), "gold": i < 2,
                         "ph": rng.uniform(0, 6.28)})
        # the year is marked as played only when the hunt resolves (_story_egg_end),
        # so quitting / crashing mid-hunt never forfeits the year's hunt
        self._egg = {"t": EGG_TIME, "eggs": eggs, "score": [0, 0], "n": 0}
        self.toast("EGG HUNT!", f"Find {len(eggs)} eggs around town in 60 seconds!",
                   icon="golden_egg", color=(255, 190, 210), seconds=4.0)
        self.audio.play("bell")
        self.audio.play("levelup")
        fx, fy = fb[0] * TILE + TILE / 2, fb[1] * TILE
        for _ in range(4):
            self.parts.confetti(fx + random.uniform(-40, 40), fy - 40, n=10)

    def _story_egg_take(self, idx, egg):
        hunt = self._egg
        pts = 3 if egg["gold"] else 1
        hunt["score"][idx] += pts
        hunt["eggs"].remove(egg)
        hunt["n"] += 1
        col = (255, 214, 90) if egg["gold"] else ART.EGG_COLORS[egg["c"]]
        self.parts.sparkle(egg["x"], egg["y"] - 6, n=14 if egg["gold"] else 8, color=col)
        fx = getattr(self.parts, "star_burst" if egg["gold"] else "poof", None)
        if fx:
            try:
                fx(egg["x"], egg["y"] - 6, color=col)
            except Exception:
                pass
        self._popup(egg["x"], egg["y"] - 20, "+3 GOLDEN!" if egg["gold"] else "+1", col)
        self.audio.play("coin" if egg["gold"] else "harvest")

    def _story_egg_grab(self, idx, p):
        for egg in list(self._egg["eggs"]):
            if abs(egg["x"] - p.x) < TILE * 1.1 and abs(egg["y"] - p.y) < TILE * 1.1:
                self._story_egg_take(idx, egg)
                return True
        return False

    def _on_update_story_fest(self, dt):
        hunt = self._egg
        if hunt is not None:
            if self.world.current != AREA_TOWN:
                self._story_egg_end(abandoned=True)
                return
            hunt["t"] -= dt
            sec = int(math.ceil(hunt["t"]))
            if sec != hunt.get("last") and 0 < sec <= 5:
                self.audio.play("bell" if sec == 1 else "ui_move")   # final countdown ticks
                self.add_shake(1.5)
            hunt["last"] = sec
            for i, p in enumerate(self.players[:2]):
                for egg in list(hunt["eggs"]):
                    if abs(egg["x"] - p.x) < 22 and abs(egg["y"] - p.y) < 22:
                        self._story_egg_take(i, egg)
            if hunt["t"] <= 0 or not hunt["eggs"]:
                self._story_egg_end()
                return
        if self._lanterns:
            for ln in self._lanterns:
                ln[1] -= dt * (26 + (ln[3] % 1.0) * 14)
                ln[0] += math.sin(ln[3] + ln[4] * 0.8) * dt * 8 + ln[2] * dt
                ln[4] += dt
            self._lanterns = [ln for ln in self._lanterns if ln[4] < 60]

    def _story_egg_end(self, abandoned=False):
        hunt, self._egg = self._egg, None
        if hunt is None:
            return
        s = hunt["score"]
        if abandoned:
            # left town mid-hunt: no result, no prize -- and the year's hunt is
            # NOT used up, so the stall offers a fresh hunt
            self.ui.log("The Egg Hunt was called off. Visit the festival stall "
                        "to start it again!")
            self.toast("Egg Hunt called off", "Back at the town stall, you can start again",
                       icon="golden_egg", color=(255, 190, 210), seconds=4.0)
            return
        self.story_egg_hunts.add(str(self.time.year))
        names = [p.name for p in self.players[:2]]
        if s[0] + s[1] <= 0:
            winners = []                   # nobody found an egg: no winner, no trophy
        elif s[0] == s[1]:
            winners = [0, 1]
        else:
            winners = [0 if s[0] > s[1] else 1]
        # prizes: winner(s) get a Golden Egg trophy, everyone gets seeds; the
        # shared purse gets 100g + 10g per egg found (balanced: ~150-250g)
        gold = (10 * (s[0] + s[1]) + 100) if winners else 0
        self.gold += gold
        for i, p in enumerate(self.players[:2]):
            p.inv.add("seed:cauliflower", 3)
            if i in winners:
                p.inv.add("golden_egg", 1)
        for w in winners:
            self.emit("festival_won", p=self.players[w], name="egg_hunt")
        self._egg_result = {"score": list(s), "names": names, "winners": winners,
                            "gold": gold, "t": 0.0}
        self.audio.play("achievement")
        self.state = "egg_hunt_end"

    # ---- HUD + world ----
    def _draw_hud_story_egg(self):
        hunt = self._egg
        if hunt is None or self.state != "play":
            return
        scr = self.screen
        w, h = 420, 64
        x, y = SCREEN_W // 2 - w // 2, 108          # below the two hotbars
        rect = pygame.Rect(x, y, w, h)
        f_res = getattr(self, "hud_reserve", None)  # the area title card keeps clear
        f_res and f_res(rect.inflate(8, 8))
        # a dark-plum HUD plate (like the boss plate): shadow, same-radius
        # fill + outline, a festive pink accent strip along the top
        K.pill(scr, rect.move(2, 3), (0, 0, 0), radius=12, alpha=70)
        K.pill(scr, rect, (34, 28, 44), (104, 92, 128), radius=12, alpha=240)
        pygame.draw.rect(scr, (246, 150, 186), (x + 16, y + 1, w - 32, 3), border_radius=2)
        light = (255, 240, 220)
        # centre column: timer over the eggs-left line
        t = max(0, int(math.ceil(hunt["t"])))
        tc = (255, 110, 110) if t <= 10 and int(hunt["t"] * 4) % 2 == 0 else light
        K.blit_text(scr, K.font(30, True), f"{t // 60}:{t % 60:02d}", tc, (rect.centerx, y + 24))
        K.blit_text(scr, K.font(12, True), f"EGG HUNT  -  {len(hunt['eggs'])} left",
                    (214, 204, 232), (rect.centerx, y + 50))
        # divider ticks between the three columns
        for dx in (-78, 78):
            pygame.draw.line(scr, (74, 64, 94), (rect.centerx + dx, y + 12),
                             (rect.centerx + dx, y + h - 12), 1)
        # side columns: each farmer's name (player colour) over their score
        col_w = 110
        for i in range(min(2, len(self.players))):
            p = self.players[i]
            ccx = x + 14 + col_w // 2 if i == 0 else x + w - 14 - col_w // 2
            nf = K.fit_font(p.name, col_w, (15, 14, 13, 12, 11), bold=True)
            pc = _mix(K.P_COL[i], (255, 255, 255), 0.3)          # brighter on the plum plate
            K.blit_text(scr, nf, K.ellipsize(nf, p.name, col_w), pc, (ccx, y + 18))
            K.blit_text(scr, K.font(24, True), str(hunt["score"][i]), light, (ccx, y + 44))

    def _world_sprites_story_eggs(self):
        out = []
        cam = self.cam
        if self._egg is not None:
            t = self.anim_t
            for egg in self._egg["eggs"]:
                spr = ART.egg_sprite(egg["c"], egg["gold"])
                bob = math.sin(t * 3 + egg["ph"]) * 2
                out.append((egg["y"] + 8, spr, (egg["x"] - 11 - cam.x, egg["y"] - 18 - cam.y + bob)))
        return out

    def _lights_story_fest(self):
        out = []
        if self._egg is not None:
            for egg in self._egg["eggs"]:
                if egg["gold"]:
                    out.append((egg["x"], egg["y"], 40, (255, 214, 110)))
        if self._lanterns and self.world.current == AREA_BEACH:
            for i, (x, y, _, _, life) in enumerate(self._lanterns):
                if i % 3 == 0:
                    out.append((x, y, 30 + 4 * math.sin(life * 3), (255, 170, 90)))
        return out

    def _draw_world_story_lanterns(self):
        if not self._lanterns or self.world.current != AREA_BEACH:
            return
        cam = self.cam
        for x, y, _, _, life in self._lanterns:
            sx, sy = int(x - cam.x), int(y - cam.y)
            a = max(0.0, min(1.0, (60 - life) / 6))
            if a <= 0:
                continue
            gl = ART.glow(26, (255, 180, 90))
            flick = 0.85 + 0.15 * math.sin(life * 7 + x)
            gl.set_alpha(int(170 * a * flick))
            self.screen.blit(gl, (sx - 26, sy - 28))
            scr = self.screen
            pygame.draw.rect(scr, (214, 96, 70), (sx - 8, sy - 11, 16, 19), border_radius=5)
            pygame.draw.rect(scr, (250, 160, 90), (sx - 7, sy - 10, 14, 17), border_radius=5)
            pygame.draw.rect(scr, (255, 232, 160), (sx - 3, sy - 6, 6, 10), border_radius=2)
            pygame.draw.line(scr, (150, 70, 50), (sx - 7, sy - 11), (sx + 7, sy - 11), 2)
            pygame.draw.line(scr, (150, 70, 50), (sx - 6, sy + 8), (sx + 6, sy + 8), 2)

    # ---- results screen ----
    def _state_event_egg_hunt_end(self, e):
        if e.type == pygame.KEYDOWN and (e.key == pygame.K_ESCAPE or self._story_is_action(e.key)):
            if self._egg_result and self._egg_result.get("t", 0) < 0.4 and e.key != pygame.K_ESCAPE:
                return
            self._egg_result = None
            self.state = "play"
            self.audio.play("ui_select")

    def _state_update_egg_hunt_end(self, dt):
        r = self._egg_result
        if r is None:
            self.state = "play"
            return
        r["t"] += dt
        if random.random() < dt * 8:
            # little bursts over the two eggs, inside the results card
            pan = _egg_panel()
            bx = pan.x + pan.w // 4 + random.choice((0, pan.w // 2)) + random.randint(-70, 70)
            self._story_ui_burst(bx, pan.y + random.randint(70, 130), 10, None)
        self._state_update_restoration(dt)

    def _state_draw_egg_hunt_end(self):
        scr = self.screen
        scr.blit(ART.dim(170), (0, 0))
        r = self._egg_result
        if r is None:
            return
        f = self.ui.font
        pan = _egg_panel()
        px, py, pw, ph = pan
        K.modal(scr, pan, "Egg Hunt Results")
        # two matching columns, split by a thin rule
        pygame.draw.line(scr, K.WELL_LINE, (pan.centerx, py + 56), (pan.centerx, py + 212), 2)
        for i in range(2):
            cx = px + pw // 4 + i * pw // 2
            nm = r["names"][i] if i < len(r["names"]) else f"P{i + 1}"
            win = i in r["winners"]
            egg = pygame.transform.scale(ART.egg_sprite(i * 2, win), (66, 78))
            bob = int(math.sin(r["t"] * 4 + i) * 4) if win else 0
            ey = py + 70
            scr.blit(egg, (cx - 33, ey + bob))
            if win:                                              # little crown
                cy = ey - 6 + bob
                pygame.draw.polygon(scr, (250, 206, 80), [(cx - 16, cy), (cx - 16, cy - 14),
                                                          (cx - 8, cy - 6), (cx, cy - 16),
                                                          (cx + 8, cy - 6), (cx + 16, cy - 14),
                                                          (cx + 16, cy)])
                pygame.draw.polygon(scr, K.GOLD_TXT, [(cx - 16, cy), (cx - 16, cy - 14),
                                                      (cx - 8, cy - 6), (cx, cy - 16),
                                                      (cx + 8, cy - 6), (cx + 16, cy - 14),
                                                      (cx + 16, cy)], 1)
            nf = K.fit_font(nm, pw // 2 - 40, (18, 16, 15, 14), bold=True)
            K.blit_text(scr, nf, K.ellipsize(nf, nm, pw // 2 - 40), K.P_COL[i % 2],
                        (cx, py + 172))
            K.blit_text(scr, K.font(28, True), f"{r['score'][i]} pts", K.INK, (cx, py + 202))
        K.divider(scr, pan.centerx, py + 236, 220)
        if not r["winners"]:
            msg = "No eggs found this time... no winner this year!"
        elif len(r["winners"]) == 2:
            msg = "A tie! Both farmers win a Golden Egg!"
        else:
            msg = f"{r['names'][r['winners'][0]]} wins the Golden Egg!"
        mf = K.fit_font(msg, pw - 60, (18, 16, 15, 14), bold=True)
        K.blit_text(scr, mf, msg, K.INK, (pan.centerx, py + 266))
        prize = (f"Everyone: +{r['gold']:,}g and Cauliflower Seeds x3" if r.get("gold")
                 else "Everyone: Cauliflower Seeds x3")
        K.blit_text(scr, K.font(15), prize, K.INK_SOFT, (pan.centerx, py + 294))
        if r["t"] > 0.4:
            K.continue_hint(scr, (pan.centerx, py + ph - 30), r["t"], text=_continue_text())
        # confetti stays on the card (no stray dots over the world)
        prev = scr.get_clip()
        scr.set_clip(pan.inflate(-28, -28).clip(prev))
        for x, y, _, _, life, c, sz in self._rs["fx"]:
            pygame.draw.rect(scr, c, (int(x), int(y), sz, sz))
        scr.set_clip(prev)

    # ---- Winter Lantern Night (beach, festival day, evening) ----
    def _story_lantern_press(self, idx, p):
        if self.time.minutes < 17 * 60:
            # a gentle, throttled hint -- the press still falls through to tools /
            # forage, so the pier foot stays usable all day
            now = self.anim_t
            last = getattr(self, "_lantern_hint_t", -99.0)
            if now - last > 4.0:
                self._lantern_hint_t = now
                self._popup(p.x, p.y - 20, "Lantern Night starts at dusk (5 PM)",
                            (255, 214, 150))
            return False
        import time as _t
        now = _t.monotonic()
        self._lantern_ready[idx] = now
        other = 1 - idx
        if len(self.players) < 2 or now - self._lantern_ready[other] <= 2.5:
            self._story_release_lanterns()
            self._lantern_ready = [-9.0, -9.0]
        else:
            self._popup(p.x, p.y - 20, "Ready! Waiting for partner...", (255, 214, 150))
            self.audio.play("ui_select")
        return True

    def _story_release_lanterns(self):
        a, b = self.players[0], self.players[-1]
        mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
        for _ in range(14):
            self._lanterns.append([mx + random.uniform(-90, 90), my + random.uniform(-30, 30),
                                   random.uniform(-9, 9), random.uniform(0, 6), 0.0])
        self._lanterns = self._lanterns[-80:]
        self.parts.heart_burst(mx, my - 20, n=18)
        self.audio.play("bell")
        wish = random.choice(LANTERN_WISHES)
        self.ui.log(f"Your lanterns carry a wish: \"{wish}\"")
        self._popup(mx, my - 60, wish, (255, 226, 170))
        first = str(self.time.year) not in self.story_lantern_nights
        self.story_lantern_nights.add(str(self.time.year))
        if first:
            self.gold += 250
            for pl in self.players:
                self._popup(pl.x, pl.y - 24, "+merit", (255, 214, 150))
            self.toast("Lantern Night", "Your lanterns drift up together. +250g",
                       color=(255, 196, 120), seconds=5.0)
            # (no festival_won: Lantern Night is cooperative, not a contest)
        else:
            self.ui.log("More lanterns float over the sea...")


LANTERN_WISHES = [
    "Another year together, side by side.",
    "May our fields and our hearts always be full.",
    "Let's grow old on this farm, you and me.",
    "Thank you for every sunrise we shared.",
    "More adventures, more harvests, more us.",
    "Wherever the seasons turn, I'll be with you.",
]


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _egg_panel():
    """Screen rect of the Egg Hunt results card (shared by update + draw)."""
    pw, ph = 640, 372
    return pygame.Rect((SCREEN_W - pw) // 2, (SCREEN_H - ph) // 2 + 6, pw, ph)


def _wrap_simple(font, text, width):
    words, lines, cur = str(text).split(), [], ""
    for wd in words:
        cand = (cur + " " + wd) if cur else wd
        if font.size(cand)[0] <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines
