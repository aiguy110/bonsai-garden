#!/usr/bin/env bash
# Read-only host evidence collection for the worker-eval reboot correlation.
# It deliberately does not contact the inference service or acquire a GPU lease.
set -u -o pipefail

# The four interrupted smoke runs began between these bounds on 2026-10-12.
SINCE=${SINCE:-"2026-10-12 14:10:00"}
UNTIL=${UNTIL:-"2026-10-12 16:40:00"}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${OUT:-"bench/results/$(date +%F)/worker_eval/reboot-diagnostic-${STAMP}"}
mkdir -p "$OUT"

printf 'reboot diagnostic collected_at_utc=%s\nwindow_since=%s\nwindow_until=%s\n' \
  "$STAMP" "$SINCE" "$UNTIL" > "$OUT/README.txt"
printf '%q ' "$0" "$@"; printf '\n' >> "$OUT/README.txt"

# Capture both output and failures: diagnostic collection must continue when a
# host restricts journal, dmesg, IPMI, or NVIDIA access.
run() {
  local name=$1
  shift
  {
    printf '+ '
    printf '%q ' "$@"
    printf '\n\n'
    "$@"
    printf '\n[exit %s]\n' "$?"
  } >"$OUT/$name.txt" 2>&1 || true
}

run host-id hostnamectl
run uptime uptime
run boot-time who -b
run last-reboots last -x -F -n 80 reboot shutdown runlevel
run journal-boots journalctl --list-boots --no-pager
run journal-window journalctl --no-pager --since "$SINCE" --until "$UNTIL" -o short-iso-precise
run kernel-window journalctl --no-pager -k --since "$SINCE" --until "$UNTIL" -o short-iso-precise

# Search all retained journal entries in the relevant time window. These terms
# cover Linux reboot/shutdown paths, OOM, NVIDIA Xid, thermal/power events, and
# soft/hard-lockup/watchdog reports without assuming a particular distro unit.
run suspect-events journalctl --no-pager --since "$SINCE" --until "$UNTIL" \
  -g 'Xid|NVRM|nvidia|Out of memory|oom-kill|Killed process|thermal|overheat|Temperature|power|Power|watchdog|soft lockup|hard LOCKUP|hung task|panic|reboot|shutdown|reset|I/O error|GPU has fallen off the bus' \
  -o short-iso-precise

# The reboots can split evidence across boots. Preserve a bounded kernel tail
# from each recently retained boot, plus its suspect lines, rather than assuming
# that the immediately preceding boot is the relevant one.
for i in 0 1 2 3 4 5 6 7 8; do
  run "kernel-boot-minus-${i}" journalctl --no-pager -k -b "-$i" -n 2000 -o short-iso-precise
  run "suspects-boot-minus-${i}" journalctl --no-pager -b "-$i" \
    -g 'Xid|NVRM|nvidia|Out of memory|oom-kill|Killed process|thermal|overheat|Temperature|power|Power|watchdog|soft lockup|hard LOCKUP|hung task|panic|reboot|shutdown|reset|I/O error|GPU has fallen off the bus' \
    -o short-iso-precise
done

run dmesg-tail dmesg -T
run nvidia-summary nvidia-smi
run nvidia-details nvidia-smi -q -d TEMPERATURE,POWER,PERFORMANCE,ERROR
run thermal-zones sh -c 'for z in /sys/class/thermal/thermal_zone*; do [ -e "$z" ] || continue; echo "== $z"; cat "$z/type" "$z/temp" 2>&1; done'
run ipmi-sel ipmitool sel elist
run pstore-list sh -c 'find /sys/fs/pstore -maxdepth 1 -type f -printf "%f\n" 2>&1'
run pstore-read sh -c 'for f in /sys/fs/pstore/*; do [ -f "$f" ] || continue; echo "== $f"; cat "$f"; done'

# Make the evidence self-describing even if a command above was unavailable.
{
  echo 'Files:'
  find "$OUT" -maxdepth 1 -type f -printf '%f\n' | sort
  echo
  echo 'Nonzero/unavailable captures:'
  grep -l '\[exit [^0]' "$OUT"/*.txt 2>/dev/null || true
} > "$OUT/index.txt"
printf 'wrote %s\n' "$OUT"
