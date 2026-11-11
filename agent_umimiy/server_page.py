"""Veb-server sahifasi: kirish, suhbatlar ro'yxati va oqimli chat (bitta fayl, tashqi kutubxonasiz)."""

PAGE = r"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d0f16">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Agent Umimiy">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<title>Agent Umimiy</title>
<style>
:root{--bg:#0d0f16;--side:#121521;--card:#1a1e2e;--hi:#232842;--line:#2a3047;--fg:#e8eaf4;--mut:#8b92ab;--acc:#7c6cff;--acc2:#9a8dff;--user:#5a49ee;--ok:#34d399;--err:#f87171;--warn:#fbbf24;--code:#080a10}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif}
button,select,input,textarea{font:inherit;color:inherit}button{cursor:pointer}
[hidden]{display:none!important}
#auth{height:100%;display:grid;place-items:center;padding:20px}
#auth form{width:100%;max-width:340px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px;display:flex;flex-direction:column;gap:12px}
#auth h1{margin:0;font-size:20px}#auth p{margin:0;color:var(--mut);font-size:13px}
#auth input{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:11px 12px;width:100%}
#auth button[type=submit]{background:var(--acc);border:0;border-radius:10px;padding:11px;font-weight:600;color:#fff}
#auth .sw{background:none;border:0;color:var(--acc2);font-size:13px;padding:0;text-align:left}
#aerr{color:var(--err);font-size:13px;min-height:18px}
#app{height:100%;display:flex}
aside{width:270px;flex:none;background:var(--side);border-right:1px solid var(--line);display:flex;flex-direction:column}
aside .top{padding:calc(14px + env(safe-area-inset-top)) 14px 14px;display:flex;flex-direction:column;gap:10px}
aside h2{margin:0;font-size:16px}
#new{background:var(--acc);border:0;border-radius:10px;padding:10px;color:#fff;font-weight:600}
#chats{flex:1;overflow-y:auto;padding:0 8px}
.chat{display:flex;align-items:center;border-radius:9px;padding:0 4px 0 10px;margin:2px 0;color:var(--mut)}
.chat:hover,.chat.on{background:var(--hi);color:var(--fg)}
.chat span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:9px 0;cursor:pointer}
.chat button{background:none;border:0;color:var(--mut);padding:6px 8px;visibility:hidden}.chat:hover button,.chat.on button{visibility:visible}
aside .me{padding:12px 14px calc(12px + env(safe-area-inset-bottom));border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;font-size:13px;gap:8px}
#user{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#out{background:none;border:1px solid var(--line);border-radius:8px;padding:5px 10px;color:var(--mut);flex:none}
main{flex:1;min-width:0;display:flex;flex-direction:column}
main header{display:flex;align-items:center;gap:10px;padding:calc(10px + env(safe-area-inset-top)) 16px 10px;border-bottom:1px solid var(--line)}
#menu{display:none;background:none;border:1px solid var(--line);border-radius:9px;padding:6px 11px}
#agent{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;max-width:100%}
#msgs{flex:1;overflow-y:auto;padding:18px 16px 6px}
#msgs>*{max-width:820px;margin-left:auto;margin-right:auto}
.row{display:flex;margin:14px auto;gap:10px}.row.u{justify-content:flex-end}
.av{width:32px;height:32px;border-radius:50%;flex:none;display:grid;place-items:center;font-weight:700;font-size:13px;color:#fff}
.col{min-width:0;max-width:86%}.nm{font-size:12px;font-weight:700;margin-bottom:3px}.nm span{color:var(--mut);font-weight:400;margin-left:6px}
.b{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:10px 14px;overflow-wrap:anywhere}
.u .b{background:var(--user);border-color:var(--user);color:#fff}.b.err{background:#2a1519;border-color:#5b2530;color:var(--err)}
.b p{margin:0 0 8px}.b p:last-child{margin:0}.b code{background:var(--code);color:#c9d1ff;padding:1px 5px;border-radius:5px;font:13px Consolas,monospace}
.b pre{background:var(--code);color:#c9d1ff;padding:10px 12px;border-radius:10px;overflow-x:auto;font:13px/1.45 Consolas,monospace;margin:8px 0}
.b h1,.b h2,.b h3{margin:8px 0 4px;font-size:16px}.b a{color:var(--acc2)}.b ul{margin:4px 0;padding-left:22px}
.cp{background:none;border:0;color:var(--mut);font-size:12px;padding:3px 0}
.act{font-size:12.5px;margin:3px auto;padding-left:42px;color:var(--mut)}.act.info{color:var(--err)}.act.agent,.act.skill{color:var(--ok)}
.files{font-size:12px;color:var(--mut);text-align:right;margin-bottom:3px}
.typing{color:var(--mut);font-size:13px;padding-left:42px;margin:8px auto}
.empty{text-align:center;color:var(--mut);margin-top:22vh}.empty div{font-size:40px}
#chips{display:flex;gap:6px;flex-wrap:wrap;padding:0 16px;max-width:852px;width:100%;margin:0 auto}
.chip{background:var(--hi);border-radius:10px;padding:4px 9px;font-size:12px;cursor:pointer}
#f{display:flex;gap:8px;align-items:flex-end;padding:10px 16px calc(14px + env(safe-area-inset-bottom));max-width:852px;width:100%;margin:0 auto}
textarea{flex:1;resize:none;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:11px 14px;max-height:30vh;min-height:46px}
.rb{width:46px;height:46px;border-radius:50%;border:0;color:#fff;font-size:20px;flex:none;background:var(--hi)}.rb.send{background:var(--acc)}.rb.stop{background:var(--err)}
#banner{background:var(--err);color:#fff;text-align:center;font-size:13px;padding:4px}
@media(max-width:760px){aside{position:fixed;inset:0 auto 0 0;z-index:5;transform:translateX(-100%);transition:transform .15s}
 aside.open{transform:none;box-shadow:0 0 0 100vmax rgba(0,0,0,.5)}#menu{display:block}}
</style></head><body>
<div id="auth" hidden><form id="af">
 <h1>Agent Umimiy</h1><p id="ahint"></p>
 <input id="aname" placeholder="Ism" autocomplete="username" required>
 <input id="apass" type="password" placeholder="Parol" required>
 <input id="ainv" placeholder="Taklif kodi" autocomplete="off" hidden>
 <div id="aerr"></div>
 <button type="submit" id="ago"></button>
 <button type="button" class="sw" id="asw"></button>
</form></div>
<div id="app" hidden>
 <aside id="side"><div class="top"><h2>Agent Umimiy</h2><button id="new">+ Yangi suhbat</button></div>
  <div id="chats"></div>
  <div class="me"><span id="user"></span><button id="out">Chiqish</button></div></aside>
 <main><div id="banner" hidden>Ulanish yo'q — qayta urinilmoqda…</div>
  <header><button id="menu" aria-label="Suhbatlar">☰</button><select id="agent" aria-label="Agent"></select></header>
  <div id="msgs"></div><div id="chips"></div>
  <form id="f"><input type="file" id="file" multiple hidden accept="image/*,.pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.json,.py,.js,.html,.log">
   <button type="button" class="rb" id="att" title="Fayl biriktirish">+</button>
   <textarea id="t" rows="1" placeholder="Xabar yozing…"></textarea>
   <button type="submit" class="rb send" id="go" title="Yuborish">↑</button></form></main>
</div>
<script>
(function(){
var $=function(i){return document.getElementById(i)};
var cur=null,es=null,busy=false,files=[],live={},typingEl=null,reg=false,MAX_FILE=15*1024*1024;
var COLORS=['#7c6cff','#22d3ee','#f59e0b','#ec4899','#34d399','#f97316','#60a5fa','#a3e635'];
function color(n){var s=0;for(var i=0;i<n.length;i++)s+=n.charCodeAt(i);return COLORS[s%8]}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function inl(s){s=esc(s);s=s.replace(/`([^`\n]+)`/g,'<code>$1</code>');s=s.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
 return s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')}
function md(t){var out=[],parts=String(t).split(/```[\w+-]*\n?([\s\S]*?)(?:```|$)/);
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
function api(path,body){var o={};if(body!==undefined)o={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
 return fetch(path,o).then(function(r){return r.json().then(function(j){if(!r.ok){var e=new Error(j.error||('Xato '+r.status));e.code=r.status;throw e}return j})})}

// ---- kirish ----
function authMode(r){reg=r;$('ainv').hidden=!r;$('ago').textContent=r?"Ro'yxatdan o'tish":'Kirish';
 $('asw').textContent=r?'Hisobim bor — kirish':"Hisobim yo'q — ro'yxatdan o'tish";
 $('ahint').textContent=r?"Taklif kodini server egasidan so'rang. Parol kamida 8 belgi.":'Ism va parolingizni kiriting.';
 $('apass').autocomplete=r?'new-password':'current-password';$('aerr').textContent=''}
function showAuth(){if(es){es.close();es=null}$('app').hidden=true;$('auth').hidden=false;authMode(false)}
$('asw').onclick=function(){authMode(!reg)};
$('af').onsubmit=function(e){e.preventDefault();
 api(reg?'/api/register':'/api/login',{name:$('aname').value,password:$('apass').value,invite:$('ainv').value})
  .then(function(){$('apass').value='';boot()}).catch(function(err){$('aerr').textContent=err.message})};
$('out').onclick=function(){api('/api/logout',{}).then(showAuth)};

// ---- suhbatlar ro'yxati ----
function renderChats(chats){var box=$('chats');box.innerHTML='';
 chats.forEach(function(c){var d=document.createElement('div');d.className='chat'+(c.id===cur?' on':'');
  var s=document.createElement('span');s.textContent=c.title||'Yangi suhbat';s.onclick=function(){openChat(c.id)};
  var x=document.createElement('button');x.textContent='✕';x.title="O'chirish";
  x.onclick=function(){if(!confirm("Suhbat o'chirilsinmi?"))return;
   api('/api/chat/delete',{chat:c.id}).then(function(){if(cur===c.id)newChat();refresh()}).catch(function(e){alert(e.message)})};
  d.appendChild(s);d.appendChild(x);box.appendChild(d)})}
function refresh(){return api('/api/me').then(function(me){renderChats(me.chats);return me}).catch(function(e){if(e.code===401)showAuth()})}
function boot(){api('/api/me').then(function(me){$('auth').hidden=true;$('app').hidden=false;$('user').textContent=me.user;
  var sel=$('agent'),keep=sel.value;sel.innerHTML='';
  me.agents.forEach(function(a){var o=document.createElement('option');o.value=a.name;o.textContent=a.name+(a.model?' · '+a.model:'');sel.appendChild(o)});
  if(keep)sel.value=keep;renderChats(me.chats);if(cur===null)newChat()}).catch(function(e){if(e.code===401)showAuth();else{showAuth();$('aerr').textContent=e.message}})}

// ---- xabarlar ----
function nearBottom(){var m=$('msgs');return m.scrollHeight-m.scrollTop-m.clientHeight<160}
function scroll(){var m=$('msgs');m.scrollTop=m.scrollHeight}
function add(html,cls){var d=document.createElement('div');d.className=cls;d.innerHTML=html;
 var e=$('msgs').querySelector('.empty');if(e)e.remove();$('msgs').appendChild(d);return d}
function copy(text,btn){var t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();
 try{document.execCommand('copy');btn.textContent='Nusxalandi ✓'}catch(e){}t.remove()}
function agentRow(name,meta,html,err){var c=err?'var(--err)':color(String(name).split(' ')[0]);
 return add('<div class="av" style="background:'+c+'">'+esc((name||'?')[0].toUpperCase())+'</div><div class="col"><div class="nm" style="color:'+c+'">'+esc(name)+(meta?'<span>'+esc(meta)+'</span>':'')+'</div><div class="b'+(err?' err':'')+'">'+html+'</div></div>','row')}
function rec(r){
 if(r.k==='user'){var f=(r.files&&r.files.length)?'<div class="files">▣ '+r.files.map(esc).join(' &nbsp; ▣ ')+'</div>':'';
  add('<div class="col">'+f+'<div class="b">'+md(r.text)+'</div></div>','row u')}
 else if(r.k==='agent'){var row=agentRow(r.name,r.meta,md(r.text),r.err);
  if(!r.err){var b=document.createElement('button');b.className='cp';b.textContent='Nusxalash';b.onclick=function(){copy(r.text,b)};row.querySelector('.col').appendChild(b)}}
 else if(r.k==='act'&&r.kind!=='todo')add(esc((r.agent||'')+': '+r.text),'act '+esc(r.kind))}
function setLive(agent,text){var l=live[agent];
 if(!l)l=live[agent]={text:'',el:agentRow(agent,'','',false)};
 l.text=text;l.el.querySelector('.b').innerHTML=md(text)}
function dropLive(agent){if(live[agent]){live[agent].el.remove();delete live[agent]}}
function dropAllLive(){Object.keys(live).forEach(dropLive)}
function typing(){if(typingEl){typingEl.remove();typingEl=null}
 if(busy&&!Object.keys(live).length)typingEl=add('● ● ●  yozmoqda…','typing')}
function setBusy(b){busy=b;var g=$('go');g.className='rb '+(b?'stop':'send');g.textContent=b?'■':'↑';g.title=b?"To'xtatish":'Yuborish';typing()}
function clearMsgs(){$('msgs').innerHTML='';live={};typingEl=null}
function handle(ev){var stick=nearBottom();
 if(ev.type==='init'){clearMsgs();ev.records.forEach(rec);Object.keys(ev.live).forEach(function(a){if(ev.live[a])setLive(a,ev.live[a])});setBusy(ev.busy);
  if(!ev.records.length&&!ev.busy)empty();stick=true}
 else if(ev.type==='record'){if(ev.record.k==='agent')dropAllLive();rec(ev.record);typing()}
 else if(ev.type==='delta'){setLive(ev.agent,((live[ev.agent]||{}).text||'')+ev.text);typing()}
 else if(ev.type==='turn'){dropLive(ev.agent);typing()}
 else if(ev.type==='busy')setBusy(true)
 else if(ev.type==='done'){dropAllLive();setBusy(false);refresh()}
 if(stick)scroll()}
function empty(){add('<div>✦</div><p>Qanday yordam bera olaman?</p>','empty')}
function openChat(id){cur=id;if(es)es.close();clearMsgs();setBusy(false);$('side').classList.remove('open');
 es=new EventSource('/api/stream?chat='+id);
 es.onmessage=function(e){$('banner').hidden=true;handle(JSON.parse(e.data))};
 es.onerror=function(){$('banner').hidden=false;api('/api/me').catch(function(e){if(e.code===401)showAuth()})};
 es.onopen=function(){$('banner').hidden=true};refresh()}
function newChat(){cur=null;if(es){es.close();es=null}clearMsgs();setBusy(false);empty();$('side').classList.remove('open');
 Array.prototype.forEach.call($('chats').children,function(d){d.classList.remove('on')});$('t').focus()}
$('new').onclick=newChat;$('menu').onclick=function(){$('side').classList.toggle('open')};
$('msgs').onclick=function(){$('side').classList.remove('open')};

// ---- fayllar ----
function chips(){var c=$('chips');c.innerHTML='';files.forEach(function(f,i){var s=document.createElement('span');s.className='chip';s.textContent='▣ '+f.name+' ✕';s.onclick=function(){files.splice(i,1);chips()};c.appendChild(s)})}
function addFile(f,name){if(f.size>MAX_FILE){alert((name||f.name)+': 15 MB dan katta');return}
 var r=new FileReader();r.onload=function(){files.push({name:name||f.name,data:String(r.result).split(',')[1]});chips()};r.readAsDataURL(f)}
$('att').onclick=function(){$('file').click()};
$('file').onchange=function(){Array.prototype.forEach.call(this.files,function(f){addFile(f)});this.value=''};
var ta=$('t');
ta.addEventListener('paste',function(e){var items=(e.clipboardData||{}).items||[];
 for(var i=0;i<items.length;i++){if(items[i].kind==='file'){var f=items[i].getAsFile();
  if(f){e.preventDefault();addFile(f,f.name&&f.name!=='image.png'?f.name:'skrinshot-'+Date.now()+'.png')}}}});
ta.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,window.innerHeight*.3)+'px'});
ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey&&!/Mobi|Android/i.test(navigator.userAgent)){e.preventDefault();$('f').requestSubmit()}});

// ---- yuborish ----
function fail(err,text,sent){add(esc(err.message),'act info');scroll();if(!ta.value)ta.value=text;files=sent;chips();if(err.code===401)showAuth()}
$('f').onsubmit=function(e){e.preventDefault();
 if(busy){api('/api/stop',{chat:cur}).catch(function(){});return}
 var text=ta.value.trim();if(!text&&!files.length)return;
 var sent=files;files=[];chips();ta.value='';ta.style.height='auto';
 var ready=cur===null?api('/api/chat/new',{}).then(function(r){openChat(r.id);return r.id}):Promise.resolve(cur);
 ready.then(function(id){return api('/api/send',{chat:id,text:text,agent:$('agent').value,files:sent})})
  .catch(function(err){fail(err,text,sent)})};
boot();
})();
</script></body></html>
"""
