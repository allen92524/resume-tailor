[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

[English](README.md) | [中文](README_CN.md)

# Resume Tailor

**AI 驱动的 CLI 工具，为每次求职申请生成定制简历。**

粘贴你的简历和职位描述，Resume Tailor 会分析岗位要求、识别经验差距、评估匹配度，并生成 ATS 友好的简历——全程在终端中完成。

## 演示

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

Using profile resume for Jane Doe

--- Step 2: Reference Resume (Optional) ---
Do you have a reference resume? (file path or Enter to skip):

--- Step 4: Target Job Description ---
Provide the job description: paste content below, or enter a file path.
/mnt/c/Users/user/Desktop/sr_platform_eng_jd.txt

  Words:    287
  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]:

--- Step 5: JD Analysis ---
Sending job description to Claude for analysis...
Analysis complete. Role: Senior Platform Engineer
Key skills identified: Python, Go, Kubernetes, distributed systems, CI/CD

--- Step 6: Gap Analysis & Follow-Up Questions ---
Comparing your resume against the job requirements...

Your resume already matches well on:
  - Python backend development
  - Cloud infrastructure (AWS)
  - CI/CD pipeline experience

I have a few questions based on gaps between your resume and the JD.

  Do you have experience with Go or similar systems languages?
  → Built internal CLI tools in Go for deployment automation

  Have you worked with data streaming technologies (Kafka, Kinesis)?
  → Used Kafka for event-driven microservices at Acme Corp

--- Step 7: Compatibility Assessment ---
==================================================
  Compatibility Assessment
==================================================

  Match Score: [████████████████░░░░] 78%

  Strong Matches:
    + Python backend and API development
    + Kubernetes and containerization
    + Mentoring and technical leadership

  Addressable Gaps:
    ~ Go experience (has related systems programming)

Match score: 78%. Proceed with generation? [Y/n]:

--- Step 8: Generating Tailored Resume ---
Generating tailored resume content...
Resume content generated.

--- Step 9: Building PDF ---

Done! Your tailored resume has been saved to:
  /home/user/projects/resume-tailor/output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## 功能特性

- **档案系统** — 保存一次简历，每次申请复用
- **智能差距分析** — 识别缺失项并提出针对性的跟进问题
- **经验库** — 记住你的回答，避免重复输入
- **兼容性评分** — 0-100% 匹配评分，附详细分析，帮你决定是否继续
- **简历评审** — 独立命令，用 AI 反馈改进你的基础简历
- **多格式输出** — DOCX、PDF 和 Markdown
- **ATS 友好格式** — 简洁布局，无表格，正确的标题结构
- **多档案支持** — 在同一台机器上为不同人管理简历
- **会话恢复** — 使用 `--resume-session` 重新运行，尝试不同的回答
- **试运行模式** — 无需消耗 API 额度即可测试完整流程
- **本地 LLM 支持** — 使用本地 Ollama 模型替代 Claude API

## 快速开始

### Windows（推荐：Docker）

Docker 是在 Windows 上运行的最简单方式——它自动处理 Python、LibreOffice 和依赖项。

```powershell
# 1. 安装 Docker Desktop: https://docs.docker.com/desktop/install/windows/
# 2. 克隆仓库
git clone https://github.com/your-username/resume-tailor.git
cd resume-tailor

# 3. 使用 Docker 运行
docker build -t resume-tailor .
docker run -it -e ANTHROPIC_API_KEY="sk-ant-..." ^
  -v %USERPROFILE%\.resume-tailor:/root/.resume-tailor ^
  -v %cd%\output:/output ^
  resume-tailor generate --format pdf --output /output/
```

