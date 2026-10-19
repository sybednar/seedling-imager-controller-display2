#!/bin/bash
# seedling-health-usb.sh  —  crash-diagnostic logger (Oct 2026)
#
# Writes a health line every 60 s, plus every kernel message as it happens,
# to a USB flash drive instead of the NVMe SSD. Purpose: System 1 has frozen
# twice with nothing in the system journal, and the evidence points at the
# NVMe/PCIe storage path. If the NVMe stops responding, anything that writes
# to it (journald, cron's health.log, the GUI) freezes too — but this logger
# keeps going on the USB stick, so we can see:
#   * whether the Pi itself was still alive after the freeze, and
#   * the actual kernel error (e.g. "nvme ... I/O timeout", "blocked for more
#     than 120 seconds"), which never reaches the NVMe journal.
#
# Each health line also includes an NVMe probe: one 4 KB direct read from the
# SSD, bypassing the page cache. "nvme=ok/3ms" is healthy; "nvme=STUCK/95s"
# means the SSD has stopped answering.
#
# Design note: inside the loop this uses bash built-ins and /run (RAM) only,
# and runs anything that could block on the NVMe in the background, so a
# storage hang cannot stop the logger itself.
#
# Installed by diagnostics/install_health_monitor.sh; runs as root under
# seedling-health-usb.service. Output: <usb>/seedling_health_<hostname>/

MNT=/mnt/healthusb
RUN=/run/seedling-health
NVME=${NVME:-/dev/nvme0n1}
mkdir -p "$RUN" "$MNT"

status() { printf '%(%FT%T)T %s\n' -1 "$*" > "$RUN/status"; }

# Built-in sleep: read with a timeout on a pipe that never delivers data.
exec 8<> <(:)
nap() { read -r -t "$1" -u 8 _ || true; }

find_usb_partition() {
    local disk part
    for disk in $(lsblk -dnrpo NAME,TRAN 2>/dev/null | awk '$2=="usb"{print $1}'); do
        part=$(lsblk -nrpo NAME,TYPE,FSTYPE "$disk" 2>/dev/null | awk '$2=="part" && $3!=""{print $1; exit}')
        [[ -z $part ]] && part=$(lsblk -nrpo NAME,FSTYPE "$disk" 2>/dev/null | awk 'NR==1 && $2!=""{print $1}')
        [[ -n $part ]] && { echo "$part"; return 0; }
    done
    return 1
}

# ---- wait for a USB stick and mount it --------------------------------------
# (HEALTH_DIR=<folder> skips USB detection — for testing only)
if [[ -n $HEALTH_DIR ]]; then PART="(test)"; TARGET=$HEALTH_DIR; fi
while [[ -z $TARGET ]]; do
    PART=$(find_usb_partition) && break
    status "waiting: no USB flash drive found"
    nap 30
done
[[ -z $TARGET ]] && TARGET=$(findmnt -nro TARGET -S "$PART" 2>/dev/null | head -1)
if [[ -z $TARGET ]]; then
    if ! mount "$PART" "$MNT" 2>"$RUN/mount_error"; then
        status "error: could not mount $PART (see $RUN/mount_error)"
        exit 1   # systemd retries in 30 s
    fi
    TARGET=$MNT
fi
DIR="$TARGET/seedling_health_$(hostname)"
mkdir -p "$DIR" || { status "error: $DIR not writable"; exit 1; }
LOG="$DIR/health.log"
KLOG="$DIR/kernel.log"
status "logging to $DIR (from $PART)"

{
    printf '\n=== %(%FT%T%z)T logger start, boot %s, uptime %ss ===\n' -1 \
        "$(cat /proc/sys/kernel/random/boot_id)" "$(cut -d' ' -f1 /proc/uptime)"
    echo "fields: time  nvme=probe/latency  thr=throttle-flags  v5=EXT5V-volts  temp  load1  availMB  app=GUI-pid"
} >> "$LOG"

