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
    if arms:
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


def _draw_seated(direction, skin, style, hair, shirt):
    """A Sims-style SITTING pose: lap folded, shins dangling past the seat's
    front edge, hands resting on the knees. The surface is TALLER than the
    standing frame so the dangling feet never get clipped off."""
    s = _surf((TILE, TILE + 10))
    cx = TILE // 2
    dk = tuple(int(c * 0.78) for c in shirt)
    # legs first (the torso then overlaps the hip joint). Facing AWAY from the
    # camera ("up"/"left") the legs hang on the FAR side of the seat -- they are
    # a SEPARATE sprite (seated_leg_frames) drawn behind the seat, so the seat
    # itself occludes them and only the feet peek out underneath.
    if direction == "down":
        pygame.draw.rect(s, PANTS, (cx - 9, 37, 18, 8), border_radius=3)   # lap/thighs
        pygame.draw.rect(s, PANTS, (cx - 8, 44, 6, 9), border_radius=2)    # shins from
        pygame.draw.rect(s, PANTS, (cx + 2, 45, 6, 9), border_radius=2)    # the knees
        pygame.draw.ellipse(s, SHOE, (cx - 9, 50, 8, 5))                   # (1px lower:
        pygame.draw.ellipse(s, SHOE, (cx + 1, 51, 8, 5))                   #  iso depth)
    elif direction == "right":
        # clear Z-shape: hip -> thigh FORWARD -> knee -> shin DOWN -> toe forward
        pygame.draw.rect(s, PANTS, (cx - 2, 38, 17, 7), border_radius=3)   # thigh
        pygame.draw.rect(s, PANTS, (cx + 9, 43, 6, 11), border_radius=2)   # shin at knee
        pygame.draw.ellipse(s, SHOE, (cx + 9, 51, 10, 5))                  # toe forward
    elif direction == "left":
        # mirrored Z-shape, drawn IN the body frame (over the seat edge) so the
        # bent leg always reads connected at chibi scale
        pygame.draw.rect(s, PANTS, (cx - 15, 38, 17, 7), border_radius=3)  # thigh
        pygame.draw.rect(s, PANTS, (cx - 15, 43, 6, 11), border_radius=2)  # shin at knee
        pygame.draw.ellipse(s, SHOE, (cx - 19, 51, 10, 5))                 # toe forward
    # torso, a touch shorter than standing (slouched onto the cushion)
    pygame.draw.rect(s, shirt, (cx - 11, 25, 22, 15), border_radius=6)
    pygame.draw.rect(s, dk, (cx - 11, 35, 22, 5), border_radius=4)
    # arms resting forward, hands on the knees
    if direction != "up":
        pygame.draw.rect(s, shirt, (cx - 14, 27, 5, 10), border_radius=3)
        pygame.draw.rect(s, shirt, (cx + 9, 27, 5, 10), border_radius=3)
        pygame.draw.circle(s, skin, (cx - 11, 38), 3)
        pygame.draw.circle(s, skin, (cx + 12, 38), 3)
    else:
        pygame.draw.rect(s, shirt, (cx - 13, 27, 4, 10), border_radius=3)
        pygame.draw.rect(s, shirt, (cx + 9, 27, 4, 10), border_radius=3)
    # neck + head + hair + face (same as standing)
    pygame.draw.rect(s, skin, (cx - 3, 23, 6, 4))
    hy = 18
    pygame.draw.circle(s, skin, (cx, hy), 11)
    _hair(s, style, hair, skin, direction, cx, hy)
    _face(s, direction, skin, cx, hy)
    return s


# y offset (px) of the HIP LINE inside the seated sprite: blit so this row
# lands on the seat's cushion top (homeiso uses it to anchor the pose)
SEATED_HIP_Y = 37


def _draw_seated_legs(direction):
    """Far-side dangling legs for away-facing sitters ('up'/'left'), on the
    SAME 48x58 canvas as the body frame so both blit at the same anchor. Drawn
    as a separate part so the seat occludes the shins and only feet peek out."""
    s = _surf((TILE, TILE + 10))
    cx = TILE // 2
    if direction == "up":
        # knees bend AWAY from camera: only short tucked shins + heels show
        pygame.draw.rect(s, PANTS, (cx - 8, 40, 6, 10), border_radius=2)   # shins
        pygame.draw.rect(s, PANTS, (cx + 2, 41, 6, 10), border_radius=2)
        pygame.draw.ellipse(s, SHOE, (cx - 9, 48, 8, 5))                   # heels
        pygame.draw.ellipse(s, SHOE, (cx + 1, 49, 8, 5))
    elif direction == "left":
        # mirrored Z-shape: thigh forward (left) -> knee -> shin down -> toe
        pygame.draw.rect(s, PANTS, (cx - 15, 38, 17, 7), border_radius=3)  # thigh
        pygame.draw.rect(s, PANTS, (cx - 15, 43, 6, 11), border_radius=2)  # shin at knee
        pygame.draw.ellipse(s, SHOE, (cx - 19, 51, 10, 5))                 # toe forward
    return s


def seated_frames(appearance):
    """{direction: seated-pose BODY frame} for an appearance dict (cached).
    'up'/'left' bodies have no legs -- those come from seated_leg_frames()."""
    skin, style, hair, shirt = resolve_appearance(appearance)
    key = ("seated", skin, style, hair, shirt)
    if key not in _cache:
        _cache[key] = {d: _draw_seated(d, skin, style, hair, shirt)
                       for d in ("down", "up", "left", "right")}
    return _cache[key]


def seated_leg_frames():
    """{direction: far-side legs frame} for away-facing sitters (cached;
    trousers/shoes are palette colours, so one set serves every player).
    Only 'up' uses this -- side facings keep their legs in the body frame."""
    key = ("seated_legs",)
    if key not in _cache:
        _cache[key] = {d: _draw_seated_legs(d) for d in ("up",)}
    return _cache[key]
