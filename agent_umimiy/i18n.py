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

    # — Sozlamalar oynasi —
    "Agentlaringiz": {"ru": "Ваши агенты", "en": "Your agents"},
    "Qo'shing, tahrirlang yoki vaqtincha o'chirib qo'ying":
        {"ru": "Добавляйте, редактируйте или временно отключайте",
         "en": "Add, edit or temporarily disable them"},
    "Agent": {"ru": "Агент", "en": "Agent"},
    "Model / buyruq": {"ru": "Модель / команда", "en": "Model / command"},
    "Yoqilgan": {"ru": "Включён", "en": "Enabled"},
    "+ Qo'shish": {"ru": "+ Добавить", "en": "+ Add"},
    "Yoq / o'chir": {"ru": "Вкл / выкл", "en": "On / off"},
    "Avto-topish": {"ru": "Автопоиск", "en": "Auto-detect"},
    "Qayta ulash": {"ru": "Переподключить", "en": "Reconnect"},
    "Kengashda hakam:": {"ru": "Судья совета:", "en": "Council judge:"},
    "Suhbatlarni shu kompyuterda saqlash (dastur qayta ochilganda tiklanadi)":
        {"ru": "Сохранять чаты на этом компьютере (восстановятся при перезапуске)",
         "en": "Save chats on this computer (restored when the app reopens)"},
    "Suhbatlar tarixini o'chirish": {"ru": "Очистить историю чатов", "en": "Clear chat history"},
    "Agentlar brauzerni boshqara olsin (sayt ochish, bosish, yozish — har safar ruxsat so'raydi)":
        {"ru": "Разрешить агентам управлять браузером (открытие сайтов, клики, ввод — каждый раз спрашивает)",
         "en": "Let agents control the browser (open sites, click, type — asks each time)"},
    "Telefondan boshqarish (mobil kirish)…":
        {"ru": "Управление с телефона (мобильный доступ)…", "en": "Phone control (mobile access)…"},
    "Agentlar internetdan qidira va sahifalarni o'qiy olsin":
        {"ru": "Разрешить агентам искать в интернете и читать страницы",
         "en": "Let agents search the internet and read pages"},
    "Saqlash va yopish": {"ru": "Сохранить и закрыть", "en": "Save and close"},
    "Tarixni o'chirish": {"ru": "Очистить историю", "en": "Clear history"},
    "Barcha saqlangan suhbatlar o'chirilsinmi?":
        {"ru": "Удалить все сохранённые чаты?", "en": "Delete all saved chats?"},
    "ha": {"ru": "да", "en": "yes"},
    "yo'q": {"ru": "нет", "en": "no"},
    "Bu agent o'chirilsinmi?": {"ru": "Удалить этого агента?", "en": "Delete this agent?"},
    "ta yangi agent topildi.": {"ru": "новых агент(ов) найдено.", "en": "new agent(s) found."},
    "Yangi agent topilmadi. Ollama/LM Studio ishga tushirilganini tekshiring.":
        {"ru": "Новые агенты не найдены. Проверьте, запущены ли Ollama/LM Studio.",
         "en": "No new agents found. Check that Ollama/LM Studio is running."},
    "loyihada faqat o'qiydi": {"ru": "в проекте только чтение", "en": "read-only in the project"},
    "Tilni o'zgartirish dasturni qayta ishga tushirgandan so'ng to'liq qo'llanadi.":
        {"ru": "Смена языка полностью применится после перезапуска приложения.",
         "en": "The language change fully applies after restarting the app."},

    # — Agent qo'shish oynasi —
    "Nomi": {"ru": "Имя", "en": "Name"},
    "Turi": {"ru": "Тип", "en": "Type"},
    "Model": {"ru": "Модель", "en": "Model"},
    "API kalit": {"ru": "API-ключ", "en": "API key"},
    "Manzil (ixtiyoriy)": {"ru": "Адрес (необязательно)", "en": "URL (optional)"},
    "Buyruq (CLI uchun)": {"ru": "Команда (для CLI)", "en": "Command (for CLI)"},
    "Diqqat": {"ru": "Внимание", "en": "Attention"},
    "Nomini yozing": {"ru": "Введите имя", "en": "Enter a name"},
    "Buyruqni yozing": {"ru": "Введите команду", "en": "Enter a command"},
    "Avval «Ro'yxat» tugmasi bilan modelni tanlang.":
        {"ru": "Сначала выберите модель кнопкой «Список».",
         "en": "First pick a model with the “List” button."},
    "Modellar ro'yxati": {"ru": "Список моделей", "en": "Model list"},
    "Ro'yxat OpenAI-mos shlyuzlar (FreeLLMAPI, LM Studio, OpenRouter...) uchun ishlaydi. Boshqalarda model nomini o'zingiz yozing.":
        {"ru": "Список работает для OpenAI-совместимых шлюзов (FreeLLMAPI, LM Studio, OpenRouter...). Для остальных впишите имя модели вручную.",
         "en": "The list works for OpenAI-compatible gateways (FreeLLMAPI, LM Studio, OpenRouter...). For others, type the model name yourself."},
    "Ro'yxat olinmadi": {"ru": "Не удалось получить список", "en": "Could not fetch the list"},
    "Shlyuz ishlayotganini va API kalit to'g'riligini tekshiring.":
        {"ru": "Проверьте, работает ли шлюз и верен ли API-ключ.",
         "en": "Check that the gateway is running and the API key is correct."},
    "ta model topildi. Ro'yxatdan tanlang.":
        {"ru": "модель(ей) найдено. Выберите из списка.", "en": "model(s) found. Pick one from the list."},
    "Ishlayapti ✓": {"ru": "Работает ✓", "en": "Working ✓"},
    "Xato": {"ru": "Ошибка", "en": "Error"},
    "Brauzerda localhost:3001 → «Agentlar» bo'limidagi API KEY ni «API kalit» maydoniga qo'ying, so'ng «Ro'yxat» tugmasi bilan modelni tanlang.":
        {"ru": "В браузере localhost:3001 → скопируйте API KEY из раздела «Агенты» в поле «API-ключ», затем выберите модель кнопкой «Список».",
         "en": "In the browser open localhost:3001 → copy the API KEY from the “Agents” section into the “API key” field, then pick a model with the “List” button."},
    "Kalitni console.anthropic.com dan oling. Model bo'sh qolsa, standarti ishlatiladi.":
        {"ru": "Получите ключ на console.anthropic.com. Если поле модели пустое, используется модель по умолчанию.",
         "en": "Get the key from console.anthropic.com. If the model is left empty, the default is used."},
    "OpenAI, OpenRouter, Groq yoki LM Studio. Lokal bo'lsa manzilni yozing: http://localhost:1234/v1":
        {"ru": "OpenAI, OpenRouter, Groq или LM Studio. Для локального укажите адрес: http://localhost:1234/v1",
         "en": "OpenAI, OpenRouter, Groq or LM Studio. For a local one, enter the URL: http://localhost:1234/v1"},
    "Kalitni aistudio.google.com dan oling.":
        {"ru": "Получите ключ на aistudio.google.com.", "en": "Get the key from aistudio.google.com."},
    "Avval ollama.com dan o'rnating va modelni yuklab oling. Kalit shart emas.":
        {"ru": "Сначала установите с ollama.com и загрузите модель. Ключ не нужен.",
         "en": "First install from ollama.com and pull a model. No key needed."},
    "Masalan: codex exec {prompt}  yoki  claude -p {prompt}":
        {"ru": "Например: codex exec {prompt}  или  claude -p {prompt}",
         "en": "For example: codex exec {prompt}  or  claude -p {prompt}"},

    # — Ruxsat so'rovi oynasi —
    "ruxsat so'ramoqda": {"ru": "запрашивает разрешение", "en": "is requesting permission"},
    "Shu suhbatda doim ruxsat": {"ru": "Всегда разрешать в этом чате", "en": "Always allow in this chat"},
    "Brauzerda doim ruxsat": {"ru": "Всегда разрешать в браузере", "en": "Always allow in the browser"},
    "Bu plaginga doim ruxsat": {"ru": "Всегда разрешать этот плагин", "en": "Always allow this plugin"},
    "Buyruqlarga doim ruxsat": {"ru": "Всегда разрешать команды", "en": "Always allow commands"},
    "Rad etish": {"ru": "Отклонить", "en": "Deny"},
    "Ruxsat berish": {"ru": "Разрешить", "en": "Allow"},

    # — Git oynasi —
    "Holati": {"ru": "Статус", "en": "Status"},
    "Fayl": {"ru": "Файл", "en": "File"},
    "Saqlash izohi:": {"ru": "Комментарий коммита:", "en": "Commit message:"},
    "Git o'rnatilmagan": {"ru": "Git не установлен", "en": "Git is not installed"},
    "git-scm.com saytidan Git ni o'rnating, so'ng bu oynani qayta oching.":
        {"ru": "Установите Git с git-scm.com, затем снова откройте это окно.",
         "en": "Install Git from git-scm.com, then reopen this window."},
    "Bu papka hali Git omboriga aylanmagan":
        {"ru": "Эта папка ещё не является репозиторием Git", "en": "This folder is not a Git repository yet"},
    "Git o'zgarishlaringiz tarixini saqlaydi. Boshlash uchun tugmani bosing.":
        {"ru": "Git хранит историю ваших изменений. Нажмите кнопку, чтобы начать.",
         "en": "Git keeps a history of your changes. Press the button to start."},
    "Git omborini yaratish": {"ru": "Создать репозиторий Git", "en": "Create Git repository"},
    "Shox:": {"ru": "Ветка:", "en": "Branch:"},
    "ta fayl o'zgargan": {"ru": "файл(ов) изменено", "en": "file(s) changed"},
    "Hammasi saqlangan — o'zgarish yo'q": {"ru": "Всё сохранено — изменений нет", "en": "All saved — no changes"},
    "Yangi fayllar «Saqlash» bosilganda qo'shiladi.":
        {"ru": "Новые файлы добавятся при нажатии «Сохранить».", "en": "New files are added when you press “Save”."},
    "Saqlash (commit)": {"ru": "Сохранить (commit)", "en": "Save (commit)"},
    "Yuborish (push)": {"ru": "Отправить (push)", "en": "Push"},
    "Olish (pull)": {"ru": "Получить (pull)", "en": "Pull"},
    "Yangilash": {"ru": "Обновить", "en": "Refresh"},
    "Saqlash izohini yozing (nima o'zgardi?)":
        {"ru": "Напишите комментарий коммита (что изменилось?)", "en": "Write a commit message (what changed?)"},
    "✓ Saqlandi": {"ru": "✓ Сохранено", "en": "✓ Saved"},
    "Xato:": {"ru": "Ошибка:", "en": "Error:"},
    "✓ Bajarildi": {"ru": "✓ Готово", "en": "✓ Done"},

    # — Telefondan boshqarish oynasi —
    "Telefon va kompyuter bir Wi-Fi tarmog'ida bo'lsin. QR-kodni telefon kamerasi bilan skanerlang: chat telefon brauzerida ochiladi, ruxsat so'rovlari ham telefonda chiqadi.":
        {"ru": "Телефон и компьютер должны быть в одной сети Wi-Fi. Отсканируйте QR-код камерой телефона: чат откроется в браузере телефона, запросы разрешений тоже появятся на телефоне.",
         "en": "Keep the phone and computer on the same Wi-Fi. Scan the QR code with the phone camera: the chat opens in the phone browser, and permission prompts also appear on the phone."},
    "Kompyuter manzili:": {"ru": "Адрес компьютера:", "en": "Computer address:"},
    "Manzilni nusxalash": {"ru": "Копировать адрес", "en": "Copy address"},
    "Yangi kalit": {"ru": "Новый ключ", "en": "New key"},
    "Windows devoriga ruxsat berish": {"ru": "Разрешить в брандмауэре Windows", "en": "Allow through Windows firewall"},
    "To'suvchi qoidalarni ham o'chiradi": {"ru": "Также удаляет блокирующие правила", "en": "Also removes blocking rules"},
    "Ulanmasa, tekshiring:\n1) Telefonda mobil internet o'chiq, Wi-Fi yoqilgan va kompyuter bilan BIR XIL tarmoqda (mehmon/guest Wi-Fi emas).\n2) Yuqoridagi «Kompyuter manzili» ni boshqasiga almashtirib ko'ring (Docker/VPN bo'lsa, birinchisi noto'g'ri bo'lishi mumkin).\n3) «Windows devoriga ruxsat berish» tugmasini bosing (administrator so'raydi).\n4) Telefon brauzerida faqat manzilni oching (kalitsiz): http://MANZIL:PORT/ — sahifa ochilsa, tarmoq yaxshi.\n5) Kompyuter boshqa joyda (masalan, Chrome Remote Desktop orqali ulangan «SERVER») bo'lsa, telefon u bilan bir Wi-Fi'da bo'lmaydi: Tailscale ishlating.":
        {"ru": "Если не подключается, проверьте:\n1) На телефоне мобильный интернет выключен, Wi-Fi включён и в ТОЙ ЖЕ сети, что и компьютер (не гостевой Wi-Fi).\n2) Попробуйте сменить «Адрес компьютера» выше (при Docker/VPN первый может быть неверным).\n3) Нажмите «Разрешить в брандмауэре Windows» (запросит администратора).\n4) В браузере телефона откройте только адрес (без ключа): http://АДРЕС:ПОРТ/ — если страница открылась, сеть в порядке.\n5) Если компьютер в другом месте (например «SERVER» через Chrome Remote Desktop), телефон не будет с ним в одной Wi-Fi: используйте Tailscale.",
         "en": "If it won't connect, check:\n1) On the phone, mobile data is off, Wi-Fi is on and on the SAME network as the computer (not guest Wi-Fi).\n2) Try switching the «Computer address» above (with Docker/VPN the first one may be wrong).\n3) Press «Allow through Windows firewall» (asks for administrator).\n4) In the phone browser open just the address (no key): http://ADDRESS:PORT/ — if the page opens, the network is fine.\n5) If the computer is elsewhere (e.g. a «SERVER» via Chrome Remote Desktop), the phone won't share its Wi-Fi: use Tailscale."},
    "Xavfsizlik: manzildagi kalit (t=...) parol vazifasini bajaradi: uni hech kimga bermang. Ulanish shifrlanmagan (HTTP), shuning uchun faqat ishonchli uy Wi-Fi'ida ishlating. Boshqa joydan ulanish uchun Tailscale kabi shifrlangan tunnel o'rnating va shu manzildagi IP o'rniga kompyuterning Tailscale IP sini yozing. Kalit boshqaga ko'rinib qolsa, «Yangi kalit» ni bosing. Windows xavfsizlik devori so'rasa, «Ruxsat berish» (shaxsiy tarmoq) ni tanlang.":
        {"ru": "Безопасность: ключ в адресе (t=...) работает как пароль — никому его не давайте. Соединение не зашифровано (HTTP), поэтому используйте только в доверенной домашней Wi-Fi. Для доступа извне установите зашифрованный туннель вроде Tailscale и укажите Tailscale-IP компьютера вместо IP в адресе. Если ключ кто-то увидел, нажмите «Новый ключ». Если спросит брандмауэр Windows, выберите «Разрешить» (частная сеть).",
         "en": "Security: the key in the address (t=...) works like a password — don't share it. The connection is unencrypted (HTTP), so use it only on a trusted home Wi-Fi. To connect from elsewhere, set up an encrypted tunnel like Tailscale and use the computer's Tailscale IP instead of the IP in the address. If someone sees the key, press «New key». If the Windows firewall asks, choose «Allow» (private network)."},
    "To'xtatish": {"ru": "Остановить", "en": "Stop"},
    "Yoqish": {"ru": "Включить", "en": "Turn on"},
    "○ O'chiq": {"ru": "○ Выключено", "en": "○ Off"},
    "Yoqilmagan": {"ru": "Не включено", "en": "Not enabled"},
    "127.0.0.1  (faqat shu kompyuter)": {"ru": "127.0.0.1  (только этот компьютер)", "en": "127.0.0.1  (this computer only)"},
    "● Yoqilgan.": {"ru": "● Включено.", "en": "● Enabled."},
    "Server kompyuterda ishlayapti.": {"ru": "Сервер работает на компьютере.", "en": "The server is running on the computer."},
    "Lekin server javob bermayapti!": {"ru": "Но сервер не отвечает!", "en": "But the server isn't responding!"},
    "QR-kod yaratib bo'lmadi.\nManzilni qo'lda yozing.":
        {"ru": "Не удалось создать QR-код.\nВведите адрес вручную.", "en": "Could not create the QR code.\nEnter the address manually."},
    "Devor": {"ru": "Брандмауэр", "en": "Firewall"},
    "Avval «Yoqish» tugmasini bosing.": {"ru": "Сначала нажмите «Включить».", "en": "First press «Turn on»."},
    "✓ Qoida qo'shildi. Endi telefondan qayta urinib ko'ring.":
        {"ru": "✓ Правило добавлено. Теперь попробуйте снова с телефона.", "en": "✓ Rule added. Now try again from the phone."},
    "Qoida topilmadi: administrator so'rovi rad etilgan yoki hali tugamagan.":
        {"ru": "Правило не найдено: запрос администратора отклонён или ещё не завершён.",
         "en": "Rule not found: the administrator prompt was declined or hasn't finished yet."},
    "Eski manzil ishlamay qoladi, telefonda QR-kodni qayta skanerlash kerak. Davom etilsinmi?":
        {"ru": "Старый адрес перестанет работать, нужно заново отсканировать QR-код на телефоне. Продолжить?",
         "en": "The old address will stop working; you'll need to rescan the QR code on the phone. Continue?"},

    # — Plagin sozlamasi va Plaginlar oynasi —
    "Shablon": {"ru": "Шаблон", "en": "Template"},
    "Nomi (lotincha, probelsiz)": {"ru": "Имя (латиницей, без пробелов)", "en": "Name (latin, no spaces)"},
    "Buyruq": {"ru": "Команда", "en": "Command"},
    "Muhit o'zgaruvchilari\n(KALIT=qiymat, har qatorda bittadan)":
        {"ru": "Переменные окружения\n(КЛЮЧ=значение, по одной в строке)",
         "en": "Environment variables\n(KEY=value, one per line)"},
    "Sarlavhalar\n(Authorization: Bearer ..., har qatorda bittadan)":
        {"ru": "Заголовки\n(Authorization: Bearer ..., по одному в строке)",
         "en": "Headers\n(Authorization: Bearer ..., one per line)"},
    "Kalitlar faqat shu kompyuterdagi sozlama faylida saqlanadi.":
        {"ru": "Ключи хранятся только в файле настроек на этом компьютере.",
         "en": "Keys are stored only in the settings file on this computer."},
    "Nomini yozing (lotin harflarida)": {"ru": "Введите имя (латиницей)", "en": "Enter a name (in latin letters)"},
    "Bu nom band": {"ru": "Это имя занято", "en": "This name is taken"},
    "URL ni yozing": {"ru": "Введите URL", "en": "Enter a URL"},
    "Kompyuterdagi dastur (masalan npx ...)":
        {"ru": "Программа на компьютере (например npx ...)", "en": "Program on the computer (e.g. npx ...)"},
    "Masofaviy server (URL)": {"ru": "Удалённый сервер (URL)", "en": "Remote server (URL)"},
    "Tayyor xizmatlarni ulang: fayllar, Notion, GitHub, hujjatlar va boshqalar. Agentlar ularning asboblaridan foydalanadi.":
        {"ru": "Подключайте готовые сервисы: файлы, Notion, GitHub, документы и другие. Агенты используют их инструменты.",
         "en": "Connect ready services: files, Notion, GitHub, docs and more. Agents use their tools."},
    "Plagin": {"ru": "Плагин", "en": "Plugin"},
    "Asboblar": {"ru": "Инструменты", "en": "Tools"},
    "Ko'nikmalar (skills)": {"ru": "Навыки (skills)", "en": "Skills"},
    "Papkaga SKILL.md joylashtiring. Claude ko'nikmalari (~/.claude/skills) va loyihadagi .claude/skills avtomatik topiladi.":
        {"ru": "Поместите SKILL.md в папку. Навыки Claude (~/.claude/skills) и .claude/skills проекта находятся автоматически.",
         "en": "Put a SKILL.md in a folder. Claude skills (~/.claude/skills) and the project's .claude/skills are found automatically."},
    "Ko'nikma": {"ru": "Навык", "en": "Skill"},
    "Manba": {"ru": "Источник", "en": "Source"},
    "Tavsif": {"ru": "Описание", "en": "Description"},
    "Ko'nikmalar papkasini ochish": {"ru": "Открыть папку навыков", "en": "Open skills folder"},
    "dastur": {"ru": "программа", "en": "program"},
    "o'chiq": {"ru": "выкл", "en": "off"},
    "kutilmoqda": {"ru": "ожидание", "en": "pending"},
    "tayyor": {"ru": "готов", "en": "ready"},
    "xato": {"ru": "ошибка", "en": "error"},
    "ulanmoqda": {"ru": "подключение", "en": "connecting"},
    "Asboblar:": {"ru": "Инструменты:", "en": "Tools:"},
    "Ulanmoqda… (birinchi marta npx paketni yuklab oladi, 1-2 daqiqa ketishi mumkin)":
        {"ru": "Подключение… (при первом запуске npx загрузит пакет, может занять 1–2 минуты)",
         "en": "Connecting… (on first run npx downloads the package, may take 1–2 minutes)"},
    "Bu plagin o'chirilsinmi?": {"ru": "Удалить этот плагин?", "en": "Delete this plugin?"},
    "Papka": {"ru": "Папка", "en": "Folder"},

    # — Boshqa (xush kelibsiz, status, nusxalash) —
    "Xush kelibsiz!": {"ru": "Добро пожаловать!", "en": "Welcome!"},
    "Kompyuteringizda quyidagi agentlar topildi:":
        {"ru": "На вашем компьютере найдены агенты:", "en": "The following agents were found on your computer:"},
    "Hammasini qo'shaymi?": {"ru": "Добавить всех?", "en": "Add them all?"},
    "Boshlash uchun «Sozlamalar» da agent qo'shing (Claude, ChatGPT, Gemini yoki lokal model).":
        {"ru": "Чтобы начать, добавьте агента в «Настройках» (Claude, ChatGPT, Gemini или локальная модель).",
         "en": "To start, add an agent in «Settings» (Claude, ChatGPT, Gemini or a local model)."},
    "To'xtatilmoqda…": {"ru": "Остановка…", "en": "Stopping…"},
    "Nusxalash": {"ru": "Копировать", "en": "Copy"},
    "Nusxalandi ✓": {"ru": "Скопировано ✓", "en": "Copied ✓"},
}


def t(s: str) -> str:
    """Matnni joriy tilga tarjima qiladi; topilmasa o'zbekcha manba qaytadi."""
    if _lang == "uz" or not s:
        return s
    entry = TR.get(s)
    if not entry:
        return s
    return entry.get(_lang, s)
