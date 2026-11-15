# O'zgarishlar tarixi / Changelog

Barcha muhim o'zgarishlar shu faylda qayd etiladi.
Format [Keep a Changelog](https://keepachangelog.com/) asosida, loyiha
[Semantik versiyalash](https://semver.org/lang/uz/) qoidasiga amal qiladi.

## [Nashr qilinmagan] / [Unreleased]

## [0.4.2] — 2026-11-14

### Xavfsizlik / Security
- Veb-sahifa yuklashda (web-fetch) SSRF tekshiruvi endi Python patch-versiyasiga bog'liq emas: maxsus
  tarmoqlar (192.0.0.0/24, 100.64.0.0/10, 198.18.0.0/15, IPv6 hujjatlashtirish/6to4/Teredo diapazonlari)
  va IPv4-mapped IPv6 manzillar har doim bloklanadi. Bu eski buildlardagi (masalan, Windows'dagi
  Python 3.11.9) bo'shliqni va Windows Python 3.11 CI xatosini tuzatadi.
  / The web-fetch SSRF check no longer depends on the Python patch version: special networks
  (192.0.0.0/24, 100.64.0.0/10, 198.18.0.0/15, documentation/6to4/Teredo IPv6 ranges) and IPv4-mapped
  IPv6 addresses are always blocked. This closes the gap on older builds such as Python 3.11.9 (Windows)
  and fixes the Windows Python 3.11 CI failure.

## [0.4.1] — 2026-11-14

### Xavfsizlik / Security
- `search_files` orqali loyiha papkasidan tashqariga chiqish imkoni yopildi (`../`, mutlaq yo'l,
  tashqariga olib chiquvchi symlink/junction rad etiladi).
- Veb-server foydalanuvchilari uchun xotira va ko'nikmalar (skills) o'chirildi.
- `X-Forwarded-For` sarlavhasidan eng o'ngdagi (proksi qo'shgan) qiymat olinadi.
- Veb-serverda sessiya 40 MB gacha bo'lgan so'rov tanasi o'qilishidan oldin tekshiriladi; kirish va
  ro'yxatdan o'tish so'rovlari 64 KB bilan cheklandi.

### Tuzatildi / Fixed
- Xato javobidan oldin o'qilmay qolgan tana tufayli ulanish yopilsa, javobda `Connection: close` yuboriladi.
- HTTP xatolari «HTTP <kod>:» bilan boshlanadi; 400/404/422 qaytaruvchi API'lar uchun asboblarsiz rejimga
  o'tish qayta tiklandi.
- Matndagi asbob chaqiruvlari: qiymatlar kesilmaydi, `<` yoki `&` bo'lsa ham o'qiladi.
- CLI agentlar bilan almashuv UTF-8 kodlashda.
- Xotira fayli o'qishda xato bo'lsa endi o'chib ketmaydi (`.bad` nusxasi saqlanadi); bo'sh bo'lmagan so'rovga
  mos topilmasa, tasodifiy yozuvlar qaytarilmaydi.
- Buzilgan `agents.json` dasturni yiqitmaydi (`.broken` nusxasi saqlanadi), BOM bilan saqlangan fayl o'qiladi.
- Suhbatlarni tiklashda buzilgan yozuvlar tashlab yuboriladi.
- Yorug' mavzuda jadvallar ko'rinmay qolishi tuzatildi.
- **Suhbat oynasi**: agent ishlayotganda yozish maydoni pastda qotib turadi; avtomatik aylantirish aqlli —
  foydalanuvchi yuqoriga aylantirgan bo'lsa, yangi javob uni pastga sudramaydi. Agent javoblari markdown
  bilan xavfsiz ko'rsatiladi (xom HTML bajarilmaydi). Enter tugmasi endi ishlayotgan agentni to'xtatmaydi.
  / Chat UI: the composer stays pinned at the bottom while the agent works; smart auto-scroll; agent
  replies are rendered as safe markdown (no raw HTML); Enter no longer stops a running agent.

## [0.4.0] - 2026-11-13

### Qo'shildi / Added
- **Yangi ish stoli oynasi**: dastur endi React interfeysini pywebview oynasida ochadi; kirish
  bir martalik kalit bilan avtomatik bo'ladi. Klassik Tk oynasi `--legacy-gui` bilan va
  Sozlamalardagi tugma bilan ochiladi.
- **Bosh sahifa paneli**: statistik kartalar, agentlar/fayllar/loyihalar ustunlari, tezkor amallar,
  rejalashtirilgan vazifalar va bildirishnomalar; pastda suhbat maydoni va mikrofon tugmasi.
- **Dastur ikonkasi**: `packaging/AgentUmimiy.ico` (AU belgisi) exe, o'rnatuvchi va oyna uchun.
- **Xotira asboblari**: agent muhim ma'lumotlarni eslab qoladi va keyin qidiradi (`memory_search`,
  `memory_remember`, `memory_forget`).
- **Avtomatik agent tanlash**: «auto» tanlansa, savolga mos agentni dastur o'zi tanlaydi.
- Asbob chaqiruvlarini qo'llamaydigan modellar uchun zaxira: javob matnidagi XML ko'rinishidagi asbob chaqiruvlari
  ham bajariladi.

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
- **Agentning yolg'on javoblari**: endi u qurollari borligini bilmay "menda bunday imkoniyat
  yo'q" demaydi, bajarmagan ishni "bajardim" deb aytmaydi va tekshirmasdan dasturni
  "o'rnatilgan" demaydi. Yangi `check_program` asbobi oq ro'yxatdagi dasturlarni
  (ffmpeg, node, git, ...) haqiqatan tekshiradi.
- **Buyruq vaqti tugashi**: odatiy chegara 300, eng ko'pi 900 soniya; to'xtatilganda
  olingan chiqish yo'qolmaydi va buyruq qisman bajarilgan bo'lishi mumkinligi aytiladi.
  Windows'da chegara endi haqiqatan ishlaydi: jarayon bolalari bilan birga o'ldiriladi
  (ilgari `shell=True` tufayli faqat cmd.exe o'lar, buyruq esa davom etardi).
- **Biriktirilgan fayllar**: suhbatga yuklangan fayl endi `files/<suhbat>/uploads/` ichida
  saqlanadi, interfeysda bosiladigan havola bo'lib chiqadi va yuklab olinadi; suhbat
  o'chirilganda u ham o'chadi. Ilgari fayl umumiy papkaga boshqa nom bilan tushib,
  qaytib olinmas edi.
- **CI yig'ish**: to'plam tekshiruvidagi `ls` quvuri `pipefail` bilan xato qaytarib,
  Windows yig'ilishini yiqitar edi; tekshiruv endi Windows bilan cheklangan.

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

[Nashr qilinmagan]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Ravshan1989/Agent-umimiy/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Ravshan1989/Agent-umimiy/releases/tag/v0.1.0