# ---- kernel messages: stream /dev/kmsg straight to the USB stick ------------
printf '\n=== %(%FT%T%z)T logger start (full boot buffer follows, then live) ===\n' -1 >> "$KLOG"
dmesg --follow --time-format iso >> "$KLOG" 2>&1 &
KPID=$!

# ---- firmware readings (vcgencmd) in their own background loop --------------
vc_loop() {
    local t v
    while :; do
        t=$(vcgencmd get_throttled 2>/dev/null); v=$(vcgencmd pmic_read_adc EXT5V_V 2>/dev/null)
        printf '%s %s %s\n' "${t#*=}" "${v##*=}" "$EPOCHSECONDS" > "$RUN/vc"
        nap 20
    done
}
vc_loop &
VCPID=$!
trap 'kill $KPID $VCPID 2>/dev/null; sync -f "$DIR"; exit 0' TERM INT

# ---- NVMe probe: one uncached 4 KB read, in the background -----------------
PROBE_T0=0
start_probe() {
    PROBE_T0=$EPOCHSECONDS
    (
        t0=$EPOCHREALTIME
        if dd if="$NVME" of=/dev/null bs=4096 count=1 skip=$((RANDOM * 64)) iflag=direct status=none 2>/dev/null; then
            t1=$EPOCHREALTIME
            echo "$PROBE_T0 ok/$(( (${t1/./} - ${t0/./}) / 1000 ))ms" > "$RUN/nvme"
        else
            echo "$PROBE_T0 READ-ERROR" > "$RUN/nvme"
        fi
    ) &
}
start_probe

# ---- main loop ---------------------------------------------------------------
while :; do
    nap 5   # give the latest probe a moment to finish

    # The probe writes "<its start time> <result>"; if that start time isn't
    # the current probe's, the current probe hasn't finished yet.
    pt=""; res=""
    [[ -r $RUN/nvme ]] && read -r pt res < "$RUN/nvme"
    if [[ $pt == "$PROBE_T0" ]]; then
        nvme=$res
        start_probe
    else
        age=$(( EPOCHSECONDS - PROBE_T0 ))
        if (( age > 10 )); then nvme="STUCK/${age}s"; else nvme="pending"; fi
    fi

    thr="?"; v5="?"; vcts=0
    [[ -r $RUN/vc ]] && read -r thr v5 vcts < "$RUN/vc"
    (( EPOCHSECONDS - vcts > 90 )) && v5="${v5}(stale)"

    temp="?"; [[ -r /sys/class/thermal/thermal_zone0/temp ]] && read -r temp < /sys/class/thermal/thermal_zone0/temp
    [[ $temp =~ ^[0-9]+$ ]] && temp="$(( temp / 1000 )).$(( temp % 1000 / 100 ))C"
    read -r load _ < /proc/loadavg
    avail="?"
    while read -r k val _; do [[ $k == MemAvailable: ]] && { avail=$(( val / 1024 )); break; }; done < /proc/meminfo

    app=""
    for f in /proc/[0-9]*/cmdline; do
        mapfile -d '' -t args < "$f" 2>/dev/null || continue
        if [[ ${args[0]} == *python* && " ${args[*]} " == *main.py* ]]; then
            app=${f#/proc/}; app=${app%/cmdline}; break
        fi
    done

    printf '%(%FT%T%z)T nvme=%s thr=%s v5=%s temp=%s load=%s availMB=%s app=%s\n' -1 \
        "$nvme" "$thr" "$v5" "$temp" "$load" "$avail" "$app" >> "$LOG" \
        || { status "error: write to $LOG failed (USB stick removed?)"; exit 1; }
    sync -f "$DIR" &   # flush the USB filesystem only — never waits on the NVMe

    kill -0 "$KPID" 2>/dev/null || { dmesg --follow --time-format iso >> "$KLOG" 2>&1 & KPID=$!; }
    status "ok: last line $(printf '%(%T)T' -1), nvme=$nvme"
    nap "${INTERVAL:-55}"
done
