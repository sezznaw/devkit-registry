#!/usr/bin/env bash
# Builds an image from the kitex-service Dockerfile template and runs it.
#
# The Dockerfile is the one template file that nothing else exercises:
# `devkit ngs` only writes it. This renders it for a stand-in service that
# loads its configuration exactly like a generated main.go does, and checks
# what the image does with APP_ENV, which is where a mistake is expensive: a
# container that starts with conf/dev.yaml looks healthy and serves nobody.
#
# Needs docker, go and python3. CI runs it on every push.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
comp="$root/components/kitex-service"
var() { python3 -c "import json,sys; print(next(v['default'] for v in json.load(open('$comp/component.json'))['vars'] if v['name']==sys.argv[1]))" "$1"; }
go_version=$(var GoVersion); common=$(var CommonModule); common_version=$(var CommonVersion); port=$(var Port)

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
cd "$work"
mkdir -p cmd/demo conf
cat > cmd/demo/main.go <<GO
package main

import (
	"fmt"

	"$common/config"
	"$common/zlog"
)

func main() {
	var cfg struct {
		Name string \`yaml:"name"\`
	}
	if err := config.LoadDefault(&cfg); err != nil {
		zlog.Fatal("cannot start", zlog.Err(err))
	}
	fmt.Println("loaded:", cfg.Name)
}
GO
for env in dev prod test; do echo "name: from-$env" > "conf/$env.yaml"; done
echo "not a configuration file" > conf/README.md

# The template with its variables filled in; the optional GOPRIVATE block is
# left out, the stand-in has no private modules.
sed -e '/^{{- if .GoPrivate}}$/,/^{{- end}}$/d' \
    -e "s/{{.GoVersion}}/$go_version/g" -e "s/{{.Service}}/demo/g" -e "s/{{.Port}}/$port/g" \
    "$comp/files/Dockerfile.tmpl" > Dockerfile
if grep -n '{{' Dockerfile; then echo "FAIL: the Dockerfile template uses a variable this script does not fill in"; exit 1; fi

go mod init demo >/dev/null 2>&1
go get "$common@$common_version" >/dev/null 2>&1
go mod tidy >/dev/null 2>&1

img=devkit-dockerfile-test
docker build -q -t "$img" . >/dev/null
fail() { echo "FAIL: $*"; exit 1; }

out=$(docker run --rm "$img") || fail "the image does not start as it is built: $out"
[ "$out" = "loaded: from-prod" ] || fail "without any variable the image must use prod.yaml, got: $out"

out=$(docker run --rm -e APP_ENV=test "$img") || fail "APP_ENV=test: $out"
[ "$out" = "loaded: from-test" ] || fail "every environment but dev must be in the image, got: $out"

# APP_ENV lost: config falls back to "dev", and that file must not be there.
set +e; out=$(docker run --rm -e APP_ENV= "$img" 2>&1); code=$?; set -e
[ "$code" -eq 1 ] || fail "with APP_ENV empty the container must exit with status 1, got $code: $out"
echo "$out" | python3 -c '
import json, sys
rec = json.loads(sys.stdin.read().strip().splitlines()[0])
assert rec["level"] == "FATAL" and rec["service"] == "demo", rec
assert "dev.yaml does not exist" in rec["err"] and "available: prod, test" in rec["err"], rec["err"]
' || fail "the refusal must be one JSON record that names the files there are, got: $out"

echo "ok: the image uses prod.yaml, has every environment but dev, and refuses to start without APP_ENV"
