"""Heart Pong on the arcade cabinet (state "arcade").

Owner: Showpieces (2026-09-28). Glue lives in ``systems/showpiece_system.py``.

Classic two-paddle pong with a bouncing heart for a ball; first to 5 wins.

* Local co-op: the two farmers' own keys -- Player 1's Up / Down (W / S)
  moves the left paddle, Player 2's Up / Down (the arrows) the right one.
  Tab on the title card switches to a game against the CPU.
* LAN (host or client): a game against the CPU (either set of keys).
* The CPU is fair: it reacts a beat late, can't move as fast as a player and
  aims a little off, so fast angled shots beat it.
* Space / Enter starts, serves and asks for a rematch; X switches the cabinet
  off and leaves; Esc leaves it glowing. Results go to the farm's saved
  scoreboard (``game.pong_stats``) through ``game._pong_result``.
"""
import math
import random

import pygame

from .settings import SCREEN_W, SCREEN_H, P1_KEYS, P2_KEYS
from . import ui_kit as K

WIN = 5
PAD_W, PAD_H = 14, 86
PAD_SPEED = 470.0
CPU_SPEED = 330.0
BALL_R = 11
BALL_V0 = 360.0
BALL_VMAX = 820.0
SPEEDUP = 1.06
CPU_COL = (170, 150, 200)


def heart(surf, cx, cy, r, col, alpha=None):
    """A little heart centred on (cx, cy), about 2r wide."""
    if alpha is not None:
        g = pygame.Surface((int(r * 2.6) + 4, int(r * 2.6) + 4), pygame.SRCALPHA)
        heart(g, g.get_width() / 2, g.get_height() / 2, r, col + (alpha,))
        surf.blit(g, (cx - g.get_width() / 2, cy - g.get_height() / 2))
        return
    rr = max(1, int(r * 0.55))
    pygame.draw.circle(surf, col, (int(cx - r * 0.45), int(cy - r * 0.25)), rr)
    pygame.draw.circle(surf, col, (int(cx + r * 0.45), int(cy - r * 0.25)), rr)
    pygame.draw.polygon(surf, col, [(cx - r * 0.98, cy - r * 0.1), (cx + r * 0.98, cy - r * 0.1),
                                    (cx, cy + r * 0.95)])


_SCAN = {}


def _scanlines(size):
    s = _SCAN.get(size)
    if s is None:
        s = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(0, size[1], 3):
            pygame.draw.line(s, (0, 0, 0, 34), (0, y), (size[0], y))
        _SCAN[size] = s
    return s


