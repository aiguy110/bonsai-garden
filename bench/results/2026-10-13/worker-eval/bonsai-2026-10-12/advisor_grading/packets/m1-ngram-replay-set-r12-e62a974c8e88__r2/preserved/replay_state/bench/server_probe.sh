#!/usr/bin/env bash
# Shared-weights multi-slot probe: ONE llama-server (one copy of weights) with
# N slots over a unified KV pool, at the production ctx/KV settings. Records
# VRAM after concurrent warmup and per-slot/aggregate decode speed.
# Run under a turnstile lease (see engine_probe.sh). Args: OUTDIR NP CTX [extra server args...]
set -euo pipefail
OUT=$1; NP=$2; CTX=$3; shift 3; mkdir -p "$OUT"
B=$HOME/Projects/llama.cpp-bonsai2/build/bin
M=$HOME/models
PORT=8089; TAG="np${NP}_c${CTX}${*:+_$(echo "$*" | tr -c 'a-z0-9' '_' | cut -c1-40)}"
LLAMA_ATTN_ROT_DISABLE=1 $B/llama-server --model $M/Ternary-Bonsai-2-27B-PQ2_0.gguf \
  --port $PORT -ngl 99 -c $CTX -np $NP --kv-unified --threads 8 -fa on \
  -ctk q4_0 -ctv q4_0 --kv-mean-center $M/Ternary-Bonsai-2-27B-PQ2_0-kv-bias.gguf \
  --jinja "$@" > "$OUT/server_$TAG.log" 2>&1 &
PID=$!; trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null' EXIT
for i in $(seq 120); do curl -sf localhost:$PORT/health >/dev/null && break; sleep 1; done
req() { curl -s localhost:$PORT/completion -d "{\"prompt\":\"$1\",\"n_predict\":$2,\"temperature\":0,\"top_k\":1,\"seed\":0,\"cache_prompt\":false}"; }
P1="Write a Python function that parses an ISO-8601 duration string into seconds, with tests."
P2="Explain, step by step, how a B-tree handles insertion when a node overflows."
# single stream
req "$P1" 256 | python3 -c "import json,sys;t=json.load(sys.stdin)['timings'];print('single',round(t['predicted_per_second'],1),t.get('draft_n'),t.get('draft_n_accepted'))" | tee -a "$OUT/server_$TAG.txt"
# NP concurrent streams
for i in $(seq $NP); do P=$P1; [ $((i%2)) = 0 ] && P=$P2; req "$P" 256 > "$OUT/conc_$TAG.$i.json" & done; wait $(jobs -p | grep -v "^$PID$") 2>/dev/null || true
sleep 1
for f in "$OUT"/conc_$TAG.*.json; do python3 -c "import json,sys;t=json.load(open('$f'))['timings'];print('conc',round(t['predicted_per_second'],1))"; done | tee -a "$OUT/server_$TAG.txt"
nvidia-smi --query-gpu=memory.used --format=csv,noheader | sed 's/^/vram /' | tee -a "$OUT/server_$TAG.txt"
