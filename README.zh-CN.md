# devkit-registry

[English](README.md) | **简体中文**

[`devkit`](../devkit) 命令行工具使用的模板仓库。使用者不需要 clone 它，devkit 通过 GitHub API（raw 文件和 tag 归档）读取。

## 组件列表

| 组件 | 版本 | 说明 |
|------|------|------|
| `kitex-service` | 见 `registry.json` | 完整的 Kitex（Thrift）服务项目：Nacos、日志、配置、代码生成 Makefile（对 `idl.mk` 里的 IDL 和 `errors/*.thrift` 跑 kitex，`errgen` 生成错误消息，前后 `devkit lock`）、GitHub Actions 与 GitLab CI 两种 CI 配置、Dockerfile；服务自己的文件 `handler/{handler,codes}.go`、`repo/`、`app/{app,jobs,verify}.go`。`devkit ngs` 生成的就是它。 |
| `hertz-service` | 见 `registry.json` | 完整的 API（HTTP）服务工程，基于 Hertz：IDL 是一个目录（`idl/<服务>/docs.thrift` 加每个领域一个 `<领域>.thrift`），Makefile 对每个领域文件跑一次 `hz`、用 `apidoc -dir` 合并出 OpenAPI 文档，每个领域一个 `handler/<领域>/`（初始是 `handler/system/`），用 Kitex 生成它要调用的 RPC 服务的客户端，Nacos、日志、配置、CI、Dockerfile 与 RPC 服务相同。`devkit nas` 生成的就是它。 |

## 目录结构

```
registry.json                       每个组件的最新版本（从 main 分支读取）
components/<name>/component.json    名称、版本、变量（共用的版本变量带 `track: true`）、钩子、once、changelog
components/<name>/files/...         写入新服务目录；*.tmpl 文件会被渲染
components/<name>/idl/...           写入项目的 IDL 仓库检出目录
```

完整格式（变量、模板函数、`once`、钩子）见 [devkit/docs/registry.md](../devkit/docs/registry.md)。

## 发布新版本

两个组件共用版本变量（`GoVersion`、`KitexVersion`、`ThriftgoVersion`、`CommonModule`、`CommonVersion`、`DevkitVersion`；不一致时 `check.py` 失败），所以一次发布通常两个一起动：

1. 修改组件；在各自的 `component.json` 里升 `version`，并给该版本加一条 `changelog`。
2. 在 `registry.json` 中写入相同的版本号。
3. `python3 scripts/check.py` 必须通过（见下文）。
4. 提交，给每个升了版本的组件打 tag，推送：

   ```sh
   git tag kitex-service/v0.51.3
   git tag hertz-service/v0.44.3
   git push origin main --tags
   ```

新版本大约五分钟内对用户可见：devkit 通过 GitHub 的 raw 文件 CDN 读取 `registry.json`，该 CDN 会缓存 300 秒。

tag 不可变：devkit 会永久缓存每个下载过的版本。不要移动或删除 tag，需要修改时发布新版本。已有的服务通过 `devkit update` 升级到新版本。

## 升级 Kitex 版本

所有服务使用同一个 Kitex 版本，所以只在一处、按顺序升级：

1. 先发布一个 `devkit-common` 版本，它的 `go.mod` 要求新的 Kitex。
2. 在本仓库用一次提交、两个组件一起完成：`KitexVersion`、`CommonVersion`，以及各自 `post_update` 钩子里的字面版本号（`hertz-service` 还有 `HertzVersion`，必须等于 devkit-common 的 `go.mod` 所要求的版本，以及 `HzVersion`），再加一条变更说明和版本号升级。
3. `python3 scripts/check.py` 必须通过，CI 也会运行它。以下情况它会失败：`registry.json` 和某个 `component.json` 不一致；某个版本没有 changelog；共用的版本变量没带 `track: true` 或两个组件不同；`post_update` 钩子里没有 Kitex / Hertz / common 的字面版本号，或含有 `{{`；模板里的 Kitex、Hertz、Go 版本和 devkit-common 的 `go.mod` 不一致；英文 `.md` 里出现中文，或英文注释和中文注释写在同一行、同一个注释块里（要分开两块）。

各服务通过 `devkit update` 获得新版本，它会对齐服务的 `go.mod`，并在需要时重装代码生成器。

## 打 tag 之前先验证

```sh
export DEVKIT_REGISTRY_DIR=$PWD            # devkit 直接读工作区，忽略 tag
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "sezznaw/shop-idl"\n' > devkit.yaml
devkit ngs order && cd order && make gen && go build ./... && make lint && make test
cd .. && devkit nas gateway && cd gateway && make gen && go build ./... && make lint && make test
```
