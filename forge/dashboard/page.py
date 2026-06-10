"""La page du dashboard (HTML/CSS/JS autonome, sans dépendance ni CDN)."""

PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forge — évaluation de sécurité</title>
<style>
:root{color-scheme:light;--bg:#0f1419;--panel:#161b22;--ink:#e6edf3;--mut:#8b949e;
--line:#30363d;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff;--vio:#bc8cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,Helvetica,Arial}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
h1{font-size:18px;margin:0;letter-spacing:.5px}h1 b{color:var(--acc)}
.badge{padding:2px 9px;border:1px solid var(--line);border-radius:20px;font-size:12px;color:var(--mut)}
.badge.on{color:var(--ok);border-color:var(--ok)}
.wrap{padding:16px 20px;display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1280px;margin:0 auto}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.panel h2{font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:var(--mut);margin:0 0 10px}
.full{grid-column:1/3}
.stats{display:flex;gap:10px;flex-wrap:wrap}
.stat{flex:1;min-width:90px;text-align:center;background:#0d1117;border:1px solid var(--line);border-radius:8px;padding:10px}
.stat .n{font-size:24px;font-weight:700}.stat .l{font-size:11px;color:var(--mut)}
.agents{display:flex;flex-wrap:wrap;gap:8px}
.agent{background:#0d1117;border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-width:150px}
.agent .role{font-weight:700;font-size:12px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
.dot.alive{background:var(--ok)}.dot.retired{background:var(--mut)}.dot.dead{background:var(--bad)}
.agent .claim{color:var(--mut);font-size:11px;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.role-detector{color:#79c0ff}.role-triager{color:#d2a8ff}.role-validator{color:#ff7b72}.role-reporter{color:#7ee787}
.cols{display:flex;gap:10px}.col{flex:1;background:#0d1117;border:1px solid var(--line);border-radius:8px;padding:8px;min-height:60px}
.col h3{margin:0 0 6px;font-size:11px;color:var(--mut);text-transform:uppercase}.col .c{font-size:20px;font-weight:700}
.chip{display:block;background:#161b22;border:1px solid var(--line);border-radius:6px;padding:3px 6px;margin:4px 0;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sev-critical{border-left:3px solid var(--bad)}.sev-high{border-left:3px solid var(--warn)}
.sev-medium{border-left:3px solid var(--acc)}.sev-low{border-left:3px solid var(--mut)}
.exp{color:var(--bad);font-weight:700}
.flow{font-family:ui-monospace,Menlo,monospace;font-size:11px;padding:5px 8px;border-radius:6px;background:#0d1117;border:1px solid var(--line);margin:5px 0}
.flow .v{color:var(--ok)}.flow .u{color:var(--bad)}
.bar{height:10px;background:#0d1117;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.bar>i{display:block;height:100%;background:var(--ok);width:0}
.kv{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:3px 0;font-size:12px}
.log{font-family:ui-monospace,Menlo,monospace;font-size:11px;max-height:200px;overflow:auto}
.log div{padding:1px 0;color:var(--mut)}.log b{color:var(--acc)}
.sink{color:var(--bad)}
</style></head><body>
<header>
  <h1><b>FORGE</b> — évaluation de sécurité agentique</h1>
  <span class="badge" id="run">run —</span>
  <span class="badge" id="cov">couverture —</span>
  <span class="badge" id="gap">rule-gaps —</span>
  <span class="badge" id="tb">testbed</span>
</header>
<div class="wrap">
  <div class="panel full"><h2>Vue d'ensemble</h2><div class="stats" id="stats"></div></div>

  <div class="panel"><h2>Fleet d'agents (vivants · claim courant)</h2><div class="agents" id="agents"></div></div>

  <div class="panel"><h2>Pipeline des findings</h2><div class="cols" id="pipe"></div></div>

  <div class="panel full"><h2>Cartographie — chaînes d'appel (entrée → sink) &amp; validation</h2><div id="flows"></div></div>

  <div class="panel"><h2>Couverture</h2><div class="bar"><i id="covbar"></i></div><div id="covtxt" style="color:var(--mut);font-size:12px;margin-top:6px"></div></div>

  <div class="panel"><h2>Budget &amp; coût</h2><div id="budget"></div></div>

  <div class="panel full"><h2>Journal d'événements</h2><div class="log" id="log"></div></div>
</div>
<script>
const KIND={spawn:'agent prêt',candidate:'candidat détecté',verdict:'verdict posé',exploited:'EXPLOITÉ',
published:'publié',rule_gap:'RULE-GAP',coverage_complete:'couverture complète',carto_ready:'carte prête',
index_ready:'index prêt',halt:'arrêt',done:'terminé',testbed_up:'testbed up',reclaim:'claim récupéré'};
function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;}
async function tick(){
 let s;try{s=await (await fetch('/api/state')).json()}catch(e){return}
 document.getElementById('run').textContent='run '+s.run_dir;
 const cov=document.getElementById('cov');cov.textContent=s.coverage_complete?'couverture complète':'couverture en cours';cov.className='badge'+(s.coverage_complete?' on':'');
 document.getElementById('gap').textContent=s.rule_gaps+' rule-gap(s)';
 document.getElementById('tb').textContent='corpus: '+Object.entries(s.corpora).map(([k,v])=>k+'·'+v).join('  ');
 // stats
 const tp=s.findings.filter(f=>f.verdict==='true-positive').length;
 const exp=s.findings.filter(f=>f.exploited).length;
 const cand=s.findings.length;
 const stats=[['fonctions',s.index.functions||0],['candidats',cand],['confirmés (TP)',tp],['exploités',exp],['rule-gaps',s.rule_gaps]];
 document.getElementById('stats').innerHTML=stats.map(([l,n])=>`<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('');
 // agents
 document.getElementById('agents').innerHTML=s.agents.map(a=>`<div class="agent"><div class="role role-${a.role}"><span class="dot ${a.status}"></span>${a.id}</div><div class="claim">${a.claim?('▶ '+a.claim):'— idle —'}</div><div class="claim">♥ ${a.hb_age}s</div></div>`).join('')||'<span style="color:var(--mut)">en attente…</span>';
 // pipeline
 const bystate={Détectés:s.findings.length,Confirmés:tp,Exploités:exp,Publiés:s.findings.filter(f=>f.state==='published').length};
 let pipe='';for(const [k,n] of Object.entries(bystate)){
   let chips='';if(k==='Confirmés'||k==='Exploités'){const list=s.findings.filter(f=>k==='Exploités'?f.exploited:f.verdict==='true-positive').slice(0,8);
     chips=list.map(f=>`<span class="chip sev-${f.severity||'low'}">${f.cwe} ${f.symbol}${f.exploited?' <span class=exp>⚡</span>':''}</span>`).join('');}
   pipe+=`<div class="col"><h3>${k}</h3><div class="c">${n}</div>${chips}</div>`;}
 document.getElementById('pipe').innerHTML=pipe;
 // flows (cartographie)
 document.getElementById('flows').innerHTML=s.flows.map(f=>{
   const chain=f.chain.map(x=>x.startsWith('→sink:')?`<span class="sink">${x}</span>`:x).join(' → ');
   return `<div class="flow">${f.validated?'<span class=v>✅ validé</span>':'<span class=u>⚠️ NON validé</span>'} &nbsp; <b>${f.entry}</b> <span style="color:var(--mut)">(${f.file})</span> : ${chain}</div>`;
 }).join('')||'<span style="color:var(--mut)">cartographie en cours…</span>';
 // couverture
 const cv=s.coverage,done=cv.filter(c=>c.state==='covered').length;
 document.getElementById('covbar').style.width=(cv.length?100*done/cv.length:0)+'%';
 document.getElementById('covtxt').textContent=`${done}/${cv.length} composants couverts`;
 // budget
 const b=s.budget;
 document.getElementById('budget').innerHTML=
   `<div class="kv"><span>Dépense</span><b>$${b.spend_usd}${b.spend_cap_usd?(' / '+b.spend_cap_usd):''}</b></div>`+
   `<div class="kv"><span>Runtime</span><b>${b.runtime_min} min</b></div>`+
   `<div class="kv"><span>Yield glissant</span><b>${b.trailing_yield} (seuil ${b.yield_threshold})</b></div>`+
   `<div class="kv"><span>Part estimée</span><b>${Math.round(b.estimated_fraction*100)}%</b></div>`+
   `<div class="kv"><span>Coût par rôle</span><b>${Object.entries(b.spend_by_role).map(([k,v])=>k+':$'+v).join('  ')||'—'}</b></div>`;
 // log
 document.getElementById('log').innerHTML=s.events.slice().reverse().map(e=>`<div><b>${(KIND[e.kind]||e.kind)}</b> ${e.agent||''} ${e.finding?('· '+e.finding.slice(0,10)):''}</div>`).join('');
}
setInterval(tick,1000);tick();
</script></body></html>
"""