或使用本地模型，无需 API 密钥——参见下方 [Docker + Ollama](#docker--ollama完全容器化)。

### macOS（推荐：Docker 或原生安装）

```bash
# 方案 A：Docker（最简单）
brew install --cask docker
docker build -t resume-tailor .
docker compose run resume-tailor

# 方案 B：原生安装
git clone https://github.com/your-username/resume-tailor.git
cd resume-tailor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# PDF 输出需要 LibreOffice
brew install --cask libreoffice

export ANTHROPIC_API_KEY="sk-ant-..."
python src/main.py generate
```

### Linux

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/resume-tailor.git
cd resume-tailor

# 2. 安装
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 系统依赖（用于 PDF 输出）
sudo apt install libreoffice-writer -y    # Ubuntu/Debian
# sudo dnf install libreoffice-writer     # Fedora
# sudo pacman -S libreoffice-still        # Arch

# 4. 设置 API 密钥
export ANTHROPIC_API_KEY="sk-ant-..."

# 5. 运行
python src/main.py generate
```

首次运行时，工具会引导你创建档案——粘贴你的简历、评审改进，然后就可以开始了。

## Docker

```bash
# 构建镜像
docker build -t resume-tailor .

# 使用 Claude API 运行
docker run -it \
  -e ANTHROPIC_API_KEY="your-key" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v ~/Desktop:/output \
  resume-tailor generate --format pdf --output /output/

# 或使用 docker-compose（自动连接宿主机的 Ollama）
docker compose run resume-tailor

# 从 Docker 中使用本地 Ollama 模型（需要宿主机运行 Ollama）
docker compose run resume-tailor generate --model ollama:qwen3.5
```

### Docker + Ollama（完全容器化）

在 Docker 中运行所有组件——无需在本机安装 Ollama 或 Python。适用于所有平台（Windows、macOS、Linux）。

```bash
# 启动 Ollama 容器并拉取模型
docker compose -f docker-compose.full.yml up -d ollama
make docker-ollama-pull MODEL=qwen3.5

# 使用本地模型运行 CLI
make docker-ollama

# 或同时启动 API 服务器和 Ollama
make docker-ollama-api
```

## 本地 LLM（Ollama）

使用 [Ollama](https://ollama.com/) 完全在本地运行——无需 API 密钥。

```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh   # Linux
# brew install ollama                            # macOS
# 从 https://ollama.com/download 下载            # Windows

# 2. 启动 Ollama 并拉取模型
ollama serve
ollama pull qwen3.5

# 3. 使用本地模型运行
python src/main.py generate --model ollama:qwen3.5

# 或使用 Makefile 快捷方式
make run-local MODEL=ollama:qwen3.5
```

> **Windows/macOS：** 建议使用 `docker-compose.full.yml`——它将 Ollama 打包在容器中，无需单独安装。参见 [Docker + Ollama](#docker--ollama完全容器化)。

支持的模型（任何 Ollama 模型都可以）：

| 模型 | 参数 |
|------|------|
| Qwen 3.5 | `--model ollama:qwen3.5` |
| Devstral | `--model ollama:devstral` |
| Gemma 3 | `--model ollama:gemma3` |

`--model` 参数适用于 `generate` 和 `review` 命令，以及所有 REST API 端点（在请求体中传入 `"model": "ollama:qwen3.5"`）。

## Kubernetes 部署

使用内置的 Helm chart 将 API 部署到 Kubernetes。

### 前置条件

- [Helm](https://helm.sh/docs/intro/install/) v3+
- Kubernetes 集群（或用于本地开发的 [minikube](https://minikube.sigs.k8s.io/)）

### 使用 minikube 快速开始

```bash
# 构建 Docker 镜像并加载到 minikube
docker build -t resume-tailor:latest .
minikube image load resume-tailor:latest

# 安装 Helm chart
make helm-install
# 或: helm upgrade --install resume-tailor helm/resume-tailor --set apiKey=$ANTHROPIC_API_KEY

# 端口转发以访问 API
kubectl port-forward svc/resume-tailor 8000:8000
curl http://localhost:8000/api/v1/health
```

### Helm 命令

```bash
make helm-install    # 安装或升级发布
make helm-uninstall  # 移除发布
make helm-template   # 本地渲染模板（干运行）
```

### 配置

在 `helm/resume-tailor/values.yaml` 中覆盖默认值，或传入 `--set` 参数：

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set replicaCount=3 \
  --set ingress.enabled=true \
  --set ingress.host=resume-tailor.example.com
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `replicaCount` | `1` | Pod 副本数 |
| `image.repository` | `resume-tailor` | Docker 镜像仓库 |
| `image.tag` | `latest` | Docker 镜像标签 |
| `service.port` | `8000` | 服务端口 |
| `ingress.enabled` | `false` | 启用 Ingress 资源 |
| `ingress.host` | `resume-tailor.local` | Ingress 主机名 |
| `apiKey` | `""` | Anthropic API 密钥（存储为 Secret） |
| `resources.limits.cpu` | `500m` | CPU 限制 |
| `resources.limits.memory` | `512Mi` | 内存限制 |

## ArgoCD GitOps 部署

使用 ArgoCD 自动化部署——任何推送到 `main` 分支且修改了 Helm chart 的提交都会自动部署到集群。

### 设置

```bash
# 1. 创建 API 密钥 Secret
kubectl create secret generic resume-tailor-api-key \
  --from-literal=api-key=$ANTHROPIC_API_KEY

# 2. 应用 ArgoCD 应用
kubectl apply -f argocd/application.yaml

# 或使用 Makefile 快捷方式
make argocd-setup
```

### 工作原理

- ArgoCD 监视仓库中 `helm/resume-tailor` 在 `main` 分支上的变更
- 启用**自动同步**，支持自愈和清理
- 集群中的手动修改会被自动回滚

```bash
make argocd-status   # 检查同步状态
```

详见 [argocd/README.md](argocd/README.md)。

## 可观测性

API 内置 OpenTelemetry 追踪和 Prometheus 指标。

### Prometheus 指标

`/metrics` 端点以 Prometheus 格式暴露指标：

```bash
# 启动 API
make api

# 查看原始指标
make metrics
# 或: curl http://localhost:8000/metrics
```

可用指标：

| 指标 | 类型 | 说明 |
|------|------|------|
| `http_requests_total` | Counter | 按方法、端点、状态码统计的总请求数 |
| `http_request_duration_seconds` | Histogram | 按方法和端点统计的请求延迟 |
| `http_active_requests` | Gauge | 当前进行中的请求数 |
| `claude_api_calls_total` | Counter | 按模型和状态统计的 Claude API 调用数 |
| `claude_api_call_duration_seconds` | Histogram | 按模型统计的 Claude API 调用延迟 |
| `resume_generations_total` | Counter | 成功生成简历的总数 |

### OpenTelemetry 追踪

默认将追踪导出到控制台。如需发送到 OTLP 收集器：

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
make api
```

### Grafana 仪表盘

预构建的仪表盘位于 `grafana/resume-tailor-dashboard.json`。可手动导入 Grafana 或通过 Helm 部署（见下文）。

面板包括：请求速率、响应时间（P50/P95/P99）、错误率、Claude API 延迟、活跃请求数、简历生成数。

### Kubernetes 监控

在 Helm 中启用 Prometheus ServiceMonitor 和 Grafana 仪表盘自动导入：

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set metrics.serviceMonitor.enabled=true \
  --set metrics.grafanaDashboard.enabled=true
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `metrics.serviceMonitor.enabled` | `false` | 为 Prometheus Operator 创建 ServiceMonitor |
| `metrics.serviceMonitor.interval` | `30s` | 抓取间隔 |
| `metrics.grafanaDashboard.enabled` | `false` | 为 Grafana sidecar 自动导入创建 ConfigMap |

## 工作原理

```
你的简历 + 职位描述
         │
         ▼
   ┌─────────────┐
   │  JD 分析     │ ← 提取技能、关键词、公司背景
   └──────┬──────┘
          ▼
   ┌──────────────┐
   │  差距分析     │ ← 找出缺失项，提出跟进问题
   └──────┬───────┘
          ▼
   ┌───────────────────┐
   │  兼容性评分        │ ← 0-100% 匹配度，附是否继续的建议
   └───────┬───────────┘
           ▼
   ┌──────────────────┐
   │  简历生成         │ ← 使用你的回答生成定制内容
   └───────┬──────────┘
           ▼
   DOCX / PDF / Markdown
```

## 命令

| 命令 | 说明 |
|------|------|
| `generate` | 完整流程——分析 JD、评分匹配度、生成定制简历 |
| `review` | 用 AI 建议评审和改进你的基础简历 |
| `profile view` | 查看档案摘要 |
| `profile update` | 更新姓名、邮箱、电话等 |
| `profile edit` | 在编辑器中打开 profile.json |
| `profile export` | 以 Markdown 格式打印档案 |
| `profile backup` | 创建带时间戳的备份 |
| `profile restore` | 从备份恢复 |
| `profile reset` | 删除档案并重新开始 |

常用参数：`--format pdf`、`--skip-questions`、`--skip-assessment`、`--resume-session`、`--dry-run`、`--model ollama:qwen3.5`、`--profile <name>`、`--verbose`

完整参考请见 [USAGE_CN.md](USAGE_CN.md)。

## REST API

Resume Tailor 还提供 FastAPI REST API 用于程序化访问。

### 启动服务器

```bash
make api
# 或: uvicorn src.web:app --reload --port 8000
```

API 文档位于 `http://localhost:8000/docs`（Swagger UI）和 `http://localhost:8000/redoc`。

### 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查——返回状态和 API 密钥存在情况 |
| `POST` | `/api/v1/analyze-jd` | 分析职位描述，返回结构化的技能/关键词/职责 |
| `POST` | `/api/v1/assess-compatibility` | 简历-JD 匹配评分（0-100%），附详细分析 |
| `POST` | `/api/v1/generate` | 生成定制简历（JSON 格式） |
| `POST` | `/api/v1/generate/pdf` | 生成定制简历并下载为 PDF |
| `POST` | `/api/v1/review` | 评审简历——评分、优势、不足、改进建议 |

### 请求示例

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 分析职位描述
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for a Senior Python Developer..."}'

# 评估兼容性
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

## 项目结构

```
resume-tailor/
├── src/
│   ├── main.py                # CLI 入口（click 命令）
│   ├── web.py                 # FastAPI REST API 入口
│   ├── api.py                 # Claude API 调用辅助（含重试逻辑）
│   ├── llm_client.py          # 统一 LLM 客户端（Claude + Ollama）
│   ├── telemetry.py           # OpenTelemetry 追踪 & Prometheus 指标
│   ├── config.py              # 集中配置
│   ├── models.py              # 数据模型（dataclasses）
│   ├── profile.py             # 档案管理（~/.resume-tailor/）
│   ├── session.py             # 会话保存/恢复
│   ├── resume_parser.py       # 解析简历（text/docx/pdf）
│   ├── jd_analyzer.py         # 分析职位描述
│   ├── gap_analyzer.py        # 比较简历与 JD 要求
│   ├── compatibility_assessor.py  # 简历-JD 匹配评分
│   ├── resume_generator.py    # 生成定制简历内容
│   ├── resume_reviewer.py     # 评审和改进基础简历
│   ├── docx_builder.py        # 构建 DOCX/PDF/Markdown 输出
│   ├── prompts.py             # 提示词模板加载器
│   └── prompts/               # 提示词模板（Markdown 文件）
├── helm/resume-tailor/        # Kubernetes Helm chart
├── argocd/                    # ArgoCD GitOps 部署
├── grafana/                   # 独立 Grafana 仪表盘
├── scripts/                   # 版本发布脚本
├── tests/                     # 测试套件（含 fixtures）
└── VERSION                    # 语义化版本文件
```

## 贡献

```bash
# 安装开发依赖
make dev-install

# 运行测试
make test

# 运行代码检查
make lint

# 格式化代码
make format

# 运行工具
make run
```

### 所有 Makefile 目标

| 目标 | 说明 |
|------|------|
| `make install` | 创建虚拟环境并安装运行时依赖 |
| `make dev-install` | 安装运行时 + 开发依赖 |
| `make test` | 运行 pytest |
| `make lint` | 运行 ruff 代码检查 |
| `make format` | 运行 black 格式化 |
| `make run` | 运行 generate 命令 |
| `make run-profile PROFILE=name` | 使用指定档案运行 generate |
| `make dry-run` | 使用模拟数据运行（不调用 API） |
| `make run-local MODEL=ollama:qwen3.5` | 使用本地 Ollama 模型运行 |
| `make api` | 在 8000 端口启动 FastAPI 服务器 |
| `make metrics` | 从运行中的 API 获取原始 Prometheus 指标 |
| `make docker-build` | 构建 Docker 镜像 |
| `make docker-run` | 以交互模式运行 Docker 容器 |
| `make docker-ollama` | 同时运行 CLI + Ollama（无需 API 密钥） |
| `make docker-ollama-api` | 同时启动 API 服务器 + Ollama |
| `make docker-ollama-pull MODEL=qwen3.5` | 向 Ollama 容器拉取模型 |
| `make helm-install` | 安装/升级 Helm chart 到 Kubernetes |
| `make helm-uninstall` | 卸载 Helm chart |
| `make helm-template` | 本地渲染 Helm 模板（干运行） |
| `make argocd-setup` | 创建 API 密钥 Secret 并应用 ArgoCD 应用 |
| `make argocd-status` | 检查 ArgoCD 同步状态 |
| `make release-patch` | 升级补丁版本号、提交并打标签 |
| `make release-minor` | 升级次版本号、提交并打标签 |
| `make release-major` | 升级主版本号、提交并打标签 |
| `make release-push` | 推送提交和标签到 GitHub |
| `make clean` | 删除虚拟环境、pycache 和输出文件 |

## 许可证

MIT
