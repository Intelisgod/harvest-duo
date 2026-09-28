"""Player / NPC character sprites — 4 directions x 4 walk frames.

Owner: "UI & Rendering" chat (sprite art). Consumed by entities.py and the
character creator (which also reads the palettes in _base).
"""
import pygame
from ..settings import TILE
from ._base import _cache, _surf, resolve_appearance, PANTS, SHOE


def _hair(s, style, hair, skin, direction, cx, hy):
    up = (direction == "up")
    # side views shift the face reveal toward the facing edge so more hair
    # shows on the BACK of the head (reads as a profile, Stardew-style)
    fdx = -2 if direction == "left" else (2 if direction == "right" else 0)
    if style == "bald":
        if not up:
            pygame.draw.arc(s, hair, (cx - 10, hy - 4, 20, 16), 3.3, 6.1, 2)  # little ring
        return
    pygame.draw.circle(s, hair, (cx, hy - 1), 11)          # hair fills head
    if not up:
        pygame.draw.ellipse(s, skin, (cx - 9 + fdx, hy - 2, 18, 15))   # reveal the face
    if style == "short":
        if not up:
            pygame.draw.rect(s, hair, (cx - 10, hy - 10, 20, 5), border_radius=3)
    elif style == "long":
        pygame.draw.rect(s, hair, (cx - 12, hy - 4, 5, 18), border_radius=3)
        pygame.draw.rect(s, hair, (cx + 7, hy - 4, 5, 18), border_radius=3)
        if up:
            pygame.draw.rect(s, hair, (cx - 9, hy, 18, 18), border_radius=5)
        else:
            pygame.draw.rect(s, hair, (cx - 10, hy - 10, 20, 5), border_radius=3)
    elif style == "ponytail":
        if not up:
            pygame.draw.rect(s, hair, (cx - 10, hy - 10, 20, 5), border_radius=3)
        if direction == "left":
            pygame.draw.ellipse(s, hair, (cx + 6, hy - 4, 7, 14))
        elif direction == "right":
            pygame.draw.ellipse(s, hair, (cx - 13, hy - 4, 7, 14))
        else:
            pygame.draw.ellipse(s, hair, (cx - 3, hy - 16, 6, 11))
    elif style == "spiky":
        for dxp in (-8, -3, 2, 7):
            pygame.draw.polygon(s, hair, [(cx + dxp, hy - 12), (cx + dxp - 3, hy - 3),
                                          (cx + dxp + 3, hy - 3)])
    elif style == "bun":
        if not up:
            pygame.draw.rect(s, hair, (cx - 10, hy - 10, 20, 5), border_radius=3)
        pygame.draw.circle(s, hair, (cx, hy - 13), 5)
    elif style == "cap":
        pygame.draw.circle(s, hair, (cx, hy - 3), 11)
        if not up:
            pygame.draw.ellipse(s, skin, (cx - 9 + fdx, hy + 1, 18, 12))
            # brim points the way the wearer faces (down keeps the classic tilt)
            bx = cx - 1 if direction == "right" else cx - 13
            pygame.draw.rect(s, tuple(int(c * 0.8) for c in hair), (bx, hy - 4, 14, 4),
                             border_radius=2)


