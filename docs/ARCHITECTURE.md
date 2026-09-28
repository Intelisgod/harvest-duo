# สถาปัตยกรรมเกม (Harvest Duo) — โครงสร้าง module สำหรับทำงานหลาย chat พร้อมกัน

เอกสารนี้คือ "แผนที่ความเป็นเจ้าของ" (ownership map) ของโค้ด ออกแบบมาเพื่อให้หลาย chat
แก้คนละโดเมนได้พร้อมกันโดยแทบไม่ชนไฟล์กัน ทุก chat ต้องอ่านส่วน **กติกา** ก่อนเริ่มงาน

> **อัปเดต 2026-09-26 — Hook bus:** ตอนนี้แต่ละโดเมน "เสียบ" เข้าวงจรเกมผ่าน hook ได้โดยไม่ต้องแก้
> ไฟล์กลาง (game.py / save_system / actions_system / render_system) — นิยาม method ชื่อขึ้นต้นด้วย
> `_on_reset_` / `_on_save_` / `_on_load_` / `_interact_late_` / `_on_update_` / `_draw_hud_` /
> `_world_sprites_` / `_lights_` / `_journal_tab_` / `_state_draw_<ชื่อ>` ... ใน mixin ของตัวเอง แล้วถูกเรียกอัตโนมัติ
> รายละเอียดเต็ม: `src/systems/hooks.py` และสัญญาร่วม/ความเป็นเจ้าของล่าสุด: `docs/UPGRADE_2026-09.md`
> mixin ใหม่ต่อโดเมน: coop_system/weather_system (Core), progress_system (Chat 1), artisan_system (Chat 2),
> forage_system (Chat 3), story_system + story_restore (Chat 4), world_system (Chat 5), ui_system (Chat 6)
> ตารางเจ้าของไฟล์ล่าสุด + ตาราง prefix ของ hook อยู่ด้านล่าง ("แผนที่ความเป็นเจ้าของ" และ "Hook bus (2026-09)")
> ทดสอบ: `py tools/smoke_test.py` (แยกเซฟไปโฟลเดอร์ชั่วคราว ไม่แตะเซฟจริง) + ไฟล์ทดสอบรายโดเมน `tools/tests/test_*.py`

## หลักการหลัก

`Game` ถูกทำให้ "บาง" (thin controller) แล้ว — เดิม `game.py` ยาว 1,865 บรรทัดเป็น god-object
ตอนนี้แตกเป็น **mixin ต่อโดเมน** ใน `src/systems/` โดย `Game` สืบทอดจาก mixin เหล่านั้น:

```python
# ณ 2026-09-26 (src/game.py)
class Game(HooksMixin, SaveMixin, ActionsMixin, CombatMixin, FarmMixin, FishingMixin,
           TempleMixin, SocialMixin, ShopMixin, NetMixin, MistMixin,
           CoopMixin, WeatherMixin, ProgressMixin, ArtisanMixin, ForageMixin,
           StoryMixin, WorldMixin, UIMixin, RenderMixin):
```

ทุก mixin ทำงานบน instance เดียวกันผ่าน `self` และ **ไม่มี `__init__` ของตัวเอง** — logic
ของแต่ละฟีเจอร์จึงอยู่คนละไฟล์ แต่ยังเรียกหากันได้ผ่าน `self.xxx()` เหมือนเดิมทุกอย่าง
(พฤติกรรมเกมไม่เปลี่ยนเลย — ผ่าน headless smoke test ครบ 7 area + save/load)

`assets.py` (เดิม 1,195 บรรทัด) แตกเป็น **package** `src/assets/` แบ่งตามหมวดสไปรต์
โดย `__init__.py` re-export ทุกอย่าง → โค้ดเดิมเรียก `assets.item_icon(...)` ได้เหมือนเดิม

## โครงไดเรกทอรี

