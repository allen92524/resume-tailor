[English](USAGE.md) | [中文](USAGE_CN.md)

# Resume Tailor - 完整使用指南

Resume Tailor 的所有功能，按你想做的事情分类。

## 目录

- [我想申请一个新职位](#我想申请一个新职位)
- [我想帮别人设置档案](#我想帮别人设置档案)
- [我想改进我的基础简历](#我想改进我的基础简历)
- [我想用不同的回答重新生成同一个职位的简历](#我想用不同的回答重新生成同一个职位的简历)
- [我想用免费的本地模型替代 Claude](#我想用免费的本地模型替代-claude)
- [我想在 Docker 里运行](#我想在-docker-里运行)
- [我想使用 REST API](#我想使用-rest-api)
- [我想部署到 Kubernetes](#我想部署到-kubernetes)
- [我想设置监控](#我想设置监控)
- [我想备份我的数据](#我想备份我的数据)
- [我想发布新版本](#我想发布新版本)
- [所有参数参考](#所有参数参考)
- [所有 Makefile 目标](#所有-makefile-目标)
- [故障排除](#故障排除)

---

## 我想申请一个新职位

### 第一次使用（还没有档案）

```bash
python src/main.py generate
```

工具会引导你完成所有步骤：

1. 创建档案——输入你的姓名、邮箱、电话
2. 粘贴你的简历（或输入 `.txt`、`.docx`、`.pdf` 文件路径）
3. 可选择提供一份类似岗位的参考简历
4. AI 评审你的简历并提出改进建议
5. 粘贴职位描述（或输入文件路径）
6. 回答几个关于你的简历与职位之间差距的问题
7. 查看兼容性评分（0-100%）
8. 在 `output/` 文件夹中获取定制简历

### 第二次及以后（已有档案）

```bash
python src/main.py generate
```

同样的命令。工具会记住你上次的简历和联系方式。只需粘贴新的职位描述并回答差距问题。如果你之前回答过类似的问题，工具会提供复用选项。

### 我想输出 PDF

```bash
python src/main.py generate --format pdf
```

需要系统安装 LibreOffice。如果没有安装：

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice
```

或者用 `--format docx` 然后手动转换。

### 我想跳过问题直接生成

```bash
python src/main.py generate --skip-questions
```

跳过差距分析问题。AI 会尽力根据你简历中的内容生成。

### 我想跳过兼容性评分

```bash
python src/main.py generate --skip-assessment
```

### 我想把输出保存到指定位置

```bash
# 保存到指定文件夹
python src/main.py generate --output ~/Desktop/

# 保存为指定文件名
python src/main.py generate --output ~/Desktop/my_resume.docx
```

### 我想提供一份参考简历

如果你有一份在你想申请的岗位上工作的人的简历：

```bash
python src/main.py generate --reference path/to/their_resume.docx
```

AI 会参考它来理解公司看重什么——语调、关键词、结构。

### 我想选择特定的 Claude 模型

交互式选择 Claude 时，会看到一个子菜单选择变体：

| 模型 | 适用场景 | 费用 |
|------|---------|------|
| Haiku | 快速草稿、测试 | 最便宜 |
| Sonnet | 日常使用（默认） | 适中 |
| Opus | 最佳质量、复杂岗位 | 最贵 |

或者通过 `--model` 直接指定：

```bash
python src/main.py generate --model claude:opus
python src/main.py generate --model claude:haiku
python src/main.py review --model claude:sonnet
```

你的选择会保存到档案中，下次自动作为默认值。

### 我已经准备好所有答案，想快速生成

```bash
python src/main.py generate --skip-questions --skip-assessment --format pdf
```

---

## 我想帮别人设置档案

使用 `--profile` 参数创建独立档案。每个档案有自己的简历、经验库和历史记录。

```bash
# 帮妻子设置
python src/main.py --profile wife generate

# 帮朋友设置
python src/main.py --profile alex generate
```

每个人的数据单独存储在 `~/.resume-tailor/<name>/profile.json`。

### 管理别人的档案

```bash
# 查看档案
python src/main.py --profile wife profile view

# 更新联系方式
python src/main.py --profile wife profile update

# 在编辑器中打开 profile.json
python src/main.py --profile wife profile edit

# 导出档案为 Markdown
python src/main.py --profile wife profile export

# 将简历恢复到原始版本（撤销所有改进）
python src/main.py --profile wife profile reset-baseline

# 备份档案
python src/main.py --profile wife profile backup

# 从备份恢复
python src/main.py --profile wife profile restore

# 重置，重新开始（删除所有数据）
python src/main.py --profile wife profile reset
```

---

## 我想改进我的基础简历

`review` 命令会分析你保存的简历并提出改进建议——更好的要点描述、缺失的关键词、以及整体质量评分。

```bash
python src/main.py review
```

工具会：
1. 显示质量评分（0-100）
2. 列出优势和不足
3. 建议改进的要点描述
4. 询问是否应用改进
5. 如果是，让你填入占位指标（例如 "将性能提升了 [X%]"）
6. 把改进后的简历保存回你的档案

### 用本地模型评审

```bash
python src/main.py review --model ollama:qwen3.5
```

---

## 我想用不同的回答重新生成同一个职位的简历

使用 `--resume-session` 重新加载上次运行的输入：

```bash
python src/main.py generate --resume-session
```

工具会恢复你的简历文本、职位描述和之前的回答。你可以保留任何一个或重新输入。适用于：

- 想强调不同的经历
- 想修改差距问题的回答
- 想生成不同格式（加上 `--format pdf`）

---

## 我想用免费的本地模型替代 Claude

[Ollama](https://ollama.com/) 让你在自己的电脑上免费运行 AI 模型。

### 安装 Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Windows — 从 https://ollama.com/download 下载
```

### 下载模型并运行

```bash
ollama pull qwen3.5
python src/main.py generate --model ollama:qwen3.5
```

无需 API 密钥。`--model` 参数在 `generate` 和 `review` 中都可以使用：

```bash
python src/main.py review --model ollama:qwen3.5
```

### 可用模型

任何 Ollama 模型都可以。一些好的选择：

| 模型 | 命令 | 备注 |
|------|------|------|
| Qwen 3.5 | `--model ollama:qwen3.5` | 综合表现好，推荐 |
| Devstral | `--model ollama:devstral` | 技术类简历表现强 |
| Gemma 3 | `--model ollama:gemma3` | 轻量，更快 |

### 不用任何 AI 测试

```bash
python src/main.py generate --dry-run
```

使用模拟数据，可以测试完整流程，不消耗额度也不需要模型。

---

## 我想在 Docker 里运行

Docker 是运行 Resume Tailor 最简单的方式——包含 Python、所有依赖和 LibreOffice PDF 输出。除了 Docker 本身，无需安装任何东西。

### Docker + Claude API

```bash
export ANTHROPIC_API_KEY="sk-ant-你的密钥"
docker compose run --rm resume-tailor
```

### Docker + Ollama（免费）

Docker 容器会连接到你电脑上运行的 Ollama——LLM 模型不会存储在容器中。

1. 在你的电脑上安装并启动 Ollama：https://ollama.com/download
2. 下载模型：`ollama pull qwen3.5`
3. 运行：

```bash
docker compose run --rm resume-tailor generate --model ollama:qwen3.5
```

### 手动 docker run（不使用 Compose）

```bash
docker build -t resume-tailor .

# Claude API
docker run -it --rm \
  -e ANTHROPIC_API_KEY="sk-ant-你的密钥" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/

# Ollama（连接到主机）
docker run -it --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  --add-host=host.docker.internal:host-gateway \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --model ollama:qwen3.5 --format pdf --output /output/
```

---

## 我想使用 REST API

Resume Tailor 有一个 Web API，支持程序化访问。

### 启动服务器

```bash
make api
```

API 文档：http://localhost:8000/docs（交互式 Swagger UI）。

### 端点

| 方法 | 端点 | 作用 |
|------|------|------|
| `GET` | `/api/v1/health` | 检查服务器是否运行 |
| `POST` | `/api/v1/analyze-jd` | 分析职位描述 |
| `POST` | `/api/v1/assess-compatibility` | 简历与职位匹配评分（0-100%） |
| `POST` | `/api/v1/generate` | 生成定制简历（返回 JSON） |
| `POST` | `/api/v1/generate/pdf` | 生成并下载 PDF 文件 |
| `POST` | `/api/v1/review` | 评审简历并获取改进建议 |
| `GET` | `/metrics` | Prometheus 指标 |

### 示例

```bash
# 检查服务器状态
curl http://localhost:8000/api/v1/health

# 分析职位描述
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for a Senior Python Developer..."}'

# 评估简历与职位的兼容性
curl -X POST http://localhost:8000/api/v1/assess-compatibility \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}'

# 生成定制简历
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer...", "additional_context": "I also know Go"}'

# 生成并下载 PDF
curl -X POST http://localhost:8000/api/v1/generate/pdf \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}' \
  -o resume.pdf

# 评审简历
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe, Software Engineer..."}'
```

### 在 API 中使用 Ollama

在任何请求体中传入 `"model": "ollama:qwen3.5"`：

```bash
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for...", "model": "ollama:qwen3.5"}'
```

---

## 我想部署到 Kubernetes

项目包含一个 Helm chart，用于 Kubernetes 部署。

### 你需要什么

- 已安装 [Docker](https://docs.docker.com/get-docker/)
- 已安装 [Helm](https://helm.sh/docs/intro/install/) v3+
- 一个 Kubernetes 集群（或用 [minikube](https://minikube.sigs.k8s.io/) 本地测试）

### 用 minikube 部署（本地测试）

```bash
# 构建镜像并加载到 minikube
docker build -t resume-tailor:latest .
minikube image load resume-tailor:latest

# 部署
make helm-install

# 访问 API
kubectl port-forward svc/resume-tailor 8000:8000
curl http://localhost:8000/api/v1/health
```

### 部署到正式集群

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set image.repository=your-registry/resume-tailor \
  --set image.tag=latest
```

### 配置选项

| 设置项 | 默认值 | 作用 |
|--------|--------|------|
| `replicaCount` | `1` | 运行的实例数 |
| `image.repository` | `resume-tailor` | 使用的 Docker 镜像 |
| `image.tag` | `latest` | 镜像版本 |
| `service.port` | `8000` | 服务监听端口 |
| `ingress.enabled` | `false` | 通过 Ingress 暴露（用于公网访问） |
| `ingress.host` | `resume-tailor.local` | Ingress 域名 |
| `apiKey` | `""` | 你的 Anthropic API 密钥 |
| `resources.limits.cpu` | `500m` | 每个实例最大 CPU |
| `resources.limits.memory` | `512Mi` | 每个实例最大内存 |

### 使用 ArgoCD 自动部署

ArgoCD 可以在你推送到 `main` 分支时自动部署：

```bash
# 一次性设置
make argocd-setup

# 检查状态
make argocd-status
```

工作原理：ArgoCD 监视你仓库中的 `helm/resume-tailor`。当你向 `main` 推送变更时，它自动同步到你的集群。集群上的手动修改会被自动回滚。

详见 [argocd/README.md](argocd/README.md)。

### 移除部署

```bash
make helm-uninstall
```

---

## 我想设置监控

API 内置了监控指标。

### 查看指标

```bash
# 启动 API
make api

# 查看原始指标
curl http://localhost:8000/metrics
```

### 可用指标

| 指标 | 追踪内容 |
|------|---------|
| `http_requests_total` | 总请求数（按端点和状态码） |
| `http_request_duration_seconds` | 请求耗时 |
| `http_active_requests` | 当前进行中的请求 |
| `claude_api_calls_total` | AI API 调用次数（按模型和成功/失败） |
| `claude_api_call_duration_seconds` | AI 调用耗时 |
| `resume_generations_total` | 已生成的简历总数 |

### Grafana 仪表盘

将 `grafana/resume-tailor-dashboard.json` 导入 Grafana，可获得预构建的仪表盘：
- 请求速率和错误率
- 响应时间（P50/P95/P99）
- AI API 延迟
- 活跃请求数和简历生成数

### Kubernetes 监控

在 Helm 中启用自动指标收集和 Grafana 仪表盘：

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set metrics.serviceMonitor.enabled=true \
  --set metrics.grafanaDashboard.enabled=true
```

### 发送追踪数据到收集器

默认情况下追踪数据输出到控制台。要发送到 OpenTelemetry 收集器：

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
make api
```

---

## 我想备份我的数据

### 创建备份

```bash
python src/main.py profile backup
```

将你的档案保存为 `profile_backup_YYYY-MM-DD.json`，存储在 `~/.resume-tailor/<profile>/`。

### 从备份恢复

```bash
python src/main.py profile restore
```

显示所有可用备份并让你选择。

### 备份特定档案

```bash
python src/main.py --profile wife profile backup
python src/main.py --profile wife profile restore
```

### 建议

- **重置前一定要备份** —— 在 `profile reset` 之前先运行 `profile backup`
- **评审前也要备份** —— `review` 命令可能会修改你的简历
- 同一天的多次备份会互相覆盖（同一日期 = 同一文件名）

---

## 我想发布新版本

项目使用语义化版本（例如 `1.5.0`），版本号记录在 `VERSION` 文件中。

### 升级并发布

```bash
# 1. 确保测试通过
make test

# 2. 升级版本号（选一个）
make release-patch   # 1.5.0 → 1.5.1（修复 bug）
make release-minor   # 1.5.0 → 1.6.0（新功能）
make release-major   # 1.5.0 → 2.0.0（破坏性变更）

# 3. 推送到 GitHub
make release-push
```

这会自动更新 `VERSION`、Helm chart 版本，创建 git 提交并打标签。

---

## 所有参数参考

| 参数 | 适用命令 | 作用 | 默认值 |
|------|---------|------|--------|
| `--verbose` | 任意命令 | 显示详细调试日志 | 关闭 |
| `--profile <name>` | 任意命令 | 使用指定名称的档案 | `default` |
| `--format <type>` | `generate` | 输出格式：`docx`、`pdf`、`md`、`all` | `docx` |
| `--output <path>` | `generate` | 自定义输出目录或文件路径 | `output/` |
| `--skip-questions` | `generate` | 跳过差距分析的跟进问题 | 关闭 |
| `--skip-assessment` | `generate` | 跳过兼容性评分 | 关闭 |
| `--reference <file>` | `generate` | 参考简历的路径 | 无 |
| `--resume-session` | `generate` | 恢复上次会话的输入 | 关闭 |
| `--model <name>` | `generate`、`review` | AI 模型：`claude`、`claude:haiku`、`claude:sonnet`、`claude:opus` 或 `ollama:<name>` | `claude`（Sonnet） |
| `--dry-run` | `generate` | 使用模拟数据，不调用 AI | 关闭 |

---

## 所有 Makefile 目标

在终端运行 `make help` 查看完整列表。

| 目标 | 作用 |
|------|------|
| `make install` | 创建虚拟环境并安装依赖 |
| `make dev-install` | 安装运行时 + 开发依赖 |
| `make test` | 运行测试套件 |
| `make lint` | 检查代码风格问题 |
| `make format` | 自动格式化代码 |
| `make run` | 运行 generate 命令 |
| `make run-local MODEL=ollama:qwen3.5` | 使用本地 Ollama 模型运行 |
| `make run-profile PROFILE=name` | 使用指定档案运行 |
| `make dry-run` | 用模拟数据测试完整流程 |
| `make api` | 在 8000 端口启动 REST API 服务器 |
| `make metrics` | 从运行中的 API 获取指标 |
| `make docker-build` | 构建 Docker 镜像 |
| `make docker-run` | 运行 Docker 容器（Claude API） |
| `make docker-ollama MODEL=ollama:qwen3.5` | 使用本地 Ollama 运行 Docker |
| `make test-docker` | 构建并测试 Docker 镜像 |
| `make helm-install` | 通过 Helm 部署到 Kubernetes |
| `make helm-uninstall` | 移除 Kubernetes 部署 |
| `make helm-template` | 预览 Helm 模板（不实际部署） |
| `make argocd-setup` | 设置 ArgoCD 自动部署 |
| `make argocd-status` | 检查 ArgoCD 部署状态 |
| `make release-patch` | 升级补丁版本（1.5.0 → 1.5.1） |
| `make release-minor` | 升级次版本（1.5.0 → 1.6.0） |
| `make release-major` | 升级主版本（1.5.0 → 2.0.0） |
| `make release-push` | 推送发布提交和标签到 GitHub |
| `make clean` | 删除虚拟环境、缓存和输出文件 |

---

## 故障排除

### "ANTHROPIC_API_KEY environment variable is not set"

你需要在运行前设置 API 密钥：

```bash
export ANTHROPIC_API_KEY="sk-ant-你的密钥"
```

在 https://console.anthropic.com/settings/keys 获取密钥。如果你不想付费，可以用本地模型：

```bash
python src/main.py generate --model ollama:qwen3.5
```

### "Invalid API key"

密钥可能过期或输入错误。在 https://console.anthropic.com/settings/keys 检查。密钥应该以 `sk-ant-` 开头。

### "Could not connect to the Anthropic API"

检查你的网络连接。如果你在公司防火墙或 VPN 后面，可能会阻止连接。

### PDF 输出不工作

PDF 转换需要 LibreOffice：

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice
```

如果无法安装，用 DOCX 替代：

```bash
python src/main.py generate --format docx
```

### Ollama 连接被拒绝

确保 Ollama 正在运行：

```bash
# 检查 Ollama 是否在运行
curl http://localhost:11434/api/tags

# 如果没有运行，启动它
ollama serve
```

### 档案损坏了

重置并重新开始：

```bash
# 先备份（如果可能的话）
python src/main.py profile backup

# 然后重置
python src/main.py profile reset
```

### 找不到文件路径

- 使用正斜杠：`path/to/resume.docx`
- 支持波浪号：`~/Documents/resume.docx`
- 在 Windows/WSL 上可以使用 Windows 路径：`/mnt/c/Users/你的用户名/Desktop/resume.docx`
- 支持的输入格式：`.txt`、`.docx`、`.pdf`

### 我想完全重新开始

```bash
# 删除档案
python src/main.py profile reset

# 删除所有生成的输出
rm -rf output/*
```
