import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { motion } from "framer-motion";
import {
  Activity, ArrowUpRight, Bot, Boxes, Check, FileSpreadsheet,
  FileText, Folder, LayoutDashboard, Menu, MessageCircle, Paperclip,
  Plug, Search, Send, Settings, ShieldCheck, Sparkles, Workflow, X, Zap,
} from "lucide-react";

type Agent = { name: string; model?: string };
type Chat = { id: number; title: string };
type RecordItem = { k: string; text?: string; name?: string; agent?: string; meta?: string; err?: boolean; files?: string[]; kind?: string };
type Upload = { name: string; data: string };
type MemoryItem = { id: string; fact: string };
type EventMessage = { type: string; records?: RecordItem[]; live?: Record<string, string>; busy?: boolean; record?: RecordItem; agent?: string; text?: string };

const nav = [
  { label: "Bosh sahifa", icon: LayoutDashboard },
  { label: "Suhbat", icon: MessageCircle },
  { label: "Agentlar", icon: Bot },
  { label: "Fayllar", icon: Folder },
  { label: "Xotira", icon: Sparkles },
  { label: "Plaginlar", icon: Plug },
  { label: "Avtomatlashtirish", icon: Workflow },
  { label: "Sozlamalar", icon: Settings },
];

async function api<T = Record<string, unknown>>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `Server xatosi (${response.status})`) as Error & { code?: number };
    error.code = response.status;
    throw error;
  }
  return data as T;
}

