# Test Report Agent 系统说明文档

本文档旨在为新接手的开发人员提供一份详尽的系统指南，涵盖系统架构、核心流程、代码细节及运行维护说明。

---

## 1. 系统简介

**Test Report Agent** 是一个基于 LLM（大语言模型）的智能化测试报告分析系统。它能够自动读取测试执行结果（Excel），通过 AI 能力进行数据清洗、模块分类、质量审计、缺陷分析和聚类，最终生成包含图表和深度洞察的 HTML 测试报告。

**核心价值**：

- **自动化分析**：替代人工编写测试总结和缺陷分析。
- **质量审计**：识别“假成功”（False Positive）用例，提升报告可信度。
- **非标数据兼容**：利用 LLM 自动对齐不同格式的 Excel 表头和结果字段。

---

## 2. 系统架构

系统采用 **Pipeline（流水线）** 模式设计，数据流向清晰，各阶段高度解耦。

### 2.1 核心流水线

```mermaid
graph LR
    A[Excel 输入] --> B[数据接入与清洗 (Ingest)]
    B --> C[智能模块打标 (Tagging)]
    C --> D[结果审计 (Audit)]
    D --> E[统计分析 (Stats)]
    E --> F[缺陷提取 (Defect Extraction)]
    F --> G[缺陷聚类 (Clustering)]
    G --> H[HTML 报告生成 (Reporting)]
```

### 2.2 技术栈

- **语言**: Python 3.10+
- **LLM**: GLM-4-Air (智谱 AI)
- **Web 框架**: FastAPI (用于后端 API)
- **任务队列**: Celery + Redis (用于异步任务)
- **ORM**: SQLAlchemy (Async)
- **模板引擎**: Jinja2 (用于生成 HTML)
- **前端可视化**: Tailwind CSS + Plotly.js

---

## 3. 核心功能模块详解

### 3.1 数据接入与清洗 (Ingest)

- **代码位置**: `backend/app/services/ingest/service.py`
- **功能**: 读取 Excel 文件，将非结构化数据转换为系统标准格式。
- **关键机制**:
  - **LLM 动态列映射 (`_align_columns_with_llm`)**: 不依赖硬编码的列名（如 "Case Name"），而是将 Excel 表头传给 LLM，让其推断并映射到系统字段（`case_name`, `steps`, `expected`, `actual`, `result` 等）。
  - **LLM 结果归一化 (`_normalize_results_with_llm`)**: 自动将各种各样的结果描述（如 "成功", "ok", "通过", "失败", "bug"）统一映射为标准的 `Pass`, `Fail`, `Blocked`, `Skipped`。

### 3.2 智能模块打标 (Module Tagging)

- **代码位置**: `backend/app/services/ingest/tagging.py`
- **功能**: 根据用例名称和步骤，自动划分功能模块。
- **实现细节**:
  - **并发处理 (Concurrency)**: 采用 `asyncio` 并发机制，同时处理多个 Batch，大幅缩短整体耗时。
  - 采用 **Batch（批处理）** 模式，将多个用例打包一次性发给 LLM，节省 Token 并提高吞吐量。
  - 相比传统的关键字匹配，LLM 能更准确地理解业务语义（例如将“登录”和“登出”都归为“用户认证模块”）。

### 3.3 结果审计 (Result Audit) - *特色功能*

- **代码位置**: `backend/app/services/audit/auditor.py`
- **功能**: 专门针对状态为 `Pass` 的用例进行“复核”。
- **逻辑**:
  - **并发执行**: 支持高并发请求，快速扫描大量通过用例。
  - LLM 会检查 `预期结果`、`实际结果` 和 `备注` 之间的一致性。
  - 如果发现实际结果描述了错误（例如实际结果为 "None" 但预期是有值），即使 Excel 中标记为 "成功"，系统也会将其标记为 **Suspicious (疑似假成功)**。
  - 这些用例会在报告的“质量审计”章节单独高亮显示。

### 3.4 缺陷分析 (Defect Analysis)

- **代码位置**: `backend/app/services/defects/extractor.py`
- **功能**: 对所有 `Fail` 或 `Blocked` 的用例进行深度分析。
- **实现**: 全并发模式，同时对所有失败用例发起 LLM 请求，极速完成分析。
- **输出**:
  - **现象描述**: 简要概括发生了什么。
  - **推测原因**: AI 基于步骤和结果推断的可能根因。
  - **复现步骤**: 提炼出的最小复现路径。

