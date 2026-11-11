# O'zgarishlar tarixi / Changelog

Barcha muhim o'zgarishlar shu faylda qayd etiladi.
Format [Keep a Changelog](https://keepachangelog.com/) asosida, loyiha
[Semantik versiyalash](https://semver.org/lang/uz/) qoidasiga amal qiladi.

## [Nashr qilinmagan] / [Unreleased]

### Qo'shildi / Added
- **Telefonda ilova kabi (PWA)**: veb-server sahifasini iPhone va Android'da bosh ekranga qo'shish mumkin
  (belgi, to'liq ekran). HTTPS proksi ortida ishlash: `X-Forwarded-*` sarlavhalari, `Secure` cookie.
- **Veb-server dastur bilan birga**: Sozlamalar → «Veb-server» da yoqiladi (manzillar, taklif kodi, yangi kod);
  yoqilgach dastur har ochilganda o'zi ishga tushadi.
- Oyna uchun haqiqiy Tk bilan tutun sinovlari (CI'da virtual ekran ostida).
- **Linux paketi**: `AgentUmimiy-Linux-x86_64.tar.gz` har nashrda Windows o'rnatuvchisi bilan birga yig'iladi.
- Yig'ilgan dastur har build'da veb-server rejimida ishga tushirib sinaladi.

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
