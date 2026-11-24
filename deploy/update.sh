#!/usr/bin/env bash
# Updates a Finanzprognose installation to the latest release, or to a given one.
#
#   sudo ./update.sh            # latest release
#   sudo ./update.sh v1.4.0     # a specific release (also used to roll back)
#   sudo ./update.sh --auto-rollback [vX.Y.Z]
#                               # on a failed health check, restore the database copy and the
#                               # previous version automatically (used by auto-update.sh, B-026)
#
# Exit codes: 0 updated or already up to date; 1 failed before or while switching;
# 2 the new version was unhealthy and was rolled back; 3 the rollback failed as well.
#
# Before switching, the database is copied to data/pre-update/<timestamp>_<old version>/.
# These copies are never deleted. The new docker-compose.yml, update.sh and install.sh are
# taken from the new image, so this script updates itself.
#
# Everything lives in main(), which bash parses completely before running it. That makes it
# safe to overwrite this file while it runs.
set -euo pipefail

IMAGE="ghcr.io/robert2611/finanzprognose"
CONTAINER="finanzprognose"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_RE='^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'

log() { printf '\n==> %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# Helpers below are duplicated in install.sh (which must work standalone). Keep them in sync.
image_version() {
    docker image inspect -f '{{ index .Config.Labels "finanzprognose.version" }}' "$1"
}

extract_deploy_files() {
    # Every step is checked explicitly: update.sh calls this inside `if`, where `set -e` is off.
    local image=$1 dest=$2 cid tmp
    cid=$(docker create "$image") || return 1
    tmp=$(mktemp -d) || return 1
    docker cp "$cid:/deploy/." "$tmp/" || { docker rm "$cid" >/dev/null; return 1; }
    docker rm "$cid" >/dev/null
    # install(1) replaces the file instead of writing into it, so a running script is unaffected.
    install -m 0644 "$tmp/docker-compose.yml" "$dest/docker-compose.yml" || return 1
    install -m 0755 "$tmp/update.sh" "$dest/update.sh" || return 1
    install -m 0755 "$tmp/install.sh" "$dest/install.sh" || return 1
    # Releases before B-026 have no automatic update; keep what is there in that case.
    if [[ -f $tmp/auto-update.sh ]]; then
        install -m 0755 "$tmp/auto-update.sh" "$dest/auto-update.sh" || return 1
        install_update_units "$tmp" "$dest"
    fi
    rm -rf "$tmp"
}

# Installs the systemd units of the automatic update (B-026) and starts the timer and path unit.
# SYSTEMD_UNIT_DIR only exists for the tests.
install_update_units() {
    local src=$1 dest=$2 unit dir=${SYSTEMD_UNIT_DIR:-/etc/systemd/system}
    command -v systemctl >/dev/null || return 0
    for unit in finanzprognose-update.service finanzprognose-update.timer finanzprognose-update.path; do
        [[ -f $src/$unit ]] || return 0
        sed "s|@INSTALL_DIR@|$dest|g" "$src/$unit" >"$dir/$unit.tmp" || return 0
        mv -f "$dir/$unit.tmp" "$dir/$unit"
    done
    mkdir -p "$dest/updater"
    systemctl daemon-reload
    systemctl enable --now finanzprognose-update.timer finanzprognose-update.path >/dev/null 2>&1 ||
        printf 'WARNING: could not enable the automatic update units\n' >&2
}

wait_healthy() {
    local status i
    for ((i = 0; i < 90; i++)); do
        status=$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo missing)
        case $status in
            healthy) return 0 ;;
            unhealthy) return 1 ;;
        esac
        sleep 2
    done
    return 1
}

env_get() {
    sed -n "s/^$1=//p" .env | tail -n 1
}

env_set() {
    if grep -q "^$1=" .env; then
        sed -i "s|^$1=.*|$1=$2|" .env
    else
        printf '%s=%s\n' "$1" "$2" >>.env
    fi
}

# Copies the database (with its WAL/SHM files) while the app is stopped.
backup_db() {
    local old=$1 dir
    docker compose stop
    if [[ ! -f data/finanzen.sqlite ]]; then
        log "No database yet, nothing to copy"
        return
    fi
    dir="data/pre-update/$(date +%Y-%m-%d_%H%M%S)_${old:-unknown}"
    mkdir -p "$dir"
    cp -p data/finanzen.sqlite* "$dir/"
    log "Database copied to $INSTALL_DIR/$dir"
    LAST_DB_COPY="$INSTALL_DIR/$dir"
}

