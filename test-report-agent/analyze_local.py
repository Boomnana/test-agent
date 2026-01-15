import os
import uuid
import sys
import argparse
import asyncio

# Add 'backend' to sys.path so 'app' module can be found
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Import Base to ensure all models are registered (Fixes SQLAlchemy 'Job' not found error)
from app.db.base import Base
from app.services.ingest.service import ingest_service
from app.services.ingest.tagging import module_tagger
from app.services.analytics.stats import stats_service
from app.services.defects.extractor import defect_extractor
from app.services.defects.clustering import defect_clusterer
from typing import Dict, Any
from app.services.audit.auditor import ResultAuditor
from app.models.testcase import TestCase
from app.services.llm.client import llm_client

async def analyze_file(file_path: str):
    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 {file_path}")
        return

    print(f">>> 开始分析文件 (并发模式): {file_path}")
    
    # 1. Setup
    job_id = f"JOB-{uuid.uuid4().hex[:8]}"
    
    try:
        # 2. Ingest
        print(f"\n[1/6] 正在读取数据...")
        raw_cases = await ingest_service.parse_excel(file_path, job_id)
        if not raw_cases:
            print("Excel 文件中未发现测试用例。")
            return

        cases = [TestCase(**d) for d in raw_cases]
        print(f"      已读取 {len(cases)} 条用例。")

        # 3. Module Tagging
        print("\n[2/6] 模块打标 (LLM 批量并发)...")
        cases = await module_tagger.tag_cases_concurrently(cases)
        
        # 3.5 Audit (Quality Check)
        print("\n[2.5/6] 结果审计 (LLM 并发检查假成功)...")
        auditor = ResultAuditor()
        cases = await auditor.audit_cases_concurrently(cases)
        suspicious_cases = [c for c in cases if c.audit_status == "Flagged"]
        print(f"      发现 {len(suspicious_cases)} 个存疑用例。")
        
        # Print a few examples
        for i, c in enumerate(cases[:5]):
            print(f"      - {c.case_name[:30]}... -> [{c.module}]")
        if len(cases) > 5:
            print(f"      ... 以及其他 {len(cases)-5} 条。")

        # 4. Stats
        print("\n[3/6] 计算统计数据...")
        stats = stats_service.compute_stats(cases)
        print(f"      通过率: {stats.get('pass_rate')}%")

        # 5. Defect Extraction
        print("\n[4/6] 提取缺陷事实 (LLM 并发)...")
        defects = await defect_extractor.extract_defect_facts_concurrently(cases)
        print(f"      提取了 {len(defects)} 条缺陷分析。")

        # Manual linking for in-memory processing (skipping DB)
        linked_defects = []
        for c in cases:
            if hasattr(c, 'defect_analysis') and c.defect_analysis:
                c.defect_analysis.testcase = c  # Bidirectional link for template
                linked_defects.append(c.defect_analysis)
        
        # 6. Clustering
        print("\n[5/6] 缺陷聚类 (LLM)...")
        clusters = await defect_clusterer.cluster_and_summarize_async(linked_defects, job_id)
        print(f"      识别出 {len(clusters)} 个聚类。")
        for c in clusters:
            print(f"      聚类: {c.cluster_name}")

        # 7. Result (JSON)
        print("\n[6/6] 生成 JSON 结果...")
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"result_{job_id}.json")
        result: Dict[str, Any] = {
            "job_id": job_id,
            "stats": stats,
            "defects": [d.dict() if hasattr(d, "dict") else d for d in linked_defects],
            "clusters": [c.dict() if hasattr(c, "dict") else c for c in clusters],
            "suspicious_cases": [c.dict() if hasattr(c, "dict") else c for c in suspicious_cases],
            "cases": [c.dict() if hasattr(c, "dict") else c for c in cases],
        }
        import json
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n成功! 结果已生成:\n{os.path.abspath(result_path)}")
        
        # Print Token Usage
        print("\n" + "="*30)
        print(f"本次分析消耗总 Tokens: {llm_client.total_tokens}")
        print("="*30)
        
        return result_path

    except Exception as e:
        print(f"\n错误: 流水线失败 - {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Test Report Agent on a local Excel file")
    parser.add_argument("file_path", nargs='?', default=r"测试用例汇总.xlsx", help="Path to the Excel file (.xlsx)")
    args = parser.parse_args()
    
    asyncio.run(analyze_file(args.file_path))
