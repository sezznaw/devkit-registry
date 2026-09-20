#!/usr/bin/env python3
"""Consistency checks for the registry. Run before tagging; CI runs it on every push.

The team uses one Kitex version. It is written in three places that must agree:
the template's KitexVersion, the literal in its post_update hook, and the go.mod
of the devkit-common release the template pins. This script is what keeps them
from drifting apart.
"""
import json, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors, notes = [], []


def err(msg):
    errors.append(msg)


def common_gomod(module, version):
    """go.mod of the pinned common release: sibling checkout first, else GitHub."""
    sibling = os.path.join(ROOT, "..", "common")
    if os.path.isdir(os.path.join(sibling, ".git")):
        r = subprocess.run(["git", "-C", sibling, "show", f"{version}:go.mod"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout, f"../common at tag {version}"
    m = re.match(r"github\.com/([^/]+/[^/]+)$", module)
    if not m:
        return None, None
    url = f"https://raw.githubusercontent.com/{m.group(1)}/{version}/go.mod"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode(), url
    except Exception as e:  # offline, or the tag does not exist
        notes.append(f"could not read {url}: {e}")
        return None, None


index = json.load(open(os.path.join(ROOT, "registry.json")))
for name, entry in index["components"].items():
    path = os.path.join(ROOT, "components", name, "component.json")
    if not os.path.exists(path):
        err(f"{name}: listed in registry.json but {path} is missing")
        continue
    comp = json.load(open(path))
    if comp.get("name") != name:
        err(f"{name}: component.json says name={comp.get('name')!r}")
    if comp.get("version") != entry.get("version"):
        err(f"{name}: registry.json has {entry.get('version')}, component.json has {comp.get('version')}")
    if not any(e.get("version") == comp.get("version") for e in comp.get("changelog", [])):
        err(f"{name}: no changelog entry for {comp.get('version')}; developers learn about changes only from it")

    defaults = {v["name"]: v.get("default", "") for v in comp.get("vars", [])}
    tracked = {v["name"] for v in comp.get("vars", []) if v.get("track")}
    for v in ("GoVersion", "KitexVersion", "ThriftgoVersion", "CommonVersion", "CommonModule"):
        if v in defaults and v not in tracked:
            err(f"{name}: {v} must be \"track\": true, versions are the same for every service")

    hook = " ".join(comp.get("hooks", {}).get("post_update", []))
    kitex, common_mod, common_ver = defaults.get("KitexVersion"), defaults.get("CommonModule"), defaults.get("CommonVersion")
    if kitex and f"github.com/cloudwego/kitex@{kitex}" not in hook:
        err(f"{name}: post_update must align go.mod with `go get github.com/cloudwego/kitex@{kitex}` (KitexVersion default); found: {hook!r}")
    if common_mod and common_ver and f"{common_mod}@{common_ver}" not in hook:
        err(f"{name}: post_update must contain `{common_mod}@{common_ver}` (CommonVersion default); found: {hook!r}")
    if "{{" in hook and ("KitexVersion" in hook or "CommonVersion" in hook):
        err(f"{name}: write versions literally in post_update; a devkit older than 0.1.8 expands the variables to stale values")

    if kitex and common_mod and common_ver:
        gomod, where = common_gomod(common_mod, common_ver)
        if gomod is None:
            notes.append(f"{name}: skipped the check against {common_mod}@{common_ver} (not reachable)")
        else:
            m = re.search(r"^\s*(?:require\s+)?github\.com/cloudwego/kitex\s+(\S+)", gomod, re.M)
            have = m.group(1) if m else None
            g = re.search(r"^go\s+(\d+)\.(\d+)", gomod, re.M)
            want_go = defaults.get("GoVersion", "")
            if g and want_go:
                need = (int(g.group(1)), int(g.group(2)))
                if tuple(int(x) for x in want_go.split(".")[:2]) < need:
                    err(f"{name}: GoVersion is {want_go} but {common_mod}@{common_ver} needs go {need[0]}.{need[1]}; "
                        "the golang Docker image refuses to build a module that needs a newer Go")
            if have != kitex:
                err(f"{name}: KitexVersion is {kitex} but {common_mod}@{common_ver} requires kitex {have} ({where}). "
                    "Release a common version on the same Kitex first, then pin it here.")
            else:
                notes.append(f"{name}: Kitex {kitex} matches {common_mod}@{common_ver} ({where})")

for n in notes:
    print("note:", n)
if errors:
    print()
    for e in errors:
        print("ERROR:", e)
    sys.exit(1)
print("registry is consistent")