function App() {
  const [active, setActive] = useState("Bosh sahifa");
  const [mobileNav, setMobileNav] = useState(false);
  const [message, setMessage] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [user, setUser] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agent, setAgent] = useState("auto");
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState<number | null>(null);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [live, setLive] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<Upload[]>([]);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [memoryFact, setMemoryFact] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authName, setAuthName] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const streamRef = useRef<EventSource | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const me = await api<{ user: string; agents: Agent[]; chats: Chat[] }>("/api/me");
    setUser(me.user);
    setAgents(me.agents);
    setChats(me.chats);
    setAgent((current) => me.agents.some((item) => item.name === current) ? current : "auto");
    return me;
  }, []);

  const showAuth = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    setUser("");
    setChatId(null);
    setRecords([]);
    setLive({});
    setBusy(false);
    setMemoryItems([]);
    setMemoryFact("");
    setActive("Bosh sahifa");
  }, []);

  useEffect(() => {
    refresh().then((me) => {
      if (me.chats.length) setChatId(me.chats[0].id);
    }).catch(() => showAuth()).finally(() => setLoading(false));
    return () => streamRef.current?.close();
  }, [refresh, showAuth]);

  useEffect(() => {
    if (!user || chatId === null) {
      streamRef.current?.close();
      streamRef.current = null;
      return;
    }
    streamRef.current?.close();
    const source = new EventSource(`/api/stream?chat=${chatId}`);
    streamRef.current = source;
    source.onmessage = (messageEvent) => {
      const event = JSON.parse(messageEvent.data) as EventMessage;
      if (event.type === "init") {
        setRecords(event.records || []);
        setLive(event.live || {});
        setBusy(Boolean(event.busy));
      } else if (event.type === "record" && event.record) {
        setRecords((items) => [...items, event.record!]);
        if (event.record.k === "agent") setLive({});
        if (event.record.k === "act" && event.record.kind === "file") refresh().catch(() => {});
      } else if (event.type === "delta" && event.agent) {
        setLive((items) => ({ ...items, [event.agent!]: (items[event.agent!] || "") + (event.text || "") }));
      } else if (event.type === "turn" && event.agent) {
        setLive((items) => ({ ...items, [event.agent!]: "" }));
      } else if (event.type === "busy") {
        setBusy(true);
      } else if (event.type === "done") {
        setBusy(false);
        setLive({});
        refresh().catch(() => {});
      }
    };
    source.onerror = () => setError("Server bilan aloqa uzildi. Qayta ulanmoqda…");
    source.onopen = () => setError("");
    return () => source.close();
  }, [user, chatId, refresh]);

  async function authenticate(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(authMode === "register" ? "/api/register" : "/api/login", {
        name: authName, password, invite,
      });
      setPassword("");
      const me = await refresh();
      setChatId(me.chats[0]?.id ?? null);
      setActive("Bosh sahifa");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kirish amalga oshmadi");
    }
  }

  async function newChat() {
    try {
      const result = await api<{ id: number }>("/api/chat/new", {});
      setChatId(result.id);
      setRecords([]);
      setLive({});
      setActive("Suhbat");
      setMobileNav(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suhbat yaratilmadi");
    }
  }

  async function openChat(id: number) {
    setChatId(id);
    setRecords([]);
    setLive({});
    setActive("Suhbat");
    setMobileNav(false);
  }

  async function deleteChat(id: number) {
    if (!window.confirm("Ushbu suhbat o‘chirilsinmi?")) return;
    try {
      await api("/api/chat/delete", { chat: id });
      const remaining = chats.filter((item) => item.id !== id);
      setChats(remaining);
      if (chatId === id) setChatId(remaining[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suhbat o‘chirilmadi");
    }
  }

  function addFiles(selected: FileList | null) {
    if (!selected) return;
    const room = 6 - files.length;
    Array.from(selected).slice(0, room).forEach((file) => {
      if (file.size > 15 * 1024 * 1024) {
        setError(`${file.name}: fayl 15 MB dan katta`);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const encoded = String(reader.result).split(",")[1] || "";
        setFiles((items) => [...items, { name: file.name, data: encoded }].slice(0, 6));
      };
      reader.onerror = () => setError(`${file.name}: faylni o‘qib bo‘lmadi`);
      reader.readAsDataURL(file);
    });
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (busy) {
      if (chatId !== null) await api("/api/stop", { chat: chatId }).catch(() => {});
      return;
    }
    const text = message.trim();
    if (!text && !files.length) return;
    const sentFiles = files;
    setFiles([]);
    setMessage("");
    try {
      let id = chatId;
      if (id === null) {
        const created = await api<{ id: number }>("/api/chat/new", {});
        id = created.id;
        setChatId(id);
      }
      await api("/api/send", { chat: id, text, agent, files: sentFiles });
      setActive("Suhbat");
      await refresh();
    } catch (err) {
      setMessage(text);
      setFiles(sentFiles);
      const failure = err as Error & { code?: number };
      setError(failure.message);
      if (failure.code === 401) showAuth();
    }
  }

  async function loadMemory() {
    try { const data = await api<{ items: MemoryItem[] }>("/api/memory"); setMemoryItems(data.items); }
    catch (err) { setError(err instanceof Error ? err.message : "Xotira yuklanmadi"); }
  }

  async function saveMemory(event: FormEvent) {
    event.preventDefault();
    if (!memoryFact.trim()) return;
    try { await api("/api/memory/remember", { fact: memoryFact.trim() }); setMemoryFact(""); await loadMemory(); }
    catch (err) { setError(err instanceof Error ? err.message : "Xotira saqlanmadi"); }
  }

  async function deleteMemory(id: string) {
    if (!window.confirm("Ushbu xotira yozuvi o‘chirilsinmi?")) return;
    try { await api("/api/memory/delete", { id }); await loadMemory(); }
    catch (err) { setError(err instanceof Error ? err.message : "Xotira o‘chirilmadi"); }
  }

  async function logout() {
    await api("/api/logout", {}).catch(() => {});
    showAuth();
  }

  const filesCount = records.filter((item) => item.k === "act" && item.kind === "file").length;
  const currentChat = chats.find((item) => item.id === chatId);

  if (loading) return <div className="loading-screen"><Bot size={36} /> Agent Umimiy yuklanmoqda…</div>;

  if (!user) return (
    <div className={`auth-screen ${theme}`}>
      <form className="auth-card" onSubmit={authenticate}>
        <div className="brand-mark">AU</div>
        <h1>Agent Umimiy</h1>
        <p>{authMode === "login" ? "Hisobingizga kiring" : "Yangi hisob yarating"}</p>
        <input value={authName} onChange={(e) => setAuthName(e.target.value)} placeholder="Ism" autoComplete="username" required />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Parol" autoComplete={authMode === "login" ? "current-password" : "new-password"} required />
        {authMode === "register" && <input value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="Taklif kodi" required />}
        {error && <div className="error-message">{error}</div>}
        <button className="primary-button" disabled={!authName.trim() || !password}>{authMode === "login" ? "Kirish" : "Ro‘yxatdan o‘tish"}</button>
        <button type="button" className="text-button" onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setError(""); }}>
          {authMode === "login" ? "Hisob yaratish" : "Hisobim bor — kirish"}
        </button>
      </form>
    </div>
  );

  return (
    <div className={`app-shell ${theme}`}>
      <aside className={mobileNav ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <div className="brand-mark">AU</div>
          <div><b>Agent Umimiy</b><span>AI platformasi</span></div>
          <button className="icon-btn mobile-close" onClick={() => setMobileNav(false)} aria-label="Yopish"><X /></button>
        </div>
        <nav>
          {nav.map(({ label, icon: Icon }) => (
            <button key={label} className={active === label ? "nav-item selected" : "nav-item"} onClick={() => { setActive(label); setMobileNav(false); if (label === "Xotira") loadMemory(); }}>
              <Icon size={18} /><span>{label}</span>{active === label && <ArrowUpRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="new-chat-button" onClick={newChat}>＋ Yangi suhbat</button>
          <div className="chat-list">
            <div className="chat-list-title">Suhbatlar</div>
            {chats.map((chat) => (
              <div className={chat.id === chatId ? "chat-item current" : "chat-item"} key={chat.id}>
                <button className="chat-open" onClick={() => openChat(chat.id)}>{chat.title || "Yangi suhbat"}</button>
                <button className="chat-delete" onClick={() => deleteChat(chat.id)} aria-label="Suhbatni o‘chirish">×</button>
              </div>
            ))}
          </div>
          <div className="profile">
            <div className="avatar">{user.slice(0, 2).toUpperCase()}</div>
            <div className="profile-copy"><b>{user}</b><span>Server foydalanuvchisi</span></div>
            <button className="logout-button" onClick={logout}>Chiqish</button>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMobileNav(true)} aria-label="Menyu"><Menu /></button>
          <div className="search"><Search size={17} /><input placeholder="Suhbatlar va agentlar..." disabled /></div>
          <select className="agent-select" value={agent} onChange={(e) => setAgent(e.target.value)} aria-label="Agent tanlash">
            {agents.map((item) => <option key={item.name} value={item.name}>{item.name === "auto" ? item.model || "Automatic selection" : item.name}</option>)}
          </select>
          <div className="server-pill"><i /> Server: Ulangan</div>
          <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Mavzuni almashtirish">◐</button>
        </header>

        <div className="content">
          {error && <div className="inline-alert" role="status">{error}<button onClick={() => setError("")}>Yopish</button></div>}
          {active === "Bosh sahifa" ? (
            <>
              <section className="hero panel">
                <div className="hero-orb"><Bot size={76} strokeWidth={1.25} /></div>
                <div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi</div><h1>Agent Umimiy</h1><p>Barcha AI agentlaringiz — bitta qulay platformada.</p><div className="hero-tags"><span><Check /> Hujjatlar bilan ishlash</span><span><Check /> Ma’lumotlar tahlili</span><span><Check /> Jarayonlarni avtomatlashtirish</span></div></div>
              </section>
              <section className="stats-grid">
                {[
                  { label: "Ulangan agentlar", value: agents.length, icon: Boxes, tone: "violet" },
                  { label: "Suhbatlar", value: chats.length, icon: MessageCircle, tone: "blue" },
                  { label: "Yaratilgan fayllar", value: filesCount, icon: FileText, tone: "pink" },
                  { label: "Joriy holat", value: busy ? "Band" : "Tayyor", icon: Activity, tone: "amber" },
                ].map(({ label, value, icon: Icon, tone }, index) => (
                  <motion.article className={`stat-card ${tone}`} key={label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .06 }}>
                    <div className="stat-icon"><Icon /></div><div className="stat-copy"><span>{label}</span><b>{value}</b></div>
                  </motion.article>
                ))}
              </section>
              <section className="columns">
                <article className="panel list-panel">
                  <div className="panel-heading"><h2><Bot /> Ulangan agentlar</h2></div>
                  {agents.map((item) => <div className="agent-row" key={item.name}><div className="file-icon blue"><Bot /></div><div className="row-copy"><b>{item.name === "auto" ? item.model || "Automatic selection" : item.name}</b><span>{item.name === "auto" ? " " : item.model || "Model avtomatik tanlanadi"}</span></div><span className="online"><i /> Mavjud</span></div>)}
                </article>
                <article className="panel list-panel">
                  <div className="panel-heading"><h2><Folder /> Suhbatlar</h2></div>
                  {chats.slice(0, 6).map((chat) => <button className="dashboard-chat" key={chat.id} onClick={() => openChat(chat.id)}>{chat.title || "Yangi suhbat"} <ArrowUpRight size={14} /></button>)}
                  {!chats.length && <p className="muted-note">Hozircha suhbatlar yo‘q.</p>}
                </article>
                <article className="panel quick-panel">
                  <div className="panel-heading"><h2><Zap /> Tezkor amallar</h2></div>
                  <button onClick={newChat}><MessageCircle /> Yangi suhbat</button>
                  <button onClick={() => { setActive("Suhbat"); inputRef.current?.focus(); }}><FileText /> Hujjat bilan ishlash</button>
                  <button onClick={() => { setActive("Suhbat"); setMessage("Excel faylimni tahlil qilib ber."); }}><FileSpreadsheet /> Excel tahlili</button>
                </article>
              </section>
            </>
          ) : active === "Suhbat" ? (
            <section className="chat-workspace panel">
              <div className="chat-heading"><div><h2>{currentChat?.title || "Yangi suhbat"}</h2><p>Haqiqiy AI serveriga ulangan suhbat</p></div><span className={busy ? "status busy" : "status"}>{busy ? "Agent ishlayapti" : "Tayyor"}</span></div>
              <div className="message-list">
                {records.map((record, index) => <div className={record.k === "user" ? "message user-message" : "message"} key={index}>
                  {record.k === "user" ? <><b>Siz</b><p>{record.text}</p>{record.files?.map((name) => <small key={name}>📎 {name}</small>)}</>
                    : record.k === "agent" ? <><b>{record.name} <small>{record.meta}</small></b><p className={record.err ? "message-error" : ""}>{record.text}</p></>
                    : record.k === "act" ? <p className="activity-line">{record.agent}: {record.text}{record.kind === "file" && <a href={`/api/file?chat=${chatId}&name=${encodeURIComponent(record.text || "")}`}> Yuklab olish</a>}</p>
                    : null}
                </div>)}
                {Object.entries(live).filter(([, value]) => value).map(([name, value]) => <div className="message live-message" key={name}><b>{name} · javob yozmoqda</b><p>{value}</p></div>)}
                {!records.length && !busy && <div className="empty-chat"><Bot size={42} /><h3>Nimadan boshlaymiz?</h3><p>Savolingizni yozing yoki Word, Excel, PDF fayl biriktiring.</p></div>}
              </div>
              {files.length > 0 && <div className="pending-files">{files.map((file, index) => <span key={index}>📎 {file.name}<button onClick={() => setFiles((items) => items.filter((_, i) => i !== index))}>×</button></span>)}</div>}
              <form className="chat-composer" onSubmit={sendMessage}>
                <input ref={inputRef} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Xabaringizni yozing…" />
                <input type="file" multiple hidden id="upload-files" onChange={(e) => { addFiles(e.target.files); e.currentTarget.value = ""; }} />
                <button type="button" className="icon-btn" title="Fayl biriktirish" onClick={() => document.getElementById("upload-files")?.click()}><Paperclip /></button>
                <button type="submit" className="send-btn" disabled={!busy && !message.trim() && !files.length}>{busy ? "■" : <Send size={17} />}</button>
              </form>
            </section>
          ) : active === "Xotira" ? (
            <section className="panel list-panel">
              <div className="panel-heading"><h2><Sparkles /> Shaxsiy xotira</h2><span className="status">{memoryItems.length} ta yozuv</span></div>
              <p className="muted-note">Bu yozuvlar faqat sizning akkauntingizga tegishli. Agent xotiraga o‘zi yozolmaydi; saqlashni siz tasdiqlaysiz.</p>
              <form className="memory-form" onSubmit={saveMemory}>
                <input value={memoryFact} onChange={(e) => setMemoryFact(e.target.value)} maxLength={1000} placeholder="Eslab qolish kerak bo‘lgan ma’lumot…" />
                <button className="primary-button" disabled={!memoryFact.trim()}>Saqlash</button>
              </form>
              {memoryItems.map((item) => (
                <div className="memory-row" key={item.id}><div><b>{item.fact}</b><small>ID: {item.id}</small></div><button className="chat-delete" onClick={() => deleteMemory(item.id)}>O‘chirish</button></div>
              ))}
              {!memoryItems.length && <p className="muted-note">Hozircha saqlangan xotira yo‘q.</p>}
            </section>
          ) : active === "Agentlar" ? (
            <section className="panel list-panel">
              <div className="panel-heading"><h2><Bot /> Haqiqiy ulangan agentlar</h2></div>
              <p className="muted-note">Quyidagi ro‘yxat Python server sozlamalaridan olinadi.</p>
              <div className="agent-cards">
                {agents.map((item) => (
                  <article className="agent-card" key={item.name}>
                    <div className="file-icon blue"><Bot /></div>
                    <div className="row-copy"><b>{item.name === "auto" ? item.model || "Automatic selection" : item.name}</b><span>{item.model || "Serverdagi agent"}</span></div>
                    <button className="primary-button" onClick={() => { setAgent(item.name); setActive("Suhbat"); }}>Tanlash</button>
                  </article>
                ))}
              </div>
            </section>
          ) : active === "Fayllar" ? (
            <section className="panel list-panel">
              <div className="panel-heading"><h2><Folder /> Joriy suhbat fayllari</h2></div>
              <p className="muted-note">Agent yaratgan va server saqlagan fayllar.</p>
              {records.filter((item) => item.k === "act" && item.kind === "file").map((item, index) => (
                <div className="file-row" key={index}>
                  <div className="file-icon word"><FileText /></div>
                  <b>{item.text}</b>
                  <a href={`/api/file?chat=${chatId}&name=${encodeURIComponent(item.text || "")}`}>Yuklab olish</a>
                </div>
              ))}
              {!records.some((item) => item.k === "act" && item.kind === "file") && <p className="muted-note">Bu suhbatda hali yaratilgan fayl yo‘q. Agentdan Word yoki Excel fayl yaratishni so‘rang.</p>}
            </section>
          ) : active === "Sozlamalar" ? (
            <section className="panel placeholder-panel">
              <Settings size={38} /><h2>Sozlamalar</h2>
              <p>Interfeys mavzusi va joriy server sessiyasini boshqarish.</p>
              <button className="primary-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>Mavzuni {theme === "dark" ? "yorug‘" : "qorong‘i"} qilish</button>
              <button className="text-button" onClick={logout}>Hisobdan chiqish</button>
            </section>
          ) : (
            <section className="panel placeholder-panel">
              <Bot size={38} /><h2>{active}</h2>
              <p>Bu bo‘lim hozirgi Python server API'sida alohida boshqaruv sahifasi sifatida mavjud emas. Ishlamaydigan demo ma’lumot ko‘rsatish o‘rniga, mavjud funksiyalarni suhbat orqali ishlatishingiz mumkin.</p>
              <button className="primary-button" onClick={() => { setActive("Suhbat"); setMessage(`${active} bo‘yicha yordam ber`); }}>Suhbatda ishlatish</button>
            </section>
          )}
          <footer><span><ShieldCheck /> Himoyalangan sessiya</span><span>Agent Umimiy · {user}</span><button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>Mavzuni almashtirish</button></footer>
        </div>
      </main>
    </div>
  );
}

export default App;
