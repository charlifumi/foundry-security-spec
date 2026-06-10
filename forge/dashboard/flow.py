"""Vue « pipeline » type N8N : graphe coloré par agent + flux animés + pas-à-pas + drill-down.

- Couleur distincte par rôle ; badge du nombre d'instances par catégorie.
- Clic sur un agent -> panneau de détail (rôle, outils, entrées, findings produits, tokens).
- Mode pas-à-pas (⏮ ⏭ ▶) : exécute réellement chaque étape, inspecteur de la donnée en transit.
Alimenté par /api/state (+ POST /api/step, /api/reset). Sans dépendance ni CDN.
"""

PAGE_FLOW = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forge — pipeline</title>
<style>
:root{color-scheme:light;--bg:#0b0f14;--grid:#141b24;--ink:#e6edf3;--mut:#8b949e;--line:#2a3340;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui,Segoe UI,Roboto,Arial;overflow:hidden}
header{position:fixed;top:0;left:0;right:0;height:52px;display:flex;align-items:center;gap:12px;
padding:0 16px;background:rgba(13,17,23,.9);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);z-index:20}
header h1{font-size:16px;margin:0;letter-spacing:.5px}header h1 b{color:var(--acc)}
.badge{padding:2px 9px;border:1px solid var(--line);border-radius:20px;font-size:12px;color:var(--mut)}
.badge.on{color:var(--ok);border-color:var(--ok)}
.ctrl{display:none;align-items:center;gap:6px}
.btn{cursor:pointer;border:1px solid var(--line);background:#0f1620;color:var(--ink);border-radius:8px;padding:5px 11px;font-size:14px;font-weight:700}
.btn:hover{border-color:var(--acc)}.btn.play{color:var(--ok)}.btn:disabled{opacity:.4;cursor:default}
.stepn{font-size:12px;color:var(--mut);min-width:74px;text-align:center}
a.tg{margin-left:auto;color:var(--mut);text-decoration:none;font-size:12px;border:1px solid var(--line);padding:4px 10px;border-radius:6px}
.stage{position:absolute;inset:88px 0 0 0;overflow:auto}.stage.insp-on{right:360px}
.canvas{position:relative;width:1520px;height:660px;margin:18px auto;
background-image:radial-gradient(var(--grid) 1px,transparent 1px);background-size:22px 22px}
svg.edges{position:absolute;left:0;top:0;width:1520px;height:660px;pointer-events:none}
.node{position:absolute;width:166px;border:1px solid var(--line);border-top:3px solid var(--mut);border-radius:12px;
background:#0f1620;box-shadow:0 6px 18px rgba(0,0,0,.35);overflow:hidden;cursor:pointer;transition:box-shadow .2s,transform .15s}
.node:hover{transform:translateY(-2px)}
.node.active{box-shadow:0 0 0 1px var(--acc),0 6px 22px rgba(88,166,255,.22)}
.node.cur{box-shadow:0 0 0 2px var(--warn),0 0 26px rgba(210,153,34,.5);transform:scale(1.04);z-index:5}
.node .hd{display:flex;align-items:center;gap:7px;padding:7px 9px;font-weight:700;font-size:12.5px;border-bottom:1px solid var(--line)}
.node .ic{width:18px;height:18px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;color:#0b0f14;font-weight:800}
.node .inst{margin-left:auto;font-size:10px;font-weight:800;padding:1px 6px;border-radius:10px;background:#0b0f14;border:1px solid var(--line);color:var(--mut)}
.node .inst.run{color:#0b0f14}
.node .bd{padding:7px 9px;font-size:11.5px;color:var(--mut)}
.node .big{font-size:20px;font-weight:800;color:var(--ink)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);display:inline-block;margin-right:4px}.dot.dead{background:var(--mut)}
.chips{display:flex;flex-wrap:wrap;gap:3px;margin-top:5px}
.chip{font-size:9.5px;padding:1px 5px;border:1px solid var(--line);border-radius:10px;color:var(--mut)}
.chip.hot{color:#0b0f14;font-weight:700}
.port{position:absolute;width:9px;height:9px;border-radius:50%;background:#0f1620;border:2px solid var(--mut);top:50%;transform:translateY(-50%)}
.port.in{left:-5px}.port.out{right:-5px}
.insp{position:fixed;top:88px;right:0;bottom:0;width:360px;border-left:1px solid var(--line);background:#0d1117;padding:14px;overflow:auto;display:none}
.insp h2{font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:var(--mut);margin:0 0 6px}
.insp .ttl{font-size:15px;font-weight:800;margin:2px 0}.insp .sum{color:var(--mut);font-size:12px;margin-bottom:10px}
.data{background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:10px;font-size:11.5px}
.leg{font-size:11px;color:var(--mut);margin:7px 0 2px}.mono{font-family:ui-monospace,Menlo,monospace}
.sink{color:var(--bad)}.okv{color:var(--ok)}.badv{color:var(--bad)}
.row{padding:5px 7px;border:1px solid var(--line);border-radius:6px;margin:5px 0;background:#0f1620}
pre{white-space:pre-wrap;word-break:break-word;margin:4px 0;font-size:11px;color:#c9d1d9}
.slog{margin-top:14px}.slog .it{font-size:11px;color:var(--mut);padding:2px 0;border-bottom:1px solid #161b22}.slog .it.cur{color:var(--warn);font-weight:700}
.sev-critical{border-left:3px solid var(--bad)}.sev-high{border-left:3px solid var(--warn)}.sev-medium{border-left:3px solid var(--acc)}.sev-low{border-left:3px solid var(--mut)}
/* modal détail agent */
.ov{position:fixed;inset:0;background:rgba(2,6,12,.6);display:none;align-items:center;justify-content:center;z-index:40}
.modal{width:560px;max-width:92vw;max-height:86vh;overflow:auto;background:#0f1620;border:1px solid var(--line);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.6)}
.modal .mh{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)}
.modal .mh .ic{width:26px;height:26px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;color:#0b0f14;font-weight:800}
.modal .mh h3{margin:0;font-size:17px}.modal .mh .x{margin-left:auto;cursor:pointer;color:var(--mut);font-size:18px;border:1px solid var(--line);border-radius:6px;padding:0 9px}
.modal .mb{padding:14px 16px}.modal .desc{color:var(--mut);font-size:13px;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.card{background:#0b0f14;border:1px solid var(--line);border-radius:10px;padding:10px}
.card h4{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--mut)}
.tok{display:flex;gap:12px;flex-wrap:wrap}.tok b{font-size:18px}
.taglist span{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:8px;padding:2px 7px;margin:2px 3px 0 0;color:var(--ink)}
.hint{font-size:11px;color:var(--mut);margin-top:4px}
/* barre d'onglets + panneaux déroulants */
.pulls{position:fixed;top:52px;left:0;right:0;height:34px;display:flex;gap:8px;align-items:center;padding:0 16px;
background:rgba(13,17,23,.85);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);z-index:18}
.pull{cursor:pointer;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:7px;padding:3px 10px;background:#0f1620}
.pull:hover{color:var(--ink)}.pull.on{color:#0b0f14;background:var(--acc);border-color:var(--acc);font-weight:700}
.panel{position:fixed;top:86px;left:0;right:0;max-height:46vh;overflow:auto;z-index:17;display:none;
background:#0d1117;border-bottom:1px solid var(--line);box-shadow:0 14px 30px rgba(0,0,0,.4);padding:14px 18px}
.panel h3{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--mut)}
.bars .bar{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px}
.bars .bar i{height:9px;border-radius:5px;display:inline-block}
.fleetgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.fcard{background:#0f1620;border:1px solid var(--line);border-radius:10px;padding:9px}
.fcard .h{font-weight:700;font-size:12px;margin-bottom:5px}.inst-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:2px}
.filerow{cursor:pointer;font-family:ui-monospace,Menlo,monospace;font-size:12px;padding:3px 6px;border-radius:6px}
.filerow:hover{background:#161b22}.filerow.on{background:#161b22;color:var(--acc)}
.code{background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:0;overflow:auto;max-height:38vh}
.code table{border-collapse:collapse;width:100%;font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
.code td{padding:0 8px;white-space:pre}.code .ln{color:#566;text-align:right;user-select:none;border-right:1px solid var(--line);background:#0d1117}
.code tr.hot{background:rgba(248,81,73,.14)}.code tr.hot .ln{color:var(--bad)}
.verdbar{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
.vd{font-size:9.5px;padding:1px 6px;border-radius:9px;border:1px solid var(--line)}
.vd.tp{color:#0b0f14;background:var(--ok)}.vd.fp{color:var(--mut)}.vd.na{color:var(--mut)}.vd.nr{color:var(--warn);border-color:var(--warn)}
.frow{cursor:pointer}.frow:hover{outline:1px solid var(--acc)}
.expl{font-size:12px;color:#c9d1d9;line-height:1.5}
.funnel{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.fstage{background:#0f1620;border:1px solid var(--line);border-radius:10px;padding:8px 16px;text-align:center;min-width:86px}
.fstage .fn{font-size:24px;font-weight:800}.fstage .fl{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
.farrow{color:var(--mut);font-size:14px;text-align:center;padding:0 2px}.farrow .fd{font-size:9.5px;color:var(--bad)}
</style></head><body>
<header>
  <h1><b>FORGE</b> · pipeline</h1>
  <span class="badge" id="run">run —</span>
  <span class="badge" id="cov">couverture —</span>
  <span class="badge" id="gap">rule-gaps —</span>
  <span class="ctrl" id="ctrl">
    <button class="btn" id="b-reset" title="recommencer">⏮</button>
    <button class="btn play" id="b-play" title="lecture auto">▶</button>
    <button class="btn" id="b-step" title="étape suivante">⏭</button>
    <span class="stepn" id="stepn">étape 0</span>
  </span>
  <a class="tg" href="/panels">vue panneaux →</a>
</header>
<div class="pulls">
  <span class="pull" id="p-res" onclick="togglePanel('res')">⚙ Ressources</span>
  <span class="pull" id="p-fleet" onclick="togglePanel('fleet')">👥 Fleet</span>
  <span class="pull" id="p-code" onclick="togglePanel('code')">&lt;/&gt; Code source</span>
  <span class="pull" id="p-find" onclick="togglePanel('find')">🛡 Findings</span>
  <span class="pull" id="p-out" onclick="togglePanel('out')">📤 Sortie priorisée</span>
  <span style="margin-left:auto;font-size:11px;color:var(--mut)" id="outflow">—</span>
</div>
<div class="panel" id="panel-res"></div>
<div class="panel" id="panel-fleet"></div>
<div class="panel" id="panel-code"></div>
<div class="panel" id="panel-find"></div>
<div class="panel" id="panel-out"></div>
<div class="stage" id="stage"><div class="canvas" id="cv"><svg class="edges" id="svg" viewBox="0 0 1520 660"></svg></div></div>
<aside class="insp" id="insp">
  <h2>Inspecteur — donnée du pas courant</h2>
  <div class="ttl" id="i-ttl">—</div><div class="sum" id="i-sum"></div>
  <div id="i-data"></div>
  <div class="slog"><h2>Journal des pas</h2><div id="i-log"></div></div>
</aside>
<div class="ov" id="ov"><div class="modal" id="modal"></div></div>
<script>
const COL={operator:'#9aa5b1',orchestrator:'#58a6ff',indexer:'#39c5cf',cartographer:'#34d399',
detector:'#f59e0b',triager:'#bc8cff',validator:'#f85149',reporter:'#7ee787',coverage:'#e879f9'};
const INFO={
 operator:{d:"L'humain qui définit les goals, lance et pilote l'évaluation.",tools:['CLI forge','goals'],in:['forge.yaml'],out:['évaluation']},
 orchestrator:{d:"Surface unique : valide, spawn et supervise le fleet, applique le budget.",tools:['superviseur heartbeat','work queue','budget governor'],in:['config','état du fleet'],out:['fleet vivant','status']},
 indexer:{d:"Construit l'index de code (parser déterministe). Gate le fleet (FR-003).",tools:['parser AST','graphe d\'appels','résolveur de citations'],in:['code source'],out:['index queryable']},
 cartographer:{d:"Carte de sécurité : chaînes d'appel entrée→sink, frontières, validation.",tools:['requêtes index','chaînes d\'appel','détection de validation'],in:['index','source','goals'],out:['carte de flux']},
 detector:{d:"Produit des candidats : règles CodeGuard + secrets + dépendances + exploration.",tools:['corpus CodeGuard (règles)','scan secrets','scan dépendances','exploration libre'],in:['index','carte','corpus fédéré'],out:['candidats','rule-gaps']},
 triager:{d:"Investigue et pose le verdict via l'evidence gate (citations vérifiées).",tools:['résolution de citations','evidence gate à 3 jambes'],in:['candidat','index','carte'],out:['verdict + preuve']},
 validator:{d:"Reproduit l'impact sur le testbed live (oracles d'exploitation).",tools:['oracles HTTP : SQLi · XSS · cmd · SSRF · IDOR · traversal · deser','testbed'],in:['finding TP','testbed'],out:['flag exploited','PoC runnable']},
 reporter:{d:"Rédige un rapport par TP + le rollup (CWE/CVSS/OWASP).",tools:['rendu Markdown','mapping CWE/CVSS/OWASP'],in:['findings TP','carte'],out:['rapports','rollup']},
 coverage:{d:"Traduit les goals en checklist et déclare la couverture complète.",tools:['checklist','référentiels OWASP/CWE'],in:['goals','carte'],out:['flag couverture','tâches dirigées']},
};
const NODES=[
 {id:'operator',ic:'OP',t:'Opérateur',x:20,y:280},{id:'orchestrator',ic:'OR',t:'Orchestrateur',x:210,y:280},
 {id:'indexer',ic:'IX',t:'Indexer',x:400,y:150},{id:'cartographer',ic:'CA',t:'Cartographe',x:590,y:410},
 {id:'detector',ic:'DE',t:'Detector',x:790,y:280},{id:'triager',ic:'TR',t:'Triager · gate',x:980,y:280},
 {id:'validator',ic:'VA',t:'Validator',x:1170,y:150},{id:'reporter',ic:'RE',t:'Reporter',x:1350,y:290},
 {id:'coverage',ic:'CV',t:'Coverage-Guide',x:790,y:480},
];
const NW=166,NH=80,BASEY=620;
const EDGES=[
 {f:'operator',t:'orchestrator',k:()=>1},{f:'orchestrator',t:'indexer',k:()=>1},
 {f:'indexer',t:'cartographer',k:()=>1},{f:'indexer',t:'detector',k:()=>1},
 {f:'cartographer',t:'detector',k:()=>1},{f:'detector',t:'triager',k:s=>s.cand},
 {f:'triager',t:'validator',k:s=>s.exploitableTP},{f:'triager',t:'reporter',k:s=>s.tp},
 {f:'validator',t:'reporter',k:s=>s.exploited},{f:'coverage',t:'detector',k:s=>s.covOpen},
 {f:'coverage',t:'orchestrator',k:s=>s.covDone?2:0},
];
const N={};NODES.forEach(n=>N[n.id]=n);
const cv=document.getElementById('cv'),svg=document.getElementById('svg');
for(const n of NODES){const d=document.createElement('div');d.className='node';d.id='n-'+n.id;
 d.style.left=n.x+'px';d.style.top=n.y+'px';d.style.borderTopColor=COL[n.id];
 d.innerHTML=`<div class="hd"><span class="ic" style="background:${COL[n.id]}">${n.ic}</span>`+
   `<span style="color:${COL[n.id]}">${n.t}</span><span class="inst" id="inst-${n.id}">×1</span></div>`+
   `<div class="bd" id="bd-${n.id}">—</div><span class="port in"></span><span class="port out"></span>`;
 d.onclick=()=>openModal(n.id);cv.appendChild(d);}
const out=n=>[n.x+NW,n.y+NH/2],inp=n=>[n.x,n.y+NH/2];
const mkpath=(a,b)=>{
 if(b[0]<a[0]-10){ // arête de rétroaction : on l'achemine par le bas (bus de feedback)
   return `M ${a[0]} ${a[1]} C ${a[0]+70} ${BASEY}, ${b[0]-70} ${BASEY}, ${b[0]} ${b[1]}`;}
 const dx=Math.max(40,(b[0]-a[0])*0.5);
 return `M ${a[0]} ${a[1]} C ${a[0]+dx} ${a[1]}, ${b[0]-dx} ${b[1]}, ${b[0]} ${b[1]}`;};
const EP=[];
for(const e of EDGES){const a=out(N[e.f]),b=inp(N[e.t]);
 const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',mkpath(a,b));
 p.setAttribute('fill','none');p.setAttribute('stroke','#222b36');p.setAttribute('stroke-width','2');svg.appendChild(p);
 const dots=[];for(let k=0;k<4;k++){const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
  c.setAttribute('r','3.6');c.setAttribute('opacity','0');svg.appendChild(c);dots.push(c);}
 EP.push({e,p,dots,len:p.getTotalLength()});}
let STATE={cand:0,tp:0,exploited:0,exploitableTP:0,covOpen:0,covDone:false},CUR_EDGE=null,LAST=null,OPEN=null;
function frame(ts){for(const ep of EP){let act=ep.e.k(STATE)||0;
  const isCur=CUR_EDGE&&ep.e.f===CUR_EDGE[0]&&ep.e.t===CUR_EDGE[1];if(isCur)act=Math.max(act,6);
  const col=COL[ep.e.f];const n=act>0?Math.min(4,1+Math.floor(Math.min(act,8)/2)):0;
  ep.p.setAttribute('stroke',isCur?'#d29922':(act>0?col:'#222b36'));ep.p.setAttribute('stroke-width',isCur?'3':'2');ep.p.setAttribute('opacity',act>0?'0.85':'0.5');
  for(let k=0;k<ep.dots.length;k++){const c=ep.dots[k];
   if(k<n){const sp=0.00010*(1+Math.min(act,10)/4);const t=((ts*sp)+(k/n))%1;const pt=ep.p.getPointAtLength(t*ep.len);
    c.setAttribute('cx',pt.x);c.setAttribute('cy',pt.y);c.setAttribute('fill',isCur?'#d29922':col);c.setAttribute('opacity',0.95);}else c.setAttribute('opacity',0);}}
 requestAnimationFrame(frame);}requestAnimationFrame(frame);
function setbd(id,html,active,cur){const bd=document.getElementById('bd-'+id);bd.innerHTML=html;
 const nd=document.getElementById('n-'+id);nd.classList.toggle('active',!!active);nd.classList.toggle('cur',!!cur);}
function esc(x){return String(x).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}

function findingsByRole(role,F){
 if(role==='detector')return F;
 if(role==='triager')return F.filter(f=>f.verdict);
 if(role==='validator')return F.filter(f=>f.exploited);
 if(role==='reporter')return F.filter(f=>f.state==='published');
 return [];}
function openModal(role){OPEN=role;renderModal();document.getElementById('ov').style.display='flex';}
function closeModal(){OPEN=null;document.getElementById('ov').style.display='none';}
document.getElementById('ov').onclick=e=>{if(e.target.id==='ov')closeModal();};
function renderModal(){if(!OPEN||!LAST)return;const s=LAST,role=OPEN,inf=INFO[role]||{},col=COL[role];
 const rs=(s.role_stats||{})[role]||{alive:0,configured:0,calls:0,in_tok:0,out_tok:0,cost:0};
 const inst=rs.configured||1, run=rs.alive||0;
 const F=s.findings||[];const mine=findingsByRole(role,F);
 let outHtml='';
 if(role==='detector'||role==='triager'||role==='validator'||role==='reporter'){
   outHtml=`<div class="leg">${mine.length} finding(s) — cliquez pour le détail</div>`+mine.slice(0,14).map(f=>`<div class="row mono frow sev-${f.severity||'low'}" onclick="openFinding('${f.fp}')">${esc(f.cwe||f.vuln_class)} ${esc(f.symbol)} ${f.exploited?'<span class=badv>⚡</span>':''}<span style="color:#8b949e"> ${esc(f.verdict||'')}</span></div>`).join('')||'<span class=hint>—</span>';
 } else if(role==='indexer'){outHtml=`<div class="data">${(s.index||{}).functions||0} fonctions indexées</div>`;}
 else if(role==='cartographer'){outHtml=`<div class="data">${(s.flows||[]).length} chaînes d'appel cartographiées</div>`;}
 else if(role==='coverage'){const c=s.coverage||[];outHtml=`<div class="data">${c.filter(x=>x.state==='covered').length}/${c.length} composants couverts</div>`;}
 else {outHtml=`<div class="data">${(s.agents||[]).length} agents dans le fleet</div>`;}
 const claim=(s.agents||[]).find(a=>a.role===role&&a.claim);
 document.getElementById('modal').innerHTML=
  `<div class="mh"><span class="ic" style="background:${col}">${(N[role]||{ic:'··'}).ic||'··'}</span>`+
  `<h3 style="color:${col}">${(N[role]||{t:role}).t}</h3><span class="x" onclick="closeModal()">✕</span></div>`+
  `<div class="mb"><div class="desc">${inf.d||''}</div>`+
  `<div class="grid2">`+
   `<div class="card"><h4>Instances</h4><div class="tok"><span><b style="color:${col}">${run}</b> en cours</span><span><b>${inst}</b> configurées</span></div>`+
     (claim?`<div class="hint">▶ ${esc(claim.claim)}</div>`:`<div class="hint">— au repos —</div>`)+`</div>`+
   `<div class="card"><h4>Consommation tokens</h4><div class="tok"><span><b>${rs.calls}</b> appels</span></div>`+
     `<div class="hint">in ${rs.in_tok} · out ${rs.out_tok} tok · $${rs.cost}</div></div>`+
  `</div>`+
  `<div class="card" style="margin-bottom:12px"><h4>Outils</h4><div class="taglist">${(inf.tools||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
  `<div class="grid2">`+
   `<div class="card"><h4>Entrées</h4><div class="taglist">${(inf.in||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
   `<div class="card"><h4>Sorties</h4><div class="taglist">${(inf.out||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
  `</div>`+
  `<div class="card" style="margin-top:12px"><h4>Findings produits / artefacts</h4>${outHtml}</div></div>`;
}

function renderData(cur){if(!cur)return '';const d=cur.data||{};let h='';
 if(d.testbed_url)h+=`<div class="data mono">${esc(d.testbed_url)}</div>`;
 if(d.functions)h+=`<div class="leg">${d.functions.length} fonctions indexées</div><div class="data mono">${d.functions.slice(0,16).map(f=>`${esc(f.file)} · <b>${esc(f.name)}</b>(${esc((f.params||[]).join(', '))})`).join('<br>')}${d.functions.length>16?'<br>…':''}</div>`;
 if(d.flows)h+=`<div class="leg">chaînes d'appel (entrée → sink)</div><div class="data">${d.flows.map(f=>{const ch=f.chain.map(x=>String(x).startsWith('→sink:')?`<span class=sink>${esc(x)}</span>`:esc(x)).join(' → ');return `<div class="row mono">${f.validated?'<span class=okv>✅</span>':'<span class=badv>⚠️</span>'} <b>${esc(f.entry)}</b>: ${ch}</div>`}).join('')}</div>`;
 if(d.items)h+=`<div class="leg">items de couverture</div><div class="data mono">${d.items.map(i=>esc(i.component)+' × '+esc(i.goal)).join('<br>')}</div>`;
 if(d.candidates)h+=`<div class="leg">candidats produits</div><div class="data">${d.candidates.map(c=>`<div class="row mono">${esc(c.vuln_class)} · <b>${esc(c.symbol)}</b> <span style=color:#8b949e>(${esc(c.file)} · ${esc(c.technique)})</span></div>`).join('')||'—'}</div>`;
 if(d.finding&&d.evidence){const f=d.finding,e=d.evidence;
   h+=`<div class="leg">finding</div><div class="data mono">${esc(f.cwe)} · <b>${esc(f.symbol)}</b> · ${esc(f.file)}<br>verdict: <b>${esc(f.verdict)}</b> · sévérité: ${esc(f.severity||'—')}</div>`;
   h+=`<div class="leg">evidence gate — 3 jambes</div><div class="data mono">① atteignabilité: ${esc((e.reachability||{}).symbol||'')} ${esc((e.reachability||{}).note||'')}<br>② frontière: ${esc((e.trust_boundary||{}).note||'')}<br>③ impact: ${esc((e.impact||{}).symbol||'')} ${esc((e.impact||{}).note||'')}</div>`;}
 if('exploited' in d){h+=`<div class="leg">résultat de validation</div><div class="data">${d.exploited?'<span class=okv><b>⚡ EXPLOITÉ sur le testbed</b></span>':'<span class=badv>non reproduit</span>'}</div>`;
   if(d.poc)h+=`<div class="leg">code d'exploitation généré ET exécuté</div><pre class="data mono">${esc(d.poc)}</pre>`;
   if(d.trace&&d.trace.request)h+=`<div class="leg">exécution observée</div><div class="data mono"><b>Requête :</b> ${esc(d.trace.request)}<br><b>Réponse :</b><pre class="data" style="margin-top:3px">${esc(d.trace.response||'')}</pre><span class="okv">✅ ${esc(d.trace.impact||'')}</span></div>`;}
 if(d.published)h+=`<div class="leg">findings publiés</div><div class="data">${d.published.map(p=>`<div class="row mono sev-${p.severity}">${esc(p.cwe)} ${esc(p.symbol)} [${esc(p.severity)}]${p.exploited?' <span class=badv>⚡</span>':''}</div>`).join('')}</div>`;
 return h;}

const CWE_INFO={
 'CWE-89':{name:'Injection SQL',problem:"Une requête SQL est construite en concaténant une entrée non fiable.",impact:"Bypass d'authentification, lecture et modification de la base."},
 'CWE-79':{name:'Cross-Site Scripting',problem:"Du HTML est renvoyé sans échapper l'entrée utilisateur.",impact:"Exécution de JavaScript arbitraire chez la victime, vol de session."},
 'CWE-78':{name:'Injection de commande',problem:"Une commande shell est bâtie à partir d'entrée non fiable (shell=True).",impact:"Exécution de code arbitraire sur le serveur (RCE)."},
 'CWE-918':{name:'SSRF',problem:"Le serveur requête une URL contrôlée par l'attaquant, sans allowlist.",impact:"Accès aux services internes et aux métadonnées cloud."},
 'CWE-639':{name:'IDOR / contrôle d\'accès cassé',problem:"Accès à une ressource par identifiant sans vérifier l'autorisation de l'appelant.",impact:"Lecture/modification des données d'autres utilisateurs."},
 'CWE-22':{name:'Path traversal',problem:"Un chemin de fichier est bâti à partir d'un nom non assaini.",impact:"Lecture de fichiers arbitraires (secrets, /etc/passwd)."},
 'CWE-502':{name:'Désérialisation non sûre',problem:"Des données non fiables sont désérialisées (pickle).",impact:"Exécution de code arbitraire (RCE)."},
 'CWE-798':{name:'Secret en dur',problem:"Un secret/clé est codé en dur dans la source.",impact:"Compromission directe pour quiconque a accès au dépôt."},
 'CWE-327':{name:'Crypto faible',problem:"Primitive de hachage dépréciée (MD5/SHA-1) pour un usage de sécurité.",impact:"Collisions / cassage facilité."},
 'CWE-916':{name:'Hash de mot de passe faible',problem:"Mot de passe haché sans KDF lent et salé.",impact:"Cassage des mots de passe par force brute."},
 'CWE-1035':{name:'Dépendance vulnérable',problem:"Dépendance tierce à vulnérabilité publiée (CVE).",impact:"Exploitation de la faille connue de la dépendance."},
 'CWE-120':{name:'Copie sans contrôle de borne',problem:"Copie dans un buffer fixe sans vérifier la taille de l'entrée.",impact:"Débordement mémoire — UNIQUEMENT si l'entrée n'est pas bornée par ailleurs."},
 'CWE-208':{name:'Canal auxiliaire temporel',problem:"Écart de temps potentiellement observable.",impact:"Fuite d'information par mesure du temps — souvent difficile à prouver."},
};
const VERD={'true-positive':{l:'true-positive',c:'tp'},'false-positive':{l:'false-positive',c:'fp'},'not-applicable':{l:'not-applicable',c:'na'},'needs-review':{l:'needs-review',c:'nr'}};
function highlightCode(src,start){if(!src)return '<div class="hint">code indisponible</div>';
 const sinks=/execute\(|os\.system|popen|subprocess|urlopen|\bopen\(|pickle\.loads?|hashlib\.(md5|sha1)|\+\s*\w+\s*\+|:\s*len\(|escape|\[\s*:\s*\d+\]/;
 return '<div class="code"><table>'+src.split('\n').map((ln,i)=>`<tr class="${sinks.test(ln)?'hot':''}"><td class="ln">${(start||1)+i}</td><td>${esc(ln)||' '}</td></tr>`).join('')+'</table></div>';}
function openFinding(fp){const s=LAST;if(!s)return;const f=(s.findings||[]).find(x=>x.fp===fp);if(!f)return;
 const ci=CWE_INFO[f.cwe]||{name:f.cwe||f.vuln_class,problem:f.title||'',impact:''};const vd=VERD[f.verdict]||{l:f.verdict,c:''};
 const reason=(f.evidence&&f.evidence.reason)?f.evidence.reason.note:'';
 const col=f.verdict==='true-positive'?(f.exploited?'#f85149':'#3fb950'):'#8b949e';
 let ev='';if(f.verdict==='true-positive'&&f.evidence&&f.evidence.reachability){const e=f.evidence;
  ev=`<div class="card" style="margin-top:10px"><h4>Preuve — evidence gate (3 jambes)</h4><div class="mono" style="font-size:11px">① atteignabilité : ${esc((e.reachability||{}).note||'')}<br>② frontière : ${esc((e.trust_boundary||{}).note||'')}<br>③ impact : ${esc((e.impact||{}).note||'')}</div></div>`;}
 OPEN='finding:'+fp;
 document.getElementById('modal').innerHTML=
  `<div class="mh"><span class="ic" style="background:${col}">⚠</span><h3>${esc(f.cwe||f.vuln_class)} · ${esc(f.symbol)}</h3><span class="x" onclick="closeModal()">✕</span></div>`+
  `<div class="mb"><div class="verdbar"><span class="vd ${vd.c}">${vd.l}</span><span class="vd">${esc(f.severity||'')}</span>${f.exploited?'<span class="vd" style="color:#f85149;border-color:#f85149">⚡ exploité en live</span>':''}<span class="vd">${esc(f.technique||'')}</span></div>`+
   `<div class="card" style="margin-top:10px"><h4>Le problème — ${esc(ci.name)}</h4><div class="expl">${esc(ci.problem)}</div><div class="hint" style="margin-top:6px"><b>Impact :</b> ${esc(ci.impact)}</div></div>`+
   (reason?`<div class="card" style="margin-top:10px"><h4>Décision du Triager (pourquoi écarté)</h4><div class="expl">${esc(reason)}</div></div>`:'')+ev+
   `<div class="card" style="margin-top:10px"><h4>Code incriminé — ${esc(f.file)}:${esc(f.symbol)}</h4>${highlightCode(f.source,f.line_start)}</div>`+
   ((f.exploited&&f.exploit_code)?`<div class="card" style="margin-top:10px"><h4>🧪 Code d'exploitation généré ET exécuté</h4><div class="hint" style="margin-bottom:5px">Ce script a réellement été lancé contre le testbed pour prouver l'exploitabilité.</div><pre class="data mono">${esc(f.exploit_code)}</pre></div>`:'')+
   ((f.exploited&&f.exploit&&f.exploit.request)?`<div class="card" style="margin-top:10px"><h4>Exécution &amp; résultat observé</h4><div class="mono" style="font-size:11px"><b>Requête envoyée :</b> ${esc(f.exploit.request)}<div style="margin-top:5px"><b>Réponse du testbed (extrait) :</b></div><pre class="data" style="margin-top:3px">${esc(f.exploit.response||'')}</pre><div class="okv" style="margin-top:5px">✅ Impact observé : ${esc(f.exploit.impact||'')}</div></div></div>`:'')+
   (f.remediation?`<div class="card" style="margin-top:10px"><h4>Remédiation (règle ${esc(f.rule_id||'')})</h4><pre class="expl">${esc(f.remediation)}</pre></div>`:'')+
  `</div>`;
 document.getElementById('ov').style.display='flex';}
let PANEL=null,SELFILE=null;
function togglePanel(id){const cur=PANEL===id;document.querySelectorAll('.panel').forEach(p=>p.style.display='none');
 document.querySelectorAll('.pull').forEach(b=>b.classList.remove('on'));
 if(cur){PANEL=null;return;}PANEL=id;document.getElementById('p-'+id).classList.add('on');
 document.getElementById('panel-'+id).style.display='block';renderPanels(LAST);}
function selFile(f){SELFILE=f;renderPanels(LAST);}
function renderPanels(s){if(!s||!PANEL)return;const rs=s.role_stats||{};
 if(PANEL==='res'){let tin=0,tout=0,tc=0,tcost=0;const ks=Object.keys(rs);ks.forEach(r=>{tin+=rs[r].in_tok;tout+=rs[r].out_tok;tc+=rs[r].calls;tcost+=rs[r].cost;});
  const mx=Math.max(1,...ks.map(r=>rs[r].calls));
  document.getElementById('panel-res').innerHTML=`<h3>Consommation de ressources</h3><div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px">`+
   `<div class="fcard"><div class="h">Appels LLM</div><b style="font-size:20px">${tc}</b></div>`+
   `<div class="fcard"><div class="h">Tokens in / out</div><b style="font-size:20px">${tin} / ${tout}</b></div>`+
   `<div class="fcard"><div class="h">Coût</div><b style="font-size:20px">$${tcost.toFixed(4)}</b><div class="hint">déterministe = $0</div></div>`+
   `<div class="fcard"><div class="h">Runtime</div><b style="font-size:20px">${(s.budget||{}).runtime_min||0} min</b></div></div>`+
   `<div class="bars">`+ks.map(r=>`<div class="bar"><span style="width:96px;color:${COL[r]||'#8b949e'}">${r}</span><i style="width:${Math.round(190*rs[r].calls/mx)}px;background:${COL[r]||'#8b949e'}"></i><span class="hint">${rs[r].calls} appels · ${rs[r].in_tok+rs[r].out_tok} tok · $${rs[r].cost}</span></div>`).join('')+`</div>`;}
 if(PANEL==='fleet'){const ag=s.agents||[];
  document.getElementById('panel-fleet').innerHTML=`<h3>Fleet — instances par catégorie (actives / configurées)</h3><div class="fleetgrid">`+
   NODES.filter(n=>rs[n.id]).map(n=>{const st=rs[n.id];let dots='';const tot=Math.max(st.configured||1,st.alive,1);
    for(let i=0;i<tot;i++)dots+=`<span class="inst-dot" style="background:${i<st.alive?COL[n.id]:'#2a3340'}"></span>`;
    return `<div class="fcard"><div class="h" style="color:${COL[n.id]}">${n.t}</div>${dots}<div class="hint">${st.alive} active(s) / ${st.configured||1} configurée(s)</div></div>`;}).join('')+`</div>`;}
 if(PANEL==='code'){const srcs=s.sources||{};const files=Object.keys(srcs).sort();
  if(!SELFILE||!srcs[SELFILE])SELFILE=files.find(f=>f.endsWith('db.py'))||files[0];
  document.getElementById('panel-code').innerHTML=`<h3>Code source évalué (${files.length} fichiers)</h3><div style="display:flex;gap:14px"><div style="min-width:170px">`+
   files.map(f=>`<div class="filerow ${f===SELFILE?'on':''}" onclick="selFile('${f}')">${esc(f)}</div>`).join('')+`</div><div style="flex:1;min-width:0">${highlightCode(srcs[SELFILE]||'',1)}</div></div>`;}
 if(PANEL==='find'){const F=s.findings||[];const byv={};F.forEach(f=>{(byv[f.verdict||'candidate']=byv[f.verdict||'candidate']||[]).push(f);});
  document.getElementById('panel-find').innerHTML=`<h3>Findings — seuls les true-positive sont publiés ; le reste est filtré (cliquez pour le détail)</h3>`+
   ['true-positive','false-positive','not-applicable','needs-review'].map(v=>{const l=byv[v]||[];if(!l.length)return '';const vd=VERD[v];
    return `<div style="margin-bottom:8px"><span class="vd ${vd.c}">${vd.l} (${l.length})</span><div style="margin-top:5px">`+
     l.map(f=>`<div class="row mono frow sev-${f.severity||'low'}" onclick="openFinding('${f.fp}')">${esc(f.cwe||f.vuln_class)} · ${esc(f.symbol)} <span style="color:#8b949e">(${esc(f.file)})</span>${f.exploited?' <span class=badv>⚡</span>':''}</div>`).join('')+`</div></div>`;}).join('');}
 if(PANEL==='out'){const fu=s.funnel||{};const pr=s.priority||[];
  const proven=pr.filter(g=>g.exploited),conf=pr.filter(g=>!g.exploited);
  const stg=(n,l,c)=>`<div class="fstage"><div class="fn" style="color:${c}">${n==null?'—':n}</div><div class="fl">${l}</div></div>`;
  const arr=t=>`<div class="farrow">▶<div class="fd">${t}</div></div>`;
  const row=g=>`<div class="row mono frow sev-${g.severity}" onclick="openFinding('${g.fps[0]}')">${g.exploited?'<span class=badv>⚡</span> ':''}${esc(g.cwes.join('/'))} · <b>${esc(g.symbol)}</b> <span style="color:#8b949e">(${esc(g.file)})</span>${g.dup?` <span class="chip" style="background:${COL.detector};color:#0b0f14">×${g.fps.length} règles</span>`:''}</div>`;
  document.getElementById('panel-out').innerHTML=`<h3>Sortie — entonnoir de pertinence &amp; liste priorisée par exploitation réelle</h3>`+
   `<div class="funnel">`+stg(fu.detected,'détectés','#79c0ff')+arr(`−${fu.false_positive||0} FP · −${fu.not_applicable||0} NA · −${fu.needs_review||0} NR`)+
    stg(fu.true_positive,'confirmés','#bc8cff')+arr(`−${fu.duplicates||0} doublons`)+
    stg(fu.distinct,'distincts','#34d399')+arr(`${(fu.distinct||0)-(fu.exploited||0)} non démontrés`)+
    stg(fu.exploited,'exploités','#f85149')+`</div>`+
   `<div class="grid2" style="margin-top:12px"><div class="card"><h4>⚡ Tier 1 — prouvés en live (prioritaires)</h4>${proven.map(row).join('')||'<span class=hint>—</span>'}</div>`+
   `<div class="card"><h4>✓ Tier 2 — confirmés, non démontrés en live (présence = vuln)</h4>${conf.map(row).join('')||'<span class=hint>—</span>'}</div></div>`;}
}
function render(s){LAST=s;
 const F=s.findings||[];
 const cand=F.length,tp=F.filter(f=>f.verdict==='true-positive').length,exploited=F.filter(f=>f.exploited).length,
   nr=F.filter(f=>f.verdict==='needs-review').length,pub=F.filter(f=>f.state==='published').length,
   exploitableTP=F.filter(f=>f.verdict==='true-positive'&&['CWE-89','CWE-78','CWE-918','CWE-639','CWE-22','CWE-502','CWE-79'].includes(f.cwe)).length;
 const cov=s.coverage||[],covDone=cov.filter(c=>c.state==='covered').length,covOpen=cov.length-covDone;
 STATE={cand,tp,exploited,exploitableTP,covOpen,covDone:s.coverage_complete};
 CUR_EDGE=(s.current&&s.current.edge)?s.current.edge:null;const curRole=s.active_role;
 const rstat=s.role_stats||{};
 // badges d'instances par catégorie
 for(const n of NODES){const rs=rstat[n.id]||{configured:0,alive:0};
  const conf=rs.configured||1,run=rs.alive||0;const b=document.getElementById('inst-'+n.id);
  b.textContent='×'+conf+(run?(' · '+run+' actif'+(run>1?'s':'')):'');
  b.classList.toggle('run',run>0);b.style.background=run>0?COL[n.id]:'#0b0f14';}
 document.getElementById('run').textContent='run '+(s.run_dir||'—');
 const cb=document.getElementById('cov');cb.textContent=s.coverage_complete?'couverture complète':'couverture en cours';cb.className='badge'+(s.coverage_complete?' on':'');
 document.getElementById('gap').textContent=(s.rule_gaps||0)+' rule-gap(s)';
 const tech={};F.forEach(f=>{const t=(f.technique||'').split(':')[0];tech[t]=(tech[t]||0)+1});
 const chips=['rule','secrets','deps','exploratory'].map(t=>`<span class="chip ${tech[t]?'hot':''}" style="${tech[t]?'background:'+COL.detector+';border-color:'+COL.detector:''}">${t} ${tech[t]||0}</span>`).join('');
 const corp=Object.entries(s.corpora||{}).map(([k,v])=>`${k}·${v}`).join('  ');
 const cur=id=>s.mode==='step'&&curRole===id;const alive=r=>(rstat[r]||{}).alive||0;
 setbd('operator',`goals définis · <span class="big">1</span> évaluation`,true,cur('operator'));
 setbd('orchestrator',`<span class="dot"></span>${(s.agents||[]).filter(a=>a.status==='alive').length} agents · supervisé`,true,cur('orchestrator'));
 setbd('indexer',`<span class="big">${(s.index||{}).functions||0}</span> fonctions · queryable`,((s.index||{}).functions||0)>0,cur('indexer'));
 setbd('cartographer',`<span class="big">${(s.flows||[]).length}</span> chaînes · carte de flux`,(s.flows||[]).length>0,cur('cartographer'));
 setbd('detector',`<span class="big">${cand}</span> candidats<div class="chips">${chips}</div>`,cand>0,cur('detector'));
 const vv=s.verdicts||{};
 setbd('triager',`<span class="big">${tp}</span> TP confirmés<div class="verdbar"><span class="vd fp">${vv['false-positive']||0} FP</span><span class="vd na">${vv['not-applicable']||0} NA</span><span class="vd nr">${vv['needs-review']||0} NR</span></div>`,tp>0,cur('triager'));
 setbd('validator',`testbed · <span class="big">${exploited}</span> ⚡ exploités`,exploited>0,cur('validator'));
 setbd('reporter',`<span class="big">${(s.funnel||{}).distinct||pub}</span> distincts<div class="verdbar"><span class="vd tp">${(s.funnel||{}).exploited||0} ⚡ prouvés</span><span class="vd">${pub} publiés</span></div>`,pub>0,cur('reporter'));
 setbd('coverage',`${covDone}/${cov.length} couverts<div class="chips"><span class="chip">${corp}</span></div>`,s.coverage_complete,cur('coverage'));
 if(s.mode==='step'){document.getElementById('ctrl').style.display='inline-flex';
   document.getElementById('insp').style.display='block';document.getElementById('stage').classList.add('insp-on');
   const c=s.current;document.getElementById('stepn').textContent='étape '+(c?c.n:0);
   document.getElementById('i-ttl').textContent=c?c.title:'— prêt —';
   document.getElementById('i-sum').textContent=c?c.summary:'Cliquez ⏭ pour démarrer.';
   document.getElementById('i-data').innerHTML=renderData(c);
   document.getElementById('i-log').innerHTML=(s.steplog||[]).slice().reverse().map(it=>`<div class="it ${c&&it.n===c.n?'cur':''}">${it.n}. [${it.role}] ${esc(it.title)}</div>`).join('');
   document.getElementById('b-step').disabled=!!s.done;}
 const fu=s.funnel||{};document.getElementById('outflow').textContent=`${fu.detected||cand} détectés → ${fu.true_positive||tp} confirmés → ${fu.distinct||0} distincts → ${fu.exploited||0} exploités · filtrés ${fu.false_positive||0} FP/${fu.not_applicable||0} NA/${fu.needs_review||0} NR`;
 if(OPEN&&!String(OPEN).startsWith('finding:'))renderModal();
 if(PANEL)renderPanels(s);
}
async function getState(){try{return await(await fetch('/api/state')).json()}catch(e){return null}}
let auto=null;
async function doStep(){const s=await(await fetch('/api/step',{method:'POST'})).json();render(s);if(s.done)stopAuto();}
async function doReset(){stopAuto();const s=await(await fetch('/api/reset',{method:'POST'})).json();render(s);}
function stopAuto(){if(auto){clearInterval(auto);auto=null;document.getElementById('b-play').textContent='▶';}}
function toggleAuto(){if(auto){stopAuto();}else{document.getElementById('b-play').textContent='⏸';auto=setInterval(doStep,1300);}}
document.getElementById('b-step').onclick=doStep;document.getElementById('b-reset').onclick=doReset;document.getElementById('b-play').onclick=toggleAuto;
addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
(async()=>{const s=await getState();if(!s)return;render(s);
 if(s.mode!=='step'){setInterval(async()=>{const x=await getState();if(x)render(x);},1000);}})();
</script></body></html>
"""