# Switches the deploy files, .env and the container to the given (already pulled) version.
switch_to() {
    local version=$1
    extract_deploy_files "$IMAGE:$version" "$INSTALL_DIR" || return 1
    env_set APP_VERSION "$version" || return 1
    docker compose up -d --remove-orphans || return 1
}

# After a failed update: set the database of the failed version aside, restore the copy made
# before the update and start the previous version again. Deletes nothing.
rollback() {
    local previous=$1 failed_dir
    [[ $previous =~ $VERSION_RE ]] || return 1
    docker image inspect "$IMAGE:$previous" >/dev/null 2>&1 || docker pull "$IMAGE:$previous" || return 1
    docker compose stop || return 1
    if [[ -n $LAST_DB_COPY ]]; then
        failed_dir="data/failed-update_$(date +%Y-%m-%d_%H%M%S)"
        mkdir -p "$failed_dir" || return 1
        if compgen -G "data/finanzen.sqlite*" >/dev/null; then mv data/finanzen.sqlite* "$failed_dir/" || return 1; fi
        cp -p "$LAST_DB_COPY"/finanzen.sqlite* data/ || return 1
        log "Database of the failed version moved to $INSTALL_DIR/$failed_dir, copy from $LAST_DB_COPY restored"
    fi
    switch_to "$previous" && wait_healthy
}

main() {
    [[ $EUID -eq 0 ]] || die "Please run as root (sudo $0 $*)"
    cd "$INSTALL_DIR"
    [[ -f .env && -f docker-compose.yml ]] || die "$INSTALL_DIR has no .env or docker-compose.yml. Run install.sh first."

    local auto_rollback=no
    if [[ ${1-} == --auto-rollback ]]; then auto_rollback=yes; shift; fi
    local requested=${1:-latest} current target target_id running_id
    [[ $requested == latest || $requested =~ $VERSION_RE ]] || die "Invalid version '$requested' (expected e.g. v1.4.0)"
    current=$(env_get APP_VERSION)

    log "Pulling $IMAGE:$requested"
    docker pull "$IMAGE:$requested" ||
        die "Pull failed. If the GitHub token expired, log in again: docker login ghcr.io -u <github user>"
    target=$(image_version "$IMAGE:$requested")
    [[ $target =~ $VERSION_RE ]] || die "Image $IMAGE:$requested has no valid version label ('$target')"
    docker tag "$IMAGE:$requested" "$IMAGE:$target"

    target_id=$(docker image inspect -f '{{.Id}}' "$IMAGE:$target")
    running_id=$(docker inspect -f '{{.Image}}' "$CONTAINER" 2>/dev/null || true)
    if [[ $target == "$current" && $running_id == "$target_id" ]]; then
        log "Already up to date ($current)"
        exit 0
    fi

    log "Updating ${current:-?} -> $target"
    LAST_DB_COPY=""
    backup_db "$current"
    if switch_to "$target" && wait_healthy; then
        docker image prune -f >/dev/null
        log "Done. Running $target"
        exit 0
    fi

    docker compose logs --tail 50 || true
    if [[ $auto_rollback == yes ]]; then
        log "$target did not become healthy, rolling back to ${current:-?}"
        if rollback "$current"; then
            log "Rolled back. Running $current again"
            exit 2
        fi
        printf '\nERROR: the rollback to %s failed as well. Follow the steps below by hand.\n' "${current:-?}" >&2
    fi
    # Move the current files aside instead of overwriting: a leftover newer -wal file must
    # never be combined with the older database copy.
    local failed_dir
    failed_dir="data/failed-update_$(date +%Y-%m-%d_%H%M%S)"
    cat >&2 <<EOF

ERROR: $target did not become healthy (see the log above).
To go back to ${current:-the previous version}:

  cd $INSTALL_DIR
  docker compose stop
  mkdir -p $failed_dir && mv data/finanzen.sqlite* $failed_dir/
  cp -p ${LAST_DB_COPY:-data/pre-update/<copy>}/finanzen.sqlite* data/
  ./update.sh ${current:-<previous version>}
EOF
    [[ $auto_rollback == yes ]] && exit 3
    exit 1
}

main "$@"
# Never read past this point, even if this file was replaced while running.
# shellcheck disable=SC2317
exit
