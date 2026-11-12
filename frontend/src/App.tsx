import { useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, ArrowUpRight, Bell, Bot, Boxes, BriefcaseBusiness, Check,
  ChevronDown, FileSpreadsheet, FileText, Folder, Globe2, LayoutDashboard,
  Menu, MessageCircle, Mic, Paperclip, Plug, Search, Send, Settings,
  ShieldCheck, Sparkles, Workflow, X, ChartNoAxesCombined, Zap,
} from "lucide-react";

const nav = [
  { label: "Bosh sahifa", icon: LayoutDashboard },
  { label: "Suhbat", icon: MessageCircle },
  { label: "Agentlar", icon: Bot },
  { label: "Fayllar", icon: Folder },
  { label: "Loyihalar", icon: BriefcaseBusiness },
  { label: "Plaginlar", icon: Plug },
  { label: "Avtomatlashtirish", icon: Workflow },
  { label: "Hisobotlar", icon: ChartNoAxesCombined },
  { label: "Ma’lumotlar bazasi", icon: Database },
  { label: "Sozlamalar", icon: Settings },
];

const stats = [
  { label: "Faol agentlar", value: "05", delta: "+1", icon: Boxes, tone: "violet" },
  { label: "Loyihalar", value: "34", delta: "+6", icon: BriefcaseBusiness, tone: "blue" },
  { label: "Vazifalar", value: "189", delta: "+12", icon: Activity, tone: "pink" },
  { label: "Fayllar", value: "1 247", delta: "+85", icon: Folder, tone: "amber" },
];

const agents = [
  { name: "Hujjat Agent", detail: "Word, Excel, PDF bilan ishlash", icon: FileText, color: "blue" },
  { name: "Tahlil Agent", detail: "Ma’lumotlar va grafik tahlili", icon: ChartNoAxesCombined, color: "violet" },
  { name: "Web Agent", detail: "Internetdan ma’lumot izlash", icon: Globe2, color: "cyan" },
  { name: "Hisobot Agent", detail: "Hisobot va jadval tayyorlash", icon: FileSpreadsheet, color: "amber" },
];

const files = [
  { name: "Murojaatlar_hisoboti.docx", time: "16:32", type: "word" },
  { name: "Murojaatlar_jadval.xlsx", time: "15:47", type: "excel" },
  { name: "Hisobot_avgust.pdf", time: "14:20", type: "pdf" },
  { name: "Sayyor_qabul_2026.xlsx", time: "12:05", type: "excel" },
];