def _face(s, direction, skin, cx, hy):
    """Facial features. Side views are a Stardew-style profile: one eye near
    the leading edge + brow, a little nose bump on the head's rim, and a
    mouth — instead of a single floating eye dot."""
    eye = (44, 40, 48)
    mouth = (170, 110, 100)
    if direction == "down":
        # same eye build as the side view (sclera + pupil + lash) so every
        # facing reads consistently; pupils sit on the inner side = cute
        for ex, inner in ((cx - 4, 1), (cx + 4, 0)):
            pygame.draw.rect(s, (250, 250, 250), (ex - 1, hy - 2, 3, 5))
            pygame.draw.rect(s, eye, (ex - 1 + inner, hy - 1, 2, 3))
            pygame.draw.line(s, eye, (ex - 1, hy - 3), (ex + 1, hy - 3), 1)
        pygame.draw.arc(s, mouth, (cx - 4, hy + 2, 8, 6), 3.4, 6.0, 1)
    elif direction in ("left", "right"):
        f = -1 if direction == "left" else 1
        # nose: tiny 1px button bump just past the head circle (cute, subtle)
        pygame.draw.circle(s, skin, (cx + f * 11, hy + 3), 1)
        # one big friendly eye near the leading edge: white sclera + dark
        # pupil on the front half + thin top lash (no brow — reads angry)
        ex = cx + f * 5
        pygame.draw.rect(s, (250, 250, 250), (ex - 1, hy - 2, 3, 5))
        pygame.draw.rect(s, eye, (ex - 1 + (1 if f > 0 else 0), hy - 1, 2, 3))
        pygame.draw.line(s, eye, (ex - 1, hy - 3), (ex + 1, hy - 3), 1)
        # mouth: short stroke under the nose, front corner tipped up = smile
        pygame.draw.line(s, mouth, (cx + f * 7, hy + 6), (cx + f * 8, hy + 6), 1)
        pygame.draw.line(s, mouth, (cx + f * 8, hy + 6), (cx + f * 9, hy + 5), 1)


def _draw_farmer(direction, step, skin, style, hair, shirt, arms=True):
    """One animated frame. arms=False omits the side arms (players draw arms that
    actually grip the held tool); NPCs keep arms=True."""
    s = _surf()
    cx = TILE // 2
    bob = (-1 if step in (1, 3) else 0)
    top = 4 + bob
    dk = tuple(int(c * 0.78) for c in shirt)
    if step == 1:
        lyo, ryo = -3, 2
    elif step == 3:
        lyo, ryo = 2, -3
    else:
        lyo = ryo = 0
    # legs + shoes
    pygame.draw.rect(s, PANTS, (cx - 8, 36 + top + lyo, 7, 9), border_radius=3)
    pygame.draw.rect(s, PANTS, (cx + 1, 36 + top + ryo, 7, 9), border_radius=3)
    pygame.draw.ellipse(s, SHOE, (cx - 10, 43 + top + lyo, 9, 5))
    pygame.draw.ellipse(s, SHOE, (cx + 1, 43 + top + ryo, 9, 5))
    # torso
    pygame.draw.rect(s, shirt, (cx - 11, 21 + top, 22, 18), border_radius=6)
    pygame.draw.rect(s, dk, (cx - 11, 34 + top, 22, 5), border_radius=4)
    # arms swing opposite legs + hands (omitted for players, who grip the tool)
    if arms == "umbrella":
        _umbrella_arms(s, direction, step, skin, shirt, cx, top)
    elif arms:
        ax = 3 if step == 1 else (-3 if step == 3 else 0)
        pygame.draw.rect(s, shirt, (cx - 14, 23 + top - ax, 5, 12), border_radius=3)
        pygame.draw.rect(s, shirt, (cx + 9, 23 + top + ax, 5, 12), border_radius=3)
        pygame.draw.circle(s, skin, (cx - 11, 35 + top - ax), 3)
        pygame.draw.circle(s, skin, (cx + 12, 35 + top + ax), 3)
    # neck + head
    pygame.draw.rect(s, skin, (cx - 3, 19 + top, 6, 4))
    hy = 14 + top
    pygame.draw.circle(s, skin, (cx, hy), 11)
    _hair(s, style, hair, skin, direction, cx, hy)
    _face(s, direction, skin, cx, hy)   # on top of hair/face boundary
    return s


