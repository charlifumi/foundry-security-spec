"""Standalone, timestamped HTML evaluation report.

Builds one self-contained, printable HTML file from the run snapshot: executive summary,
prioritized findings (with evidence, exploit, fix), filtered candidates, security map,
extension contributions, coverage and budget. Saved to runs/<id>/report-<ts>.html.
"""
from __future__ import annotations

import html
import os
import time


def _esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def generate_report(ctx) -> str:
    # Local import to avoid any import cycle at module load.
    from .dashboard.server import build_snapshot
    s = build_snapshot(ctx)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = ctx.config.get("target", {}).get("source", "?")
    fu = s.get("funnel", {})
    findings = s.get("findings", [])
    tps = [f for f in findings if f["verdict"] == "true-positive"]
    pr = s.get("priority", [])
    ex = s.get("extensions", {}) or {}

    def sev_badge(sev):
        c = {"critical": "#b00", "high": "#c60", "medium": "#06c", "low": "#666"}.get(sev, "#666")
        return f'<span style="background:{c};color:#fff;padding:1px 7px;border-radius:10px;font-size:11px">{_esc(sev)}</span>'

    rows = []
    for f in tps:
        ev = f.get("evidence", {}) or {}
        exj = f.get("exploit", {}) or {}
        fix = f.get("fix", {}) or {}
        rows.append(f"""
        <div class="finding">
          <h3>{_esc(f['cwe'])} — {_esc(f['symbol'])} {sev_badge(f['severity'])}
              {'<span class="ex">⚡ exploited (proven live)</span>' if f['exploited'] else '<span class="cf">confirmed (not demonstrated live)</span>'}</h3>
          <div class="meta">{_esc(f['file'])} · {_esc(f.get('owasp') or '')} · technique: {_esc(f['technique'])}</div>
          <p>{_esc(f.get('title'))}</p>
          <div class="leg"><b>Evidence (gate):</b> reachability — {_esc((ev.get('reachability') or {}).get('note',''))};
             boundary — {_esc((ev.get('trust_boundary') or {}).get('note',''))};
             impact — {_esc((ev.get('impact') or {}).get('note',''))}</div>
          {('<div class="leg"><b>Exploit:</b> <code>'+_esc(exj.get('request',''))+'</code> → '+_esc(exj.get('impact',''))+'</div>') if f['exploited'] and exj else ''}
          <details><summary>Offending code</summary><pre>{_esc(f.get('source',''))}</pre></details>
          {('<details open><summary>🛠 Fix proposal (safe code)</summary><pre class="fix">'+_esc(fix.get('safe_code',''))+'</pre></details>') if fix.get('safe_code') else ''}
        </div>""")

    filtered = [f for f in findings if f["verdict"] in ("false-positive", "not-applicable", "needs-review")]
    filt_rows = "".join(
        f"<tr><td>{_esc(f['verdict'])}</td><td>{_esc(f['cwe'])}</td><td>{_esc(f['symbol'])}</td>"
        f"<td>{_esc((f.get('evidence',{}).get('reason') or {}).get('note',''))}</td></tr>"
        for f in filtered)

    flows = s.get("flows", [])
    flow_rows = "".join(
        f"<tr><td>{'✅' if fl['validated'] else '⚠️'}</td><td>{_esc(fl['entry'])}</td>"
        f"<td>{_esc(fl['file'])}</td><td>{_esc(' → '.join(str(x) for x in fl['chain']))}</td></tr>"
        for fl in flows)

    patches = ex.get("patches", [])
    pat_rows = "".join(
        f"<tr><td>{'✓' if p['verified'] else '⚠'}</td><td>{_esc(p['cwe'])}</td><td>{_esc(p['symbol'])}</td></tr>"
        for p in patches)
    attack_rows = "".join(
        f"<tr><td>{_esc(p['entry'])}</td><td>{_esc(p['capability'])}</td><td>{_esc(p['goal'])}</td></tr>"
        for p in (ex.get("attack", {}) or {}).get("paths", []))

    cov = s.get("coverage", [])
    cov_done = sum(1 for c in cov if c["state"] == "covered")
    b = s.get("budget", {})

    htmlc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Forge report {stamp}</title>
