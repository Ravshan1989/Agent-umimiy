# Agent Umimiy

Barcha AI agentlarni (Claude, ChatGPT, Gemini, lokal modellar — Ollama/LM Studio, va kompyuterdagi CLI agentlar) **bitta chat oynasida** birlashtiradi.

## Oddiy foydalanuvchi uchun (Windows)

1. `AgentUmimiy-Setup.exe` ni yuklab oling (Releases yoki Actions → Artifacts).
2. O'rnating (Keyingi → Keyingi) va ishga tushiring.
3. Birinchi ishga tushishda dastur kompyuterdagi agentlarni o'zi topadi. Qolganini **⚙ Sozlamalar → ➕ Qo'shish** orqali qo'shing: turini tanlang, API kalitni qo'ying, **Sinab ko'rish** ni bosing.
4. Chatga yozing. Yuqoridan rejimni tanlang.

Sozlamalar `%APPDATA%\AgentUmimiy\agents.json` da saqlanadi (faqat sizning kompyuteringizda).

## Loyiha bilan ishlash (dasturlash yordamchisi)

Yuqoridagi **«Loyiha papkasini tanlash»** tugmasi bilan o'z loyihangiz papkasini tanlang. Shundan so'ng agentlar (Claude, ChatGPT-mos, Ollama) o'zlari:

