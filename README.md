<div align="center">

# 🤖 Agent Umimiy

**Barcha AI agentlarni bitta desktop ilovada birlashtiruvchi o'zbekcha dastur**

Claude, ChatGPT, Gemini, Ollama va boshqa modellar bilan bitta oynada ishlang:
agentlar fayllaringizni o'qiydi, tahrirlaydi, brauzerni boshqaradi va bir-biriga yordam beradi.

![Platforma](https://img.shields.io/badge/platforma-Windows-0078D6?logo=windows&logoColor=white)
![Versiya](https://img.shields.io/badge/versiya-0.1.0-orange)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Til](https://img.shields.io/badge/interfeys-o'zbek%20tilida-1EB53A)

[📥 Yuklab olish](#-ornatish) · [✨ Imkoniyatlar](#-imkoniyatlar) · [⚙️ Sozlash](#️-sozlash) · [❓ Savollar](#-kop-beriladigan-savollar)

</div>

---

## 📌 Bu nima?

**Agent Umimiy** — bir nechta sun'iy intellekt agentlarini bitta joyga yig'adigan desktop ilova.
Har bir xizmat uchun alohida sayt yoki dastur ochish shart emas: hammasi bitta qulay, qorong'i
mavzudagi oynada, **to'liq o'zbek tilida**.

Ilova kompyuteringizdagi mavjud agentlarni **o'zi topadi** — hech narsa yozib o'tirishingiz kerak emas.

## ✨ Imkoniyatlar

| | Imkoniyat | Tavsif |
|---|---|---|
| 🧠 | **Ko'p modelli** | Anthropic (Claude), OpenAI va unga mos API'lar (OpenRouter, Groq, LM Studio), Google Gemini, Ollama, FreeLLMAPI |
| 🔍 | **Avtomatik aniqlash** | Kompyuterdagi Ollama, LM Studio, FreeLLMAPI va Claude CLI'ni o'zi topib, agent sifatida taklif qiladi |
| 🛠 | **Haqiqiy agent rejimi** | Agent loyiha papkasida fayllarni o'qiydi, yozadi, tahrirlaydi, qidiradi va buyruqlarni ishga tushiradi (ruxsatingiz bilan) |
| 🤝 | **Agentlar jamoasi** | Bir agent boshqasidan yordam so'rashi mumkin — masalan, Claude Gemini'dan maslahat oladi |
| 🌐 | **Brauzerni boshqarish** | Agent Edge/Chrome'ni ochadi, sahifani o'qiydi, tugma bosadi, matn yozadi. Qo'shimcha dastur kerak emas |
| 📎 | **Fayl biriktirish** | Rasm, PDF, Word va matn fayllarini suhbatga qo'shish |
| 📊 | **Hujjatlar tahlili** | Excel (xlsx), PowerPoint (pptx), Word (docx) va CSV jadvallarini o'qish va tahlil qilish |
| 🔌 | **MCP plaginlari** | GitHub, Notion, fayllar va boshqa tayyor MCP serverlarini agentlarga asbob sifatida ulash |
| 📚 | **Ko'nikmalar (Skills)** | `SKILL.md` ko'rsatmalari bilan agentga ish uslubini o'rgatish. `~/.claude/skills` papkasi ham avtomatik topiladi |
| 📱 | **Telefondan boshqarish** | QR-kodni skanerlang — chat telefon brauzerida ochiladi, ruxsat so'rovlari ham telefonga keladi |
| 💾 | **Suhbatlar saqlanadi** | Dasturni yopib ochganingizda suhbatlar joyida qoladi |
| 🌿 | **Git yordamchisi** | Loyihadagi Git holatini oddiy tilda ko'rsatadi |

## 📥 O'rnatish

> Hozircha faqat **Windows 10/11 (64-bit)** uchun.

1. Ushbu repodagi **[`AgentUmimiy-Windows.zip`](AgentUmimiy-Windows.zip)** faylini yuklab oling.
2. Zip faylni oching: o'ng tugma → **«Hammasini chiqarish»**.
3. **`AgentUmimiy.exe`** ni ikki marta bosing.
4. Windows ogohlantirsa: **«Qo'shimcha ma'lumot»** → **«Baribir ishga tushirish»**.

> [!NOTE]
> Windows ogohlantirishi dastur raqamli imzo bilan imzolanmaganligi uchun chiqadi — bu yangi va
> mustaqil dasturlar uchun odatiy holat.

## ⚙️ Sozlash

### Agent qo'shish

Ilova ishga tushganda mavjud agentlarni o'zi qidiradi. Bulut xizmatlari uchun API kalit kerak:

| Xizmat | Muhit o'zgaruvchisi | Standart model |
|---|---|---|
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Google Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| Ollama / LM Studio | kerak emas (lokal) | kompyuterdagi modellar |

### Telefondan boshqarish

1. Ilovada **«Telefondan boshqarish»** bo'limini oching va yoqing.
2. Telefon va kompyuter **bitta Wi-Fi tarmog'ida** bo'lsin.
3. Ekrandagi QR-kodni telefon kamerasi bilan skanerlang.

Kirish maxfiy kalit (token) bilan himoyalangan.

### Sozlamalar qayerda saqlanadi?

```
%APPDATA%\AgentUmimiy\agents.json
```

### Loyiha ko'rsatmalari

Loyiha papkasida `CLAUDE.md` yoki `AGENTS.md` fayli bo'lsa, agent uni har doim hisobga oladi.

## 🔒 Xavfsizlik

- Agent fayllarni faqat **siz tanlagan loyiha papkasida** o'zgartiradi.
- Buyruq ishga tushirish va fayl yozish **ruxsatingiz bilan** bajariladi.
- Brauzer alohida profilda ishlaydi — asosiy brauzeringiz ma'lumotlariga tegmaydi.
- API kalitlaringiz faqat sizning kompyuteringizda saqlanadi.

## ❓ Ko'p beriladigan savollar

<details>
<summary><b>Pullikmi?</b></summary>

Dasturning o'zi bepul. Bulut modellaridan (Claude, ChatGPT) foydalanish uchun ularning o'z API
kaliti kerak. Ollama yoki LM Studio orqali lokal modellarni esa butunlay bepul ishlatish mumkin.
</details>

<details>
<summary><b>Internet kerakmi?</b></summary>

Bulut modellari uchun — ha. Ollama/LM Studio bilan lokal modellar internetsiz ham ishlaydi.
</details>

<details>
<summary><b>Mac yoki Linux'da ishlaydimi?</b></summary>

Hozircha tayyor dastur faqat Windows uchun.
</details>

## 🗺 Reja

- [ ] Manba kodini ochiq qilish
- [ ] macOS va Linux versiyalari
- [ ] Ingliz va rus tillaridagi interfeys
- [ ] Avtomatik yangilanish

## 🤝 Hissa qo'shish

Taklif yoki xato topsangiz — [Issue](../../issues) oching. Har qanday fikr-mulohaza uchun rahmat!

---

<div align="center">

**Agent Umimiy** — o'zbek tilida AI bilan ishlashni osonlashtirish uchun yaratilgan ❤️

⭐ Loyiha yoqqan bo'lsa, yulduzcha bosishni unutmang!

</div>