```
src/
  game.py                ← CORE บางๆ: __init__, main loop, reset/warp/on_new_day,
                            update, event dispatch, helper กลาง (_grant_xp/_popup/add_shake)
  systems/               ← mixin ต่อโดเมน (หัวใจของการแบ่งงาน)
    hooks.py               HooksMixin   — hook bus: ค้นหา/เรียก _on_*_ / _interact_* / _state_* + emit()  [Core]
    save_system.py         SaveMixin    — _collect_save / _apply_save / settings (+ รวม _on_save_/_on_load_ ทุกโดเมน)
    actions_system.py      ActionsMixin — player_action (dispatch) + use_tool  [SEAM]
    coop_system.py         CoopMixin    — อีโมท, Love boost, ให้ของ P1↔P2, day report, สถิติ (แท็บ Stats)   (ใหม่ 09-26)
    weather_system.py      WeatherMixin — storm/fog/windy, พยากรณ์, รุ้ง, ambience                        (ใหม่ 09-26)
    net_system.py          NetMixin     — LAN host/client glue (ใช้ package src/net/)
    areactx_system.py      AreaCtxMixin — ออนไลน์: ผู้เล่นแต่ละคนอยู่คนละแมพได้ (p_area, area_ctx, warp_player)   (ใหม่ 09-28)
    combat_system.py       CombatMixin  — _reward_kill, sword_attack, คริ/knockback, ระเบิด, อัญมณี, บอส
    progress_system.py     ProgressMixin — achievements + แท็บ Journal                                 (ใหม่ 09-26)
    farm_system.py         FarmMixin    — สัตว์/collector/forest regrow + affection สัตว์
    artisan_system.py      ArtisanMixin — เครื่องแปรรูป, ปุ๋ย, buff food, แท็บ Farm                     (ใหม่ 09-26)
    shop_system.py         ShopMixin    — ร้านค้า/ขายของ + sell_value / unit_sell_value (HOT TODAY)
    fishing_system.py      FishingMixin — _land_fish, ขนาดปลา/สถิติ, หีบสมบัติ, hot spot
    forage_system.py       ForageMixin  — ของป่า, ของป่ากินได้, สัตว์ป่า, แท็บ Collection               (ใหม่ 09-26)
    temple_system.py       TempleMixin  — _monk_fortune, _donate, บัฟ Blessed, ระฆัง Harmony
    social_system.py       SocialMixin  — _talk_reward, _friendship_reward, In-Sync
    story_system.py        StoryMixin   — ชาวบ้าน/ตารางเวลา/ของขวัญ/วันเกิด/heart events, แท็บ Friends   (ใหม่ 09-26)
    story_restore.py       (mix เข้า StoryMixin) — กระดาน Valley Restoration + มินิเกมเทศกาล, แท็บ Bundles
    world_system.py        WorldMixin   — ของตกแต่งฟาร์ม, Meadow/Promise Tree, Decor mode, อันตรายในเหมือง, แท็บ Places (ใหม่ 09-26)
    ui_system.py           UIMixin      — Journal, toast, การ์ดชื่อพื้นที่, ป้ายชื่อไอเทม                  (ใหม่ 09-26)
    render_system.py       RenderMixin  — draw pipeline + HUD ทั้งหมด (พื้น pre-render ต่อ area/ฤดู)
  assets/                ← package สไปรต์ (procedural ทั้งหมด)
    _base.py               cache + palette + helper ใช้ร่วม (_surf, _shade, …)
    chars.py               สไปรต์ผู้เล่น/NPC
    terrain.py             น้ำ/ต้นไม้/หิน/slime/อาคาร/ป้ายบอส (+ ต้นไม้/หญ้าตามฤดู)
    items.py               ไอคอนไอเทม+เครื่องมือ + วาดของที่ถืออยู่ (+ register_item_icon)
    icon_art.py            ไอคอนชุดวาดใหม่ (เครื่องมือ/ปลา/พืช/วัตถุดิบ/อาหาร) + finish() ขอบ 1px — item_icon ดูที่นี่ก่อน
    props.py               props โต้ตอบ/ตกแต่ง + prop_sprite (+ register_prop)  [SEAM]
    hud.py                 ชิ้นส่วน HUD ใหม่ (การ์ดนาฬิกา, แผงผู้เล่น, ไอคอน)                          (ใหม่ 09-26)
  mistcity/              ← โหมด Mist City (side-scroller) — Chat 7
    mist_system.py world2d.py zones.py player2d.py zombies.py boss.py events.py items.py
  net/                   ← LAN transport: protocol.py (JSON framing), transport.py (Host/Client TCP)
  world.py world_art.py build.py isofurn.py homeiso.py furniture.py storage.py creator.py
  entities.py inventory.py crops.py animals.py cooking.py
  fishing.py critters.py forage.py forage_art.py
  npc.py quests.py festival.py story_data.py story_art.py
  progress.py monsters.py monster_ai.py monster_shapes.py loot.py craft.py
  ui.py menu.py menu_scene.py gallery.py inventory_screen.py
  timesystem.py camera.py settings.py particles.py audio.py lighting.py weather.py savegame.py
tools/
  smoke_test.py            headless DoD test (แยกเซฟไปโฟลเดอร์ชั่วคราว)
  tests/test_<domain>.py   เทสต์รายโดเมน: core, combat, farming, fishing, story, world, ui, mist
main.py  launcher.py  start_game.bat
```