class HeartPong:
    """Full-screen Heart Pong for player ``pidx`` at the Placed ``cabinet``."""

    def __init__(self, game, pidx, cabinet, client=False, vs_cpu=None):
        self.g = game
        self.pidx = pidx
        self.cab = cabinet
        self.client = client
        self.local = getattr(game, "net_mode", None) not in ("host", "client")
        self.vs_cpu = (not self.local) if vs_cpu is None else (bool(vs_cpu) or not self.local)
        self.card = pygame.Rect(70, 40, SCREEN_W - 140, SCREEN_H - 74)
        self.court = pygame.Rect(130, 162, SCREEN_W - 260, 420)
        self.held = set()
        self.t = 0.0
        self.phase = "title"
        self.phase_t = 0.0
        self.score = [0, 0]
        self.rally = 0
        self.best_rally = 0
        self.server = random.choice((0, 1))
        self.last_point = None
        self.winner = None
        self.trail = []
        self.confetti = []
        self.result_msg = ""
        self.cpu_err = 0.0
        self.cpu_t = 0.0
        self.cpu_target = float(self.court.centery)
        self.closed = False
        self.pad = [float(self.court.centery), float(self.court.centery)]
        self._reset_ball()

    # ------------------------------------------------------------ helpers
    def names(self):
        ps = self.g.players
        if self.vs_cpu:
            me = ps[self.pidx].name if self.pidx < len(ps) else "You"
            return [me, "CPU"]
        return [ps[0].name, ps[1].name]

    def colors(self):
        me = K.P_COL[self.pidx % 2] if self.vs_cpu else K.P_COL[0]
        return [me, CPU_COL if self.vs_cpu else K.P_COL[1]]

    def _reset_ball(self):
        self.bx, self.by = float(self.court.centerx), float(self.court.centery)
        self.vx = self.vy = 0.0
        self.trail = []

    def _launch(self):
        d = 1 if self.server == 0 else -1          # the server sends it to the other side
        ang = random.uniform(-0.45, 0.45)
        self.vx = math.cos(ang) * BALL_V0 * d
        self.vy = math.sin(ang) * BALL_V0
        self.rally = 0
        self.cpu_err = random.gauss(0, 16)

    def start(self):
        """Title / game over -> a fresh game."""
        self.score = [0, 0]
        self.winner = None
        self.confetti = []
        self.result_msg = ""
        self.best_rally = 0
        self.pad = [float(self.court.centery), float(self.court.centery)]
        self._serve()
        self._sfx("ui_select")

    def _serve(self):
        self._reset_ball()
        self.phase = "serve"
        self.phase_t = 0.9

    def _sfx(self, name, fallback="ui_move"):
        a = getattr(self.g, "audio", None)
        if a is None:
            return
        real = getattr(a, "_real", None) or a
        a.play(name if getattr(real, "sfx", {}).get(name) is not None else fallback)

    # ------------------------------------------------------------ input
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            self.handle_key(e.key)
        elif e.type == pygame.KEYUP:
            self.held.discard(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            if self.phase in ("title", "over"):
                self.start()

    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            self.close(power_off=False)
            return
        if key == pygame.K_x:
            self.close(power_off=True)
            return
        if key == pygame.K_TAB and self.local and self.phase in ("title", "over"):
            self.vs_cpu = not self.vs_cpu
            self._sfx("ui_toggle")
            return
        if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER,
                   P1_KEYS.get("action"), P2_KEYS.get("action")):
            if self.phase in ("title", "over"):
                self.start()
            return
        self.held.add(key)

    def close(self, power_off=False):
        if self.closed:
            return
        self.closed = True
        self.held.clear()
        fn = getattr(self.g, "_pong_closed", None)
        if fn:
            fn(self, power_off)

    # ------------------------------------------------------------ simulation
    def _axis(self, keys_list):
        d = 0
        for K_ in keys_list:
            if K_.get("up") in self.held:
                d -= 1
            if K_.get("down") in self.held:
                d += 1
        return max(-1, min(1, d))

    def _clamp_pad(self, y):
        return max(self.court.y + PAD_H / 2 + 6, min(self.court.bottom - PAD_H / 2 - 6, y))

    def _predict(self):
        """Where the ball will cross the CPU's paddle line (walls folded in)."""
        if self.vx <= 0:
            return float(self.court.centery)
        px = self.court.right - 26 - PAD_W
        t = (px - self.bx) / self.vx
        y = self.by + self.vy * t
        top, bot = self.court.y + BALL_R, self.court.bottom - BALL_R
        span = bot - top
        k = (y - top) % (2 * span)
        return top + (k if k <= span else 2 * span - k)

    def update(self, dt):
        self.t += dt
        for c in self.confetti:
            c[0] += c[2] * dt
            c[1] += c[3] * dt
            c[3] += 60 * dt
            c[4] += dt * c[5]
        self.confetti = [c for c in self.confetti if c[1] < self.court.bottom + 30]
        if self.phase == "over" and len(self.confetti) < 60 and random.random() < 0.5:
            self._confetti(1)
        # paddles (move in every phase but the title so you can warm up)
        if self.phase != "title":
            if self.vs_cpu:
                me = self._axis([P1_KEYS, P2_KEYS])
                self.pad[0] = self._clamp_pad(self.pad[0] + me * PAD_SPEED * dt)
                self._cpu(dt)
            else:
                self.pad[0] = self._clamp_pad(self.pad[0] + self._axis([P1_KEYS]) * PAD_SPEED * dt)
                self.pad[1] = self._clamp_pad(self.pad[1] + self._axis([P2_KEYS]) * PAD_SPEED * dt)
        if self.phase == "serve":
            self.phase_t -= dt
            if self.phase_t <= 0:
                self.phase = "play"
                self._launch()
                self._sfx("pong_serve", "ui_toggle")
        elif self.phase == "play":
            steps = max(1, int(math.ceil(dt * 240)))
            for _ in range(steps):
                if self._step(dt / steps):
                    break
            self.trail.append((self.bx, self.by))
            self.trail = self.trail[-9:]
        elif self.phase == "point":
            self.phase_t -= dt
            if self.phase_t <= 0:
                if max(self.score) >= WIN:
                    self._game_over()
                else:
                    self._serve()

    def _cpu(self, dt):
        self.cpu_t -= dt
        if self.cpu_t <= 0:                       # a human-ish reaction time
            self.cpu_t = 0.12
            if self.phase == "play" and self.vx > 0:
                self.cpu_target = self._predict() + self.cpu_err
            else:
                self.cpu_target = float(self.court.centery)
        d = self.cpu_target - self.pad[1]
        step = CPU_SPEED * dt
        self.pad[1] = self._clamp_pad(self.pad[1] + max(-step, min(step, d)))

    def _step(self, dt):
        """Advance the ball one sub-step. True = a point was scored."""
        self.bx += self.vx * dt
        self.by += self.vy * dt
        top, bot = self.court.y + BALL_R, self.court.bottom - BALL_R
        if self.by < top:
            self.by, self.vy = top + (top - self.by), abs(self.vy)
            self._sfx("pong_wall", "ui_move")
        elif self.by > bot:
            self.by, self.vy = bot - (self.by - bot), -abs(self.vy)
            self._sfx("pong_wall", "ui_move")
        lx = self.court.x + 26 + PAD_W            # left paddle's face
        rx = self.court.right - 26 - PAD_W        # right paddle's face
        if self.vx < 0 and lx - 10 <= self.bx - BALL_R <= lx and abs(self.by - self.pad[0]) <= PAD_H / 2 + BALL_R:
            self._hit(0, lx + BALL_R)
        elif self.vx > 0 and rx <= self.bx + BALL_R <= rx + 10 and abs(self.by - self.pad[1]) <= PAD_H / 2 + BALL_R:
            self._hit(1, rx - BALL_R)
        if self.bx < self.court.x - BALL_R:
            self._point(1)
            return True
        if self.bx > self.court.right + BALL_R:
            self._point(0)
            return True
        return False

    def _hit(self, side, x):
        off = (self.by - self.pad[side]) / (PAD_H / 2 + BALL_R)
        off = max(-1.0, min(1.0, off))
        sp = min(BALL_VMAX, math.hypot(self.vx, self.vy) * SPEEDUP)
        ang = off * math.radians(58)
        d = 1 if side == 0 else -1
        self.vx = math.cos(ang) * sp * d
        self.vy = math.sin(ang) * sp
        self.bx = x
        self.rally += 1
        self.best_rally = max(self.best_rally, self.rally)
        self.cpu_err = random.gauss(0, 14 + sp / 40)
        self._sfx("pong_hit", "ui_select")

    def _point(self, side):
        self.score[side] += 1
        self.last_point = side
        self.server = side                       # the scorer serves next
        self.phase = "point"
        self.phase_t = 0.9
        self._sfx("pong_score", "coin")
        self.vx = self.vy = 0.0

    def _game_over(self):
        self.phase = "over"
        self.winner = 0 if self.score[0] > self.score[1] else 1
        self._confetti(40)
        fn = getattr(self.g, "_pong_result", None)
        self.result_msg = (fn(self) if fn else "") or ""
        self._sfx("pong_win", "levelup")

    def _confetti(self, n):
        cols = [(255, 130, 165), (255, 214, 120), (190, 160, 226), (160, 206, 150), (255, 255, 255)]
        for _ in range(n):
            self.confetti.append([random.uniform(self.court.x + 20, self.court.right - 20),
                                  random.uniform(self.court.y - 40, self.court.y + 40),
                                  random.uniform(-40, 40), random.uniform(20, 120),
                                  random.uniform(0, math.tau), random.uniform(-3, 3),
                                  random.choice(cols), random.uniform(4, 8)])

    # ------------------------------------------------------------ draw
    def draw(self, surf):
        K.dim(surf, 160, (18, 10, 26))
        K.modal(surf, self.card, "Heart Pong")
        names, cols = self.names(), self.colors()
        self._scoreboard(surf, names, cols)
        self._draw_court(surf, names, cols)
        self._footer(surf)

    def _scoreboard(self, surf, names, cols):
        y = 104
        for side in (0, 1):
            w = 350
            r = pygame.Rect(0, y - 20, w, 42)
            if side == 0:
                r.right = self.card.centerx - 62
            else:
                r.left = self.card.centerx + 62
            K.well(surf, r, hot=self.phase == "over" and self.winner == side)
            pygame.draw.circle(surf, cols[side], (r.x + 20 if side == 0 else r.right - 20, r.centery), 8)
            nf = K.fit_font(names[side], 170, (18, 16, 14), bold=True)
            if side == 0:
                K.blit_text(surf, nf, names[side], K.INK, (r.x + 36, r.centery), align="left")
            else:
                K.blit_text(surf, nf, names[side], K.INK, (r.right - 36, r.centery), align="right")
            for i in range(WIN):                           # hearts = points
                hx = (r.right - 22 - i * 24) if side == 0 else (r.x + 22 + i * 24)
                if i < self.score[side]:
                    heart(surf, hx, r.centery, 9, K.HEART)
                else:
                    heart(surf, hx, r.centery, 9, K.WELL_LINE)
        K.blit_text(surf, K.font(28, True), f"{self.score[0]} - {self.score[1]}", K.INK,
                    (self.card.centerx, y + 1))

    def _draw_court(self, surf, names, cols):
        c = self.court
        # the arcade glass: a deep plum screen with a neon rim
        glow = pygame.Surface((c.w + 40, c.h + 40), pygame.SRCALPHA)
        for i in range(6, 0, -1):
            pygame.draw.rect(glow, (255, 120, 170, 10 + i * 3), glow.get_rect().inflate(-i * 5, -i * 5),
                             border_radius=26)
        surf.blit(glow, (c.x - 20, c.y - 20))
        pygame.draw.rect(surf, K.WOOD_DK, c.inflate(14, 14), border_radius=18)
        scr = pygame.Surface(c.size)
        for y in range(0, c.h, 4):
            k = y / c.h
            scr.fill((int(46 - 18 * k), int(28 - 8 * k), int(70 - 22 * k)), (0, y, c.w, 4))
        # centre line of tiny hearts
        for y in (range(18, c.h - 10, 30) if self.phase not in ("title", "over") else ()):
            heart(scr, c.w / 2, y, 5, (120, 80, 150))
        # paddles
        for side in (0, 1):
            x = 26 if side == 0 else c.w - 26 - PAD_W
            y = self.pad[side] - c.y - PAD_H / 2
            col = cols[side]
            g = pygame.Surface((PAD_W + 20, PAD_H + 20), pygame.SRCALPHA)
            pygame.draw.rect(g, col + (60,), g.get_rect(), border_radius=14)
            scr.blit(g, (x - 10, y - 10))
            pygame.draw.rect(scr, col, (x, y, PAD_W, PAD_H), border_radius=7)
            pygame.draw.rect(scr, tuple(min(255, v + 60) for v in col), (x + 3, y + 6, 4, PAD_H - 12),
                             border_radius=2)
        # the heart ball + its trail
        if self.phase in ("serve", "play", "point"):
            for i, (tx, ty) in enumerate(self.trail[:-1]):
                a = int(30 + 110 * i / max(1, len(self.trail)))
                heart(scr, tx - c.x, ty - c.y, BALL_R * (0.5 + 0.5 * i / len(self.trail)), (255, 150, 190),
                      alpha=a)
            blink = self.phase != "serve" or int(self.t * 6) % 2 == 0
            if blink:
                pulse = 1.0 + 0.08 * math.sin(self.t * 10)
                bx, by = self.bx - c.x, self.by - c.y
                heart(scr, bx, by, BALL_R * 1.5 * pulse, (255, 120, 170), alpha=60)
                heart(scr, bx, by, BALL_R * pulse, (255, 110, 160))
                pygame.draw.circle(scr, (255, 220, 236), (int(bx - 4), int(by - 5)), 2)
        for x, y, _vx, _vy, rot, _vr, col, r in self.confetti:
            heart(scr, x - c.x, y - c.y, r * (0.8 + 0.2 * math.sin(rot)), col)
        scr.blit(_scanlines(c.size), (0, 0))
        mask = pygame.Surface(c.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=14)
        scr = scr.convert_alpha() if pygame.display.get_surface() else scr
        out = pygame.Surface(c.size, pygame.SRCALPHA)
        out.blit(scr, (0, 0))
        out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(out, c.topleft)
        pygame.draw.rect(surf, (255, 150, 190), c, 2, border_radius=14)
        self._overlay(surf, names, cols)

    def _overlay(self, surf, names, cols):
        c = self.court
        if self.phase == "title":
            t = K.outlined(K.font(56, True), "HEART PONG", (255, 150, 190), (60, 20, 50), 4)
            bob = math.sin(self.t * 2.4) * 4
            surf.blit(t, (c.centerx - t.get_width() // 2, c.y + 70 + bob))
            heart(surf, c.centerx - t.get_width() // 2 - 34, c.y + 100 + bob, 16, (255, 120, 170))
            heart(surf, c.centerx + t.get_width() // 2 + 34, c.y + 100 + bob, 16, (255, 120, 170))
            sub = K.outlined(K.font(20, True), f"First to {WIN} wins", (255, 236, 244), (50, 24, 60), 2)
            surf.blit(sub, (c.centerx - sub.get_width() // 2, c.y + 160))
            if self.vs_cpu:
                mode = f"{names[0]} vs the CPU"
                how = "Up / Down or W / S to move"
            else:
                mode = f"{names[0]} vs {names[1]}"
                how = "P1: W / S      P2: Up / Down"
            for i, (txt, col) in enumerate(((mode, (255, 226, 150)), (how, (220, 210, 240)))):
                s = K.outlined(K.font(18, True), txt, col, (40, 20, 50), 2)
                surf.blit(s, (c.centerx - s.get_width() // 2, c.y + 214 + i * 30))
            if int(self.t * 2) % 2 == 0:
                s = K.outlined(K.font(22, True), "Press SPACE to start", (255, 255, 255), (60, 20, 50), 2)
                surf.blit(s, (c.centerx - s.get_width() // 2, c.y + 300))
            if self.local:
                s = K.outlined(K.font(15, True), "TAB  switch: 2 players / vs CPU", (200, 190, 220),
                               (40, 20, 50), 2)
                surf.blit(s, (c.centerx - s.get_width() // 2, c.y + 350))
        elif self.phase == "serve":
            s = K.outlined(K.font(24, True), "Ready...", (255, 236, 244), (50, 20, 50), 2)
            surf.blit(s, (c.centerx - s.get_width() // 2, c.y + 40))
        elif self.phase == "point" and self.last_point is not None:
            side = self.last_point
            k = 1.0 - self.phase_t / 0.9
            s = K.outlined(K.font(30, True), f"+1  {names[side]}!", cols[side], (40, 20, 50), 3)
            x = c.x + c.w * (0.25 if side == 0 else 0.75) - s.get_width() / 2
            surf.blit(s, (x, c.y + 150 - k * 30))
        elif self.phase == "over" and self.winner is not None:
            r = pygame.Rect(0, 0, 460, 200)
            r.center = (c.centerx, c.centery - 10)
            K.draw_card(surf, r, radius=18)
            w = self.winner
            title = f"{names[w]} wins!"
            K.blit_text(surf, K.fit_font(title, 400, (34, 30, 26, 22), bold=True), title, K.INK,
                        (r.centerx, r.y + 44))
            heart(surf, r.x + 40, r.y + 44, 14, K.HEART)
            heart(surf, r.right - 40, r.y + 44, 14, K.HEART)
            K.blit_text(surf, K.font(22, True), f"{self.score[0]} - {self.score[1]}", cols[w],
                        (r.centerx, r.y + 84))
            line = self.result_msg or (f"Longest rally: {self.best_rally}")
            K.blit_text(surf, K.fit_font(line, 420, (16, 15, 14, 13), bold=True), line, K.INK_SOFT,
                        (r.centerx, r.y + 118))
            K.divider(surf, r.centerx, r.y + 142, 150)
            K.blit_text(surf, K.font(15, True), "SPACE  rematch      ESC  leave", K.SPROUT,
                        (r.centerx, r.y + 168))

    def _footer(self, surf):
        y = self.card.bottom - 30
        st = getattr(self.g, "pong_stats", None) or {}
        bits = [f"Best rally {int(st.get('best_rally', 0))}"]
        cw, cl = int(st.get("cpu_w", 0)), int(st.get("cpu_l", 0))
        if cw or cl:
            bits.append(f"vs CPU {cw}-{cl}")
        duel = st.get("duel") or [0, 0]
        if not self.vs_cpu and (duel[0] or duel[1]):
            n = self.names()
            bits.append(f"Duels: {n[0]} {duel[0]} - {duel[1]} {n[1]}")
        txt = "   |   ".join(bits)
        K.blit_text(surf, K.font(14, True), txt, K.INK_SOFT, (self.card.x + 40, y), align="left")
        f = K.font(13, True)
        x = self.card.right - 40
        pills = [("Esc", "Leave"), ("X", "Power off")]
        if self.vs_cpu:
            pills.append(("Up/Down", "Move"))
        else:
            pills += [("Up/Down", "P2"), ("W/S", "P1")]
        for k, lab in pills:
            w_ = f.size(k)[0] + f.size(lab)[0] + 44
            K.key_pill(surf, k, lab, (x - w_ // 2, y), fnt=f)
            x -= w_ + 8
