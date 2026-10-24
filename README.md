# Agent Umimiy

Barcha AI agentlarni (Claude, ChatGPT, Gemini, lokal modellar — Ollama/LM Studio, va kompyuterdagi CLI agentlar) **bitta chat oynasida** birlashtiradi.

## Oddiy foydalanuvchi uchun (Windows)

1. `AgentUmimiy-Setup.exe` ni yuklab oling (Releases yoki Actions → Artifacts).
2. O'rnating (Keyingi → Keyingi) va ishga tushiring.
3. Birinchi ishga tushishda dastur kompyuterdagi agentlarni o'zi topadi. Qolganini **⚙ Sozlamalar → ➕ Qo'shish** orqali qo'shing: turini tanlang, API kalitni qo'ying, **Sinab ko'rish** ni bosing.
4. Chatga yozing. Yuqoridan rejimni tanlang.

Sozlamalar `%APPDATA%\AgentUmimiy\agents.json` da saqlanadi (faqat sizning kompyuteringizda).

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
Yangi agent turi: `providers.py` da `Agent` ni meros qilib, `KINDS` ga qo'shing.