## แผนที่ความเป็นเจ้าของ (7 chat + Core) — อัปเดต 2026-09-26

ไฟล์ที่มีป้าย **(ใหม่ 09-26)** เกิดในอัปเกรด "Level-Up" (ดู `docs/UPGRADE_2026-09.md` §2 และ `docs/WHATS_NEW_2026-09-26.md`)

| Chat | โดเมน | ไฟล์ที่เป็นเจ้าของ | mixin / โมดูลใหม่ (09-26) |
|---|---|---|---|
| **0** | **Core & Infra** (กลาง, แก้อย่างระวัง) | `game.py`, `systems/hooks.py`, `systems/save_system.py`, `systems/actions_system.py`, `systems/coop_system.py`, `systems/weather_system.py`, `systems/net_system.py`, `net/`, `savegame.py`, `settings.py`, `timesystem.py`, `camera.py`, `inventory.py`, `entities.py` (Player), `particles.py`, `audio.py`, `lighting.py`, `weather.py` | `CoopMixin` (อีโมท, Love boost, ให้ของคู่, day report, แท็บ Stats), `WeatherMixin` (storm/fog/windy, พยากรณ์, รุ้ง, ambience), `HooksMixin` (hook bus + `emit`) |
| **1** | **Combat, Mining & Progression** | `systems/combat_system.py`, `systems/progress_system.py`, `progress.py`, `monsters.py`, `monster_ai.py`, `monster_shapes.py`, `loot.py`, `craft.py` (Monster ใน `entities.py` ประสานกับ Core) | `ProgressMixin` (achievements + แท็บ Journal), `monster_ai.py` (`monsters.BEHAVIORS`), `monster_shapes.py` (`monsters.SHAPE_PAINTERS`) |
| **2** | **Farming, Animals & Cooking & ร้านค้า** | `systems/farm_system.py`, `systems/shop_system.py`, `systems/artisan_system.py`, `crops.py`, `animals.py`, `cooking.py` | `ArtisanMixin` (เครื่องแปรรูป, ปุ๋ย, buff food, แท็บ Farm) |
| **3** | **Fishing & Foraging** | `systems/fishing_system.py`, `systems/forage_system.py`, `fishing.py`, `critters.py`, `forage.py`, `forage_art.py` | `ForageMixin` (ของป่า, สัตว์ป่า, แท็บ Collection), `forage.py` (ทะเบียนของป่า, pure data), `forage_art.py` (ไอคอน + หีบสมบัติ) |
| **4** | **Story: Temple, NPC, Quests & Festival** | `systems/temple_system.py`, `systems/social_system.py`, `systems/story_system.py`, `systems/story_restore.py`, `npc.py`, `quests.py`, `festival.py`, `story_data.py`, `story_art.py` | `StoryMixin` (+ `story_restore.py`: Valley Restoration + มินิเกมเทศกาล, แท็บ Friends/Bundles), `story_data.py` (ชาวบ้าน/ตาราง/บทพูด/heart events, pure data), `story_art.py` |
| **5** | **World, Areas & Build** | `world.py`, `world_art.py`, `systems/world_system.py`, `build.py`, `isofurn.py`, `homeiso.py`, `furniture.py`, `storage.py`, `creator.py` | `WorldMixin` (ของตกแต่งฟาร์ม, Meadow, Promise Tree, Decor mode, อันตรายในเหมือง, แท็บ Places), `world_art.py` (props + แคตตาล็อก decor) |
| **6** | **UI & Rendering** | `systems/render_system.py`, `systems/ui_system.py`, `ui.py`, `menu.py`, `menu_scene.py`, `gallery.py`, `inventory_screen.py`, `assets/` (ทั้ง package) | `UIMixin` (Journal, toast, การ์ดชื่อพื้นที่, ป้ายชื่อไอเทม), `menu_scene.py` (ฉาก title screen), `assets/hud.py` |
| **7** | **Mist City (โหมด 2D side-scroller เมืองซอมบี้)** | `src/mistcity/` ทั้งโฟลเดอร์ — สเปคใน `docs/TASK_mist_city.md` | `zones.py` (Old Factory, Clock Tower), `boss.py` (The Bell Keeper), `events.py` (random events), `items.py` (cursed_gear, city_key); `MistMixin` เพิ่มสถิติ/เซฟ/แท็บ Journal |
| – | **เอกสาร** | `README.md`, `docs/*.md` | `docs/UPGRADE_2026-09.md` (สัญญาร่วม), `docs/WHATS_NEW_2026-09-26.md` (สรุปภาษาไทย) |

