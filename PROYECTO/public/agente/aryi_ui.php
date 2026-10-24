<?php
/**
 * aryi_ui.php — Interfaz de voz compartida (index.php y area_privada.php).
 * Variables esperadas: $autenticado, $error_msg, $csrf_token, $DEFAULT_OLLAMA_MODEL,
 * $UI_LOGOUT (url), $UI_USER (?string), $UI_ARCHIVADOR (?ruta a parcial), $flash (opcional).
 */
$UI_LOGOUT     = $UI_LOGOUT     ?? '?salir=true';
$UI_USER       = $UI_USER       ?? null;
$UI_ARCHIVADOR = $UI_ARCHIVADOR ?? null;
$h = fn($v) => htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8');
$openFiles = $UI_ARCHIVADOR && (isset($_GET['path']) || !empty($flash));
?>
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Aryi</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet">
<style>
:root{--ink:#0A0F1A;--lift:#122038;--tx:#E8EEF8;--mu:#8190A8;--ln:rgba(232,238,248,.11);--listen:#46D9F0;--think:#A592FF;--speak:#FFC978;--ok:#5FE0A0;--err:#FF7A7A;
--primary:var(--listen);--accent-green:var(--ok);--text-muted:var(--mu);--c:var(--mu);
--serif:"Newsreader",Georgia,serif;--sans:"Hanken Grotesk",system-ui,sans-serif}
body[data-s=listening]{--c:var(--listen)}body[data-s=thinking]{--c:var(--think)}body[data-s=speaking]{--c:var(--speak)}
*{box-sizing:border-box}[hidden]{display:none!important}
html,body{height:100%;margin:0}
body{background:radial-gradient(60vmax 50vmax at 50% 42%,var(--lift),var(--ink) 70%);color:var(--tx);font:400 .86rem/1.4 var(--sans);overflow:hidden}
button,input,select,textarea{font:inherit;color:inherit}
button{cursor:pointer;background:none;border:0;padding:0}
:focus-visible{outline:2px solid var(--c);outline-offset:3px;border-radius:6px}
.app{height:100dvh;display:grid;grid-template:"top top top" auto "l core r" 1fr "dock dock dock" auto/minmax(150px,230px) minmax(0,1fr) minmax(150px,230px);padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
.top{grid-area:top;display:flex;justify-content:space-between;align-items:center;gap:14px;padding:16px 22px;flex-wrap:wrap}
.who{display:flex;align-items:baseline;gap:12px}.who b{font:500 1.35rem var(--serif);letter-spacing:.01em}
#state{color:var(--c);transition:color .4s}
.nav{display:flex;align-items:center;flex-wrap:wrap;gap:6px 16px;color:var(--mu);min-width:0}
.nav a,.nav button{color:var(--mu);text-decoration:none}.nav a:hover,.nav button:hover{color:var(--tx)}
.svc{display:inline-flex;align-items:center;gap:6px;color:var(--mu)}.svc i{width:7px;height:7px;border-radius:50%;background:var(--mu);opacity:.5}
.svc.on i{background:var(--ok);opacity:1}.svc.off i{background:var(--err);opacity:1}
.rail{align-self:center;padding:0 22px;color:var(--mu);display:flex;flex-direction:column;gap:14px}
.rail.l{grid-area:l}.rail.r{grid-area:r;text-align:right;align-items:flex-end}
.rail h2{margin:0 0 4px;font:700 .72rem var(--sans);color:var(--mu);letter-spacing:.02em}
.m{display:grid;gap:3px;min-width:130px}.m>div{display:flex;justify-content:space-between;gap:10px}.m b{color:var(--tx);font-weight:500;font-variant-numeric:tabular-nums}
.m .bar{height:2px;background:var(--ln);border-radius:2px;overflow:hidden}.m .bar i{display:block;height:100%;width:0;background:var(--mu);transition:width .8s}
.m.run .bar i{background:var(--c)}.m.run>div:first-child span{color:var(--tx)}
#vram.hot{color:var(--tx)}.rail button.mini{color:var(--mu);text-decoration:underline;text-underline-offset:3px;font-size:.78rem;padding:0}.rail button.mini:hover{color:var(--tx)}
.core{grid-area:core;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;min-height:0;padding:0 12px;text-align:center}
#orb{border-radius:50%;line-height:0}#cv{width:min(46vmin,360px);aspect-ratio:1;display:block}
#phase{overflow-wrap:anywhere;margin:0;min-height:1.3em;color:var(--mu);font-variant-numeric:tabular-nums}
#phase button{margin-left:10px;color:var(--c);text-decoration:underline;text-underline-offset:3px}
#you{overflow-wrap:anywhere;margin:6px 0 0;color:var(--mu);max-width:60ch}
#say{overflow-wrap:anywhere;width:100%;font:400 clamp(1.1rem,2.2vw,1.5rem)/1.5 var(--serif);max-width:60ch;max-height:26vh;overflow:auto;white-space:pre-wrap;text-align:left;padding:0 6px}
#hint{margin:0;color:var(--mu);max-width:44ch}
#err{display:flex;gap:10px;align-items:center;color:var(--err);margin:0}#err button{color:var(--mu)}
.dock{grid-area:dock;padding:8px 22px 20px;display:flex;flex-direction:column;align-items:center;gap:10px}
#chips{min-height:1.2em;color:var(--mu);font-variant-numeric:tabular-nums;display:flex;gap:16px;flex-wrap:wrap;justify-content:center}
#f{display:flex;width:min(640px,100%);border-bottom:1px solid var(--ln)}#f:focus-within{border-color:var(--c)}
#txt{flex:1;background:none;border:0;padding:10px 2px;outline:0}#txt::placeholder{color:var(--mu)}
#f button{color:var(--mu);padding:0 4px}#f button:hover{color:var(--tx)}
#img{position:fixed;right:22px;bottom:92px;margin:0;width:min(250px,60vw);background:var(--lift);border:1px solid var(--ln);border-radius:12px;padding:8px}
#img img{width:100%;border-radius:8px;display:block;cursor:zoom-in}#imgcap{color:var(--mu);font-size:.72rem;margin:6px 2px;max-height:4.2em;overflow:auto}
#img div{display:flex;justify-content:space-between}#img a,#img button{color:var(--mu);font-size:.78rem}
#dr{position:fixed;inset:0 0 0 auto;width:min(420px,100%);background:#0D1626;border-left:1px solid var(--ln);display:flex;flex-direction:column;z-index:5}
#dr header{display:flex;gap:16px;padding:16px 18px;border-bottom:1px solid var(--ln)}#dr header button{color:var(--mu)}#dr header button[aria-selected=true]{color:var(--tx);border-bottom:2px solid var(--c)}#dr header .x{margin-left:auto}
#dr section{padding:16px 18px;overflow:auto;flex:1}
label.f{display:grid;gap:5px;margin-bottom:12px;color:var(--mu)}label.c{display:flex;gap:8px;margin-bottom:10px;color:var(--tx)}
#dr select,#dr input[type=text],#dr input[type=number],#dr textarea{width:100%;background:rgba(0,0,0,.35);border:1px solid var(--ln);border-radius:8px;padding:8px 10px}
#dr select option{background:#0D1626}
.hi{padding:10px 0;border-bottom:1px solid var(--ln);cursor:pointer}.hi small{color:var(--mu);display:flex;justify-content:space-between}.hi p{margin:2px 0;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.tools{display:flex;gap:16px;margin-bottom:8px}.tools button{color:var(--mu);text-decoration:underline;text-underline-offset:3px}
table.tabla{width:100%;border-collapse:collapse;margin-top:10px}table.tabla td,table.tabla th{padding:7px 4px;border-bottom:1px solid var(--ln);text-align:left}
[data-p=files] a{color:var(--listen)}[data-p=files] .outline,[data-p=files] .danger-outline,[data-p=files] button{border:1px solid var(--ln);border-radius:6px;padding:4px 8px;color:var(--tx);text-decoration:none;display:inline-block}
[data-p=files] input[type=text]{flex:1;min-width:0}.toast-error{border:1px solid var(--ok);color:var(--ok);padding:8px;border-radius:8px;margin-bottom:8px}
#lb{position:fixed;inset:0;background:rgba(5,8,14,.92);display:grid;place-items:center;z-index:9;cursor:zoom-out}#lb img{max-width:94vw;max-height:94vh;border-radius:10px}
.login{height:100dvh;display:grid;place-items:center;padding:20px}.login form{display:grid;gap:14px;width:min(320px,100%);text-align:center}
.login h1{font:500 2.4rem var(--serif);margin:0}.login input{background:none;border:0;border-bottom:1px solid var(--ln);padding:10px 2px;text-align:center;outline:0}.login input:focus{border-color:var(--listen)}
.login button{color:var(--listen);padding:8px}.login p{margin:0;color:var(--err)}
@media(max-width:899px){.app{grid-template:"top" auto "core" minmax(0,1fr) "r" auto "dock" auto/minmax(0,1fr)}.rail.r>div{min-width:0}.rail.l{display:none}.rail.r{flex-direction:row;flex-wrap:wrap;gap:6px 18px;text-align:left;justify-content:center;padding:0 16px}.rail.r h2{display:none}.top{padding:12px 16px}#img{bottom:120px;right:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body data-s="idle">
<?php if (empty($autenticado)): ?>
<div class="login">
  <form method="POST" autocomplete="off">
    <h1>Aryi</h1>
    <?php if (!empty($error_msg)): ?><p role="alert"><?= $h($error_msg) ?></p><?php endif; ?>
    <input type="password" name="password" placeholder="Clave de operador" aria-label="Clave de operador" required autofocus>
    <button type="submit">Entrar</button>
  </form>
</div>
<?php else: ?>
<div class="app">
  <header class="top">
    <div class="who"><b>Aryi</b><span id="state" role="status" aria-live="polite">En espera</span></div>
    <nav class="nav" aria-label="Sistema">
      <span class="svc" data-s="stt"><i></i>Oído</span><span class="svc" data-s="ollama"><i></i>Cerebro</span><span class="svc" data-s="tts"><i></i>Voz</span><span class="svc" data-s="sd"><i></i>Imagen</span>
      <button data-open="hist">Historial</button><button data-open="set">Ajustes</button>
      <?php if ($UI_ARCHIVADOR): ?><button data-open="files">Archivos</button><?php endif; ?>
      <?php if ($UI_USER): ?><span title="Sesión verificada"><?= $h($UI_USER) ?></span><?php endif; ?>
        <code class="hash-box"><?php echo htmlspecialchars($accessKey); ?></code>
      <a href="https://syntaxsanctuary.com" id="out">127.0.0.1</a>
      <a href="<?= $h($UI_LOGOUT) ?>" id="out">Salir</a>
    </nav>
  </header>

  <aside class="rail l" aria-label="Tiempos medios por motor">
    <h2>Tiempo medio</h2>
    <?php foreach (['stt'=>'Oído','ollama'=>'Cerebro','tts'=>'Voz','sd'=>'Imagen'] as $k=>$n): ?>
    <div class="m" id="m-<?= $k ?>"><div><span><?= $n ?></span><b>–</b></div><div class="bar"><i></i></div></div>
    <?php endforeach; ?>
  </aside>

  <main class="core">
    <button id="orb" aria-label="Hablar con Aryi. Toca para empezar o terminar; barra espaciadora también"><canvas id="cv"></canvas></button>
    <p id="phase" aria-live="off"></p>
    <p id="err" hidden><span></span><button aria-label="Cerrar aviso">Cerrar</button></p>
    <p id="you"></p>
    <div id="say" aria-live="polite"></div>
    <p id="hint">Toca el orbe y habla, o escribe abajo. Prueba «dibuja un faro al amanecer» o «libera la memoria de video».</p>
  </main>

  <aside class="rail r" aria-label="Cola y memoria de video">
    <div><h2>Cola</h2><span id="queue">GPU libre</span></div>
    <div><h2>Memoria de video</h2><span id="vram">Libre</span><br><button class="mini" id="free">Liberar</button></div>
  </aside>

  <footer class="dock">
    <div id="chips" aria-live="off"></div>
    <form id="f"><input id="txt" type="text" placeholder="Escribe aquí si prefieres no hablar" aria-label="Mensaje para Aryi" autocomplete="off"><button type="submit">Enviar</button></form>
  </footer>
</div>

<figure id="img" hidden>
  <img id="pic" alt="Imagen generada por Aryi"><figcaption id="imgcap"></figcaption>
  <div><a id="dl" href="#" download="aryi_render.png">Descargar</a><button id="imgx">Cerrar</button></div>
</figure>

<aside id="dr" hidden aria-label="Panel lateral">
  <header role="tablist">
    <button data-tab="hist" role="tab">Historial</button><button data-tab="set" role="tab">Ajustes</button>
    <?php if ($UI_ARCHIVADOR): ?><button data-tab="files" role="tab">Archivos</button><?php endif; ?>
    <button class="x" id="drx" aria-label="Cerrar panel">Cerrar</button>
  </header>
  <section data-p="hist" hidden>
    <div class="tools"><button id="exp">Exportar</button><button id="clr">Borrar historial</button></div>
    <div id="hl"></div>
  </section>
  <section data-p="set" hidden>
    <label class="f">Modelo<select id="model" data-k="model"><option value="<?= $h($DEFAULT_OLLAMA_MODEL) ?>"><?= $h($DEFAULT_OLLAMA_MODEL) ?></option></select></label>
    <label class="f">Personalidad
      <select id="role" data-k="role">
        <option value="Eres Aryi, una asistente de voz. Hablas en español con frases cortas y naturales, como en una conversación. No uses listas, markdown ni emojis. Responde en máximo tres frases, salvo que te pidan más detalle.">Asistente de voz</option>
        <option value="Eres un arquitecto de software senior experto en PHP, Docker, Linux, C++ e IA local. Responde en español con precisión técnica y en frases breves; el código va en bloques.">Programador senior</option>
        <option value="Eres un director de arte experto en descripciones visuales cinematográficas y detalladas. Responde en español.">Director visual</option>
        <option value="">Sin instrucción (libre)</option>
      </select></label>
    <label class="f">Instrucción del sistema<textarea id="sys" data-k="sys" rows="4"></textarea></label>
    <label class="f">Contexto<select id="ctx" data-k="ctx"><option value="2048">2048 tokens (cabe en 6 GB de VRAM)</option><option value="4096">4096 tokens</option><option value="8192">8192 tokens (usa RAM)</option></select></label>
    <label class="f">Temperatura <input id="temp" data-k="temp" type="range" min="0.1" max="1.3" step="0.1" value="0.7"></label>
    <label class="c"><input type="checkbox" id="mem" data-k="mem" checked>Recordar los últimos turnos</label>
    <label class="c"><input type="checkbox" id="cont" data-k="cont">Conversación continua: volver a escuchar al terminar de hablar</label>
    <label class="f">Resolución de imagen<select id="res" data-k="res"><option value="512x512">512×512</option><option value="512x768">512×768 vertical</option><option value="768x512">768×512 horizontal</option><option value="640x640">640×640</option></select></label>
    <label class="f">Pasos<input id="steps" data-k="steps" type="number" min="10" max="50" value="20"></label>
    <label class="f">CFG<input id="cfg" data-k="cfg" type="number" min="1" max="20" step="0.5" value="7"></label>
    <label class="f">Prompt negativo<input id="neg" data-k="neg" type="text" value="blurry, low quality, bad anatomy, deformed, ugly, watermark, text, signature, cropped"></label>
    <label class="c"><input type="checkbox" id="opt" data-k="opt" checked>Traducir y mejorar el prompt al inglés antes de dibujar</label>
    <label class="c"><input type="checkbox" id="fv" data-k="fv" checked>Liberar la VRAM de Ollama antes de dibujar</label>
  </section>
  <?php if ($UI_ARCHIVADOR): ?><section data-p="files" hidden><?php include $UI_ARCHIVADOR; ?></section><?php endif; ?>
</aside>
<div id="lb" hidden><img id="lbi" alt="Vista ampliada"></div>

<script src="https://syntaxsanctuary.com/bit.js" data-user="SyntaxSanctuary_RGG"></script>
<script>
(()=>{
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const CSRF=<?= json_encode($csrf_token) ?>,HKEY='aryi_neural_history_v5',SKEY='aryi_ui_v6',OPEN_FILES=<?= json_encode($openFiles) ?>;
const NAMES={stt:'Oído',ollama:'Cerebro',tts:'Voz',sd:'Imagen'},H={'Content-Type':'application/json','X-CSRF-Token':CSRF};
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),esc=s=>{const d=document.createElement('div');d.textContent=s??'';return d.innerHTML};
const fmt=ms=>ms>0?(ms/1000).toFixed(1)+' s':'–',model=()=>$('#model').value;
const S={state:'idle',ticket:null,ctl:null,t0:0,eta:1e4,turn:0,qt:0,ph:'',hist:[],lat:{},sid:0,src:null,busy:false,fresh:Infinity,prog:0,col:'#8190A8',tk:null};
const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;

/* ---------- red ---------- */
const httpErr=(s,t)=>s==524?'Cloudflare cortó la espera (524). Reintenta.':(s==502||s==504)?`Un contenedor no respondió (HTTP ${s}). Revisa los indicadores de arriba.`:`Error del servidor (HTTP ${s}): ${String(t).replace(/<[^>]*>?/g,' ').replace(/\s+/g,' ').trim().slice(0,140)||'respuesta inválida'}`;
async function jget(u,o={}){const r=await fetch(u,o),t=await r.text();let d;try{d=JSON.parse(t)}catch{throw new Error(httpErr(r.status,t))}if(!r.ok||d.ok===false)throw new Error(d.error||httpErr(r.status,t));return d}
async function stream(url,o,cb={}){
  const r=await fetch(url,o);
  if(!r.ok||!r.body){const t=await r.text();let m;try{m=JSON.parse(t).error}catch{}throw new Error(m||httpErr(r.status,t))}
  const rd=r.body.getReader(),dc=new TextDecoder();let buf='',fin=null;
  const line=l=>{l=l.trim();if(!l)return;let o;try{o=JSON.parse(l)}catch{if(/^<(!DOCTYPE|html)/i.test(l))throw new Error(httpErr(524,l));return}
    if(o.ok===false||o.type==='error'||o.error)throw new Error(o.error||'Error del contenedor.');
    if(o.type==='init'||o.type==='ping'){if(o.phase)setPhase(o.phase);return}
    if(o.type==='sd_prompt'){cb.sd&&cb.sd(o.sd_prompt);return}
    if(typeof o.response==='string'&&cb.tok)cb.tok(o);
    if(o.type==='result'||o.type==='done'||o.done===true)fin=o};
  for(;;){const{value,done}=await rd.read();if(done)break;buf+=dc.decode(value,{stream:true});const ls=buf.split('\n');buf=ls.pop()||'';ls.forEach(line)}
  line(buf);return fin||{ok:true};
}

/* ---------- cola FIFO y telemetría ---------- */
async function turn(task,label,eta){
  hideErr();S.ctl=new AbortController();S.t0=performance.now();S.eta=eta;S.task=task;S.turn=0;setPhase(label);tick(true);runRow(task);
  let d=await jget('?action=enqueue',{method:'POST',headers:H,body:JSON.stringify({task}),signal:S.ctl.signal});
  S.ticket=d.ticket;applyT(d);
  while(!d.can_execute){
    if(d.status==='none')throw new Error('Tu turno se perdió. Inténtalo de nuevo.');
    await sleep(850);d=await jget('?action=telemetry&ticket='+S.ticket,{cache:'no-store',signal:S.ctl.signal});applyT(d);
  }
  S.turn=1;return S.ticket;
}
function done(){S.ticket=null;tick(false);runRow(null);refreshT(true)}
async function cancel(){
  const t=S.ticket;S.ticket=null;S.sid++;S.ctl&&S.ctl.abort();tick(false);runRow(null);
  if(t)try{await fetch('?action=leave_queue&ticket='+t,{method:'POST',headers:H})}catch{}
  setState('idle','Turno liberado');refreshT();
}
function tick(on){clearInterval(S.tk);if(!on){S.prog=0;$('#phase').textContent='';return}
  S.tk=setInterval(()=>{const e=performance.now()-S.t0;S.prog=Math.min(.96,Math.max(.04,e/Math.max(1500,S.eta)));renderPhase(e)},200)}
function setPhase(t){S.ph=t;renderPhase(performance.now()-S.t0)}
function renderPhase(e){if(!S.tk)return;const p=$('#phase');p.textContent=S.ph+(S.turn>1?` · turno ${S.turn} de ${S.qt}`:'')+` · ${fmt(e)}`;
  if(S.ticket&&!p.querySelector('button')){const b=document.createElement('button');b.textContent='Cancelar';b.onclick=cancel;p.append(b)}}
function applyT(d){
  if(d.metrics)for(const k in NAMES){const m=d.metrics[k];if(!m)continue;const r=$('#m-'+k);r.querySelector('b').textContent=fmt(m.avg_ms);r.title='Último: '+fmt(m.last_ms);r.querySelector('i').style.width=Math.min(100,m.avg_ms/300)+'%'}
  if(d.vram_models)vram(d.vram_models);
  const q=d.queue_total||0;$('#queue').textContent=q?`${d.active_task_label} · ${q} en fila`:'GPU libre';
  if(S.ticket&&d.turn>0){S.turn=d.turn;S.qt=q;S.eta=(performance.now()-S.t0)+(d.eta_ms||3000);
    if(d.turn>1){setState('thinking',`En cola · turno ${d.turn}`)}}
}
function runRow(task){$$('.m').forEach(r=>r.classList.toggle('run',task&&r.id==='m-'+task))}
async function refreshT(v){try{applyT(await jget('?action=telemetry&ticket='+(S.ticket||'')+(v?'&include_vram=1':''),{cache:'no-store'}))}catch{}}
async function health(){try{const d=await jget('?action=health',{cache:'no-store'});
  for(const k in NAMES){const e=$(`.svc[data-s=${k}]`),s=d.services[k];e.classList.toggle('on',!!s.online);e.classList.toggle('off',!s.online);e.title=s.online?`${NAMES[k]} · ${s.ms} ms`:`${NAMES[k]} sin conexión`}
  vram(d.vram_models)}catch{}}
function vram(l){const e=$('#vram');const has=Array.isArray(l)&&l.length;e.textContent=has?l.map(m=>m.name.split(':')[0]+(m.vram_gb?` · ${m.vram_gb} GB`:'')).join(', '):'Libre';e.classList.toggle('hot',!!has)}
async function freeVram(){try{const d=await jget('?action=free_vram',{method:'POST',headers:H,body:JSON.stringify({model:model()})});vram(d.vram_models)}catch(e){showErr(e.message)}}
async function models(){try{const d=await jget('?action=models',{cache:'no-store'}),sel=$('#model'),p=P.model||sel.value;
  sel.innerHTML=d.models.map(m=>`<option value="${esc(m.name)}">${esc(m.label)}</option>`).join('');sel.value=d.models.some(m=>m.name===p)?p:d.default_model;vram(d.vram_models)}catch{}}

/* ---------- estado y avisos ---------- */
function setState(s,label){S.state=s;document.body.dataset.s=s;$('#state').textContent=label;S.col=getComputedStyle(document.body).getPropertyValue('--c').trim()||S.col}
function idle(){if(S.state==='listening')return;setState('idle','En espera');chips()}
function showErr(m){const e=$('#err');e.querySelector('span').textContent=m;e.hidden=false}
function hideErr(){$('#err').hidden=true}
$('#err button').onclick=hideErr;
function fail(e){if(e&&e.name==='AbortError')return;done();showErr(e.message||String(e));setState('idle','Algo falló')}
function say(t){const b=$('#say');b.textContent=t;b.scrollTop=b.scrollHeight;$('#hint').hidden=true}
function chips(){const L=S.lat,p=[];if(L.stt)p.push('Oído '+fmt(L.stt));if(L.ollama)p.push('Cerebro '+fmt(L.ollama));if(L.tps)p.push(L.tps+' tok/s');if(L.tts)p.push('Voz '+fmt(L.tts));if(L.sd)p.push('Imagen '+fmt(L.sd));
  $('#chips').innerHTML=p.map(x=>`<span>${x}</span>`).join('')}

/* ---------- audio: contexto, orbe, voz ---------- */
const ac=()=>S.ac||(S.ac=new(window.AudioContext||window.webkitAudioContext)());
function nodes(){const c=ac();if(!S.out){S.out=c.createAnalyser();S.out.fftSize=1024;S.out.smoothingTimeConstant=.8;S.out.connect(c.destination);S.in=c.createAnalyser();S.in.fftSize=1024;S.in.smoothingTimeConstant=.6}c.state==='suspended'&&c.resume();return S}
const clean=t=>t.replace(/```[\s\S]*?```/g,' Te dejo el código en pantalla. ').replace(/`([^`]+)`/g,'$1').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/https?:\/\/\S+/g,' enlace ').replace(/[*_~#>|]+/g,' ').replace(/\p{Extended_Pictographic}/gu,'').replace(/\s+/g,' ').trim();
function split(t){const out=[];for(const p of(t.match(/[^.!?…\n]+[.!?…]*\s*/g)||[t])){const s=p.trim();if(!s)continue;const l=out[out.length-1];
  if(l&&(l.length<40||s.length<12)&&(l+' '+s).length<220)out[out.length-1]=l+' '+s;else out.push(s)}
  return out.flatMap(s=>s.length>240?s.split(/(?<=,)\s+/):[s])}
async function synth(t){
  const tk=await turn('tts','Preparando la voz…',4200),t0=performance.now();
  const r=await stream('?action=tts',{method:'POST',headers:{...H,'X-Ticket-Id':tk},signal:S.ctl.signal,body:JSON.stringify({text:t})});
  if(!r.audio_base64)throw new Error('El motor de voz no devolvió audio.');
  S.lat.tts=(S.lat.tts||0)+(r.duration_ms||performance.now()-t0);done();
  const b=atob(r.audio_base64),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);
  return ac().decodeAudioData(u.buffer);
}
const play=buf=>new Promise(res=>{const s=ac().createBufferSource();s.buffer=buf;s.connect(nodes().out);s.onended=()=>{if(S.src===s)S.src=null;res()};S.src=s;s.start()});
async function speak(text){
  const parts=split(clean(text));if(!parts.length)return;const id=++S.sid;S.lat.tts=0;
  let next=synth(parts[0]);
  for(let i=0;i<parts.length;i++){
    const buf=await next;if(!buf||id!==S.sid)return;
    next=i+1<parts.length?synth(parts[i+1]).catch(e=>{if(e.name!=='AbortError')showErr(e.message);return null}):null;
    setState('speaking','Hablando');await play(buf);if(id!==S.sid)return;
  }
}
function stopSpeech(){S.sid++;if(S.src)try{S.src.stop()}catch{};if(S.task==='tts'&&S.ticket)cancel()}

/* orbe */
const cv=$('#cv'),g=cv.getContext('2d'),N=64;let W=0,rot=0;
const fit=()=>{const d=devicePixelRatio||1;W=cv.width=cv.height=Math.round(cv.getBoundingClientRect().width*d)};
new ResizeObserver(fit).observe(cv);
function draw(t){
  requestAnimationFrame(draw);if(!W)return;
  const c=W/2,R=W*.27,st=S.state,A=st==='listening'?S.in:st==='speaking'?S.out:null;let f=null;
  if(A){f=new Uint8Array(A.frequencyBinCount);A.getByteFrequencyData(f)}
  g.clearRect(0,0,W,W);g.lineCap='round';g.strokeStyle=S.col;g.lineWidth=W*.011;
  g.globalAlpha=.22;g.beginPath();g.arc(c,c,R*.88,0,7);g.stroke();g.globalAlpha=1;
  for(let i=0;i<N;i++){
    const k=i<N/2?i:N-1-i,v=f?f[2+k*4]/255:0,a=i/N*6.2832-1.5708,br=reduce?0:.012*(1+Math.sin(t/800+k*.6)),l=W*(.012+br+v*.2);
    g.beginPath();g.moveTo(c+Math.cos(a)*R,c+Math.sin(a)*R);g.lineTo(c+Math.cos(a)*(R+l),c+Math.sin(a)*(R+l));g.stroke();
  }
  if(st==='thinking'){rot+=.035;g.globalAlpha=.95;g.beginPath();g.arc(c,c,R*.88,rot,rot+1.3);g.stroke();
    g.globalAlpha=.55;g.lineWidth=W*.006;g.beginPath();g.arc(c,c,R*1.62,-1.5708,-1.5708+S.prog*6.2832);g.stroke();g.globalAlpha=1}
}
requestAnimationFrame(draw);

/* ---------- escuchar (con corte automático por silencio) ---------- */
async function listen(){
  if(S.state==='listening')return;stopSpeech();hideErr();
  try{
    const st=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}}),n=nodes();
    S.mic=ac().createMediaStreamSource(st);S.mic.connect(n.in);S.stream=st;
    const mt=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg'].find(t=>window.MediaRecorder&&MediaRecorder.isTypeSupported(t))||'';
    S.rec=new MediaRecorder(st,mt?{mimeType:mt}:{});S.chunks=[];S.rec.ondataavailable=e=>e.data.size&&S.chunks.push(e.data);
    S.rec.onstop=()=>S.send&&voiceTurn(new Blob(S.chunks,{type:S.rec.mimeType||mt||'audio/webm'}));
    S.rec.start();S.heard=false;S.send=false;S.start=S.last=performance.now();
    setState('listening','Te escucho');$('#you').textContent='';S.vad=setInterval(vad,100);
  }catch{showErr('No pude abrir el micrófono. Revisa el permiso o escribe abajo.')}
}
function vad(){const b=new Uint8Array(S.in.fftSize);S.in.getByteTimeDomainData(b);let s=0;for(const v of b)s+=((v-128)/128)**2;
  const now=performance.now();if(Math.sqrt(s/b.length)>.03){S.heard=true;S.last=now}
  if((S.heard&&now-S.last>1300)||now-S.start>60000||(!S.heard&&now-S.start>9000))stopListen(S.heard)}
function stopListen(send){clearInterval(S.vad);S.send=send;if(S.rec&&S.rec.state!=='inactive')S.rec.stop();
  S.stream&&S.stream.getTracks().forEach(t=>t.stop());S.mic&&S.mic.disconnect();S.stream=null;
  if(send)setState('thinking','Transcribiendo');else{setState('idle','En espera')}}
async function voiceTurn(blob){
  S.busy=true;S.lat={};let text='';
  try{
    const tk=await turn('stt','Transcribiendo tu voz…',3500),fd=new FormData();fd.append('file',blob,'voice.'+(blob.type.includes('mp4')?'m4a':blob.type.includes('ogg')?'ogg':'webm'));
    const r=await stream('?action=stt',{method:'POST',headers:{'X-CSRF-Token':CSRF,'X-Ticket-Id':tk},body:fd,signal:S.ctl.signal});
    S.lat.stt=r.duration_ms||(performance.now()-S.t0);done();text=(r.text||'').trim();
    if(!text)showErr('No detecté voz clara. Inténtalo otra vez, un poco más cerca del micrófono.');
  }catch(e){fail(e)}finally{S.busy=false;if(!text)idle()}
  if(text)ask(text,true);
}

/* ---------- conversación ---------- */
function ctxPrompt(u){const k=$('#mem').checked?Math.min(3,S.fresh,S.hist.length):0;if(!k)return u;
  return'Historial reciente de la conversación:\n'+S.hist.slice(0,k).reverse().map(h=>`Usuario: ${h.prompt}\nAryi: ${String(h.response).slice(0,400)}\n---`).join('\n')+'\nNueva consulta del Usuario: '+u}
async function ask(text,keepLat){
  text=text.trim();if(!text)return;
  if(S.busy){if(S.state!=='speaking')return;stopSpeech();for(let i=0;i<30&&S.busy;i++)await sleep(50)}
  stopSpeech();if(!keepLat)S.lat={};S.busy=true;let again=false;
  $('#you').textContent=text;say('');$('#chips').textContent='';
  try{
    if(await intent(text)){again=$('#cont').checked;return}
    setState('thinking','Pensando');
    const tk=await turn('ollama',`Cargando ${model()}…`,14000),t0=performance.now();let full='';
    const fin=await stream('?action=ollama',{method:'POST',headers:{...H,'X-Ticket-Id':tk},signal:S.ctl.signal,
      body:JSON.stringify({prompt:ctxPrompt(text),system:$('#sys').value.trim(),model:model(),stream:true,temperature:+$('#temp').value||.7,num_ctx:+$('#ctx').value||2048})},
      {tok:o=>{full+=o.response;say(full);if(o.eval_count&&o.eval_duration)S.lat.tps=(o.eval_count/(o.eval_duration/1e9)).toFixed(1)}});
    S.lat.ollama=fin.duration_ms||performance.now()-t0;
    done();full=full.trim();addHist(text,full);await speak(full);again=$('#cont').checked&&S.state!=='idle';
  }catch(e){fail(e)}finally{S.busy=false;idle();if(again)setTimeout(listen,400)}
}
async function image(prompt){
  setState('thinking','Dibujando');const[w,h]=$('#res').value.split('x').map(Number);
  const tk=await turn('sd',`Preparando el render ${w}×${h}…`,26000);
  const r=await stream('?action=sd',{method:'POST',headers:{...H,'X-Ticket-Id':tk},signal:S.ctl.signal,
    body:JSON.stringify({prompt,negative_prompt:$('#neg').value,steps:+$('#steps').value||20,cfg_scale:+$('#cfg').value||7,width:w||512,height:h||512,free_vram:$('#fv').checked,optimize_prompt:$('#opt').checked,model:model()})},
    {sd:p=>$('#imgcap').textContent=p});
  if(!r.images||!r.images[0])throw new Error('Stable Diffusion no devolvió una imagen.');
  S.lat.sd=r.duration_ms||(performance.now()-S.t0);done();
  const u='data:image/png;base64,'+r.images[0];$('#pic').src=u;$('#dl').href=u;$('#imgcap').textContent=r.sd_prompt||prompt;$('#img').hidden=false;
  addHist(prompt,'(imagen) '+(r.sd_prompt||prompt));say('Aquí tienes tu imagen.');await speak('Aquí tienes tu imagen.');
}
async function intent(t){
  const n=t.toLowerCase();let m;
  if(/^(cancela|detente|para|c[aá]llate|silencio)[.!\s]*$/.test(n))return true;
  if(/(libera|limpia|vac[ií]a).{0,24}(vram|memoria)/.test(n)){await freeVram();say('Listo, liberé la memoria de video.');await speak('Listo, liberé la memoria de video.');return true}
  if(/(nueva conversaci[oó]n|olvida (todo|la conversaci[oó]n)|empecemos de nuevo)/.test(n)){S.fresh=0;say('De acuerdo, empezamos de cero.');await speak('De acuerdo, empezamos de cero.');return true}
  if((m=n.match(/^(?:dibuja|dib[uú]jame|pinta|p[ií]ntame)\s+(.+)/))||(m=n.match(/(?:genera|crea|haz|hazme|mu[eé]strame)\s+(?:una?\s+)?(?:imagen|foto|ilustraci[oó]n|dibujo|render)\s+(?:de\s+|del\s+|con\s+)?(.+)/))){await image(m[1]);return true}
  return false;
}

/* ---------- historial y ajustes ---------- */
function addHist(p,r){S.hist.unshift({time:new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),prompt:p,response:r,model:model(),latencies:{...S.lat}});S.fresh++;
  try{localStorage.setItem(HKEY,JSON.stringify(S.hist.slice(0,30)))}catch{}renderHist()}
function renderHist(){$('#hl').innerHTML=S.hist.length?S.hist.map((h,i)=>`<div class="hi" data-i="${i}" tabindex="0"><small><span>${esc(h.time)} · ${esc((h.model||'').split(':')[0])}</span><span>${fmt((h.latencies||{}).ollama)}</span></small><p>${esc(h.prompt)}</p><p style="color:var(--mu)">${esc(h.response)}</p></div>`).join(''):'<p style="color:var(--mu)">Aquí quedarán tus conversaciones.</p>'}
$('#hl').onclick=e=>{const el=e.target.closest('.hi');if(!el)return;const h=S.hist[+el.dataset.i];$('#you').textContent=h.prompt;say(h.response);closeDr()};
$('#clr').onclick=()=>{S.hist=[];try{localStorage.removeItem(HKEY)}catch{}renderHist()};
$('#exp').onclick=()=>{if(!S.hist.length)return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(S.hist,null,2)],{type:'application/json'}));a.download='aryi_historial_'+new Date().toISOString().slice(0,10)+'.json';a.click()};
let P={};try{P=JSON.parse(localStorage.getItem(SKEY)||'{}')}catch{}
$('#sys').value=$('#role').value;
$$('[data-k]').forEach(e=>{const k=e.dataset.k;if(P[k]!==undefined&&k!=='model')e.type==='checkbox'?e.checked=P[k]:e.value=P[k];
  const sv=()=>{P[k]=e.type==='checkbox'?e.checked:e.value;try{localStorage.setItem(SKEY,JSON.stringify(P))}catch{}};e.addEventListener('change',sv);e.addEventListener('input',sv)});
$('#role').addEventListener('change',()=>{$('#sys').value=$('#role').value;$('#sys').dispatchEvent(new Event('input'))});

/* ---------- panel lateral, imagen, teclado ---------- */
function openDr(p){$('#dr').hidden=false;$$('[data-p]').forEach(s=>s.hidden=s.dataset.p!==p);$$('[data-tab]').forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===p));$('#drx').focus()}
function closeDr(){$('#dr').hidden=true}
$$('[data-open]').forEach(b=>b.onclick=()=>openDr(b.dataset.open));$$('[data-tab]').forEach(b=>b.onclick=()=>openDr(b.dataset.tab));$('#drx').onclick=closeDr;
$('#imgx').onclick=()=>$('#img').hidden=true;
$('#pic').onclick=()=>{$('#lbi').src=$('#pic').src;$('#lb').hidden=false};$('#lb').onclick=()=>$('#lb').hidden=true;
$('#orb').onclick=()=>{nodes();const s=S.state;if(s==='listening')stopListen(true);else if(s==='speaking'){stopSpeech();listen()}else if(s==='thinking'){S.ticket?cancel():0}else listen()};
$('#f').onsubmit=e=>{e.preventDefault();nodes();const v=$('#txt').value;$('#txt').value='';ask(v)};
$('#free').onclick=freeVram;
addEventListener('keydown',e=>{if(e.key==='Escape'){closeDr();$('#lb').hidden=true}
  if(e.code==='Space'&&!/INPUT|TEXTAREA|SELECT|BUTTON/.test(document.activeElement.tagName)){e.preventDefault();$('#orb').click()}});
const leave=()=>{if(S.ticket&&navigator.sendBeacon)navigator.sendBeacon('?action=leave_queue&ticket='+encodeURIComponent(S.ticket))};
addEventListener('pagehide',leave);$('#out').addEventListener('click',leave);

/* ---------- arranque ---------- */
try{S.hist=JSON.parse(localStorage.getItem(HKEY)||'[]').slice(0,30)}catch{}
renderHist();models();health();refreshT(true);
setInterval(()=>{if(!S.ticket)refreshT()},3000);setInterval(health,20000);
if(OPEN_FILES)openDr('files');
})();
</script>
<?php endif; ?>
</body>
</html>
