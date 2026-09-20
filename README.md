# devkit-registry

**English** | [简体中文](README.zh-CN.md)

Templates consumed by the [`devkit`](../devkit) CLI. Users never clone this
repository: devkit reads it through the GitHub API (raw files and tag tarballs).

## Components

| Component | Version | Description |
|-----------|---------|-------------|
| `kitex-service` | 0.1.1 | Whole Kitex (Thrift) service project: Nacos, logging, config, codegen Makefile, GitHub Actions CI, Dockerfile. This is what `devkit ngs` generates. |

## Layout

```
registry.json                       latest version of every component (read from main)
components/<name>/component.json    name, version, vars, hooks, once
components/<name>/files/...         written into the new service; *.tmpl files are rendered
components/<name>/idl/...           written into the project's IDL checkout
```

The full format (variables, template functions, `once`, hooks) is documented in
[devkit/docs/registry.md](../devkit/docs/registry.md).

## Publishing a new version

1. Edit the component and bump `version` in its `component.json`.
2. Put the same version in `registry.json`.
3. Commit, tag and push:

   ```sh
   git tag kitex-service/v0.2.0
   git push origin main --tags
   ```

Tags are immutable: devkit caches every downloaded version forever. Never move
or delete a tag; publish a new version instead. Existing services pick the new
version up with `devkit update`.

## Testing before you tag

```sh
export DEVKIT_REGISTRY_DIR=$PWD            # devkit reads the working tree, ignores tags
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "sezznaw/shop-idl"\n' > devkit.yaml
devkit ngs order && cd order && go build ./... && go vet ./...
```