<style>
body{{font:14px/1.55 system-ui,Segoe UI,Roboto,Arial;color:#1a1a1a;max-width:980px;margin:24px auto;padding:0 18px}}
h1{{margin:0}} .sub{{color:#666;margin:2px 0 18px}}
.kpis{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}}
.kpi{{border:1px solid #ddd;border-radius:10px;padding:10px 14px;text-align:center;min-width:90px}}
.kpi b{{font-size:24px;display:block}}
h2{{border-bottom:2px solid #eee;padding-bottom:4px;margin-top:28px}}
.finding{{border:1px solid #e3e3e3;border-left:4px solid #c60;border-radius:8px;padding:10px 14px;margin:12px 0}}
.finding h3{{margin:0 0 4px}} .meta{{color:#777;font-size:12px}} .leg{{font-size:12.5px;margin:6px 0}}
.ex{{background:#b00;color:#fff;padding:1px 7px;border-radius:10px;font-size:11px}}
.cf{{background:#eee;color:#444;padding:1px 7px;border-radius:10px;font-size:11px}}
pre{{background:#0d1117;color:#e6edf3;padding:10px;border-radius:8px;overflow:auto;font-size:12px}}
pre.fix{{background:#06281a;color:#d6ffe6}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}} td,th{{border:1px solid #e3e3e3;padding:5px 8px;text-align:left}}
code{{background:#f3f3f3;padding:1px 5px;border-radius:4px}}
.foot{{color:#999;font-size:12px;margin-top:30px;border-top:1px solid #eee;padding-top:10px}}
</style></head><body>
<h1>Forge — Security Evaluation Report</h1>
<div class="sub">Generated {ts} · target <code>{_esc(target)}</code> · run <code>{_esc(s.get('run_dir'))}</code></div>
<div class="kpis">
  <div class="kpi"><b>{fu.get('detected',0)}</b>candidates</div>
  <div class="kpi"><b>{fu.get('true_positive',0)}</b>confirmed</div>
  <div class="kpi"><b>{fu.get('distinct',0)}</b>distinct</div>
  <div class="kpi"><b style="color:#b00">{fu.get('exploited',0)}</b>exploited</div>
  <div class="kpi"><b>{fu.get('false_positive',0)}/{fu.get('not_applicable',0)}/{fu.get('needs_review',0)}</b>FP/NA/NR</div>
</div>
<h2>Prioritized findings</h2>
{''.join(rows) or '<p>None.</p>'}
<h2>Filtered candidates (why they did not surface)</h2>
<table><tr><th>Verdict</th><th>Class</th><th>Symbol</th><th>Reason</th></tr>{filt_rows or '<tr><td colspan=4>None</td></tr>'}</table>
<h2>Security map (attack surface · data flow)</h2>
<table><tr><th></th><th>Entry</th><th>Component</th><th>Call chain → sink</th></tr>{flow_rows or '<tr><td colspan=4>—</td></tr>'}</table>
<h2>Extension roles (§6)</h2>
<p>Variant-Hunter: {sum(len(v['variants']) for v in ex.get('variants',[]))} same-pattern locations.
   Remediator: {sum(1 for p in patches if p['verified'])}/{len(patches)} patches verified.</p>
<h3>Attack-Mapper — privilege paths</h3>
<table><tr><th>Entry</th><th>Capability</th><th>Goal</th></tr>{attack_rows or '<tr><td colspan=3>—</td></tr>'}</table>
<h3>Remediator — patch verification</h3>
<table><tr><th></th><th>Class</th><th>Symbol</th></tr>{pat_rows or '<tr><td colspan=3>—</td></tr>'}</table>
<h2>Coverage &amp; cost</h2>
<p>Coverage: {cov_done}/{len(cov)} components · spend ${b.get('spend_usd',0)} · runtime {b.get('runtime_min',0)} min · trailing yield {b.get('trailing_yield',0)}</p>
<div class="foot">Forge — demonstrator of the Foundry Security Spec (Cisco). Findings gated on verifiable evidence (Constitution I); <code>exploited</code> = demonstrated live (Constitution VII).</div>
</body></html>"""

    out = os.path.join(ctx.run_dir, f"report-{stamp}.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(htmlc)
    ctx.events.emit("report_generated", path=out)
    return out
