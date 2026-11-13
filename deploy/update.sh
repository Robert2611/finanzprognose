#!/usr/bin/env bash
# Updates a Finanzprognose installation to the latest release, or to a given one.
#
#   sudo ./update.sh            # latest release
#   sudo ./update.sh v1.4.0     # a specific release (also used to roll back)
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
    local image=$1 dest=$2 cid tmp
    cid=$(docker create "$image")
    tmp=$(mktemp -d)
    docker cp "$cid:/deploy/." "$tmp/"
    docker rm "$cid" >/dev/null
    # install(1) replaces the file instead of writing into it, so a running script is unaffected.
    install -m 0644 "$tmp/docker-compose.yml" "$dest/docker-compose.yml"
    install -m 0755 "$tmp/update.sh" "$dest/update.sh"
    install -m 0755 "$tmp/install.sh" "$dest/install.sh"
    rm -rf "$tmp"
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

main() {
    [[ $EUID -eq 0 ]] || die "Please run as root (sudo $0 $*)"
    cd "$INSTALL_DIR"
    [[ -f .env && -f docker-compose.yml ]] || die "$INSTALL_DIR has no .env or docker-compose.yml. Run install.sh first."

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
    extract_deploy_files "$IMAGE:$target" "$INSTALL_DIR"
    env_set APP_VERSION "$target"
    docker compose up -d --remove-orphans

    log "Waiting for the app to become healthy"
    if wait_healthy; then
        docker image prune -f >/dev/null
        log "Done. Running $target"
        exit 0
    fi

    docker compose logs --tail 50 || true
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
    exit 1
}

main "$@"
# Never read past this point, even if this file was replaced while running.
# shellcheck disable=SC2317
exit
