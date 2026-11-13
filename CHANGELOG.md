# O'zgarishlar tarixi / Changelog

Barcha muhim o'zgarishlar shu faylda qayd etiladi.
Format [Keep a Changelog](https://keepachangelog.com/) asosida, loyiha
[Semantik versiyalash](https://semver.org/lang/uz/) qoidasiga amal qiladi.

## [Nashr qilinmagan] / [Unreleased]

## [0.4.0] - 2026-11-13

### Qo'shildi / Added
- **Yangi ish stoli oynasi**: dastur endi React interfeysini pywebview oynasida ochadi; kirish
  bir martalik kalit bilan avtomatik bo'ladi. Klassik Tk oynasi `--legacy-gui` bilan va
  Sozlamalardagi tugma bilan ochiladi.
- **Bosh sahifa paneli**: statistik kartalar, agentlar/fayllar/loyihalar ustunlari, tezkor amallar,
  rejalashtirilgan vazifalar va bildirishnomalar; pastda suhbat maydoni va mikrofon tugmasi.
- **Dastur ikonkasi**: `packaging/AgentUmimiy.ico` (AU belgisi) exe, o'rnatuvchi va oyna uchun.

### Tuzatildi / Fixed
- **GitHub'da yig'ilgan exe ishga tushmasligi**: CI skriptida tkinter yashirin importlari,
  Tcl/Tk uchun runtime-hook va oyna ikonkasi yo'q edi; `--windowed` bo'lgani uchun xato ham
  ko'rinmasdi. Endi CI mahalliy build bilan bir xil va to'plam tarkibini tekshiradi.
- **So'rov tanasi o'qilmay javob berilishi**: xato javoblarida (415, 401, 413) Windows ulanishni
  RST bilan uzar edi va mijoz xato matnini o'qiy olmasdi.
- **Ish stoli hisobi**: OS foydalanuvchi nomi bilan ro'yxatdan o'tgan veb-foydalanuvchi hisobi
  oynaga berilib qolishi mumkin edi; endi hisob `meta` jadvalidagi id bo'yicha bog'lanadi.
- **DNS rebinding**: desktop rejimida boshqa domen orqali yuborilgan so'rovlar rad etiladi.
- **Oyna o'lchami**: oyna ekrandan katta ochilmaydi, kichik noutbuklarda to'liq ekranga o'tadi.
- `/api/workspace` mahalliy ma'lumotni (loyiha papkasi, MCP plaginlar, skills) faqat
  dasturning o'z oynasiga beradi, `--serve` rejimidagi veb-foydalanuvchilarga bermaydi.

## [0.3.0] — 2026-11-12

### Qo'shildi / Added
- **Fayl yaratish**: agent tayyor Word (.docx), Excel (.xlsx) va matn fayllarini yaratadi (`create_document`,
  `create_spreadsheet`); oynada bosib ochiladi, veb-serverda yuklab olinadi.
- **Jonli ko'rinish**: veb-serverda agent yaratgan sahifa/diagramma (.html) va jadval (.xlsx, .csv) chat yonidagi
  qum qutisi (sandbox) oynasida ochiladi.
- Excel o'qishda hali hisoblanmagan formulalar formula matni bilan ko'rsatiladi.
- **Telefonda ilova kabi (PWA)**: veb-server sahifasini iPhone va Android'da bosh ekranga qo'shish mumkin
  (belgi, to'liq ekran). HTTPS proksi ortida ishlash: `X-Forwarded-*` sarlavhalari, `Secure` cookie.
- **Veb-server dastur bilan birga**: Sozlamalar → «Veb-server» da yoqiladi (manzillar, taklif kodi, yangi kod);
  yoqilgach dastur har ochilganda o'zi ishga tushadi.
- Oyna uchun haqiqiy Tk bilan tutun sinovlari (CI'da virtual ekran ostida).
- **Linux paketi**: `AgentUmimiy-Linux-x86_64.tar.gz` har nashrda Windows o'rnatuvchisi bilan birga yig'iladi.
- Yig'ilgan dastur har build'da veb-server rejimida ishga tushirib sinaladi.

### Xavfsizlik / Security
- Veb-server so'rovlarini tekshirish kuchaytirildi (noto'g'ri va haddan katta `Content-Length` rad etiladi).
- Plagin (MCP) asboblari va brauzer amallari uchun ruxsat chegaralari qat'iylashtirildi.
- Office fayllari va CSV o'qishda hajm chegaralari qo'shildi.

### O'zgardi / Changed
- Ishlatilmaydigan kod olib tashlandi.

## [0.2.0] — 2026-11-11

### Qo'shildi / Added
- **Oqimli javoblar (streaming)**: Claude, OpenAI-mos, Gemini va Ollama agentlarida matn yozilishi bilan ko'rinadi;
  to'xtatish javob o'rtasida ham darhol ishlaydi.
- **Veb-server rejimi** (`--serve`): lokal tarmoqdagi odamlar brauzerdan kirib ishlatadi. Foydalanuvchilar
  (taklif kodi bilan ro'yxatdan o'tish), alohida suhbatlar, oqimli chat, fayl va skrinshot biriktirish.
- Skrinshotni chatga **Ctrl+V** bilan qo'yish (clipboard'dagi rasm yoki nusxalangan fayllar biriktiriladi).
- README ingliz (`README.en.md`) va rus (`README.ru.md`) tillarida; har uch faylda til almashtirgich.
- "Claude for Open Source" bo'limi va dastur havolasi.
- Loyiha hujjatlari: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` va issue shablonlari.

### O'zgardi / Changed
- Windows dasturi endi repodagi zip o'rnida **Releases** sahifasidan (`AgentUmimiy-Setup.exe`) tarqatiladi.

### Tuzatildi / Fixed
- Windows'da yiqiladigan ikki test tuzatildi: shu sabab `v0.1.0` uchun o'rnatuvchi yig'ilmagan edi.

## [0.1.0] — 2026-10-24

Birinchi ochiq nashr. / First public release.

### Qo'shildi / Added
- **Ko'p modelli desktop ilova** (Tkinter + CLI): Anthropic (Claude), OpenAI va mos
  API'lar (OpenRouter, Groq, LM Studio), Google Gemini, Ollama, FreeLLMAPI.
- **Agentlarni avtomatik aniqlash**: Ollama, LM Studio, FreeLLMAPI, `claude`/`codex`/`gemini`/`aider` CLI.
- **Haqiqiy agent rejimi**: fayllarni o'qish/yozish/tahrirlash, qidiruv va buyruq ishga tushirish
  (ruxsat bilan, diff ko'rsatiladi).
- **Agentlar jamoasi**: `ask_agent` orqali agentlararo yordam; rejimlar — Avtomatik, Bitta,
  Hammasi, Ketma-ket, Kengash.
- **Brauzerni boshqarish** (CDP, Edge/Chrome, alohida profil).
- **Hujjatlar tahlili**: Excel (.xlsx), PowerPoint (.pptx), Word (.docx), CSV; `analyze_data`,
  `read_table`; katta fayllarni bo'laklab o'qish.
- **Fayl biriktirish**: rasm, PDF, Word, matn.
- **MCP plaginlari** va **Ko'nikmalar (Skills)** qo'llab-quvvatlanadi.
- **Telefondan boshqarish**: QR orqali ulanish, ruxsat so'rovlariga telefondan javob.
- **Suhbatlarni saqlash**, **Git yordamchisi**, qorong'i mavzu, to'liq o'zbekcha interfeys.
- **Windows build**: `AgentUmimiy-Windows.zip` va GitHub Actions orqali `AgentUmimiy-Setup.exe`.

[Nashr qilinmagan]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ravshan1989/Agent-umimiy/releases/tag/v0.1.0
