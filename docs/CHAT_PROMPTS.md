# Prompt เริ่มต้นของแต่ละ chat

วิธีใช้: เปิด chat ใหม่ในโปรเจกต์นี้ 1 chat ต่อ 1 โดเมน แล้วก็อป "บล็อก" ด้านล่างไปวางเป็นข้อความแรก
แต่ละ chat จะแก้คนละไฟล์ จึงทำงานพร้อมกันได้โดยแทบไม่ชนกัน รายละเอียดเต็มอยู่ใน `docs/ARCHITECTURE.md`

กติกาที่ทุก chat ใช้ร่วมกัน (ย่อ): แก้เฉพาะไฟล์ของโดเมนตัวเอง • เรียกข้ามโดเมนผ่าน `self.method()` เท่านั้น •
mixin ห้ามมี `__init__` (state ตั้งใน `Game.reset()` เท่านั้น) • helper กลาง `_grant_xp/_popup/add_shake/_max_hp`
อยู่ใน core เรียกผ่าน `self` • **ก่อนปิดงานต้อง `py_compile` ทุกไฟล์ + รัน headless smoke test (boot + กวาด 7 area +
save/load) ให้เขียว** • ถ้า bash อ่านไฟล์เพี้ยน/null byte ให้ก็อป `src/` ไป `/tmp` แล้วล้างด้วย `tr -d '\0'` ก่อน compile

---

## Chat 0 — Core & Infra (กลาง, แก้อย่างระวัง)

```text
นี่คือเกม Harvest Duo (Pygame, 2 ผู้เล่นบนคีย์บอร์ดเดียว) โค้ดถูกแบ่งเป็น mixin ต่อโดเมนแล้ว
โปรดอ่าน docs/ARCHITECTURE.md ก่อนเริ่ม

โดเมนของ chat นี้: Core & Infra (เอนจิน/วงจรเกม) — เป็นไฟล์กลางที่โดเมนอื่นพึ่งพา ให้แก้อย่างระวัง
ไฟล์ที่ดูแล: src/game.py, src/systems/save_system.py, src/systems/actions_system.py,
  src/savegame.py, src/settings.py, src/timesystem.py, src/camera.py, src/inventory.py,
  src/entities.py (คลาส Player), src/particles.py, src/audio.py, src/lighting.py, src/weather.py
รับผิดชอบ: __init__/main loop/reset/warp/on_new_day/update/on_keydown, schema การเซฟ
  (_collect_save + _apply_save ต้องแก้คู่กันและทนเซฟเก่า), การ "เดินสาย" interaction ใน
  actions_system.player_action (ลำดับ = ความสำคัญ), และ helper กลาง

หมายเหตุ: actions_system.py และ save_system.py เป็น "จุดใช้ร่วม" — chat โดเมนอื่นจะมาขอให้เพิ่ม
branch interaction หรือ field เซฟ ให้รับคำขอเหล่านั้นและทำให้ลำดับ/ความเข้ากันได้ของเซฟถูกต้อง
อย่าใส่ logic ของฟีเจอร์ไว้ใน core — core แค่เรียก self.<method> ของ mixin โดเมนนั้น

งานแรกที่อยากให้ทำ: <อธิบายงาน เช่น "เพิ่มระบบสภาพอากาศพายุ" / "ปรับสมดุลพลังงาน">
ก่อนปิดงาน: py_compile ทุกไฟล์ + รัน headless smoke test ให้เขียว และยืนยันพฤติกรรมเดิมไม่พัง
```

---

## Chat 1 — Combat, Mining & Progression

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: Combat, Mining & Progression
ไฟล์ที่ดูแล: src/systems/combat_system.py (_reward_kill, sword_attack),
  src/progress.py (สกิล/XP/เลเวล/เพิร์ก), src/monsters.py (อาร์คีไทป์มอนสเตอร์ + สเกลตามชั้นเหมือง),
  src/loot.py (แร่/วัสดุ/drop table/มูลค่าขาย), src/craft.py (ทีเออร์เครื่องมือ + Workbench)
  พฤติกรรมคลาส Monster อยู่ใน entities.py — ถ้าต้องแก้ ให้ประสานกับ Core
