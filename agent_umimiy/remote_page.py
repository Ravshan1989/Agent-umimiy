"""Telefon uchun veb-sahifa (bitta fayl, tashqi kutubxonasiz)."""

PAGE = r"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d0f16">
<title>Agent Umimiy</title>
<style>
:root{--bg:#0d0f16;--side:#121521;--card:#1a1e2e;--hi:#232842;--line:#2a3047;--fg:#e8eaf4;--mut:#8b92ab;--acc:#7c6cff;--acc2:#9a8dff;--user:#5a49ee;--ok:#34d399;--err:#f87171;--warn:#fbbf24;--code:#080a10}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.45 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;display:flex;flex-direction:column;
 padding-left:env(safe-area-inset-left);padding-right:env(safe-area-inset-right)}
header{background:var(--side);padding:calc(8px + env(safe-area-inset-top)) 10px 8px;display:flex;gap:8px;align-items:center;border-bottom:1px solid var(--line)}
header select,header button{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:12px;padding:9px 10px;font:inherit}
header select{flex:1;min-width:0}header button{min-width:42px}
#sub{font-size:12px;color:var(--mut);padding:6px 14px;background:var(--bg);border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:8px}
#msgs{flex:1;overflow-y:auto;padding:12px 12px 4px;-webkit-overflow-scrolling:touch}
.row{display:flex;margin:10px 0;gap:8px}.row.u{justify-content:flex-end}
.av{width:30px;height:30px;border-radius:50%;flex:none;display:grid;place-items:center;font-weight:700;font-size:13px;color:#fff}
.col{min-width:0;max-width:86%}.nm{font-size:12px;font-weight:700;margin-bottom:3px}.nm span{color:var(--mut);font-weight:400;margin-left:6px}
.b{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:9px 12px;overflow-wrap:anywhere}
.u .b{background:var(--user);border-color:var(--user);color:#fff}.b.err{background:#2a1519;border-color:#5b2530;color:var(--err)}
.b p{margin:0 0 6px}.b p:last-child{margin:0}.b code{background:var(--code);color:#c9d1ff;padding:1px 5px;border-radius:5px;font:13px Consolas,monospace}
.b pre{background:var(--code);color:#c9d1ff;padding:8px 10px;border-radius:10px;overflow-x:auto;font:12.5px/1.4 Consolas,monospace;margin:6px 0}
.b h1,.b h2,.b h3{margin:6px 0 4px;font-size:16px}.b a{color:var(--acc2)}.b ul{margin:4px 0;padding-left:20px}
.act{font-size:12.5px;margin:3px 0 3px 38px;color:var(--mut)}.act.write{color:var(--warn)}.act.agent,.act.skill{color:var(--ok)}.act.run,.act.browser,.act.mcp{color:var(--acc2)}.act.info{color:var(--err)}
.todo{margin:8px 0 8px 38px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 12px;font-size:13.5px}
.todo b{color:var(--mut);font-size:12px;display:block;margin-bottom:3px}.todo .d{color:var(--mut)}
.typing{color:var(--mut);font-size:13px;margin:6px 0 6px 38px}
.files{font-size:12px;color:var(--mut);text-align:right;margin-bottom:3px}
#asks{padding:0 10px}.ask{background:var(--hi);border:1px solid var(--warn);border-radius:14px;padding:10px 12px;margin:8px 0}
.ask h4{margin:0 0 2px;font-size:12px;color:var(--warn)}.ask h3{margin:0 0 6px;font-size:15px}
.ask pre{background:var(--code);color:#c9d1ff;padding:8px;border-radius:8px;max-height:28vh;overflow:auto;font:12px/1.4 Consolas,monospace;white-space:pre-wrap;word-break:break-word;margin:0 0 8px}
.ask pre .a{color:var(--ok)}.ask pre .d{color:var(--err)}
.btns{display:flex;gap:8px}.btns button{flex:1;border:0;border-radius:11px;padding:11px 6px;font:600 14px inherit;color:#fff;background:var(--card)}
.btns .y{background:var(--acc)}.btns .n{color:var(--err)}.btns .al{border:1px solid var(--line)}
form{display:flex;gap:8px;align-items:flex-end;padding:8px 10px calc(8px + env(safe-area-inset-bottom));background:var(--side);border-top:1px solid var(--line)}
#chips{padding:6px 12px 0;display:flex;gap:6px;flex-wrap:wrap;background:var(--side)}.chip{background:var(--hi);border-radius:10px;padding:4px 9px;font-size:12px}
textarea{flex:1;resize:none;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:18px;padding:10px 14px;font:inherit;max-height:30vh;min-height:42px}
.rb{width:42px;height:42px;border-radius:50%;border:0;color:#fff;font-size:20px;flex:none;background:var(--hi)}.rb.send{background:var(--acc)}.rb.stop{background:var(--err)}
#banner{display:none;background:var(--err);color:#fff;text-align:center;font-size:13px;padding:4px}
.empty{text-align:center;color:var(--mut);margin-top:18vh}.empty div{font-size:40px}
</style></head><body>
<div id="banner">Ulanish yo'q — qayta urinilmoqda…</div>
<header><select id="chat" aria-label="Suhbat"></select><button id="new" title="Yangi suhbat">＋</button><button id="close" title="Suhbatni yopish">✕</button></header>
<div id="sub"><span id="proj"></span><select id="mode" style="background:transparent;color:var(--mut);border:0;font-size:12px"></select></div>
<div id="msgs"></div><div id="asks"></div><div id="chips"></div>
<form id="f"><input type="file" id="file" multiple hidden accept="image/*,.pdf,.docx,.txt,.md,.csv,.json,.py,.js,.html,.log">
<button type="button" class="rb" id="att" title="Fayl biriktirish">＋</button>
<textarea id="t" rows="1" placeholder="Xabar yozing…"></textarea>
<button type="submit" class="rb send" id="go" title="Yuborish">↑</button></form>
<script>
(function(){
var T=new URLSearchParams(location.search).get('t')||sessionStorage.getItem('t')||'';
try{sessionStorage.setItem('t',T)}catch(e){}
history.replaceState(null,'',location.pathname);
var $=function(i){return document.getElementById(i)};
var cur=null,since=0,busy=false,files=[],todoEl=null,typingEl=null,lastErr=0,COLORS=['#7c6cff','#22d3ee','#f59e0b','#ec4899','#34d399','#f97316','#60a5fa','#a3e635'];
function color(n){var s=0;for(var i=0;i<n.length;i++)s+=n.charCodeAt(i);return COLORS[s%8]}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function inl(s){s=esc(s);s=s.replace(/`([^`\n]+)`/g,'<code>$1</code>');s=s.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
 return s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')}
function md(t){var out=[],parts=String(t).split(/```[\w+-]*\n?([\s\S]*?)```/);
 for(var i=0;i<parts.length;i++){if(i%2){out.push('<pre>'+esc(parts[i].replace(/\n+$/,''))+'</pre>');continue}
  var lines=parts[i].split('\n'),list=false,tbl=[];
  var flush=function(){if(tbl.length){out.push('<pre>'+esc(tbl.join('\n'))+'</pre>');tbl=[]}};
  for(var j=0;j<lines.length;j++){var l=lines[j],m;
   if(/^\s*\|.*\|\s*$/.test(l)){tbl.push(l);continue}flush();
   if(m=l.match(/^(#{1,3})\s+(.*)$/)){if(list){out.push('</ul>');list=false}out.push('<h'+m[1].length+'>'+inl(m[2])+'</h'+m[1].length+'>')}
   else if(m=l.match(/^\s*[-*+]\s+(.*)$/)){if(!list){out.push('<ul>');list=true}out.push('<li>'+inl(m[1])+'</li>')}
   else{if(list){out.push('</ul>');list=false}if(l.trim())out.push('<p>'+inl(l)+'</p>')}}
  flush();if(list)out.push('</ul>')}
 return out.join('')}
function api(path,body){var o={headers:{'X-Token':T}};if(body!==undefined){o.method='POST';o.headers['Content-Type']='application/json';o.body=JSON.stringify(body)}
 return fetch(path,o).then(function(r){if(r.status===401){document.body.innerHTML='<div class="empty"><div>🔒</div><p>Kirish rad etildi.<br>Kompyuterdagi QR-kodni qayta skanerlang.</p></div>';throw new Error('401')}
  if(!r.ok)return r.json().then(function(j){throw new Error(j.error||r.status)});return r.json()})}
function scroll(){var m=$('msgs');m.scrollTop=m.scrollHeight}
function nearBottom(){var m=$('msgs');return m.scrollHeight-m.scrollTop-m.clientHeight<140}
function add(html,cls){var d=document.createElement('div');d.className=cls;d.innerHTML=html;$('msgs').appendChild(d);return d}
function rec(r){
 if(r.k==='user'){var f=(r.files&&r.files.length)?'<div class="files">▣ '+r.files.map(esc).join(' &nbsp; ▣ ')+'</div>':'';
  add('<div class="col">'+f+'<div class="b">'+md(r.text)+'</div></div>','row u')}
 else if(r.k==='agent'){var c=r.err?'var(--err)':color(String(r.name).split(' ')[0]);
  add('<div class="av" style="background:'+c+'">'+esc((r.name||'?')[0].toUpperCase())+'</div><div class="col"><div class="nm" style="color:'+c+'">'+esc(r.name)+(r.meta?'<span>'+esc(r.meta)+'</span>':'')+'</div><div class="b'+(r.err?' err':'')+'">'+md(r.text)+'</div></div>','row')}
 else if(r.k==='act'){if(r.kind==='todo'){try{var it=JSON.parse(r.text);if(todoEl)todoEl.remove();var dn=it.filter(function(x){return x.status==='completed'}).length;
   todoEl=add('<b>Reja · '+dn+'/'+it.length+'</b>'+it.map(function(x){var d=x.status==='completed';return '<div class="'+(d?'d':'')+'">'+(d?'☑':x.status==='in_progress'?'◐':'☐')+' '+esc(x.content)+'</div>'}).join(''),'todo')}catch(e){}}
  else add(esc((r.agent||'')+': '+r.text),'act '+esc(r.kind))}}
function diff(s){return esc(s).split('\n').map(function(l){return /^\+(?!\+\+)/.test(l)?'<span class="a">'+l+'</span>':/^-(?!--)/.test(l)?'<span class="d">'+l+'</span>':l}).join('\n')}
function renderAsks(asks){var box=$('asks');if(JSON.stringify(asks)===box.dataset.k)return;box.dataset.k=JSON.stringify(asks);box.innerHTML='';
 asks.forEach(function(a){var d=document.createElement('div');d.className='ask';
  d.innerHTML='<h4>'+esc(a.agent)+' ruxsat so\'ramoqda</h4><h3>'+esc(a.title)+'</h3><pre>'+diff(a.detail)+'</pre><div class="btns"><button class="n" data-a="no">Rad etish</button><button class="al" data-a="always">Doim</button><button class="y" data-a="yes">Ruxsat</button></div>';
  d.querySelectorAll('button').forEach(function(b){b.onclick=function(){d.querySelectorAll('button').forEach(function(x){x.disabled=true});api('/api/approve',{id:a.id,answer:b.dataset.a}).then(poll)}});box.appendChild(d)});
 if(asks.length&&nearBottom())scroll()}
function setBusy(b){busy=b;var g=$('go');g.className='rb '+(b?'stop':'send');g.textContent=b?'■':'↑';g.title=b?'To\'xtatish':'Yuborish'}
function chips(){var c=$('chips');c.innerHTML='';files.forEach(function(f,i){var s=document.createElement('span');s.className='chip';s.textContent='▣ '+f.name+' ✕';s.onclick=function(){files.splice(i,1);chips()};c.appendChild(s)})}
function render(s){
 $('banner').style.display='none';lastErr=0;
 var sel=$('chat');if(JSON.stringify(s.chats)!==sel.dataset.k){sel.dataset.k=JSON.stringify(s.chats);sel.innerHTML='';s.chats.forEach(function(c){var o=document.createElement('option');o.value=c.id;o.textContent=(c.busy?'● ':c.unread?'○ ':'')+c.title;sel.appendChild(o)});}
 if(cur===null||!s.chats.some(function(c){return c.id===cur})){cur=s.chat;since=0;$('msgs').innerHTML='';todoEl=null;typingEl=null}
 sel.value=cur;
 var ms=$('mode');if(!ms.options.length){Object.keys(s.modes).forEach(function(k){var o=document.createElement('option');o.value=k;o.textContent=s.modes[k];ms.appendChild(o)})}ms.value=s.mode;
 var ch=s.chats.filter(function(c){return c.id===cur})[0]||{};$('proj').textContent=ch.project?'Loyiha: '+ch.project.split(/[\\/]/).pop():s.agents.filter(function(a){return a.on}).length+' agent faol';
 if(s.reset){$('msgs').innerHTML='';todoEl=null;typingEl=null;since=0}
 var stick=nearBottom()||since===0;
 if(typingEl){typingEl.remove();typingEl=null}
 s.records.forEach(rec);since=s.total;
 if(!since&&!s.records.length&&!$('msgs').children.length)add('<div>✦</div><p>Qanday yordam bera olaman?<br>Xabar yozing.</p>','empty');
 else if(since&&$('msgs').querySelector('.empty'))$('msgs').querySelector('.empty').remove();
 if(s.busy)typingEl=add('● ● ●  '+esc((s.typing||[]).join(', '))+' yozmoqda…','typing');
 setBusy(s.busy);renderAsks(s.asks);if(stick)scroll()}
var polling=false;
function poll(){if(polling)return Promise.resolve();polling=true;
 return api('/api/state?chat='+(cur===null?'':cur)+'&since='+since).then(render).catch(function(e){if(e.message!=='401'){if(++lastErr>1)$('banner').style.display='block'}}).then(function(){polling=false})}
setInterval(function(){if(!document.hidden)poll()},1300);document.addEventListener('visibilitychange',poll);poll();
$('chat').onchange=function(){cur=Number(this.value);since=0;$('msgs').innerHTML='';todoEl=null;typingEl=null;poll()};
$('new').onclick=function(){api('/api/new',{}).then(function(r){cur=r.id;since=0;$('msgs').innerHTML='';poll()})};
$('close').onclick=function(){if(cur!==null)api('/api/close',{chat:cur}).then(function(){cur=null;poll()})};
$('mode').onchange=function(){api('/api/mode',{mode:this.value}).then(poll)};
$('att').onclick=function(){$('file').click()};
$('file').onchange=function(){Array.prototype.forEach.call(this.files,function(f){if(f.size>15*1024*1024){alert(f.name+': 15 MB dan katta');return}
 var r=new FileReader();r.onload=function(){files.push({name:f.name,data:String(r.result).split(',')[1]});chips()};r.readAsDataURL(f)});this.value=''};
var ta=$('t');ta.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,window.innerHeight*.3)+'px'});
$('f').onsubmit=function(e){e.preventDefault();
 if(busy){api('/api/stop',{chat:cur}).then(poll);return}
 var text=ta.value.trim();if(!text&&!files.length)return;
 var body={chat:cur,text:text,files:files};ta.value='';ta.style.height='auto';var sent=files;files=[];chips();
 api('/api/send',body).then(poll).catch(function(err){add(esc(err.message),'act info');files=sent;chips()})};
ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey&&!/Mobi|Android/i.test(navigator.userAgent)){e.preventDefault();$('f').requestSubmit()}});
})();
</script></body></html>
"""
