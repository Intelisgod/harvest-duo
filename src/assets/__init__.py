"""Procedurally generated *animated* graphics — zero external art files needed.

This package is split by domain so visual work in one area doesn't collide with
another:
  _base   - shared palettes, the surface cache and low-level helpers
  chars   - player / NPC walk-frame sprites
  terrain - water, trees, rocks, slime, buildings, boss name tag
  items   - hotbar/item & tool icons + held-tool / held-item renderers
  props   - interaction & decorative props (beds, temple set, farm, coop)

Everything is re-exported here, so external code keeps using ``assets.<name>``
exactly as before (e.g. ``assets.item_icon``, ``assets.prop_sprite``).
"""
from ._base import (
    PANTS, SHOE, SKIN_TONES, HAIR_COLORS, SHIRT_COLORS, HAIR_STYLES,
    IC, WOOD, STEEL, CROP_FORM, FISH_LOOK, HELD_TWO_HAND, HELD_ONE_HAND,
    CAN_BLUE, GOLD_HILT, resolve_appearance, shadow,
)
from .chars import player_frames, frames_for, player_sprite
from .terrain import (
    water_frames, tree_frames, tree_sprite, rock_sprite,
    building_sprite, boss_label, tilled_tile, shore_foam, crop_sprite,
)
from .items import (
    fish_icon, tool_icon, item_icon, hotbar_icon,
    draw_tool, draw_can, draw_held_item, ITEM_PAINTERS, register_item_icon,
)
from .props import (
    bed_sprite, bin_sprite, stall_sprite, signpost_sprite, buddha_sprite,
    incense_sprite, candle_sprite, lotus_sprite, bell_sprite, temple_gate_sprite,
    donation_box_sprite, chedi_sprite, naga_sprite, tung_sprite, bodhi_sprite,
    chatra_sprite, offering_bowl_sprite, collector_sprite, scarecrow_sprite,
    flowerbed_sprite, windmill_sprite, phra_pratan_sprite, pillar_sprite,
    haybale_sprite, trough_sprite, prop_sprite, crab, PROPS, register_prop,
)
from . import hud          # HUD icon painters: assets.hud.weather_icon(...) etc.

__all__ = [
    # palettes & shared
    "PANTS", "SHOE", "SKIN_TONES", "HAIR_COLORS", "SHIRT_COLORS", "HAIR_STYLES",
    "IC", "WOOD", "STEEL", "CROP_FORM", "FISH_LOOK", "HELD_TWO_HAND",
    "HELD_ONE_HAND", "CAN_BLUE", "GOLD_HILT", "resolve_appearance", "shadow",
    # chars
    "player_frames", "frames_for", "player_sprite",
    # terrain
    "water_frames", "tree_frames", "tree_sprite", "rock_sprite",
    "building_sprite", "boss_label",
    # items
    "fish_icon", "tool_icon", "item_icon", "hotbar_icon",
    "draw_tool", "draw_can", "draw_held_item", "ITEM_PAINTERS", "register_item_icon",
    # props
    "bed_sprite", "bin_sprite", "stall_sprite", "signpost_sprite", "buddha_sprite",
    "incense_sprite", "candle_sprite", "lotus_sprite", "bell_sprite",
    "temple_gate_sprite", "donation_box_sprite", "chedi_sprite", "naga_sprite",
    "tung_sprite", "bodhi_sprite", "chatra_sprite", "offering_bowl_sprite",
    "collector_sprite", "scarecrow_sprite", "flowerbed_sprite", "windmill_sprite",
    "phra_pratan_sprite", "pillar_sprite", "haybale_sprite", "trough_sprite",
    "prop_sprite", "crab", "PROPS", "register_prop",
]
