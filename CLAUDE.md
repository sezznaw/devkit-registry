# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The template registry consumed by the `devkit` CLI (sibling checkout at
`../devkit`). There is no build here: the repo is data. Format and rules are
authoritative in `../devkit/docs/registry.md`; read that before editing.
The only component is `kitex-service`, the whole-project template behind
`devkit ngs` (the early `logger` and `grpc` components were removed; shared
code lives in the Go module `github.com/sezznaw/devkit-common`, checked out
locally at `../common`).

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

After pushing, the new index is not visible immediately: raw.githubusercontent.com
caches `registry.json` for 300 s, separately per `Accept-Encoding`. Plain
`curl` may already show the new version while devkit (Go client, gzip) still
gets the old one. Check with `curl --compressed` and wait before concluding a
publish went wrong.

Test hygiene: commit real edits before mutating template files for an
upgrade test, and clean up with `git stash`/a scratch copy, never with
`git checkout --` on files that also carry uncommitted work.

## Testing a template before tagging

```sh
export DEVKIT_REGISTRY_DIR=$PWD          # devkit reads the working tree, ignores tags
export HOME=$(mktemp -d)                 # keep your real ~/.devkit untouched
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "/path/to/a/local/idl/git/repo"\n' > devkit.yaml
devkit ngs order && cd order && go build ./... && go vet ./...
```

`devkit-common` is public, so `go mod tidy` in the generated service resolves
through proxy.golang.org. Only when testing an *unpublished* version of the
common module do you need the file-based module proxy described in
`../devkit/CLAUDE.md`.

## kitex-service specifics

- `Module` is passed by ngs with `--set` semantics (there is no go.mod to read
  yet). `go.mod`, `idl.mk`, `conf/*`, `handler/*`, `README.md` are `once` files: created,
  then owned by the developer. Infra files (Makefile,
  the CI files, Dockerfile, `cmd/<svc>/main.go`) stay managed so
  they can be upgraded with `devkit update`.
- User data never lives in a managed file. The list of IDLs to generate is in
  `idl.mk` (a `once` file, `IDLS := ...`), which the managed `Makefile` pulls
  in with `-include idl.mk` and a `?=` fallback. Before 0.2.1 the list was a
  line in the Makefile, so any service calling another one had a "modified"
  Makefile that `devkit update` could no longer upgrade.
- The Makefile generates from `IDL_DIR ?= ../idl`; `kitex_gen/` is git-ignored
  and CI regenerates it after checking out the IDL project.
- Two CI files, both wrapped in `{{if}}` on the `CI` var (`github`, `gitlab`,
  `both`, `none`): `.github/workflows/ci.yml` and `.gitlab-ci.yml`. A template
  that renders empty produces no file (devkit >= 0.1.3), so exactly the wanted
  ones appear. ngs sets `CI` from the host of `module_prefix`/`idl_repo` and
  `IdlRepo` to the IDL project *path*; when `IdlRepo` is empty the GitHub file
  falls back to `<repository_owner>/idl` and the GitLab file to
  `${CI_PROJECT_NAMESPACE}/idl`. The GitLab pipeline clones IDL with
  `CI_JOB_TOKEN`, which the IDL project must allow (job token permissions).
  It has not been run on a real GitLab yet.
- `main.go` imports `kitex_gen/...`, so the service only compiles after
  `make gen`; the post_install hook runs it (ngs installs kitex/thriftgo first).
- Kitex package naming used in templates: namespace `{{.Service | snake}}`,
  service package `{{.Service | title | lower}}service`
  (`order-item` -> `order_item/orderitemservice`).
- `main.go` is managed and uses the common library's API, while `go.mod` is a
  `once` file and `devkit update` reuses the vars stored at creation time
  (including the then-default `CommonVersion`). So when a template version
  needs a newer common, the `post_update` hook must name that version
  literally (`go get ...devkit-common@vX.Y.Z && go mod tidy`); relying on
  `{{.CommonVersion}}` would re-pin existing services to the old one.
- Defaults `CommonModule`/`CommonVersion`/`KitexVersion` must stay in sync
  with `../common` (module `github.com/sezznaw/devkit-common`, its go.mod
  kitex version and latest tag). Releasing a new common version therefore
  means a new `kitex-service` version here too. `IdlRepo` and
  `GoPrivate` are filled by ngs from the project's devkit.yaml; the CI
  template uses `{{"{{"}}` escapes to emit literal GitHub `${{ }}` syntax.

## Gotchas

- Templates run with `missingkey=error`: an undefined `{{.Foo}}` breaks the
  install. Built-ins are `Module`, `Project`, `ComponentName`,
  `ComponentVersion` plus the component's declared `vars`.
- Hooks are rendered as templates and run with `sh -c` in the service directory.
