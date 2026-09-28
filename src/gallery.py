"""Gallery / Models screen — a browsable catalogue of EVERY sprite in the game.

Owner: "UI & Rendering" chat. The single rule here: the gallery never draws art
of its own. Every entry's thumbnail is produced by the real drawing function
that the game uses in play, so this screen is always an accurate source of truth
(add a sprite anywhere and it shows up here unchanged).

Sources used (all real):
  Tools      assets.tool_icon(t)            for t in inventory.TOOLS
  Items      assets.item_icon(id)           crops / fish / materials / foods
  Characters assets.player_sprite(look) + assets.player_frames(...)["down"][0]
  Animals    critters.chicken / critters.cow drawn onto a surface
  Monsters   entities.Monster(...).draw(surf, cam)  via a fake camera
  Props      assets.prop_sprite(kind)       for every dispatcher kind
  Furniture  furniture.sprite(kind, PALETTE[0][1], 0) for kind in furniture.CAT
  Terrain    water_frames()[0] / tree_sprite() / rock_sprite(ore)

Layout: category tabs + a scaled thumbnail grid with names, scrolled with the
shared helpers in ui.py (scroll_window / draw_scrollbar / draw_scroll_arrows).
Core only needs to route the "gallery" state to handle_event / update / draw.
"""
import math
import re
import pygame

from . import animals, assets, critters, furniture, loot, monsters, npc, ui
from .entities import Monster
from .inventory import TOOLS
from .crops import CROPS
from .fishing import FISH
from .settings import SCREEN_W, SCREEN_H, GOLD, UI_BORDER


class _Cam:
    """Minimal stand-in for the game camera (Monster.draw only reads .x/.y)."""
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y


# (hair_style, hair_color_index, skin_index) — matches NPC.__init__ in npc.py
_NPC_LOOKS = {"Mira": ("ponytail", 7, 1), "Tomas": ("short", 0, 3),
              "Elya": ("bun", 2, 2), "Luang Por": ("bald", 0, 3)}

from .cooking import FOODS as _COOKING_FOODS
_FOODS = list(_COOKING_FOODS)     # registry-driven: new dishes appear automatically

CATEGORIES = ["Tools", "Items", "Characters", "Animals", "Monsters",
              "Props", "Furniture", "Terrain"]

# Mist City lives in its own domain (src/mistcity); it publishes its models via
# gallery_entries() so this screen stays registry-driven (guarded per ARCHITECTURE
# — the gallery must keep working even before/without that package).
try:
    from .mistcity import gallery_entries as _mist_entries
except Exception:
    _mist_entries = None
if _mist_entries:
    CATEGORIES.append("Mist City")

CELL_W, CELL_H = 116, 118
GRID_X, GRID_Y = 40, 132
CARD_Y = 52                     # top of the parchment card holding the tabs + grid
STAGE_R = 186                   # detail view: radius of the stage ring the model sits in


_SUFFIX_WORDS = {"h": "Horizontal", "v": "Vertical", "p": "Post", "s": "South", "w": "West",
                 "sw": "South-West", "sub": "Submerged"}


def _title(s):
    """Friendly display name for a registry key: 'mflowers2b' -> 'Meadow
    Flowers 2B', 'cobble2' -> 'Cobble 2', 'hill_sw' -> 'Hill South-West'."""
    s = str(s)
    m = re.match(r"^mflowers(\d?)([a-z]?)$", s)
    if m:
        return ("Meadow Flowers " + m.group(1) + m.group(2).upper()).rstrip()
    parts = s.split("_")
    if len(parts) > 1 and parts[-1] in _SUFFIX_WORDS:
        parts[-1] = _SUFFIX_WORDS[parts[-1]]
    t = " ".join(parts).title()
    return re.sub(r"(?<=[A-Za-z])(?=\d)", " ", t)


