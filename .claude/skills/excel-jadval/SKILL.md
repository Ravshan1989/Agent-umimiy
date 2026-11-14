---
name: excel-jadval
description: Excel (.xlsx) moliyaviy jadvallar, hisob-kitoblar, ombor ro'yxatlari va formulalar (=SUM, =AVERAGE) yaratish.
---

# Excel (.xlsx) jadvallar yaratish ko'nikmasi

Foydalanuvchi Excel jadval, smeta, byudjet yoki hisob-kitob so'raganda:
1. `create_spreadsheet` asbobini chaqiring (`name="hisobot.xlsx"`).
2. `sheets` ro'yxatida har bir varaq uchun `name` va `rows` bering (birinchi qator — ustun sarlavhalari).
3. Sonli ustunlarni string emas, haqiqiy son (`int`/`float`) sifatida kiriting.
4. Jami va o'rtacha qiymatlar uchun Excel formulalaridan foydalaning: `=SUM(B2:B10)`, `=AVERAGE(C2:C10)`.