ขอบเขต: แก้เฉพาะไฟล์ข้างบน เรียกของข้ามโดเมนผ่าน self (เช่น self._grant_xp, self._popup, self.add_shake)
  การได้ XP ใช้ self._grant_xp(p, skill, amount) เสมอ; โชคจากวัด (self.fortune[idx]) มีผลกับ drop แล้ว
เพิ่ม "ทีเออร์เครื่องมือ/มอนสเตอร์/แร่/เพิร์ก" ได้ในไฟล์ของตัวเอง; ถ้าจะเพิ่มวิธีโจมตีใหม่ที่ผูกกับการกดปุ่ม
  ให้ขอ Core เพิ่ม branch ใน actions_system (use_tool) แล้วเอา logic มาไว้ใน combat_system

งานแรก: <อธิบายงาน เช่น "เพิ่มบอสชั้น 50" / "เพิ่มสกิลใหม่">
ก่อนปิดงาน: py_compile + headless smoke test (รวมลงเหมือง+สู้+เก็บ drop) ให้เขียว
```

---

## Chat 2 — Farming, Animals & Cooking (+ ร้านค้า/เศรษฐกิจ)

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: Farming, Animals & Cooking + ระบบร้านค้า/ขายของ
ไฟล์ที่ดูแล: src/systems/farm_system.py (สัตว์/auto-collector/forest regrow),
  src/systems/shop_system.py (เมนูร้าน + ขายของ + sell_value = แหล่งราคากลาง),
  src/crops.py (พืช/การโต), src/animals.py (ปศุสัตว์+ผลผลิต), src/cooking.py (สูตรอาหาร)
ขอบเขต: แก้เฉพาะไฟล์ข้างบน; ราคาขายทุกอย่างต้องผ่าน sell_value() อย่า hard-code ที่อื่น
  การปลูก/รดน้ำ/เก็บเกี่ยว (ตรรกะการกดปุ่ม) อยู่ใน actions_system (Core) — ถ้าต้องเพิ่มพฤติกรรมเครื่องมือ
  ฟาร์มใหม่ ให้ขอ Core เพิ่ม branch แล้วเอา logic มาไว้ฝั่งเรา
เพิ่ม "พืช/สัตว์/อาหาร/สินค้าในร้าน" ได้ในไฟล์ของตัวเอง; ถ้าพืช/อาหารใหม่ต้องมีไอคอน ให้ขอ Chat 6 (assets)

งานแรก: <อธิบายงาน เช่น "เพิ่มพืชฤดูใบไม้ร่วง 3 ชนิด" / "เพิ่มสัตว์แกะ">
ก่อนปิดงาน: py_compile + headless smoke test (ปลูก/เก็บ/ขาย/เก็บผลผลิตสัตว์) ให้เขียว
```

---

## Chat 3 — Fishing & Foraging

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: Fishing & Foraging
ไฟล์ที่ดูแล: src/systems/fishing_system.py (_land_fish — รางวัล/XP/ทองโบนัส/ถ้วยรางวัล/แฟนแฟร์),
  src/fishing.py (FISH_DATA, ทีเออร์ปลา, สเตตเครื่อง cast/hook/reel, ปลาพิเศษเฉพาะบ่อป่า),
  src/critters.py (สัตว์/แมลงบรรยากาศ)
ขอบเขต: แก้เฉพาะไฟล์ข้างบน; การเหวี่ยงเบ็ด (กดปุ่ม) อยู่ใน actions_system (Core) ฝั่งเราจัดการ
  "ตอนปลาติดเบ็ดแล้ว" เท่านั้น โชคจากวัด (self.fortune) มีผลกับการหลุด/ดับเบิลแล้ว
  ปลาพิเศษ/ตำนาน gate ด้วย forest=True; ทีเออร์โบนัสอยู่ใน TIER_XP_BONUS/TIER_GOLD_BONUS
