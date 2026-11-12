import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity, Bot, Check, ChevronDown, Clock3, Database, Download,
  FileSpreadsheet, FileText, Folder, Globe2, LayoutDashboard, Loader2,
  LogOut, Menu, MessageSquare, Moon, Paperclip, Plus, Search, Send,
  Settings, ShieldCheck, Sparkles, Square, Sun, Trash2, X, Zap,
} from "lucide-react";
import { Toaster, toast } from "sonner";

type Agent = { name: string; model?: string };
type Chat = { id: number; title?: string };
type RecordItem = { k: string; text?: string; name?: string; agent?: string; meta?: string; err?: boolean; files?: string[]; kind?: string };
type LiveState = Record<string, string>;
type ApiError = Error & { code?: number };
const MAX_FILE = 15 * 1024 * 1024;

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
  return <div className={small ? "robot robot-small" : "robot"} aria-label="Agent Umumiy AI robot">
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
  const [activeView, setActiveView] = useState("Bosh sahifa");
  const [search, setSearch] = useState("");
  const eventSource = useRef<EventSource | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    const me = await api<{ user: string; agents: Agent[]; chats: Chat[] }>("/api/me");
    setUser(me.user); setAgents(me.agents || []); setChats(me.chats || []);
    return me;
  }, []);

  const openChat = useCallback((id: number) => {
    eventSource.current?.close();
    setChatId(id); setRecords([]); setLive({}); setBusy(false);
    const source = new EventSource(`/api/stream?chat=${id}`);
    eventSource.current = source;
    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as Record<string, unknown>;
      if (item.type === "init") {
        setRecords((item.records as RecordItem[]) || []);
        setLive((item.live as LiveState) || {});
        setBusy(Boolean(item.busy));
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
      else if (item.type === "done") {
        setBusy(false); setLive({});
        void refresh().catch(() => undefined);
      } else if (item.type === "overflow") {
        toast.info("Jonli ulanish yangilanmoqda");
        source.close();
        window.setTimeout(() => openChat(id), 500);
      }
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) toast.error("Suhbat bilan aloqa uzildi");
    };
    setActiveView("Suhbat"); setMobileNav(false);
  }, [refresh]);

  useEffect(() => {
    let active = true;
    api<{ user: string; agents: Agent[]; chats: Chat[] }>("/api/me")
      .then((me) => {
        if (!active) return;
        setUser(me.user); setAgents(me.agents || []); setChats(me.chats || []);
        setAuthChecked(true);
        if (me.chats?.length) openChat(me.chats[0].id);
      })
      .catch((error: ApiError) => {
        if (!active) return;
        if (error.code !== 401) toast.error(error.message);
        setAuthChecked(true);
      });
    return () => { active = false; eventSource.current?.close(); };
  }, [openChat]);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [records, live]);

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setAuthBusy(true);
    try {
      await api(register ? "/api/register" : "/api/login", { name: authName, password, invite });
      setPassword(""); const me = await refresh();
      if (me.chats.length) openChat(me.chats[0].id);
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
      if (chatId === id && me.chats.length) openChat(me.chats[0].id);
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

  const generatedFiles = useMemo(() => records.filter((r) => r.k === "act" && r.kind === "file"), [records]);
  const completed = records.filter((r) => r.k === "agent").length;
  const metrics = [
    { label: "Faol agentlar", value: agents.length, icon: Bot, color: "violet", hint: "Server konfiguratsiyasi" },
    { label: "Suhbatlar", value: chats.length, icon: MessageSquare, color: "blue", hint: "Sizning hisobingiz" },
    { label: "Javoblar", value: completed, icon: Activity, color: "pink", hint: "Joriy suhbat" },
    { label: "Yaratilgan fayllar", value: generatedFiles.length, icon: Folder, color: "amber", hint: "Joriy suhbat" },
  ];
  const filteredChats = chats.filter((chat) => (chat.title || "Yangi suhbat").toLowerCase().includes(search.toLowerCase()));

  if (!authChecked) return <div className="boot-screen"><Robot /><span>Agent Umumiy ishga tushmoqda…</span><Loader2 className="spin" /></div>;

  if (!user) return <div className={`auth-screen ${theme}`}><Toaster richColors position="top-right" /><div className="auth-card panel"><Robot /><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi</div><h1>Agent Umumiy</h1><p>{register ? "Yangi hisob yarating" : "Hisobingizga kiring"}</p><form onSubmit={submitAuth}><label>Foydalanuvchi nomi<input required minLength={2} value={authName} onChange={(e) => setAuthName(e.target.value)} autoComplete="username" /></label><label>Parol<input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={register ? "new-password" : "current-password"} /></label>{register && <label>Taklif kodi<input required value={invite} onChange={(e) => setInvite(e.target.value)} /></label>}<button className="primary-btn" disabled={authBusy}>{authBusy ? <Loader2 className="spin" /> : <ShieldCheck size={17} />}{register ? "Ro‘yxatdan o‘tish" : "Kirish"}</button></form><button className="switch-auth" onClick={() => setRegister(!register)}>{register ? "Hisobim bor — kirish" : "Hisobim yo‘q — ro‘yxatdan o‘tish"}</button><small>Server egasidan taklif kodini oling.</small></div></div>;

  return <div className={`app-shell ${theme}`}><Toaster richColors position="top-right" />
    <aside className={mobileNav ? "sidebar open" : "sidebar"}>
      <div className="brand"><div className="brand-mark">AU</div><div><b>Agent Umumiy</b><span>AI platformasi</span></div><button className="icon-btn mobile-close" onClick={() => setMobileNav(false)}><X /></button></div>
      <nav>
        {[["Bosh sahifa",LayoutDashboard],["Suhbat",MessageSquare],["Agentlar",Bot],["Fayllar",Folder],["Loyihalar",Database],["Plaginlar",Zap],["Avtomatlashtirish",Clock3],["Hisobotlar",Activity],["Ma’lumotlar bazasi",Database],["Sozlamalar",Settings]].map(([label, Icon]) => {
          const I = Icon as typeof LayoutDashboard;
          return <button key={label as string} className={activeView === label ? "nav-item selected" : "nav-item"} onClick={() => { setActiveView(label as string); setMobileNav(false); if (label === "Suhbat" && chatId === null) void createChat(); }}><I size={17} /><span>{label as string}</span></button>;
        })}
      </nav>
      <div className="sidebar-section"><div className="sidebar-section-title">SO‘NGGI SUHBATLAR <button onClick={createChat} title="Yangi suhbat"><Plus size={14} /></button></div>
        <div className="chat-list">{filteredChats.slice(0, 8).map((chat) => <div className={chat.id === chatId ? "chat-link active" : "chat-link"} key={chat.id}><button onClick={() => openChat(chat.id)}><MessageSquare size={13} /><span>{chat.title || "Yangi suhbat"}</span></button><button className="delete-chat" onClick={() => void deleteChat(chat.id)} title="O‘chirish"><Trash2 size={13} /></button></div>)}</div>
      </div>
      <div className="sidebar-bottom"><div className="mini-bot"><Robot small /><div><b>AI yordamchi</b><span>Agentlar tayyor</span></div></div><div className="profile"><div className="avatar">{user.slice(0, 2).toUpperCase()}</div><div><b>{user}</b><span><i /> Ulangan</span></div><button onClick={() => void logout()} title="Chiqish"><LogOut size={16} /></button></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="icon-btn menu-btn" onClick={() => setMobileNav(true)}><Menu /></button><div className="search"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Suhbatlarni qidirish..." /></div>
        <label className="agent-select"><Bot size={15} /><select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}>{agents.map((a) => <option key={a.name} value={a.name}>{a.name === "auto" ? "Avtomatik agent" : a.name}</option>)}</select><ChevronDown size={13} /></label>
        <div className="server-pill"><i /> Server: Ulangan</div><button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Mavzuni almashtirish">{theme === "dark" ? <Sun /> : <Moon />}</button>
      </header>
      <div className="content">
        <section className="hero panel"><div className="hero-mascot"><Robot /></div><div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi / Boshqaruv paneli</div><h1>Agent Umumiy</h1><p>Sizning ko‘p funksiyali AI yordamchingiz</p><div className="hero-tags"><span><Check /> Hujjatlar bilan ishlash (Word, Excel, PDF)</span><span><Check /> Ma’lumotlarni tahlil va hisobot</span><span><Check /> Web-ma’lumotlarni izlash</span></div></div><div className="hero-glow" /></section>
        <section className="stats-grid">{metrics.map(({ label, value, icon: Icon, color, hint }) => <article className={`stat-card ${color}`} key={label}><div className="stat-icon"><Icon /></div><div className="stat-copy"><span>{label}</span><b>{value}</b><small>{hint}</small></div></article>)}</section>
        <section className="columns">
          <article className="panel list-panel"><div className="panel-heading"><h2><Bot /> Agentlar</h2><span className="text-link">{agents.length} ta sozlangan</span></div>{agents.map((agent) => <div className="agent-row" key={agent.name}><div className="file-icon cyan"><Bot /></div><div className="row-copy"><b>{agent.name === "auto" ? "Avtomatik tanlash" : agent.name}</b><span>{agent.model || "Konfiguratsiyadagi AI agent"}</span></div><span className="online"><i /> Tayyor</span></div>)}</article>
          <article className="panel list-panel"><div className="panel-heading"><h2><Folder /> Suhbat fayllari</h2><span className="text-link">{generatedFiles.length} ta</span></div>{generatedFiles.length ? generatedFiles.slice(-5).reverse().map((file, i) => <div className="file-row" key={i}><div className="file-icon blue"><FileText /></div><b>{file.text}</b><a href={chatId ? `/api/file?chat=${chatId}&name=${encodeURIComponent(file.text || "")}` : "#"} download><Download size={14} /></a></div>) : <div className="empty-state"><FileText /><span>Agent yaratgan fayllar shu yerda ko‘rinadi</span></div>}</article>
          <article className="panel quick-panel"><div className="panel-heading"><h2><Zap /> Tezkor amallar</h2></div><button onClick={() => { setMessage("Word hujjat tayyorlab ber: "); setActiveView("Suhbat"); }}><FileText /> Word / PDF hujjat</button><button onClick={() => { setMessage("Biriktirilgan Excel faylni tahlil qilib ber"); fileInput.current?.click(); }}><FileSpreadsheet /> Excel tahlili</button><button onClick={() => { setMessage("Internetdan shu mavzu bo‘yicha ma’lumot top: "); setActiveView("Suhbat"); }}><Globe2 /> Web qidiruv</button><button onClick={() => { setMessage("Hisobot tayyorlab ber: "); setActiveView("Suhbat"); }}><Activity /> Hisobot tayyorlash</button></article>
        </section>
        <section className="workspace panel"><div className="workspace-title"><div className="spark-badge"><Sparkles /></div><div><h2>Agent Umumiy bilan suhbat</h2><p>Haqiqiy AI agentiga ulanadi · Javoblar jonli keladi</p></div><button className="new-chat-btn" onClick={createChat}><Plus size={15} /> Yangi suhbat</button></div>
          <div className="messages">
            {!records.length && !busy && <div className="welcome-chat"><Robot small /><b>Qanday yordam bera olaman?</b><span>Agent tanlang, xabar yozing yoki fayl biriktiring.</span></div>}
            {records.map((record, index) => <div className={record.k === "user" ? "message-row user-message" : "message-row"} key={index}><div className="message-avatar">{record.k === "user" ? user.slice(0, 1).toUpperCase() : <Bot size={17} />}</div><div className="message-body"><b>{record.k === "user" ? user : record.name || record.agent || "Agent"}</b><div className={record.err ? "message-bubble error" : "message-bubble"}>{record.text}{record.files?.length ? <small>📎 {record.files.join(", ")}</small> : null}</div>{record.meta && <small className="message-meta">{record.meta}</small>}</div></div>)}
            {Object.entries(live).map(([name, text]) => <div className="message-row" key={name}><div className="message-avatar"><Bot size={17} /></div><div className="message-body"><b>{name} <span className="typing-label">yozmoqda…</span></b><div className="message-bubble live">{text}</div></div></div>)}
            {busy && !Object.keys(live).length && <div className="typing-indicator"><span /><span /><span /> Agent javob tayyorlamoqda…</div>}
            <div ref={messagesEnd} />
          </div>
          <form className="composer" onSubmit={sendMessage}><input ref={fileInput} type="file" multiple hidden accept="image/*,.pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.json,.py,.js,.html,.log" onChange={(e) => { void addFiles(e.target.files); e.currentTarget.value = ""; }} />
            <button type="button" className="icon-btn" onClick={() => fileInput.current?.click()} title="Fayl biriktirish"><Paperclip /></button><div className="composer-main">{attachments.length > 0 && <div className="attachment-chips">{attachments.map((file, i) => <button type="button" key={i} onClick={() => setAttachments((a) => a.filter((_, n) => n !== i))}>{file.name} <X size={12} /></button>)}</div>}<input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Xabaringizni yozing..." onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }} /></div>
            <button className={busy ? "send-btn stop-btn" : "send-btn"} type="submit" disabled={!busy && !message.trim() && !attachments.length}>{busy ? <Square size={16} /> : <Send size={17} />}</button></form>
          <div className="composer-foot"><span><ShieldCheck size={13} /> Himoyalangan server sessiyasi</span><span>Enter — yuborish · Shift+Enter — yangi qator</span></div>
        </section>
      </div>
    </main>
  </div>;
}

export default App;
