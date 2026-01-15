from typing import List, Dict, Any
import json
import asyncio
from app.models.testcase import TestCase
from app.services.llm.client import llm_client
from app.core.logging import get_logger

logger = get_logger("module_tagging")

class ModuleTagger:
    async def tag_cases_concurrently(self, cases: List[TestCase], batch_size: int = 10) -> List[TestCase]:
        """
        Use LLM to batch tag all cases with modules concurrently.
        """
        total = len(cases)
        logger.info(f"Starting concurrent module tagging for {total} cases...")
        
        tasks = []
        for i in range(0, total, batch_size):
            batch = cases[i:i + batch_size]
            tasks.append(self._process_batch_async(batch, i))
            
        await asyncio.gather(*tasks)
        logger.info("Module tagging completed.")
            
        return cases

    async def _process_batch_async(self, batch: List[TestCase], start_index: int):
        # Prepare concise input for LLM
        batch_input = []
        for idx, case in enumerate(batch):
            # Truncate long fields to save tokens
            batch_input.append({
                "id": idx,
                "name": case.case_name,
                "pre": (case.precondition or "")[:50],
                "steps": (case.steps or "")[:100],
                "expect": (case.expected or "")[:50]
            })
            
        prompt = f"""
        你是一个分类引擎。请将以下测试用例归类到合适的功能模块。
        
        【重要指令】
        1. 仅输出纯 JSON 字符串（列表格式）。
        2. 严禁输出 Python 代码或 Markdown。
        3. 模块名称必须为中文。
        
        输入列表 (JSON):
        {json.dumps(batch_input, ensure_ascii=False)}
        
        示例输出：
        [
            {{"id": 0, "module": "登录模块"}},
            {{"id": 1, "module": "支付中心"}}
        ]
        """
        
        try:
            response = await llm_client.achat_completion([{"role": "user", "content": prompt}], response_format=list)
            
            if not isinstance(response, list):
                 # Fallback parsing
                 try:
                    # sometimes it might be wrapped in a dict key like "modules": [...]
                    if isinstance(response, dict):
                        response = list(response.values())[0]
                    else:
                        response = json.loads(str(response))
                 except:
                     logger.error("Failed to parse batch tagging response")
                     return

            # Map results back to cases
            if isinstance(response, list):
                for item in response:
                    if not isinstance(item, dict): continue
                    
                    local_id = item.get("id")
                    module_name = item.get("module")
                    
                    if local_id is not None and 0 <= local_id < len(batch) and module_name:
                        batch[local_id].module = module_name
                        batch[local_id].module_confidence = 0.9 # High confidence for LLM
                        
        except Exception as e:
            logger.error(f"Batch tagging failed: {e}")
            # Leave as default (None or existing)

module_tagger = ModuleTagger()