เพิ่ม "ปลา/ทีเออร์/critter" ได้ในไฟล์ของตัวเอง; สีปลา/ไอคอนใหม่ต้องเพิ่มใน assets (ขอ Chat 6: FISH_LOOK)

งานแรก: <อธิบายงาน เช่น "เพิ่มปลาตำนานตัวที่ 4" / "เพิ่มเหยื่อตกปลา">
ก่อนปิดงาน: py_compile + headless smoke test (cast/hook/_land_fish ทุกทีเออร์) ให้เขียว
```

---

## Chat 4 — Temple, Fortune, NPC & Quests

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: Temple, Fortune, NPC & Quests (สังคม/เหตุการณ์)
ไฟล์ที่ดูแล: src/systems/temple_system.py (_monk_fortune, _donate, DONATION_COST),
  src/systems/social_system.py (_talk_reward, _friendship_reward),
  src/npc.py (NPC/หัวใจ/ของขวัญ), src/quests.py (กระดานเควส), src/festival.py (เทศกาล)
ขอบเขต: แก้เฉพาะไฟล์ข้างบน; โชค (self.fortune[idx]) ถูกเคลียร์ทุกเช้าใน Game.on_new_day (Core)
  ผลของโชคไปออกที่ combat/fishing/farming (โดเมนอื่น) — ฝั่งเราคุมแค่ "การอ่านดวง/ทำบุญ"
  การโต้ตอบ NPC/กระดาน/กล่องบุญ เดินสายใน actions_system (Core) แล้วเรียก self._monk_fortune ฯลฯ
  แผนที่วัด/พระประธาน/props อยู่ใน world.py (Chat 5) — ประสานถ้าจะเพิ่มจุดในวัด

งานแรก: <อธิบายงาน เช่น "เพิ่ม NPC ใหม่ 2 คน" / "เพิ่มเทศกาลฤดูหนาว">
ก่อนปิดงาน: py_compile + headless smoke test (อ่านดวง/ทำบุญ/คุย NPC/รับเควส) ให้เขียว
```

---

## Chat 5 — World, Areas & Build

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: World, Areas & Build
ไฟล์ที่ดูแล: src/world.py (แผนที่ area/ไทล์/warp/วาง props/อาคาร/build_temple ฯลฯ),
  src/build.py (โหมดสร้าง), src/isofurn.py + src/homeiso.py (ห้องไอโซเมตริก),
  src/furniture.py (เฟอร์นิเจอร์+คุณภาพ), src/storage.py (หีบ), src/creator.py (สร้างตัวละคร)
ขอบเขต: แก้เฉพาะไฟล์ข้างบน; เมื่อเพิ่ม area ใหม่ ต้องเพิ่มค่าคงที่ AREA_* ใน settings.py (ขอ Core)
  และมักต้องให้ Core เพิ่ม warp/สแปอนใน _spawn_area_entities เพิ่ม prop = ต้องมีสไปรต์ใน
  assets/props.py (ขอ Chat 6) + ลงทะเบียนใน prop_sprite
  ปุ่ม/ไทล์โต้ตอบใหม่ใน area เดินสายผ่าน actions_system (Core)

งานแรก: <อธิบายงาน เช่น "เพิ่ม area ทะเลทราย" / "เพิ่มเฟอร์นิเจอร์ 5 ชิ้น">
ก่อนปิดงาน: py_compile + headless smoke test (World() สร้างครบทุก area + warp ไม่เด้ง) ให้เขียว
```

---

## Chat 6 — UI & Rendering

```text
เกม Harvest Duo (Pygame). โค้ดแบ่งเป็น mixin ต่อโดเมน — อ่าน docs/ARCHITECTURE.md ก่อน

