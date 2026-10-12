#!/usr/bin/env python3
"""Host-only exploration of event stream structure + reconstruction test."""
import json,sys,pathlib

BASE=pathlib.Path("/home/josiah/Projects/bonsai-garden/evals/results/2026-10-11-baseline-mem0")
TAP=(BASE/"tap.jsonl")
# (run_id, step) pairs to explore
targets=[("inventory-baseline-r0",1),("inventory-mem0-r0",0),("inventory-baseline-r1",1)]
print("TAP records for these:",[ (r.get("run"),r.get("step"),r.get("role"),r.get("n_messages"),
    (r.get("timings") or {}).get("prompt_n"),(r.get("timings") or {}).get("cache_n"))
   for r in (json.loads(l) for l in TAP.read_text().splitlines() if l.strip())
   if (r.get("run"),str(r.get("step"))) in {(t[0],str(t[1])) for t in targets}])

for rid,step in targets:
    p=(BASE/"runs"/rid/("step%d"%step)+".events.jsonl")
    evs=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    print("\n===== %s step%d (n_events=%d) ====="%(rid,step,len(evs)))
    # session header
    print("SESSION:",json.dumps(evs[0],ensure_ascii=False)[:300])
    # message start/end roles
    ms=[(e.get("type"),e.get("role"),e.get("id")) for e in evs if e.get("type") in("message_start","message_end")]
    print("msg_start/end (first 30):")
    for m in ms[:30]:
        print("  ",m)
    # turns
    turns=[]
    for e in evs:
        if e.get("type")=="turn_end":
            m=e.get("message") or {}
            content=m.get("content") or []
            tr=e.get("toolResults") or []
            turns.append({"content_types":[c.get("type") for c in content],
                          "n_toolcalls":len([c for c in content if c.get("type")=="toolCall"]),
                          "n_toolresults":len(tr),
                          "first_block": (content[0] if content else {})} )
    print("n_turns=%d; first 5 turns:"%len(turns))
    for i,t in enumerate(turns[:5]):
        print("  turn%d: %s tc=%d tr=%d"%(i,t["content_types"],t["n_toolcalls"],t["n_toolresults"]))
    # sample one toolResult
    for e in evs:
        if e.get("type")=="turn_end" and (e.get("toolResults") or []):
            tr=e["toolResults"][0]
            print("TOOLRESULT:",{k:(v if k!="content" else (v[0]["text"][:120] if isinstance(v,list) and v else str(v)[:120])) for k,v in tr.items()})
            break
