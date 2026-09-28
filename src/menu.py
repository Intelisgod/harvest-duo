"""Modern main menu, settings and how-to-play screens (keyboard + mouse)."""
import math
import random
import pygame
from .settings import (SCREEN_W, SCREEN_H, WHITE, GOLD, UI_BG, UI_BORDER,
                       P1_KEYS, P2_KEYS, DEFAULT_P1_KEYS, DEFAULT_P2_KEYS, KEY_ACTIONS)


from .ui import key_label as keyname      # single source for key names (ui.py)

from .ui_kit import (card_surface as _card, WOOD, CREAM, CREAM_HI, INK, INK_SOFT, SPROUT,
                     P_COL, blit_text)

ACCENT = (96, 206, 130)
ACCENT2 = (240, 205, 90)
_CTRL_STEP = 40           # Controls page row pitch (8 actions fit above the footer)
LEAF = (122, 182, 92)     # slider fill / toggle ON on the parchment cards
WELL = (240, 224, 194)    # recessed parchment (value boxes, slider track)
GOLD_RIM = (214, 160, 70)
WARN = (196, 72, 60)
# sub-page parchment cards: (width, height); centred in the band between the
# top of the screen (room for the title ribbon) and the footer hint
_PAGE_SIZE = {"settings": (560, 424), "controls": (660, 526),
              "online": (600, 444), "help": (720, 490)}
_BAND_TOP, _BAND_BOT = 60, SCREEN_H - 56