โดเมนของ chat นี้: UI & Rendering (เลเยอร์การแสดงผล — ระบบอื่นถือ state เราเปลี่ยน state เป็นพิกเซล)
ไฟล์ที่ดูแล: src/systems/render_system.py (draw pipeline + HUD ทั้งหมด: draw_world/draw_entities/
  draw_prompts/draw_hud/แบนเนอร์โชค-ปลา ฯลฯ), src/ui.py (ฟอนต์/พาเนล/hotbar/minimap),
  src/menu.py, และ package src/assets/ ทั้งหมด (_base, chars, terrain, items, props)
ขอบเขต: แก้เฉพาะไฟล์ข้างบน; ห้ามเปลี่ยน logic เกม — อ่านค่าจาก self.* มาวาดเท่านั้น
  เพิ่มสไปรต์: เขียนฟังก์ชันในหมวดที่ใช่ (items.py/props.py/terrain.py/chars.py) ใช้ helper จาก _base
  เท่านั้น (submodule ห้าม import กันเอง) แล้วลงทะเบียนใน dispatcher (item_icon/prop_sprite) +
  re-export ใน assets/__init__.py ถ้าจำเป็นต้องเรียกจากนอก
  draw_world วาดหลายฟีเจอร์ inline (พืช/สปริงเกลอร์/ป้าย/เทศกาล) — ที่นี่คือจุดประสานงานภาพ

งานแรก: <อธิบายงาน เช่น "ปรับ HUD ให้อ่านง่ายขึ้น" / "เพิ่มสไปรต์ไอเทมชุดใหม่">
ก่อนปิดงาน: py_compile + headless smoke test (draw ครบ 7 area) + เซฟ PNG เฟรมมาดูด้วย Read
```

---

## Chat 7 — Mist City (เมืองนาฬิกาหยุดเดิน, โหมด 2D Side-scroller)

```text
เกม Harvest Duo (Pygame, 2D top-down, co-op 2 คนคีย์บอร์ดเดียว) โค้ดแบ่งเป็นโดเมนต่อแชท
อ่าน docs/ARCHITECTURE.md (กติกากลาง) และ docs/TASK_mist_city.md (สเปคเต็มของโดเมนนี้) ก่อนเริ่ม

โดเมนของ chat นี้: "Mist City — เมืองนาฬิกาหยุดเดิน" โหมดพิเศษ 2D side-scroller:
วาร์ปจากป่าเข้าเมืองซอมบี้มุมมองข้าง (gravity/กระโดด) ฟาร์มชิ้นส่วนใต้เวลาจำกัด 5 นาที (+ตู้ยาฮีล 3 จุด)
ไฟล์ที่ดูแล (สร้างใหม่ทั้งหมด เป็นเจ้าของคนเดียว): src/mistcity/
  world2d.py / player2d.py / zombies.py / mist_system.py (รายละเอียดใน TASK doc)
กฎเหล็ก: ห้ามแก้ไฟล์นอก src/mistcity/ — จุดเชื่อม (AREA_MIST ใน settings, ประตูวาร์ปในป่า,
ลงทะเบียนดรอป 7 ชนิดใน loot.MATERIALS, hook state ใน Core แบบ guarded) ให้แจ้งผู้ใช้ส่งคำขอไป
Chat 0 / Chat 5 / Chat 1 ตามที่ระบุใน TASK doc
สำคัญสุด: co-op 2 คนต้องเล่นได้เต็มรูปแบบ (กล้องตามสองคน, ตาย=ผีรอชุบ) และโทนภาพ pastel เดิม

เริ่มจาก player2d (ฟิสิกส์) + world2d (พื้น/แพลตฟอร์ม) ให้เดิน-กระโดดได้ก่อน แล้วค่อย zombies + mist timer
ก่อนปิดงาน: py_compile + headless เทสต์ครบ flow (เข้า-สู้-เก็บ-ตาย/ชุบ-หมดเวลา-ออก-ขายของ)
+ เซฟ PNG เฟรมมารีวิวภาพ + รัน smoke test เกมหลักให้เขียว (โหมดใหม่ห้ามกระทบของเดิม)
```