class GalleryScreen:
    def __init__(self, game, on_close=None):
        self.g = game
        self._on_close = on_close      # called on ESC; falls back to state="menu"
        self.tab = 0
        self.sel = 0
        self.cols = max(1, (SCREEN_W - GRID_X - 70) // CELL_W)
        self._entries = {}        # category -> [(name, render_fn)]
        self._art = {}            # (tab, idx) -> cached Surface
        self._tab_rects = []      # [(Rect, tab_index)]  filled during draw
        self._cell_rects = []     # [(Rect, entry_index)] filled during draw
        # detail / inspect overlay (click a cell to zoom + turn a model)
        self.detail_idx = None    # None = grid; int = inspecting that entry
        self.view = 0             # which facing/view (front/right/back/left, etc.)
        self.spin = 0.0           # free in-plane rotation (drag, or arrows fallback)
        self.zoom = 1.0           # extra zoom on top of the fit-to-box scale
        self._drag = None         # (start_x, start_spin, moved) while dragging
        self._views = {}          # (tab_idx, entry_idx) -> () -> [(label, surface)]
        self._build()

    # ---- catalogue (every render_fn calls a REAL draw function) ----
    def _build(self):
        E = {c: [] for c in CATEGORIES}
        for t in TOOLS:
            E["Tools"].append((_title(t), (lambda t=t: assets.tool_icon(t))))
        # Items: every registry, de-duplicated (crops, fish, loot.MATERIALS incl.
        # loot.register_item additions, foods, seeds, and any icon registered via
        # assets.register_item_icon) -- new content shows up with no edits here
        seen = set()

        def add_item(iid, name=None):
            if iid in seen:
                return
            seen.add(iid)
            if name is None:
                name = (loot.MATERIALS.get(iid) or {}).get("label") or _title(iid)
            E["Items"].append((name, (lambda i=iid: assets.item_icon(i))))

        for cid in CROPS:
            add_item(cid)
        for fid in FISH:
            add_item(fid)
        for mid in loot.MATERIALS:          # registry-driven: new loot shows up free
            add_item(mid)
        for fid in _FOODS:
            add_item(fid)
        for iid in list(getattr(assets, "ITEM_PAINTERS", {})):
            add_item(iid)
        for cid in CROPS:
            add_item("seed:" + cid, _title(cid) + " Seed")

        ctab = CATEGORIES.index("Characters")
        player_look = {"skin": 2, "hair_style": 3, "hair_color": 1, "shirt_color": 6}
        E["Characters"].append(("Player", (lambda L=player_look: assets.player_sprite(L))))
        self._views[(ctab, 0)] = (lambda L=player_look: self._char_views(assets.frames_for(L)))
        # every villager in the NPC registry (new villagers appear automatically)
        nf = getattr(npc, "npc_frames", None)
        for j, nm in enumerate(npc.NPC_DATA):
            if nf is not None:
                fr = (lambda nm=nm: nf(nm))
            else:
                style, hair_i, skin_i = _NPC_LOOKS.get(nm, ("short", 0, 2))
                fr = (lambda style=style, hair_i=hair_i, skin_i=skin_i, nm=nm:
                      assets.player_frames(assets.SKIN_TONES[skin_i % len(assets.SKIN_TONES)],
                                           style, assets.HAIR_COLORS[hair_i % len(assets.HAIR_COLORS)],
                                           npc.NPC_DATA[nm].get("color", (160, 160, 170))))
            E["Characters"].append((nm, (lambda fr=fr: fr()["down"][0])))
            self._views[(ctab, j + 1)] = (lambda fr=fr: self._char_views(fr()))

        for kind, a in animals.ANIMALS.items():   # registry-driven: new livestock show up free
            E["Animals"].append((a["label"], (
                lambda sh=a.get("shape", kind), c=a["color"]:
                self._critter(lambda s, x, y, z, f: critters.farm_animal(s, x, y, z, f, sh, c)))))

        mtab = CATEGORIES.index("Monsters")
        for j, (key, a) in enumerate(monsters.ARCHETYPES.items()):
            E["Monsters"].append((a.get("label", _title(key)),
                                  (lambda key=key: self._monster(key))))
            self._views[(mtab, j)] = (lambda key=key: self._mon_views(key))

        for kind in assets.PROPS:           # registry-driven: new props show up free
            E["Props"].append((_title(kind), (lambda k=kind: assets.prop_sprite(k))))

        for kind in furniture.CAT:
            lab = furniture.CAT[kind].get("label", _title(kind))
            E["Furniture"].append((lab, (
                lambda k=kind: furniture.sprite(k, furniture.PALETTE[0][1], 0))))

        E["Terrain"].append(("Water", (lambda: assets.water_frames()[0])))
        E["Terrain"].append(("Tree", (lambda: assets.tree_sprite())))
        from .settings import SEASONS
        for se in SEASONS:                  # seasonal canopies used in play
            E["Terrain"].append((f"{se} Tree", (lambda se=se: assets.tree_sprite(se))))
        E["Terrain"].append(("Rock", (lambda: assets.rock_sprite(None))))
        for ore in ("copper", "iron", "gold"):
            E["Terrain"].append((_title(ore) + " Rock",
                                 (lambda o=ore: assets.rock_sprite(o))))
        try:                                # one boulder per mine biome (World registry)
            from .world import BIOME_STYLE
        except Exception:
            BIOME_STYLE = {}
        for biome, st in BIOME_STYLE.items():
            tint = st.get("rock_tint")
            E["Terrain"].append((_title(biome) + " Boulder",
                                 (lambda t=tuple(tint) if tint else None: assets.rock_sprite(None, t))))
        if hasattr(assets, "tilled_tile"):
            E["Terrain"].append(("Tilled Soil", (lambda: assets.tilled_tile(False))))
            E["Terrain"].append(("Watered Soil", (lambda: assets.tilled_tile(True))))
        if _mist_entries:                   # provider-driven: Chat 7's own models
            try:
                E["Mist City"] = list(_mist_entries())
            except Exception:
                E["Mist City"] = []
        self._entries = E

    def _critter(self, fn):
        s = pygame.Surface((46, 42), pygame.SRCALPHA)
        fn(s, 23, 26, 11, 1)          # (surf, cx, cy, size, facing) — draws in place
        return s

    def _monster(self, key):
        m = Monster(0, 0, key, 1)
        m.anim_t = 0.7                # a lively mid-animation pose
        sz = int(m.size)
        w, h = sz * 4 + 12, sz * 4 + 32
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        # body + shadow only: the in-game HP bar and boss name plate are HUD,
        # not part of the model (the label under the card already names it)
        cx, cy = w / 2, h * 0.62
        body = getattr(m, "_draw_body", None)
        if callable(body):
            try:
                s.blit(assets.shadow(int(sz * 1.8), int(sz * 0.7)),
                       (cx - sz * 0.9, cy + sz * 0.55))
                body(s, cx, cy)
                return s
            except Exception:
                s.fill((0, 0, 0, 0))
        m.draw(s, _Cam(m.x - w / 2, m.y - h * 0.62))   # fake camera centres the body
        return s

    @staticmethod
    def _char_views(frames):
        """Real 4-way facings of a character: front/right/back/left."""
        order = [("front", "down"), ("right", "right"), ("back", "up"), ("left", "left")]
        out = []
        for label, d in order:
            f = frames.get(d)
            if f:
                out.append((label, f[0]))
        return out or [("front", frames.get("down", [None])[0])]

    def _mon_views(self, key):
        """A monster seen facing right and left (mirror)."""
        art = self._monster(key)
        return [("right", art), ("left", pygame.transform.flip(art, True, False))]

    def _detail_views(self):
        """List of (label, surface) for the inspected entry. Multi-view for
        characters (4 facings) and monsters (L/R); single view otherwise."""
        prov = self._views.get((self.tab, self.detail_idx))
        if prov:
            try:
                vs = prov()
                if vs:
                    return vs
            except Exception:
                pass
        name, fn = self._entries[CATEGORIES[self.tab]][self.detail_idx][:2]
        return [(name, self._art_for(self.detail_idx, fn))]

    # ---- art cache (one bad entry can never crash the screen) ----
    def _art_for(self, idx, fn):
        key = (self.tab, idx)
        if key not in self._art:
            try:
                self._art[key] = self._crop(fn())
            except Exception:
                ph = pygame.Surface((28, 28), pygame.SRCALPHA)
                pygame.draw.rect(ph, (190, 80, 80), (4, 4, 20, 20), border_radius=4)
                self._art[key] = ph
        return self._art[key]

    @staticmethod
    def _crop(art):
        """Trim transparent margins so small sprites on a roomy canvas (e.g. the
        Wild Man) are scaled by what is actually drawn, not by empty space."""
        try:
            br = art.get_bounding_rect(min_alpha=8)
        except Exception:
            return art
        if br.w <= 0 or br.h <= 0 or br.size == art.get_size():
            return art
        return art.subsurface(br).copy()

    @staticmethod
    def _fit(art, bw, bh):
        aw, ah = art.get_size()
        if aw <= 0 or ah <= 0:
            return art
        scale = max(0.1, min(bw / aw, bh / ah, 4.0))
        return pygame.transform.scale(art, (max(1, int(aw * scale)), max(1, int(ah * scale))))

    # ---- input / state ----
    def _open_detail(self, idx):
        self.detail_idx = idx
        self.sel = idx            # the dimmed grid behind highlights the shown model
        self.view = 0
        self.spin = 0.0
        self.zoom = 1.0
        self._drag = None

    def handle_event(self, e):
        if self.detail_idx is not None:
            self._handle_detail(e)
            return
        n = len(self._entries[CATEGORIES[self.tab]])
        # --- mouse: click tab switches, click cell opens detail, wheel scrolls ---
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, i in self._tab_rects:
                if rect.collidepoint(e.pos):
                    if i != self.tab:
                        self.tab = i
                        self.sel = 0
                    return
            for rect, idx in self._cell_rects:
                if rect.collidepoint(e.pos):
                    self.sel = idx
                    self._open_detail(idx)
                    return
            return
        if e.type == pygame.MOUSEWHEEL:
            self.sel = max(0, min(n - 1, self.sel - e.y * self.cols))
            return
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k == pygame.K_ESCAPE:
            self._close()
            return
        if k in (pygame.K_RETURN, pygame.K_SPACE):
            self._open_detail(self.sel)
            return
        if k == pygame.K_q:
            self.tab = (self.tab - 1) % len(CATEGORIES)
            self.sel = 0
        elif k == pygame.K_e:
            self.tab = (self.tab + 1) % len(CATEGORIES)
            self.sel = 0
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.sel = max(0, self.sel - 1)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.sel = min(n - 1, self.sel + 1)
        elif k in (pygame.K_UP, pygame.K_w):
            self.sel = max(0, self.sel - self.cols)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel = min(n - 1, self.sel + self.cols)

    def _handle_detail(self, e):
        n = len(self._entries[CATEGORIES[self.tab]])
        nview = len(self._detail_views())
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.detail_idx = None
            elif k in (pygame.K_LEFT, pygame.K_a):           # turn left / rotate
                if nview > 1:
                    self.view = (self.view - 1) % nview
                else:
                    self.spin = (self.spin - 15) % 360
            elif k in (pygame.K_RIGHT, pygame.K_d):          # turn right / rotate
                if nview > 1:
                    self.view = (self.view + 1) % nview
                else:
                    self.spin = (self.spin + 15) % 360
            elif k in (pygame.K_UP, pygame.K_w):
                self.zoom = min(5.0, self.zoom + 0.2)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.zoom = max(0.4, self.zoom - 0.2)
            elif k in (pygame.K_RETURN, pygame.K_SPACE):     # reset view/zoom/tilt
                self.view = 0
                self.spin = 0.0
                self.zoom = 1.0
            elif k == pygame.K_q:
                self.detail_idx = (self.detail_idx - 1) % n
                self._open_detail(self.detail_idx)
            elif k == pygame.K_e:
                self.detail_idx = (self.detail_idx + 1) % n
                self._open_detail(self.detail_idx)
            return
        if e.type == pygame.MOUSEWHEEL:
            self.zoom = max(0.4, min(5.0, self.zoom + e.y * 0.2))
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._drag = (e.pos[0], self.spin, False)
            return
        if e.type == pygame.MOUSEMOTION and self._drag:
            sx, s0, _ = self._drag
            self.spin = (s0 + (e.pos[0] - sx)) % 360
            self._drag = (sx, s0, True)
            return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self._drag and not self._drag[2]:    # a click (no drag) closes detail
                self.detail_idx = None
            self._drag = None
            return

    def _close(self):
        if self._on_close:
            self._on_close()
        else:
            self.g.state = "menu"

    def update(self, dt):
        pass    # no auto-rotation -- the model only turns when the player asks

    # ---- draw ----
    def draw(self, surf):
        ui_ = self.g.ui
        surf.fill((26, 24, 30))
        # the living title-screen diorama behind a deep dim (menu page only)
        scene = getattr(getattr(self.g, "menu", None), "scene", None)
        if scene is not None:
            try:
                t = getattr(self.g.menu, "t", 0.0)
                scene.draw(surf, t)
                dim = getattr(self, "_dim", None)
                if dim is None:
                    dim = self._dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    dim.fill((30, 20, 40, 110))       # the menu pages' soft dim
                surf.blit(dim, (0, 0))
            except Exception:
                surf.fill((26, 24, 30))
        from . import ui_kit as K
        detail = self.detail_idx is not None
        entries = self._entries[CATEGORIES[self.tab]]
        n = len(entries)
        grid_w = SCREEN_W - GRID_X - 70
        cols = self.cols
        rows_total = max(1, math.ceil(n / cols))
        visible_rows = max(1, (SCREEN_H - GRID_Y - 110) // CELL_H)
        list_h = visible_rows * CELL_H
        foot_y = GRID_Y + list_h + 22
        # the title menu's parchment card, ribbon title straddling its top edge
        card = pygame.Rect(24, CARD_Y, SCREEN_W - 48, foot_y + 30 - CARD_Y)
        K.modal(surf, card, "Gallery", K.font(28, True))

        # category tabs (clickable): each sized to its label, the row centred
        self._tab_rects = []
        tf = K.font(15, True)
        widths = [tf.size(c)[0] + 26 for c in CATEGORIES]
        gap = 8
        tx = card.centerx - (sum(widths) + gap * (len(widths) - 1)) // 2
        rects = []
        for i, bw in enumerate(widths):
            rect = pygame.Rect(tx, CARD_Y + 36, bw, 30)
            rects.append(rect)
            self._tab_rects.append((rect, i))
            tx += bw + gap
        K.tabs(surf, rects, CATEGORIES, self.tab, fnt_sizes=(15, 14, 13, 12))

        sel = min(self.sel, n - 1) if n else 0
        start_row, end_row = ui.scroll_window(rows_total, visible_rows, sel // cols)

        self._cell_rects = []
        for idx in range(start_row * cols, min(n, end_row * cols)):
            r = idx // cols - start_row
            c = idx % cols
            x = GRID_X + c * CELL_W
            y = GRID_Y + r * CELL_H
            self._cell_rects.append((pygame.Rect(x, y, CELL_W, CELL_H), idx))
            inner = pygame.Rect(x + 2, y + 2, CELL_W - 8, CELL_H - 8)
            if idx == sel:
                pygame.draw.rect(surf, K.HILITE, inner, border_radius=10)
                pygame.draw.rect(surf, K.GOLD_RIM, inner, 3, border_radius=10)
            else:
                K.well(surf, inner, radius=10)
            name, fn = entries[idx]
            art = self._art_for(idx, fn)
            labels = self._card_label(name)
            extra = 12 * (len(labels) - 1)          # a 2-line name borrows art room
            box_w, box_h = CELL_W - 22, CELL_H - 46 - extra          # 10 px under the rim, 8 above the name
            fitted = self._fit(art, box_w, box_h)
            cx = x + (CELL_W - 8) // 2
            surf.blit(fitted, (cx - fitted.get_width() // 2,
                               y + 12 + (box_h - fitted.get_height()) // 2))
            ly = y + CELL_H - 26 - extra
            for nm in labels:
                surf.blit(nm, (cx - nm.get_width() // 2, ly))
                ly += 12

        # scroll affordances in the card's wood/ink colours
        ui_.draw_scrollbar(surf, GRID_X + grid_w + 10, GRID_Y, list_h - 8,
                           rows_total, visible_rows, start_row,
                           track=K.WELL_LINE, thumb_col=K.WOOD)
        ui_.draw_scroll_arrows(surf, start_row, end_row, rows_total, GRID_X, GRID_Y,
                               cols * CELL_W - 8, list_h - 8, vertical=True, color=K.WOOD)

        if not detail:          # the detail view covers the grid; never ghost its footer
            K.blit_text(surf, K.font(14, True),
                        "Q/E or <- ->: category    WASD / arrows: move    ENTER / click: inspect"
                        "    ESC: back", K.INK_SOFT, (GRID_X + 4, foot_y), align="left")
            K.blit_text(surf, K.font(14, True), f"{CATEGORIES[self.tab]}: {n} models",
                        K.GOLD_TXT, (GRID_X + cols * CELL_W - 10, foot_y), align="right")
        else:
            self._draw_detail(surf)

    def _card_label(self, name):
        """Grid-card name fitted by PIXEL width (not a character count):
        one line, else two word-wrapped lines, '...' only as a last resort.
        Cached rendered lines."""
        cache = self.__dict__.setdefault("_label_cache", {})
        hit = cache.get(name)
        if hit is not None:
            return hit
        f = self.g.ui.tiny
        maxw = CELL_W - 16
        col = (74, 44, 36)                  # ui_kit.INK on the parchment cells
        if f.size(name)[0] <= maxw:
            lines = [name]
        else:
            lines, cur = [], ""
            for wd in name.split():
                cand = (cur + " " + wd).strip()
                if f.size(cand)[0] <= maxw or not cur:
                    cur = cand
                else:
                    lines.append(cur)
                    cur = wd
            if cur:
                lines.append(cur)
            if len(lines) > 2:
                lines = [lines[0], " ".join(lines[1:])]
            for i, ln in enumerate(lines):
                if f.size(ln)[0] > maxw:
                    while ln and f.size(ln + "...")[0] > maxw:
                        ln = ln[:-1]
                    lines[i] = ln.rstrip() + "..."
        out = [f.render(ln, True, col) for ln in lines[:2]]
        if len(cache) > 600:
            cache.clear()
        cache[name] = out
        return out

    def _draw_detail(self, surf):
        """Full-screen inspect overlay: one model shown big; turn it left/right
        (real facings for characters/monsters) and zoom in."""
        ui_ = self.g.ui
        entries = self._entries[CATEGORIES[self.tab]]
        idx = max(0, min(self.detail_idx, len(entries) - 1))
        name = entries[idx][0]
        views = self._detail_views()
        self.view %= max(1, len(views))
        from . import ui_kit as K
        vlabel, art = views[self.view]
        # every facing trimmed to what is drawn; one scale for all facings (from
        # the largest) so turning a character never changes its size
        crops = [self._crop(v[1]) for v in views]
        art = crops[self.view]
        K.dim(surf, 170)
        R = STAGE_R
        card = pygame.Rect(0, 0, 2 * R + 220, 2 * R + 130)
        # its ribbon title starts just under the grid's tab row (never on it)
        card.midtop = (SCREEN_W // 2, CARD_Y + 36 + 30 + 26)
        tf = K.fit_font(name, card.w - 150, (28, 24, 22, 20, 18), bold=True)
        K.modal(surf, card, name, tf)
        cx, cy = card.centerx, card.y + 60 + R
        # stage ring behind the model (a warm tan dish, so pale art still reads)
        pygame.draw.circle(surf, (226, 204, 168), (cx, cy), R)
        pygame.draw.circle(surf, (212, 188, 150), (cx, cy), R - 26, 2)
        pygame.draw.circle(surf, K.WOOD, (cx, cy), R, 3)
        aw = max(c.get_width() for c in crops)
        ah = max(c.get_height() for c in crops)
        # fit the model's bounding box INSIDE the ring (its half-diagonal < R),
        # then let small pixel art grow (nearest-neighbour) up to 14x
        base = min((R - 12) / max(1.0, 0.5 * math.hypot(aw, ah)), 14.0)
        scale = max(0.1, base * self.zoom)
        aw, ah = art.get_size()
        try:
            if self.spin:                            # free rotation while spinning
                img = pygame.transform.rotozoom(art, -self.spin, scale)
            elif scale >= 1.0:                       # crisp pixel art: nearest-neighbour,
                k = int(scale) if scale >= 3 else scale   # whole-number when it is big
                img = pygame.transform.scale(art, (max(1, int(aw * k)), max(1, int(ah * k))))
            else:                                    # big scenes shrinking: smooth
                img = pygame.transform.smoothscale(art, (max(1, int(aw * scale)),
                                                         max(1, int(ah * scale))))
        except Exception:
            img = art
        if self.zoom > 1.0 or self.spin:          # zoomed in: stay on the stage
            clip = surf.get_clip()
            surf.set_clip(card.inflate(-14, -14))
            surf.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))
            surf.set_clip(clip)
        else:
            surf.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))
        # labels: the subtitle on its own line between the ribbon and the ring
        facing = f"   -   {vlabel}" if len(views) > 1 else ""
        K.blit_text(surf, K.font(14, True), f"{CATEGORIES[self.tab]}   -   {idx + 1}/{len(entries)}"
                    f"{facing}   -   zoom {self.zoom:.1f}x", K.INK_SOFT, (cx, card.y + 42))
        turn = "<- ->: turn (front/back)" if len(views) > 1 else "<- -> / drag: rotate"
        hints = (f"{turn}    wheel / up-down: zoom",
                 "Q/E: prev-next    SPACE: reset    ESC / click: back")
        for j, hint in enumerate(hints):
            hf = K.fit_font(hint, card.w - 36, (14, 13, 12, 11), bold=True)
            K.blit_text(surf, hf, hint, K.INK_SOFT, (cx, card.bottom - 46 + j * 20))
