from typing import List, Dict, Any
import asyncio
from app.models.testcase import TestCase
from app.models.defect import DefectAnalysis
from app.services.llm.client import llm_client
from app.core.logging import get_logger

logger = get_logger("defect_extractor")

class DefectExtractor:
    async def extract_defect_facts_concurrently(self, cases: List[TestCase]) -> List[DefectAnalysis]:
        failed_cases = [c for c in cases if c.normalized_result in ["Fail", "Blocked"]]
        analyses = []
        
        logger.info(f"Extracting defects for {len(failed_cases)} cases concurrently...")
        
        tasks = [self._extract_single_defect_async(case) for case in failed_cases]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results (failures)
        analyses = [r for r in results if r is not None]
        logger.info(f"Extracted {len(analyses)} defects.")
        
        return analyses

    async def _extract_single_defect_async(self, case: TestCase) -> Any:
        try:
            # Prompt adapted from manual
            prompt = f"""
            分析此失败用例并提取缺陷事实。
            
            【重要指令】
            1. 仅输出纯 JSON 字符串。
            2. 严禁输出 Python 代码或 Markdown。
            3. 使用中文。
            4. 注意：如果在 JSON 值中引用包含双引号的内容，请务必进行转义，或者将其替换为单引号，确保 JSON 格式合法。
            
            用例: {case.case_name}
            步骤: {case.steps}
            预期结果: {case.expected}
            实际结果: {case.actual}
            备注: {case.remark}
            
            JSON 结构:
            {{
              "phenomenon": "简要描述（中文）",
              "observed_fact": "客观事实（中文）",
              "hypothesis": "推测原因（中文）",
              "evidence": ["证据文本"],
              "repro_steps": "复现步骤（中文）",
              "severity_guess": "Critical/Major/Minor"
            }}
            """
            
            messages = [{"role": "user", "content": prompt}]
            result = await llm_client.achat_completion(messages, response_format=dict)
            
            if isinstance(result, dict):
                analysis = DefectAnalysis(
                    testcase_id=case.id, # Note: ID might not be set if not flushed to DB yet, handle carefully
                    phenomenon=result.get("phenomenon"),
                    observed_fact=result.get("observed_fact"),
                    hypothesis=result.get("hypothesis"),
                    evidence=result.get("evidence", []),
                    repro_steps=result.get("repro_steps"),
                    severity_guess=result.get("severity_guess")
                )
                
                # Link in memory for now
                case.defect_analysis = analysis
                return analysis
                
        except Exception as e:
            logger.error(f"Failed to extract defect for {case.case_name}: {e}")
            return None

defect_extractor = DefectExtractor()
