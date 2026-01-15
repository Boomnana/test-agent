from typing import List, Dict, Any
from loguru import logger
import json
import asyncio
from app.models.testcase import TestCase
from app.services.llm.client import LLMClient

class ResultAuditor:
    def __init__(self):
        self.llm = LLMClient()

    async def audit_cases_concurrently(self, cases: List[TestCase], batch_size: int = 10) -> List[TestCase]:
        """
        Audit test cases concurrently to find "False Positives" (marked Pass but actually failed).
        Only audits cases with normalized_result="Pass".
        """
        pass_cases = [c for c in cases if c.normalized_result == "Pass"]
        other_cases = [c for c in cases if c.normalized_result != "Pass"]
        
        logger.info(f"Starting concurrent result audit for {len(pass_cases)} passed cases...")
        
        tasks = []
        for i in range(0, len(pass_cases), batch_size):
            batch = pass_cases[i:i + batch_size]
            tasks.append(self._audit_batch_async(batch))
            
        await asyncio.gather(*tasks)
        logger.info("Result audit completed.")
            
        return pass_cases + other_cases

    async def _audit_batch_async(self, batch: List[TestCase]):
        prompt = self._build_audit_prompt(batch)
        try:
            response = await self.llm.achat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, # Low temperature for strict analysis
                response_format={"type": "json_object"}
            )
            
            results = self._parse_llm_response(response)
            self._apply_audit_results(batch, results)
            
        except Exception as e:
            logger.error(f"Error auditing batch: {e}")
            # Fallback: mark as Unchecked or try individual? 
            # For now, leave as Unchecked (default)

    def _apply_audit_results(self, batch: List[TestCase], results: List[Dict[str, Any]]):
        result_map = {str(r.get("id")): r for r in results}
        
        for case in batch:
            # Match by ID. Since ID might be string or int, convert both to string.
            # In local processing without DB, we might rely on index or temporary ID.
            # The prompt builder used str(c.id).
            res = result_map.get(str(case.id))
            if res:
                case.audit_status = res.get("status", "Pass")
                case.audit_reason = res.get("reason", "")
            else:
                case.audit_status = "Pass" # Default if not flagged

    def _build_audit_prompt(self, batch: List[TestCase]) -> str:
        cases_text = []
        for c in batch:
            # Construct a concise representation
            item = {
                "id": str(c.id),
                "case_name": c.case_name,
                "expected": c.expected or "N/A",
                "actual": c.actual or "N/A",
                "remark": c.remark or "N/A"
            }
            cases_text.append(item)
            
        return f"""
你是一名严格的测试质量审计员（QA Auditor）。你的任务是审查以下被标记为“成功（Pass）”的测试用例，判断其是否为“假成功（False Positive）”。

请仔细对比【预期结果】、【实际结果】和【备注】，如果发现以下情况，请将其标记为“Flagged”（存疑）：
1. 实际结果明确描述了失败、错误、未找到、不匹配、异常等情况，但状态却为 Pass。
2. 实际结果与预期结果明显矛盾（例如：预期显示A，实际显示B）。
3. 实际结果为空（None/Null）或仅为占位符，无法证明测试通过。
4. 备注中包含“失败”、“Bug”、“缺陷”等关键词。

如果用例确实通过，请标记为“Pass”。

输入用例列表 (JSON):
{json.dumps(cases_text, ensure_ascii=False, indent=2)}

请返回一个 JSON 对象，格式如下：
{{
    "results": [
        {{
            "id": "用例ID",
            "status": "Pass" 或 "Flagged",
            "reason": "如果是Flagged，请简要说明理由（中文）；如果是Pass，留空。"
        }}
    ]
}}

注意：
- 严禁返回任何 Python 代码块或 Markdown 格式。
- 仅返回纯 JSON 字符串。
"""

    def _parse_llm_response(self, response: Any) -> List[Dict[str, Any]]:
        try:
            if isinstance(response, dict):
                return response.get("results", [])
            
            if isinstance(response, str):
                content = response.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    if content.endswith("```"):
                        content = content.rsplit("\n", 1)[0]
                data = json.loads(content)
                return data.get("results", [])
                
        except Exception as e:
            logger.error(f"Failed to parse audit response: {e}")
            return []
        return []

    def _apply_audit_results(self, batch: List[TestCase], results: List[Dict[str, Any]]):
        result_map = {str(r["id"]): r for r in results}
        
        for case in batch:
            res = result_map.get(str(case.id))
            if res:
                case.audit_status = res.get("status", "Unchecked")
                case.audit_reason = res.get("reason", "")
            else:
                case.audit_status = "Unchecked"
