import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity, BarChart3, Bell, Bot, Boxes, CalendarClock, Camera, Check, CheckCircle2, ChevronDown, ChevronRight,
  Clock3, Database, Download, FileSpreadsheet, FileText, Folder, FolderKanban, Globe2, Home, Layers,
  LayoutGrid, Loader2, LogOut, Menu, MessageSquare, Mic, Moon, Paperclip, Plus, Puzzle, Search, Send,
  Settings, ShieldCheck, SlidersHorizontal, Sparkles, Square, Sun, Trash2, TriangleAlert, Volume2, X, Zap,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { Markdown } from "./Markdown";

type Agent = { name: string; model?: string; description?: string };
type Chat = { id: number; title?: string };
type Attached = string | { name?: string; file?: string };  // eski yozuvlar oddiy matn, yangilari diskdagi nom bilan
type RecordItem = { k: string; text?: string; name?: string; agent?: string; meta?: string; err?: boolean; files?: Attached[]; kind?: string };
type LiveState = Record<string, string>;
type WebSettings = { lang: "uz" | "ru" | "en"; theme: "dark" | "light"; accent: "violet" | "blue" | "cyan" | "emerald" };
type NetworkInfo = { enabled: boolean; urls: string[]; port: number; invite: string; error: string };
type Employee = { id: number; name: string; enabled: boolean; chats: number };
type ApiError = Error & { code?: number };
type AutoJob = { id: number; title: string; prompt: string; agent: string; interval_minutes: number; enabled: boolean; last_run: number; last_status: string; last_result: string };
type RagHit = { path: string; name: string; snippet: string };
type TelegramInfo = { enabled: boolean; status: string; bot_username: string; allowed_username: string; error: string };
type AgentStat = { agent: string; calls: number; errors: number; avg_seconds: number };
type AnalyticsInfo = { user_messages: number; agent_messages: number; errors: number; files_created: number; by_agent: AgentStat[] };
type MemoryItem = { id: string; fact: string };
type SystemHealth = { cpu_cores?: number; python?: string; disk_free_gb?: number; disk_total_gb?: number; ollama_online?: boolean; freellm_online?: boolean };
type Workspace = { project: string; plugins: { name: string; transport: string; enabled: boolean }[]; skills: { name: string; description: string; source: string }[]; automation: { available: boolean; reason: string; jobs?: AutoJob[] }; rag?: { indexed: number }; telegram?: TelegramInfo; memory?: MemoryItem[]; system?: SystemHealth; analytics?: AnalyticsInfo; database: { engine: string; status: string; users: number; chats: number } };
type Task = { id: number; text: string; when: string; done: boolean };
type Approval = { id: string; agent: string; kind: string; title: string; detail: string };
type SpeechRec = { lang: string; interimResults: boolean; start: () => void; stop: () => void; onresult: ((e: { results: { 0: { transcript: string } }[] }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null };
const MAX_FILE = 15 * 1024 * 1024;
const NAV: [string, typeof Home][] = [["Bosh sahifa", Home], ["Suhbat", MessageSquare], ["Agentlar", Bot], ["Fayllar", FileText], ["Loyihalar", FolderKanban], ["Plaginlar", Puzzle], ["Avtomatlashtirish", Boxes], ["Hisobotlar", BarChart3], ["Ma’lumotlar bazasi", Database], ["Sozlamalar", Settings]];
const WORKSPACE_VIEWS = ["Bosh sahifa", "Loyihalar", "Plaginlar", "Avtomatlashtirish", "Hisobotlar", "Ma’lumotlar bazasi", "Sozlamalar"];
const I18N: Record<"ru" | "en", Record<string, string>> = {
  ru: {
    "Bosh sahifa": "Главная", "Suhbat": "Чат", "Agentlar": "Агенты", "Fayllar": "Файлы", "Loyihalar": "Проекты",
    "Plaginlar": "Плагины", "Avtomatlashtirish": "Автоматизация", "Hisobotlar": "Отчёты", "Ma’lumotlar bazasi": "База данных",
    "Sozlamalar": "Настройки", "Yangi suhbat": "Новый чат", "Agent Umimiy bilan suhbat": "Чат с Agent Umimiy",
    "Sizning ko‘p funksiyali AI yordamchingiz": "Ваш многофункциональный ИИ-помощник",
    "Faol agentlar": "Активные агенты", "Vazifalar": "Задачи", "Server: Ulangan": "Сервер: Подключён",
    "Avtomatik agent": "Авто-выбор агента", "Xabaringizni yozing...": "Введите сообщение...",
  },
  en: {
    "Bosh sahifa": "Dashboard", "Suhbat": "Chat", "Agentlar": "Agents", "Fayllar": "Files", "Loyihalar": "Projects",
    "Plaginlar": "Plugins", "Avtomatlashtirish": "Automation", "Hisobotlar": "Analytics", "Ma’lumotlar bazasi": "Database",
    "Sozlamalar": "Settings", "Yangi suhbat": "New chat", "Agent Umimiy bilan suhbat": "Chat with Agent Umimiy",
    "Sizning ko‘p funksiyali AI yordamchingiz": "Your multi-functional AI assistant",
    "Faol agentlar": "Active agents", "Vazifalar": "Tasks", "Server: Ulangan": "Server: Connected",
    "Avtomatik agent": "Auto-select agent", "Xabaringizni yozing...": "Type your message...",
  },
};
const PROMPTS: [string, string, typeof Home, string][] = [
  ["Excel ma’lumotni tahlil qil", "Biriktirilgan Excel faylni tahlil qilib ber", FileSpreadsheet, "excel"],
  ["Word hujjat tayyorla", "Word hujjat tayyorlab ber: ", FileText, "word"],
  ["PowerPoint taqdimot", "PowerPoint (.pptx) taqdimot tayyorlab ber: ", Layers, "violet"],
  ["Vebdan ma’lumot top", "Internetdan shu mavzu bo‘yicha ma’lumot top: ", Globe2, "cyan"],
  ["Shartnoma / Huquqiy tahlil", "Ushbu matn yoki shartnomani huquqiy va moliyaviy jihatdan tahlil qil: ", ShieldCheck, "amber"],
  ["Hisobot tayyorla", "Hisobot tayyorlab ber: ", BarChart3, "pdf"],
];

const isNotice = (r: RecordItem) => r.k === "agent" || (r.k === "act" && r.kind === "file");

function fileTone(name = "") {
  const ext = name.toLowerCase().split(".").pop() || "";
  if (["xlsx", "xls", "csv", "tsv"].includes(ext)) return "excel";
  if (ext === "pdf") return "pdf";
  if (["docx", "doc", "txt", "md"].includes(ext)) return "word";
  return "blue";
}

function formatWhen(value: string) {
  if (!value) return "Vaqt belgilanmagan";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Vaqt belgilanmagan";
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((day(date) - day(new Date())) / 86400000);
  const time = `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  const label = diff === 0 ? "Bugun" : diff === 1 ? "Ertaga" : diff === -1 ? "Kecha" : `${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}.${date.getFullYear()}`;
  return `${label}, ${time}`;
}

function loadTasks(user: string): Task[] {
  try { const raw = JSON.parse(localStorage.getItem(`au-tasks-${user}`) || "[]"); return Array.isArray(raw) ? raw : []; }
  catch { return []; }
}

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? { credentials: "same-origin" } : {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || `Xato ${response.status}`) as ApiError;
    error.code = response.status;
    throw error;
  }
  return payload as T;
}

function Robot({ small = false }: { small?: boolean }) {
  return <div className={small ? "robot robot-small" : "robot"} aria-label="Agent Umimiy AI robot">
    <div className="robot-aura" /><div className="robot-antenna"><i /></div>
    <div className="robot-head"><span className="robot-ear left" /><span className="robot-ear right" />
      <div className="robot-face"><i className="eye eye-left" /><i className="eye eye-right" /><span className="robot-smile" /></div>
    </div>
    <div className="robot-neck" /><div className="robot-body"><b>AU</b></div>
    <span className="robot-arm arm-left" /><span className="robot-arm arm-right" />
    <span className="robot-foot foot-left" /><span className="robot-foot foot-right" />
    <div className="robot-ring" />
  </div>;
}

function App() {
  const [user, setUser] = useState("");
  const [authChecked, setAuthChecked] = useState(false);
  const [register, setRegister] = useState(false);
  const [authName, setAuthName] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState<number | null>(null);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [live, setLive] = useState<LiveState>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<{ name: string; data: string }[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("auto");
  const [mobileNav, setMobileNav] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [settings, setSettings] = useState<WebSettings>({ lang: "uz", theme: "dark", accent: "violet" });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [network, setNetwork] = useState<NetworkInfo | null>(null);
  const [networkBusy, setNetworkBusy] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeBusy, setEmployeeBusy] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaceError, setWorkspaceError] = useState("");
  const [activeView, setActiveView] = useState("Bosh sahifa");
  const [search, setSearch] = useState("");
  const [navHidden, setNavHidden] = useState(false);
  const [desktop, setDesktop] = useState(false);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskText, setTaskText] = useState("");
  const [taskWhen, setTaskWhen] = useState("");
  const [seenNotices, setSeenNotices] = useState(0);
  const [listening, setListening] = useState(false);
  const [autoTitle, setAutoTitle] = useState("");
  const [autoPrompt, setAutoPrompt] = useState("");
  const [autoInterval, setAutoInterval] = useState(60);
  const [newAgentName, setNewAgentName] = useState("");
  const [newAgentType, setNewAgentType] = useState("openai");
  const [newAgentModel, setNewAgentModel] = useState("");
  const [newAgentUrl, setNewAgentUrl] = useState("");
  const [newAgentKey, setNewAgentKey] = useState("");
  const [newAgentDesc, setNewAgentDesc] = useState("");
  const [projectInput, setProjectInput] = useState("");
  const [ragQuery, setRagQuery] = useState("");
  const [ragResults, setRagResults] = useState<RagHit[]>([]);
  const [tgToken, setTgToken] = useState("");
  const [tgUser, setTgUser] = useState("");
  const [memoryFact, setMemoryFact] = useState("");
  const recognition = useRef<SpeechRec | null>(null);
  const noticePanel = useRef<HTMLElement>(null);
  const eventSource = useRef<EventSource | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const composerInput = useRef<HTMLInputElement>(null);
  const stickToBottom = useRef(true);  // foydalanuvchi pastda bo‘lsa, yangi xabarlarda avtomatik pastga tushamiz

  async function decideApproval(answer: "yes" | "always" | "no") {
    if (!approval || approvalBusy) return;
    const current = approval;
    setApprovalBusy(true);
    try {
      await api("/api/approve", { id: current.id, answer });
      setApproval((value) => value?.id === current.id ? null : value);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setApprovalBusy(false);
    }
  }

  const refresh = useCallback(async () => {
    const me = await api<{ user: string; agents: Agent[]; chats: Chat[]; desktop?: boolean }>("/api/me");
    setUser(me.user); setAgents(me.agents || []); setChats(me.chats || []); setDesktop(Boolean(me.desktop));
    return me;
  }, []);

  const openChat = useCallback((id: number, show = true) => {
    eventSource.current?.close();
    setChatId(id); setRecords([]); setLive({}); setBusy(false);
    stickToBottom.current = true;
    try { if (user) localStorage.setItem(`au-active-chat-${user}`, String(id)); } catch { /* chat serverda qoladi */ }
    setApproval(null); setApprovalBusy(false);
    const source = new EventSource(`/api/stream?chat=${id}`);
    eventSource.current = source;
    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as Record<string, unknown>;
      if (item.type === "init") {
        setRecords((item.records as RecordItem[]) || []);
        setSeenNotices(((item.records as RecordItem[]) || []).filter(isNotice).length);
        setLive((item.live as LiveState) || {});
        setBusy(Boolean(item.busy));
        setApproval((item.approval as Approval | undefined) || null);
      } else if (item.type === "record") {
        const record = item.record as RecordItem;
        setRecords((current) => [...current, record]);
        if (record.k === "agent") setLive({});
      } else if (item.type === "delta") {
        const name = String(item.agent || "Agent");
        setLive((current) => ({ ...current, [name]: (current[name] || "") + String(item.text || "") }));
      } else if (item.type === "turn") {
        const name = String(item.agent || "Agent");
        setLive((current) => { const next = { ...current }; delete next[name]; return next; });
      } else if (item.type === "busy") setBusy(true);
      else if (item.type === "agent_changed") setSelectedAgent(String(item.agent || "auto"));
      else if (item.type === "approval") setApproval(item.approval as Approval);
      else if (item.type === "approval_done") setApproval((current) => current?.id === item.id ? null : current);
      else if (item.type === "done") {
        setBusy(false); setLive({});
        void refresh().catch(() => undefined);
      } else if (item.type === "overflow") {
        toast.info("Jonli ulanish yangilanmoqda");
        source.close();
        window.setTimeout(() => openChat(id, false), 500);
      }
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) toast.error("Suhbat bilan aloqa uzildi");
    };
    if (show) setActiveView("Suhbat");
    setMobileNav(false);
  }, [refresh, user]);

  useEffect(() => {
    let active = true;
    api<{ user: string; agents: Agent[]; chats: Chat[]; desktop?: boolean }>("/api/me")
      .then((me) => {
        if (!active) return;
        setUser(me.user); setAgents(me.agents || []); setChats(me.chats || []); setDesktop(Boolean(me.desktop));
        void api<WebSettings>("/api/settings").then((value) => { setSettings(value); setTheme(value.theme); }).catch(() => undefined);
        setAuthChecked(true);
        if (me.chats?.length) {
          let remembered = 0;
          try { remembered = Number(localStorage.getItem(`au-active-chat-${me.user}`) || 0); } catch { /* brauzer xotirasi yopiq */ }
          openChat(me.chats.find((chat) => chat.id === remembered)?.id || me.chats[0].id, false);
        }
      })
      .catch((error: ApiError) => {
        if (!active) return;
        if (error.code !== 401) toast.error(error.message);
        setAuthChecked(true);
      });
    return () => { active = false; eventSource.current?.close(); };
  }, [openChat]);

  useEffect(() => {
    // Faqat foydalanuvchi pastda turgan bo‘lsa siljitamiz: yuqoriga o‘qish uchun chiqqan bo‘lsa, joyida qoladi
    const box = messagesEnd.current?.parentElement;
    if (box && stickToBottom.current) box.scrollTop = box.scrollHeight;
  }, [records, live, busy, activeView]);
  useEffect(() => {
    if (!user || !WORKSPACE_VIEWS.includes(activeView)) return;
    let alive = true;
    setWorkspaceError("");
    api<Workspace>("/api/workspace").then((data) => { if (alive) setWorkspace(data); })
      .catch((error) => { if (alive) setWorkspaceError((error as Error).message); });
    return () => { alive = false; };
  }, [activeView, user]);

  useEffect(() => { setTasks(user ? loadTasks(user) : []); }, [user]);

  const refreshEmployees = useCallback(async () => {
    const result = await api<{ users: Employee[] }>("/api/network/users");
    setEmployees(result.users);
  }, []);

  useEffect(() => {
    if (desktop && activeView === "Sozlamalar") void refreshEmployees().catch(() => setEmployees([]));
  }, [desktop, activeView, refreshEmployees]);

  async function manageEmployee(employee: Employee, action: "enable" | "disable" | "delete") {
    if (action === "delete" && !window.confirm(`${employee.name} hisobini va uning suhbatlarini butunlay o‘chirasizmi?`)) return;
    setEmployeeBusy(employee.id);
    try {
      const result = await api<{ users: Employee[] }>("/api/network/users/action", { id: employee.id, action });
      setEmployees(result.users);
      toast.success(action === "delete" ? "Xodim hisobi o‘chirildi" : action === "disable" ? "Xodim kirishi to‘xtatildi" : "Xodim kirishi yoqildi");
    } catch (error) { toast.error((error as Error).message); }
    finally { setEmployeeBusy(null); }
  }

  function saveTasks(next: Task[]) {
    setTasks(next);
    try { localStorage.setItem(`au-tasks-${user}`, JSON.stringify(next)); } catch { /* brauzer xotirasi yopiq bo‘lsa, vazifalar faqat shu oynada turadi */ }
  }

  function addTask(event: FormEvent) {
    event.preventDefault();
    const text = taskText.trim();
    if (!text) return;
    saveTasks([...tasks, { id: Date.now(), text, when: taskWhen, done: false }]);
    setTaskText(""); setTaskWhen("");
  }

  function toggleMic() {
    if (recognition.current) { recognition.current.stop(); return; }
    const scope = window as unknown as Record<string, (new () => SpeechRec) | undefined>;
    const Recognition = scope.SpeechRecognition || scope.webkitSpeechRecognition;
    if (!Recognition) { toast.info("Bu brauzer ovozli kiritishni qo‘llamaydi"); return; }
    const rec = new Recognition();
    rec.lang = settings.lang === "ru" ? "ru-RU" : settings.lang === "en" ? "en-US" : "uz-UZ";
    rec.interimResults = false;
    rec.onresult = (e) => { const said = e.results[0][0].transcript; setMessage((current) => current ? `${current} ${said}` : said); };
    rec.onerror = () => toast.error("Ovozni aniqlab bo‘lmadi");
    rec.onend = () => { recognition.current = null; setListening(false); };
    recognition.current = rec; setListening(true); rec.start();
  }

  function speakText(text?: string) {
    if (!text || !("speechSynthesis" in window)) { toast.info("Ovoz chiqarish qo‘llanmaydi"); return; }
    if (window.speechSynthesis.speaking) { window.speechSynthesis.cancel(); return; }
    const clean = text.replace(/[#*`_~[\]()>-]/g, " ").slice(0, 1500);
    const u = new SpeechSynthesisUtterance(clean);
    const voices = window.speechSynthesis.getVoices();
    const targetRe = settings.lang === "ru" ? /ru/i : settings.lang === "en" ? /en/i : /uz|tr|ru/i;
    const preferred = voices.find((v) => targetRe.test(v.lang));
    if (preferred) u.voice = preferred;
    u.lang = preferred?.lang || (settings.lang === "ru" ? "ru-RU" : settings.lang === "en" ? "en-US" : "uz-UZ");
    window.speechSynthesis.speak(u);
  }

  async function captureScreenshot() {
    try {
      const res = await api<{ name: string; data: string }>("/api/desktop/screenshot", {});
      setAttachments((current) => [...current, { name: res.name, data: res.data }].slice(0, 6));
      toast.success("Ekran rasmi biriktirildi");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  const runPythonSnippet = useCallback(async (code: string) => {
    const res = await api<{ output: string }>("/api/desktop/run-code", { code });
    return res.output;
  }, []);

  function copyMessage(text?: string) {
    if (!text) return;
    void navigator.clipboard?.writeText(text).then(() => toast.success("Javob nusxalandi"));
  }

  async function regenerateFrom(index: number) {
    if (busy || chatId === null) return;
    let prompt = "";
    for (let i = index - 1; i >= 0; i--) {
      if (records[i]?.k === "user" && records[i]?.text) {
        prompt = records[i].text || "";
        break;
      }
    }
    if (!prompt) return;
    stickToBottom.current = true;
    try {
      await api("/api/send", { chat: chatId, text: prompt, agent: selectedAgent, files: [] });
      setBusy(true);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  function fillPrompt(text: string, pickFile = false) {
    setMessage(text);
    if (pickFile) fileInput.current?.click();
    else composerInput.current?.focus();
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setAuthBusy(true);
    try {
      await api(register ? "/api/register" : "/api/login", { name: authName, password, invite });
      setPassword(""); const me = await refresh();
      if (me.chats.length) {
        let remembered = 0;
        try { remembered = Number(localStorage.getItem(`au-active-chat-${me.user}`) || 0); } catch { /* brauzer xotirasi yopiq */ }
        openChat(me.chats.find((chat) => chat.id === remembered)?.id || me.chats[0].id, false);
      }
      toast.success(register ? "Hisob yaratildi" : "Tizimga kirdingiz");
    } catch (error) { toast.error((error as Error).message); }
    finally { setAuthBusy(false); }
  }

  async function createChat() {
    try {
      const result = await api<{ id: number }>("/api/chat/new", {});
      await refresh(); openChat(result.id);
    } catch (error) { toast.error((error as Error).message); }
  }

  async function deleteChat(id: number) {
    if (!window.confirm("Ushbu suhbat o‘chirilsinmi?")) return;
    try {
      await api("/api/chat/delete", { chat: id });
      if (chatId === id) { eventSource.current?.close(); setChatId(null); setRecords([]); }
      const me = await refresh();
      if (chatId === id && me.chats.length) openChat(me.chats[0].id, false);
      toast.success("Suhbat o‘chirildi");
    } catch (error) { toast.error((error as Error).message); }
  }

  async function addFiles(list: FileList | null) {
    if (!list) return;
    const accepted: { name: string; data: string }[] = [];
    for (const file of Array.from(list)) {
      if (file.size > MAX_FILE) { toast.error(`${file.name}: fayl 15 MB dan katta`); continue; }
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = () => reject(new Error("Faylni o‘qib bo‘lmadi"));
        reader.readAsDataURL(file);
      });
      accepted.push({ name: file.name, data });
    }
    setAttachments((current) => [...current, ...accepted].slice(0, 6));
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (busy) {
      if (chatId !== null) void api("/api/stop", { chat: chatId }).catch((e) => toast.error((e as Error).message));
      return;
    }
    const text = message.trim();
    if (!text && !attachments.length) return;
    const files = attachments;
    setMessage(""); setAttachments([]);
    stickToBottom.current = true;
    try {
      let id = chatId;
      if (id === null) {
        const created = await api<{ id: number }>("/api/chat/new", {});
        id = created.id; setChatId(id);
        await refresh();
        openChat(id);
      }
      await api("/api/send", { chat: id, text, agent: selectedAgent, files });
      setBusy(true);
      setActiveView("Suhbat");
    } catch (error) {
      setMessage(text); setAttachments(files);
      toast.error((error as Error).message);
    }
  }

  async function logout() {
    try { await api("/api/logout", {}); eventSource.current?.close(); setUser(""); setChatId(null); setRecords([]); setChats([]); }
    catch (error) { toast.error((error as Error).message); }
  }

  async function openClassic() {
    try { await api("/api/desktop/classic", {}); toast.success("Klassik oyna ochilmoqda"); }
    catch (error) { toast.error((error as Error).message); }
  }

  async function saveSettings(next: WebSettings) {
    setSettingsSaving(true);
    try {
      const saved = await api<WebSettings>("/api/settings", next);
      setSettings(saved); setTheme(saved.theme);
      toast.success("Sozlamalar saqlandi");
    } catch (error) { toast.error((error as Error).message); }
    finally { setSettingsSaving(false); }
  }

  async function toggleNetwork(enabled: boolean) {
    setNetworkBusy(true);
    try {
      const info = await api<NetworkInfo>("/api/network", { enabled });
      setNetwork(info);
      if (info.enabled) toast.success("Web ulanish yoqildi");
      else toast.info("Web ulanish o‘chirildi");
    } catch (error) { toast.error((error as Error).message); }
    finally { setNetworkBusy(false); }
  }

  async function allowNetworkFirewall() {
    setNetworkBusy(true);
    try {
      const result = await api<{ ok: boolean; message: string }>("/api/network/firewall", {});
      toast[result.ok ? "success" : "error"](result.message);
    } catch (error) { toast.error((error as Error).message); }
    finally { setNetworkBusy(false); }
  }

  useEffect(() => {
    if (!desktop || activeView !== "Sozlamalar") return;
    let alive = true;
    api<NetworkInfo>("/api/network").then((info) => { if (alive) setNetwork(info); })
      .catch(() => { if (alive) setNetwork(null); });
    return () => { alive = false; };
  }, [activeView, desktop]);

  const t = useCallback((key: string) => settings.lang === "uz" ? key : (I18N[settings.lang]?.[key] || key), [settings.lang]);
  const generatedFiles = useMemo(() => records.filter((r) => r.k === "act" && r.kind === "file"), [records]);
  const completed = records.filter((r) => r.k === "agent").length;
  const notices = useMemo(() => records.filter(isNotice), [records]);
  const unread = Math.max(0, notices.length - seenNotices);
  const openTasks = tasks.filter((task) => !task.done).length;
  const projectCount = workspace?.project ? 1 : 0;
  const metrics = [
    { label: t("Faol agentlar"), value: agents.length, icon: Layers, color: "violet", hint: "onlayn" },
    { label: t("Loyihalar"), value: projectCount, icon: FileText, color: "blue", hint: projectCount ? "faol" : "sozlanmagan" },
    { label: t("Vazifalar"), value: tasks.length, icon: BarChart3, color: "pink", hint: `${openTasks} ochiq` },
    { label: t("Fayllar"), value: generatedFiles.length, icon: Folder, color: "amber", hint: "joriy suhbat" },
  ];
  const fileHref = (name?: string) => chatId ? `/api/file?chat=${chatId}&name=${encodeURIComponent(name || "")}` : "#";
  const agentIcons = [FileText, BarChart3, Globe2, FileSpreadsheet];
  const agentTones = ["blue", "", "cyan", "amber"];

  const chatPanel = (full: boolean) => <section className={full ? "workspace panel chat-full" : "workspace panel"}>
    <div className="workspace-title"><div className="spark-badge"><Sparkles /></div><h2>{t("Agent Umimiy bilan suhbat")}</h2>{chatId && records.length > 0 && <><a className="new-chat-btn" href={`/api/chat/export?chat=${chatId}&format=docx`} download title="Word (.docx) yuklab olish"><Download size={14} /> .docx</a><a className="new-chat-btn" href={`/api/chat/export?chat=${chatId}&format=pptx`} download title="PowerPoint (.pptx) yuklab olish"><Download size={14} /> .pptx</a><a className="new-chat-btn" href={`/api/chat/export?chat=${chatId}&format=xlsx`} download title="Excel (.xlsx) yuklab olish"><Download size={14} /> .xlsx</a><a className="new-chat-btn" href={`/api/chat/export?chat=${chatId}&format=md`} download title="Markdown (.md) yuklab olish"><Download size={14} /> .md</a></>}<button className="new-chat-btn" onClick={createChat}><Plus size={15} /> {t("Yangi suhbat")}</button></div>
    {!records.length && !busy && !Object.keys(live).length ? <>
      <p className="workspace-sub">Savolingizni yozing yoki quyidagi misollardan birini tanlang:</p>
      <div className="prompt-chips">{PROMPTS.map(([label, text, Icon, tone], i) => <button type="button" key={label} onClick={() => fillPrompt(text, i === 0)}><span className={`chip-icon ${tone}`}><Icon /></span>{label}</button>)}</div>
    </> : <div className="messages" onScroll={(e) => { const box = e.currentTarget; stickToBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80; }}>
      {records.map((record, index) => record.k === "act"
        ? <div className="activity-line" key={index}>{record.agent}: {record.text}{record.kind === "file" && <><a href={fileHref(record.text)} download><Download size={12} /> Yuklab olish</a>{/\.(png|jpe?g|gif|webp|bmp)$/i.test(record.text || "") && <a className="chat-image-link" href={`${fileHref(record.text)}&inline=1`} target="_blank" rel="noreferrer"><img className="chat-image" src={`${fileHref(record.text)}&inline=1`} alt={record.text || "Rasm"} loading="lazy" /></a>}</>}</div>
        : <div className={record.k === "user" ? "message-row user-message" : "message-row"} key={index}><div className="message-avatar">{record.k === "user" ? user.slice(0, 1).toUpperCase() : <Bot size={17} />}</div><div className="message-body"><b>{record.k === "user" ? user : record.name || record.agent || "Agent"}</b><div className={record.err ? "message-bubble error" : record.k === "agent" ? "message-bubble md-bubble" : "message-bubble"}>{record.k === "agent" && !record.err ? <Markdown text={record.text || ""} onRunCode={desktop ? runPythonSnippet : undefined} /> : record.text}{record.files?.length ? <small className="attached">{record.files.map((file, i) => {
                  const shown = typeof file === "string" ? file : (file.name || file.file || "fayl");
                  const stored = typeof file === "string" ? "" : file.file;  // eski yozuvlarda diskdagi nom saqlanmagan
                  return <span key={i}>📎 {stored ? <a href={fileHref(stored)} download={shown}>{shown}</a> : shown}</span>;
                })}</small> : null}</div><div className="message-meta-row">{record.meta && <small className="message-meta">{record.meta}</small>}{record.k === "agent" && !record.err && record.text && <><button type="button" className="text-link" onClick={() => speakText(record.text)} title="Ovoz chiqarib o‘qish"><Volume2 size={13} /> Eshitish</button><button type="button" className="text-link" onClick={() => copyMessage(record.text)} title="Matnni nusxalash">📋 Nusxalash</button><button type="button" className="text-link" onClick={() => void regenerateFrom(index)} title="Boshqattan javob olish">🔄 Qayta so‘rash</button></>}</div></div></div>)}
      {Object.entries(live).map(([name, text]) => <div className="message-row" key={name}><div className="message-avatar"><Bot size={17} /></div><div className="message-body"><b>{name} <span className="typing-label">yozmoqda…</span></b><div className="message-bubble live md-bubble"><Markdown text={text} /></div></div></div>)}
      {busy && !Object.keys(live).length && <div className="typing-indicator"><span /><span /><span /> Agent javob tayyorlamoqda…</div>}
      <div ref={messagesEnd} />
    </div>}
    <form className="composer-row" onSubmit={sendMessage}><input ref={fileInput} type="file" multiple hidden accept="image/*,.pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.json,.py,.js,.html,.log" onChange={(e) => { void addFiles(e.target.files); e.currentTarget.value = ""; }} />
      <button type="button" className="round-btn" onClick={() => fileInput.current?.click()} title="Fayl biriktirish"><Paperclip /></button>
      {desktop && <button type="button" className="round-btn" onClick={() => void captureScreenshot()} title="Ekran rasmini olish (Screenshot)"><Camera /></button>}
      <div className="composer"><div className="composer-main">{attachments.length > 0 && <div className="attachment-chips">{attachments.map((file, i) => <button type="button" key={i} onClick={() => setAttachments((a) => a.filter((_, n) => n !== i))}>{file.name} <X size={12} /></button>)}</div>}<input ref={composerInput} value={message} onChange={(e) => setMessage(e.target.value)} placeholder={t("Xabaringizni yozing...")} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy) void sendMessage(); } }} /></div>
        <button type="button" className={listening ? "mic-btn on" : "mic-btn"} onClick={toggleMic} title="Ovoz bilan yozish"><Mic /></button></div>
      <button className={busy ? "send-btn stop-btn" : "send-btn"} type="submit" title={busy ? "To‘xtatish" : "Yuborish"} disabled={!busy && !message.trim() && !attachments.length}>{busy ? <Square size={16} /> : <Send size={18} />}</button>
      <button type="button" className="round-btn" onClick={() => setActiveView("Sozlamalar")} title={t("Sozlamalar")}><SlidersHorizontal /></button></form>
  </section>;
  const filteredChats = chats.filter((chat) => (chat.title || "Yangi suhbat").toLowerCase().includes(search.toLowerCase()));

  if (!authChecked) return <div className="boot-screen"><Robot /><span>Agent Umimiy ishga tushmoqda…</span><Loader2 className="spin" /></div>;

  if (!user) return <div className={`auth-screen ${theme}`}><Toaster richColors position="top-right" /><div className="auth-card panel"><Robot /><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi</div><h1>Agent Umimiy</h1><p>{register ? "Yangi hisob yarating" : "Hisobingizga kiring"}</p><form onSubmit={submitAuth}><label>Foydalanuvchi nomi<input required minLength={2} value={authName} onChange={(e) => setAuthName(e.target.value)} autoComplete="username" /></label><label>Parol<input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={register ? "new-password" : "current-password"} /></label>{register && <label>Taklif kodi<input required value={invite} onChange={(e) => setInvite(e.target.value)} /></label>}<button className="primary-btn" disabled={authBusy}>{authBusy ? <Loader2 className="spin" /> : <ShieldCheck size={17} />}{register ? "Ro‘yxatdan o‘tish" : "Kirish"}</button></form><button className="switch-auth" onClick={() => setRegister(!register)}>{register ? "Hisobim bor — kirish" : "Hisobim yo‘q — ro‘yxatdan o‘tish"}</button><small>Server egasidan taklif kodini oling.</small></div></div>;

  return <div className={`app-shell ${theme} accent-${settings.accent}`}><Toaster richColors position="top-right" />
    <aside className={`sidebar${mobileNav ? " open" : ""}${navHidden ? " hidden" : ""}`}>
      <div className="brand"><div className="brand-mark">AU</div><div><b>Agent Umimiy</b><span>AI platformasi</span></div><button className="icon-btn mobile-close" onClick={() => setMobileNav(false)}><X /></button></div>
      <nav>
        {NAV.map(([label, Icon]) => <button key={label} title={t(label)} className={activeView === label ? "nav-item selected" : "nav-item"} onClick={() => { setActiveView(label); setMobileNav(false); }}><Icon size={18} /><span>{t(label)}</span>{activeView === label && <ChevronRight size={15} />}</button>)}
      </nav>
      <div className="sidebar-section"><div className="sidebar-section-title">SO‘NGGI SUHBATLAR <button onClick={createChat} title={t("Yangi suhbat")}><Plus size={14} /></button></div>
        <div className="chat-list">{filteredChats.slice(0, 6).map((chat) => <div className={chat.id === chatId ? "chat-link active" : "chat-link"} key={chat.id}><button onClick={() => openChat(chat.id)}><MessageSquare size={13} /><span>{chat.title || t("Yangi suhbat")}</span></button><button className="delete-chat" onClick={() => void deleteChat(chat.id)} title="O‘chirish"><Trash2 size={13} /></button></div>)}</div>
      </div>
      <div className="sidebar-bottom"><div className="side-bot"><Robot /></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="icon-btn menu-btn" title="Menyu" onClick={() => { if (window.innerWidth <= 900) setMobileNav(true); else setNavHidden(!navHidden); }}><Menu /></button><div className="search"><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Qidirish (suhbat, fayl, agent)..." /><Search size={17} /></div>
        <label className="agent-select"><Bot size={16} /><select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)} aria-label="Agent tanlash">
          {agents.map((a) => <option key={a.name} value={a.name} title={a.description || undefined}>{a.name === "auto" ? t("Avtomatik agent") : a.name}</option>)}
          <option value="broadcast">⚡ Barcha agentlar (Broadcast)</option>
          <option value="pipeline">🔗 Zanjir rejimi (Pipeline)</option>
          <option value="consensus">⚖️ Konsensus (Hakam xulosasi)</option>
        </select><ChevronDown size={14} /></label>
        <div className="server-pill"><i /> {t("Server: Ulangan")}</div>
        <div className="topbar-right">
          <button className="icon-btn notification" title="Bildirishnomalar" onClick={() => { setSeenNotices(notices.length); setActiveView("Bosh sahifa"); window.setTimeout(() => noticePanel.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50); }}><Bell />{unread > 0 && <em>{unread}</em>}</button>
          <button className="icon-btn" title="Plaginlar" onClick={() => setActiveView("Plaginlar")}><LayoutGrid /></button>
          <button className="icon-btn" onClick={() => void saveSettings({ ...settings, theme: theme === "dark" ? "light" : "dark" })} title="Mavzuni almashtirish">{theme === "dark" ? <Sun /> : <Moon />}</button>
          <div className="profile-pill"><div className="avatar">{user.slice(0, 2).toUpperCase()}</div><span>{user}</span>{!desktop && <button onClick={() => void logout()} title="Chiqish"><LogOut size={15} /></button>}</div>
        </div>
      </header>
      <div className="content">
        {["Loyihalar", "Plaginlar", "Avtomatlashtirish", "Ma’lumotlar bazasi"].includes(activeView) && <section className="panel settings-page">
          <div className="panel-heading"><h2><Database /> {activeView}</h2><span className="text-link">Serverdan olingan ma’lumot</span></div>
          {workspaceError && <p className="settings-note">{workspaceError}</p>}
          {!workspace && !workspaceError && <div className="empty-state"><Loader2 className="spin" /> Ma’lumot yuklanmoqda…</div>}
          {workspace && activeView === "Loyihalar" && <>
            <div className="agent-row"><div className="file-icon blue"><Folder /></div><div className="row-copy"><b>{workspace.project || "Loyiha tanlanmagan"}</b><span>Server konfiguratsiyasidagi faol loyiha · RAG indeksda: {workspace.rag?.indexed ?? 0} ta hujjat</span></div><span className="online"><i /> {workspace.project ? "Ulangan" : "Sozlanmagan"}</span></div>
            {desktop && <div className="classic-box">
              <div className="row-copy"><b>Loyiha papkasi va SQLite FTS5 RAG qidiruv</b><span>Loyihadagi PDF, Word, Excel, Markdown va Python fayllarni indeksatsiya qilib, bir zumda qidiring.</span></div>
              <div className="settings-grid">
                <input value={projectInput} onChange={(e) => setProjectInput(e.target.value)} placeholder="Masalan: D:\llm yoki D:\agent (bo‘sh qolsa joriy loyiha)" />
                <button className="secondary-btn" onClick={() => void api<{ indexed: number; project: string }>("/api/desktop/rag", { action: "index", project: projectInput.trim() }).then((res) => { toast.success(`${res.indexed} ta fayl indekslandi (${res.project})`); return api<Workspace>("/api/workspace").then(setWorkspace); }).catch((e) => toast.error((e as Error).message))}>Hujjatlarni indekslash (FTS5)</button>
              </div>
              <div className="settings-grid">
                <input value={ragQuery} onChange={(e) => setRagQuery(e.target.value)} placeholder="Hujjatlar ichidan tezkor qidirish..." />
                <button className="secondary-btn" onClick={() => void api<{ results: RagHit[] }>("/api/desktop/rag", { action: "search", query: ragQuery }).then((res) => setRagResults(res.results || [])).catch((e) => toast.error((e as Error).message))}>Qidirish</button>
              </div>
              {ragResults.map((hit, i) => <div className="agent-row" key={i}><div className="file-icon cyan"><FileText /></div><div className="row-copy"><b>{hit.path}</b><span>{hit.snippet}</span></div></div>)}
            </div>}
            <p className="settings-note">Loyiha katalogi va fayllari tarmoq xodimlariga masofadan ochilmaydi.</p>
          </>}
          {workspace && activeView === "Plaginlar" && <>
            <div className="panel-heading"><b>MCP ulanishlari</b><span className="text-link">{workspace.plugins.length} ta</span></div>
            {workspace.plugins.length ? workspace.plugins.map((plugin) => <div className="agent-row" key={plugin.name}><div className="file-icon cyan"><Zap /></div><div className="row-copy"><b>{plugin.name}</b><span>{plugin.transport} · maxfiy sozlamalar yashirilgan</span></div><span className={plugin.enabled ? "online" : "text-link"}>{plugin.enabled ? "Yoqilgan" : "O‘chirilgan"}</span></div>) : <div className="empty-state">Hozircha MCP plaginlari sozlanmagan.</div>}
            <div className="panel-heading"><b>Ko‘nikmalar (Skills)</b><span className="text-link">{workspace.skills.length} ta</span></div>
            {workspace.skills.map((skill) => <div className="agent-row" key={skill.name}><div className="file-icon blue"><Sparkles /></div><div className="row-copy"><b>{skill.name}</b><span>{skill.description || skill.source}</span></div></div>)}
            <p className="settings-note">Ulanishlarni qo‘shish, tahrirlash va qayta ulash desktop sozlamalarida bajariladi.</p>
          </>}
          {workspace && activeView === "Avtomatlashtirish" && <>
            {desktop ? <>
              <div className="classic-box">
                <div className="row-copy"><b>Yangi avtomat vazifa (Jadval / Trigger)</b><span>Belgilangan vaqt oralig‘ida yoki «Bajarish» tugmasi bilan agent topshiriqni fonda bajaradi.</span></div>
                <div className="settings-grid">
                  <input value={autoTitle} onChange={(e) => setAutoTitle(e.target.value)} placeholder="Vazifa nomi (masalan: Kunlik tahlil)" />
                  <input value={autoPrompt} onChange={(e) => setAutoPrompt(e.target.value)} placeholder="Agentga beriladigan topshiriq matni..." />
                  <input type="number" min={5} max={10080} value={autoInterval} onChange={(e) => setAutoInterval(Number(e.target.value) || 60)} title="Takrorlanish vaqti (daqiqa)" />
                  <button className="primary-btn" onClick={() => void api<{ jobs: AutoJob[] }>("/api/automation", { action: "add", title: autoTitle, prompt: autoPrompt, agent: selectedAgent, interval_minutes: autoInterval }).then((res) => { setWorkspace({ ...workspace, automation: { ...workspace.automation, jobs: res.jobs } }); setAutoTitle(""); setAutoPrompt(""); toast.success("Avtomat vazifa qo‘shildi"); }).catch((e) => toast.error((e as Error).message))}><Plus size={15} /> Qo‘shish</button>
                </div>
              </div>
              {(workspace.automation.jobs || []).length ? (workspace.automation.jobs || []).map((job) => <div className="agent-row" key={job.id}>
                <div className="file-icon violet"><Clock3 /></div>
                <div className="row-copy"><b>{job.title} ({job.interval_minutes} daq · {job.agent})</b><span>{job.prompt}{job.last_result ? ` — Natija: ${job.last_result.slice(0, 140)}` : ""}</span></div>
                <span className="online"><i /> {job.last_status}</span>
                <button className="secondary-btn" onClick={() => void api<{ jobs: AutoJob[] }>("/api/automation", { action: "run", id: job.id }).then((res) => { setWorkspace({ ...workspace, automation: { ...workspace.automation, jobs: res.jobs } }); toast.success("Vazifa fonda ishga tushdi"); }).catch((e) => toast.error((e as Error).message))}>Bajarish</button>
                <button className="secondary-btn danger-btn" onClick={() => void api<{ jobs: AutoJob[] }>("/api/automation", { action: "delete", id: job.id }).then((res) => setWorkspace({ ...workspace, automation: { ...workspace.automation, jobs: res.jobs } })).catch((e) => toast.error((e as Error).message))}><Trash2 size={14} /></button>
              </div>) : <div className="empty-state"><Clock3 /><b>Hozircha avtomat vazifa yo‘q</b><span>Yuqoridagi shakldan birinchi jadval vazifasini qo‘shing.</span></div>}
            </> : <div className="empty-state"><Clock3 /><b>Avtomatlashtirish faqat desktop oynasida boshqariladi</b><span>{workspace.automation.reason}</span></div>}
          </>}
          {workspace && activeView === "Ma’lumotlar bazasi" && <>
            <div className="stats-grid">
              <article className="stat-card violet"><div className="stat-copy"><span>Ma’lumotlar ombori</span><b>{workspace.database.engine}</b></div></article>
              <article className="stat-card blue"><div className="stat-copy"><span>Holati</span><b>{workspace.database.status === "connected" ? "Ulangan" : workspace.database.status}</b></div></article>
              <article className="stat-card pink"><div className="stat-copy"><span>Foydalanuvchilar</span><b>{workspace.database.users}</b></div></article>
              <article className="stat-card amber"><div className="stat-copy"><span>Suhbatlar</span><b>{workspace.database.chats}</b></div></article>
            </div>
            {desktop && <div className="classic-box">
              <div className="row-copy"><b>SQLite ma’lumotlar bazasi zaxira nusxasi (Backup)</b><span>Barcha suhbatlar, hisoblar va tarixni bitta .sqlite3 fayl sifatida yuklab oling.</span></div>
              <a className="primary-btn" href="/api/desktop/backup" download><Download size={15} /> Bazani zaxiralash (.sqlite3)</a>
            </div>}
            <p className="settings-note">Ma’lumotlar bazasi holati ko‘rsatiladi. SQL buyruqlari va o‘chirish amallari xavfsizlik uchun web orqali ochilmagan.</p>
          </>}
        </section>}
        {activeView === "Sozlamalar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Settings /> {t("Sozlamalar")}</h2><span className="text-link">Xavfsiz web sozlamalari</span></div>
          <div className="settings-grid">
            <label>Interfeys tili<select value={settings.lang} disabled={settingsSaving} onChange={(e) => void saveSettings({ ...settings, lang: e.target.value as WebSettings["lang"] })}><option value="uz">O‘zbekcha</option><option value="ru">Русский</option><option value="en">English</option></select></label>
            <label>Ko‘rinish<select value={settings.theme} disabled={settingsSaving} onChange={(e) => void saveSettings({ ...settings, theme: e.target.value as WebSettings["theme"] })}><option value="dark">Qorong‘i</option><option value="light">Yorug‘</option></select></label>
            <label>Asosiy rang<select value={settings.accent} disabled={settingsSaving} onChange={(e) => void saveSettings({ ...settings, accent: e.target.value as WebSettings["accent"] })}><option value="violet">Neon binafsha</option><option value="blue">Ko‘k</option><option value="cyan">Moviy</option><option value="emerald">Zumrad</option></select></label>
          </div>
          <p className="settings-note"><ShieldCheck size={15} /> API kalitlari va maxfiy ma’lumotlar internet orqali ko‘rsatilmaydi yoki o‘zgartirilmaydi.</p>
          {desktop && <div className="classic-box network-settings">
            <div className="row-copy"><b>Xodimlar uchun web ulanish</b><span>{network?.enabled ? "Yoqilgan — xodimlar quyidagi manzillardan ulanadi." : "O‘chiq — yoqsangiz, manzil va ro‘yxatdan o‘tish kodi shu yerda chiqadi."}</span></div>
            {network?.error && <p className="settings-note">Server xatosi: {network.error}</p>}
            {network?.enabled && <>
              <div className="network-detail"><b>Ulanish manzili</b>{network.urls.length ? network.urls.map((url) => <code key={url}>{url}</code>) : <span>Kompyuterning tarmoq manzili topilmadi.</span>}</div>
              <div className="network-detail"><b>Ro‘yxatdan o‘tish taklif kodi</b><code>{network.invite}</code></div>
              <p className="settings-note">Xodimlar shu Wi-Fi/tarmoqqa ulanib, manzilni brauzerda ochadi. Windows so‘rasa, devor ruxsatini admin tasdiqlaydi.</p>
              <button className="secondary-btn" disabled={networkBusy} onClick={() => void allowNetworkFirewall()}>Windows devorida portga ruxsat</button>
            </>}
            <button className="secondary-btn" disabled={networkBusy} onClick={() => void toggleNetwork(!network?.enabled)}>{networkBusy ? "Kutilmoqda…" : network?.enabled ? "Web ulanishni o‘chirish" : "Web ulanishni yoqish"}</button>
          </div>}
          {desktop && <div className="classic-box employee-settings">
            <div className="row-copy"><b>Xodimlar</b><span>Hisoblarni ko‘ring, kirishini vaqtincha to‘xtating yoki hisobni o‘chiring. O‘chirilgan xodim sessiyasi darhol yopiladi.</span></div>
            {!employees.length ? <p className="settings-note">Hozircha ro‘yxatdan o‘tgan xodim yo‘q.</p> : employees.map((employee) => <div className="employee-row" key={employee.id}>
              <div className="row-copy"><b>{employee.name}</b><span>{employee.chats} ta suhbat · {employee.enabled ? "Faol" : "Kirish yopiq"}</span></div>
              <button className="secondary-btn" disabled={employeeBusy !== null} onClick={() => void manageEmployee(employee, employee.enabled ? "disable" : "enable")}>{employeeBusy === employee.id ? "Kutilmoqda…" : employee.enabled ? "Kirishni to‘xtatish" : "Kirishni yoqish"}</button>
              <button className="secondary-btn danger-btn" disabled={employeeBusy !== null} onClick={() => void manageEmployee(employee, "delete")} title="Hisob va suhbatlarni o‘chirish"><Trash2 size={14} /></button>
            </div>)}
            <button className="secondary-btn" disabled={employeeBusy !== null} onClick={() => void refreshEmployees().catch((error) => toast.error((error as Error).message))}>Ro‘yxatni yangilash</button>
          </div>}
          {desktop && <div className="classic-box">
            <div className="row-copy"><b>🧠 Doimiy AI Xotirasi (Memory)</b><span>Barcha suhbatlarda agentlar eslab qoladigan shaxsiy qoidalar va faktlar ({workspace?.memory?.length ?? 0} ta).</span></div>
            <div className="settings-grid">
              <input value={memoryFact} onChange={(e) => setMemoryFact(e.target.value)} placeholder="Masalan: Javoblarni doim qisqa va aniq o‘zbek tilida yoz" />
              <button className="primary-btn" onClick={() => void api<{ memory: MemoryItem[]; message: string }>("/api/desktop/memory", { action: "add", fact: memoryFact }).then((res) => { if (workspace) setWorkspace({ ...workspace, memory: res.memory }); setMemoryFact(""); toast.success(res.message || "Xotiraga saqlandi"); }).catch((e) => toast.error((e as Error).message))}><Plus size={15} /> Xotiraga qo‘shish</button>
            </div>
            {(workspace?.memory || []).map((m) => <div className="employee-row" key={m.id}>
              <div className="row-copy"><b>{m.fact}</b><span>ID: {m.id}</span></div>
              <button className="secondary-btn danger-btn" onClick={() => void api<{ memory: MemoryItem[] }>("/api/desktop/memory", { action: "delete", id: m.id }).then((res) => { if (workspace) setWorkspace({ ...workspace, memory: res.memory }); toast.info("Xotiradan o‘chirildi"); }).catch((e) => toast.error((e as Error).message))} title="O‘chirish"><Trash2 size={14} /></button>
            </div>)}
          </div>}
          {desktop && <div className="classic-box">
            <div className="row-copy"><b>Telegram Bot ko‘prigi (Masofadan boshqarish)</b><span>@BotFather dan olingan tokenni kiriting — telefoningizdan Telegram orqali yozib Agent Umimiyni ishlating.</span></div>
            <div className="settings-grid">
              <input type="password" value={tgToken} onChange={(e) => setTgToken(e.target.value)} placeholder="Bot tokeni (123456:ABC-DEF...)" />
              <input value={tgUser} onChange={(e) => setTgUser(e.target.value)} placeholder="Ruxsat berilgan @username (ixtiyoriy)" />
              <button className="secondary-btn" onClick={() => void api<{ telegram: TelegramInfo }>("/api/desktop/telegram", { token: tgToken, allowed_username: tgUser }).then((res) => { if (res.telegram.status === "ulangan") toast.success(`Telegram ulandi: @${res.telegram.bot_username}`); else if (res.telegram.error) toast.error(res.telegram.error); else toast.info("Telegram bot o‘chirildi"); }).catch((e) => toast.error((e as Error).message))}>Telegram botni saqlash</button>
            </div>
          </div>}
          {desktop && <div className="classic-box"><div className="row-copy"><b>Klassik oyna</b><span>Agent qo‘shish, API kalitlari, loyiha papkasi va plaginlarni sozlash.</span></div><button className="secondary-btn" onClick={() => void openClassic()}>Klassik oynani ochish</button></div>}
          {settingsSaving && <span className="online"><i /> Saqlanmoqda…</span>}
        </section>}
        {activeView === "Agentlar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Bot /> Agentlar</h2><span className="text-link">{agents.length} ta serverda sozlangan</span></div>
          {agents.map((agent) => <div className="agent-row" key={agent.name}><div className="file-icon cyan"><Bot /></div><div className="row-copy"><b>{agent.name === "auto" ? "Avtomatik tanlash" : agent.name}</b><span>{agent.model || "Model server konfiguratsiyasidan olinadi"}{agent.description ? ` · ${agent.description}` : ""}</span></div><span className="online"><i /> Mavjud</span><button className="secondary-btn" onClick={() => { setSelectedAgent(agent.name); setActiveView("Suhbat"); }}>Suhbat boshlash</button>{desktop && agent.name !== "auto" && <button className="secondary-btn danger-btn" onClick={() => void api<{ agents: Agent[] }>("/api/desktop/agents", { action: "delete", name: agent.name }).then((res) => { setAgents(res.agents); toast.success("Agent o‘chirildi"); }).catch((e) => toast.error((e as Error).message))} title="O‘chirish"><Trash2 size={14} /></button>}</div>)}
          {desktop && <div className="classic-box">
            <div className="row-copy"><b>Yangi AI Agent qo‘shish (To‘g‘ridan-to‘g‘ri)</b><span>Klassik oynaga kirmasdan shu yerning o‘zida yangi provayder yoki model qo‘shing.</span></div>
            <div className="settings-grid">
              <input value={newAgentName} onChange={(e) => setNewAgentName(e.target.value)} placeholder="Nomi (masalan: groq-llama)" />
              <select value={newAgentType} onChange={(e) => setNewAgentType(e.target.value)}><option value="openai">OpenAI / FreeLLM / OpenRouter</option><option value="ollama">Ollama (lokal)</option><option value="anthropic">Anthropic Claude</option><option value="gemini">Google Gemini</option></select>
              <input value={newAgentModel} onChange={(e) => setNewAgentModel(e.target.value)} placeholder="Model (masalan: codestral, qwen2.5:0.5b)" />
              <input value={newAgentUrl} onChange={(e) => setNewAgentUrl(e.target.value)} placeholder="Base URL (masalan: http://127.0.0.1:3001/v1)" />
              <input type="password" value={newAgentKey} onChange={(e) => setNewAgentKey(e.target.value)} placeholder="API kalit (bo‘sh qolishi mumkin)" />
              <input value={newAgentDesc} onChange={(e) => setNewAgentDesc(e.target.value)} placeholder="Tavsif (ixtiyoriy)" />
            </div>
            <button className="primary-btn" onClick={() => void api<{ agents: Agent[] }>("/api/desktop/agents", { action: "add", name: newAgentName, type: newAgentType, model: newAgentModel, base_url: newAgentUrl, api_key: newAgentKey, description: newAgentDesc }).then((res) => { setAgents(res.agents); setNewAgentName(""); setNewAgentModel(""); setNewAgentKey(""); toast.success("Agent saqlandi"); }).catch((e) => toast.error((e as Error).message))}><Plus size={15} /> Agentni saqlash</button>
          </div>}
          <p className="settings-note">Kengaytirilgan CLI va MCP sozlamalari uchun klassik oynadan ham foydalanish mumkin.{desktop && <button className="secondary-btn" onClick={() => void openClassic()}>Klassik oynani ochish</button>}</p>
        </section>}
        {activeView === "Fayllar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Folder /> Fayllar</h2><span className="text-link">Tanlangan suhbat</span></div>
          {generatedFiles.length ? generatedFiles.slice().reverse().map((file, i) => <div className="file-row" key={i}><div className="file-icon blue"><FileText /></div><b>{file.text}</b><a href={chatId ? `/api/file?chat=${chatId}&name=${encodeURIComponent(file.text || "")}` : "#"} download><Download size={14} /> Yuklab olish</a></div>) : <div className="empty-state"><FileText /><span>Agent yaratgan fayllar hozircha yo‘q. Chatda fayl yaratishni so‘rang.</span></div>}
        </section>}
        {activeView === "Hisobotlar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Activity /> {t("Hisobotlar")}</h2><span className="text-link">Jonli analitika va agentlar tezligi</span></div>
          <div className="stats-grid">
            <article className="stat-card violet"><div className="stat-icon"><Bot /></div><div className="stat-copy"><span>{t("Agentlar")}</span><b>{agents.length}</b></div></article>
            <article className="stat-card blue"><div className="stat-icon"><MessageSquare /></div><div className="stat-copy"><span>Suhbatlar</span><b>{chats.length}</b></div></article>
            <article className="stat-card pink"><div className="stat-icon"><Activity /></div><div className="stat-copy"><span>Jami javoblar</span><b>{workspace?.analytics?.agent_messages ?? completed}</b></div></article>
            <article className="stat-card amber"><div className="stat-icon"><Folder /></div><div className="stat-copy"><span>Yaratilgan fayllar</span><b>{workspace?.analytics?.files_created ?? generatedFiles.length}</b></div></article>
          </div>
          <div className="panel-heading"><b>Agentlar javob tezligi va faolligi</b><span className="text-link">{workspace?.analytics?.by_agent?.length ?? 0} ta agent</span></div>
          {(workspace?.analytics?.by_agent || []).length ? (workspace?.analytics?.by_agent || []).map((stat) => <div className="agent-row" key={stat.agent}>
            <div className="file-icon cyan"><Zap /></div>
            <div className="row-copy"><b>{stat.agent}</b><span>So‘rovlar: {stat.calls} ta · Xatolar: {stat.errors} ta</span></div>
            <span className="online"><i /> O‘rtacha: {stat.avg_seconds ? `${stat.avg_seconds} s` : "—"}</span>
          </div>) : <div className="empty-state"><Activity /><span>Agentlar javob bergandan so‘ng ularning tezlik statistikasi shu yerda chiqadi.</span></div>}
          {desktop && workspace?.system && <>
            <div className="panel-heading"><b>🖥 Tizim va Lokal AI Serverlar Salomatligi</b><span className="text-link">Python {workspace.system.python}</span></div>
            <div className="stats-grid">
              <article className="stat-card violet"><div className="stat-copy"><span>CPU Oqimlari</span><b>{workspace.system.cpu_cores} ta</b></div></article>
              <article className="stat-card blue"><div className="stat-copy"><span>Bo‘sh Disk Joyi</span><b>{workspace.system.disk_free_gb} GB</b></div></article>
              <article className="stat-card pink"><div className="stat-copy"><span>Ollama (11434)</span><b>{workspace.system.ollama_online ? "Onlayn ⚡" : "O‘chiq"}</b></div></article>
              <article className="stat-card amber"><div className="stat-copy"><span>FreeLLM (3001)</span><b>{workspace.system.freellm_online ? "Onlayn ⚡" : "O‘chiq"}</b></div></article>
            </div>
          </>}
        </section>}
        {activeView === "Suhbat" && chatPanel(true)}
        {activeView === "Bosh sahifa" && <div className="dash">
          <div className="dash-main">
            <section className="hero panel">
              <svg className="hero-waves" viewBox="0 0 900 180" preserveAspectRatio="none" aria-hidden="true"><path d="M0 150 C150 90 260 170 420 120 S700 60 900 110" /><path d="M0 165 C180 120 300 185 470 140 S730 90 900 135" /><path d="M0 135 C120 70 300 150 450 95 S720 40 900 85" /></svg>
              <div className="hero-mascot"><Robot /></div>
              <div className="hero-copy"><h1>Agent Umimiy</h1><p>Sizning ko‘p funksiyali AI yordamchingiz</p></div>
              <div className="hero-badge" aria-hidden="true"><b>AU</b></div>
              <ul className="hero-tags"><li><Check /> Hujjatlar bilan ishlash (Word, Excel, PDF)</li><li><Check /> Ma’lumotlarni tahlil va hisobot</li><li><Check /> Veb-ma’lumotlarni olish (Web scraping)</li><li><Check /> Vazifalarni avtomatlashtirish</li></ul>
            </section>
            <section className="stats-grid">{metrics.map(({ label, value, icon: Icon, color, hint }) => <article className={`stat-card ${color}`} key={label}><div className="stat-icon"><Icon /></div><div className="stat-copy"><span>{label}</span><b>{value}</b></div><small>{hint}</small></article>)}</section>
            <section className="columns">
              <article className="panel list-panel"><div className="panel-heading"><h2><Layers /> Agentlar</h2><button className="text-link" onClick={() => setActiveView("Agentlar")}>Barchasi →</button></div>{agents.slice(0, 4).map((agent, i) => { const Icon = agentIcons[i % 4]; return <div className="agent-row" key={agent.name}><div className={`file-icon ${agentTones[i % 4]}`}><Icon /></div><div className="row-copy"><b>{agent.name === "auto" ? "Avtomatik tanlash" : agent.name}</b><span>{agent.model || "Konfiguratsiyadagi AI agent"}</span></div><span className="online"><i /> Onlayn</span></div>; })}{!agents.length && <div className="empty-state"><Bot /><span>Serverda agent sozlanmagan</span></div>}</article>
              <article className="panel list-panel"><div className="panel-heading"><h2>So‘nggi fayllar</h2><button className="text-link" onClick={() => setActiveView("Fayllar")}>Barchasi →</button></div>{generatedFiles.length ? generatedFiles.slice(-4).reverse().map((file, i) => <div className="file-row" key={i}><div className={`file-icon ${fileTone(file.text)}`}>{fileTone(file.text) === "excel" ? <FileSpreadsheet /> : <FileText />}</div><b>{file.text}</b><a href={fileHref(file.text)} download title="Yuklab olish"><Download size={14} /></a></div>) : <div className="empty-state"><FileText /><span>Agent yaratgan fayllar shu yerda ko‘rinadi</span></div>}</article>
              <article className="panel list-panel"><div className="panel-heading"><h2>So‘nggi loyihalar</h2><button className="text-link" onClick={() => setActiveView("Loyihalar")}>Barchasi →</button></div>{workspace?.project && <div className="file-row"><div className="file-icon folder"><Folder /></div><div className="row-copy"><b>{workspace.project}</b><span>Faol loyiha</span></div></div>}{chats.slice(0, workspace?.project ? 2 : 3).map((chat) => <button className="file-row row-btn" key={chat.id} onClick={() => openChat(chat.id)}><div className="file-icon folder"><Folder /></div><div className="row-copy"><b>{chat.title || "Yangi suhbat"}</b><span>Suhbat</span></div></button>)}{!workspace?.project && !chats.length && <div className="empty-state"><Folder /><span>Hozircha loyiha yoki suhbat yo‘q</span></div>}</article>
            </section>
            {chatPanel(false)}
          </div>
          <aside className="dash-rail">
            <article className="panel rail-panel"><div className="panel-heading"><h2><Zap /> Tezkor amallar</h2></div><div className="quick-grid">
              <button onClick={() => fillPrompt("Word hujjat tayyorlab ber: ")}><span className="chip-icon word"><FileText /></span>Word yaratish</button>
              <button onClick={() => fillPrompt("Excel jadval tayyorlab ber: ")}><span className="chip-icon excel"><FileSpreadsheet /></span>Excel jadval</button>
              <button onClick={() => fillPrompt("Biriktirilgan PDF faylni tahlil qilib ber", true)}><span className="chip-icon pdf"><FileText /></span>PDF tahlil</button>
              <button onClick={() => fillPrompt("Internetdan shu mavzu bo‘yicha ma’lumot top: ")}><span className="chip-icon cyan"><Globe2 /></span>Veb-qidiruv</button>
            </div></article>
            <article className="panel rail-panel"><div className="panel-heading"><h2><CalendarClock /> Rejalashtirilgan vazifalar</h2></div>
              {tasks.map((task) => <div className={task.done ? "task-row done" : "task-row"} key={task.id}><label><input type="checkbox" checked={task.done} onChange={() => saveTasks(tasks.map((t) => t.id === task.id ? { ...t, done: !t.done } : t))} /><span className="task-box"><Check /></span><span className="row-copy"><b>{task.text}</b><span>{formatWhen(task.when)}</span></span></label><button onClick={() => saveTasks(tasks.filter((t) => t.id !== task.id))} title="O‘chirish"><X size={13} /></button></div>)}
              {!tasks.length && <p className="rail-note">Hozircha vazifa yo‘q. Quyida birinchisini qo‘shing.</p>}
              <form className="task-form" onSubmit={addTask}><input value={taskText} onChange={(e) => setTaskText(e.target.value)} maxLength={120} placeholder="Yangi vazifa..." aria-label="Yangi vazifa" /><input type="datetime-local" value={taskWhen} onChange={(e) => setTaskWhen(e.target.value)} aria-label="Vaqti" /><button disabled={!taskText.trim()} title="Qo‘shish"><Plus size={15} /></button></form>
              <p className="rail-note">Eslatma ro‘yxati shu brauzerda saqlanadi; vazifalar avtomatik ishga tushmaydi.</p>
            </article>
            <article className="panel rail-panel" ref={noticePanel}><div className="panel-heading"><h2><Bell /> Bildirishnomalar</h2>{unread > 0 && <em className="count-badge">{unread}</em>}</div>
              {notices.slice(-3).reverse().map((item, i) => { const file = item.k === "act"; return <div className="notice-row" key={i}><div className={`notice-icon ${item.err ? "err" : file ? "info" : "ok"}`}>{item.err ? <TriangleAlert /> : file ? <FileText /> : <CheckCircle2 />}</div><div className="row-copy"><b>{item.err ? "Xato yuz berdi" : file ? "Yangi fayl yaratildi" : "Javob tayyorlandi"}</b><span>{file ? item.text : [item.name || item.agent, item.meta].filter(Boolean).join(" · ")}</span></div></div>; })}
              {!notices.length && <p className="rail-note">Joriy suhbatda hali yangilik yo‘q.</p>}
            </article>
          </aside>
        </div>}
      </div>
    </main>
    {approval && <div className="approval-backdrop">
      <section className="approval-dialog panel" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <div className="approval-heading"><ShieldCheck /><div><h2 id="approval-title">Amalga ruxsat kerak</h2><span>{approval.agent} · {approval.title}</span></div></div>
        <pre>{approval.detail}</pre>
        <div className="approval-actions">
          <button className="secondary-btn" disabled={approvalBusy} onClick={() => void decideApproval("no")}>Rad etish</button>
          <button className="secondary-btn" disabled={approvalBusy} onClick={() => void decideApproval("always")}>Bu ish davomida doim</button>
          <button className="primary-btn" disabled={approvalBusy} onClick={() => void decideApproval("yes")}>Ruxsat berish</button>
        </div>
      </section>
    </div>}
  </div>;
}

export default App;
