#!/usr/bin/env bash
# Checks for a new release and installs it with update.sh (B-026). Started by systemd:
#   finanzprognose-update.timer  every 15 minutes
#   finanzprognose-update.path   as soon as the app writes updater/request.json ("Jetzt aktualisieren")
#
# The app and this script only talk through files in $INSTALL_DIR/updater/ (mounted into the
# container at /updater):
#   status.json       written here, read by the app (versions, mode, last update and its result)
#   request.json      written by the app; this script consumes (removes) it and updates right away
#   last-update.log   output of the last update.sh run, shown in the app
#   state             this script's own memory between runs (key=value, never read by the app)
#
# AUTO_UPDATE in .env: "auto" (default) installs every new release, "notify" only reports it
# and waits for a request from the app. A release whose update failed is not retried
# automatically; a request from the app retries it.
#
# Exit codes: 0 also when there was nothing to do; 1 when an update failed.
set -euo pipefail

IMAGE="ghcr.io/robert2611/finanzprognose"
INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
UPDATER_DIR="$INSTALL_DIR/updater"
VERSION_RE='^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'
SAFE_RE='^[0-9A-Za-z._+:-]+$'

declare -A ST=()

env_get() {
    sed -n "s/^$1=//p" "$INSTALL_DIR/.env" | tail -n 1 | tr -d "'\""
}

now() { date -Iseconds; }

load_state() {
    local k v
    [[ -f $UPDATER_DIR/state ]] || return 0
    while IFS='=' read -r k v; do
        [[ $k =~ ^[A-Z_]+$ ]] && ST[$k]=$v
    done <"$UPDATER_DIR/state"
}

save_state() {
    local k tmp="$UPDATER_DIR/.state.tmp"
    : >"$tmp"
    for k in "${!ST[@]}"; do printf '%s=%s\n' "$k" "${ST[$k]}" >>"$tmp"; done
    mv -f "$tmp" "$UPDATER_DIR/state"
}

# A JSON string, or null for an empty or unexpected value (only safe characters are ever written).
jstr() {
    if [[ -n ${1-} && $1 =~ $SAFE_RE ]]; then printf '"%s"' "$1"; else printf 'null'; fi
}

write_status() {
    local state=$1 target=${2-} last tmp="$UPDATER_DIR/.status.tmp"
    last=null
    if [[ -n ${ST[LAST_AT]-} ]]; then
        last=$(printf '{"from": %s, "to": %s, "result": %s, "at": %s}' \
            "$(jstr "${ST[LAST_FROM]-}")" "$(jstr "${ST[LAST_TO]-}")" \
            "$(jstr "${ST[LAST_RESULT]-}")" "$(jstr "${ST[LAST_AT]-}")")
    fi
    cat >"$tmp" <<JSON
{
  "schema": 1,
  "mode": $(jstr "$MODE"),
  "state": "$state",
  "current": $(jstr "$(env_get APP_VERSION)"),
  "latest": $(jstr "${ST[LATEST]-}"),
  "checked_at": $(jstr "${ST[CHECKED_AT]-}"),
  "check_error": $(jstr "${ST[CHECK_ERROR]-}"),
  "target": $(jstr "$target"),
  "failed_version": $(jstr "${ST[FAILED_VERSION]-}"),
  "last_update": $last
}
JSON
    chmod 0644 "$tmp"
    mv -f "$tmp" "$UPDATER_DIR/status.json"
}

# Sets ST[LATEST] from the :latest tag on ghcr.io (pulling it, which also pre-loads the image).
check_latest() {
    local v
    ST[CHECKED_AT]=$(now)
    if ! docker pull -q "$IMAGE:latest" >/dev/null 2>&1; then
        ST[CHECK_ERROR]=pull_failed
        return
    fi
    v=$(docker image inspect -f '{{ index .Config.Labels "finanzprognose.version" }}' "$IMAGE:latest" 2>/dev/null || true)
    if [[ $v =~ $VERSION_RE ]]; then
        ST[LATEST]=$v
        ST[CHECK_ERROR]=""
    else
        ST[CHECK_ERROR]=bad_version_label
    fi
}

# Takes a pending request from the app. Prints the requested version ("" = latest), returns 1 if none.
take_request() {
    local f="$UPDATER_DIR/request.json" v
    [[ -f $f ]] || return 1
    v=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$f" | sed 's/.*"\([^"]*\)"$/\1/' || true)
    rm -f "$f"
    [[ $v =~ $VERSION_RE ]] || v=""
    printf '%s' "$v"
}

run_update() {
    local target=$1 from rc=0 flag=()
    from=$(env_get APP_VERSION)
    write_status updating "$target"
    # An older update.sh (after a rollback to a release from before B-026) has no --auto-rollback.
    grep -q -- '--auto-rollback' "$INSTALL_DIR/update.sh" && flag=(--auto-rollback)
    "$INSTALL_DIR/update.sh" "${flag[@]}" "$target" >"$UPDATER_DIR/last-update.log" 2>&1 || rc=$?
    ST[LAST_FROM]=$from
    ST[LAST_TO]=$target
    ST[LAST_AT]=$(now)
    case $rc in
        0) ST[LAST_RESULT]=success; ST[FAILED_VERSION]="" ;;
        2) ST[LAST_RESULT]=rolled_back; ST[FAILED_VERSION]=$target ;;
        3) ST[LAST_RESULT]=rollback_failed; ST[FAILED_VERSION]=$target ;;
        *) ST[LAST_RESULT]=failed; ST[FAILED_VERSION]=$target ;;
    esac
    return "$rc"
}

main() {
    [[ -f $INSTALL_DIR/.env ]] || { echo "No $INSTALL_DIR/.env, run install.sh first" >&2; exit 1; }
    mkdir -p "$UPDATER_DIR"
    exec 9>"$UPDATER_DIR/.lock"
    # Another run is busy; the path unit starts us again afterwards if a request is still there.
    flock -n 9 || exit 0

    MODE=$(env_get AUTO_UPDATE)
    [[ $MODE == auto || $MODE == notify ]] || MODE=auto
    load_state

    local requested=no req_version="" target="" current rc=0
    if req_version=$(take_request); then requested=yes; fi
    check_latest
    current=$(env_get APP_VERSION)

    if [[ $requested == yes ]]; then
        target=${req_version:-${ST[LATEST]-}}
    # Not after a failed check: the update would fail to pull too and mark the release as failed.
    elif [[ $MODE == auto && -z ${ST[CHECK_ERROR]-} && -n ${ST[LATEST]-} && ${ST[LATEST]} != "$current" &&
        ${ST[LATEST]} != "${ST[FAILED_VERSION]-}" ]]; then
        target=${ST[LATEST]}
    fi

    if [[ -n $target ]]; then
        run_update "$target" || rc=$?
    fi
    save_state
    write_status idle
    [[ $rc -eq 0 ]] || exit 1
}

main "$@"
exit