เทสต์รายโดเมน `tools/tests/test_<domain>.py` เป็นของโดเมนนั้นๆ · `tools/smoke_test.py` เป็นของ Core/ผู้ประสานงาน

## Hook bus (2026-09) — วิธีเสียบฟีเจอร์ใหม่โดยไม่แก้ไฟล์กลาง

ตัวจริง + คำอธิบายเต็ม: **`src/systems/hooks.py`** (docstring) · สัญญาร่วม + ตาราง events/ใครปล่อย: **`docs/UPGRADE_2026-09.md`** §0-§1

- นิยาม method ที่ขึ้นต้นด้วย prefix ใน mixin ของตัวเอง แล้ว `HooksMixin` จะหาเจอและเรียกเองตาม **ลำดับชื่อ**
  (ใส่ตัวเลขคั่นเพื่อกำหนดลำดับ เช่น `_interact_early_05_coop_gift` มาก่อน `_interact_early_40_story_npc`)
- ตั้งชื่อ `<prefix><domain>_<what>` เสมอ เพื่อไม่ชนกัน

| prefix | เรียกเมื่อ |
|---|---|
| `_on_reset_` | ท้าย `Game.reset()` — **สร้าง state ของโดเมนที่นี่** (mixin ห้ามมี `__init__`) |
| `_on_area_enter_` / `_on_new_day_` / `_on_update_(dt)` | ทุกครั้งที่วาร์ป / เริ่มวันใหม่ / ทุกเฟรมตอน state "play" |
| `_on_keydown_(key)->bool` | กดปุ่มตอนเล่น (True = กินปุ่มแล้ว) |
| `_interact_early_(idx,p)->bool` / `_interact_late_` | ใน `player_action` ก่อน NPC/ร้าน/เตียง... / ก่อน `use_tool` |
| `_on_tool_(idx,p,tool,gx,gy)->bool` | ใน `use_tool` ก่อน logic เครื่องมือปกติ |
| `_on_save_()->dict` / `_on_load_(d)` | รวมเข้าไฟล์เซฟ (key ต้องขึ้นต้นด้วยชื่อโดเมน, JSON ล้วน) / โหลดด้วย `d.get(k, default)` |
| `_draw_world_` / `_draw_hud_` / `_world_sprites_()->list` / `_lights_()->list` | วาดในโลก / บน HUD / สไปรต์เรียงตามแกน y / แสงเรือง |
| `_on_event_(event, data)` | ทุกครั้งที่มี `self.emit(event, **data)` (harvest, fish_caught, monster_killed, item_sold, partner_gift, bundle_done, achievement, mist_run_end ...) |
| `_state_event_<ชื่อ>` / `_state_update_<ชื่อ>` / `_state_draw_<ชื่อ>` | จอเต็ม/overlay ของตัวเอง (`self.state = "<ชื่อ>"`) — ตอนนี้มี `day_report`, `journal`, `decor`, `heart_event`, `restoration`, `egg_hunt_end` |
| `_journal_tab_<NN>_<domain>()->dict` | เพิ่มแท็บใน Journal (`{"title", "draw", "key"?}`) เรียงตาม NN |