# where the umbrella hand grips the shaft, per facing (frame px, before the
# walk bob). 'up' holds it in front of the chest -- hidden behind the body.
UMBRELLA_HAND = {"down": (TILE // 2 + 13, 24), "up": (TILE // 2 + 4, 22),
                 "left": (TILE // 2 - 15, 26), "right": (TILE // 2 + 15, 26)}


def _umbrella_arms(s, direction, step, skin, shirt, cx, top):
    """Arms for a villager walking in the rain: one arm swings as usual, the
    other is bent up with the hand GRIPPING the umbrella shaft (the shaft and
    canopy themselves are drawn by the NPC so they can sway with the walk)."""
    ax = 3 if step == 1 else (-3 if step == 3 else 0)
    hx, hy = UMBRELLA_HAND[direction]
    hy += top - 4
    if direction in ("down", "up"):
        pygame.draw.rect(s, shirt, (cx - 14, 23 + top - ax, 5, 12), border_radius=3)
        pygame.draw.circle(s, skin, (cx - 11, 35 + top - ax), 3)
        if direction == "down":           # elbow down at the side, forearm up
            pygame.draw.line(s, shirt, (cx + 11, 24 + top), (cx + 12, 30 + top), 5)
            pygame.draw.line(s, shirt, (cx + 12, 30 + top), (hx, hy + 2), 4)
            pygame.draw.circle(s, skin, (hx, hy), 3)
        else:                             # from behind: just the raised sleeve
            pygame.draw.rect(s, shirt, (cx + 9, 23 + top, 5, 8), border_radius=3)
    else:
        f = -1 if direction == "left" else 1
        back_x = cx + 9 if f < 0 else cx - 14
        pygame.draw.rect(s, shirt, (back_x, 23 + top + ax, 5, 12), border_radius=3)
        pygame.draw.circle(s, skin, (back_x + 2, 35 + top + ax), 3)
        sh = (cx + f * 7, 25 + top)       # front shoulder -> hand held out front
        pygame.draw.line(s, shirt, sh, (cx + f * 9, 31 + top), 5)
        pygame.draw.line(s, shirt, (cx + f * 9, 31 + top), (hx - f, hy + 2), 4)
        pygame.draw.circle(s, skin, (hx, hy), 3)


def player_frames(skin, style, hair, shirt, arms=True):
    key = ("pframes", skin, style, hair, shirt, arms)
    if key in _cache:
        return _cache[key]
    frames = {d: [_draw_farmer(d, st, skin, style, hair, shirt, arms) for st in range(4)]
              for d in ("down", "up", "left", "right")}
    _cache[key] = frames
    return frames


def frames_for(appearance, arms=True):
    """Build (and cache) walk frames from an appearance dict."""
    skin, style, hair, shirt = resolve_appearance(appearance)
    return player_frames(skin, style, hair, shirt, arms)


def player_sprite(appearance):
    """Single front frame from an appearance dict (preview/icon)."""
    return frames_for(appearance)["down"][0]


def _face_three_quarter(s, skin, cx, hy):
    """Front 3/4 face turned toward screen-LEFT (an iso sitter facing SW):
    both eyes show, shifted toward the turn, the far eye a touch narrower,
    plus the little nose bump on the leading rim (Habbo / Sims-style 3/4)."""
    eye = (44, 40, 48)
    mouth = (170, 110, 100)
    pygame.draw.circle(s, skin, (cx - 11, hy + 3), 1)                   # nose bump
    for ex, w, inner in ((cx - 7, 2, 0), (cx + 1, 3, 0)):               # far, near eye
        pygame.draw.rect(s, (250, 250, 250), (ex - 1, hy - 2, w, 5))
        pygame.draw.rect(s, eye, (ex - 1 + inner, hy - 1, 2, 3))
        pygame.draw.line(s, eye, (ex - 1, hy - 3), (ex - 2 + w, hy - 3), 1)
    pygame.draw.arc(s, mouth, (cx - 7, hy + 2, 7, 6), 3.4, 6.0, 1)


def _draw_seated(direction, skin, style, hair, shirt):
    """A SITTING upper body for the ISO home, drawn on the room's diagonals so
    the sitter lines up with the seat (Habbo / Sims / LINE PLAY style):

        grid 'down'  (+y) -> faces SW, 3/4 front      grid 'right' (+x) -> SE (mirror)
        grid 'left'  (-x) -> faces NW, 3/4 back       grid 'up'    (-y) -> NE (mirror)

    Only torso, arms and head live in the sprite. The LEGS are real 3D boxes
    built in tile space by homeiso (thighs along the seat, knees over its front
    edge, shins down to the floor), so they turn with the seat and the chair's
    own parts occlude them correctly. Hands rest where the thighs land."""
    if direction in ("right", "up"):
        base = _draw_seated("down" if direction == "right" else "left",
                            skin, style, hair, shirt)
        return pygame.transform.flip(base, True, False)
    s = _surf((TILE, TILE + 10))
    cx = TILE // 2
    dk = tuple(int(c * 0.78) for c in shirt)
    sd = tuple(int(c * 0.88) for c in shirt)          # the body's turned side
    front = direction == "down"                       # SW 3/4 front / NW 3/4 back
    sleeve_w = 5
    if not front:
        # far arm (screen-right) peeks past the back, elbow bent forward
        pygame.draw.line(s, dk, (cx + 9, 28), (cx + 9, 34), sleeve_w)
    # torso -- a hair narrower than standing, the turned side in shade
    # (it ends just above the lap so the thighs' top faces show beneath it)
    pygame.draw.rect(s, shirt, (cx - 10, 25, 20, 12), border_radius=6)
    if front:
        pygame.draw.rect(s, sd, (cx + 4, 26, 6, 10), border_radius=4)   # right flank
    else:
        pygame.draw.rect(s, sd, (cx - 10, 26, 6, 10), border_radius=4)  # left flank
        pygame.draw.line(s, dk, (cx + 1, 27), (cx + 1, 33), 1)          # spine crease
    pygame.draw.rect(s, dk, (cx - 10, 32, 20, 5), border_radius=4)
    if front:
        # both forearms reach FORWARD-left onto the lap: hands on the thighs
        pygame.draw.line(s, sd, (cx - 9, 28), (cx - 10, 33), sleeve_w)  # far upper arm
        pygame.draw.line(s, sd, (cx - 10, 33), (cx - 8, 35), sleeve_w - 1)
        pygame.draw.circle(s, skin, (cx - 8, 36), 3)                    # far hand
        pygame.draw.line(s, shirt, (cx + 9, 28), (cx + 8, 33), sleeve_w)   # near arm
        pygame.draw.line(s, shirt, (cx + 8, 33), (cx + 2, 37), sleeve_w - 1)
        pygame.draw.circle(s, skin, (cx + 1, 38), 3)                    # near hand
    else:
        # near arm (screen-left) hangs along the side, hand forward = hidden
        pygame.draw.line(s, shirt, (cx - 10, 28), (cx - 11, 35), sleeve_w)
    # neck + head
    pygame.draw.rect(s, skin, (cx - 4 if front else cx - 2, 22, 6, 4))
    hy = 18
    pygame.draw.circle(s, skin, (cx, hy), 11)
    if front:
        _hair(s, style, hair, skin, "left", cx, hy)       # profile-ish hair mass
        _face_three_quarter(s, skin, cx, hy)
    else:
        _hair(s, style, hair, skin, "up", cx, hy)         # back of the head...
        if style != "bald":                               # ...+ a sliver of cheek
            pygame.draw.ellipse(s, skin, (cx - 11, hy + 1, 4, 8))
    return s


# y offset (px) of the SEAT-TOP line inside the seated sprite: blit so this row
# lands on the seat's cushion top (homeiso uses it to anchor the pose)
SEATED_HIP_Y = 37


def seated_frames(appearance):
    """{grid direction: seated upper-body frame} for an appearance dict
    (cached). The legs are drawn as 3D boxes by homeiso."""
    skin, style, hair, shirt = resolve_appearance(appearance)
    key = ("seated", skin, style, hair, shirt)
    if key not in _cache:
        _cache[key] = {d: _draw_seated(d, skin, style, hair, shirt)
                       for d in ("down", "up", "left", "right")}
    return _cache[key]
