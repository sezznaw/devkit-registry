# devkit-registry

[English](README.md) | **简体中文**

[`devkit`](../devkit) 命令行工具使用的模板仓库。使用者不需要 clone 它，devkit 通过 GitHub API（raw 文件和 tag 归档）读取。

## 组件列表

| 组件 | 版本 | 说明 |
|------|------|------|
| `kitex-service` | 0.2.0 | 完整的 Kitex（Thrift）服务项目：Nacos、日志、配置、代码生成 Makefile、GitHub Actions 与 GitLab CI 两种 CI 配置、Dockerfile。`devkit ngs` 生成的就是它。 |

## 目录结构

```
registry.json                       每个组件的最新版本（从 main 分支读取）
components/<name>/component.json    名称、版本、变量、钩子、once
components/<name>/files/...         写入新服务目录；*.tmpl 文件会被渲染
components/<name>/idl/...           写入项目的 IDL 仓库检出目录
```

完整格式（变量、模板函数、`once`、钩子）见 [devkit/docs/registry.md](../devkit/docs/registry.md)。

## 发布新版本

1. 修改组件，并更新其 `component.json` 中的 `version`。
2. 在 `registry.json` 中写入相同的版本号。
3. 提交、打 tag 并推送：

   ```sh
   git tag kitex-service/v0.2.0
   git push origin main --tags
   ```

tag 不可变：devkit 会永久缓存每个下载过的版本。不要移动或删除 tag，需要修改时发布新版本。已有的服务通过 `devkit update` 升级到新版本。

## 打 tag 之前先验证

```sh
export DEVKIT_REGISTRY_DIR=$PWD            # devkit 直接读工作区，忽略 tag
mkdir /tmp/proj && cd /tmp/proj
printf 'module_prefix: "github.com/sezznaw"\nidl_repo: "sezznaw/shop-idl"\n' > devkit.yaml
devkit ngs order && cd order && go build ./... && go vet ./...
```
