## Mock Server 使用说明

### 本地运行

1. 安装依赖：

```bash
cd /Users/cfd/workstation/Agents/gohumanloop/apiservices/mock
pip install -r requirements.txt
```

2. 运行服务器：

```bash
python mock.py
```

或者使用 uvicorn：

```bash
uvicorn mock:app --reload --host 0.0.0.0 --port 8000
```

### Docker 部署

1. 构建并启动容器：

使用 Dockerfile 构建：

```bash
# 在 mock 目录下构建 Docker 镜像
docker build -t gohumanloop-mock .

# 启动容器
docker run -d -p 8000:8000 --name gohumanloop-mock-service gohumanloop-mock
```

2. 查看日志：

```bash
# 查看容器日志
docker logs gohumanloop-mock-service

# 实时跟踪日志
docker logs -f gohumanloop-mock-service
```

3. 停止服务：

```bash
# 停止容器
docker stop gohumanloop-mock-service

# 删除容器
docker rm gohumanloop-mock-service
```

### 使用 Mock 服务器

要使用这个 Mock 服务器，您需要将 APIProvider 对象中的参数

- api_base_url 设置为 Mock 服务器的地址
- api_key 设置为您的 API 密钥（gohumanloop）

## 特性说明

1. 自动响应 ：Mock 服务器会在随机的 5-15 秒后自动响应请求，模拟真实用户的行为。
2. 状态跟踪 ：服务器会跟踪所有请求和对话的状态。
3. 支持所有 API 端点 ：实现了与 APIProvider 兼容的所有端点。
4. 简单的 API 密钥验证 ：提供了基本的 API 密钥验证机制。
5. 健康检查 ：提供了健康检查端点，方便监控服务状态。
