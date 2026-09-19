# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The template registry consumed by the `devkit` CLI (sibling checkout at
`../devkit`). There is no build here: the repo is data. Format and rules are
authoritative in `../devkit/docs/registry.md`; read that before editing.
The only component is `kitex-service`, the whole-project template behind
`devkit ngs` (the early `logger` and `grpc` components were removed; shared
code lives in the `../common` Go module instead).

## Layout and contract

- `registry.json` on `main` lists the *latest* version of every component. It
  is what `devkit ngs` installs and what `devkit update --check` compares with.
- `components/<name>/component.json` declares name, version, vars, hooks, once.
- `components/<name>/files/**` is written into the new service keeping relative
  paths. Path segments may contain `{{.Var}}`; only files ending in `.tmpl`
  are rendered (suffix dropped), everything else is copied byte for byte.
- `components/<name>/idl/**` is written by ngs into `<project>/idl/` (the IDL
  repository checkout), never over an existing file.
- Every published version is an immutable git tag `<name>/v<version>`.
  devkit downloads by tag and caches forever, so never retag or force-push a
  tag once pushed; publish a new version instead.

## Publishing a change

1. Edit files, bump `version` in `component.json`.
2. Set the same version in `registry.json`.
3. Commit, then `git tag <name>/v<version>` and push the tag.

Version strings carry no leading `v` in JSON; the `v` is only in the tag.

## Testing a template before tagging

```sh
export DEVKIT_REGISTRY_DIR=$PWD          # devkit reads the working tree, ignores tags
export HOME=$(mktemp -d)                 # keep your real ~/.devkit untouched
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "/path/to/a/local/idl/git/repo"\n' > devkit.yaml
devkit ngs order && cd order && go build ./... && go vet ./...
```

Until `common` is published on GitHub, `go mod tidy` needs the file-based
module proxy described in `../devkit/CLAUDE.md`.

## kitex-service specifics

- `Module` is passed by ngs with `--set` semantics (there is no go.mod to read
  yet). `go.mod`, `conf/*`, `handler/*`, `README.md` are `once` files: created,
  then owned by the developer. Infra files (Makefile,
  `.github/workflows/ci.yml`, Dockerfile, `cmd/<svc>/main.go`) stay managed so
  they can be upgraded with `devkit update`.
- The Makefile generates from `IDL_DIR ?= ../idl`; `kitex_gen/` is git-ignored
  and CI regenerates it after checking out `IdlRepo`.
- `main.go` imports `kitex_gen/...`, so the service only compiles after
  `make gen`; the post_install hook runs it (ngs installs kitex/thriftgo first).
- Kitex package naming used in templates: namespace `{{.Service | snake}}`,
  service package `{{.Service | title | lower}}service`
  (`order-item` -> `order_item/orderitemservice`).
- Defaults `CommonModule`/`CommonVersion`/`KitexVersion` must stay in sync
  with `../common` (its go.mod kitex version and latest tag). `IdlRepo` and
  `GoPrivate` are filled by ngs from the project's devkit.yaml; the CI
  template uses `{{"{{"}}` escapes to emit literal GitHub `${{ }}` syntax.

## Gotchas

- Templates run with `missingkey=error`: an undefined `{{.Foo}}` breaks the
  install. Built-ins are `Module`, `Project`, `ComponentName`,
  `ComponentVersion` plus the component's declared `vars`.
- Hooks are rendered as templates and run with `sh -c` in the service directory.
