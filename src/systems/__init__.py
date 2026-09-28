"""Game system mixins.

The :class:`~src.game.Game` controller is composed from these per-domain mixins
(one file per domain) so that separate work streams can edit different gameplay
systems without touching the same file. Each mixin operates on the shared
``Game`` instance via ``self`` and defines no ``__init__`` of its own.

See ``docs/ARCHITECTURE.md`` for the ownership map and conventions.
"""
from .hooks import HooksMixin
from .save_system import SaveMixin
from .actions_system import ActionsMixin
from .combat_system import CombatMixin
from .farm_system import FarmMixin
from .fishing_system import FishingMixin
from .temple_system import TempleMixin
from .social_system import SocialMixin
from .shop_system import ShopMixin, ShopMenu, sell_value
from .net_system import NetMixin
from .render_system import RenderMixin
from .coop_system import CoopMixin
from .weather_system import WeatherMixin
from .progress_system import ProgressMixin
from .artisan_system import ArtisanMixin
from .forage_system import ForageMixin
from .story_system import StoryMixin
from .world_system import WorldMixin
from .ui_system import UIMixin
from .areactx_system import AreaCtxMixin
from .home_system import HomeMixin
from .piano_system import PianoMixin
from .records_system import RecordsMixin
from .homelife_system import HomeLifeMixin

__all__ = [
    "SaveMixin", "ActionsMixin", "CombatMixin", "FarmMixin", "FishingMixin",
    "TempleMixin", "SocialMixin", "ShopMixin", "ShopMenu", "sell_value",
    "NetMixin", "RenderMixin",
]
