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
            prompt = f"""
            你是一名资深测试工程师，请对下面的失败用例进行缺陷事实抽取，生成高质量、便于后续聚类分析的结构化信息。

            【输入用例】
            - 用例标题: {case.case_name}
            - 步骤: {case.steps}
            - 预期结果: {case.expected}
            - 实际结果: {case.actual}
            - 备注: {case.remark}

            【输出要求】
            1. 仅输出一个合法的 JSON 字符串，不要包含任何 Markdown 代码块、解释或自然语言说明。
            2. 所有字段必须使用中文描述，severity_guess 除外。
            3. 如果在 JSON 字符串中需要出现双引号，请务必进行转义，或者改用单引号，确保整体是可被解析的合法 JSON。

            【字段语义说明】
            1) phenomenon
               - 用一句话概括缺陷现象，格式推荐：
                 "【受影响模块】场景简述 - 具体错误现象"
               - 示例： "【订单结算】提交订单时 - 前端提示未知错误，订单未生成"
               - 必须同时包含：功能模块、操作场景、用户可见异常结果，尽量避免空泛词。

            2) observed_fact
               - 站在“日志/页面观察”的角度，客观描述系统真实行为。
               - 不要写推测或原因，只写可直接观察到的事实。

            3) hypothesis
               - 对可能根因的专业推测，推荐格式：
                 "类型: <根因类别>; 详情: <详细推断>"
               - 根因类别建议从以下集合中选择最贴近的一类：
                 "需求缺陷", "实现逻辑错误", "接口契约不一致", "配置错误",
                 "数据边界/空值处理缺陷", "并发/时序问题", "兼容性问题",
                 "环境/部署问题", "第三方依赖问题", "性能问题",
                 "安全问题", "测试数据问题", "用例设计问题", "其他"

            4) evidence
               - 使用字符串数组，每个元素是一条可以支持上述推测的“证据片段”。
               - 可以来自步骤描述、实际结果、备注中的关键语句，尽量保持原文引用。

            5) repro_steps
               - 用最少的步骤给出“从零开始可以稳定复现该缺陷”的操作路径。
               - 需要是完整的、多步的自然语言描述，而不是简单复述标题。

            6) severity_guess
               - 用以下枚举值之一表示严重等级： "Critical", "Major", "Minor"。
               - 参考标准：
                 - Critical: 核心业务流程不可用，或造成严重数据错误/安全风险。
                 - Major: 主要功能受影响，有明显业务价值损失但仍可局部绕过。
                 - Minor: 次要功能、展示问题或对业务影响有限的缺陷。

            【JSON 输出结构】
            {{
              "phenomenon": "简要但信息密集的中文描述",
              "observed_fact": "只包含可观察事实的中文描述",
              "hypothesis": "包含根因类别和详细说明的中文描述",
              "evidence": ["证据文本1", "证据文本2"],
              "repro_steps": "可直接用于复现缺陷的中文步骤说明",
              "severity_guess": "Critical/Major/Minor 三选一"
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