- papka va fayllarni **o'qiydi**, kod ichidan **qidiradi** (so'rashsiz);
- fayl **yaratadi / tahrirlaydi** va **buyruq ishga tushiradi** (testlar, o'rnatish...) — **har safar ruxsat so'raydi**, o'zgarish (diff) ko'rsatiladi;
- «Shu suhbatda doim ruxsat» tugmasi ruxsat so'rashni o'chiradi; **■** tugmasi ishni to'xtatadi.

Xavfsizlik: agent faqat tanlangan papka ichida ishlaydi (tashqariga chiqolmaydi, `.git` ga tegmaydi). «Hammasi birga» va «Kengash» rejimlarida bir nechta agent bir vaqtda ishlagani uchun ular **faqat o'qiydi**.
`claude`, `codex` kabi CLI agentlar tanlangan papkada ishga tushadi.

**Git** tugmasi: nima o'zgargani (oddiy tilda), o'zgarishlarni ko'rish, **Saqlash (commit)**, **Yuborish (push)**, **Olish (pull)**. Git kompyuteringizda o'rnatilgan bo'lishi kerak (git-scm.com); parollar sizning Git sozlamangizdan olinadi.

## Fayllarni o'qish va tahlil qilish

| Fayl | Nima o'qiladi |
|---|---|
| **Excel (.xlsx)** | barcha varaqlar, sanalar (2024-03-15), sonlar, mantiqiy qiymatlar; formulalarning hisoblangan natijasi |
| **PowerPoint (.pptx)** | slayd sarlavhalari, matn, jadvallar, spiker izohlari |
| **Word (.docx)** | sarlavhalar (#), ro'yxatlar (•), jadvallar |
| **CSV/TSV** | `,` `;` Tab ajratgichlari va UTF-8/Windows-1251 kodirovkalari avtomatik aniqlanadi |
| **PDF** | matni; skaner PDF uchun sahifani rasm qilib yuboring (Claude/GPT-4/Gemini o'zi o'qiydi) |
| **Rasm** | ko'ra oladigan modellar |

Loyiha papkasidagi katta jadvallar uchun agent maxsus asboblardan foydalanadi: **`analyze_data`** (ustunlar, turlari, bo'sh joylar, min/maks/o'rtacha/median/jami, eng ko'p uchraydigan qiymatlar) va **`read_table`** (qatorlarni raqamlari bilan o'qish yoki matn bo'yicha topish). Katta matn fayllari (3 MB+) bo'laklab o'qiladi. Biriktirilgan juda katta jadval o'rniga tahlil va birinchi qatorlar beriladi.
**Cheklovlar:** eski `.xls/.doc/.ppt` formatlari qo'llanmaydi (yangi formatda saqlab yuboring); rasm ichidagi matnni o'qish (OCR) modelga bog'liq; tahlil sifati tanlangan model kuchiga bog'liq.

## Rasm, PDF va fayllar

Yozish maydonidagi **＋** tugmasi bilan **rasm** (PNG, JPG, GIF, WebP), **PDF**, **Word (.docx)** yoki **matn fayl** biriktiring — agent ularni ko'rib javob beradi. Rasmlarni Claude, ChatGPT-mos modellar, Gemini va ko'rish qobiliyatli Ollama modellari ko'ra oladi. PDF matni boshqa modellarga ham yuboriladi. Cheklov: rasm ≤ 5 MB, PDF ≤ 20 MB.

## Internet

Agentlar **internetdan qidirishi** (DuckDuckGo) va **sahifalarni o'qishi** mumkin, kerak bo'lsa sahifani **sizning brauzeringizda ochish**ni (ruxsat bilan) taklif qiladi. Sozlamalarda o'chirib qo'yish mumkin. Xavfsizlik: kompyuter va ichki tarmoq manzillariga (localhost, 192.168.x.x va h.k.) kirish taqiqlangan; sahifadagi matn «buyruq» emas, faqat ma'lumot sifatida qaraladi.
Eslatma: bu brauzerni *boshqarish* (tugma bosish, forma to'ldirish) emas — faqat qidirish va o'qish.

## Suhbatlarni saqlash, ko'rsatmalar, reja

- **Saqlash:** suhbatlar (tablar, tarix, loyiha) `%APPDATA%\AgentUmimiy\chats.json` da saqlanadi va dastur qayta ochilganda tiklanadi (oxirgi 15 ta suhbat). Sozlamalarda o'chirib qo'yish yoki tarixni tozalash mumkin. Fayl shifrlanmagan: maxfiy ma'lumot yozmang yoki saqlashni o'chiring.
- **Loyiha ko'rsatmalari:** loyiha papkasida `CLAUDE.md`, `AGENTS.md` yoki `AGENT.md` bo'lsa, agent uni avtomatik o'qiydi va qoidalarga amal qiladi.
- **Reja kartasi:** ko'p bosqichli ishda agent «Reja» ro'yxatini ko'rsatadi va bosqichlarni belgilab boradi.
- **Markdown:** javoblarda sarlavha, ro'yxat, jadval, `kod`, havola va kod bloklari chiroyli ko'rinadi.

## Telefondan boshqarish

**Sozlamalar → «Telefondan boshqarish» → Yoqish.** Dastur QR-kod ko'rsatadi: telefon kamerasi bilan skanerlang (telefon va kompyuter bir Wi-Fi'da bo'lsin) va chat telefon brauzerida ochiladi. U yerdan yozasiz, fayl/rasm yuborasiz, ishni to'xtatasiz, suhbatlar orasida o'tasiz va **ruxsat so'rovlariga («Fayl o'zgartiriladi», «Buyruq ishga tushadi»...) telefondan javob berasiz**: kompyuterdagi oyna o'zi yopiladi.
- Kompyuter yoqilgan va dastur ochiq bo'lishi kerak. Sozlamalar, agent va plagin qo'shish faqat kompyuterda.
- Kirish uzun maxfiy kalit (QR-dagi `t=...`) bilan: noto'g'ri urinishlar bloklanadi. **Kalit parol kabi**: kimgadir ko'rinib qolsa, «Yangi kalit» ni bosing.
- Ulanish **shifrlanmagan (HTTP)**: faqat ishonchli uy Wi-Fi'ida ishlating (kafe/ommaviy tarmoqda emas). Uydan tashqarida ishlatish uchun Tailscale kabi shifrlangan tunnel o'rnating.
- Windows xavfsizlik devori birinchi marta so'rasa, «Shaxsiy tarmoqlar» uchun ruxsat bering. Sukut bo'yicha o'chiq.

## Plaginlar (MCP) va ko'nikmalar (skills)

**Plaginlar.** Chap paneldagi **Plaginlar** tugmasi: «Qo'shish» → tayyor shablonni tanlang (Fayllar, Xotira, Hujjatlar/Context7, Notion, Playwright, GitHub...) yoki istalgan MCP serverni o'zingiz kiriting (buyruq yoki URL, kerak bo'lsa kalit). Dastur serverni ishga tushiradi va uning asboblarini barcha agentlarga beradi.
- **O'qiydigan** asboblar ruxsatsiz ishlaydi, **o'zgartiradigan**lari har safar ruxsat so'raydi («Bu plaginga doim ruxsat» tugmasi bor). «Hammasi birga» va «Kengash» rejimlarida faqat o'qiydiganlari ishlaydi.
- `npx ...` bilan boshlanadigan plaginlar uchun kompyuterda **Node.js** (nodejs.org) kerak; birinchi ishga tushishda paket yuklanadi (1-2 daqiqa).
- Kalitlar (`NOTION_TOKEN`, GitHub tokeni...) faqat shu kompyuterdagi sozlama faylida saqlanadi.
- **Cheklov:** claude.ai'dagi tayyor ulanishlar (Gmail, Google Drive, Calendar...) sizning claude.ai hisobingizga bog'liq, ularni bu dasturga ko'chirib bo'lmaydi. Ularning o'rniga shu xizmatlarning o'z MCP serverlarini (o'z kalitingiz bilan) ulaysiz. OAuth (brauzerda «Kirish» tugmasi) talab qiladigan masofaviy serverlar hozircha qo'llanmaydi.

**Ko'nikmalar.** `SKILL.md` fayli bor papka (Claude formatida: `name`, `description`, matn). Quyidagi joylardan avtomatik topiladi: `%APPDATA%\AgentUmimiy\skills\<nom>\SKILL.md`, `~/.claude/skills`, Claude plaginlaridagi ko'nikmalar va loyihadagi `.claude/skills`. Agent tavsifga qarab kerakli ko'nikmani o'zi yuklaydi va unga amal qiladi.

## Agent brauzerda ishlaydi

Agent **haqiqiy brauzer oynasida** sayt ochadi, o'qiydi, tugmalarni bosadi va formalarni to'ldiradi (siz oynada nima bo'layotganini ko'rib turasiz). Windows'da **Edge** (yoki Chrome) ishlatiladi, hech narsa o'rnatish shart emas.
- Brauzer **alohida profilda** ochiladi (`%APPDATA%\AgentUmimiy\browser-profile`): asosiy brauzeringizdagi parollar va sessiyalarga tegmaydi. Biror saytga bir marta o'zingiz kirsangiz, keyingi safar ham kirgan holda qoladi.
- **Har bir yangi sayt** va **har bir yozish** ruxsat so'raydi. **Parol maydoniga yozmaydi**: parolni o'zingiz oynada kiriting.
- «Hammasi birga» va «Kengash» rejimlarida brauzer o'chiq. Sozlamalarda umuman o'chirib qo'yish mumkin.
- Sahifa matni agent uchun faqat ma'lumot: u yerdagi «buyruqlarga» amal qilinmaydi.

## Agentlar bir-birini biladi

Har bir agent ilovadagi **barcha agentlar ro'yxatini** biladi («qaysi agentlar bor?» deb so'rasangiz hammasini sanab beradi) va kerak bo'lsa boshqa agentdan yordam so'raydi (`ask_agent`): masalan «gemini dan so'rab ko'r». Yordamga chaqirilgan agent faqat o'qiy oladi va o'zi boshqasini chaqira olmaydi. Chatda `⇄` qatori kimdan kimga so'ralganini ko'rsatadi.

## Bir nechta suhbat

Tepada brauzerdagi kabi **tablar**: har bir suhbatning o'z tarixi va o'z loyiha papkasi bor, bir vaqtda ishlayveradi (fon suhbat tugasa tabda yashil nuqta chiqadi). `＋` — yangi suhbat, `×` — yopish.
Suhbatlar dastur yopilganda saqlanmaydi.

## Rejimlar

| Rejim | Ishlashi |
|---|---|
| Avtomatik | `routes` dagi kalit so'zlar bo'yicha agentni tanlaydi |
| Bitta agent | birinchi tanlangan agent |
| Hammasi bir vaqtda | barcha agentlar parallel javob beradi |
| Ketma-ket | har bir agent oldingisining javobini yaxshilaydi |
| Kengash | hammasi javob beradi, hakam agent yagona xulosa chiqaradi |

## FreeLLMAPI (lokal shlyuz) ulash

Kompyuteringizda FreeLLMAPI (`localhost:3001`) ishlab tursa:
1. **Sozlamalar → ＋ Qo'shish → Turi: «FreeLLMAPI — lokal shlyuz»** (manzil o'zi to'ldiriladi). Yoki «Avto-topish» uni o'zi topadi.
2. FreeLLMAPI sahifasidagi (**Agentlar** bo'limi) **API KEY** ni «API kalit» maydoniga qo'ying.
3. **Ro'yxat** tugmasi shlyuzdagi modellarni oladi — birini tanlang, **Sinab ko'rish** → **Saqlash**.

Kalit faqat sizning kompyuteringizdagi sozlama faylida saqlanadi. Model fayl asboblarini (tools) qo'llamasa, dastur oddiy chatga o'tadi.

## Lokal agentlar

- **Ollama** (`localhost:11434`) va **LM Studio** (`localhost:1234`) ishlab turgan bo'lsa, «Avto-topish» ularning modellarini qo'shadi.
- `claude`, `codex`, `gemini`, `aider` dasturlari o'rnatilgan bo'lsa, ular ham avtomatik topiladi.
- Boshqa istalgan dastur: tur «Kompyuterdagi dastur», buyruq `mening-agent {prompt}`.

## .exe ni yig'ish

- **GitHub Actions:** Actions → "Windows .exe" → Run workflow. Natija: `AgentUmimiy-Setup.exe`.
- **Qo'lda (Windows):** `packaging\build_windows.bat` (Python va ixtiyoriy ravishda Inno Setup kerak).

## Dasturchilar uchun

```bash
python app.py                          # oyna
python app.py --cli -m broadcast "salom"   # terminal
python -m unittest discover -s tests -t .
```
Asboblar: `tools.py`, agent sikli: `agentic.py`, git: `gitutil.py`. Gemini hozircha asbobsiz (oddiy chat).
Yangi agent turi: `providers.py` da `Agent` ni meros qilib, `KINDS` ga qo'shing.
