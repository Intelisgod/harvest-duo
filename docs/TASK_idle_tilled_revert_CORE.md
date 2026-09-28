# คำขอถึง Chat 0 (Core): ผูกระบบ "ดินไถปล่อยว่าง 2 วัน revert"

ฝั่ง Chat 2 ทำเสร็จแล้ว: เพิ่มเมธอด `FarmMixin._revert_idle_tilled(days=2)` ใน
`src/systems/farm_system.py` (เทสต์ logic ผ่านครบ) เมธอดนี้พึ่ง state + การเรียก 3 จุดจาก Core:

## 1) init ตัวนับใน reset()
ใน `game.py` reset()/__init__ (ตรงกลุ่มที่ตั้ง world-state เช่น ก่อน `self._spawn_area_entities()` ~บรรทัด 225)
เพิ่ม:
```python
self.tilled_idle = {}      # {(area, gx, gy): empty_days} -- ตัวนับวันที่ดินไถถูกปล่อยว่าง
```

## 2) เรียกทุกเช้าใน on_new_day()
ใน `game.py` `on_new_day()` (~บรรทัด 385) หลังลูป advance พืช (บรรทัด 387-388) เพิ่ม 1 บรรทัด:
```python
for key, crop in list(self.world.crops.items()):
    crop.advance_day()
self._revert_idle_tilled()        # <-- เพิ่มตรงนี้ (หลังเช็คพืช)
self.world.watered.clear()
...
```
> วางหลัง advance พืชเพื่อให้เช็ค "มีพืช = ใช้งานอยู่" จากสถานะล่าสุด ลำดับเทียบกับ weather/sprinkler
> ไม่สำคัญ เพราะ revert จะ discard ทั้ง tilled+watered ของช่องที่หลุด (ลูป weather วนบน tilled อยู่แล้ว)

## 3) persist ใน save/load
คีย์ใช้ฟอร์แมตเดียวกับ tilled/crops (`"area|gx|gy"`) — helper `kstr`/`parse` มีอยู่แล้วในเมธอดทั้งสอง

ใน `save_system.py` `_collect_save()` (เพิ่มใน dict ที่ return ~บรรทัด 73):
```python
"tilled_idle": {kstr(k): v for k, v in self.tilled_idle.items()},
```
ใน `save_system.py` `_apply_save()` (เพิ่มใกล้จุดโหลด tilled/watered ~บรรทัด 92-93):
```python
self.tilled_idle = {parse(s): int(v) for s, v in d.get("tilled_idle", {}).items()}
```
> ใช้ `d.get("tilled_idle", {})` เพื่อทนเซฟเก่าที่ยังไม่มีคีย์นี้ (ตามกติกา seam #3)

## ลำดับ build เขียว
- ข้อ 1+2 ต้องมาคู่กัน (ถ้าเรียก _revert_idle_tilled โดยไม่ init tilled_idle จะ AttributeError)
- ข้อ 3 จะลงพร้อมกันหรือทีหลังก็ได้ — ถ้ายังไม่ลง save แค่ตัวนับรีเซ็ตเมื่อโหลดเกม (ดินที่ค้างปล่อยว่าง
  จะเริ่มนับใหม่หลังโหลด ไม่พัง)

## Definition of Done (รวมทั้งระบบ หลัง Core ลงครบ)
- py_compile ทุกไฟล์ผ่าน
- headless: ไถช่องเปล่าในฟาร์ม -> เรียก on_new_day() 2 ครั้ง -> ช่องหลุดจาก world.tilled แล้ว
  และช่องที่มีพืช (อยู่ใน world.crops) ยังอยู่ครบ
- save/load roundtrip: ตัวนับ tilled_idle คงค่าข้ามการเซฟ และเซฟเก่า (ไม่มีคีย์) โหลดได้ไม่พัง

## หมายเหตุการทดสอบ (gotcha #6)
ตอนนี้ bash (mount) อ่าน `farm_system.py`/`quests.py` แบบ "ถูกตัด" (truncated) ทำให้ py_compile ทั้ง repo
ใน sandbox ขึ้น SyntaxError ปลอม — ไฟล์จริง (ผ่าน Read tool) สมบูรณ์ดี เมื่อรัน headless ให้ก็อป src ไป
/tmp และตรวจ `wc -l` ให้ตรงกับไฟล์จริงก่อน (ถ้าไม่ตรง = mount ตัด ให้ก็อปซ้ำจนตรง) หรือรันบนเครื่องผู้ใช้