- hook ที่ error จะไม่ทำเกมล่ม (บันทึกลง `hook_errors.txt` ข้างไฟล์เซฟ) ยกเว้นตั้ง `HD_STRICT_HOOKS=1` (smoke test ตั้งไว้) จะ raise ให้เทสต์ล้ม
- ทะเบียนกลางที่ใช้คู่กัน: `loot.register_item`, `assets.register_item_icon`, `assets.register_prop`, `monsters.BEHAVIORS` / `SHAPE_PAINTERS`,
  `p.add_buff(kind, sec, amount, label)` / `p.buff(kind)`, `self.toast(...)`

## จุดที่ใช้ร่วมกัน (Shared seams) — ต้องประสานก่อนแก้

ไฟล์เหล่านี้หลาย chat อาจแตะ ให้แก้ทีละน้อย ระบุชัดใน commit และเลี่ยงแก้พร้อมกันถ้าทำได้:

1. **`systems/actions_system.py`** — `player_action` คือ "ลำดับการตรวจการกดปุ่ม" (NPC → quest board →
   alms box → collector → สัตว์ → festival → ร้าน → เตียง → เฟอร์นิเจอร์ → บันไดเหมือง → เก็บเกี่ยว →
   ตกลงไปที่ `use_tool`) **ลำดับ = ความสำคัญ** — *ตั้งแต่ 2026-09:* interaction ใหม่ให้ใช้ hook
   `_interact_early_NN_*` / `_interact_late_NN_*` / `_on_tool_*` ใน mixin ตัวเองแทนการเพิ่ม branch ที่นี่
2. **`game.py` (core)** — `__init__`, loop, `reset`, `warp`, `on_new_day`, `update`, `on_keydown`,
   และ helper กลาง `_grant_xp / _popup / add_shake / _max_hp / _count_all / _remove_all`
   แก้เฉพาะเมื่อจำเป็นจริงๆ (`_count_all/_remove_all` = นับ/หักไอเทมรวมสองผู้เล่น ใช้โดย quests.py + cooking.py)
3. **`systems/save_system.py`** — *ตั้งแต่ 2026-09:* state ใหม่ของโดเมนให้คืนจาก `_on_save_<domain>()` (key ขึ้นต้นด้วยชื่อโดเมน,
   JSON ล้วน) และโหลดใน `_on_load_<domain>(d)` ด้วย `d.get(key, default)` (ทนเซฟเก่า) — ไม่ต้องแก้ `_collect_save/_apply_save`
   smoke test ตรวจว่าเซฟ → reset → โหลด แล้วได้ dict เดิมเป๊ะ
4. **`assets/props.py` → `prop_sprite`** และ **`assets/items.py` → `item_icon`** — dispatcher ของสไปรต์
   เพิ่มสไปรต์ใหม่ = เขียนฟังก์ชันในไฟล์เดียวกัน + ลงทะเบียนใน dispatcher — หรือ (2026-09) เรียก
   `assets.register_prop(kind, painter)` / `assets.register_item_icon(item_id, painter)` จากไฟล์ของโดเมนตัวเอง
5. **`world.py`** — แผนที่ area เป็นของ Chat 5 ถ้า chat อื่นอยากวาง prop/warp ใน area ให้ประสานกับ Chat 5

## กติกา (อ่านก่อนเริ่มทุก chat)

1. **แก้เฉพาะไฟล์ของโดเมนตัวเอง** ถ้าต้องการพฤติกรรมจากโดเมนอื่น ให้เรียกผ่าน `self.method()`
   ไม่ก็อปโค้ดข้ามโดเมน
2. **mixin ห้ามมี `__init__`** — state ของโดเมนสร้างใน hook `_on_reset_<domain>()` ของตัวเอง (เรียกท้าย `Game.reset()`)
   state ส่วนกลางยังอยู่ใน `Game.reset()`/`__init__` (core)
3. **helper กลาง** (`_grant_xp`, `_popup`, `add_shake`, `_max_hp`, `_count_all`, `_remove_all`) อยู่ใน core — เรียกผ่าน `self` อย่าทำซ้ำ
4. **เพิ่มฟีเจอร์ในโดเมน** → ใส่ method ใน mixin ของตัวเอง แล้วเสียบผ่าน **hook bus** (ดูหัวข้อ Hook bus ด้านบน);
   **เพิ่ม interaction** → seam #1; **เพิ่ม state เซฟ** → seam #3; **เพิ่มสไปรต์** → seam #4; **แจ้งโดเมนอื่น** → `self.emit(event, ...)`
