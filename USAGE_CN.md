[English](USAGE.md) | [中文](USAGE_CN.md)

# Resume Tailor - 快速参考指南

## 开始使用

```bash
cd resume-tailor
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
export ANTHROPIC_API_KEY="your-key-here"
```

## 命令

### `generate` — 创建定制简历

```bash
# 交互模式（提示输入简历 + JD）
python src/main.py generate

# 快速运行——跳过跟进问题
python src/main.py generate --skip-questions

# 跳过兼容性评估
python src/main.py generate --skip-assessment

# 选择输出格式
python src/main.py generate --format pdf
python src/main.py generate --format md
python src/main.py generate --format all

# 自定义输出路径
python src/main.py generate --output ~/Desktop/my_resume.docx

# 提供一份类似岗位的参考简历
python src/main.py generate --reference path/to/reference_resume.docx

# 从上次会话重新加载输入
python src/main.py generate --resume-session

# 无需消耗 API 额度进行测试
python src/main.py generate --dry-run

# 使用本地 Ollama 模型替代 Claude
python src/main.py generate --model ollama:qwen3.5
python src/main.py generate --model ollama:devstral
python src/main.py generate --model ollama:gemma3

# 组合参数
python src/main.py generate --resume-session --skip-questions --format pdf
```

### `review` — 评审和改进你的基础简历

```bash
python src/main.py review

# 使用本地 Ollama 模型评审
python src/main.py review --model ollama:qwen3.5
```

分析你保存的基础简历质量，提出改进建议，并可选择性地应用改进。

### `profile` — 管理你的档案

```bash
python src/main.py profile view      # 查看完整档案摘要
python src/main.py profile update    # 更新姓名、邮箱、电话等
python src/main.py profile edit      # 在编辑器中打开 profile.json
python src/main.py profile export    # 以 Markdown 格式打印档案
python src/main.py profile backup    # 创建带时间戳的备份
python src/main.py profile restore   # 从备份恢复
python src/main.py profile reset     # 删除档案并重新开始
```

### 全局参数

```bash
python src/main.py --verbose generate   # 启用调试日志（适用于所有命令）
python src/main.py --profile wife generate   # 使用指定档案
```

### 多档案支持

使用 `--profile <name>` 在同一台机器上为不同人管理独立的档案。每个档案有自己的简历、经验库、历史记录和偏好设置。

```bash
# 为你的妻子创建/使用档案
python src/main.py --profile wife generate
python src/main.py --profile wife profile view
python src/main.py --profile wife profile reset

# 默认档案（无需参数）
python src/main.py generate
```

档案存储在 `~/.resume-tailor/<profile_name>/profile.json`。

## 常见工作流程

### 首次设置

1. 运行 `python src/main.py generate`
2. 工具创建档案——输入你的姓名、邮箱等
3. 粘贴或提供基础简历的文件路径
4. 可选择提供一份参考简历
5. 工具评审你的简历并提出改进建议
6. 粘贴目标职位描述
7. 回答关于差距的跟进问题
8. 在 `output/` 目录获取你的定制简历

### 申请新职位

1. 运行 `python src/main.py generate`
2. 自动使用你的档案简历
3. 粘贴新的职位描述
4. 回答差距问题（之前保存的答案会提供复用选项）
5. 查看兼容性评分
6. 获取你的定制简历

### 复用会话

如果你想用相同的简历 + JD 重新生成（例如尝试不同的回答）：

```bash
python src/main.py generate --resume-session
```

工具会恢复你上次的简历文本、JD 和回答。你可以复用或重新输入。

### 评审你的基础简历

```bash
python src/main.py review
```

定期运行此命令以改进你的基础简历。工具会建议更好的要点并让你填入具体指标。改进内容会保存回你的档案。

### 管理你的档案

```bash
# 查看已保存的内容
python src/main.py profile view

# 更新联系信息
python src/main.py profile update

# 重新开始
python src/main.py profile reset
```

你的档案存储：身份信息、基础简历、经验库（差距问题的保存答案）、申请历史和输出偏好。

## CLI 参数参考

| 参数 | 命令 | 说明 |
|------|------|------|
| `--verbose` | （全局） | 启用调试日志 |
| `--profile` | （全局） | 档案名称（默认：`default`） |
| `--format` | `generate` | 输出格式：`docx`、`pdf`、`md` 或 `all` |
| `--output` | `generate` | 自定义输出文件或目录路径 |
| `--skip-questions` | `generate` | 跳过跟进问题 |
| `--skip-assessment` | `generate` | 跳过兼容性评估 |
| `--reference` | `generate` | 参考简历路径 |
| `--resume-session` | `generate` | 恢复上次会话的输入 |
| `--model` | `generate`、`review` | LLM 模型：`claude`（默认）或 `ollama:<name>` |
| `--dry-run` | `generate` | 使用模拟数据，不调用 API |

## 备份与数据安全

### 创建备份

```bash
python src/main.py profile backup
```

将你的 `profile.json` 复制为 `profile_backup_YYYY-MM-DD.json`，存储在相同的档案目录中（`~/.resume-tailor/<profile>/`）。在进行重大更改（如 `profile reset` 或应用 `review` 改进）之前运行此命令。

### 从备份恢复

```bash
python src/main.py profile restore
```

列出所有可用备份并让你选择一个进行恢复。所选备份会覆盖当前的 `profile.json`。

### 多档案备份

备份按档案区分。使用 `--profile` 备份或恢复特定档案：

