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
.canvas{position:relative;width:1520px;height:800px;margin:18px auto;
background-image:radial-gradient(var(--grid) 1px,transparent 1px);background-size:22px 22px}
svg.edges{position:absolute;left:0;top:0;width:1520px;height:800px;pointer-events:none}
.node{position:absolute;width:166px;border:1px solid var(--line);border-top:3px solid var(--mut);border-radius:12px;
background:#0f1620;box-shadow:0 6px 18px rgba(0,0,0,.35);overflow:hidden;cursor:pointer;transition:box-shadow .2s,transform .15s}
.node:hover{transform:translateY(-2px)}
.node.active{box-shadow:0 0 0 1px var(--acc),0 6px 22px rgba(88,166,255,.22)}
.node.cur{box-shadow:0 0 0 2px var(--warn),0 0 26px rgba(210,153,34,.5);transform:scale(1.04);z-index:5}
.node.ext{opacity:.85;background:#0c1118;border:1px dashed #44505e;border-top:3px dashed #8b949e}
.node.ext .bd{color:#7d8794;font-style:italic}
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
.ov{position:fixed;inset:0;display:none;z-index:40;pointer-events:none}
.modal{position:fixed;left:70px;top:100px;width:560px;max-width:92vw;max-height:80vh;overflow:auto;
background:#0f1620;border:1px solid var(--line);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.6);pointer-events:auto}
.winhead{cursor:move;user-select:none}
.modal .mh{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)}
/* widget flottant de file de tâches */
.qwin{position:fixed;left:16px;top:150px;width:344px;max-height:60vh;overflow:auto;background:#0f1620;
border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 36px rgba(0,0,0,.5);z-index:16}
.qhead{display:flex;align-items:center;gap:6px;padding:8px 11px;border-bottom:1px solid var(--line);font-weight:700;font-size:12px;cursor:move}
.qhead .qx{margin-left:auto;cursor:pointer;color:var(--mut);border:1px solid var(--line);border-radius:5px;padding:0 7px;font-size:13px}
.qbody{padding:8px 11px}.qstat{font-size:11px;margin-bottom:6px;line-height:1.7}
.qrow{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;padding:2px 0;border-bottom:1px solid #161b22;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qrow.qcur{background:rgba(210,153,34,.14)}
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
.leg-flow{position:fixed;left:14px;bottom:10px;font-size:10.5px;color:var(--mut);background:rgba(13,17,23,.82);border:1px solid var(--line);border-radius:8px;padding:5px 10px;z-index:15}
.leg-flow b{color:var(--ink)}
</style></head><body>
<header>
  <h1><b>FORGE</b> · pipeline</h1>
  <span class="badge" id="run">run —</span>
  <span class="badge" id="cov">coverage —</span>
  <span class="badge" id="gap">rule-gaps —</span>
  <span class="ctrl" id="ctrl">
    <button class="btn" id="b-reset" title="restart">⏮</button>
    <button class="btn play" id="b-play" title="auto-play">▶</button>
    <button class="btn" id="b-step" title="next step">⏭</button>
    <span class="stepn" id="stepn">step 0</span>
  </span>
  <a class="tg" href="/panels">panels view →</a>
</header>
<div class="pulls">
  <span class="pull" id="p-res" onclick="togglePanel('res')">⚙ Resources</span>
  <span class="pull" id="p-fleet" onclick="togglePanel('fleet')">👥 Fleet</span>
  <span class="pull" id="p-code" onclick="togglePanel('code')">&lt;/&gt; Source</span>
  <span class="pull" id="p-find" onclick="togglePanel('find')">🛡 Findings</span>
  <span class="pull" id="p-out" onclick="togglePanel('out')">📤 Prioritized output</span>
  <span class="pull on" id="p-tasks" onclick="toggleQueue()">📋 Queue widget</span>
  <span class="pull" id="p-exch" onclick="togglePanel('exch')">🔀 Exchanges</span>
  <span class="pull" id="p-tools" onclick="togglePanel('tools')">🧰 Tools</span>
  <span class="pull" id="p-fixes" onclick="togglePanel('fixes')">🛠 Fixes</span>
  <span class="pull" id="p-stories" onclick="togglePanel('stories')">📖 Stories</span>
  <span style="margin-left:auto;font-size:11px;color:var(--mut)" id="outflow">—</span>
</div>
<div class="panel" id="panel-res"></div>
<div class="panel" id="panel-fleet"></div>
<div class="panel" id="panel-code"></div>
<div class="panel" id="panel-find"></div>
<div class="panel" id="panel-out"></div>
<div class="panel" id="panel-tasks"></div>
<div class="panel" id="panel-exch"></div>
<div class="panel" id="panel-tools"></div>
<div class="panel" id="panel-fixes"></div>
<div class="panel" id="panel-stories"></div>
<div class="stage" id="stage"><div class="canvas" id="cv"><svg class="edges" id="svg" viewBox="0 0 1520 800"></svg></div></div>
<aside class="insp" id="insp">
  <h2>Inspector — current step data</h2>
  <div class="ttl" id="i-ttl">—</div><div class="sum" id="i-sum"></div>
  <div id="i-data"></div>
  <div class="slog"><h2>Step log</h2><div id="i-log"></div></div>
</aside>
<div class="leg-flow">━ data flow (animated) &nbsp;·&nbsp; ┄ supervision (orchestrator → all) &nbsp;·&nbsp; <b>click an edge</b> for its exchange contract · <b>drag</b> the windows · ┈ extension roles (§6)</div>
<div class="qwin win" id="qwidget"><div class="qhead winhead">📋 Task queue (live)<span class="qx" onclick="document.getElementById('qwidget').style.display='none';document.getElementById('p-tasks').classList.remove('on')">–</span></div><div class="qbody" id="qbody"></div></div>
<div class="ov" id="ov"><div class="modal win" id="modal"></div></div>
<script>
const COL={operator:'#9aa5b1',orchestrator:'#58a6ff',indexer:'#39c5cf',cartographer:'#34d399',
detector:'#f59e0b',triager:'#bc8cff',validator:'#f85149',reporter:'#7ee787',coverage:'#e879f9'};
const INFO={
 operator:{d:"The human who sets the goals, starts and steers the evaluation.",tools:['forge CLI','goals'],in:['forge.yaml'],out:['evaluation']},
 orchestrator:{d:"Single surface: validates, spawns and supervises the fleet, enforces budget.",tools:['heartbeat supervisor','work queue','budget governor'],in:['config','fleet state'],out:['live fleet','status']},
 indexer:{d:"Builds the code index (deterministic parser). Gates the fleet (FR-003).",tools:['AST parser','call graph','citation resolver'],in:['source code'],out:['queryable index']},
 cartographer:{d:"Security map: entry→sink call chains, trust boundaries, validation.",tools:['index queries','call chains','validation detection'],in:['index','source','goals'],out:['data-flow map']},
 detector:{d:"Produces candidates: CodeGuard rules + secrets + dependencies + exploration.",tools:['CodeGuard corpus (rules)','secret scan','dependency scan','free exploration'],in:['index','map','federated corpus'],out:['candidates','rule-gaps']},
 triager:{d:"Investigates and assigns the verdict via the evidence gate (verified citations).",tools:['citation resolution','3-leg evidence gate'],in:['candidate','index','map'],out:['verdict + evidence']},
 validator:{d:"Reproduces impact on the live testbed (exploitation oracles).",tools:['HTTP oracles: SQLi · XSS · cmd · SSRF · IDOR · traversal · deser','testbed'],in:['TP finding','testbed'],out:['exploited flag','runnable PoC']},
 reporter:{d:"Writes one report per TP + the rollup (CWE/CVSS/OWASP).",tools:['Markdown rendering','CWE/CVSS/OWASP mapping'],in:['TP findings','map'],out:['reports','rollup']},
 coverage:{d:"Turns goals into a checklist and declares coverage complete.",tools:['checklist','OWASP/CWE references'],in:['goals','map'],out:['coverage flag','directed tasks']},
};
const NODES=[
 {id:'operator',ic:'OP',t:'Operator',x:20,y:280},{id:'orchestrator',ic:'OR',t:'Orchestrator',x:210,y:280},
 {id:'indexer',ic:'IX',t:'Indexer',x:400,y:150},{id:'cartographer',ic:'CA',t:'Cartographer',x:590,y:410},
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
const NS='http://www.w3.org/2000/svg';
// Supervision : l'Orchestrateur interagit avec TOUS les agents (pointillés discrets, cliquables).
for(const id of ['indexer','cartographer','detector','triager','validator','reporter','coverage']){
 const a=out(N['orchestrator']),b=inp(N[id]);const p=document.createElementNS(NS,'path');
 p.setAttribute('d',mkpath(a,b));p.setAttribute('fill','none');p.setAttribute('stroke','#8b949e');
 p.setAttribute('stroke-width','1');p.setAttribute('stroke-dasharray','3 5');p.setAttribute('opacity','0.16');
 p.style.cursor='pointer';p.style.pointerEvents='stroke';p.onclick=()=>openExchange('orchestrator','(all)');svg.appendChild(p);}
const EP=[];
for(const e of EDGES){const a=out(N[e.f]),b=inp(N[e.t]);
 const p=document.createElementNS(NS,'path');p.setAttribute('d',mkpath(a,b));
 p.setAttribute('fill','none');p.setAttribute('stroke','#222b36');p.setAttribute('stroke-width','2');svg.appendChild(p);
 const hit=document.createElementNS(NS,'path');hit.setAttribute('d',mkpath(a,b));hit.setAttribute('fill','none');
 hit.setAttribute('stroke','transparent');hit.setAttribute('stroke-width','14');hit.style.cursor='pointer';
 hit.style.pointerEvents='stroke';hit.onclick=()=>openExchange(e.f,e.t);svg.appendChild(hit);
 const dots=[];for(let k=0;k<4;k++){const c=document.createElementNS(NS,'circle');
  c.setAttribute('r','3.6');c.setAttribute('opacity','0');svg.appendChild(c);dots.push(c);}
 EP.push({e,p,dots,len:p.getTotalLength()});}
const EXTN_BYID={};
const EXTN=[
 {id:'self-improver',ic:'SI',t:'Self-Improver',x:300,y:700,anchor:'detector',desc:"Reads the fleet's own logs, metrics and rule-gap records; proposes configuration, prompt and detection-rule changes to the operator. Closes the detection\u2192prevention flywheel (FR-042)."},
 {id:'deep-tester',ic:'DT',t:'Deep-Tester',x:600,y:700,anchor:'detector',desc:"Input-generation testing (fuzzing, property-based) against specific functions or endpoints the core pipeline already flagged. Depth where Detector gave breadth."},
 {id:'variant-hunter',ic:'VH',t:'Variant-Hunter',x:880,y:700,anchor:'triager',desc:"Given one confirmed finding, searches the rest of the target for the same pattern."},
 {id:'attack-mapper',ic:'AM',t:'Attack-Mapper',x:1140,y:700,anchor:'reporter',desc:"Assembles confirmed findings into a privilege graph showing how they chain from attacker entry points to operator-defined goals."},
 {id:'remediator',ic:'RM',t:'Remediator',x:1340,y:700,anchor:'reporter',desc:"Generates and verifies candidate patches for confirmed findings (see the \uD83D\uDEE0 Fixes panel)."},
];
for(const x of EXTN){const a=N[x.anchor];
 const pa=document.createElementNS(NS,'path');
 pa.setAttribute('d',`M ${a.x+NW/2} ${a.y+NH} C ${a.x+NW/2} ${a.y+NH+40}, ${x.x+NW/2} ${x.y-40}, ${x.x+NW/2} ${x.y}`);
 pa.setAttribute('fill','none');pa.setAttribute('stroke','#5b6673');pa.setAttribute('stroke-width','1.4');pa.setAttribute('stroke-dasharray','4 5');pa.setAttribute('opacity','0.55');svg.appendChild(pa);
 const d=document.createElement('div');d.className='node ext';d.id='x-'+x.id;d.style.left=x.x+'px';d.style.top=x.y+'px';
 d.innerHTML=`<div class="hd"><span class="ic" style="background:#8b949e">${x.ic}</span><span style="color:#aab4c0">${x.t}</span><span class="inst" style="border-color:#5b6673">\u00A76 EXT</span></div><div class="bd">extension role \u00B7 not in core</div>`;
 d.onclick=()=>openExt(x.id);cv.appendChild(d);EXTN_BYID[x.id]=x;}
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
function openModal(role){OPEN=role;renderModal();document.getElementById('ov').style.display='block';}
function closeModal(){OPEN=null;document.getElementById('ov').style.display='none';}
document.getElementById('ov').onclick=e=>{if(e.target.id==='ov')closeModal();};
function renderModal(){if(!OPEN||!LAST)return;const s=LAST,role=OPEN,inf=INFO[role]||{},col=COL[role];
 const rs=(s.role_stats||{})[role]||{alive:0,configured:0,calls:0,in_tok:0,out_tok:0,cost:0};
 const inst=rs.configured||1, run=rs.alive||0;
 const F=s.findings||[];const mine=findingsByRole(role,F);
 let outHtml='';
 if(role==='detector'||role==='triager'||role==='validator'||role==='reporter'){
   outHtml=`<div class="leg">${mine.length} finding(s) — click for details</div>`+mine.slice(0,14).map(f=>`<div class="row mono frow sev-${f.severity||'low'}" onclick="openFinding('${f.fp}')">${esc(f.cwe||f.vuln_class)} ${esc(f.symbol)} ${f.exploited?'<span class=badv>⚡</span>':''}<span style="color:#8b949e"> ${esc(f.verdict||'')}</span></div>`).join('')||'<span class=hint>—</span>';
 } else if(role==='indexer'){outHtml=`<div class="data">${(s.index||{}).functions||0} indexed functions</div>`;}
 else if(role==='cartographer'){outHtml=`<div class="data">${(s.flows||[]).length} mapped call chains</div>`;}
 else if(role==='coverage'){const c=s.coverage||[];outHtml=`<div class="data">${c.filter(x=>x.state==='covered').length}/${c.length} components covered</div>`;}
 else if(role==='operator'){const US=s.user_stories||[];outHtml=`<div class="hint" style="margin-bottom:4px">Operator intents that trigger the Orchestrator:</div>`+US.slice(0,10).map(u=>`<div class="row" style="font-size:11px"><b style="color:#58a6ff">${esc(u.id)}</b> ${esc(u.want)} <span style="color:#3fb950">→ ${esc(u.trigger)}</span></div>`).join('');}
 else {outHtml=`<div class="data">${(s.agents||[]).length} agents in the fleet</div>`;}
 const claim=(s.agents||[]).find(a=>a.role===role&&a.claim);
 document.getElementById('modal').innerHTML=
  `<div class="mh winhead"><span class="ic" style="background:${col}">${(N[role]||{ic:'··'}).ic||'··'}</span>`+
  `<h3 style="color:${col}">${(N[role]||{t:role}).t}</h3><span class="x" onclick="closeModal()">✕</span></div>`+
  `<div class="mb"><div class="desc">${inf.d||''}</div>`+
  `<div class="grid2">`+
   `<div class="card"><h4>Instances</h4><div class="tok"><span><b style="color:${col}">${run}</b> running</span><span><b>${inst}</b> configured</span></div>`+
     (claim?`<div class="hint">▶ ${esc(claim.claim)}</div>`:`<div class="hint">— idle —</div>`)+`</div>`+
   `<div class="card"><h4>Token usage</h4><div class="tok"><span><b>${rs.calls}</b> calls</span></div>`+
     `<div class="hint">in ${rs.in_tok} · out ${rs.out_tok} tok · $${rs.cost}</div></div>`+
  `</div>`+
  `<div class="card" style="margin-bottom:12px"><h4>Tools</h4><div class="taglist">${(inf.tools||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
  `<div class="grid2">`+
   `<div class="card"><h4>Inputs</h4><div class="taglist">${(inf.in||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
   `<div class="card"><h4>Outputs</h4><div class="taglist">${(inf.out||[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></div>`+
  `</div>`+
  `<div class="card" style="margin-top:12px"><h4>Findings produced / artifacts</h4>${outHtml}</div></div>`;
}

function renderData(cur){if(!cur)return '';const d=cur.data||{};let h='';
 if(d.testbed_url)h+=`<div class="data mono">${esc(d.testbed_url)}</div>`;
 if(d.functions)h+=`<div class="leg">${d.functions.length} indexed functions</div><div class="data mono">${d.functions.slice(0,16).map(f=>`${esc(f.file)} · <b>${esc(f.name)}</b>(${esc((f.params||[]).join(', '))})`).join('<br>')}${d.functions.length>16?'<br>…':''}</div>`;
 if(d.flows)h+=`<div class="leg">call chains (entry → sink)</div><div class="data">${d.flows.map(f=>{const ch=f.chain.map(x=>String(x).startsWith('→sink:')?`<span class=sink>${esc(x)}</span>`:esc(x)).join(' → ');return `<div class="row mono">${f.validated?'<span class=okv>✅</span>':'<span class=badv>⚠️</span>'} <b>${esc(f.entry)}</b>: ${ch}</div>`}).join('')}</div>`;
 if(d.items)h+=`<div class="leg">coverage items</div><div class="data mono">${d.items.map(i=>esc(i.component)+' × '+esc(i.goal)).join('<br>')}</div>`;
 if(d.candidates)h+=`<div class="leg">candidates produced</div><div class="data">${d.candidates.map(c=>`<div class="row mono">${esc(c.vuln_class)} · <b>${esc(c.symbol)}</b> <span style=color:#8b949e>(${esc(c.file)} · ${esc(c.technique)})</span></div>`).join('')||'—'}</div>`;
 if(d.finding&&d.evidence){const f=d.finding,e=d.evidence;
   h+=`<div class="leg">finding</div><div class="data mono">${esc(f.cwe)} · <b>${esc(f.symbol)}</b> · ${esc(f.file)}<br>verdict: <b>${esc(f.verdict)}</b> · severity: ${esc(f.severity||'—')}</div>`;
   h+=`<div class="leg">evidence gate — 3 legs</div><div class="data mono">① reachability: ${esc((e.reachability||{}).symbol||'')} ${esc((e.reachability||{}).note||'')}<br>② boundary: ${esc((e.trust_boundary||{}).note||'')}<br>③ impact: ${esc((e.impact||{}).symbol||'')} ${esc((e.impact||{}).note||'')}</div>`;}
 if('exploited' in d){h+=`<div class="leg">validation result</div><div class="data">${d.exploited?'<span class=okv><b>⚡ EXPLOITED on the testbed</b></span>':'<span class=badv>not reproduced</span>'}</div>`;
   if(d.poc)h+=`<div class="leg">exploit code generated AND executed</div><pre class="data mono">${esc(d.poc)}</pre>`;
   if(d.trace&&d.trace.request)h+=`<div class="leg">observed execution</div><div class="data mono"><b>Request:</b> ${esc(d.trace.request)}<br><b>Response:</b><pre class="data" style="margin-top:3px">${esc(d.trace.response||'')}</pre><span class="okv">✅ ${esc(d.trace.impact||'')}</span></div>`;}
 if(d.published)h+=`<div class="leg">published findings</div><div class="data">${d.published.map(p=>`<div class="row mono sev-${p.severity}">${esc(p.cwe)} ${esc(p.symbol)} [${esc(p.severity)}]${p.exploited?' <span class=badv>⚡</span>':''}</div>`).join('')}</div>`;
 return h;}

const CWE_INFO={
 'CWE-89':{name:'SQL Injection',problem:"A SQL query is built by concatenating untrusted input.",impact:"Authentication bypass, read/modify the database."},
 'CWE-79':{name:'Cross-Site Scripting',problem:"HTML is returned without escaping user input.",impact:"Arbitrary JavaScript in the victim's browser, session theft."},
 'CWE-78':{name:'Command Injection',problem:"A shell command is built from untrusted input (shell=True).",impact:"Arbitrary code execution on the server (RCE)."},
 'CWE-918':{name:'SSRF',problem:"The server fetches an attacker-controlled URL, no allowlist.",impact:"Access to internal services and cloud metadata."},
 'CWE-639':{name:'IDOR / broken access control',problem:"Access to a record by id without checking the caller's authorization.",impact:"Read/modify other users' data."},
 'CWE-22':{name:'Path traversal',problem:"A file path is built from an unsanitized name.",impact:"Arbitrary file read (secrets, /etc/passwd)."},
 'CWE-502':{name:'Unsafe deserialization',problem:"Untrusted data is deserialized (pickle).",impact:"Arbitrary code execution (RCE)."},
 'CWE-798':{name:'Hardcoded secret',problem:"A secret/key is hardcoded in the source.",impact:"Direct compromise for anyone with repo access."},
 'CWE-327':{name:'Weak crypto',problem:"Deprecated hash primitive (MD5/SHA-1) used for security.",impact:"Collisions / easier cracking."},
 'CWE-916':{name:'Weak password hash',problem:"Password hashed without a slow, salted KDF.",impact:"Password cracking by brute force."},
 'CWE-1035':{name:'Vulnerable dependency',problem:"Third-party dependency with a published vulnerability (CVE).",impact:"Exploitation of the dependency's known flaw."},
 'CWE-120':{name:'Copy without bounds check',problem:"Copy into a fixed buffer without checking input size.",impact:"Memory overflow — ONLY if the input is not otherwise bounded."},
 'CWE-208':{name:'Timing side-channel',problem:"Potentially observable timing difference.",impact:"Information leak via timing — often hard to prove."},
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
  ev=`<div class="card" style="margin-top:10px"><h4>Evidence — evidence gate (3 legs)</h4><div class="mono" style="font-size:11px">① reachability: ${esc((e.reachability||{}).note||'')}<br>② boundary: ${esc((e.trust_boundary||{}).note||'')}<br>③ impact: ${esc((e.impact||{}).note||'')}</div></div>`;}
 OPEN='finding:'+fp;
 document.getElementById('modal').innerHTML=
  `<div class="mh winhead"><span class="ic" style="background:${col}">⚠</span><h3>${esc(f.cwe||f.vuln_class)} · ${esc(f.symbol)}</h3><span class="x" onclick="closeModal()">✕</span></div>`+
  `<div class="mb"><div class="verdbar"><span class="vd ${vd.c}">${vd.l}</span><span class="vd">${esc(f.severity||'')}</span>${f.exploited?'<span class="vd" style="color:#f85149;border-color:#f85149">⚡ exploited live</span>':''}<span class="vd">${esc(f.technique||'')}</span></div>`+
   `<div class="card" style="margin-top:10px"><h4>The issue — ${esc(ci.name)}</h4><div class="expl">${esc(ci.problem)}</div><div class="hint" style="margin-top:6px"><b>Impact:</b> ${esc(ci.impact)}</div></div>`+
   (reason?`<div class="card" style="margin-top:10px"><h4>Triager decision (why dismissed)</h4><div class="expl">${esc(reason)}</div></div>`:'')+ev+
   `<div class="card" style="margin-top:10px"><h4>Offending code — ${esc(f.file)}:${esc(f.symbol)}</h4>${highlightCode(f.source,f.line_start)}</div>`+
   ((f.exploited&&f.exploit_code)?`<div class="card" style="margin-top:10px"><h4>🧪 Exploit code generated AND executed</h4><div class="hint" style="margin-bottom:5px">This script was actually run against the testbed to prove exploitability.</div><pre class="data mono">${esc(f.exploit_code)}</pre></div>`:'')+
   ((f.exploited&&f.exploit&&f.exploit.request)?`<div class="card" style="margin-top:10px"><h4>Execution &amp; observed result</h4><div class="mono" style="font-size:11px"><b>Request sent:</b> ${esc(f.exploit.request)}<div style="margin-top:5px"><b>Testbed response (excerpt):</b></div><pre class="data" style="margin-top:3px">${esc(f.exploit.response||'')}</pre><div class="okv" style="margin-top:5px">✅ Observed impact: ${esc(f.exploit.impact||'')}</div></div></div>`:'')+
   (f.remediation?`<div class="card" style="margin-top:10px"><h4>Remediation (rule ${esc(f.rule_id||'')})</h4><pre class="expl">${esc(f.remediation)}</pre></div>`:'')+
   ((f.fix&&f.fix.safe_code)?`<div class="card" style="margin-top:10px"><h4 style="color:#3fb950">🛠 Fix proposal — safe code</h4><div class="hint" style="margin-bottom:6px">${(f.fix.steps||[]).map(x=>'• '+esc(x)).join('<br>')}</div><pre class="data mono" style="border-color:#3fb950">${esc(f.fix.safe_code)}</pre></div>`:'')+
  `</div>`;
 document.getElementById('ov').style.display='block';}
function openExt(id){const x=EXTN_BYID[id];if(!x)return;OPEN='ext:'+id;
 document.getElementById('modal').innerHTML=`<div class="mh winhead"><span class="ic" style="background:#8b949e">${x.ic}</span><h3>${esc(x.t)} <span class="vd" style="border-color:#8b949e;color:#8b949e">extension \u00A76</span></h3><span class="x" onclick="closeModal()">\u2715</span></div><div class="mb"><div class="expl">${esc(x.desc)}</div><div class="hint" style="margin-top:8px">Described in spec.md \u00A74.3 / \u00A76 (extension role, not specified with FRs). Build after the eight core roles produce trustworthy findings.</div><div class="hint">Plugs in at: <b>${esc(x.anchor)}</b>.</div></div>`;
 document.getElementById('ov').style.display='block';}
function openExchange(f,t){const s=LAST;if(!s||!s.protocol)return;const ex=s.protocol.exchanges||[];
 const e=ex.find(x=>x.frm===f&&x.to===t)||ex.find(x=>x.frm===f&&(x.to==='(all)'||x.to==='(output)'));
 if(!e)return;OPEN='exch:'+e.id;
 document.getElementById('modal').innerHTML=
  `<div class="mh winhead"><span class="ic" style="background:#58a6ff">⇄</span><h3>${esc(e.label)}</h3><span class="x" onclick="closeModal()">✕</span></div>`+
  `<div class="mb"><div class="verdbar"><span class="vd">${esc(e.frm)} → ${esc(e.to)}</span><span class="vd" style="border-color:#58a6ff;color:#58a6ff">payload: ${esc(e.payload)}</span></div>`+
   `<div class="card" style="margin-top:10px"><h4>Data (normalized schema)</h4><table class="mono" style="font-size:11.5px;width:100%">${(e.fields||[]).map(fl=>`<tr><td style="color:#79c0ff;padding-right:12px;vertical-align:top">${esc(fl[0])}</td><td style="color:#8b949e">${esc(fl[1])}</td></tr>`).join('')}</table></div>`+
   `<div class="grid2" style="margin-top:10px"><div class="card"><h4>Format</h4><div class="expl">${esc(e.format)}</div></div>`+
   `<div class="card"><h4>Normative references</h4><div class="taglist">${(e.refs||[]).map(r=>`<span>${esc(r)}</span>`).join('')}</div></div></div>`+
  `</div>`;
 document.getElementById('ov').style.display='block';}
let PANEL=null,SELFILE=null;
function togglePanel(id){const cur=PANEL===id;document.querySelectorAll('.panel').forEach(p=>p.style.display='none');
 document.querySelectorAll('.pull').forEach(b=>b.classList.remove('on'));
 if(cur){PANEL=null;return;}PANEL=id;document.getElementById('p-'+id).classList.add('on');
 document.getElementById('panel-'+id).style.display='block';renderPanels(LAST);}
function selFile(f){SELFILE=f;renderPanels(LAST);}
function renderPanels(s){if(!s||!PANEL)return;const rs=s.role_stats||{};
 if(PANEL==='res'){let tin=0,tout=0,tc=0,tcost=0;const ks=Object.keys(rs);ks.forEach(r=>{tin+=rs[r].in_tok;tout+=rs[r].out_tok;tc+=rs[r].calls;tcost+=rs[r].cost;});
  const mx=Math.max(1,...ks.map(r=>rs[r].calls));
  document.getElementById('panel-res').innerHTML=`<h3>Resource usage</h3><div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px">`+
   `<div class="fcard"><div class="h">LLM calls</div><b style="font-size:20px">${tc}</b></div>`+
   `<div class="fcard"><div class="h">Tokens in / out</div><b style="font-size:20px">${tin} / ${tout}</b></div>`+
   `<div class="fcard"><div class="h">Cost</div><b style="font-size:20px">$${tcost.toFixed(4)}</b><div class="hint">deterministic = $0</div></div>`+
   `<div class="fcard"><div class="h">Runtime</div><b style="font-size:20px">${(s.budget||{}).runtime_min||0} min</b></div></div>`+
   `<div class="bars">`+ks.map(r=>`<div class="bar"><span style="width:96px;color:${COL[r]||'#8b949e'}">${r}</span><i style="width:${Math.round(190*rs[r].calls/mx)}px;background:${COL[r]||'#8b949e'}"></i><span class="hint">${rs[r].calls} calls · ${rs[r].in_tok+rs[r].out_tok} tok · $${rs[r].cost}</span></div>`).join('')+`</div>`;}
 if(PANEL==='fleet'){const ag=s.agents||[];
  document.getElementById('panel-fleet').innerHTML=`<h3>Fleet — instances per role (active / configured)</h3><div class="fleetgrid">`+
   NODES.filter(n=>rs[n.id]).map(n=>{const st=rs[n.id];let dots='';const tot=Math.max(st.configured||1,st.alive,1);
    for(let i=0;i<tot;i++)dots+=`<span class="inst-dot" style="background:${i<st.alive?COL[n.id]:'#2a3340'}"></span>`;
    return `<div class="fcard"><div class="h" style="color:${COL[n.id]}">${n.t}</div>${dots}<div class="hint">${st.alive} active / ${st.configured||1} configured</div></div>`;}).join('')+`</div>`;}
 if(PANEL==='code'){const srcs=s.sources||{};const files=Object.keys(srcs).sort();
  if(!SELFILE||!srcs[SELFILE])SELFILE=files.find(f=>f.endsWith('db.py'))||files[0];
  document.getElementById('panel-code').innerHTML=`<h3>Evaluated source code (${files.length} files)</h3><div style="display:flex;gap:14px"><div style="min-width:170px">`+
   files.map(f=>`<div class="filerow ${f===SELFILE?'on':''}" onclick="selFile('${f}')">${esc(f)}</div>`).join('')+`</div><div style="flex:1;min-width:0">${highlightCode(srcs[SELFILE]||'',1)}</div></div>`;}
 if(PANEL==='find'){const F=s.findings||[];const byv={};F.forEach(f=>{(byv[f.verdict||'candidate']=byv[f.verdict||'candidate']||[]).push(f);});
  document.getElementById('panel-find').innerHTML=`<h3>Findings — only true-positives are published; the rest is filtered (click for details)</h3>`+
   ['true-positive','false-positive','not-applicable','needs-review'].map(v=>{const l=byv[v]||[];if(!l.length)return '';const vd=VERD[v];
    return `<div style="margin-bottom:8px"><span class="vd ${vd.c}">${vd.l} (${l.length})</span><div style="margin-top:5px">`+
     l.map(f=>`<div class="row mono frow sev-${f.severity||'low'}" onclick="openFinding('${f.fp}')">${esc(f.cwe||f.vuln_class)} · ${esc(f.symbol)} <span style="color:#8b949e">(${esc(f.file)})</span>${f.exploited?' <span class=badv>⚡</span>':''}</div>`).join('')+`</div></div>`;}).join('');}
 if(PANEL==='out'){const fu=s.funnel||{};const pr=s.priority||[];
  const proven=pr.filter(g=>g.exploited),conf=pr.filter(g=>!g.exploited);
  const stg=(n,l,c)=>`<div class="fstage"><div class="fn" style="color:${c}">${n==null?'—':n}</div><div class="fl">${l}</div></div>`;
  const arr=t=>`<div class="farrow">▶<div class="fd">${t}</div></div>`;
  const row=g=>`<div class="row mono frow sev-${g.severity}" onclick="openFinding('${g.fps[0]}')">${g.exploited?'<span class=badv>⚡</span> ':''}${esc(g.cwes.join('/'))} · <b>${esc(g.symbol)}</b> <span style="color:#8b949e">(${esc(g.file)})</span>${g.dup?` <span class="chip" style="background:${COL.detector};color:#0b0f14">×${g.fps.length} rules</span>`:''}</div>`;
  document.getElementById('panel-out').innerHTML=`<h3>Output — relevance funnel &amp; list prioritized by real exploitation</h3>`+
   `<div class="funnel">`+stg(fu.detected,'detected','#79c0ff')+arr(`−${fu.false_positive||0} FP · −${fu.not_applicable||0} NA · −${fu.needs_review||0} NR`)+
    stg(fu.true_positive,'confirmed','#bc8cff')+arr(`−${fu.duplicates||0} duplicates`)+
    stg(fu.distinct,'distinct','#34d399')+arr(`${(fu.distinct||0)-(fu.exploited||0)} not demonstrated`)+
    stg(fu.exploited,'exploited','#f85149')+`</div>`+
   `<div class="grid2" style="margin-top:12px"><div class="card"><h4>⚡ Tier 1 — proven live (priority)</h4>${proven.map(row).join('')||'<span class=hint>—</span>'}</div>`+
   `<div class="card"><h4>✓ Tier 2 — confirmed, not demonstrated live (presence = vuln)</h4>${conf.map(row).join('')||'<span class=hint>—</span>'}</div></div>`;}
 if(PANEL==='tasks'){const TL=s.tasks_list||[];const grp={claimed:[],open:[],blocked:[],closed:[]};
  TL.forEach(t=>{(grp[t.state]||grp.closed).push(t);});
  const sec=(title,arr,col,by)=>arr.length?`<div style="margin-bottom:8px"><div class="leg" style="color:${col};font-weight:700">${title} (${arr.length})</div>`+
    arr.map(t=>`<div class="row mono" style="display:flex;justify-content:space-between;gap:8px"><span><span style="color:${COL[t.role]||'#8b949e'}">${esc(t.role||'—')}</span> · ${esc(t.title)}</span>${by&&t.by?`<span style="color:var(--ok)">▶ ${esc(t.by)}</span>`:''}</div>`).join('')+`</div>`:'';
  document.getElementById('panel-tasks').innerHTML=`<h3>Task queue — running (by which agent) · upcoming · done · blocked</h3>`+
   (TL.length?(sec('⏳ Running',grp.claimed,'#d29922',true)+sec('📥 Upcoming',grp.open,'#58a6ff',false)+sec('⛔ Blocked',grp.blocked,'#f85149',false)+sec('✅ Done',grp.closed.slice(0,100),'#3fb950',false)):'<span class=hint>empty queue</span>');}
 if(PANEL==='exch'){const pr=s.protocol||{};const env=pr.envelope||{};const tax=pr.taxonomies||[];const exs=pr.exchanges||[];
  document.getElementById('panel-exch').innerHTML=`<h3>Normalized inter-agent exchanges — what data · what format · what normative reference</h3>`+
   `<div class="hint" style="margin-bottom:8px">Click a graph edge (or a card below) for the detailed contract. Dashed = Orchestrator supervision over all agents.</div>`+
   `<div class="card" style="margin-bottom:10px"><h4>Common envelope (carried by every message)</h4><table class="mono" style="font-size:11px">${(env.fields||[]).map(fl=>`<tr><td style="color:#79c0ff;padding-right:10px">${esc(fl[0])}</td><td style="color:#8b949e;padding-right:10px">${esc(fl[1])}</td><td style="color:#667">${esc(fl[2])}</td></tr>`).join('')}</table><div class="hint" style="margin-top:5px">Format: ${esc(env.format||'')} · Refs: ${(env.refs||[]).join(', ')}</div></div>`+
   `<div class="card" style="margin-bottom:10px"><h4>Taxonomies (closed vocabularies — out-of-list value rejected)</h4>${tax.map(t=>`<div class="row" style="font-size:11px"><b>${esc(t.name)}</b> : <span style="color:#c9d1d9">${esc(t.values)}</span> <span class="hint">— ${esc(t.ref)}</span></div>`).join('')}</div>`+
   `<div class="leg">Exchange contracts</div><div class="fleetgrid">`+
    exs.map(e=>`<div class="fcard frow" onclick="openExchange('${e.frm}','${e.to}')"><div class="h">${esc(e.frm)} → ${esc(e.to)}</div><div style="font-size:11px;color:#c9d1d9">${esc(e.label)}</div><div class="hint">payload <b>${esc(e.payload)}</b> · ${esc(e.format)}</div><div class="hint" style="color:#58a6ff">${(e.refs||[]).join(' · ')}</div></div>`).join('')+`</div>`;}
 if(PANEL==='fixes'){const F=(s.findings||[]).filter(f=>f.verdict==='true-positive'&&f.fix&&f.fix.safe_code);
  const seen={},rows=[];F.forEach(f=>{const k=f.file+'::'+f.symbol;if(seen[k])return;seen[k]=1;rows.push(f);});
  document.getElementById('panel-fixes').innerHTML=`<h3>Remediation — proposed safe-code fixes (Remediator role)</h3>`+
   rows.map(f=>`<div class="card" style="margin-bottom:8px"><div class="h" style="display:flex;gap:8px;align-items:center"><span class="vd" style="color:${f.exploited?'#f85149':'#3fb950'};border-color:${f.exploited?'#f85149':'#3fb950'}">${esc(f.cwe)}</span> <b>${esc(f.symbol)}</b> <span class="hint">${esc(f.file)}</span></div><div class="hint" style="margin:4px 0">${(f.fix.steps||[]).map(x=>'• '+esc(x)).join('<br>')}</div><pre class="data mono" style="border-color:#3fb950">${esc(f.fix.safe_code)}</pre></div>`).join('')||'<span class=hint>no fixes yet</span>';}
 if(PANEL==='stories'){const US=s.user_stories||[];
  document.getElementById('panel-stories').innerHTML=`<h3>User stories — operator intents that TRIGGER the Orchestrator</h3>`+
   `<div class="hint" style="margin-bottom:8px">Each story is the "why" behind an operator action; the <b>Trigger</b> is what starts/steers the pipeline via the Orchestrator (operator → orchestrator).</div>`+
   `<table class="mono" style="font-size:11px;width:100%"><tr style="color:#8b949e"><td>ID</td><td>Persona</td><td>Wants to…</td><td>Trigger →</td><td>Orchestrator does</td><td>Maps</td></tr>`+
   US.map(u=>`<tr><td style="color:#58a6ff;vertical-align:top">${esc(u.id)}</td><td style="vertical-align:top">${esc(u.persona)}</td><td style="color:#c9d1d9;vertical-align:top">${esc(u.want)}</td><td style="color:#3fb950;vertical-align:top">${esc(u.trigger)}</td><td style="color:#8b949e;vertical-align:top">${esc(u.to)}</td><td class="hint" style="vertical-align:top">${esc(u.maps)}</td></tr>`).join('')+`</table>`;}
 if(PANEL==='tools'){const T=s.tools||[];const FN=s.tool_functions||[];
  const ICOL={mcp:'#e879f9',sarif:'#34d399',cli:'#58a6ff',rest:'#f59e0b',lib:'#8b949e'};
  const ACOL={Indexer:'#39c5cf',Cartographe:'#34d399',Detector:'#f59e0b',Triager:'#bc8cff',Validator:'#f85149',Reporter:'#7ee787'};
  const byfn={};T.forEach(t=>{(byfn[t.function]=byfn[t.function]||[]).push(t);});
  const card=t=>`<div class="fcard"><div class="h" style="display:flex;align-items:center;gap:6px">`+
    `<a href="${t.homepage}" target="_blank" style="color:var(--ink);text-decoration:none">${esc(t.name)}</a>`+
    `<span class="vd" style="background:${ICOL[t.integration]||'#8b949e'};color:#0b0f14">${t.integration.toUpperCase()}</span>`+
    (t.mcp?`<span class="vd" style="border-color:#e879f9;color:#e879f9">MCP</span>`:'')+
    (t.available===true?'<span class="inst-dot" style="background:#3fb950" title="installed locally"></span>':t.available===false?'<span class="inst-dot" style="background:#2a3340" title="not installed"></span>':'')+
    `</div><div style="font-size:11px;color:#c9d1d9;margin:3px 0">${esc(t.task)}</div>`+
    `<div class="hint" style="font-family:ui-monospace,Menlo,monospace">$ ${esc(t.invoke)}</div>`+
    (t.mcp?`<div class="hint" style="margin-top:3px;color:#e879f9">via MCP: ${esc(t.mcp)}</div>`:'')+`</div>`;
  document.getElementById('panel-tools').innerHTML=`<h3>Tool library — by PIPELINE FUNCTION: where it plugs in, what it injects, how to integrate</h3>`+
   `<div class="hint" style="margin-bottom:8px">The LLM reasons; deterministic tools are oracles. Semgrep, sqlmap… are just <b>interchangeable examples</b> of each function. Badge = integration mode (CLI · SARIF · MCP · REST · LIB); green dot = binary detected locally.</div>`+
   FN.map(f=>{const tools=byfn[f.id]||[];if(!tools.length)return '';
    return `<div class="card" style="margin-bottom:10px"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><b style="font-size:13px">${esc(f.label)}</b><span class="vd" style="background:${ACOL[f.agent]||'#8b949e'};color:#0b0f14">→ ${esc(f.agent)}</span></div>`+
     `<div class="hint" style="margin:4px 0 8px"><b>Injects into the pipeline:</b> ${esc(f.feeds)}<br><b>Integration mode:</b> ${esc(f.how)}</div>`+
     `<div class="fleetgrid">${tools.map(card).join('')}</div></div>`;}).join('');}
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
 const cb=document.getElementById('cov');cb.textContent=s.coverage_complete?'coverage complete':'coverage in progress';cb.className='badge'+(s.coverage_complete?' on':'');
 document.getElementById('gap').textContent=(s.rule_gaps||0)+' rule-gap(s)';
 const tech={};F.forEach(f=>{const t=(f.technique||'').split(':')[0];tech[t]=(tech[t]||0)+1});
 const chips=['rule','secrets','deps','exploratory'].map(t=>`<span class="chip ${tech[t]?'hot':''}" style="${tech[t]?'background:'+COL.detector+';border-color:'+COL.detector:''}">${t} ${tech[t]||0}</span>`).join('');
 const corp=Object.entries(s.corpora||{}).map(([k,v])=>`${k}·${v}`).join('  ');
 const cur=id=>s.mode==='step'&&curRole===id;const alive=r=>(rstat[r]||{}).alive||0;
 setbd('operator',`goals set · <span class="big">1</span> evaluation`,true,cur('operator'));
 setbd('orchestrator',`<span class="dot"></span>${(s.agents||[]).filter(a=>a.status==='alive').length} agents · supervised`,true,cur('orchestrator'));
 setbd('indexer',`<span class="big">${(s.index||{}).functions||0}</span> functions · queryable`,((s.index||{}).functions||0)>0,cur('indexer'));
 setbd('cartographer',`<span class="big">${(s.flows||[]).length}</span> chains · data-flow map`,(s.flows||[]).length>0,cur('cartographer'));
 setbd('detector',`<span class="big">${cand}</span> candidates<div class="chips">${chips}</div>`,cand>0,cur('detector'));
 const vv=s.verdicts||{};
 setbd('triager',`<span class="big">${tp}</span> confirmed TP<div class="verdbar"><span class="vd fp">${vv['false-positive']||0} FP</span><span class="vd na">${vv['not-applicable']||0} NA</span><span class="vd nr">${vv['needs-review']||0} NR</span></div>`,tp>0,cur('triager'));
 setbd('validator',`testbed · <span class="big">${exploited}</span> ⚡ exploited`,exploited>0,cur('validator'));
 setbd('reporter',`<span class="big">${(s.funnel||{}).distinct||pub}</span> distinct<div class="verdbar"><span class="vd tp">${(s.funnel||{}).exploited||0} ⚡ proven</span><span class="vd">${pub} published</span></div>`,pub>0,cur('reporter'));
 setbd('coverage',`${covDone}/${cov.length} covered<div class="chips"><span class="chip">${corp}</span></div>`,s.coverage_complete,cur('coverage'));
 if(s.mode==='step'){document.getElementById('ctrl').style.display='inline-flex';
   document.getElementById('insp').style.display='block';document.getElementById('stage').classList.add('insp-on');
   const c=s.current;document.getElementById('stepn').textContent='step '+(c?c.n:0);
   document.getElementById('i-ttl').textContent=c?c.title:'— ready —';
   document.getElementById('i-sum').textContent=c?c.summary:'Click ⏭ to start.';
   document.getElementById('i-data').innerHTML=renderData(c);
   document.getElementById('i-log').innerHTML=(s.steplog||[]).slice().reverse().map(it=>`<div class="it ${c&&it.n===c.n?'cur':''}">${it.n}. [${it.role}] ${esc(it.title)}</div>`).join('');
   document.getElementById('b-step').disabled=!!s.done;}
 const fu=s.funnel||{};document.getElementById('outflow').textContent=`${fu.detected||cand} detected → ${fu.true_positive||tp} confirmed → ${fu.distinct||0} distinct → ${fu.exploited||0} exploited · filtered ${fu.false_positive||0} FP/${fu.not_applicable||0} NA/${fu.needs_review||0} NR`;
 if(OPEN&&!String(OPEN).startsWith('finding:')&&!String(OPEN).startsWith('exch:')&&!String(OPEN).startsWith('ext:'))renderModal();
 if(PANEL)renderPanels(s);
 renderQueue(s);
}
async function getState(){try{return await(await fetch('/api/state')).json()}catch(e){return null}}
let auto=null;
async function doStep(){const s=await(await fetch('/api/step',{method:'POST'})).json();render(s);if(s.done)stopAuto();}
async function doReset(){stopAuto();const s=await(await fetch('/api/reset',{method:'POST'})).json();render(s);}
function stopAuto(){if(auto){clearInterval(auto);auto=null;document.getElementById('b-play').textContent='▶';}}
function toggleAuto(){if(auto){stopAuto();}else{document.getElementById('b-play').textContent='⏸';auto=setInterval(doStep,1300);}}
// Fenêtres déplaçables (délégation sur les .winhead).
let _drag=null;
document.addEventListener('mousedown',e=>{const h=e.target.closest('.winhead');if(!h)return;const w=h.closest('.win');if(!w)return;const r=w.getBoundingClientRect();_drag={w,dx:e.clientX-r.left,dy:e.clientY-r.top};w.style.zIndex=70;e.preventDefault();});
document.addEventListener('mousemove',e=>{if(!_drag)return;_drag.w.style.left=Math.max(0,e.clientX-_drag.dx)+'px';_drag.w.style.top=Math.max(54,e.clientY-_drag.dy)+'px';_drag.w.style.right='auto';_drag.w.style.bottom='auto';});
document.addEventListener('mouseup',()=>{_drag=null;});
function toggleQueue(){const w=document.getElementById('qwidget');const sh=w.style.display==='none';w.style.display=sh?'block':'none';document.getElementById('p-tasks').classList.toggle('on',sh);}
function renderQueue(s){const TL=s.tasks_list||[];const c={claimed:0,open:0,blocked:0,closed:0};TL.forEach(t=>c[t.state]=(c[t.state]||0)+1);
 const IC={closed:'<span style="color:#3fb950">\u2713</span>',claimed:'<span style="color:#d29922">\u25B6</span>',open:'<span style="color:#58a6ff">\u25CB</span>',blocked:'<span style="color:#f85149">\u26D4</span>'};
 document.getElementById('qbody').innerHTML=
  `<div class="qstat">\u2713 ${c.closed} done \u00B7 \u25B6 ${c.claimed} running \u00B7 \u25CB ${c.open} to do${c.blocked?` \u00B7 \u26D4 ${c.blocked} blocked`:''}</div>`+
  `<div class="hint" style="margin-bottom:4px">Full execution sequence (${TL.length} tasks)</div>`+
  TL.map(t=>`<div class="qrow ${t.state==='claimed'?'qcur':''}">${IC[t.state]||''} <span style="color:${COL[t.role]||'#8b949e'}">${esc(t.role||'')}</span> ${esc(t.title)}${t.by?` <span style="color:#d29922">${esc(t.by)}</span>`:''}</div>`).join('');}
document.getElementById('b-step').onclick=doStep;document.getElementById('b-reset').onclick=doReset;document.getElementById('b-play').onclick=toggleAuto;
addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
(async()=>{const s=await getState();if(!s)return;render(s);
 if(s.mode!=='step'){setInterval(async()=>{const x=await getState();if(x)render(x);},1000);}})();
</script></body></html>
"""