def _page_rect(page):
    pw, ph = _PAGE_SIZE[page]
    py = _BAND_TOP + max(0, (_BAND_BOT - _BAND_TOP - ph) // 2)
    return pygame.Rect(SCREEN_W // 2 - pw // 2, py, pw, ph)


def blit_centred(surf, font, text, color, center, align="center"):
    """Optically-centred text (see ui_kit.blit_text)."""
    return blit_text(surf, font, text, color, center, align)


def _reserved_keys():
    """Global single-purpose hotkeys a player action may not be bound to
    (Journal, Build/Decor, Inventory, fullscreen). Esc still cancels."""
    try:
        from .settings import JOURNAL_KEY, BUILD_KEY
    except Exception:                  # pragma: no cover
        JOURNAL_KEY, BUILD_KEY = pygame.K_j, pygame.K_b
    return {pygame.K_i, pygame.K_F11, JOURNAL_KEY, BUILD_KEY}


class Menu:
    def __init__(self, game):
        self.g = game
        self.page = "main"
        self.sel = 0
        self.t = 0.0
        self.trans = 1.0          # fade-in transition 1->0
        self.dragging = None
        self.binding = None       # (keys_dict, action) while waiting for a key press
        self.bind_msg = ""        # "J is reserved" note on the Controls page
        self.bind_msg_t = 0.0
        self.ip_text = ""       # host IP the joiner types on the Online page
        self.editing_ip = False   # True while capturing the IP text field
        self._gallery = None      # lazily-built GalleryScreen (the "gallery" page)
        self.title_font = pygame.font.SysFont("consolas", 76, bold=True)
        self.item_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.head_font = pygame.font.SysFont("consolas", 34, bold=True)   # card ribbons
        self.label_font = pygame.font.SysFont("consolas", 20, bold=True)  # card rows
        self.font = game.ui.font
        self.small = game.ui.small
        self.tiny = game.ui.tiny
        self.motes = [{"x": random.uniform(0, SCREEN_W), "y": random.uniform(0, SCREEN_H),
                       "r": random.uniform(1, 3), "s": random.uniform(8, 26),
                       "p": random.uniform(0, 6.28)} for _ in range(46)]
        self.vignette = self._make_vignette()
        # animated pixel diorama behind the menu (sky cycle, hills, farm, couple)
        try:
            from .menu_scene import TitleScene
            self.scene = TitleScene(game)
        except Exception:
            self.scene = None
        self._hover = {}          # row index -> 0..1 eased hover amount
        self._logo = None         # cached logo surface

    def _make_vignette(self):
        small = pygame.Surface((32, 18), pygame.SRCALPHA)
        cx, cy = 16, 9
        maxd = (cx * cx + cy * cy) ** 0.5
        for y in range(18):
            for x in range(32):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / maxd
                a = int(min(1.0, max(0.0, (d - 0.55) * 1.9)) * 90)
                small.set_at((x, y), (40, 20, 30, a))
        return pygame.transform.smoothscale(small, (SCREEN_W, SCREEN_H))

    # ---------- layout ----------
    def main_items(self):
        if self.g.started:
            first = ("Resume", "start")
        elif getattr(self.g, "has_save", False):
            first = ("Continue", "start")
        else:
            first = ("Start Game", "start")
        items = [first]
        if getattr(self.g, "net_mode", None) == "client":
            items.append(("Leave online game", "leave"))    # back to your own farm
        elif self.g.started or getattr(self.g, "has_save", False):
            items.append(("New Game", "new"))
        items += [("Online (LAN)", "online"), ("Gallery / Models", "gallery"),
                  ("Settings", "settings"), ("How to Play", "help"), ("Quit", "quit")]
        return items

    def layout(self):
        rows = []
        if self.page == "main":
            items = self.main_items()
            n = len(items)
            w, gap = 360, 14
            # band below the title block (ends ~274 with its bob) and ABOVE the
            # footer hint line (drawn at SCREEN_H-40): with 7 items the old
            # 300..690 band ran the last button into the hint text.
            top, bottom = 286, SCREEN_H - 56
            avail = bottom - top
            h = min(56, (avail - (n - 1) * gap) // n)   # shrink only if many items
            total = n * h + (n - 1) * gap
            y0 = top + (avail - total) // 2        # vertically centred in the band
            for i, (label, action) in enumerate(items):
                rect = pygame.Rect(SCREEN_W // 2 - w // 2, y0 + i * (h + gap), w, h)
                rows.append({"kind": "button", "label": label, "action": action, "hit": rect})
        elif self.page == "settings":
            P = _page_rect("settings")
            inner_l, inner_r = P.x + 40, P.right - 40
            ry = P.y + 58
            tog = pygame.Rect(inner_r - 104, ry + 1, 104, 36)
            rows.append({"kind": "toggle", "label": "Fullscreen", "action": "fullscreen",
                         "hit": pygame.Rect(inner_l, ry, inner_r - inner_l, 38), "ctrl": tog})
            for label, which in (("Master Volume", "master"), ("Sound Effects", "sfx"),
                                 ("Music", "music")):
                ry += 54
                # track ends leaving room for a right-aligned "100%"
                track = pygame.Rect(inner_r - 62 - 200, ry + 15, 200, 8)
                rows.append({"kind": "slider", "label": label, "which": which,
                             "hit": pygame.Rect(inner_l, ry, inner_r - inner_l, 38),
                             "track": track})
            ry += 66
            ctrl_btn = pygame.Rect(P.centerx - 190, ry, 380, 46)
            rows.append({"kind": "button", "label": "Controls (rebind keys)",
                         "action": "controls", "hit": ctrl_btn})
            ry += 62
            back = pygame.Rect(P.centerx - 90, ry, 180, 46)
            rows.append({"kind": "button", "label": "Back", "action": "back", "hit": back})
        elif self.page == "controls":
            P = _page_rect("controls")
            col_w = (P.w - 60 - 40) // 2
            col_x = {"p1": P.x + 30, "p2": P.x + 30 + col_w + 40}
            key_w = 130
            for which, kd in (("p1", P1_KEYS), ("p2", P2_KEYS)):
                for i, (act, label) in enumerate(KEY_ACTIONS):
                    ry = P.y + 118 + i * _CTRL_STEP    # below the PLAYER 1/2 headers
                    hit = pygame.Rect(col_x[which] + col_w - 14 - key_w, ry, key_w, 34)
                    rows.append({"kind": "rebind", "which": which, "act": act,
                                 "label": label, "kd": kd, "hit": hit,
                                 "lx": col_x[which] + 14, "col": (col_x[which], col_w)})
            # buttons follow however many actions exist (Core added 'Emote')
            rrow = P.y + 118 + len(KEY_ACTIONS) * _CTRL_STEP + 14
            # the pair is centred as a group; wide enough for "Reset to Defaults"
            bw1, bw2, gap = 320, 200, 24
            bx = P.centerx - (bw1 + gap + bw2) // 2
            rows.append({"kind": "button", "label": "Reset to Defaults",
                         "action": "resetkeys", "hit": pygame.Rect(bx, rrow, bw1, 46)})
            rows.append({"kind": "button", "label": "Back", "action": "back",
                         "hit": pygame.Rect(bx + bw1 + gap, rrow, bw2, 46)})
        elif self.page == "online":
            P = _page_rect("online")
            w = 440
            x = P.centerx - w // 2
            rows.append({"kind": "button", "label": "Host Game  (you are P1)",
                         "action": "host", "hit": pygame.Rect(x, P.y + 114, w, 52)})
            # the "Host IP" caption sits in the gap above the field, clear of
            # the Host button's selection glow
            rows.append({"kind": "ipfield", "label": "Host IP",
                         "action": "editip", "hit": pygame.Rect(x, P.y + 218, w, 46)})
            rows.append({"kind": "button", "label": "Join Game  (you are P2)",
                         "action": "join", "hit": pygame.Rect(x, P.y + 282, w, 52)})
            rows.append({"kind": "button", "label": "Back", "action": "back",
                         "hit": pygame.Rect(P.centerx - 90, P.y + 354, 180, 46)})
        else:  # help
            P = _page_rect("help")
            back = pygame.Rect(P.centerx - 90, P.bottom - 66, 180, 46)
            rows.append({"kind": "button", "label": "Back", "action": "back", "hit": back})
        return rows

    def _close_gallery(self):
        self.page = "main"; self.sel = 0; self.g.audio.play("ui_move")

    # ---------- update ----------
    def update(self, dt):
        if self.page == "gallery":
            self._gallery.update(dt)
            self.t += dt                      # keep the backdrop diorama alive
            if self.scene is not None:
                self.scene.update(dt, self.t)
            return
        self.t += dt
        if self.bind_msg_t > 0:
            self.bind_msg_t = max(0.0, self.bind_msg_t - dt)
        if self.trans > 0:
            self.trans = max(0.0, self.trans - dt * 2.5)
        if self.scene is not None:
            self.scene.update(dt, self.t)
        rows = len(self.layout()) if self.page != "gallery" else 0
        for i in range(rows):
            want = 1.0 if i == self.sel else 0.0
            cur = self._hover.get(i, 0.0)
            self._hover[i] = cur + (want - cur) * min(1.0, dt * 14)
        for m in self.motes:
            m["y"] -= m["s"] * dt
            if m["y"] < -5:
                m["y"] = SCREEN_H + 5
                m["x"] = random.uniform(0, SCREEN_W)

    def _slider_val(self, which):
        a = self.g.audio
        return {"master": a.master, "sfx": a.sfx_vol, "music": a.music_vol}[which]

    def _set_slider(self, which, v):
        a = self.g.audio
        v = max(0.0, min(1.0, v))
        if which == "master":
            a.set_master(v)
        elif which == "sfx":
            a.set_sfx(v)
        else:
            a.set_music(v)
        if hasattr(self.g, "save_settings"):
            self.g.save_settings()

    # ---------- input ----------
    def handle_event(self, e):
        # capturing a new key binding takes priority over everything else
        if self.binding is not None:
            if e.type == pygame.KEYDOWN:
                if e.key in _reserved_keys():
                    # global hotkeys (Journal, Build/Decor, Inventory, F11) can't
                    # become a player action -- they would fight each other
                    self.g.audio.play("error")
                    self.bind_msg = f"{keyname(e.key)} is reserved - pick another key"
                    self.bind_msg_t = 2.5
                    return                    # keep waiting for a valid key
                if e.key != pygame.K_ESCAPE:
                    kd, act = self.binding
                    kd[act] = e.key
                    if hasattr(self.g, "save_settings"):
                        self.g.save_settings()
                    self.g.audio.play("ui_select")
                else:
                    self.g.audio.play("ui_move")
                self.binding = None
            return
        if self.editing_ip:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_RETURN:
                    self.editing_ip = False
                    if self.ip_text:
                        self.g.start_client(self.ip_text)
                elif e.key == pygame.K_ESCAPE:
                    self.editing_ip = False
                elif e.key == pygame.K_BACKSPACE:
                    self.ip_text = self.ip_text[:-1]
                else:
                    ch = e.unicode
                    if ch and (ch.isdigit() or ch in ".:") and len(self.ip_text) < 21:
                        self.ip_text += ch
            return
        if self.page == "gallery":
            self._gallery.handle_event(e)
            return
        rows = self.layout()
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE,):
                if self.page == "controls":
                    self.page = "settings"; self.sel = 0; self.g.audio.play("ui_move")
                elif self.page != "main":
                    self.page = "main"; self.sel = 0; self.g.audio.play("ui_move")
                elif self.g.started:
                    self.g.state = "play"
                return
            if e.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(rows); self.g.audio.play("ui_move")
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(rows); self.g.audio.play("ui_move")
            elif e.key in (pygame.K_LEFT, pygame.K_a):
                self._adjust(rows[self.sel], -0.05)
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                self._adjust(rows[self.sel], +0.05)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(rows[self.sel])
            return

        if e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(rows):
                if r["hit"].collidepoint(e.pos):
                    if self.sel != i:
                        self.sel = i; self.g.audio.play("ui_move")
                    break
            if self.dragging is not None:
                self._drag_to(e.pos)
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(rows):
                if r["hit"].collidepoint(e.pos):
                    self.sel = i
                    if r["kind"] == "slider":
                        self.dragging = r["which"]
                        self._drag_to(e.pos)
                    else:
                        self._activate(r)
                    return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dragging = None

    def _drag_to(self, pos):
        for r in self.layout():
            if r.get("kind") == "slider" and r["which"] == self.dragging:
                track = r["track"]
                self._set_slider(self.dragging, (pos[0] - track.x) / track.w)
                return

    def _adjust(self, row, delta):
        if row["kind"] == "slider":
            self._set_slider(row["which"], self._slider_val(row["which"]) + delta)
            self.g.audio.play("ui_move")
        elif row["kind"] == "toggle":
            self._activate(row)

    def _activate(self, row):
        if row["kind"] == "toggle":
            self.g.toggle_fullscreen(); self.g.audio.play("ui_toggle"); return
        if row["kind"] == "slider":
            return
        if row["kind"] == "rebind":
            self.binding = (row["kd"], row["act"])
            self.g.audio.play("ui_select")
            return
        act = row["action"]
        self.g.audio.play("ui_select")
        if act == "online":
            self.page = "online"; self.sel = 0
            return
        if act == "host":
            self.g.start_host()
            return
        if act == "editip":
            self.editing_ip = True
            return
        if act == "join":
            if self.ip_text:
                self.g.start_client(self.ip_text)
            else:
                self.editing_ip = True      # nudge them to type an IP first
            return
        if act == "controls":
            self.page = "controls"; self.sel = 0
            return
        if act == "resetkeys":
            P1_KEYS.update(DEFAULT_P1_KEYS)
            P2_KEYS.update(DEFAULT_P2_KEYS)
            if hasattr(self.g, "save_settings"):
                self.g.save_settings()
            self.g.audio.play("ui_toggle")
            return
        if act == "start":
            if self.g.started or getattr(self.g, "has_save", False):
                self.g.begin_play()
            else:
                self.g.open_creator()
        elif act == "new":
            self.g.open_creator()
        elif act == "leave":
            if hasattr(self.g, "net_leave"):
                self.g.net_leave()
            self.sel = 0
        elif act == "gallery":
            # hosted as a menu PAGE so it runs under the existing state=="menu"
            # dispatch (no Core wiring needed) -- ESC returns to the main page
            if getattr(self, "_gallery", None) is None:
                from .gallery import GalleryScreen
                self._gallery = GalleryScreen(self.g, on_close=self._close_gallery)
            self._gallery.tab = 0
            self._gallery.sel = 0
            self.page = "gallery"
        elif act == "settings":
            self.page = "settings"; self.sel = 0
        elif act == "help":
            self.page = "help"; self.sel = 0
        elif act == "back":
            self.page = "main"; self.sel = 0
        elif act == "quit":
            self.g.running = False

    # ---------- draw ----------
    def draw(self, surf):
        if self.page == "gallery":
            self._gallery.draw(surf)
            return
        self._draw_bg(surf)
        if self.page == "main":
            self._draw_main(surf)
        elif self.page == "settings":
            self._draw_settings(surf)
        elif self.page == "controls":
            self._draw_controls(surf)
        elif self.page == "online":
            self._draw_online(surf)
        else:
            self._draw_help(surf)
        surf.blit(self.vignette, (0, 0))
        # footer (on a soft pill so it reads over the bright scenery)
        hint = "Arrow/WASD: navigate   Enter: select   Esc: back" + \
               ("   (game paused)" if self.g.started and self.page == "main" else "")
        h = self.small.render(hint, True, (250, 244, 232))
        pill = pygame.Surface((h.get_width() + 28, h.get_height() + 10), pygame.SRCALPHA)
        pygame.draw.rect(pill, (40, 28, 36, 170), pill.get_rect(), border_radius=12)
        surf.blit(pill, (SCREEN_W // 2 - pill.get_width() // 2, SCREEN_H - 45))
        surf.blit(h, (SCREEN_W // 2 - h.get_width() // 2, SCREEN_H - 40))
        v = self.tiny.render("Harvest Duo  v1.1", True, (70, 60, 80))
        surf.blit(v, (SCREEN_W - v.get_width() - 14, 12))
        if self.trans > 0:
            # soft cream fade-in: bright from the very first frame (was black)
            ov = pygame.Surface((SCREEN_W, SCREEN_H))
            ov.set_alpha(int(self.trans * 170)); ov.fill((255, 246, 232))
            surf.blit(ov, (0, 0))

    def _draw_bg(self, surf):
        if self.scene is not None:
            try:
                self.scene.draw(surf, self.t)
                if self.page != "main":        # calmer backdrop behind the panels
                    dim = getattr(self, "_dim", None)
                    if dim is None:
                        dim = self._dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                        dim.fill((30, 20, 40, 90))
                    surf.blit(dim, (0, 0))
                return
            except Exception:
                self.scene = None              # fall back to the classic backdrop
        top = (20, 32, 30)
        bot = (12, 18, 24)
        for y in range(0, SCREEN_H, 4):
            f = y / SCREEN_H
            c = (int(top[0] + (bot[0] - top[0]) * f),
                 int(top[1] + (bot[1] - top[1]) * f),
                 int(top[2] + (bot[2] - top[2]) * f))
            pygame.draw.rect(surf, c, (0, y, SCREEN_W, 4))
        # soft drifting glow blobs
        for k, cx in enumerate((SCREEN_W * 0.25, SCREEN_W * 0.75)):
            r = 220 + int(30 * math.sin(self.t * 0.6 + k))
            blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            col = ACCENT if k == 0 else (70, 110, 180)
            pygame.draw.circle(blob, (col[0], col[1], col[2], 22), (r, r), r)
            surf.blit(blob, (cx - r, SCREEN_H * 0.5 - r))
        # fireflies
        for m in self.motes:
            a = int(120 + 110 * math.sin(self.t * 2 + m["p"]))
            s = pygame.Surface((m["r"] * 4, m["r"] * 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (200, 240, 170, max(0, a)),
                               (int(m["r"] * 2), int(m["r"] * 2)), int(m["r"]))
            surf.blit(s, (m["x"], m["y"]))

    def _make_logo(self):
        """Logo: warm gradient letters, thick dark outline, drop shadow, a
        sprout on the left and a heart on the right. Built once."""
        text = "HARVEST DUO"
        f = self.title_font
        body = f.render(text, True, (255, 255, 255))
        w, h = body.get_size()
        grad = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            k = y / max(1, h - 1)
            c = (255, int(246 - 70 * k), int(170 - 110 * k))
            pygame.draw.line(grad, c, (0, y), (w, y))
        body = body.copy()
        body.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        outline = f.render(text, True, (74, 44, 40))
        pad = 64
        out = pygame.Surface((w + pad * 2, h + 20), pygame.SRCALPHA)
        shadow = f.render(text, True, (40, 20, 30))
        shadow.set_alpha(110)
        out.blit(shadow, (pad + 6, 12))
        for ox in range(-4, 5, 2):
            for oy in range(-4, 5, 2):
                if ox or oy:
                    out.blit(outline, (pad + ox, 4 + oy))
        out.blit(body, (pad, 4))
        # highlight line across the letters' top
        hl = f.render(text, True, (255, 255, 240))
        hl.set_alpha(70)
        out.blit(hl, (pad, 2), area=pygame.Rect(0, 0, w, h // 3))
        # sprout (left) and heart (right)
        sx, sy = 30, h // 2 + 8
        pygame.draw.line(out, (74, 44, 40), (sx, sy + 16), (sx, sy - 6), 6)
        pygame.draw.line(out, (120, 190, 90), (sx, sy + 15), (sx, sy - 5), 3)
        for dx, col in ((-10, (120, 200, 96)), (10, (150, 214, 110))):
            pygame.draw.ellipse(out, (74, 44, 40), (sx + dx - 11, sy - 18, 22, 14))
            pygame.draw.ellipse(out, col, (sx + dx - 8, sy - 16, 16, 9))
        hx, hy = w + pad + 30, h // 2 + 4
        for dx in (-7, 7):
            pygame.draw.circle(out, (74, 44, 40), (hx + dx, hy - 4), 11)
        pygame.draw.polygon(out, (74, 44, 40), [(hx - 18, hy), (hx + 18, hy), (hx, hy + 20)])
        for dx in (-7, 7):
            pygame.draw.circle(out, (244, 104, 136), (hx + dx, hy - 4), 8)
        pygame.draw.polygon(out, (244, 104, 136), [(hx - 14, hy - 1), (hx + 14, hy - 1), (hx, hy + 15)])
        pygame.draw.circle(out, (255, 214, 224), (hx - 8, hy - 7), 2)
        return out

    def _draw_title(self, surf):
        if self._logo is None:
            self._logo = self._make_logo()
        cx = SCREEN_W // 2
        bob = math.sin(self.t * 1.6) * 5
        tilt = math.sin(self.t * 0.8) * 1.2
        logo = pygame.transform.rotozoom(self._logo, tilt, 1.0) if abs(tilt) > 0.05 else self._logo
        y = 118 + int(bob)
        surf.blit(logo, (cx - logo.get_width() // 2, y - (logo.get_height() - self._logo.get_height()) // 2))
        # subtitle ribbon
        sub = self.font.render("Two-player co-op farming  -  share one keyboard", True, (80, 46, 40))
        rw, rh = sub.get_width() + 56, sub.get_height() + 12
        ry = 214
        rib = pygame.Rect(cx - rw // 2, ry, rw, rh)
        pygame.draw.polygon(surf, (206, 150, 110), [(rib.x - 16, ry + 4), (rib.x + 4, ry + 4),
                                                    (rib.x + 4, ry + rh + 4), (rib.x - 16, ry + rh + 4),
                                                    (rib.x - 8, ry + rh // 2 + 4)])
        pygame.draw.polygon(surf, (206, 150, 110), [(rib.right + 16, ry + 4), (rib.right - 4, ry + 4),
                                                    (rib.right - 4, ry + rh + 4), (rib.right + 16, ry + rh + 4),
                                                    (rib.right + 8, ry + rh // 2 + 4)])
        pygame.draw.rect(surf, (250, 236, 206), rib, border_radius=6)
        pygame.draw.rect(surf, (196, 140, 100), rib, 2, border_radius=6)
        surf.blit(sub, (cx - sub.get_width() // 2, ry + 6))

    def _draw_main(self, surf):
        self._draw_title(surf)
        for i, r in enumerate(self.layout()):
            self._button(surf, r["hit"], r["label"], i == self.sel, hover=self._hover.get(i))

    def _button(self, surf, rect, label, selected, font=None, hover=None):
        """Parchment button with a wooden rim. The selected one grows, glows
        gold and gets a bouncing sprout marker; ``hover`` (0..1) eases it."""
        font = font or self.item_font
        hv = (1.0 if selected else 0.0) if hover is None else max(0.0, min(1.0, hover))
        grow = int(8 * hv)
        rr = rect.inflate(grow, grow)
        rr.y -= int(2 * hv)
        # drop shadow
        sh = pygame.Surface((rr.w, rr.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (40, 20, 30, 90), sh.get_rect(), border_radius=14)
        surf.blit(sh, (rr.x + 3, rr.y + 5))
        base = (250, 238, 212) if not selected else (255, 224, 150)
        face = tuple(int(base[k] * (0.92 + 0.08 * hv)) for k in range(3))
        pygame.draw.rect(surf, (138, 94, 64), rr, border_radius=14)                   # wood rim
        inner = rr.inflate(-6, -6)
        pygame.draw.rect(surf, face, inner, border_radius=11)
        pygame.draw.rect(surf, (255, 255, 244), (inner.x + 6, inner.y + 3, inner.w - 12, 4),
                         border_radius=2)                                              # sheen
        if hv > 0.05:
            glow = pygame.Surface((rr.w + 24, rr.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 220, 120, int(70 * hv)), glow.get_rect(), 6,
                             border_radius=20)
            surf.blit(glow, (rr.x - 12, rr.y - 12))
        if selected:
            b = int(abs(math.sin(self.t * 5)) * 4)
            mx, my = rr.x + 22 + b, rr.centery
            pygame.draw.polygon(surf, (92, 150, 70), [(mx - 7, my - 7), (mx + 3, my), (mx - 7, my + 7)])
            mx2 = rr.right - 22 - b
            pygame.draw.polygon(surf, (92, 150, 70), [(mx2 + 7, my - 7), (mx2 - 3, my), (mx2 + 7, my + 7)])
        col = (74, 44, 36) if selected else (110, 78, 60)
        blit_centred(surf, font, label, col, rr.center)

    # ---------- sub-page cards (the creator's parchment look) ----------
    def _draw_card(self, surf, page, title):
        """Parchment card with a wooden rim, and its title on the title
        screen's folded ribbon straddling the top edge, centred."""
        P = _page_rect(page)
        surf.blit(_card(P.w, P.h), (P.x - 4, P.y - 2))
        t = self.head_font.render(title, True, INK)
        rw, rh = t.get_width() + 72, t.get_height() + 14
        rib = pygame.Rect(P.centerx - rw // 2, P.y - rh // 2 - 4, rw, rh)
        ry = rib.y
        tail = (206, 150, 110)
        pygame.draw.polygon(surf, tail, [(rib.x - 22, ry + 6), (rib.x + 4, ry + 6),
                                         (rib.x + 4, ry + rh + 6), (rib.x - 22, ry + rh + 6),
                                         (rib.x - 12, ry + rh // 2 + 6)])
        pygame.draw.polygon(surf, tail, [(rib.right + 22, ry + 6), (rib.right - 4, ry + 6),
                                         (rib.right - 4, ry + rh + 6), (rib.right + 22, ry + rh + 6),
                                         (rib.right + 12, ry + rh // 2 + 6)])
        pygame.draw.rect(surf, (250, 236, 206), rib, border_radius=6)
        pygame.draw.rect(surf, (196, 140, 100), rib, 2, border_radius=6)
        blit_centred(surf, self.head_font, title, INK, rib.center)
        return P

    def _row_cursor(self, surf, band):
        """Keyboard highlight behind a card row (same as the creator's)."""
        pulse = 0.5 + 0.5 * math.sin(self.t * 5)
        pygame.draw.rect(surf, (252, 226, 164), band, border_radius=10)
        rim = tuple(int(a + (b - a) * pulse) for a, b in zip(GOLD_RIM, (240, 192, 104)))
        pygame.draw.rect(surf, rim, band, 2, border_radius=10)
        mx, my = band.x + 5, band.centery
        pygame.draw.polygon(surf, SPROUT, [(mx, my - 5), (mx + 6, my), (mx, my + 5)])

    def _divider(self, surf, cx, y, half):
        """Thin rule with a small heart in the middle."""
        pygame.draw.line(surf, (214, 190, 160), (cx - half, y), (cx - 14, y), 2)
        pygame.draw.line(surf, (214, 190, 160), (cx + 14, y), (cx + half, y), 2)
        for dx in (-3, 3):
            pygame.draw.circle(surf, (228, 128, 150), (cx + dx, y - 2), 4)
        pygame.draw.polygon(surf, (228, 128, 150), [(cx - 7, y - 1), (cx + 7, y - 1), (cx, y + 6)])

    def _text_line(self, font, text, color, cx, y):
        """One line of text horizontally centred on ``cx`` with its top at ``y``."""
        t = font.render(text, True, color)
        return t, (cx - t.get_width() // 2, y)

    def _draw_settings(self, surf):
        self._draw_card(surf, "settings", "Settings")
        for i, r in enumerate(self.layout()):
            hot = (i == self.sel)
            hit = r["hit"]
            if r["kind"] in ("toggle", "slider") and hot:
                self._row_cursor(surf, hit.inflate(28, 8))
            if r["kind"] == "toggle":
                blit_centred(surf, self.label_font, r["label"], INK, (hit.x + 14, hit.centery),
                             align="left")
                on = self.g.fullscreen
                pill = r["ctrl"]
                pygame.draw.rect(surf, LEAF if on else (212, 196, 170), pill, border_radius=18)
                pygame.draw.rect(surf, INK_SOFT, pill, 2, border_radius=18)
                knob = pygame.Rect(pill.right - 34 if on else pill.x + 2, pill.y + 2, 32, 32)
                pygame.draw.ellipse(surf, CREAM_HI, knob)
                pygame.draw.ellipse(surf, INK_SOFT, knob, 2)
                txt_cx = (pill.x + knob.x) // 2 if on else (knob.right + pill.right) // 2
                blit_centred(surf, self.label_font, "ON" if on else "OFF",
                             CREAM_HI if on else INK_SOFT, (txt_cx, pill.centery))
            elif r["kind"] == "slider":
                blit_centred(surf, self.label_font, r["label"], INK, (hit.x + 14, hit.centery),
                             align="left")
                track = r["track"]
                val = self._slider_val(r["which"])
                well = track.inflate(0, 4)
                pygame.draw.rect(surf, WELL, well, border_radius=6)
                pygame.draw.rect(surf, (206, 184, 150), well, 1, border_radius=6)
                pygame.draw.rect(surf, LEAF, (well.x, well.y, int(well.w * val), well.h),
                                 border_radius=6)
                kx = track.x + int(track.w * val)
                pygame.draw.circle(surf, CREAM_HI, (kx, track.centery), 10)
                pygame.draw.circle(surf, WOOD, (kx, track.centery), 10, 3)
                blit_centred(surf, self.label_font, f"{int(val * 100)}%", INK_SOFT,
                             (hit.right - 14, hit.centery), align="right")
            else:
                self._button(surf, hit, r["label"], hot, hover=self._hover.get(i))

    def _draw_controls(self, surf):
        P = self._draw_card(surf, "controls", "Controls")
        rows = self.layout()
        if self.bind_msg_t > 0 and self.bind_msg:
            t, pos = self._text_line(self.font, self.bind_msg, WARN, P.centerx, P.y + 40)
        else:
            t, pos = self._text_line(self.font, "Click a key, then press the new key  -  Esc to cancel",
                                     INK_SOFT, P.centerx, P.y + 40)
        surf.blit(t, pos)
        # PLAYER headers centred over their columns, each on a soft tinted plate
        cols = {}
        for r in rows:
            if r["kind"] == "rebind":
                cols.setdefault(r["which"], r["col"])
        for n, which in enumerate(("p1", "p2")):
            if which not in cols:
                continue
            cx0, cw = cols[which]
            plate = pygame.Rect(cx0, P.y + 70, cw, 38)
            tint = P_COL[n]
            pygame.draw.rect(surf, tuple(int(c * 0.22 + 244 * 0.78) for c in tint), plate,
                             border_radius=10)
            blit_centred(surf, self.item_font, f"PLAYER {n + 1}", tint, plate.center)
        for i, r in enumerate(rows):
            hot = (i == self.sel)
            if r["kind"] == "rebind":
                box = r["hit"]
                cx0, cw = r["col"]
                if hot:
                    self._row_cursor(surf, pygame.Rect(cx0, box.y - 3, cw, box.h + 6))
                blit_centred(surf, self.label_font, r["label"], INK, (r["lx"], box.centery),
                             align="left")
                binding_here = self.binding == (r["kd"], r["act"])
                pygame.draw.rect(surf, (255, 232, 170) if binding_here else
                                 (CREAM_HI if hot else WELL), box, border_radius=8)
                pygame.draw.rect(surf, GOLD_RIM if (binding_here or hot) else INK_SOFT,
                                 box, 2, border_radius=8)
                txt = "press a key..." if binding_here else keyname(r["kd"][r["act"]])
                blit_centred(surf, self.small if binding_here else self.label_font, txt,
                             WARN if binding_here else INK, box.center)
            else:
                self._button(surf, r["hit"], r["label"], hot, hover=self._hover.get(i))

    def _draw_online(self, surf):
        P = self._draw_card(surf, "online", "Online LAN")
        try:
            from .net.transport import local_ip
            myip = local_ip()
        except Exception:
            myip = "?"
        t, pos = self._text_line(self.font, "Same Wi-Fi only", INK_SOFT, P.centerx, P.y + 38)
        surf.blit(t, pos)
        # "Your IP" on a small plate so it is easy to read out to P2
        cap = self.font.render("Your IP (give to P2):  ", True, INK)
        ip = self.label_font.render(myip, True, INK)
        w = cap.get_width() + ip.get_width()
        plate = pygame.Rect(P.centerx - w // 2 - 16, P.y + 62, w + 32, 30)
        pygame.draw.rect(surf, WELL, plate, border_radius=8)
        x = plate.x + 16
        blit_centred(surf, self.font, "Your IP (give to P2):  ", INK, (x, plate.centery),
                     align="left")
        blit_centred(surf, self.label_font, myip, INK, (x + cap.get_width(), plate.centery),
                     align="left")
        for i, r in enumerate(self.layout()):
            hot = (i == self.sel)
            if r["kind"] == "ipfield":
                box = r["hit"]
                t, pos = self._text_line(self.label_font, "Host IP", INK, box.centerx, box.y - 30)
                surf.blit(t, pos)
                editing = self.editing_ip
                pygame.draw.rect(surf, CREAM_HI if (editing or hot) else WELL, box, border_radius=10)
                pygame.draw.rect(surf, GOLD_RIM if (editing or hot) else INK_SOFT, box,
                                 3 if editing else 2, border_radius=10)
                if self.ip_text:
                    caret = "_" if (editing and int(self.t * 2) % 2 == 0) else " "
                    blit_centred(surf, self.label_font, self.ip_text + caret, INK, box.center)
                else:
                    blit_centred(surf, self.font, "type IP then Enter..." if editing else
                                 "click to type host IP", (176, 150, 128), box.center)
            else:
                self._button(surf, r["hit"], r["label"], hot, hover=self._hover.get(i))
        status = getattr(self.g, "net_status", "") or ""
        if status:
            t, pos = self._text_line(self.font, status, (150, 96, 30), P.centerx, P.bottom - 36)
            surf.blit(t, pos)

    def _help_player_font(self, texts, maxw):
        """Largest font in which EVERY text fits ``maxw`` px (cached per
        text set, i.e. per binding set)."""
        cache = self.__dict__.setdefault("_help_font_cache", {})
        key = (tuple(texts), maxw)
        f = cache.get(key)
        if f is None:
            cands = [self.font, self.small]
            for size in (13, 12, 11, 10):
                cands.append(pygame.font.SysFont("consolas", size))
            f = cands[-1]
            for c in cands:
                if all(c.size(t)[0] <= maxw for t in texts):
                    f = c
                    break
            if len(cache) > 16:
                cache.clear()
            cache[key] = f
        return f

    def _draw_help(self, surf):
        P = self._draw_card(surf, "help", "How to Play")
        try:
            from .settings import JOURNAL_KEY, BUILD_KEY
        except Exception:                  # pragma: no cover
            JOURNAL_KEY, BUILD_KEY = pygame.K_j, pygame.K_b

        def move(K):
            ks = [K.get(a) for a in ("up", "left", "down", "right")]
            if ks == [pygame.K_UP, pygame.K_LEFT, pygame.K_DOWN, pygame.K_RIGHT]:
                return "Arrows"
            return " ".join(keyname(k) for k in ks)

        def row(K):
            # every key name comes from the live bindings (follows rebinding)
            # 'Prev X  Next Y' (not 'X / Y': '/' is P2's default Emote key)
            txt = (f"Move {move(K)}  Use {keyname(K.get('action'))}"
                   f"  Prev {keyname(K.get('prev'))}  Next {keyname(K.get('next'))}")
            if K.get("emote") is not None:
                txt += f"  Emote {keyname(K['emote'])}"
            return txt

        maxw = P.w - 64
        # player control lines: a coloured "PLAYER n" tag + the keys, each pair
        # centred; ONE font for both (the largest that fits both)
        prow = [row(P1_KEYS), row(P2_KEYS)]
        tag_w = self.label_font.size("PLAYER 1")[0] + 18
        pfont = self._help_player_font(prow, maxw - tag_w - 12)
        y = P.y + 42
        for n, txt in enumerate(prow):
            tw = pfont.size(txt)[0]
            x = P.centerx - (tag_w + 12 + tw) // 2
            tag = pygame.Rect(x, y, tag_w, 26)
            pygame.draw.rect(surf, P_COL[n], tag, border_radius=8)
            blit_centred(surf, self.label_font, f"PLAYER {n + 1}", CREAM_HI, tag.center)
            blit_centred(surf, pfont, txt, INK, (tag.right + 12 + tw // 2, tag.centery))
            y += 34
        keys = f"{keyname(JOURNAL_KEY)}: journal   I: inventory   F11: fullscreen   Esc: menu"
        kf = self.font if self.font.size(keys)[0] <= maxw else self.small
        t, pos = self._text_line(kf, keys, INK_SOFT, P.centerx, y + 2)
        surf.blit(t, pos)
        y += 40
        self._divider(surf, P.centerx, y, P.w // 2 - 70)
        y += 18
        tips = [
            ("Farm", "Hoe to till, plant a seed, then Watering Can.",
             "Crops grow over days - sleep in your bed to advance."),
            ("Town", "Walk the bottom path: talk to villagers,",
             "fish at the pond (Rod), buy & sell at the Shop."),
            ("Mine", "From town go bottom-left: break rocks",
             "(Pickaxe) for ore, fight slimes (Sword)."),
            ("Decor", f"{keyname(BUILD_KEY)} on the farm: outdoor decor.  At home: furniture.", None),
            ("Gifts", "Face your partner holding an item + Use.", None),
            ("Map", "The minimap (top-left) shows arrows to each map.", None),
        ]
        # tips read best left-aligned, so the block itself is centred in the card
        gap = 14
        head_w = max(self.label_font.size(h)[0] for h, *_ in tips)
        body_w = max(self.font.size(s)[0] for _, a, b in tips for s in (a, b) if s)
        bx = P.centerx - (head_w + gap + body_w) // 2
        for head, a, b in tips:
            h = self.label_font.render(head, True, SPROUT)
            surf.blit(h, (bx + head_w - h.get_width(), y))
            for s in (a, b):
                if s:
                    surf.blit(self.font.render(s, True, INK), (bx + head_w + gap, y + 1))
                    y += 24
            y += 5
        for r in self.layout():
            self._button(surf, r["hit"], r["label"], self.sel == 0)
