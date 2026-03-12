[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

[English](README.md) | [中文](README_CN.md)

# Resume Tailor

**5 分钟内把任何职位招聘信息变成一份量身定制的简历。**

你有一份简历，但每个职位都不同。Resume Tailor 读取职位描述，分析岗位需求，问你几个问题，然后生成一份精美的简历——支持 DOCX、PDF 或 Markdown 格式。

## 你需要准备什么

- **Docker**（[点这里下载](https://www.docker.com/products/docker-desktop/)）— 推荐，无需安装其他东西
- **AI 后端**（二选一）：
  - **Claude API**（质量最好，每份简历约 ¥0.07-0.35）— [获取 API 密钥](https://console.anthropic.com/settings/keys)
  - **Ollama**（完全免费，在你电脑上本地运行）— [点这里安装](https://ollama.com/download)

## 快速开始（Docker — 最简单）

Docker 包含一切：Python、所有依赖和 PDF 支持。无需安装其他东西。

### 1. 下载

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
```

### 2. 选择你的 AI 并运行

**方案 A：Claude API**（质量最好，每份简历约 ¥0.20）

到 https://console.anthropic.com/settings/keys 获取 API 密钥（以 `sk-ant-` 开头），然后：

```bash
export ANTHROPIC_API_KEY="sk-ant-你的密钥"
docker compose run --rm resume-tailor
```

**方案 B：Ollama**（完全免费）

从 https://ollama.com/download 安装 Ollama，然后：

```bash
ollama pull gemma3

# macOS / Windows / WSL2（Docker Desktop）
docker compose run --rm resume-tailor generate --model ollama:gemma3

# Linux（原生 Docker）
make docker-ollama MODEL=ollama:gemma3
```

> Docker 容器会连接到你电脑上运行的 Ollama。LLM 模型不会存储在容器中。

就这样！工具会一步步引导你完成。PDF 输出开箱即用。

<details>
<summary>替代方案：本地安装（不使用 Docker）</summary>

如果你不想用 Docker，可以直接安装。需要 Python 3.12+。

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-你的密钥"   # 如果使用 Claude
python src/main.py generate
```

> 本地安装的 PDF 输出需要 LibreOffice：`sudo apt install libreoffice-writer`（Linux）或 `brew install --cask libreoffice`（macOS）。或者直接用 `--format docx`。

</details>

---

## 运行时是什么样的

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

--- Step 1: Your Resume ---
Paste your resume below (or enter a file path like ~/Downloads/resume.pdf).
Type END on its own line when done.

--- Step 4: Target Job Description ---
Paste the job description (or enter a file path).

  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]: y

--- Step 6: Gap Analysis ---
Your resume already matches well on:
  + Python backend development
  + Cloud infrastructure (AWS)

I have a few questions to strengthen your resume:
  Do you have experience with Go?
  → Built internal CLI tools in Go for deployment automation

--- Step 7: Compatibility Score ---
  Match Score: [████████████████░░░░] 78%

Proceed with generation? [Y/n]: y

--- Step 8: Generating Tailored Resume ---
Done! Your tailored resume has been saved to:
  output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## 功能特性

- **只需回答问题** — AI 负责写作，你只需提供事实
- **一次保存，处处复用** — 保存一次简历，之后每次申请都能直接用
- **智能提问** — 只针对你的简历与职位描述之间的差距提问
- **匹配评分** — 生成前查看 0-100% 的兼容性评分
- **经验库** — 记住你的回答，同样的问题不用重复输入
- **简历评审** — 获取 AI 反馈来改进你的基础简历
- **多格式输出** — DOCX、PDF 或 Markdown
- **ATS 友好** — 简洁的格式，能通过自动化简历筛选系统
- **多档案支持** — 在同一台电脑上为不同人管理简历
- **隐私优先** — 你的数据留在你的电脑上，不会被上传

## 常用操作

### 申请新工作

```bash
python src/main.py generate
```

### 获取简历评审和改进建议

```bash
python src/main.py review
```

### 输出为 PDF

```bash
# Docker（PDF 开箱即用）
docker compose run --rm resume-tailor generate --format pdf --output /output/

# 本地安装（需要 LibreOffice）
python src/main.py generate --format pdf
```

> 仅本地安装：PDF 需要 LibreOffice。安装方法：`sudo apt install libreoffice-writer`（Linux）或 `brew install --cask libreoffice`（macOS）。Docker 已自动包含。

### 管理你的档案

```bash
# 查看已保存的信息
python src/main.py profile view

# 编辑已保存的简历
python src/main.py profile edit

# 完全重新开始
python src/main.py profile reset
```

### 为别人管理简历

```bash
python src/main.py --profile wife generate
python src/main.py --profile wife profile view
```

### 选择特定的 Claude 模型

```bash
# 使用最强大的模型
python src/main.py generate --model claude:opus

# 使用最快最便宜的模型
python src/main.py generate --model claude:haiku
```

交互式运行时（不带 `--model` 参数），选择 Claude 后会让你在 Haiku、Sonnet 和 Opus 之间选择。

### 用不同的回答重新生成

```bash
python src/main.py generate --resume-session
```

### 跳过问题直接生成

```bash
python src/main.py generate --skip-questions --skip-assessment
```

### 不使用 AI 测试完整流程

```bash
python src/main.py generate --dry-run
```

完整参考请见 [USAGE_CN.md](USAGE_CN.md)，包含所有参数、工作流程和故障排除。

## 开发者

<details>
<summary>Docker、REST API、Kubernetes 等</summary>

### Docker 详情

Docker Compose 是最简单的运行方式（见上方快速开始）。手动 `docker run`：

```bash
docker build -t resume-tailor .

# Claude API
docker run -it --rm \
  -e ANTHROPIC_API_KEY="sk-ant-你的密钥" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/

# Ollama（macOS / Windows / WSL2 — Docker Desktop）
docker run -it --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --model ollama:gemma3 --format pdf --output /output/

# Ollama（Linux — 原生 Docker，使用 host 网络模式）
docker run -it --rm \
  --network host \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --model ollama:gemma3 --format pdf --output /output/
```

> LLM 模型不会存储在容器中。Docker 镜像连接到你主机上运行的 Ollama。生成的文件会自动设置为你的用户权限（不是 root）。

### REST API

```bash
make api    # 启动服务器 http://localhost:8000
```

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/analyze-jd` | 分析职位描述 |
| `POST` | `/api/v1/assess-compatibility` | 简历与职位匹配评分（0-100%） |
| `POST` | `/api/v1/generate` | 生成定制简历（JSON） |
| `POST` | `/api/v1/generate/pdf` | 生成并下载 PDF |
| `POST` | `/api/v1/review` | AI 反馈评审简历 |

API 文档：http://localhost:8000/docs

### Kubernetes（Helm）

```bash
make helm-install
kubectl port-forward svc/resume-tailor 8000:8000
```

详见 [USAGE_CN.md](USAGE_CN.md) 中的 Helm 配置、ArgoCD 部署和监控说明。

### 参与开发

```bash
make dev-install   # 安装开发依赖
make test          # 运行测试
make lint          # 运行代码检查
make format        # 格式化代码
make check-secrets # 检查是否误提交了个人信息
```

</details>

## 隐私

- **档案** 保存在本地 `~/.resume-tailor/`，不会离开你的电脑。
- **生成的简历** 保存到 `output/` 文件夹，不会上传。
- **Claude API** 会将你的简历和职位描述发送给 Anthropic 处理。如果你使用 **Ollama**，所有数据都在你的电脑上。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
