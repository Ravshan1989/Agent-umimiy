# Agent-umimiy — Telegram media bot

Funksiyalar: havoladan video yuklash (Instagram, TikTok, YouTube va b.), qo'shiq topish, rasm orqali kino topish.

## Ishga tushirish
```
pip install -r requirements.txt
export BOT_TOKEN=...   # @BotFather dan
python -m bot.main
```
Videoni birlashtirish uchun `ffmpeg` o'rnatilgan bo'lishi kerak. Kalitlar faqat muhit o'zgaruvchilarida (`.env.example` ga qarang), kodga yozilmaydi.

## Test
```
pip install -r requirements-dev.txt && pytest
```
