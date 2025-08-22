# Contributing to GoHumanLoop

感谢您对 GoHumanLoop 项目的关注！我们欢迎各种形式的贡献，包括但不限于：

- 🐛 Bug 修复
- ✨ 新功能开发
- 📚 文档改进
- 🧪 测试用例补充
- 💡 功能建议和讨论

## 🚀 快速开始

### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (推荐的包管理工具)

### 开发环境设置

1. **Fork 并克隆仓库**

   ```bash
   git clone https://github.com/your-username/gohumanloop.git
   cd gohumanloop
   ```

2. **安装依赖**

   ```bash
   uv sync --all-extras
   ```

3. **安装开发工具**
   ```bash
   make githooks  # 安装 pre-push 钩子
   ```

## 🔧 开发工作流

### 代码质量检查

在提交代码前，请运行完整的代码质量检查：

```bash
make check
```

这个命令会执行：

- **pre-commit**: 代码格式化和基础检查
- **mypy**: 静态类型检查
- **deptry**: 依赖项检查

### 运行测试

```bash
make test
```

测试覆盖了以下模块：

- `core/`: 核心接口和管理器
- `providers/`: 各种提供者实现
- `adapters/`: 框架适配器
- `utils/`: 工具函数

### 单独运行工具

```bash
# 仅类型检查
make typecheck

# 仅运行 pre-commit 检查
uv run pre-commit run -a

# 运行特定测试
uv run pytest tests/unit/core/ -v
```

## 📝 代码规范

### 代码风格

我们使用以下工具确保代码质量：

- **Ruff**: 代码格式化和 linting
- **MyPy**: 静态类型检查
- **Prettier**: Markdown 和配置文件格式化

### 类型注解

- 所有公共 API 必须包含完整的类型注解
- 使用 `from __future__ import annotations` 支持前向引用
- 遵循 PEP 484 和 PEP 526 规范

### 文档字符串

使用 Google 风格的文档字符串：

```python
def example_function(param1: str, param2: int) -> bool:
    """简短描述函数功能。

    Args:
        param1: 参数1的描述
        param2: 参数2的描述

    Returns:
        返回值的描述

    Raises:
        ValueError: 异常情况的描述
    """
    pass
```

## 🏗️ 项目架构

### 核心模块

- `core/`: 定义核心接口和默认管理器
- `providers/`: 实现各种人机交互提供者（Terminal、Email、API 等）
- `adapters/`: 与 AI 框架的集成适配器
- `manager/`: 高级管理器实现
- `utils/`: 通用工具函数

### 添加新功能

1. **新的 Provider**: 继承 `BaseProvider` 并实现必要接口
2. **新的 Adapter**: 实现 `HumanloopAdapter` 接口
3. **核心功能**: 遵循现有的接口设计模式

## 🧪 测试指南

### 测试结构

```
tests/
├── unit/           # 单元测试
│   ├── core/       # 核心功能测试
│   ├── providers/  # 提供者测试
│   ├── adapters/   # 适配器测试
│   └── utils/      # 工具函数测试
└── main.py         # 测试入口
```

### 编写测试

- 为新功能编写对应的单元测试
- 使用 `pytest` 和 `pytest-asyncio` 进行异步测试
- 保持测试覆盖率在合理水平

## 📦 构建和发布

### 构建包

```bash
make build
```

### 发布（维护者）

```bash
make build-and-publish
```

## 🤝 提交 Pull Request

1. **创建功能分支**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **提交更改**

   - 使用清晰的提交信息
   - 每个提交应该是一个逻辑单元
   - 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范

3. **推送并创建 PR**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **PR 检查清单**
   - [ ] 代码通过所有质量检查 (`make check`)
   - [ ] 测试通过 (`make test`)
   - [ ] 添加了必要的测试用例
   - [ ] 更新了相关文档
   - [ ] PR 描述清晰说明了更改内容

## 💬 获取帮助

- 📖 查看 [README](README.md) 了解项目概述
- 🐛 通过 [Issues](https://github.com/ptonlix/gohumanloop/issues) 报告问题
- 💡 在 [Discussions](https://github.com/ptonlix/gohumanloop/discussions) 中讨论想法

## 📄 许可证

通过贡献代码，您同意您的贡献将在 [MIT License](LICENSE) 下授权。

---

再次感谢您的贡献！🎉
