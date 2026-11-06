"""Oddiy ichki tarjima (i18n) tizimi.

Dizayn: kalit sifatida **o'zbekcha** manba matnning o'zi ishlatiladi. `t("Saqlash")`
joriy tilga qarab tarjimani qaytaradi; til "uz" bo'lsa yoki tarjima topilmasa,
o'zbekcha matn o'zgarishsiz qaytadi. Shu sabab GUI'ni bosqichma-bosqich ko'chirish
mumkin — hali o'ralmagan matnlar shunchaki o'zbekcha ko'rinadi.

Simple built-in i18n. The key is the Uzbek source string itself, so untranslated
strings gracefully fall back to Uzbek.
"""
from __future__ import annotations

LANGS = ("uz", "ru", "en")
LANG_NAMES = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}

_lang = "uz"


def get_lang() -> str:
    return _lang


def set_lang(code: str | None) -> str:
    """Tilni o'rnatadi. Noto'g'ri qiymat e'tiborsiz qoldiriladi. Joriy tilni qaytaradi."""
    global _lang
    if code in LANGS:
        _lang = code
    return _lang


# TR[o'zbekcha manba] = {"ru": "...", "en": "..."}
TR: dict[str, dict[str, str]] = {
    # — Rejimlar —
    "Avtomatik": {"ru": "Автоматический", "en": "Automatic"},
    "Eng mos agentni o'zi tanlaydi": {"ru": "Сам выбирает подходящего агента", "en": "Picks the best-matching agent"},
    "Bitta agent": {"ru": "Один агент", "en": "Single agent"},
    "Tanlangan birinchi agent javob beradi": {"ru": "Отвечает первый выбранный агент", "en": "The first selected agent answers"},
    "Hammasi birga": {"ru": "Все вместе", "en": "All together"},
    "Barcha agentlar bir vaqtda javob beradi": {"ru": "Все агенты отвечают одновременно", "en": "All agents answer at once"},
    "Ketma-ket": {"ru": "По очереди", "en": "Sequential"},
    "Har bir agent oldingisining javobini yaxshilaydi": {"ru": "Каждый агент улучшает ответ предыдущего", "en": "Each agent improves the previous answer"},
    "Kengash": {"ru": "Совет", "en": "Council"},
    "Hammasi javob beradi, hakam yagona xulosa chiqaradi": {"ru": "Отвечают все, судья выдаёт единый вывод", "en": "Everyone answers, a judge gives one conclusion"},

    # — Oyna va dialog sarlavhalari —
    "Agent sozlamasi": {"ru": "Настройка агента", "en": "Agent settings"},
    "Sozlamalar": {"ru": "Настройки", "en": "Settings"},
    "Ruxsat kerak": {"ru": "Требуется разрешение", "en": "Permission required"},
    "Git — o'zgarishlar": {"ru": "Git — изменения", "en": "Git — changes"},
    "Telefondan boshqarish": {"ru": "Управление с телефона", "en": "Phone control"},
    "Plagin sozlamasi": {"ru": "Настройка плагина", "en": "Plugin settings"},
    "Plaginlar": {"ru": "Плагины", "en": "Plugins"},

    # — Umumiy tugmalar —
    "Saqlash": {"ru": "Сохранить", "en": "Save"},
    "Bekor qilish": {"ru": "Отмена", "en": "Cancel"},
    "Bekor": {"ru": "Отмена", "en": "Cancel"},
    "Yuborish": {"ru": "Отправить", "en": "Send"},
    "Qo'shish": {"ru": "Добавить", "en": "Add"},
    "O'chirish": {"ru": "Удалить", "en": "Delete"},
    "Yopish": {"ru": "Закрыть", "en": "Close"},
    "Sinab ko'rish": {"ru": "Проверить", "en": "Test"},
    "Ro'yxat": {"ru": "Список", "en": "List"},
    "Tahrirlash": {"ru": "Редактировать", "en": "Edit"},
    "Ha": {"ru": "Да", "en": "Yes"},
    "Yo'q": {"ru": "Нет", "en": "No"},
    "Ortga": {"ru": "Назад", "en": "Back"},

    # — Agent turlari (TYPE_LABELS / SHORT_TYPE) —
    "FreeLLMAPI — lokal shlyuz (localhost:3001)": {"ru": "FreeLLMAPI — локальный шлюз (localhost:3001)", "en": "FreeLLMAPI — local gateway (localhost:3001)"},
    "Claude (API kalit kerak)": {"ru": "Claude (нужен API-ключ)", "en": "Claude (API key required)"},
    "ChatGPT / OpenAI-mos (API kalit)": {"ru": "ChatGPT / OpenAI-совместимый (API-ключ)", "en": "ChatGPT / OpenAI-compatible (API key)"},
    "Google Gemini (API kalit)": {"ru": "Google Gemini (API-ключ)", "en": "Google Gemini (API key)"},
    "Lokal model — Ollama": {"ru": "Локальная модель — Ollama", "en": "Local model — Ollama"},
    "Kompyuterdagi dastur (CLI)": {"ru": "Программа на компьютере (CLI)", "en": "Program on the computer (CLI)"},
    "OpenAI-mos": {"ru": "OpenAI-совм.", "en": "OpenAI-compat."},
    "Lokal · Ollama": {"ru": "Локально · Ollama", "en": "Local · Ollama"},
    "Dastur (CLI)": {"ru": "Программа (CLI)", "en": "Program (CLI)"},
    "Demo": {"ru": "Демо", "en": "Demo"},

    # — Chat takliflari (SUGGESTIONS) —
    "Bu kodni tushuntirib ber": {"ru": "Объясни этот код", "en": "Explain this code"},
    "Menga qisqa xat yozib ber": {"ru": "Напиши мне короткое письмо", "en": "Write me a short letter"},
    "Ingliz tiliga tarjima qil": {"ru": "Переведи на английский", "en": "Translate to English"},
    "Internetdan bugungi yangiliklarni top": {"ru": "Найди сегодняшние новости в интернете", "en": "Find today's news on the internet"},

    # — Loyiha takliflari (PROJECT_SUGGESTIONS) —
    "Bu loyiha nima haqida? Qisqa tushuntirib ber": {"ru": "О чём этот проект? Объясни кратко", "en": "What is this project about? Explain briefly"},
    "Kodda xatolarni top va tuzat": {"ru": "Найди и исправь ошибки в коде", "en": "Find and fix bugs in the code"},
    "README.md faylini yoz yoki yangila": {"ru": "Напиши или обнови файл README.md", "en": "Write or update the README.md file"},
    "Testlarni ishga tushir, xato bo'lsa tuzat": {"ru": "Запусти тесты и исправь ошибки", "en": "Run the tests and fix failures"},

    # — Til tanlovi —
    "Til": {"ru": "Язык", "en": "Language"},
    "Interfeys tili": {"ru": "Язык интерфейса", "en": "Interface language"},

    # — Asosiy oyna —
    "Yangi suhbat": {"ru": "Новый чат", "en": "New chat"},
    "Barcha AI bir joyda": {"ru": "Весь ваш AI в одном месте", "en": "All your AI in one place"},
    "REJIM": {"ru": "РЕЖИМ", "en": "MODE"},
    "AGENTLAR": {"ru": "АГЕНТЫ", "en": "AGENTS"},
    "＋  Yangi suhbat": {"ru": "＋  Новый чат", "en": "＋  New chat"},
    "⬡   Plaginlar": {"ru": "⬡   Плагины", "en": "⬡   Plugins"},
    "⚙   Sozlamalar": {"ru": "⚙   Настройки", "en": "⚙   Settings"},
    "Xabar yozing…   (Enter — yuborish, Shift+Enter — yangi qator)":
        {"ru": "Напишите сообщение…   (Enter — отправить, Shift+Enter — новая строка)",
         "en": "Type a message…   (Enter — send, Shift+Enter — new line)"},
    "agent faol": {"ru": "агент(ов) активно", "en": "agent(s) active"},
    "Loyiha:": {"ru": "Проект:", "en": "Project:"},
    "Loyiha papkasini tanlash": {"ru": "Выбрать папку проекта", "en": "Choose project folder"},
    "Avval «Loyiha papkasini tanlash» tugmasi bilan papkani tanlang.":
        {"ru": "Сначала выберите папку кнопкой «Выбрать папку проекта».",
         "en": "First choose a folder with the “Choose project folder” button."},
    "Qanday yordam bera olaman?": {"ru": "Чем могу помочь?", "en": "How can I help?"},
    "Agent sozlanmagan — chap pastdagi «Sozlamalar» orqali qo'shing.":
        {"ru": "Агент не настроен — добавьте через «Настройки» внизу слева.",
         "en": "No agent configured — add one via “Settings” at the bottom left."},
    "Agentlar fayllarni o'qiydi va ruxsatingiz bilan o'zgartiradi.":
        {"ru": "Агенты читают файлы и изменяют их с вашего разрешения.",
         "en": "Agents read files and change them with your permission."},
    "Savolingizni yozing — agentlaringiz birgalikda javob beradi.":
        {"ru": "Напишите вопрос — ваши агенты ответят вместе.",
         "en": "Type your question — your agents answer together."},
    "loyihada faqat o'qiydi": {"ru": "в проекте только чтение", "en": "read-only in the project"},
    "Tilni o'zgartirish dasturni qayta ishga tushirgandan so'ng to'liq qo'llanadi.":
        {"ru": "Смена языка полностью применится после перезапуска приложения.",
         "en": "The language change fully applies after restarting the app."},
}


def t(s: str) -> str:
    """Matnni joriy tilga tarjima qiladi; topilmasa o'zbekcha manba qaytadi."""
    if _lang == "uz" or not s:
        return s
    entry = TR.get(s)
    if not entry:
        return s
    return entry.get(_lang, s)
