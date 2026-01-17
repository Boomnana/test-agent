from fastapi import APIRouter, UploadFile, File
from app.services.ingest.service import ingest_service
from app.services.ingest.tagging import module_tagger
from app.services.analytics.stats import stats_service
from app.services.defects.extractor import defect_extractor
from app.services.defects.clustering import defect_clusterer
from app.services.audit.auditor import ResultAuditor
from app.models.testcase import TestCase
from app.models.defect import DefectAnalysis, DefectCluster
from app.services.report_gen.renderer import report_generator
from typing import Dict, Any, List
import shutil
import os
import uuid
import asyncio
from fastapi.responses import RedirectResponse

router = APIRouter()

job_logs: Dict[str, List[str]] = {}
job_meta: Dict[str, Dict[str, Any]] = {}
job_tasks: Dict[str, asyncio.Task] = {}
JOB_TIMEOUT_SECONDS = 3600


def append_log(job_id: str, message: str) -> None:
    if job_id not in job_logs:
        job_logs[job_id] = []
    job_logs[job_id].append(message)


def ensure_not_cancelled(job_id: str) -> None:
    meta = job_meta.get(job_id)
    if meta and meta.get("status") == "cancelling":
        raise asyncio.CancelledError()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{job_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_logs[job_id] = []
    job_meta[job_id] = {"status": "pending", "report_url": None, "error": None}
    append_log(job_id, "文件已上传，等待开始处理。")
    task = asyncio.create_task(run_local_pipeline_with_timeout(job_id, file_path))
    job_tasks[job_id] = task

    return {
        "job_id": job_id,
        "message": "本地流水线已启动。",
    }


async def run_local_pipeline_with_timeout(job_id: str, file_path: str) -> None:
    try:
        await asyncio.wait_for(run_local_pipeline(job_id, file_path), timeout=JOB_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        job_meta[job_id]["status"] = "failed"
        job_meta[job_id]["error"] = f"任务执行超时（超过 {JOB_TIMEOUT_SECONDS} 秒），请重试或缩小数据量。"
        append_log(job_id, f"流水线执行超时，已终止。超时时间: {JOB_TIMEOUT_SECONDS} 秒。")
    except asyncio.CancelledError:
        job_meta[job_id]["status"] = "cancelled"
        job_meta[job_id]["error"] = "任务已被用户取消。"
        append_log(job_id, "流水线已被用户取消。")
        raise
    finally:
        job_tasks.pop(job_id, None)


async def run_local_pipeline(job_id: str, file_path: str) -> None:
    job_meta[job_id]["status"] = "running"
    try:
        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 1/6：解析 Excel 数据。")
        raw_cases = await ingest_service.parse_excel(file_path, job_id)
        cases = [TestCase(**d) for d in raw_cases]
        append_log(job_id, f"已解析 {len(cases)} 条用例。")

        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 2/6：模块打标（LLM 并发）。")
        cases = await module_tagger.tag_cases_concurrently(cases)

        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 3/6：结果审计（LLM 并发检查假成功）。")
        auditor = ResultAuditor()
        cases = await auditor.audit_cases_concurrently(cases)
        suspicious_cases = [c for c in cases if c.audit_status == "Flagged"]
        append_log(job_id, f"发现 {len(suspicious_cases)} 个存疑用例。")

        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 4/6：计算统计数据。")
        stats = stats_service.compute_stats(cases)

        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 5/6：提取缺陷事实（LLM 并发）。")
        defects = await defect_extractor.extract_defect_facts_concurrently(cases)
        append_log(job_id, f"提取了 {len(defects)} 条缺陷分析。")
        
        linked_defects: List[DefectAnalysis] = []
        for c in cases:
            if hasattr(c, "defect_analysis") and c.defect_analysis:
                c.defect_analysis.testcase = c
                linked_defects.append(c.defect_analysis)

        ensure_not_cancelled(job_id)
        append_log(job_id, "步骤 6/6：缺陷聚类并生成报告。")
        clusters = await defect_clusterer.cluster_and_summarize_async(linked_defects, job_id)

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        output_dir = os.path.join(project_root, "reports")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"report_{job_id}.html"
        report_path = os.path.join(output_dir, filename)
        report_generator.render_report(job_id, stats, linked_defects, clusters, suspicious_cases, cases, report_path)
        report_url = f"/reports/{filename}"
        job_meta[job_id]["status"] = "completed"
        job_meta[job_id]["report_url"] = report_url
        append_log(job_id, f"报告已生成：{report_url}")
        append_log(job_id, "流水线执行完成。")
    except Exception as exc:
        job_meta[job_id]["status"] = "failed"
        job_meta[job_id]["error"] = str(exc)
        append_log(job_id, f"流水线执行失败：{exc}")


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    meta = job_meta.get(job_id)
    logs = job_logs.get(job_id, [])
    if not meta:
        return {
            "job_id": job_id,
            "status": "unknown",
            "logs": logs,
        }
    return {
        "job_id": job_id,
        "status": meta.get("status"),
        "logs": logs,
        "report_url": meta.get("report_url"),
        "error": meta.get("error"),
    }


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    meta = job_meta.get(job_id)
    if not meta:
        return {
            "job_id": job_id,
            "status": "unknown",
            "message": "Job not found.",
        }
    status = meta.get("status")
    if status in {"completed", "failed", "cancelled"}:
        return {
            "job_id": job_id,
            "status": status,
            "message": "Job already finished.",
        }
    task = job_tasks.get(job_id)
    if task and not task.done():
        append_log(job_id, "收到取消请求，尝试终止流水线。")
        task.cancel()
        meta["status"] = "cancelling"
        return {
            "job_id": job_id,
            "status": "cancelling",
            "message": "Cancellation requested.",
        }
    meta["status"] = "failed"
    meta["error"] = "未找到可取消的运行中任务。"
    append_log(job_id, "取消请求失败：未找到运行中的任务。")
    return {
        "job_id": job_id,
        "status": "failed",
        "message": "No running task found to cancel.",
    }

@router.get("/result/{job_id}")
async def get_job_result(job_id: str):
    meta = job_meta.get(job_id)
    if not meta or not meta.get("report_url"):
        return {"error": {"code": 404, "message": "Result not found"}}
    return RedirectResponse(url=meta["report_url"])
