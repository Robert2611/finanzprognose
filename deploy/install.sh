#!/usr/bin/env bash
# Sets up Finanzprognose on a Debian 12/13 VM, or reconfigures an existing installation.
#
#   sudo bash install.sh            # installs the latest release
#   sudo bash install.sh v1.4.0     # installs a specific release
#
# What it does:
#   1. installs Docker Engine + compose plugin (official Docker apt repo), the NAS client
#      tools and unattended-upgrades, and enables Docker log rotation
#   2. logs in to ghcr.io (the image is private; a classic token with read:packages is enough)
#   3. mounts the NAS share for the backups (SMB or NFS, via /etc/fstab) and creates .nas-marker
#   4. writes /opt/finanzprognose/.env (an existing .env is kept unless you choose otherwise)
#   5. pulls the image, copies docker-compose.yml/update.sh/install.sh/auto-update.sh out of it,
#      installs the systemd timer of the automatic update (B-026) and starts the app
#
# Safe to run again. This file is published as a release asset and must work standalone.
set -euo pipefail

IMAGE="ghcr.io/robert2611/finanzprognose"
CONTAINER="finanzprognose"
INSTALL_DIR="${INSTALL_DIR:-/opt/finanzprognose}"
NAS_MOUNT="/mnt/nas-finanzen"
SMB_CREDENTIALS="/root/.smb-finanzprognose"
VERSION_RE='^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'

log() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# ask VAR "Question" [default] -- reads from the terminal, so `curl ... | bash` works too.
ask() {
    local __var=$1 prompt=$2 default=${3-} reply
    [[ -n $default ]] && prompt+=" [$default]"
    read -r -p "$prompt: " reply </dev/tty
    printf -v "$__var" '%s' "${reply:-$default}"
}

ask_secret() {
    local __var=$1 prompt=$2 reply
    read -r -s -p "$prompt: " reply </dev/tty
    printf '\n' >&2
    printf -v "$__var" '%s' "$reply"
}

ask_yes() {
    local reply
    read -r -p "$1 [${2:-y}/n]: " reply </dev/tty
    reply=${reply:-${2:-y}}
    [[ $reply =~ ^[YyJj] ]]
}

# ------------------------------------------------------------------ helpers shared with update.sh
# Duplicated in update.sh. Keep them in sync.
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

# ------------------------------------------------------------------ 1. system
check_system() {
    [[ $EUID -eq 0 ]] || die "Please run as root: sudo bash $0"
    # shellcheck disable=SC1091
    . /etc/os-release
    [[ ${ID:-} == debian ]] || die "This script supports Debian only (found: ${ID:-unknown})"
    case ${VERSION_ID:-} in
        12 | 13) ;;
        *) warn "Tested on Debian 12 and 13, found ${VERSION_ID:-unknown}. Continuing anyway." ;;
    esac
}

install_packages() {
    log "Installing system packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ca-certificates curl openssl cifs-utils nfs-common unattended-upgrades

    # Automatic Debian security updates (the default unattended-upgrades policy).
    echo 'unattended-upgrades unattended-upgrades/enable_auto_updates boolean true' | debconf-set-selections
    dpkg-reconfigure -f noninteractive unattended-upgrades

    if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
        log "Docker is already installed"
    else
        log "Installing Docker from the official Docker repository"
        # shellcheck disable=SC1091
        . /etc/os-release
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
        chmod a+r /etc/apt/keyrings/docker.asc
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $VERSION_CODENAME stable" \
            >/etc/apt/sources.list.d/docker.list
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi

    if [[ ! -f /etc/docker/daemon.json ]]; then
        log "Enabling Docker log rotation"
        mkdir -p /etc/docker
        cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
        systemctl restart docker
    fi
    systemctl enable --now docker
}

# ------------------------------------------------------------------ 2. registry login
ghcr_logged_in() {
    grep -qs '"ghcr.io"' "${DOCKER_CONFIG:-$HOME/.docker}/config.json"
}

ghcr_login() {
    if ghcr_logged_in && ! ask_yes "Already logged in to ghcr.io. Log in again (e.g. new token)?" n; then
        return
    fi
    log "Login to ghcr.io"
    echo "You need a GitHub token (classic) with only the scope 'read:packages'."
    local user token
    ask user "GitHub user name"
    ask_secret token "GitHub token"
    printf '%s' "$token" | docker login ghcr.io -u "$user" --password-stdin
}

