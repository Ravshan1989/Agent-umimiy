# Agent Umimiy — React web interfeysi

React + Vite + TypeScript interfeysi mavjud Python veb-server API'siga ulanadi.

## Ishga tushirish (development)

1. Python serverni ishga tushiring: `python app.py --serve --host 127.0.0.1 --port 8080`.
2. Alohida terminalda:
   `cd frontend`
   `npm install`
   `npm run dev`
3. `http://localhost:5173` manzilini oching. Vite `/api` so‘rovlarini 8080-portdagi Python serverga uzatadi.

Serverning taklif kodi orqali ro‘yxatdan o‘ting yoki mavjud hisobga kiring.

## Release build

`npm install && npm run build` buyrug‘i `dist/` papkasini yaratadi. Release workflow uni `agent_umimiy/static/web/` ichiga joylab, PyInstaller orqali Windows va Linux dasturiga qo‘shadi. O‘rnatilgan dasturda React interfeysi asosiy sahifada ochiladi; frontend build mavjud bo‘lmasa, eski HTML sahifa zaxira sifatida ishlaydi.

## Ulangan imkoniyatlar

- Server sessiyasi orqali kirish va ro‘yxatdan o‘tish
- Suhbatlarni yaratish, tanlash va o‘chirish
- Haqiqiy agentlar ro‘yxati va agent tanlash
- SSE orqali oqimli javoblar va ishni to‘xtatish
- Fayl biriktirish va agent yaratgan fayllarni yuklab olish
- Haqiqiy server statistikasi; demo raqamlar ishlatilmaydi

## Hozirgi chegaralar

React interfeysi Python serveridagi mavjud web API bilan ishlaydi. Desktop GUI'dagi loyiha papkasi, shell tasdiqlash, brauzer avtomatizatsiyasi va MCP boshqaruvi bu web API'da hozircha mavjud emas. Shu sababli tegishli menyular hozircha bu cheklovni ochiq ko‘rsatadi, ular bajarilmagan ishni bajargandek ko‘rsatmaydi.
