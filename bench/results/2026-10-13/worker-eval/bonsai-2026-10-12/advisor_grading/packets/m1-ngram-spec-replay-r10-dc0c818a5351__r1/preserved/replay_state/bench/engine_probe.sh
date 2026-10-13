#!/usr/bin/env bash
# Engine probe for Ternary-Bonsai-2-27B PQ2_0 on the 3080. Run under a turnstile
# lease: ~/Projects/local-llm-bench/turnstile_run.py -- ./engine_probe.sh OUTDIR
# Measures (1) aggregate throughput of N concurrent sequences sharing one copy
# of the weights, (2) decode cost of KV quant choices, (3) depth sensitivity.
set -euo pipefail
OUT=${1:-./results}; mkdir -p "$OUT"
B=$HOME/Projects/llama.cpp-bonsai2/build/bin
M=$HOME/models/Ternary-Bonsai-2-27B-PQ2_0.gguf
export LLAMA_ATTN_ROT_DISABLE=1

# 1) Batched decode: npl parallel sequences, shared weights, one context.
$B/llama-batched-bench -m "$M" -ngl 99 -fa on -c 16384 -b 2048 -ub 512 \
  -ctk q4_0 -ctv q4_0 -npp 512 -ntg 128 -npl 1,2,3,4,6,8 --output-format jsonl \
  > "$OUT/batched_q4.jsonl" 2> "$OUT/batched_q4.log"

# 2) KV-type and depth sensitivity for single-stream decode/prefill.
for kv in q4_0 q8_0; do
  $B/llama-bench -m "$M" -ngl 99 -fa 1 -ctk $kv -ctv $kv \
    -p 512 -n 128 -d 0,32768 -r 2 -o jsonl \
    > "$OUT/kv_${kv}_depth.jsonl" 2> "$OUT/kv_${kv}_depth.log" || true
done
