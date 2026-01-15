# 0) 总体编排 DAG（推荐）

一个“报告生成 Job”拆成 6 个 Stage（每个 stage 都是 Celery task，产生明确产物）：

1. `ingest_and_normalize`（预检 + 标准化）
2. `module_tagging`（规则优先 + LMM 兜底）
3. `compute_stats_and_charts`（纯程序统计+图表数据）
4. `extract_defects_fail_only`（Fail/Blocked 行 LLM 抽取，**并发**）
5. `cluster_and_summarize_defects`（聚类算法 + 簇级 LLM 总结，部分并发）
6. `render_report_and_export`（生成 HTML + 多sheet Excel + 存储产物）

编排形式（推荐）：

- Stage 间：`chain`
- Stage 4：`group` + `chord`（并发抽取 → 汇总）
- Stage 5：聚类（单任务）+ 簇总结（group）

------

# 1) 任务输入/输出规范（建议固定 schema）

所有 task 都遵循：

**输入**：`job_id`（唯一）+（必要时）`payload_ref`（对象存储/DB引用）
**输出**：`artifact_refs`（产物引用）+ `metrics` + `warnings` + `next_inputs`

统一返回结构（Pydantic）：

```json
{
  "job_id": "J20260101_xxx",
  "stage": "module_tagging",
  "status": "ok",
  "artifacts": {
    "normalized_cases_ref": "db:testcases?job=...",
    "module_map_ref": "db:modules?job=..."
  },
  "metrics": { "cases": 120, "low_conf": 8 },
  "warnings": [ "missing_exec_time: 14 rows" ]
}
```

------

# 2) Celery Queue 规划（关键：隔离 LLM 与 CPU 任务）

建议至少 4 个队列：

- `q_io`：文件下载/读取/写产物（I/O型）
- `q_cpu`：统计、聚类、导出 Excel（CPU型）
- `q_llm`：LLM 调用（限流、并发可控）
- `q_orch`：编排与汇总（轻量）

并设置不同 worker 数量和并发：

- `q_llm`：并发小、严格限速（比如 worker=2~4, concurrency=2）
- `q_cpu`：并发中等（worker=2, concurrency=4）
- `q_io`：并发高一点（concurrency=8）
- `q_orch`：concurrency=1~2

------

# 3) 失败重试总策略（统一规则）

### 3.1 任务类型与重试策略

| 任务类型         | 典型失败                   | 重试策略                                                 |
| ---------------- | -------------------------- | -------------------------------------------------------- |
| I/O（读写/存储） | 网络抖动、S3 超时          | `autoretry_for`，指数退避，最多 5 次                     |
| CPU（统计/导出） | 数据异常、内存不足         | 不自动重试或 1 次；异常要落 `ParseIssues`                |
| LLM（抽取/总结） | 超时、429、输出不合 schema | 2~4 次重试；schema失败走“修复prompt”再重试；仍失败则降级 |
| Orchestrator     | 上游失败                   | 不重试，改为 job fail 并给出可重跑 stage                 |

### 3.2 推荐 Celery 重试参数（通用）

- `max_retries=4`
- `retry_backoff=True`
- `retry_backoff_max=120`（秒）
- `retry_jitter=True`

**LLM 特殊**：

- 429/timeout → 重试
- schema 校验失败 → **切换为 repair prompt** 重试 1~2 次
- 仍失败 → 标记该 case `llm_failed=true`，继续 job（整体不崩）

------

# 4) 幂等与可重跑（必须做）

### 4.1 幂等键（Idempotency Key）

每个 stage 产物用：

- `job_id + stage_name + version + input_hash`

例如：

- `Jxxx/module_tagging/v1/hash( normalized_cases_version )`

如果同一个 key 已存在产物 → 直接返回（避免重复计费 LLM）。

### 4.2 断点重跑

DB 保存：

- `job.stage_status[stage]=ok/failed/pending`
- `job.stage_artifacts[stage]=artifact_refs`
- `job.stage_started_at/finished_at`

重跑策略：

- 允许从指定 stage 开始（后续 stage 清理或重算）
- 若上游产物未变 → 下游可复用

------

# 5) 具体 task 编排（逐步：输入/输出/并发/重试）