5. **assets**: ใช้ helper/พาเลตจาก `_base` เท่านั้น (เช่น `from ._base import _surf, _cache`)
   submodule ห้าม import กันเอง — กันลูปและกันชนกัน
6. **gotcha ตอนทดสอบ (สำคัญ):** bash (mount) บางครั้งอ่านไฟล์ที่เพิ่งแก้เป็นฉบับ "ถูกตัด/มี null byte"
   ทำให้ขึ้น SyntaxError/null-byte ปลอม — เครื่องมือ Read/Edit คือฉบับจริงเสมอ
   วิธีทดสอบ headless ที่เชื่อถือได้: ก็อปทั้ง repo ไป `/tmp` แล้วล้าง null ด้วย `tr -d '\0'` ก่อน compile/run
7. **นิยามของ "เสร็จ" (Definition of Done):** ก่อนปิดงานทุกครั้ง ต้อง
   (ก) `py_compile` ทุกไฟล์ผ่าน, (ข) `py tools/smoke_test.py` เขียว ("0 failed") รวมเทสต์รายโดเมน `tools/tests/test_*.py`,
   (ค) ยืนยันว่าพฤติกรรมเดิมไม่เปลี่ยน (ดูภาพจาก `--shots DIR` ด้วย)
8. **Single Source of Truth — ห้าม hard-code ข้อมูลที่มีทะเบียนกลาง** (ดู `docs/TASK_no_hardcode.md`):
   ชื่อปุ่มในป้าย/hint ต้องประกอบจาก `P1_KEYS/P2_KEYS` ผ่าน `ui.key_label()` (ห้ามพิมพ์ "SPACE"/"ENTER"),
   ลิสต์ไอเทม/มอนสเตอร์/props/เฟอร์นิเจอร์ ต้อง derive จากทะเบียน (`loot.MATERIALS`, `CROPS`, `FISH_DATA`,
   `ARCHETYPES`, `F.CAT`, `PROPS`), ชื่อ area ใช้ `name.upper()` ไม่ทำ dict ซ้ำ, จุดโต้ตอบใช้ attribute บน
   area (แพทเทิร์น `donation_box`/`collector`) ไม่ฝังพิกัดในโค้ด — เพิ่มของใหม่ที่ทะเบียนที่เดียวแล้ว
   gallery/ร้าน/เควสต์/HUD ต้องเห็นเองทั้งหมด

## วิธีรัน / ทดสอบ

รันเกมจริง (เครื่องผู้ใช้): `start_game.bat` / `Play HarvestDuo.bat` หรือ `py main.py` (`py` = Python ที่มี pygame บนเครื่องนี้)

ทดสอบ headless (อัปเดต 2026-09):
```bash
py tools/smoke_test.py                   # กวาดทั้งเกม ~20 วินาที ต้องจบด้วย "0 failed"
py tools/smoke_test.py --shots DIR       # เซฟภาพ PNG ไว้ตรวจด้วยตา
py tools/smoke_test.py --only sec1,sec2  # รันบาง section
```
smoke test กวาดทุก area / ไอเทมใน hotbar / ทิศ / จุดโต้ตอบ / custom state / hotkey / event, เหมืองชั้น 1-100, ทุกฤดูและอากาศ,
save round-trip + เซฟเก่า และเรียก `tools/tests/test_<domain>.py` (แต่ละไฟล์นิยาม `run(g, check, H)`)

**สำคัญ — ห้ามแตะเซฟจริง:** สคริปต์ headless ที่เขียนเองต้องตั้ง env `APPDATA` เป็นโฟลเดอร์ชั่วคราว **ก่อน** import `src`
(`savegame` คำนวณ path ตอน import) + `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy HD_STRICT_HOOKS=1` และ stub `webbrowser.open`
— ก็อปส่วนตั้งค่าด้านบนของ `tools/smoke_test.py` ไปใช้ (เคยมีสคริปต์ที่ย้ายแค่ `SAVE_PATH` แล้วลบ `savegame.bak` จริงไปแล้ว)
