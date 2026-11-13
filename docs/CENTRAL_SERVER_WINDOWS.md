# Windows'da markaziy server

## Asosiy kompyuter

1. `AgentUmimiy.exe` ni ishga tushiring. Dastur markaziy serverni va yangi oynani o'zi ochadi.
2. Birinchi marta bo'lsa, **Hisob yaratish**ni bosing. Asosiy kompyuterda taklif kodi avtomatik kiritiladi.
3. Hisobga kirgach, **Sozlamalar → Markaziy server** bo'limidan mahalliy tarmoq manzili va taklif kodini nusxalang.
4. Tarmoqdan ulanish bloklansa, **Windows Firewall'da ruxsat berish** tugmasini bosing va Windows tasdiqlashini qabul qiling.
5. Asosiy kompyuterda Agent Umimiy ochiq tursin. Ilova yopilsa server ham to'xtaydi.

## Xodimlar kompyuteri

1. Asosiy kompyuter va xodimlarning kompyuterlari bir xil ishonchli Wi‑Fi/LAN tarmog'ida bo'lsin.
2. Brauzerda asosiy kompyuterdan olingan tarmoq manzilini oching. `127.0.0.1` manzilini boshqa kompyuterga yubormang.
3. **Hisob yaratish**ni tanlab, ism, parol va asosiy kompyuterdan berilgan taklif kodini kiriting.
4. Xodim kompyuterlariga EXE yoki Python o'rnatish shart emas.

## Yig'ish

Yig'ish kompyuterida Python 3.12 va Node.js o'rnatilgan bo'lsin. `packaging/build_windows.bat` frontend'ni yig'ib, keyin EXE tayyorlaydi. Yig'ilgan dastur `dist/AgentUmimiy/AgentUmimiy.exe` ichida bo'ladi. EXE ishlaydigan asosiy kompyuterda Microsoft Edge WebView2 Runtime kerak bo'lishi mumkin.

> Server brauzer ulanishida HTTP ishlatadi. Uni faqat ishonchli ichki tarmoqda ishlating.