```bash
python src/main.py --profile wife profile backup
python src/main.py --profile wife profile restore
```

### 最佳实践

- **重置前备份：** 在 `profile reset` 之前运行 `profile backup`，以便需要时恢复。
- **评审前备份：** `review` 命令可能修改你的基础简历。如果想比较版本，请先备份。
- **同一天的多次备份**会互相覆盖（相同日期 = 相同文件名）。如果需要同一天的多个快照，请手动重命名备份文件。

## 发布工作流程

项目使用语义化版本（`MAJOR.MINOR.PATCH`），版本号记录在 `VERSION` 文件中。发布操作会自动更新 VERSION 文件和 Helm `Chart.yaml`，创建提交并打标签。

### 升级版本号

```bash
make release-patch   # 1.2.1 -> 1.2.2（修复 bug）
make release-minor   # 1.2.2 -> 1.3.0（新功能）
make release-major   # 1.3.0 -> 2.0.0（破坏性变更）
```

### 推送发布

```bash
make release-push    # 推送提交和标签到 GitHub
```

### 完整发布示例

```bash
# 1. 确保所有测试通过
make test

# 2. 升级版本号
make release-patch

# 3. 推送到 GitHub
make release-push
```

### 发布过程中的操作

1. 从 `VERSION` 读取当前版本号
2. 升级相应的版本段（patch/minor/major）
3. 更新 `VERSION` 和 `helm/resume-tailor/Chart.yaml`
4. 以 `release: vX.Y.Z` 为消息提交
5. 创建 git 标签 `vX.Y.Z`

## REST API

启动 FastAPI 服务器：

```bash
make api
# 或: uvicorn src.web:app --reload --port 8000
```

API 文档：`http://localhost:8000/docs`（Swagger UI）或 `http://localhost:8000/redoc`。

### 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/analyze-jd` | 分析职位描述 |
| `POST` | `/api/v1/assess-compatibility` | 简历-JD 匹配评分（0-100%） |
| `POST` | `/api/v1/generate` | 生成定制简历（JSON 格式） |
| `POST` | `/api/v1/generate/pdf` | 生成并下载 PDF |
| `POST` | `/api/v1/review` | 用 AI 反馈评审简历 |
| `GET` | `/metrics` | Prometheus 指标 |

### 示例

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer...", "additional_context": "I also know Go"}'
```

## Makefile 目标

运行 `make help` 查看所有目标。主要目标：

| 目标 | 说明 |
|------|------|
| `make install` | 创建虚拟环境并安装依赖 |
| `make dev-install` | 安装运行时 + 开发依赖 |
| `make test` | 运行 pytest |
| `make lint` | 运行 ruff 代码检查 |
| `make format` | 运行 black 格式化 |
| `make run` | 运行 generate 命令 |
| `make run-profile PROFILE=name` | 使用指定档案运行 |
| `make dry-run` | 使用模拟数据运行（不调用 API） |
| `make run-local MODEL=ollama:qwen3.5` | 使用本地 Ollama 模型运行 |
| `make api` | 启动 FastAPI 服务器 |
| `make metrics` | 从运行中的 API 获取 Prometheus 指标 |
| `make docker-build` | 构建 Docker 镜像 |
| `make docker-run` | 运行 Docker 容器 |
| `make docker-ollama` | 同时运行 CLI + Ollama（完全容器化） |
| `make docker-ollama-api` | 同时启动 API 服务器 + Ollama |
| `make docker-ollama-pull MODEL=qwen3.5` | 向 Ollama 容器拉取模型 |
| `make helm-install` | 安装/升级 Helm chart |
| `make helm-uninstall` | 卸载 Helm chart |
| `make helm-template` | 本地渲染 Helm 模板 |
| `make argocd-setup` | 创建 Secret + 应用 ArgoCD 应用 |
| `make argocd-status` | 检查 ArgoCD 同步状态 |
| `make release-patch` | 升级补丁版本号、提交并打标签 |
| `make release-minor` | 升级次版本号、提交并打标签 |
| `make release-major` | 升级主版本号、提交并打标签 |
| `make release-push` | 推送提交和标签到 GitHub |
| `make clean` | 删除虚拟环境、pycache 和输出文件 |

## 故障排除

### API 密钥未设置

```
Error: ANTHROPIC_API_KEY environment variable is not set.
```

解决方法：`export ANTHROPIC_API_KEY="sk-ant-..."`（在 https://console.anthropic.com/settings/keys 获取密钥）

### API 密钥无效

```
Error: Invalid API key. Check your ANTHROPIC_API_KEY.
```

解决方法：在 https://console.anthropic.com/settings/keys 验证密钥。密钥以 `sk-ant-` 开头。

### API 连接错误

```
Error: Could not connect to the Anthropic API.
```

解决方法：检查网络连接和代理/防火墙设置。

### PDF 转换问题

PDF 输出需要系统安装 LibreOffice：

```bash
# Ubuntu/Debian
sudo apt install libreoffice

# macOS
brew install --cask libreoffice
```

如果 LibreOffice 不可用，使用 `--format docx` 并手动转换。

### 文件路径格式

- 使用正斜杠或转义反斜杠：`path/to/resume.docx`
- 支持的输入格式：`.txt`、`.docx`、`.pdf`
- 波浪号展开可用：`~/Documents/resume.docx`

### 档案问题

如果档案损坏：

```bash
python src/main.py profile reset
```

这会删除 `profile.json` 并让你在下次运行时重新开始。
