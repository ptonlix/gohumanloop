## Apiservices

`Apiservices` 提供一系列对接`GoHumanLoop`的`APIProvider`示例服务。让`GoHumanLoop`轻松将 AI Agent 框架审批和获取信息的能力，拓展到更多第三方服务中，比`飞书`、`企业微信`和`钉钉`等常见的企业内部 OA 系统。

## 服务列表

- `mock`：基于`FastAPI`的`Mock`服务，用于模拟`GoHumanLoop`的`APIProvider`接口。
- `gohumanloop-wework`: 基于 Go 实现的企业微信 APIProvider 服务，用于对接企业微信的审批和消息接口。

## 实例说明

### 1. mock 服务

跳转到 [mock 服务](./mock/README.md) 查看详细说明。

### 2. GoHumanLoopHub 服务

- [gohumanloophub](https://github.com/ptonlix/gohumanloophub)

更多信息请前往查看

### 3. gohumanloop-wework 服务

**仓库地址:**

- [gohumanloop-wework](https://github.com/ptonlix/gohumanloop-wework)

**快速 Docker 部署:**

- 提前安装好 Docker 服务

```shell
docker pull ptonlix/gohumanloop-wework:latest
```

- 运行容器

```shell
docker run -d \
  --name gohumanloop-wework \
  -v /path/to/local/conf:/app/conf \
  -v /path/to/local/data:/app/data \
  -p 9800:9800 \
  ptonlix/gohumanloop-wework:latest

```

### 4. gohumanloop-feishu 服务

**仓库地址:**

- [gohumanloop-feishu](https://github.com/ptonlix/gohumanloop-feishu)

**快速 Docker 部署:**

- 提前安装好 Docker 服务

```shell
docker pull ptonlix/gohumanloop-feishu:latest
```

- 运行容器

```shell
docker run -d \
  --name gohumanloop-feishu \
  -v /path/to/local/conf:/app/conf \
  -v /path/to/local/data:/app/data \
  -p 9800:9800 \
  ptonlix/gohumanloop-feishu:latest

```