# ------------------------------------------------------------------ 3. NAS
# Replaces any existing fstab line for $NAS_MOUNT, so re-running with new settings works.
write_fstab_line() {
    local line=$1
    cp -p /etc/fstab "/etc/fstab.bak-finanzprognose-$(date +%Y%m%d%H%M%S)"
    awk -v mp="$NAS_MOUNT" '$2 != mp' /etc/fstab >/etc/fstab.new
    printf '%s\n' "$line" >>/etc/fstab.new
    mv /etc/fstab.new /etc/fstab
    systemctl daemon-reload
}

mount_nas() {
    mkdir -p "$NAS_MOUNT"
    if mountpoint -q "$NAS_MOUNT"; then umount "$NAS_MOUNT" || true; fi
    mount "$NAS_MOUNT" || die "Could not mount the NAS share. Check server, share name and credentials, then run install.sh again."
    local fstype
    fstype=$(findmnt -n -o FSTYPE --target "$NAS_MOUNT")
    [[ $fstype == cifs || $fstype == smb3 || $fstype == nfs* ]] ||
        die "$NAS_MOUNT is not a network share after mounting (type: $fstype)"
}

setup_smb() {
    local server share user pass
    ask server "NAS host name or IP"
    ask share "Share name, optionally with subfolder (e.g. finanzbackup or homes/finanzprognose)"
    # A leading/trailing slash makes the UNC path malformed ("//host//share").
    share=${share#"${share%%[!/]*}"}
    share=${share%"${share##*[!/]}"}
    [[ -n $share ]] || die "Share name must not be empty"
    share=${share// /\\040} # spaces must be escaped in fstab
    ask user "NAS user (needs write access to the share)"
    ask_secret pass "NAS password"
    umask 077
    printf 'username=%s\npassword=%s\n' "$user" "$pass" >"$SMB_CREDENTIALS"
    umask 022
    chmod 600 "$SMB_CREDENTIALS"
    write_fstab_line "//$server/$share $NAS_MOUNT cifs credentials=$SMB_CREDENTIALS,uid=0,gid=0,file_mode=0660,dir_mode=0770,iocharset=utf8,_netdev,nofail,x-systemd.automount 0 0"
    mount_nas
}

setup_nfs() {
    local server export_path
    echo "The NFS export must allow this VM's IP and map all users to a NAS user with write access"
    echo "(Synology: 'Map all users to admin', otherwise all_squash with anonuid/anongid)."
    ask server "NAS host name or IP"
    ask export_path "Export path (e.g. /volume1/finanzbackup)"
    write_fstab_line "$server:$export_path $NAS_MOUNT nfs defaults,_netdev,nofail,x-systemd.automount 0 0"
    mount_nas
}

# Sets BACKUP_HOST_DIR.
setup_nas() {
    log "Backup target (NAS)"
    local kind
    ask kind "How is the NAS reached? smb / nfs / manual (already mounted by you)" smb
    case $kind in
        smb) setup_smb ;;
        nfs) setup_nfs ;;
        manual)
            ask BACKUP_HOST_DIR "Path of the backup folder (must contain .nas-marker)"
            [[ -d $BACKUP_HOST_DIR ]] || die "$BACKUP_HOST_DIR does not exist"
            [[ -f $BACKUP_HOST_DIR/.nas-marker ]] || die "$BACKUP_HOST_DIR/.nas-marker is missing. Create it on the mounted share first."
            return
            ;;
        *) die "Unknown choice '$kind'" ;;
    esac

    BACKUP_HOST_DIR="$NAS_MOUNT/finanzprognose"
    mkdir -p "$BACKUP_HOST_DIR"
    local probe="$BACKUP_HOST_DIR/.install-write-test"
    { : >"$probe" && rm -f "$probe"; } ||
        die "No write access to $BACKUP_HOST_DIR. Check the share permissions (NFS: squash settings)."
    if [[ ! -f $BACKUP_HOST_DIR/.nas-marker ]]; then
        : >"$BACKUP_HOST_DIR/.nas-marker"
        log "Created $BACKUP_HOST_DIR/.nas-marker"
    fi
}

# ------------------------------------------------------------------ 4. configuration
write_env() {
    log "App settings"
    local port user pass backup_time
    ask port "Port for the web interface" 8080
    ask user "Login user name" admin
    while true; do
        ask_secret pass "Login password (empty = generate one)"
        if [[ -z $pass ]]; then
            pass=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)
            GENERATED_PASSWORD=$pass
            break
        fi
        [[ $pass == *"'"* ]] && { echo "Please do not use single quotes (')."; continue; }
        local again
        ask_secret again "Repeat password"
        [[ $pass == "$again" ]] && break
        echo "Passwords do not match."
    done
    ask backup_time "Time of the daily backup (HH:MM)" 03:00
    local auto_update
    while true; do
        ask auto_update "New releases: install automatically (auto) or only show them in the app (notify)" auto
        [[ $auto_update == auto || $auto_update == notify ]] && break
        echo "Please answer auto or notify."
    done

    umask 077
    cat >"$INSTALL_DIR/.env" <<EOF
