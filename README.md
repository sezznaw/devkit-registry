# devkit-registry

**English** | [简体中文](README.zh-CN.md)

Templates consumed by the [`devkit`](../devkit) CLI. Users never clone this
repository: devkit reads it through the GitHub API (raw files and tag tarballs).

## Components

| Component | Version | Description |
|-----------|---------|-------------|
| `kitex-service` | see `registry.json` | Whole Kitex (Thrift) service project: Nacos, logging, config, codegen Makefile (kitex for the IDLs in `idl.mk` and for `errors/*.thrift`, `errgen` for the error messages, `devkit lock` around it), CI for GitHub Actions and GitLab CI, Dockerfile; `handler/{handler,codes}.go`, `repo/`, `app/{app,jobs,verify}.go` as the service's own files. This is what `devkit ngs` generates. |
| `hertz-service` | see `registry.json` | Whole API (HTTP) service project on Hertz: the IDL is a directory (`idl/<service>/docs.thrift` + one `<domain>.thrift` per domain), the Makefile runs `hz` once per domain file and `apidoc -dir` for the merged OpenAPI document, `handler/<domain>/` per domain (`handler/system/` to start), Kitex clients for the RPC services behind it, and the same Nacos, logging, config, CI and Dockerfile as an RPC service. This is what `devkit nas` generates. |

## Layout

```
registry.json                       latest version of every component (read from main)
components/<name>/component.json    name, version, vars (`track: true` on the shared versions), hooks, once, changelog
components/<name>/files/...         written into the new service; *.tmpl files are rendered
components/<name>/idl/...           written into the project's IDL checkout
```

The full format (variables, template functions, `once`, hooks) is documented in
[devkit/docs/registry.md](../devkit/docs/registry.md).

## Publishing a new version

Both components share their version variables (`GoVersion`, `KitexVersion`,
`ThriftgoVersion`, `CommonModule`, `CommonVersion`, `DevkitVersion`;
`check.py` fails when they differ), so a release normally touches both:

1. Edit the component(s); bump `version` in each `component.json` and add a
   `changelog` entry for that version.
2. Put the same versions in `registry.json`.
3. `python3 scripts/check.py` must pass (see below).
4. Commit, tag each component you bumped, and push:

   ```sh
   git tag kitex-service/v0.51.3
   git tag hertz-service/v0.44.3
   git push origin main --tags
   ```

A new version becomes visible to users within about five minutes: devkit reads
`registry.json` through GitHub's raw-file CDN, which caches it for 300 seconds.

Tags are immutable: devkit caches every downloaded version forever. Never move
or delete a tag; publish a new version instead. Existing services pick the new
version up with `devkit update`.

## Raising the Kitex version

Every service uses the same Kitex, so it is raised in one place and in order:

1. Release a `devkit-common` version whose `go.mod` requires the new Kitex.
2. Here, in one commit, in both components: `KitexVersion`, `CommonVersion`
   and the literal versions in each `post_update` hook (`hertz-service` also
   has `HertzVersion`, which must equal what devkit-common's `go.mod`
   requires, and `HzVersion`), plus a changelog entry and the version bump.
3. `python3 scripts/check.py` must pass; CI runs it too. It fails when:
   `registry.json` and a `component.json` disagree; a version has no
   changelog entry; a shared version variable lacks `track: true` or differs
   between the two components; the `post_update` hook does not contain the
   literal Kitex / Hertz / common versions, or contains `{{`; the template's
   Kitex, Hertz or Go version disagrees with devkit-common's `go.mod`; an
   English `.md` contains Chinese, or an English and a Chinese comment share a
   line or a comment block (they go in separate blocks).

Services pick it up with `devkit update`, which aligns their `go.mod` and
reinstalls the generators if needed.

## Testing before you tag

```sh
export DEVKIT_REGISTRY_DIR=$PWD            # devkit reads the working tree, ignores tags
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "sezznaw/shop-idl"\n' > devkit.yaml
devkit ngs order && cd order && make gen && go build ./... && make lint && make test
cd .. && devkit nas gateway && cd gateway && make gen && go build ./... && make lint && make test
```