下面按你的 6 步给出**可执行级别**的 Celery 任务设计。

------

## Stage 1：ingest_and_normalize（q_io）

**任务**：`ingest_and_normalize(job_id, file_ref)`
**输入**：

- `job_id`
- `file_ref`（S3 key/本地路径）
- 可选：`sheet_whitelist`

**处理**：

- 读 Excel → 行级清洗 → 字段映射 → 枚举归一
- 产出：
  - 标准化用例表 `testcases`（DB）
  - 质量报告 `validation_report`（DB/JSON）

**输出 artifacts**：

- `normalized_cases_ref = db:testcases?job_id=...`
- `validation_report_ref = db:validation?job_id=...`

**失败/重试**：

- 文件读失败 → 重试 3~5 次（IO错误）
- 必填缺失率过高 → 不失败，写 warning + ParseIssues

------

## Stage 2：module_tagging（q_cpu + q_llm）

拆成两步：规则先跑，LLM 兜底并发

### 2.1 `module_tagging_rules(job_id, normalized_cases_ref)`（q_cpu）

**输出**：

- `module_assignments_ref`（已分模块+标注 low_conf/unknown）

### 2.2 `module_tagging_llm_fallback`（group 并发，q_llm）

只对 `unknown` / `conflict` / `low_conf` 的 case 才调用 LLM。

- `group([classify_case_module.s(job_id, case_pk) ...])`
- 汇总：`collect_module_results(job_id, results)`

**并发策略**：

- group 的粒度：**每条用例一个 task**
- 但要加限流（见 §7）

**失败/重试**：

- LLM 超时/429 → 重试
- schema 失败 → repair prompt 重试 1 次
- 仍失败 → 该 case `module="Uncategorized"` + `module_confidence=0`，继续

------

## Stage 3：compute_stats_and_charts（q_cpu）

**任务**：`compute_stats_and_charts(job_id, normalized_cases_ref)`
**处理**：

- 全局/按模块统计
- 图表数据（建议输出 JSON，前端渲染）

**输出**：

- `stats_ref`（DB JSON）
- `charts_ref`（DB JSON）

**失败/重试**：

- 统计异常（比如结果字段空）→ 不重试，写 ParseIssues，继续（但 stats 中标注“不完整”）

------

## Stage 4：extract_defects_fail_only（并发 chord，q_llm）

**目标**：Fail/Blocked 行 LLM 抽取缺陷事实（defect_facts）

### 4.1 `prepare_fail_cases(job_id)`（q_cpu）

- 查询 Fail/Blocked case 列表
- 输出 `fail_case_ids`

### 4.2 `extract_defect_fact(job_id, case_pk)`（q_llm）并发

- **一个失败用例一个 task**
- 输出单条 `defect_fact` 写 DB（强烈建议：每条写入，避免汇总丢）

### 4.3 `finalize_defect_facts(job_id, results)`（q_orch）

- 统计成功率/失败率
- 输出 `defect_facts_ref`

**并发策略（关键）**：

- `chord(group(extract_defect_fact.s(...)), finalize_defect_facts.s(job_id))`
- chunk 大 job：可按模块分批 chord（避免一次 group 10k 条）

**失败/重试**：

- LLM 失败：重试 3 次
- schema失败：repair prompt → 重试 1 次
- 最终失败：写 DB `llm_failed=true`，记录 raw snippet，继续 job（整体不中断）

------

## Stage 5：cluster_and_summarize_defects（q_cpu + q_llm）

### 5.1 `cluster_defects(job_id, defect_facts_ref)`（q_cpu）

- embedding/相似度聚类（或关键词+TF-IDF也可先用）
- 输出 `clusters_ref`（每簇包含成员 defect_ids/case_ids）

### 5.2 `summarize_cluster(job_id, cluster_id)`（q_llm）并发

- 每个簇一个 task（簇数通常 << case 数）
- 输出：簇命名、共性、系统性风险、证据 case_id 列表

并发：

- `group([summarize_cluster.s(job_id, cid) ...])`
- 汇总：`finalize_cluster_summaries(job_id, results)`

失败策略：

- 单簇总结失败不影响整体：该簇用“规则模板总结”（fallback）替代

------

## Stage 6：render_report_and_export（q_cpu/q_io）

