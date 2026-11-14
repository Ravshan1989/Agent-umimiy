<div align="center">

# 🤖 Agent Umimiy

**A desktop app that brings every AI agent together in one window**

Work with Claude, ChatGPT, Gemini, Ollama and other models in a single window:
the agents read and edit your files, control the browser, and help each other.

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Version](https://img.shields.io/badge/version-0.4.2-orange)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![UI](https://img.shields.io/badge/interface-Uzbek-1EB53A)
[![Tests](https://github.com/Ravshan1989/Agent-umimiy/actions/workflows/tests.yml/badge.svg)](https://github.com/Ravshan1989/Agent-umimiy/actions/workflows/tests.yml)

[📥 Download](#-installation) · [✨ Features](#-features) · [⚙️ Setup](#️-setup) · [📖 Guide](#-detailed-guide) · [👨‍💻 Developers](#-for-developers)

🌐 [O'zbekcha](README.md) · **English** · [Русский](README.ru.md)

</div>

---

## 📌 What is this?

**Agent Umimiy** is a desktop app that gathers several AI agents in one place.
You don't need a separate site or app for each service: everything lives in one convenient,
dark-themed window. The interface is currently **in Uzbek**.

The app **finds the agents already on your computer by itself** — you don't have to type anything.

## 📸 Screenshots

> Screenshots go into the `docs/screenshots/` folder ([guide](docs/screenshots/README.md)).
> Once you add the files, uncomment the block below and the images appear.

<!--
<div align="center">
<img src="docs/screenshots/main.png" alt="Main window" width="800">
<br><br>
<img src="docs/screenshots/settings.png" alt="Settings" width="420">
<img src="docs/screenshots/phone.png" alt="Phone control" width="240">
</div>
-->

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🧠 | **Multi-model** | Anthropic (Claude), OpenAI and compatible APIs (OpenRouter, Groq, LM Studio), Google Gemini, Ollama, FreeLLMAPI |
| 🔍 | **Auto-detection** | Finds Ollama, LM Studio, FreeLLMAPI and the Claude CLI on your computer and offers them as agents |
| 🛠 | **Real agent mode** | The agent reads, writes, edits and searches files in the project folder and runs commands (with your permission) |
| 🤝 | **Team of agents** | One agent can ask another for help — e.g. Claude getting advice from Gemini |
| 🌐 | **Browser control** | The agent opens Edge/Chrome, reads pages, clicks buttons and types text. No extra software needed |
| 📎 | **File attachments** | Add images, PDFs, Word and text files to the chat |
| 📊 | **Document analysis** | Read and analyze Excel (xlsx), PowerPoint (pptx), Word (docx) and CSV tables |
| 🔌 | **MCP plugins** | Connect ready MCP servers (GitHub, Notion, files and more) as tools for the agents |
| 📚 | **Skills** | Teach an agent a way of working with `SKILL.md` instructions. The `~/.claude/skills` folder is detected automatically too |
| 📱 | **Phone control** | Scan a QR code — the chat opens in your phone's browser, and permission prompts reach the phone too |
| 💾 | **Conversations are saved** | Your chats stay where you left them after you close and reopen the app |
| 🌿 | **Git helper** | Shows the project's Git status in plain language |

## 📥 Installation

**Windows 10/11 (64-bit)**

1. Download **`AgentUmimiy-Setup.exe`** from the
   **[latest release](https://github.com/Ravshan1989/Agent-umimiy/releases/latest)**.
2. Double-click it and install: an "Agent Umimiy" shortcut appears on the desktop.
3. If Windows warns you: **"More info"** → **"Run anyway"**.

> [!NOTE]
> The Windows warning appears because the app is not code-signed — this is normal for new and
> independent apps.

**Linux (64-bit)**

1. Download **`AgentUmimiy-Linux-x86_64.tar.gz`** from the **[latest release](https://github.com/Ravshan1989/Agent-umimiy/releases/latest)**.
2. Unpack and run: `tar -xzf AgentUmimiy-Linux-x86_64.tar.gz && ./AgentUmimiy/AgentUmimiy`
3. To paste screenshots with Ctrl+V, install `xclip` (X11) or `wl-clipboard` (Wayland).

**Phone (iPhone, Android)**: there is no separate app. Start the [web server](#web-server-many-people-on-the-local-network) on a computer or server and use it on the phone like an app.

## ⚙️ Setup

### Adding an agent

When the app starts it searches for existing agents by itself. Add the rest via **⚙ Settings → ➕ Add**:
pick the type, enter the API key, press **Test**. You can also provide the API key through an
environment variable:

| Service | Environment variable | Default model |
|---|---|---|
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Google Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| Ollama / LM Studio | not needed (local) | models on your computer |

### Phone control

1. Open and enable the **"Phone control"** section in the app.
2. Keep the phone and the computer **on the same Wi-Fi network**.
3. Scan the on-screen QR code with your phone's camera.

Access is protected with a secret key (token).

### Where are the settings stored?

```
%APPDATA%\AgentUmimiy\agents.json
```

### Project instructions

If the project folder has a `CLAUDE.md` or `AGENTS.md` file, the agent always takes it into account.

## 🔒 Security

- The agent changes files **only in the project folder you chose**.
- Running commands and writing files are done **with your permission**.
- The browser runs in a separate profile — it doesn't touch your main browser's data.
- Your API keys are stored only on your own computer.

## 📖 Detailed guide

### Working with a project (coding assistant)

Use the **"Choose project folder"** button at the top to select your own project folder. After that
the agents (Claude, ChatGPT-compatible, Ollama) will:

- **read** folders and files and **search** through the code (without asking);
- **create / edit** files and **run commands** (tests, installs...) — **asking each time**, with a
  diff shown;
- the "Always allow in this chat" button turns off permission prompts; the **■** button stops the work.

Security: the agent works only inside the chosen folder (it can't go outside, and won't touch `.git`).
In "All together" and "Council" modes several agents run at once, so they are **read-only**.
CLI agents like `claude`, `codex` run in the chosen folder.

The **Git** button: what changed (in plain language), viewing the changes, **Commit**, **Push**,
**Pull**. Git must be installed on your computer (git-scm.com); passwords come from your Git settings.

### Reading and analyzing files

| File | What is read |
|---|---|
| **Excel (.xlsx)** | all sheets, dates (2024-03-15), numbers, booleans; the computed result of formulas |
| **PowerPoint (.pptx)** | slide titles, text, tables, speaker notes |
| **Word (.docx)** | headings (#), lists (•), tables |
| **CSV/TSV** | `,` `;` Tab separators and UTF-8/Windows-1251 encodings are detected automatically |
| **PDF** | text; for scanned PDFs, send the page as an image (Claude/GPT-4/Gemini read it themselves) |
| **Image** | models that can see |

For large tables in the project folder the agent uses special tools: **`analyze_data`** (columns,
types, empty cells, min/max/average/median/sum, most frequent values) and **`read_table`** (reading
rows by number or finding them by text). Large text files (3 MB+) are read in chunks. Instead of an
attached, very large table, the agent gets the analysis and the first rows.
**Limits:** old `.xls/.doc/.ppt` formats aren't supported (re-save in the new format); reading text
inside an image (OCR) depends on the model; analysis quality depends on the chosen model's strength.

### Images, PDFs and files

Use the **＋** button in the input area to attach an **image** (PNG, JPG, GIF, WebP), a **PDF**,
a **Word (.docx)** or a **text file** — the agent looks at them and answers. Images can be seen by
Claude, ChatGPT-compatible models, Gemini and vision-capable Ollama models. PDF text is sent to other
models too. Limit: image ≤ 5 MB, PDF ≤ 20 MB.

### Creating files (Word, Excel)

Ask the agent for a document or a table: "Make an Excel table from this data", "Write a letter in Word". The agent creates a finished **.docx** or **.xlsx** file (text files too: .txt, .md, .csv, .html) and shows it in the chat.
- **In the app window:** the file is saved to `Documents\Agent Umimiy`; click the row in the chat to open it.
- **On the web server:** a "Download" link appears in the chat; only the owner of that conversation can get the file.
- An existing file is never overwritten: a taken name gets a number.
- **Live preview (web server):** a page or chart (`.html`) and a table (`.xlsx`, `.csv`) created by the agent opens at once in a panel next to the chat; the "Ko'rish" (View) button on the file row opens it again. To get a chart, ask: "Draw a chart from these numbers". The page runs in a sandbox: it cannot reach your conversations or account. In the app window, clicking the file opens it in the browser or Excel.
- Works with agents that support tools (Claude, OpenAI-compatible, Ollama); not yet with Gemini and CLI agents.

### Internet

Agents can **search the internet** (DuckDuckGo) and **read pages**, and when needed they offer to
**open the page in your browser** (with permission). You can turn this off in settings. Security:
access to the computer and the internal network (localhost, 192.168.x.x, etc.) is forbidden; text on
a page is treated as information only, never as a "command".
For clicking buttons and filling forms on sites, see the "The agent works in the browser" section below.

### Saving conversations, instructions, plan

- **Saving:** conversations (tabs, history, project) are stored in `%APPDATA%\AgentUmimiy\chats.json`
  and restored when the app reopens (the last 15 conversations). You can turn this off or clear the
  history in settings. The file is unencrypted: don't write secrets or turn saving off.
- **Project instructions:** if the project folder has `CLAUDE.md`, `AGENTS.md` or `AGENT.md`, the
  agent reads it automatically and follows the rules.
- **Plan card:** in multi-step work the agent shows a "Plan" list and checks off the steps.
- **Markdown:** headings, lists, tables, `code`, links and code blocks look nice in the answers.

### Phone control

**Settings → "Phone control" → Enable.** The app shows a QR code: scan it with your phone's camera
(phone and computer on the same Wi-Fi) and the chat opens in your phone's browser. From there you
type, send files/images, stop work, switch between conversations, and **answer permission prompts
("A file will be changed", "A command will run"...) from the phone**: the window on the computer
closes itself.
- The computer must be on and the app open. Settings, adding agents and plugins are only on the computer.
- Access uses a long secret key (the `t=...` in the QR): wrong attempts are blocked. **The key is like
  a password**: if someone sees it, press "New key".
- The connection is **unencrypted (HTTP)**: only use it on a trusted home Wi-Fi (not café/public
  networks). To use it away from home, set up an encrypted tunnel like Tailscale.
- If the Windows firewall asks the first time, allow it for "Private networks". Off by default.

### Web server: many people on the local network

Run the app on one computer or server and people on the network use it from a browser (nothing to install).

**From the app window:** Settings → **"Web server"** → **Turn on**. The window shows the addresses and the invite code. Once turned on, the server starts by itself every time the app opens.

**Without a window (on a server):**

```bash
python -m agent_umimiy --serve            # default: all interfaces, port 8080
python -m agent_umimiy --serve --port 9000 --host 192.168.1.10
```

The app prints the address and an **invite code**. People open the address and register with a name, a password and that code. Everyone has their own conversations, answers appear as they are written, and files and screenshots (Ctrl+V) can be attached.
- Agents and API keys come from `agents.json` on that computer: everyone uses **your keys and your limits**.
- For safety, agents in web mode **cannot touch** the server's files, commands, browser or plugins; CLI agents (`claude`, `codex`...) are not listed. Chat, file analysis and web search work.
- Data is stored in `server.db` (SQLite) in the settings folder. Passwords are stored hashed.
- The connection is **not encrypted (HTTP)**: use it only on a trusted local network. To expose it to the internet, put an HTTPS proxy (Caddy, nginx) in front. On Windows, allow the port if the firewall asks.

**Like an app on the phone (PWA).** Open the server address in the phone browser and add it to the home screen:
- **iPhone (Safari):** Share button → **"Add to Home Screen"**.
- **Android (Chrome):** menu (⋮) → **"Install app"** or **"Add to Home screen"**.

An Agent Umimiy icon appears and opens full screen. On Android, full-screen mode works only on an **HTTPS** address; on a plain `http://192.168...` address the icon opens a browser tab.

**HTTPS and use away from home.** The easiest way is [Tailscale](https://tailscale.com) (free). Install it on the server and the phones, then run `tailscale serve --bg 8080` on the server: you get a secure `https://...ts.net` address that is open only to your own devices.

### Plugins (MCP) and skills

**Plugins.** The **Plugins** button in the left panel: "Add" → pick a ready template (Files, Memory,
Docs/Context7, Notion, Playwright, GitHub...) or enter any MCP server yourself (command or URL, plus a
key if needed). The app starts the server and gives its tools to all agents.
- **Read** tools run without permission, **writing** ones ask each time (there's an "Always allow this
  plugin" button). In "All together" and "Council" modes only the read tools run.
- Plugins that start with `npx ...` need **Node.js** (nodejs.org) on the computer; the package is
  downloaded on first run (1–2 minutes).
- Keys (`NOTION_TOKEN`, a GitHub token...) are stored only in the settings file on this computer.
- **Limit:** the ready connections on claude.ai (Gmail, Google Drive, Calendar...) are tied to your
  claude.ai account and can't be moved into this app. Instead you connect those services' own MCP
  servers (with your own key). Remote servers that require OAuth (a "Sign in" button in the browser)
  aren't supported yet.

**Skills.** A folder with a `SKILL.md` file (Claude format: `name`, `description`, text). They're
found automatically in: `%APPDATA%\AgentUmimiy\skills\<name>\SKILL.md`, `~/.claude/skills`, skills in
Claude plugins, and the project's `.claude/skills`. The agent loads the right skill based on the
description and follows it.

### The agent works in the browser

The agent opens a site in a **real browser window**, reads it, clicks buttons and fills forms (you see
what's happening in the window). On Windows it uses **Edge** (or Chrome), nothing to install.
- The browser opens in a **separate profile** (`%APPDATA%\AgentUmimiy\browser-profile`): it doesn't
  touch the passwords and sessions in your main browser. If you sign in to a site once yourself, you
  stay signed in next time.
- **Every new site** and **every keystroke** asks for permission. It **won't type in a password
  field**: enter the password yourself in the window.
- In "All together" and "Council" modes the browser is off. You can disable it entirely in settings.
- Page text is information only for the agent: it won't follow "commands" written there.

### Agents know each other

Each agent knows the **full list of agents** in the app (ask "which agents are there?" and it names
them all) and, when needed, asks another agent for help (`ask_agent`): e.g. "try asking gemini". The
agent called for help can only read and can't call another itself. The `⇄` line in the chat shows who
asked whom.

### Several conversations

At the top there are browser-like **tabs**: each conversation has its own history and its own project
folder, and they run at the same time (a green dot appears on a tab when a background conversation
finishes). `＋` — new conversation, `×` — close.
Conversations are saved when the app closes (see the "Saving" item above).

### Modes

| Mode | How it works |
|---|---|
| Automatic | picks an agent by the keywords in `routes` |
| Single agent | the first selected agent |
| All at once | all agents answer in parallel |
| Sequential | each agent improves the previous one's answer |
| Council | everyone answers, a judge agent produces a single conclusion |

### Connecting FreeLLMAPI (local gateway)

If FreeLLMAPI (`localhost:3001`) is running on your computer:
1. **Settings → ＋ Add → Type: "FreeLLMAPI — local gateway"** (the address fills in itself). Or
   "Auto-detect" finds it by itself.
2. Put the **API KEY** from the FreeLLMAPI page (**Agents** section) into the "API key" field.
3. The **List** button fetches the gateway's models — pick one, **Test** → **Save**.

The key is stored only in the settings file on your computer. If a model doesn't support file tools
(tools), the app falls back to a plain chat.

### Local agents

- If **Ollama** (`localhost:11434`) and **LM Studio** (`localhost:1234`) are running, "Auto-detect"
  adds their models.
- If the `claude`, `codex`, `gemini`, `aider` programs are installed, they are found automatically too.
- Any other program: type "Program on the computer", command `my-agent {prompt}`.

## 👨‍💻 For developers

### Running from source

Python 3.9+ required. Optional libraries: `pypdf` (reading PDFs), `qrcode` (QR code for phone) `pillow` (pasting screenshots with Ctrl+V), `python-docx` and `openpyxl` (creating Word and Excel files).

```bash
git clone https://github.com/Ravshan1989/Agent-umimiy.git
cd Agent-umimiy
pip install pypdf qrcode pillow python-docx openpyxl
python app.py                              # window
python app.py --cli -m broadcast "hello"   # terminal
python -m unittest discover -s tests -t .  # tests
```

### Project structure

| File | Purpose |
|---|---|
| `gui.py`, `theme.py` | window and design (Tkinter) |
| `providers.py` | Claude, OpenAI, Gemini, Ollama, CLI agents |
| `stream.py` | reading streamed responses |
| `writer.py` | creating Word, Excel and text files |
| `preview.py` | live preview of created files (sandboxed) |
| `server.py`, `server_page.py`, `store.py` | web server mode: HTTP, page, SQLite |
| `agentic.py`, `tools.py` | the agent loop and tools (files, commands, search) |
| `orchestrator.py` | modes and agent-to-agent help |
| `browser.py` | browser control (CDP) |
| `mcp.py`, `skills.py` | plugins and skills |
| `remote.py`, `remote_page.py` | phone control |
| `docs.py`, `attachments.py` | reading documents and files |
| `detect.py` | auto-detecting agents |

New agent type: subclass `Agent` in `providers.py` and add it to `KINDS`.

### Building the .exe

- **GitHub Actions:** Actions → "Dastur yig'ish / Build" → Run workflow. Result: `AgentUmimiy-Setup.exe` (Windows) and `AgentUmimiy-Linux-x86_64.tar.gz` (Linux).
- **Manually (Windows):** `packaging\build_windows.bat` (needs Python and, optionally, Inno Setup).

## ❓ Frequently asked questions

<details>
<summary><b>Is it paid?</b></summary>

The app itself is free. To use cloud models (Claude, ChatGPT) you need their own API key. Local models
via Ollama or LM Studio can be used completely free.
</details>

<details>
<summary><b>Do I need the internet?</b></summary>

For cloud models — yes. Local models with Ollama/LM Studio work without the internet too.
</details>

<details>
<summary><b>Does it work on Mac or Linux?</b></summary>

Ready packages exist for Windows and Linux (see Installation above). On macOS you can try running
from source (`python app.py`), but it hasn't been tested there.
</details>

## 💜 Claude for Open Source

Agent Umimiy is an open-source project and fully supports working with Claude. Anthropic offers the
**Claude for Open Source** program for the open-source community: eligible OSS maintainers and
contributors can use the **Claude Ultra** plan **free for 6 months**.

- **Who is it for?** People who actively maintain open-source projects or contribute to them
  regularly. Your GitHub activity is taken into account.
- **There are conditions:** the program has its own criteria — it isn't granted to everyone. The full
  terms and Q&A are on the official page.

👉 **Apply:** <https://claude.com/contact-sales/claude-for-oss>

> The link goes to Anthropic's official page. The terms and availability are set by Anthropic and may
> change.

## 🗺 Roadmap

- [x] Open-source the code
- [x] Documentation (README) in English and Russian
- [x] Linux version
- [ ] macOS version
- [ ] English and Russian app interface
- [ ] Automatic updates

## 📄 License

[MIT](LICENSE) — the code may be freely used, modified and distributed.

## 🤝 Contributing

Found a bug or have a suggestion? Open an [Issue](../../issues). Pull requests are warmly welcome too:

1. Fork the repository and open a new branch.
2. Make your change and run the tests: `python -m unittest discover -s tests -t .`
3. Send a pull request.

---

<div align="center">

**Agent Umimiy** — built to make working with AI in Uzbek easier ❤️

⭐ If you like the project, don't forget to give it a star!

</div>
