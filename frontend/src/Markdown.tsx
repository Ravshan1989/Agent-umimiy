import { Fragment, useState, type ReactNode } from "react";

// Kichik, xavfsiz markdown ko‘rsatgich: matn faqat React elementlari orqali chiqadi
// (dangerouslySetInnerHTML yo‘q), shuning uchun HTML avtomatik ekranlanadi.
// Qo‘llanadi: sarlavhalar, **qalin**, *kursiv*, `kod`, ```kod bloklari```, jadvallar, ro‘yxatlar, havolalar, > iqtibos.

const SAFE_URL = /^(https?:|mailto:|\/|#)/i;
const INLINE = /(`+)([^`]+?)\1|\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+?)\*\*|__([^_\n]+?)__|(?<![\w*])\*(?![\s*])([^*\n]+?)\*(?![\w*])|(?<![\w_])_(?![\s_])([^_\n]+?)_(?![\w_])|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g;

function inline(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const k = `${key}-${n++}`;
    if (m[2] !== undefined) out.push(<code key={k}>{m[2]}</code>);
    else if (m[3] !== undefined) {
      out.push(SAFE_URL.test(m[4]) ? <a key={k} href={m[4]} target="_blank" rel="noreferrer noopener">{inline(m[3], k)}</a> : <Fragment key={k}>{m[0]}</Fragment>);
    } else if (m[5] !== undefined || m[6] !== undefined) out.push(<strong key={k}>{inline(m[5] ?? m[6], k)}</strong>);
    else if (m[7] !== undefined || m[8] !== undefined) out.push(<em key={k}>{inline(m[7] ?? m[8], k)}</em>);
    else if (m[9] !== undefined) out.push(<a key={k} href={m[9]} target="_blank" rel="noreferrer noopener">{m[9]}</a>);
    last = at + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function withBreaks(lines: string[], key: string): ReactNode[] {
  return lines.flatMap((line, i) => i ? [<br key={`${key}-br${i}`} />, ...inline(line, `${key}-${i}`)] : inline(line, `${key}-${i}`));
}

function CodeBlock({ lang, code, onRunCode }: { lang: string; code: string; onRunCode?: (code: string) => Promise<string> }) {
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState(false);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const norm = (lang || "text").toLowerCase();
  const canRun = Boolean(onRunCode && (norm === "python" || norm === "py"));
  const canPreview = norm === "html" || norm === "svg";

  function copy() {
    void navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    });
  }

  async function run() {
    if (!onRunCode || running) return;
    setRunning(true);
    try {
      setOutput(await onRunCode(code));
    } catch (e) {
      setOutput((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="md-code-wrap">
      <div className="md-code-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 10px", fontSize: "12px", opacity: 0.88, borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <b style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>{lang || "kod"}</b>
        <div style={{ display: "flex", gap: "8px" }}>
          {canPreview && <button type="button" className="text-link" onClick={() => setPreview(!preview)}>{preview ? "Kodni ko‘rish" : "👁 Ko‘rish"}</button>}
          {canRun && <button type="button" className="text-link" onClick={() => void run()} disabled={running}>{running ? "Ishlamoqda…" : "▶ Ishga tushirish"}</button>}
          <button type="button" className="text-link" onClick={copy}>{copied ? "✓ Nusxalandi" : "📋 Nusxalash"}</button>
        </div>
      </div>
      {preview ? (
        <iframe title="HTML preview" sandbox="" srcDoc={code} style={{ width: "100%", minHeight: "220px", border: "none", borderRadius: "6px", background: "#fff" }} />
      ) : (
        <pre><code>{code}</code></pre>
      )}
      {output !== null && (
        <pre style={{ marginTop: "6px", borderLeft: "3px solid #22c55e", paddingLeft: "10px", fontSize: "12px" }}>
          <code>Natija:\n{output}</code>
        </pre>
      )}
    </div>
  );
}

const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_SEP = /^\s*\|[\s:|-]+\|\s*$/;
const BLOCK_START = /^\s*(#{1,6}\s|>|```|~~~|\|.*\|)/;

export function Markdown({ text, onRunCode }: { text: string; onRunCode?: (code: string) => Promise<string> }) {
  const lines = (text || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = `b${i}`;
    const fence = line.match(/^\s*(```|~~~)\s*([\w+#.-]*)\s*$/);
    if (fence) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) body.push(lines[i++]);
      i++;  // yopuvchi ``` (javob hali oqib kelayotgan bo‘lsa, bo‘lmasligi mumkin)
      blocks.push(<CodeBlock key={key} lang={fence[2]} code={body.join("\n")} onRunCode={onRunCode} />);
      continue;
    }
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      const parseCells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const headers = parseCells(lines[i]);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(parseCells(lines[i++]));
      blocks.push(
        <div key={key} style={{ overflowX: "auto", margin: "8px 0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr>{headers.map((h, idx) => <th key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.18)", padding: "6px 10px", textAlign: "left" }}>{inline(h, `${key}-h${idx}`)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, rIdx) => <tr key={rIdx}>{r.map((c, cIdx) => <td key={cIdx} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "6px 10px" }}>{inline(c, `${key}-r${rIdx}-${cIdx}`)}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      );
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const heading = line.match(/^\s*(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      const Tag = `h${Math.min(heading[1].length + 2, 6)}` as "h3" | "h4" | "h5" | "h6";
      blocks.push(<Tag key={key} className={`md-h${heading[1].length}`}>{inline(heading[2], key)}</Tag>);
      i++;
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { blocks.push(<hr key={key} />); i++; continue; }
    if (/^\s*>/.test(line)) {
      const body: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) body.push(lines[i++].replace(/^\s*>\s?/, ""));
      blocks.push(<blockquote key={key}>{withBreaks(body, key)}</blockquote>);
      continue;
    }
    const first = line.match(LIST_ITEM);
    if (first) {
      const ordered = /\d/.test(first[2]);
      const items: { indent: number; text: string[] }[] = [];
      while (i < lines.length) {
        const m = lines[i].match(LIST_ITEM);
        if (m) { items.push({ indent: m[1].length, text: [m[3]] }); i++; continue; }
        if (items.length && lines[i].trim() && /^\s+/.test(lines[i]) && !BLOCK_START.test(lines[i])) { items[items.length - 1].text.push(lines[i].trim()); i++; continue; }
        break;
      }
      const base = Math.min(...items.map((it) => it.indent));
      const List = ordered ? "ol" : "ul";
      blocks.push(<List key={key}>{items.map((it, n) => <li key={n} style={it.indent > base ? { marginLeft: Math.min(it.indent - base, 8) * 6 } : undefined}>{withBreaks(it.text, `${key}-${n}`)}</li>)}</List>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !LIST_ITEM.test(lines[i]) && !BLOCK_START.test(lines[i])) para.push(lines[i++]);
    if (!para.length) para.push(lines[i++]);
    blocks.push(<p key={key}>{withBreaks(para, key)}</p>);
  }
  return <div className="md">{blocks}</div>;
}
