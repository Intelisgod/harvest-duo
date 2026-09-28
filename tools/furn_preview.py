"""Contact sheets of every iso furniture model at all 4 rotations.

Run from the game folder:  python tools\\furn_preview.py
Writes furn_preview_1.png .. _N.png in the game folder root (8 kinds per sheet
so each PNG stays small enough to zoom/inspect).
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()
pygame.display.set_mode((64, 64))

from src import isofurn
from src import furniture as F

TW, TH = 64, 32
CELL_W, CELL_H = 200, 150          # one cell per (kind, rot)
PER = 8                            # kinds per sheet


def proj(ox, oy, gx, gy):
    return (ox + int((gx - gy) * (TW // 2)), oy + int((gx + gy) * (TH // 2)))


def render(sheet, chunk, font):
    for r, kind in enumerate(chunk):
        col = dict(F.PALETTE)["Blue"] if F.CAT[kind]["cat"] != "Bedroom" else dict(F.PALETTE)["Pink"]
        sheet.blit(font.render(kind, True, (235, 235, 240)), (8, r * CELL_H + 6))
        for rot in range(4):
            ox = 170 + rot * CELL_W + CELL_W // 2
            oy = r * CELL_H + CELL_H // 2 - 6
            fw, fh = F.footprint(kind, rot)
            cx, cy = fw / 2.0, fh / 2.0

            def Pf(a, b, _ox=ox, _oy=oy, _cx=cx, _cy=cy):
                return proj(_ox - int((_cx - _cy) * (TW // 2)),
                            _oy - int((_cx + _cy) * (TH // 2)) + 18, a, b)

            # floor diamond under the footprint so grounding is visible
            for gy in range(fh):
                for gx in range(fw):
                    q = [Pf(gx, gy), Pf(gx + 1, gy), Pf(gx + 1, gy + 1), Pf(gx, gy + 1)]
                    pygame.draw.polygon(sheet, (70, 64, 58) if (gx + gy) % 2 else (78, 72, 64), q)
                    pygame.draw.polygon(sheet, (52, 48, 44), q, 1)
            isofurn.draw(sheet, Pf, 0, 0, fw, fh, kind, col, rot)
            sheet.blit(font.render(f"rot{rot}", True, (160, 162, 170)),
                       (170 + rot * CELL_W + 6, r * CELL_H + 6))


def main():
    kinds = [k for k, d in F.CAT.items() if d["layer"] in ("ground", "floor")]
    font = pygame.font.SysFont("consolas,menlo,monospace", 15)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for part in range(0, len(kinds), PER):
        chunk = kinds[part:part + PER]
        sheet = pygame.Surface((CELL_W * 4 + 170, CELL_H * len(chunk)), pygame.SRCALPHA)
        sheet.fill((36, 38, 46))
        render(sheet, chunk, font)
        out = os.path.join(root, f"furn_preview_{part // PER + 1}.png")
        pygame.image.save(sheet, out)
        print("saved", out)


if __name__ == "__main__":
    main()
