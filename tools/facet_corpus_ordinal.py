"""Exploratory ordinal follow-up to the failed absolute-score corpus screen.

Compare graph relationships directly through the same facet definitions, without
asking for scalar magnitudes. Collect both A/B orientations. A second variant also
asks for short evidence quotations and a rationale, without seeing query values or
retrieval preferences. This uses already inspected cases: diagnosis, not fresh testing.
The original corpus screen remains authoritative and is not replaced by this probe.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from harness.chat import _CLAUDE_EXE

FACETS = ("topic", "temporal", "why", "activity", "concreteness")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    source = json.loads((args.corpus / "manifest.json").read_text())
    graph_system = next(j["system"] for j in source["jobs"] if j["id"] == "graph_0")
    definitions = graph_system.split("\ntopic —",1)[1].split("Treat cases independently.",1)[0]
    definitions = "topic —"+definitions.strip()
    system = """Each case contains two relationships: the same tag attached to text A and to text B.
For each facet, compare how relevant the tag is to its own text, seen through that facet.
Judge the tag-to-content relationship, not the tag's type or the facet's importance.
Read the full supplied contexts. Do not import missing facts. Compare the relationships
directly; do not estimate absolute numbers. Choose A, B, or equal when neither is clearly stronger.
"""+definitions
    jobs = []
    for variant in ("plain", "evidence"):
        wrapper = '\nReturn only JSON: {"cases":{"case_id":{"topic":"A|B|equal","temporal":"A|B|equal","why":"A|B|equal","activity":"A|B|equal","concreteness":"A|B|equal"},...}}.'
        if variant == "evidence":
            wrapper = '\nFor each facet give a short reason, quote the strongest supporting excerpt from each text (or use an empty string if none), then give the comparison. Quotes must be exact substrings of that text, at most 40 words each. Return only JSON: {"cases":{"case_id":{"topic":{"reason":"...","quote_A":"...","quote_B":"...","choice":"A|B|equal"},"temporal":{...},"why":{...},"activity":{...},"concreteness":{...}},...}}.'
        for reverse in (False,True):
            items, orientation = [], {}
            rng = random.Random(220923)
            for d in source["cases"]["domains"]:
                if len(d["texts"]) != 2:
                    raise ValueError("ordinal probe expects two corpus passages per subject")
                swap = rng.choice([False,True]) ^ reverse
                ai, bi = (1,0) if swap else (0,1)
                orientation[d["id"]] = [ai,bi]
                items.append((d["id"],f"Case {d['id']}\nTag: {d['tag']}\n\nText A:\n{d['texts'][ai]}\n\nText B:\n{d['texts'][bi]}"))
            random.Random(220923+int(reverse)).shuffle(items)
            jobs.append({"id":f"{variant}_{int(reverse)}", "variant":variant,
                "system":system+wrapper+" Include every case and facet. No tools or extra commentary.",
                "user":"\n\n".join(v for _,v in items), "orientation_not_sent":orientation})
    manifest = {"protocol":__doc__, "model":source["model"], "source_manifest_sha256":hashlib.sha256((args.corpus/'manifest.json').read_bytes()).hexdigest(),
        "jobs":jobs, "analysis_prespecified":"Canonical sign(A-B) per facet from each reading; average signs across the two orientations within variant, retain disagreement as uncertainty. Compare equal query-times-sign sum, nonnegative fitted coefficients with original nested subject folds, and query-priority first decisive facet. Report each variant, original scalar results and all missing readings. No deployment or population claim."}
    args.out.mkdir(parents=True,exist_ok=True)
    path = args.out/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("ordinal manifest changed")
    path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("Saved four exact ordinal call inputs",flush=True)

    def run(job):
        path = args.out/(job['id']+'.json')
        if path.exists():
            return json.loads(path.read_text())
        raw_path = args.out/(job['id']+'.raw.json')
        start = time.perf_counter()
        if raw_path.exists():
            envelope = json.loads(raw_path.read_text())
        else:
            with tempfile.TemporaryDirectory(prefix="facet-ordinal-") as cwd:
                r = subprocess.run([_CLAUDE_EXE,'-p','--model',source['model'],'--effort','high',
                    '--output-format','json','--tools','','--setting-sources','','--no-session-persistence',
                    '--system-prompt',job['system']],input=job['user'],cwd=cwd,capture_output=True,
                    text=True,encoding='utf-8',timeout=240)
            if r.returncode:
                raise RuntimeError(f"ordinal {job['id']} failed: {r.stderr[:300]}")
            envelope = json.loads(r.stdout)
            raw_path.write_text(json.dumps(envelope,indent=2)+'\n',encoding='utf-8')
        if envelope.get('is_error'):
            raise RuntimeError(str(envelope.get('result')))
        raw = envelope['result'].strip()
        if raw.startswith('```'):
            raw = raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        answers = json.loads(raw)['cases']
        if set(answers)-set(job['orientation_not_sent']):
            raise ValueError('unexpected ordinal case IDs')
        quote_checks = []
        for cid,values in answers.items():
            if set(values) != set(FACETS):
                raise ValueError('missing ordinal facet')
            domain = next(d for d in source['cases']['domains'] if d['id']==cid)
            for f,v in values.items():
                choice = v if job['variant']=='plain' else v['choice']
                if choice not in ('A','B','equal'):
                    raise ValueError('invalid ordinal choice')
                if job['variant']=='evidence':
                    for side,idx in zip(('A','B'),job['orientation_not_sent'][cid]):
                        quote = v['quote_'+side]
                        quote_checks.append({'case':cid,'facet':f,'side':side,
                            'exact_substring':quote in domain['texts'][idx], 'words':len(quote.split()),
                            'nonempty':bool(quote)})
        result = {'id':job['id'],'answer':answers,'missing_cases':sorted(set(job['orientation_not_sent'])-set(answers)),
            'quote_checks':quote_checks,'usage':envelope.get('usage'),'model_usage':envelope.get('modelUsage'),
            'cost_usd_reported':envelope.get('total_cost_usd'),'seconds':time.perf_counter()-start,
            'created_utc':datetime.now(timezone.utc).isoformat()}
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result

    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in as_completed([pool.submit(run,j) for j in jobs]):
                r=f.result()
                print(r['id'],len(r['answer']),r['missing_cases'],flush=True)


if __name__=='__main__':
    main()
