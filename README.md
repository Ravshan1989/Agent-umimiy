# Agent Umimiy

Barcha AI agentlarni (Claude, GPT, Gemini, Ollama va kompyuteringizdagi istalgan CLI agent) bitta **desktop oynada** birlashtiradi. Faqat Python standart kutubxonasi kerak.

## Ishga tushirish

```bash
cp agents.example.json agents.json     # keraklilarini qoldiring
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=... GEMINI_API_KEY=...
python -m agent_umimiy                 # desktop oyna (Tkinter)
python -m agent_umimiy --cli -m broadcast "salom"   # terminalda
```

Linux'da Tkinter bo'lmasa: `sudo apt install python3-tk`.

## Rejimlar

| Rejim | Ishlashi |
|---|---|
| `auto` | `routes` dagi kalit so'zlar bo'yicha eng mos agentni tanlaydi |
| `single` | bitta agent |
| `broadcast` | hamma agentga parallel yuboradi |
| `pipeline` | agentlar ketma-ket: har biri oldingisining javobini yaxshilaydi |
| `consensus` | hamma javob beradi, "hakam" (`judge`) agent yagona javob tuzadi |

## Agent turlari (`agents.json`)

`anthropic`, `openai` (OpenAI-mos API'lar uchun `base_url`), `gemini`, `ollama` (lokal), `cli` (`"command": "codex exec {prompt}"`), `echo` (demo).
Yangi agent qo'shish: `providers.py` da `Agent` ni meros qilib `_ask` ni yozing va `KINDS` ga qo'shing.

## Testlar

```bash
python -m unittest discover -s tests -t .
```
