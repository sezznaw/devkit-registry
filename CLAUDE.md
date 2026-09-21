# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The template registry consumed by the `devkit` CLI (sibling checkout at
`../devkit`). There is no build here: the repo is data. Format and rules are
authoritative in `../devkit/docs/registry.md`; read that before editing.
There are two components, both whole-project templates: `kitex-service`
behind `devkit ngs` (RPC) and `hertz-service` behind `devkit nas` (HTTP API) (the early `logger` and `grpc` components were removed; shared
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

## hertz-service specifics

- The HTTP API is Thrift IDL with Hertz annotations (`api.get="/ping"`), generated with `hz`.
  Verified with hz v0.9.7 / Hertz v0.10.6: never run `hz new`. The template ships `.hz`
  (`handlerDir: handler`, `modelDir: hertz_gen`, `routerDir: router`; `hz update` has no
  `--router_dir` flag, it reads this file) and the Makefile runs only
  `hz update -I $(IDL_DIR) -idl ... -t template=slim`. `template=slim` makes plain structs;
  without it the models need `replace github.com/apache/thrift => v0.13.0` in go.mod.
- Generated and git-ignored like `kitex_gen/`: `hertz_gen/`, `router/**/*.go` except
  `router/**/middleware.go`. hz creates `handler/<ns>/<service>.go` and `middleware.go` once and
  afterwards only appends (a stub per new method); the template pre-creates the handler with a
  working `Ping`, at the path hz expects (`handler/{{.Service | snake}}/{{.Service | snake}}_service.go`).
  That file must import `hertz_gen/<ns>` under the package's own name, never an alias: hz appends
  stubs that say `<ns>.XxxReq` and does not touch the imports of an existing file (0.1.0 used the
  alias `api` and the first added route did not compile; found by doing the new-employee
  walkthrough for real). When a template pre-creates a file a generator later appends to, run the
  generator once more with a changed IDL before releasing.
- A Hertz handler imports `github.com/cloudwego/hertz/pkg/app`, so the service's own `app` package
  cannot be used from handlers. What handlers need (RPC clients, Redis) lives in package `deps`
  (`deps/deps.go`, a `once` file); `app.Setup(cfg, h)` creates it. Do not move it back into `app`.
- `main.go`: `config.LoadDefault` -> `hertzx.New` -> `app.Setup(&cfg, h)` ->
  `router.GeneratedRegister(h)` -> `hertzx.Run`. The configuration is `kitexx.Config`
  (`hertzx.Config` is an alias), so `conf/*` are the RPC template's with HTTP wording; keep the
  two sets in step when a setting is added.
- Both templates must pin the same `CommonVersion`, `KitexVersion`, `ThriftgoVersion`, `GoVersion`
  (a project has one `common/` and one set of generators); `scripts/check.py` fails otherwise, and
  also checks `HertzVersion` against the pinned common's go.mod and the `post_update` literal.
  A common release therefore means a new version of BOTH templates.

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
  (`order-item` -> `order_item/orderitemservice`). One exception that `main.go.tmpl` mirrors with
  template built-ins (`slice`, `eq`; no devkit function, so older CLIs still render it): thriftgo
  appends `_` to a Thrift service whose name begins with `New` (`news` -> `news/newsservice_`,
  interface `NewsService_`), because of the `NewXxx` constructors it generates. Do not name a
  test service `new...` and expect the plain name. `main.go` has no helper around `zlog.Fatal`:
  called in place, the record's caller is the step that failed.
- `main.go` is managed and uses the common library's API, while `go.mod` is a
  `once` file and `devkit update` reuses the vars stored at creation time
  (including the then-default `CommonVersion`). So when a template version
  needs a newer common, the `post_update` hook must name that version
  literally (`go get ...devkit-common@vX.Y.Z && go mod tidy`): with a devkit
  older than 0.1.8, `{{.CommonVersion}}` still resolves to the value stored at
  creation and would re-pin existing services to the old one.
- Defaults `CommonModule`/`CommonVersion`/`KitexVersion` must stay in sync
  with `../common` (module `github.com/sezznaw/devkit-common`, its go.mod
  kitex version and latest tag). Releasing a new common version therefore
  means a new `kitex-service` version here too. `IdlRepo` and
  `GoPrivate` are filled by ngs from the project's devkit.yaml; the CI
  template uses `{{"{{"}}` escapes to emit literal GitHub `${{ }}` syntax.

## One version for the whole team

The owner's rule: every service uses the same Kitex, thriftgo and common
version, and nobody can choose otherwise. The template is the single source:

- `KitexVersion`, `ThriftgoVersion`, `CommonVersion`, `CommonModule` are
  `"track": true`. devkit (>= 0.1.9) always renders them from the newest
  template, on creation and on update, and refuses `--set` / `devkit.yaml`
  `vars:` for them. Do not add an escape hatch.
- Kitex appears in three places that must agree: the `KitexVersion` default,
  the literal in the `post_update` hook, and the `go.mod` of the pinned
  `devkit-common` release. **To raise Kitex: first release a common version on
  the new Kitex, then set `KitexVersion`, `CommonVersion` and both literals in
  the hook here, in one commit.** `scripts/check.py` enforces all of this and
  runs in CI (`.github/workflows/check.yml`); run it before tagging.
- The hook names versions literally because a devkit older than 0.1.8 would
  expand `{{.KitexVersion}}` to the value stored when the service was created
  and downgrade it.
- `go.mod` is a `once` file, so the hook (`go get kitex@… common@…`) is what
  moves existing services; the Makefile's `check-tools` stops `make gen` when
  the installed generators are not the team's versions.

## Framework files versus service files

The owner's rule: the framework is maintained centrally through devkit, so
nothing specific to one service may live in a framework file. A managed file
that developers are told to edit becomes "modified" and can never be updated
again. This went wrong twice (the `IDLS` line in the Makefile, then `Config`
and `OnShutdown` in `main.go`) and was fixed the same way both times: move the
service's part into a `once` file that the managed file calls or includes.

- Managed (framework): `cmd/<svc>/main.go`, `Makefile`, CI files,
  `Dockerfile`, `.gitignore`, `conf/README.md`. Never tell anyone to edit these.
- `once` (service): `app/*`, `handler/*`, `conf/*.yaml`, `idl.mk`, `go.mod`,
  `README.md`.
- `main.go` only sequences the start-up and calls `app.Setup(&cfg)` and
  `app.ServerOptions(&cfg)`. When a service needs a new kind of hook, add a
  function to the `app/app.go` template and call it from `main.go`; do not
  document "edit main.go". Existing services get new `app` functions only if
  `main.go` tolerates their absence, so a new required hook is a breaking
  change that needs a changelog action.

## Telling developers what changed

`conf/*.yaml`, `handler/*`, `go.mod`, `idl.mk` are `once` files, so an update
can never put a new setting into them. Two things compensate, and both must be
maintained with every template change:

- `changelog` in `component.json`: one entry per version with `changes` (what
  is different) and `action` (what the developer may want to do by hand, with
  the exact snippet). `devkit update` (>= 0.1.6) prints the entries between the
  installed and the new version. An entry with no `action` is fine; a new
  config setting without an `action` is a bug.
- `conf/README.md` and `conf/README.zh-CN.md`: a managed reference of every setting with its
  default, one file per language. It is excluded from `once` because the pattern is `conf/*.yaml`.

Comments in `conf/local.yaml` / `conf/dev.yaml` / `conf/uat.yaml` / `conf/prod.yaml` are bilingual and
explain every key. The owner could not read them while the languages ran into each other, so the
layout is a rule and `scripts/check.py` enforces it: the English block, an empty comment line, then
the Chinese block; never both languages on one line (a short `English / 中文` label is the one
exception); a file header is the whole English part, a `# ----` divider, the whole Chinese part.
Markdown is never bilingual in one file: `conf/README.md` (English) and `conf/README.zh-CN.md`
(Chinese) have the same structure and a language switch in the first lines; change both together.

## Gotchas

- Templates run with `missingkey=error`: an undefined `{{.Foo}}` breaks the
  install. Built-ins are `Module`, `Project`, `ComponentName`,
  `ComponentVersion` plus the component's declared `vars`.
- Hooks are rendered as templates and run with `sh -c` in the service directory.
