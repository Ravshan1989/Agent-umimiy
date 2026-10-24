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

## Rejimlar

| Rejim | Ishlashi |
|---|---|
| Avtomatik | `routes` dagi kalit so'zlar bo'yicha agentni tanlaydi |
| Bitta agent | birinchi tanlangan agent |
| Hammasi bir vaqtda | barcha agentlar parallel javob beradi |
| Ketma-ket | har bir agent oldingisining javobini yaxshilaydi |
| Kengash | hammasi javob beradi, hakam agent yagona xulosa chiqaradi |

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