function App() {
  const [active, setActive] = useState("Bosh sahifa");
  const [mobileNav, setMobileNav] = useState(false);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState<string[]>([]);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  function sendMessage() {
    const value = message.trim();
    if (!value) return;
    setSent((items) => [...items, value]);
    setMessage("");
    setActive("Suhbat");
  }

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
            <button key={label} className={active === label ? "nav-item selected" : "nav-item"} onClick={() => { setActive(label); setMobileNav(false); }}>
              <Icon size={18} /><span>{label}</span>{active === label && <ArrowUpRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mini-bot"><Bot size={34} /><div><b>Yordam kerakmi?</b><span>AI yordamchi doim tayyor</span></div></div>
          <div className="profile"><div className="avatar">RQ</div><div><b>Foydalanuvchi</b><span><i /> Online</span></div><ChevronDown size={16} /></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMobileNav(true)} aria-label="Menyu"><Menu /></button>
          <div className="search"><Search size={17} /><input placeholder="Qidirish (fayl, loyiha, agent, ma’lumot)..." /></div>
          <button className="model-pill"><Sparkles size={16} /> GPT modeli <ChevronDown size={14} /></button>
          <div className="server-pill"><i /> Server: Ulangan</div>
          <button className="icon-btn notification" aria-label="Bildirishnomalar"><Bell /><em>3</em></button>
          <button className="profile-pill"><div className="avatar">RQ</div><span>Profil</span><ChevronDown size={14} /></button>
        </header>

        <div className="content">
          <section className="hero panel">
            <div className="hero-orb"><Bot size={76} strokeWidth={1.25} /></div>
            <div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> Yagona AI ekotizimi</div><h1>Agent Umimiy</h1><p>Barcha AI agentlaringiz — bitta qulay platformada.</p><div className="hero-tags"><span><Check /> Hujjatlar bilan ishlash</span><span><Check /> Ma’lumotlar tahlili</span><span><Check /> Jarayonlarni avtomatlashtirish</span></div></div>
            <div className="hero-glow" />
          </section>

          <section className="stats-grid">
            {stats.map(({ label, value, delta, icon: Icon, tone }, index) => (
              <motion.article className={`stat-card ${tone}`} key={label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .06 }}>
                <div className="stat-icon"><Icon /></div><div className="stat-copy"><span>{label}</span><b>{value}</b></div><small>{delta}</small>
              </motion.article>
            ))}
          </section>

          <section className="columns">
            <article className="panel list-panel">
              <div className="panel-heading"><h2><Bot /> Agentlar</h2><button className="text-link">Barchasi <ArrowUpRight /></button></div>
              {agents.map(({ name, detail, icon: Icon, color }) => <div className="agent-row" key={name}><div className={`file-icon ${color}`}><Icon /></div><div className="row-copy"><b>{name}</b><span>{detail}</span></div><span className="online"><i /> Online</span></div>)}
            </article>
            <article className="panel list-panel">
              <div className="panel-heading"><h2><Folder /> So‘nggi fayllar</h2><button className="text-link">Barchasi <ArrowUpRight /></button></div>
              {files.map((file) => <div className="file-row" key={file.name}><div className={`file-icon ${file.type}`}>{file.type === "excel" ? <FileSpreadsheet /> : <FileText />}</div><b>{file.name}</b><time>{file.time}</time></div>)}
            </article>
            <article className="panel quick-panel">
              <div className="panel-heading"><h2><Zap /> Tezkor amallar</h2></div>
              <button><FileText /> Word hujjat yaratish</button><button><FileSpreadsheet /> Excel jadval tahlili</button><button><Globe2 /> Web qidiruv</button><button><ChartNoAxesCombined /> Hisobot tayyorlash</button>
            </article>
          </section>

          <section className="workspace panel">
            <div className="workspace-title"><div className="spark-badge"><Sparkles /></div><div><h2>Agent Umimiy bilan suhbat</h2><p>Savolingizni yozing yoki tezkor amallardan foydalaning</p></div></div>
            <div className="prompt-chips"><button onClick={() => setMessage("Excel ma’lumotlarini tahlil qilib ber")}> <FileSpreadsheet /> Excel tahlili</button><button onClick={() => setMessage("Word hujjat tayyorlab ber")}><FileText /> Word hujjat</button><button onClick={() => setMessage("Internetdan ma’lumot top")}><Globe2 /> Web qidiruv</button><button onClick={() => setMessage("Hisobot tayyorlab ber")}><ChartNoAxesCombined /> Hisobot</button></div>
            {sent.length > 0 && <div className="sent-list">{sent.map((item, i) => <div className="sent-message" key={i}>{item}</div>)}</div>}
            <div className="composer"><button className="icon-btn" aria-label="Fayl biriktirish"><Paperclip /></button><input value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") sendMessage(); }} placeholder="Xabaringizni yozing..." /><button className="icon-btn" aria-label="Ovoz"><Mic /></button><button className="send-btn" onClick={sendMessage} aria-label="Yuborish"><Send /></button></div>
          </section>
          <footer><span><ShieldCheck /> Xavfsiz ulanish</span><span>Agent Umimiy · AI platformasi</span><button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>Mavzuni almashtirish</button></footer>
        </div>
      </main>
    </div>
  );
}

export default App;
