#!/usr/bin/env python3
"""A stand-in for the `docker` CLI, just enough for deploy/update.sh and deploy/auto-update.sh.

State lives in the JSON file named by FAKE_DOCKER_STATE:
  registry   {tag: version label} that `pull` can fetch
  local      {tag: version label} of pulled/tagged images
  unhealthy  versions whose container reports "unhealthy"
  pull_fail  every pull fails
  running    version of the running container, or null
  calls      every invocation (argv), appended
`compose up` starts the version in ./.env and appends "opened by <version>" to
./data/finanzen.sqlite, standing in for a migration. `cp <cid>:/deploy/. <dir>` copies
FAKE_DEPLOY_SRC (the repo's deploy/ folder).
"""
import json
import os
import shutil
import sys

state_file = os.environ["FAKE_DOCKER_STATE"]
with open(state_file) as f:
    st = json.load(f)
args = sys.argv[1:]
st["calls"].append(args)


def save(rc=0, out=""):
    with open(state_file, "w") as f:
        json.dump(st, f)
    if out:
        print(out)
    sys.exit(rc)


def tag_of(ref):
    return ref.rsplit(":", 1)[1] if ":" in ref else "latest"


def fmt():
    return args[args.index("-f") + 1] if "-f" in args else ""


def env_version():
    with open(".env") as f:
        lines = [line.strip() for line in f if line.startswith("APP_VERSION=")]
    return lines[-1].split("=", 1)[1] if lines else None


cmd = args[0]
if cmd == "pull":
    tag = tag_of(args[-1])
    if st.get("pull_fail") or tag not in st["registry"]:
        save(1)
    st["local"][tag] = st["registry"][tag]
    save()
if cmd == "tag":
    st["local"][tag_of(args[2])] = st["local"][tag_of(args[1])]
    save()
if cmd == "image" and args[1] == "inspect":
    tag = tag_of(args[-1])
    if tag not in st["local"]:
        save(1)
    f = fmt()
    if "finanzprognose.version" in f:
        save(0, st["local"][tag])
    if ".Id" in f:
        save(0, "sha:" + st["local"][tag])
    save(0, "[]")
if cmd == "image" and args[1] == "prune":
    save()
if cmd == "inspect":
    if st["running"] is None:
        save(1)
    f = fmt()
    if ".Image" in f:
        save(0, "sha:" + st["running"])
    if "Health" in f:
        save(0, "unhealthy" if st["running"] in st["unhealthy"] else "healthy")
    save(1)
if cmd == "compose":
    sub = args[1]
    if sub == "stop":
        st["running"] = None
    elif sub == "up":
        st["running"] = env_version()
        os.makedirs("data", exist_ok=True)
        with open("data/finanzen.sqlite", "a") as db:
            db.write(f"opened by {st['running']}\n")
    save()
if cmd == "create":
    save(0, "cid-" + tag_of(args[1]))
if cmd == "cp":
    dest = args[2]
    src = os.environ["FAKE_DEPLOY_SRC"]
    for name in os.listdir(src):
        shutil.copy(os.path.join(src, name), os.path.join(dest, name))
    save()
if cmd == "rm":
    save()
print(f"fake docker: unsupported {args}", file=sys.stderr)
save(2)
