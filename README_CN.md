[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

[English](README.md) | [中文](README_CN.md)

# Resume Tailor

**5 分钟内把任何职位招聘信息变成一份量身定制的简历。**

你有一份简历，但每个职位都不同。Resume Tailor 读取职位描述（JD），分析岗位要求，问你几个问题，然后生成一份精美的、ATS 友好的简历——支持 DOCX、PDF 或 Markdown 格式。

支持 Claude API（最佳质量）或通过 Ollama 使用免费本地模型（无需注册账号）。

## 工作原理

```
你的简历 + 职位描述
         │
         ▼
   ┌─────────────┐
   │  JD 分析     │ ← 提取技能、关键词、公司关注点
   └──────┬──────┘
          ▼
   ┌──────────────┐
   │  差距分析     │ ← 找出缺失项，问你针对性的问题
   └──────┬───────┘
          ▼
   ┌───────────────────┐
   │  兼容性评分        │ ← 生成前展示 0-100% 的匹配度
   └───────┬───────────┘
           ▼
   ┌──────────────────┐
   │  简历生成         │ ← 基于你的真实经历生成定制内容
   └───────┬──────────┘
           ▼
   DOCX / PDF / Markdown
```

## 快速开始

从以下三个选项中选择**一个**。如果你不想付费购买 API 密钥，选项 B 最简单。

---

### 选项 A：Docker + Claude API（最佳质量）

Claude 生成的简历质量最好。你需要一个 API 密钥（每份简历约 ¥0.07-0.35）。

**1. 获取 API 密钥**（只需 1 分钟）

访问 https://console.anthropic.com/settings/keys → 创建密钥 → 复制。密钥以 `sk-ant-` 开头。

**2. 克隆并构建**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
docker build -t resume-tailor .
```

**3. 生成你的第一份简历**

```bash
# Linux / macOS
docker run -it \
  -e ANTHROPIC_API_KEY="sk-ant-你的密钥" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/

# Windows (PowerShell)
docker run -it `
  -e ANTHROPIC_API_KEY="sk-ant-你的密钥" `
  -v $env:USERPROFILE\.resume-tailor:/root/.resume-tailor `
  -v ${PWD}\output:/output `
  resume-tailor generate --format pdf --output /output/
```

工具会引导你完成：粘贴你的简历、粘贴职位描述、回答几个问题，就能获得定制简历。

---

### 选项 B：Docker + Ollama（免费，本地运行）

无需 API 密钥、无需账号、无需花钱。所有内容都在你的电脑上运行。需要约 4 GB 内存。

**1. 克隆并启动**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor

# 启动 Ollama 容器（首次运行下载约 2 GB）
docker compose -f docker-compose.full.yml up -d ollama
```

**2. 下载模型**（一次性操作，约 2 GB）

```bash
docker compose -f docker-compose.full.yml exec ollama ollama pull qwen3.5
```

**3. 生成你的第一份简历**

```bash
docker compose -f docker-compose.full.yml run --rm resume-tailor
```

---

### 在 Docker 中访问本地文件

使用 Docker 运行时（选项 A 或 B），你的 **Downloads**、**Desktop** 和 **Documents** 文件夹会自动以只读方式挂载到容器中。你可以直接使用原始路径引用文件，路径会自动转换：

```
~/Downloads/resume.pdf       → /mnt/downloads/resume.pdf
~/Documents/my_resume.docx   → /mnt/documents/my_resume.docx
~/Desktop/job_posting.txt    → /mnt/desktop/job_posting.txt
```

你也可以把文件放在项目目录下的 `input/` 文件夹中，在容器内通过 `/mnt/input/` 访问。

---

### 选项 C：本地安装（无需 Docker）

适合想修改代码或不想用 Docker 的用户。

**1. 克隆并安装**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. 安装 LibreOffice**（仅 PDF 输出需要）

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice

# Windows — 从 https://www.libreoffice.org/download/ 下载
# 或者直接用 --format docx 跳过这步
```

**3. 设置 AI 后端**

```bash
# 方案 1：Claude API（最佳质量）
export ANTHROPIC_API_KEY="sk-ant-你的密钥"
python src/main.py generate

# 方案 2：Ollama（免费，本地运行）
# 安装 Ollama：https://ollama.com/download
ollama pull qwen3.5
python src/main.py generate --model ollama:qwen3.5
```

---

## 第一次运行的样子

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

Using profile resume for Jane Doe

--- Step 4: Target Job Description ---
Provide the job description: paste content below, or enter a file path.
/path/to/job_posting.txt

  Words:    287
  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]:

--- Step 5: JD Analysis ---
Analysis complete. Role: Senior Platform Engineer
Key skills identified: Python, Go, Kubernetes, distributed systems, CI/CD

--- Step 6: Gap Analysis & Follow-Up Questions ---
Your resume already matches well on:
  - Python backend development
  - Cloud infrastructure (AWS)
  - CI/CD pipeline experience

I have a few questions based on gaps between your resume and the JD.

  Do you have experience with Go or similar systems languages?
  → Built internal CLI tools in Go for deployment automation

--- Step 7: Compatibility Assessment ---
  Match Score: [████████████████░░░░] 78%

  Strong Matches:
    + Python backend and API development
    + Kubernetes and containerization

Match score: 78%. Proceed with generation? [Y/n]:

--- Step 8: Generating Tailored Resume ---
Resume content generated.

Done! Your tailored resume has been saved to:
  output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## 功能特性

- **保存一次，处处复用** — 档案系统记住你的简历和联系方式
- **智能差距分析** — AI 识别缺失项并提出针对性的问题
- **经验库** — 记住你的回答，同样的问题不用重复输入
- **匹配评分** — 生成前查看 0-100% 的兼容性评分
- **简历评审** — 独立命令，用 AI 反馈改进你的基础简历
- **多格式输出** — DOCX、PDF 和 Markdown
- **ATS 友好** — 简洁的格式，能通过自动化简历筛选系统
- **多档案支持** — 在同一台电脑上为不同人管理简历
- **会话恢复** — 使用 `--resume-session` 重新运行，尝试不同的回答
- **试运行模式** — 无需消耗 API 额度即可测试完整流程
- **本地或云端 AI** — 使用 Claude API 或免费的本地 Ollama 模型

## 命令

| 命令 | 作用 |
|------|------|
| `generate` | 完整流程：分析职位、评估匹配度、生成定制简历 |
| `review` | 获取 AI 反馈并改进基础简历 |
| `profile view` | 查看档案内容 |
| `profile update` | 修改姓名、邮箱、电话等 |
| `profile edit` | 在文本编辑器中打开档案 |
| `profile export` | 以可读文本打印档案 |
| `profile backup` | 保存档案备份 |
| `profile restore` | 恢复之前的备份 |
| `profile reset` | 删除档案，重新开始 |

### 常用参数

| 参数 | 适用命令 | 作用 |
|------|---------|------|
| `--format pdf` | `generate` | 输出为 PDF（也支持：`docx`、`md`、`all`） |
| `--model ollama:qwen3.5` | `generate`、`review` | 使用本地模型替代 Claude |
| `--skip-questions` | `generate` | 跳过跟进问题 |
| `--skip-assessment` | `generate` | 跳过兼容性评分 |
| `--resume-session` | `generate` | 复用上次运行的输入 |
| `--dry-run` | `generate` | 测试流程，不调用 AI |
| `--profile wife` | 任意命令 | 使用不同的档案 |
| `--verbose` | 任意命令 | 显示详细日志 |

完整参考请见 [USAGE_CN.md](USAGE_CN.md)，包含所有参数、工作流程和故障排除。

## REST API

Resume Tailor 也可以作为 Web API 运行，支持程序化访问。

```bash
# 启动服务器
make api

# 健康检查
curl http://localhost:8000/api/v1/health

# 生成简历
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}'
```

API 文档：http://localhost:8000/docs（交互式 Swagger UI）。

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/analyze-jd` | 分析职位描述 |
| `POST` | `/api/v1/assess-compatibility` | 简历与职位匹配评分（0-100%） |
| `POST` | `/api/v1/generate` | 生成定制简历（JSON） |
| `POST` | `/api/v1/generate/pdf` | 生成并下载 PDF |
| `POST` | `/api/v1/review` | AI 反馈评审简历 |

## 支持的 Ollama 模型

任何 Ollama 模型都可以。一些常用选择：

| 模型 | 参数 | 备注 |
|------|------|------|
| Qwen 3.5 | `--model ollama:qwen3.5` | 综合表现好，推荐 |
| Devstral | `--model ollama:devstral` | 技术类简历表现强 |
| Gemma 3 | `--model ollama:gemma3` | 轻量选项 |

## 贡献

```bash
make dev-install   # 安装开发依赖
make test          # 运行测试
make lint          # 运行代码检查
make format        # 格式化代码
```

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
