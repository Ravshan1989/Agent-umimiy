# Agent Umumiy — Ultra Modern web interfeys

React + Vite + TypeScript frontend, mavjud Python server API bilan ishlaydi.

## Lokal ishlab chiqish

1. Python serverni ishga tushiring: `python -m agent_umimiy --serve --host 127.0.0.1 --port 8123`
2. Ikkinchi terminalda:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. Vite `/api` so‘rovlarini Python serverga yo‘naltiradi. Brauzerda `http://localhost:5173` ni oching.

## Release / ishlab chiqarish

```bash
cd frontend
npm install
npm run build
```

Build natijasi `agent_umimiy/static/web` ichiga yoziladi. Python server shu build mavjud bo‘lsa, `/` manzilida yangi React interfeysini beradi; build bo‘lmasa eski ichki sahifa zaxira sifatida qoladi. PyInstaller va Python paket konfiguratsiyasi build fayllarini release tarkibiga qo‘shadi.

## Haqiqiy ishlaydigan imkoniyatlar

- Python serverdagi mavjud login va ro‘yxatdan o‘tish oqimi.
- Server sozlamasidan agentlarni olish va agent tanlash.
- Suhbat yaratish, ro‘yxatlash, o‘chirish va SSE orqali jonli javob.
- Agent ishini to‘xtatish.
- Rasm, PDF, Word, Excel va qo‘llab-quvvatlanadigan fayllarni biriktirish.
- Agent yaratgan fayllarni yuklab olish.
- Haqiqiy foydalanuvchi/suhbat ma’lumotlaridan hisoblagichlar.
- Moslashuvchan desktop va mobil maket hamda CSS robot animatsiyasi.

## Chegaralar

Web server ataylab CLI/shell, lokal brauzer boshqaruvi va MCP administrator amallarini masofaviy foydalanuvchiga bermaydi. Desktop ilovadagi barcha lokal boshqaruv funksiyalari web API’da hozircha mavjud emas. AI javobi uchun server egasi `agents.json` ichida kamida bitta provider va API credential sozlashi kerak. Ro‘yxatdan o‘tish uchun server taklif kodi talab qilinadi.
