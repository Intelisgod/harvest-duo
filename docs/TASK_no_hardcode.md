# TASK: Single Source of Truth — กวาดล้าง hard-code ให้ทุก function อัปเดตตามกันเอง

หลักการ: **ข้อมูลทุกชนิดมี "ทะเบียนกลาง" (registry) ที่เดียว** — ทุก UI/ระบบต้อง "ดึง" จากทะเบียน
ห้ามพิมพ์ค่าซ้ำ เพื่อให้เพิ่มของใหม่ที่ทะเบียนแล้ว gallery/HUD/ป้าย/คีย์ลัด อัปเดตเองทั้งเกม

## ทะเบียนกลาง (แหล่งความจริงของแต่ละเรื่อง)
| เรื่อง | ทะเบียน |
|---|---|
| คีย์ของผู้เล่น | `settings.P1_KEYS / P2_KEYS` (rebind ได้) — ชื่อปุ่มใช้ `pygame.key.name()` |
| ไอเทม/วัสดุ + ราคา | `loot.MATERIALS`, `crops.CROPS`, `fishing.FISH_DATA`, `cooking.FOODS`, `animals.ANIMALS/PRODUCE_SELL` |
| มอนสเตอร์ | `monsters.ARCHETYPES` |
| เฟอร์นิเจอร์ | `furniture.CAT / CATALOG` |
| props | dict ใน `assets.props.prop_sprite` (ควร expose เป็น `PROPS` ระดับโมดูล) |
| ชื่อ area | คีย์ของ `World.areas` / ค่าคงที่ `AREA_*` — ป้าย/HUD ใช้ `name.upper()` |
| จุดโต้ตอบใน area | attribute บน area (`shop/bed/ladder/quest_board/donation_box/collector`) — ตามแพทเทิร์นนี้เสมอ |

## จุดที่ hard-code อยู่ตอนนี้ (audit 2026-06-04) — แก้แล้วติ๊กออก
| ที่ | ปัญหา | วิธีแก้ | เจ้าของ |
|---|---|---|---|
| `gallery.py:57` `_MATERIALS=[...]` | ลิสต์วัสดุพิมพ์มือ → ของใหม่ (เช่นดรอป Mist City) ไม่โผล่ | `list(loot.MATERIALS)` | Chat 6 |
| `render_system.py:545` `"SPACE"/"ENTER"` | ป้ายปุ่มไม่ตาม rebind | `pygame.key.name(P1_KEYS["action"]).upper()` (helper กลาง ดูข้างล่าง) | Chat 6 |
| `ui.py:279` `"P1: W/S move - SPACE select - Q close"` | เหมือนกัน | ประกอบสตริงจาก P1_KEYS ผ่าน helper | Chat 6 |
| `render_system.py:584` dict ชื่อ area ใน HUD | ขาด beach (และ mistcity ในอนาคต) | `self.world.current.upper()` + special-case mine level | Chat 6 |
| `render_system.py:410` `signdest` dict | ซ้ำซ้อน (มี fallback `.upper()` แล้ว) | ลบ dict ใช้ `.upper()` อย่างเดียว | Chat 6 |
| `ui.py:201` + `ui.py:226` dict ชื่อ area ใน minimap | `:226` มีแค่ 4 area! | ใช้ `.upper()` | Chat 6 |
| `render_system.py:636` "Press B" | ปุ่ม B จริงอยู่ใน on_keydown (K_b) | เพิ่ม `BUILD_KEY` ใน settings แล้วทั้ง on_keydown+ป้ายใช้ตัวเดียวกัน | Core + Chat 6 |
| ~~`quests.py:92` ลิสต์วัสดุใน pool เควสต์~~ ✅ 2026-06-04 | ของใหม่ไม่เข้าเควสต์เอง | derive จาก `loot.MATERIALS` แล้ว (กรอง `value>0`; `where()` มี fallback ตาม cat) | Chat 4 |
| `actions_system.py:151` `fb=(20,12)` แผงเทศกาล | ตำแหน่งฝังในโค้ด | ให้ world ตั้ง `area.festival_stall` แล้ว actions/render อ่าน attr (ตามแพทเทิร์น donation_box) | Chat 5 + Core |
| `assets/props.py` dict ใน `prop_sprite` | ทะเบียน props ไม่ enumerate ได้ | ยกเป็น `PROPS = {...}` ระดับโมดูล แล้ว `prop_sprite` อ่านจากมัน (gallery iterate ได้) | Chat 6 |

## helper กลางที่ต้องมี (ทำครั้งเดียว)
`menu.py:11` มี `pygame.key.name(code).upper()` อยู่แล้ว → **ย้าย/ทำซ้ำเป็นของกลางใน `ui.py`**:
```python
def key_label(code):              # ui.py (module-level, ใช้ได้ทุกเมนู)
    return pygame.key.name(code).upper()
def keys_hint(*pairs):            # ("เลือก", P1_KEYS["action"]), ... -> "เลือก SPACE - ..."
    return "  -  ".join(f"{label} {key_label(c)}" for label, c in pairs)
```
ทุกเมนู (shop/quest/cook/craft/storage/build/gallery) ประกอบ hint จาก helper นี้ — rebind แล้วป้ายตามทันที

## กติกาถาวร (เพิ่มใน ARCHITECTURE.md แล้ว)
เพิ่มของใหม่ = เพิ่มที่ทะเบียนที่เดียว แล้วทุกอย่าง (gallery, ร้าน, เควสต์, ไกด์, ป้าย) ต้องเห็นเอง
ถ้าพบว่าต้องไปแก้ไฟล์ที่สอง "เพื่อให้ของโผล่" = มี hard-code แอบอยู่ → แก้ให้ derive ก่อนแล้วค่อยไปต่อ

## Definition of Done
แต่ละแชทแก้รายการของตัวเอง + ทดสอบ: rebind คีย์แล้ว hint เปลี่ยนตาม, เพิ่มไอเทมปลอม 1 ตัวใน
loot.MATERIALS แล้วเห็นใน gallery+ขายได้+เข้า pool เควสต์โดยไม่แตะไฟล์อื่น, HUD แสดงชื่อ beach ถูกต้อง
