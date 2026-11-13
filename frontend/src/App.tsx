import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity, BarChart3, Bell, Bot, Boxes, CalendarClock, Check, CheckCircle2, ChevronDown, ChevronRight,
  Clock3, Database, Download, FileSpreadsheet, FileText, Folder, FolderKanban, Globe2, Home, Layers,
  LayoutGrid, Loader2, LogOut, Menu, MessageSquare, Mic, Moon, Paperclip, Plus, Puzzle, Search, Send,
  Settings, ShieldCheck, SlidersHorizontal, Sparkles, Square, Sun, Trash2, TriangleAlert, X, Zap,
} from "lucide-react";
import { Toaster, toast } from "sonner";

type Agent = { name: string; model?: string };
type Chat = { id: number; title?: string };
type Attached = string | { name?: string; file?: string };  // eski yozuvlar oddiy matn, yangilari diskdagi nom bilan
type RecordItem = { k: string; text?: string; name?: string; agent?: string; meta?: string; err?: boolean; files?: Attached[]; kind?: string };
type LiveState = Record<string, string>;
type WebSettings = { lang: "uz" | "ru" | "en"; theme: "dark" | "light"; accent: "violet" | "blue" | "cyan" | "emerald" };
type NetworkInfo = { enabled: boolean; urls: string[]; port: number; invite: string; error: string };
type Employee = { id: number; name: string; enabled: boolean; chats: number };
type ApiError = Error & { code?: number };
type Workspace = { project: string; plugins: { name: string; transport: string; enabled: boolean }[]; skills: { name: string; description: string; source: string }[]; automation: { available: boolean; reason: string }; database: { engine: string; status: string; users: number; chats: number } };
type Task = { id: number; text: string; when: string; done: boolean };
type Approval = { id: string; agent: string; kind: string; title: string; detail: string };
type SpeechRec = { lang: string; interimResults: boolean; start: () => void; stop: () => void; onresult: ((e: { results: { 0: { transcript: string } }[] }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null };
const MAX_FILE = 15 * 1024 * 1024;
const NAV: [string, typeof Home][] = [["Bosh sahifa", Home], ["Suhbat", MessageSquare], ["Agentlar", Bot], ["Fayllar", FileText], ["Loyihalar", FolderKanban], ["Plaginlar", Puzzle], ["Avtomatlashtirish", Boxes], ["Hisobotlar", BarChart3], ["Ma’lumotlar bazasi", Database], ["Sozlamalar", Settings]];
const WORKSPACE_VIEWS = ["Bosh sahifa", "Loyihalar", "Plaginlar", "Avtomatlashtirish", "Ma’lumotlar bazasi"];
const PROMPTS: [string, string, typeof Home, string][] = [
  ["Excel ma’lumotni tahlil qil", "Biriktirilgan Excel faylni tahlil qilib ber", FileSpreadsheet, "excel"],
  ["Word hujjat tayyorla", "Word hujjat tayyorlab ber: ", FileText, "word"],
  ["Vebdan ma’lumot top", "Internetdan shu mavzu bo‘yicha ma’lumot top: ", Globe2, "cyan"],
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
  const recognition = useRef<SpeechRec | null>(null);
  const noticePanel = useRef<HTMLElement>(null);
  const eventSource = useRef<EventSource | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const composerInput = useRef<HTMLInputElement>(null);

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
    const box = messagesEnd.current?.parentElement;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
  }, [records, live]);
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
    rec.lang = "uz-UZ"; rec.interimResults = false;
    rec.onresult = (e) => { const said = e.results[0][0].transcript; setMessage((current) => current ? `${current} ${said}` : said); };
    rec.onerror = () => toast.error("Ovozni aniqlab bo‘lmadi");
    rec.onend = () => { recognition.current = null; setListening(false); };
    recognition.current = rec; setListening(true); rec.start();
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

  const generatedFiles = useMemo(() => records.filter((r) => r.k === "act" && r.kind === "file"), [records]);
  const completed = records.filter((r) => r.k === "agent").length;
  const notices = useMemo(() => records.filter(isNotice), [records]);
  const unread = Math.max(0, notices.length - seenNotices);
  const openTasks = tasks.filter((task) => !task.done).length;
  const projectCount = workspace?.project ? 1 : 0;
  const metrics = [
    { label: "Faol agentlar", value: agents.length, icon: Layers, color: "violet", hint: "onlayn" },
    { label: "Loyihalar", value: projectCount, icon: FileText, color: "blue", hint: projectCount ? "faol" : "sozlanmagan" },
    { label: "Vazifalar", value: tasks.length, icon: BarChart3, color: "pink", hint: `${openTasks} ochiq` },
    { label: "Fayllar", value: generatedFiles.length, icon: Folder, color: "amber", hint: "joriy suhbat" },
  ];
  const fileHref = (name?: string) => chatId ? `/api/file?chat=${chatId}&name=${encodeURIComponent(name || "")}` : "#";
  const agentIcons = [FileText, BarChart3, Globe2, FileSpreadsheet];
  const agentTones = ["blue", "", "cyan", "amber"];

  const chatPanel = (full: boolean) => <section className={full ? "workspace panel chat-full" : "workspace panel"}>
    <div className="workspace-title"><div className="spark-badge"><Sparkles /></div><h2>Agent Umimiy bilan suhbat</h2><button className="new-chat-btn" onClick={createChat}><Plus size={15} /> Yangi suhbat</button></div>
    {!records.length && !busy && !Object.keys(live).length ? <>
      <p className="workspace-sub">Savolingizni yozing yoki quyidagi misollardan birini tanlang:</p>
      <div className="prompt-chips">{PROMPTS.map(([label, text, Icon, tone], i) => <button type="button" key={label} onClick={() => fillPrompt(text, i === 0)}><span className={`chip-icon ${tone}`}><Icon /></span>{label}</button>)}</div>
    </> : <div className="messages">
      {records.map((record, index) => record.k === "act"
        ? <div className="activity-line" key={index}>{record.agent}: {record.text}{record.kind === "file" && <a href={fileHref(record.text)} download><Download size={12} /> Yuklab olish</a>}</div>
        : <div className={record.k === "user" ? "message-row user-message" : "message-row"} key={index}><div className="message-avatar">{record.k === "user" ? user.slice(0, 1).toUpperCase() : <Bot size={17} />}</div><div className="message-body"><b>{record.k === "user" ? user : record.name || record.agent || "Agent"}</b><div className={record.err ? "message-bubble error" : "message-bubble"}>{record.text}{record.files?.length ? <small className="attached">{record.files.map((file, i) => {
                  const shown = typeof file === "string" ? file : (file.name || file.file || "fayl");
                  const stored = typeof file === "string" ? "" : file.file;  // eski yozuvlarda diskdagi nom saqlanmagan
                  return <span key={i}>📎 {stored ? <a href={fileHref(stored)} download={shown}>{shown}</a> : shown}</span>;
                })}</small> : null}</div>{record.meta && <small className="message-meta">{record.meta}</small>}</div></div>)}
      {Object.entries(live).map(([name, text]) => <div className="message-row" key={name}><div className="message-avatar"><Bot size={17} /></div><div className="message-body"><b>{name} <span className="typing-label">yozmoqda…</span></b><div className="message-bubble live">{text}</div></div></div>)}
      {busy && !Object.keys(live).length && <div className="typing-indicator"><span /><span /><span /> Agent javob tayyorlamoqda…</div>}
      <div ref={messagesEnd} />
    </div>}
    <form className="composer-row" onSubmit={sendMessage}><input ref={fileInput} type="file" multiple hidden accept="image/*,.pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.json,.py,.js,.html,.log" onChange={(e) => { void addFiles(e.target.files); e.currentTarget.value = ""; }} />
      <button type="button" className="round-btn" onClick={() => fileInput.current?.click()} title="Fayl biriktirish"><Paperclip /></button>
      <div className="composer"><div className="composer-main">{attachments.length > 0 && <div className="attachment-chips">{attachments.map((file, i) => <button type="button" key={i} onClick={() => setAttachments((a) => a.filter((_, n) => n !== i))}>{file.name} <X size={12} /></button>)}</div>}<input ref={composerInput} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Xabaringizni yozing..." onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }} /></div>
        <button type="button" className={listening ? "mic-btn on" : "mic-btn"} onClick={toggleMic} title="Ovoz bilan yozish"><Mic /></button></div>
      <button className={busy ? "send-btn stop-btn" : "send-btn"} type="submit" title={busy ? "To‘xtatish" : "Yuborish"} disabled={!busy && !message.trim() && !attachments.length}>{busy ? <Square size={16} /> : <Send size={18} />}</button>
      <button type="button" className="round-btn" onClick={() => setActiveView("Sozlamalar")} title="Sozlamalar"><SlidersHorizontal /></button></form>
  </section>;
  const filteredChats = chats.filter((chat) => (chat.title || "Yangi suhbat").toLowerCase().includes(search.toLowerCase()));

  if (!authChecked) return <div className="boot-screen"><Robot /><span>Agent Umimiy ishga tushmoqda…</span><Loader2 className="spin" /></div>;

  if (!user) return <div className={`auth-screen ${theme}`}><Toaster richColors position="top-right" /><div className="auth-card panel"><Robot /><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi</div><h1>Agent Umimiy</h1><p>{register ? "Yangi hisob yarating" : "Hisobingizga kiring"}</p><form onSubmit={submitAuth}><label>Foydalanuvchi nomi<input required minLength={2} value={authName} onChange={(e) => setAuthName(e.target.value)} autoComplete="username" /></label><label>Parol<input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={register ? "new-password" : "current-password"} /></label>{register && <label>Taklif kodi<input required value={invite} onChange={(e) => setInvite(e.target.value)} /></label>}<button className="primary-btn" disabled={authBusy}>{authBusy ? <Loader2 className="spin" /> : <ShieldCheck size={17} />}{register ? "Ro‘yxatdan o‘tish" : "Kirish"}</button></form><button className="switch-auth" onClick={() => setRegister(!register)}>{register ? "Hisobim bor — kirish" : "Hisobim yo‘q — ro‘yxatdan o‘tish"}</button><small>Server egasidan taklif kodini oling.</small></div></div>;

  return <div className={`app-shell ${theme} accent-${settings.accent}`}><Toaster richColors position="top-right" />
    <aside className={`sidebar${mobileNav ? " open" : ""}${navHidden ? " hidden" : ""}`}>
      <div className="brand"><div className="brand-mark">AU</div><div><b>Agent Umimiy</b><span>AI platformasi</span></div><button className="icon-btn mobile-close" onClick={() => setMobileNav(false)}><X /></button></div>
      <nav>
        {NAV.map(([label, Icon]) => <button key={label} title={label} className={activeView === label ? "nav-item selected" : "nav-item"} onClick={() => { setActiveView(label); setMobileNav(false); }}><Icon size={18} /><span>{label}</span>{activeView === label && <ChevronRight size={15} />}</button>)}
      </nav>
      <div className="sidebar-section"><div className="sidebar-section-title">SO‘NGGI SUHBATLAR <button onClick={createChat} title="Yangi suhbat"><Plus size={14} /></button></div>
        <div className="chat-list">{filteredChats.slice(0, 6).map((chat) => <div className={chat.id === chatId ? "chat-link active" : "chat-link"} key={chat.id}><button onClick={() => openChat(chat.id)}><MessageSquare size={13} /><span>{chat.title || "Yangi suhbat"}</span></button><button className="delete-chat" onClick={() => void deleteChat(chat.id)} title="O‘chirish"><Trash2 size={13} /></button></div>)}</div>
      </div>
      <div className="sidebar-bottom"><div className="side-bot"><Robot /></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="icon-btn menu-btn" title="Menyu" onClick={() => { if (window.innerWidth <= 900) setMobileNav(true); else setNavHidden(!navHidden); }}><Menu /></button><div className="search"><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Qidirish (suhbat, fayl, agent)..." /><Search size={17} /></div>
        <label className="agent-select"><Bot size={16} /><select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)} aria-label="Agent tanlash">{agents.map((a) => <option key={a.name} value={a.name}>{a.name === "auto" ? "Avtomatik agent" : a.name}</option>)}</select><ChevronDown size={14} /></label>
        <div className="server-pill"><i /> Server: Ulangan</div>
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
            <div className="agent-row"><div className="file-icon blue"><Folder /></div><div className="row-copy"><b>{workspace.project || "Loyiha tanlanmagan"}</b><span>Server konfiguratsiyasidagi faol loyiha</span></div><span className="online"><i /> {workspace.project ? "Ulangan" : "Sozlanmagan"}</span></div>
            <p className="settings-note">Loyiha katalogi va fayllari masofadan ochilmaydi. Bu yerda faqat xavfsiz holat ma’lumoti ko‘rsatiladi.</p>
          </>}
          {workspace && activeView === "Plaginlar" && <>
            <div className="panel-heading"><b>MCP ulanishlari</b><span className="text-link">{workspace.plugins.length} ta</span></div>
            {workspace.plugins.length ? workspace.plugins.map((plugin) => <div className="agent-row" key={plugin.name}><div className="file-icon cyan"><Zap /></div><div className="row-copy"><b>{plugin.name}</b><span>{plugin.transport} · maxfiy sozlamalar yashirilgan</span></div><span className={plugin.enabled ? "online" : "text-link"}>{plugin.enabled ? "Yoqilgan" : "O‘chirilgan"}</span></div>) : <div className="empty-state">Hozircha MCP plaginlari sozlanmagan.</div>}
            <div className="panel-heading"><b>Ko‘nikmalar (Skills)</b><span className="text-link">{workspace.skills.length} ta</span></div>
            {workspace.skills.map((skill) => <div className="agent-row" key={skill.name}><div className="file-icon blue"><Sparkles /></div><div className="row-copy"><b>{skill.name}</b><span>{skill.description || skill.source}</span></div></div>)}
            <p className="settings-note">Ulanishlarni qo‘shish, tahrirlash va qayta ulash hozircha desktop sozlamalarida bajariladi.</p>
          </>}
          {workspace && activeView === "Avtomatlashtirish" && <div className="empty-state"><Clock3 /><b>Avtomatlashtirish hali ulanmagan</b><span>{workspace.automation.reason}. Bu bo‘lim hozircha vazifa yaratmaydi yoki fon rejimida ishga tushmaydi.</span></div>}
          {workspace && activeView === "Ma’lumotlar bazasi" && <>
            <div className="stats-grid">
              <article className="stat-card violet"><div className="stat-copy"><span>Ma’lumotlar ombori</span><b>{workspace.database.engine}</b></div></article>
              <article className="stat-card blue"><div className="stat-copy"><span>Holati</span><b>{workspace.database.status === "connected" ? "Ulangan" : workspace.database.status}</b></div></article>
              <article className="stat-card pink"><div className="stat-copy"><span>Foydalanuvchilar</span><b>{workspace.database.users}</b></div></article>
              <article className="stat-card amber"><div className="stat-copy"><span>Suhbatlar</span><b>{workspace.database.chats}</b></div></article>
            </div>
            <p className="settings-note">Ma’lumotlar bazasi holati ko‘rsatiladi. SQL buyruqlari, zaxira nusxa va o‘chirish amallari xavfsizlik uchun web orqali ochilmagan.</p>
          </>}
        </section>}
        {activeView === "Sozlamalar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Settings /> Sozlamalar</h2><span className="text-link">Xavfsiz web sozlamalari</span></div>
          <div className="settings-grid">
            <div className="settings-info"><b>Interfeys tili</b><span>O‘zbekcha · boshqa tillar tarjimasi hali ulanmagan</span></div>
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
          {desktop && <div className="classic-box"><div className="row-copy"><b>Klassik oyna</b><span>Agent qo‘shish, API kalitlari, loyiha papkasi va plaginlarni sozlash.</span></div><button className="secondary-btn" onClick={() => void openClassic()}>Klassik oynani ochish</button></div>}
          {settingsSaving && <span className="online"><i /> Saqlanmoqda…</span>}
        </section>}
        {activeView === "Agentlar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Bot /> Agentlar</h2><span className="text-link">{agents.length} ta serverda sozlangan</span></div>
          {agents.map((agent) => <div className="agent-row" key={agent.name}><div className="file-icon cyan"><Bot /></div><div className="row-copy"><b>{agent.name === "auto" ? "Avtomatik tanlash" : agent.name}</b><span>{agent.model || "Model server konfiguratsiyasidan olinadi"}</span></div><span className="online"><i /> Mavjud</span><button className="secondary-btn" onClick={() => { setSelectedAgent(agent.name); setActiveView("Suhbat"); }}>Suhbat boshlash</button></div>)}
          <p className="settings-note">Agent qo‘shish va API kalitlarini tahrirlash xavfsizlik sababli klassik oynada bajariladi.{desktop && <button className="secondary-btn" onClick={() => void openClassic()}>Klassik oynani ochish</button>}</p>
        </section>}
        {activeView === "Fayllar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Folder /> Fayllar</h2><span className="text-link">Tanlangan suhbat</span></div>
          {generatedFiles.length ? generatedFiles.slice().reverse().map((file, i) => <div className="file-row" key={i}><div className="file-icon blue"><FileText /></div><b>{file.text}</b><a href={chatId ? `/api/file?chat=${chatId}&name=${encodeURIComponent(file.text || "")}` : "#"} download><Download size={14} /> Yuklab olish</a></div>) : <div className="empty-state"><FileText /><span>Agent yaratgan fayllar hozircha yo‘q. Chatda fayl yaratishni so‘rang.</span></div>}
        </section>}
        {activeView === "Hisobotlar" && <section className="panel settings-page">
          <div className="panel-heading"><h2><Activity /> Hisobotlar</h2><span className="text-link">Joriy hisob ma’lumotlari</span></div>
          <div className="stats-grid">
            <article className="stat-card violet"><div className="stat-icon"><Bot /></div><div className="stat-copy"><span>Agentlar</span><b>{agents.length}</b></div></article>
            <article className="stat-card blue"><div className="stat-icon"><MessageSquare /></div><div className="stat-copy"><span>Suhbatlar</span><b>{chats.length}</b></div></article>
            <article className="stat-card pink"><div className="stat-icon"><Activity /></div><div className="stat-copy"><span>Joriy chat javoblari</span><b>{completed}</b></div></article>
            <article className="stat-card amber"><div className="stat-icon"><Folder /></div><div className="stat-copy"><span>Joriy chat fayllari</span><b>{generatedFiles.length}</b></div></article>
          </div>
          <p className="settings-note">Bu ko‘rsatkichlar serverdan olinadi. To‘liq tarixiy tahlil uchun alohida analitika ombori hali mavjud emas.</p>
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