### 3.5 缺陷聚类 (Clustering)

- **代码位置**: `backend/app/services/defects/clustering.py`
- **功能**: 将零散的缺陷按语义相似度归类。
- **流程 (纯 LLM 实现)**:
  1. 收集所有缺陷的现象描述，生成带临时 ID 的列表。
  2. 将整个列表发送给 LLM，要求其根据语义相似性进行分组，并为每组生成名称、总结和风险评估。
  3. 解析 LLM 返回的 JSON 结果，将缺陷对象映射回对应的聚类中。
- **鲁棒性设计**:
  - **自动补漏**: 如果 LLM 遗漏了部分缺陷未归类，系统会自动将其放入“未分类缺陷”聚类，防止数据丢失。
  - **全量降级**: 如果 LLM 调用完全失败（如网络错误），系统会将所有缺陷归入“全部缺陷 (自动聚类失败)”组，确保报告生成流程不中断。

### 3.6 报告生成 (Reporting)

- **代码位置**: `backend/app/services/report_gen/renderer.py`
- **模板**: `backend/app/services/report_gen/templates/report.html`
- **功能**: 渲染最终产物。
- **交互特性**:
  - 包含“悬浮窗”功能：鼠标悬停在表格行上 1 秒后，会显示详细信息的 Tooltip。
  - 包含完整的“附录”章节，列出所有原始数据。

### 3.7 全局特性

- **Token 统计**: 系统会自动统计整个分析过程中所有 LLM 调用消耗的总 Token 数量，并在 CLI 结束时输出，便于成本监控。
- **异步架构**: 核心 LLM 调用链路全面升级为 `async/await` 异步并发模式，显著提升了处理大文件时的性能。

---

## 4. 目录结构说明

```text
test-report-agent/
├── analyze_local.py          # [入口] 本地运行脚本，集成所有服务
├── .env                      # [配置] API Key 和数据库配置
├── requirements.txt          # [依赖] Python 依赖包
├── backend/
│   ├── app/
│   │   ├── core/             # 配置读取 (config.py)
│   │   ├── db/               # 数据库模型 (models/)
│   │   ├── services/         # 核心业务逻辑
│   │   │   ├── ingest/       # 数据接入
│   │   │   ├── audit/        # 结果审计
│   │   │   ├── defects/      # 缺陷分析与聚类
│   │   │   ├── analytics/    # 统计服务
│   │   │   ├── report_gen/   # 报告渲染
│   │   │   └── llm/          # LLM 客户端封装
│   │   └── workers/          # Celery 异步任务定义
└── reports/                  # 生成的 HTML 报告输出目录
```

---

## 5. 运行指南

### 5.1 环境准备

确保已安装 Python 3.10+，并安装依赖：

```bash
pip install -r requirements.txt
```

### 5.2 配置文件 (.env)

确保项目根目录下有 `.env` 文件，内容如下（根据实际情况修改）：

```ini
PROJECT_NAME="Test Report Agent"
GLM_API_KEY="your_api_key_here"
LLM_MODEL="glm-4-air"
```

### 5.3 运行分析

使用 `analyze_local.py` 脚本即可一键完成全流程分析：

```bash
python analyze_local.py "C:\path\to\your\test_data.xlsx"
```

### 5.4 查看结果

运行完成后，控制台会输出报告路径，例如： 
`.../reports/report_JOB-xxxxxxxx.html`
直接用浏览器打开即可。

---

## 6. 维护与扩展

- **修改 Prompt**: 所有 LLM 的提示词均位于各 Service 类的代码中（如 `extractor.py`, `clustering.py`）。如果觉得 AI 分析不准确，请优先调整这些 Prompt。
- **调整 LLM 模型**: 在 `.env` 中修改 `LLM_MODEL` 即可切换模型（需确保代码中的 `LLMClient` 适配该模型 API）。
- **调试**: 系统使用了 `loguru` 进行日志记录，运行时的详细日志会直接输出到控制台，方便排查问题。

---

*文档生成时间: 2026-01-01*