### 6.1 `compose_report_content(job_id, stats_ref, clusters_ref, summaries_ref)`（q_llm 或 q_cpu）

- LLM 只负责“文案 JSON”（目标范围/结论/风险等）
- 强制引用 case_id/cluster_id

### 6.2 `render_html(job_id, report_json_ref, charts_ref)`（q_cpu）

- 用 Jinja 模板渲染 HTML（不要让 LLM 拼 HTML）

### 6.3 `export_excel(job_id, normalized_cases_ref, stats_ref, defect_facts_ref, parse_issues_ref)`（q_cpu）

- 输出多 sheet xlsx

### 6.4 `store_artifacts(job_id, html_path, xlsx_path)`（q_io）

- 上传对象存储，写 DB artifact refs

失败策略：

- Excel 导出失败 → 可重试 1 次；仍失败至少保证 HTML 出
- HTML 渲染失败 → fallback 简版报告（只统计+链接）

------

# 6) Orchestrator：一键启动的 Celery Canvas（推荐写法）

伪代码（Celery canvas）：

```python
from celery import chain, group, chord

def build_job_flow(job_id, file_ref):
    return chain(
        ingest_and_normalize.s(job_id, file_ref).set(queue="q_io"),
        module_tagging_rules.s(job_id).set(queue="q_cpu"),
        module_tagging_llm_fallback.s(job_id).set(queue="q_orch"),  # 内部会发group到q_llm
        compute_stats_and_charts.s(job_id).set(queue="q_cpu"),

        # Stage4: chord
        extract_defects_entry.s(job_id).set(queue="q_orch"),  # 内部：prepare + chord(group(extract), finalize)

        cluster_defects.s(job_id).set(queue="q_cpu"),
        summarize_clusters_entry.s(job_id).set(queue="q_orch"),  # 内部：group(summarize_cluster)->finalize

        compose_report_content.s(job_id).set(queue="q_llm"),
        render_html.s(job_id).set(queue="q_cpu"),
        export_excel.s(job_id).set(queue="q_cpu"),
        store_artifacts.s(job_id).set(queue="q_io"),
        mark_job_done.s(job_id).set(queue="q_orch"),
    )
```

**注意**：`module_tagging_llm_fallback` / `extract_defects_entry` / `summarize_clusters_entry` 这些“entry task”内部再发 group/chord，方便统一管理进度与限流。

------

# 7) 并发与限流（LLM 成本控制的关键）

### 7.1 Celery 层限流

对 LLM tasks 设置：

- `rate_limit="30/m"`（示例）
- 或者 worker 启动时控制 `--concurrency=2`

并在 task 上指定队列 `q_llm`。

### 7.2 批量分发策略（避免 chord 太大）

如果 Fail 用例很多（>2000）：

- 按模块切分成多个 chord（每 chord 200~500 个任务）
- 每个 chord 完成后写 partial results
- 最终再汇总（reduce）

------

# 8) 进度上报（给你前端展示板用）

每个 stage 开始/结束都写 DB + 发“进度事件”：

- `job_progress` 表：
  - `job_id, stage, status, percent, message, updated_at`
- 每条 LLM 子任务：
  - `completed/total` 计数器（Redis 原子计数或 DB）

前端轮询 `GET /jobs/{job_id}` 即可展示“数据清洗中/模块识别中/缺陷抽取 37%...”。

------

# 9) 降级策略（必须写进代码，不然一定翻车）

- **LLM 全挂/预算不足**：仍输出
  - 统计面板 + 失败列表 + 原始 Excel 标准化版
  - 报告中“分析部分降级，仅输出统计与失败用例”
- **单模块/单簇总结失败**：
  - 输出模板化句式 + 证据列表（case_id）
- **输入质量差**：
  - 报告第一屏提示“数据质量告警”，并附 ParseIssues

------

# 10) 你可以直接照抄的 Celery task 配置建议

- `task_acks_late=True`（避免 worker 掉线丢任务）
- `task_reject_on_worker_lost=True`
- `worker_prefetch_multiplier=1`（LLM 队列强烈建议）
- `broker_transport_options={"visibility_timeout": ...}`（按任务最长时间设置）
- LLM task `soft_time_limit=60`，`time_limit=90`（按模型延迟调）