# Written by install.sh. Run install.sh again to change it, or edit it and run: docker compose up -d
APP_VERSION=$APP_VERSION
PORT=$port
APP_USER=$user
APP_PASSWORD='$pass'
BACKUP_TIME=$backup_time
BACKUP_HOST_DIR=$BACKUP_HOST_DIR
# auto: install new releases automatically (checked every 15 minutes); notify: only show them in the app
AUTO_UPDATE=$auto_update
EOF
    umask 022
    chmod 600 "$INSTALL_DIR/.env"
}

env_get() {
    sed -n "s/^$1=//p" "$INSTALL_DIR/.env" | tail -n 1
}

env_set() {
    if grep -q "^$1=" "$INSTALL_DIR/.env"; then
        sed -i "s|^$1=.*|$1=$2|" "$INSTALL_DIR/.env"
    else
        printf '%s=%s\n' "$1" "$2" >>"$INSTALL_DIR/.env"
    fi
}

# ------------------------------------------------------------------ 5. image + start
pull_image() {
    local requested=$1
    log "Pulling $IMAGE:$requested"
    docker pull "$IMAGE:$requested" || die "Pull failed. Check the GitHub token (scope read:packages) and the version."
    APP_VERSION=$(image_version "$IMAGE:$requested")
    [[ $APP_VERSION =~ $VERSION_RE ]] || die "Image $IMAGE:$requested has no valid version label ('$APP_VERSION')"
    docker tag "$IMAGE:$requested" "$IMAGE:$APP_VERSION"
}

main() {
    local requested=${1:-latest}
    [[ $requested == latest || $requested =~ $VERSION_RE ]] || die "Invalid version '$requested' (expected e.g. v1.4.0)"
    GENERATED_PASSWORD=""

    check_system
    install_packages
    ghcr_login
    pull_image "$requested"

    mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/updater"
    local installed=""
    [[ -f $INSTALL_DIR/.env ]] && installed=$(env_get APP_VERSION)
    # Changing the version of an existing installation is update.sh's job: it copies the
    # database before a newer release migrates it.
    if [[ -n $installed && $installed != "$APP_VERSION" ]] &&
        ! ask_yes "Installed version is $installed. Switch to $APP_VERSION without a database copy? (Better: answer n and use update.sh)" n; then
        APP_VERSION=$installed
        docker pull "$IMAGE:$APP_VERSION"
    fi

    if [[ -f $INSTALL_DIR/.env ]] && ask_yes "$INSTALL_DIR/.env exists. Keep the current settings (NAS, password, port)?" y; then
        BACKUP_HOST_DIR=$(env_get BACKUP_HOST_DIR)
        [[ -f $BACKUP_HOST_DIR/.nas-marker ]] ||
            warn "$BACKUP_HOST_DIR/.nas-marker is missing. Backups will fail until the NAS is mounted."
        env_set APP_VERSION "$APP_VERSION"
    else
        setup_nas
        write_env
    fi

    extract_deploy_files "$IMAGE:$APP_VERSION" "$INSTALL_DIR"

    log "Starting Finanzprognose $APP_VERSION"
    cd "$INSTALL_DIR"
    docker compose up -d --remove-orphans
    wait_healthy || {
        docker compose logs --tail 50 || true
        die "The app did not become healthy (see the log above)."
    }

    local ip port
    ip=$(hostname -I | awk '{print $1}')
    port=$(env_get PORT)
    log "Finanzprognose $APP_VERSION is running"
    cat <<EOF

  URL:       http://$ip:${port:-8080}
  User:      $(env_get APP_USER)
EOF
    [[ -n $GENERATED_PASSWORD ]] && printf '  Password:  %s   (generated, write it down)\n' "$GENERATED_PASSWORD"
    cat <<EOF

  Next steps:
    - open the URL and run "Sicherung -> Jetzt sichern" once, then check the NAS for the file
    - updates: checked every 15 minutes, installed automatically unless AUTO_UPDATE=notify in .env;
      the "Version" page of the app shows the state. By hand: sudo $INSTALL_DIR/update.sh
EOF
}

main "$@"
exit
