"""Exécution pas-à-pas du pipeline (mode pédagogique).

Rejoue le pipeline réel — mêmes agents, même substrate, même exploitation live —
mais une action à la fois, en exposant à chaque pas la **donnée générée** et son
**transit** entre agents. Idéal pour montrer comment Forge fonctionne.

Aucune concurrence ici : le stepper appelle directement la logique des agents dans
un ordre déterministe. Les invariants du substrate restent ceux de spec.md.
"""
from __future__ import annotations

import json
import os

from .agents import (cartographer, coverage_guide, detector, indexer, reporter,
                     triager, validator)
from .dashboard.server import build_snapshot
from .orchestrator import setup


class StepRunner:
    def __init__(self, cfg):
        self.cfg = cfg
        self._build()

    def _build(self):
        self.ctx, self.run_id = setup(self.cfg)
        # testbed pour l'exploitation live pendant le stepping
        if self.ctx.config["testbed"]["enabled"]:
            from targets.vulnshop.app import serve_in_thread
            srv, base = serve_in_thread(host=self.ctx.config["testbed"]["host"],
                                        port=self.ctx.config["testbed"]["port"])
            self.ctx.testbed_url = base
            self.ctx.events.emit("testbed_up", url=base)
        self.log: list[dict] = []
        self.current: dict | None = None
        self.active_role = "operator"
        self.done = False
        self._gen = self._steps()

    # ----- API contrôleur -------------------------------------------------------
    def step(self) -> dict | None:
        if self.done:
            return None
        try:
            next(self._gen)
        except StopIteration:
            self.done = True
        return self.current

    def reset(self):
        self._build()

    def snapshot(self) -> dict:
        snap = build_snapshot(self.ctx)
        # agents synthétisés (pas de threads en mode pas-à-pas) pour animer le graphe
        roles = ["orchestrator", "indexer", "cartographer", "detector", "triager",
                 "validator", "reporter", "coverage"]
        snap["agents"] = [
            {"id": r + "-0", "role": r, "status": "alive",
             "claim": (self.current["title"] if self.current and self.current["role"] == r else None),
             "hb_age": 0.0}
            for r in roles
        ]
        snap["mode"] = "step"
        snap["done"] = self.done
        snap["active_role"] = self.active_role
        snap["current"] = self.current
        snap["steplog"] = [{"n": s["n"], "stage": s["stage"], "role": s["role"],
                            "title": s["title"], "summary": s["summary"]} for s in self.log]
        return snap

    # ----- enregistrement d'un pas ----------------------------------------------
    def _mk(self, stage, role, title, summary, data, edge):
        self.active_role = role
        self.current = {"n": len(self.log) + 1, "stage": stage, "role": role, "title": title,
                        "summary": summary, "data": data, "edge": edge}
        self.log.append(self.current)

    # ----- la séquence ----------------------------------------------------------
    def _steps(self):
        ctx = self.ctx
        self._mk("testbed", "orchestrator", "Testbed démarré",
                 f"VulnShop écoute sur {ctx.testbed_url}", {"testbed_url": ctx.testbed_url},
                 ["operator", "orchestrator"])
        yield

        indexer.run_indexer(ctx)
        funcs = [{"file": f.file, "name": f.name, "params": f.params} for f in ctx.index.all_functions()]
        self._mk("index", "indexer", "Index construit (gate FR-003)",
                 f"{ctx.index.function_count()} fonctions dans {len(ctx.index.functions)} fichiers",
                 {"functions": funcs}, ["orchestrator", "indexer"])
        yield

        cartographer.run_cartographer(ctx)
        flows = ctx.security_map.get("flows", [])
        self._mk("cartography", "cartographer", "Carte de flux (chaînes d'appel)",
                 f"{len(flows)} chaînes entrée→sink ; "
                 f"{ctx.security_map.get('unguarded_boundaries', 0)} frontières non gardées",
                 {"flows": [{"entry": f["entry"], "file": f["file"],
                             "chain": [str(x) for x in f["chain"]], "validated": f["validated"]}
                            for f in flows]},
                 ["indexer", "cartographer"])
        yield

        coverage_guide.init_coverage(ctx)
        cov = ctx.db.connect().execute("SELECT component, goal FROM coverage").fetchall()
        self._mk("coverage-init", "coverage", "Checklist de couverture dérivée",
                 f"{len(cov)} items (composant × goal)",
                 {"items": [dict(r) for r in cov]}, ["cartographer", "coverage"])
        yield

        # --- Détection : un pas par tâche, données = candidats produits ---
        files = sorted({f.file for f in ctx.index.all_functions()})
        specs = [{"kind": "rules", "file": rel} for rel in files]
        specs += [{"kind": "secrets"}, {"kind": "deps"}, {"kind": "explore"}]
        triage_specs, seen = [], set()
        for spec in specs:
            follow = detector.handle({"payload": spec}, ctx, "detector-0")
            cands = []
            for t in follow:
                fp = t["payload"]["fp"]
                if fp not in seen:
                    seen.add(fp)
                    triage_specs.append(t)
                f = ctx.findings.get(fp)
                cands.append({"fp": fp, "file": f["file"], "symbol": f["symbol"],
                              "vuln_class": f["vuln_class"], "technique": f["technique"],
                              "title": f["title"]})
            label = spec.get("file") or spec["kind"]
            self._mk("detect", "detector", f"Detector · {spec['kind']} · {label}",
                     f"{len(cands)} candidat(s) écrit(s) au finding store",
                     {"candidates": cands}, ["cartographer", "detector"])
            yield

        # --- Triage : un pas par candidat, données = evidence gate + verdict ---
        validate_specs, report_specs = [], []
        for ts in triage_specs:
            fp = ts["payload"]["fp"]
            follow = triager.handle({"payload": ts["payload"]}, ctx, "triager-0")
            f = ctx.findings.get(fp)
            import json as _j
            self._mk("triage", "triager", f"Triager · {f['cwe']} {f['symbol']}",
                     f"verdict = {f['verdict']}" + ("" if f["verdict"] == "true-positive"
                                                    else " (démoté par le gate)"),
                     {"finding": {"fp": fp, "file": f["file"], "symbol": f["symbol"],
                                  "cwe": f["cwe"], "severity": f["severity"],
                                  "verdict": f["verdict"]},
                      "evidence": _j.loads(f["evidence"])},
                     ["detector", "triager"])
            for nf in follow:
                if nf["role"] == "validator":
                    validate_specs.append(nf)
                elif nf["role"] == "reporter":
                    report_specs.append(nf)
            yield

        # --- Validation : un pas par exploit, données = requête + impact observé ---
        for vs in validate_specs:
            fp = vs["payload"]["fp"]
            validator.handle({"payload": vs["payload"]}, ctx, "validator-0")
            f = ctx.findings.get(fp)
            poc, trace = "", {}
            if f["poc_path"]:
                try:
                    poc = open(f["poc_path"], encoding="utf-8").read()
                    tj = f["poc_path"][:-3] + ".json"
                    if os.path.exists(tj):
                        trace = json.load(open(tj, encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            self._mk("validate", "validator",
                     f"Validator · {f['cwe']} {f['symbol']}",
                     ("⚡ EXPLOITÉ sur le testbed" if f["exploited"] else "non reproduit"),
                     {"exploited": bool(f["exploited"]), "poc": poc, "trace": trace},
                     ["triager", "validator"])
            yield

        # --- Reporting + rollup ---
        for rs in report_specs:
            reporter.handle({"payload": rs["payload"]}, ctx, "reporter-0")
        coverage_guide.review(ctx)
        reporter.write_rollup(ctx)
        tps = ctx.findings.confirmed_true_positives()
        self._mk("report", "reporter", "Rapports publiés + rollup",
                 f"{len(tps)} rapports, {sum(1 for f in tps if f['exploited'])} exploités",
                 {"published": [{"cwe": f["cwe"], "symbol": f["symbol"], "severity": f["severity"],
                                 "exploited": bool(f["exploited"])} for f in tps]},
                 ["validator", "reporter"])
        yield


class StepController:
    mode = "step"

    def __init__(self, cfg):
        self.runner = StepRunner(cfg)

    def snapshot(self):
        return self.runner.snapshot()

    def step(self):
        self.runner.step()
        return self.runner.snapshot()

    def reset(self):
        self.runner.reset()
        return self.runner.snapshot()
