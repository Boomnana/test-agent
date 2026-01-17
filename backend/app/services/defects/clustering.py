import asyncio
from typing import List, Dict, Any
from app.models.defect import DefectAnalysis, DefectCluster
from app.core.logging import get_logger
from app.services.llm.client import llm_client

logger = get_logger("defect_clustering")

class DefectClusterer:
    async def cluster_and_summarize_async(self, defects: List[DefectAnalysis], job_id: str) -> List[DefectCluster]:
        if not defects:
            return []

        # 1. Prepare data for LLM
        # Use index as a temporary ID since database IDs might not be set yet
        defect_map = {str(i): d for i, d in enumerate(defects)}
        
        defect_text_list = []
        for i, d in enumerate(defects):
            phenomenon = d.phenomenon or "无描述"
            severity = d.severity_guess or "未知"
            module = ""
            if getattr(d, "testcase", None) is not None:
                module = getattr(d.testcase, "module", "") or ""
            module_text = module or "未知模块"
            defect_text_list.append(f"ID: {i} | 模块: {module_text} | 严重级别: {severity} | 现象: {phenomenon}")
        
        defect_input = "\n".join(defect_text_list)

        prompt = f"""
        你是一名资深测试架构师，负责对本次测试中发现的所有缺陷进行深度分析与智能聚类。请根据以下缺陷列表，依据根本原因、表现现象或影响模块的语义相似性进行合理分组。

        【缺陷列表】
        {defect_input}

        【关键原则：避免孤立缺陷】
        1. 绝不轻易归为孤立：仅当缺陷描述完全缺失可分析的技术要素（如“系统错误”“功能异常”“无法复现”且无上下文）时，才归入“待确认/孤立缺陷”。
        2. 优先聚类，再兜底：
           - 若缺陷描述包含业务模块（如“支付”“用户中心”）、错误现象（如“超时”“404”）或错误码，必须尝试聚类，不得直接归为孤立。
           - 例如：“登录失败”→聚类到“登录功能异常”；“支付超时”→聚类到“支付接口超时”。
        3. 相似性判断标准：
           - 相同模块 + 相似现象 = 可聚类（如“支付超时”和“支付回调丢失”→同属“支付异常”）。
           - 相同现象但不同模块 = 不合并（如“登录超时”和“注册超时”→不同聚类）。
           - 模糊描述：优先基于可提取的关键词、模块、用例路径进行聚类，而不是直接归为孤立。

        【聚类原则】
        1. 归属原则：每个缺陷必须归属一个聚类，禁止默认孤立。仅当描述无任何技术要素时，才归入“待确认/孤立缺陷”聚类。
        2. 粒度控制：
           - 聚类总数应在 3～7 个（不含“待确认/孤立缺陷”）。
           - 若某聚类包含超过 7 个缺陷，检查是否可按错误码、子模块或更细颗粒度拆分。
        3. 孤立缺陷处理：
           - 仅限少量缺陷可归为“待确认/孤立缺陷”；如确实比例偏高，应在对应聚类的 summary 中说明“描述模糊/信息不足”。
           - 对这些缺陷，仍需给出风险评估和改进建议（例如：建议补充日志、抓包或截图）。

        【输出字段含义】
        - cluster_name：简明聚类名称（建议 ≤12 字），推荐形式为“<模块>/<领域> - <问题类型>”，例如“支付/结算 - 接口超时问题”。
        - summary：用 1～2 句话概括聚类内缺陷的共同特征（典型场景 + 常见现象）。
        - root_cause_hypothesis：对可能的根本原因进行专业推测，即使不 100% 准确，也要给出合理假设，例如“可能因缓存未刷新导致状态不同步”。
        - risk_assessment：用“高/中/低 + 简短说明”的形式给出风险评估，例如“高 - 阻断核心支付流程，影响下单转化”。
        - action_suggestion：给出具体、可执行的改进建议，建议可以直接用作 Jira 任务标题，例如“为订单状态更新接口增加重试和幂等校验”。

        【对模糊/低质量缺陷的处理】
        - 若某条缺陷描述较模糊（如只写“功能异常”），优先结合模块信息、现象关键词尝试归类到最相近的聚类。
        - 仅当无法找到任何合理归属时，才放入“待确认/孤立缺陷”聚类，并在 summary 中说明“描述缺失关键信息”。
        - 对这类缺陷的 action_suggestion 中，给出“建议补充日志或截图”等后续动作提示。

        【输出格式】
        请严格输出单行、标准、可直接由 Python json.loads() 解析的 JSON 字符串。禁止包含任何解释、Markdown 或额外文本。所有字符串中的双引号必须转义为\\"。

        JSON 结构示例（仅示意，实际返回内容需结合输入缺陷列表）：
        {{
          "clusters": [
            {{
              "cluster_name": "简明聚类名称",
              "summary": "共同特征描述（1～2句）",
              "root_cause_hypothesis": "尽力推断的根本原因（避免占位语）",
              "risk_assessment": "高/中/低 + 影响说明",
              "action_suggestion": "具体、可执行的改进建议（可直接作为 Jira 标题）",
              "defect_ids": ["ID1", "ID2"]
            }}
          ]
        }}
        """

        clusters = []
        
        try:
            # 2. Call LLM to cluster and summarize
            response = await llm_client.achat_completion([{"role": "user", "content": prompt}], response_format=dict)
            
            if isinstance(response, dict) and "clusters" in response:
                llm_clusters = response["clusters"]
                
                # Track which defects have been assigned to avoid duplicates (though LLM instruction says exclusive)
                assigned_indices = set()
                
                for cluster_data in llm_clusters:
                    defect_ids = cluster_data.get("defect_ids", [])
                    cluster = DefectCluster(
                        job_id=job_id,
                        cluster_name=cluster_data.get("cluster_name", "未知聚类"),
                        summary=cluster_data.get("summary", ""),
                        risk_assessment=cluster_data.get("risk_assessment", "")
                    )
                    setattr(cluster, "root_cause_hypothesis", cluster_data.get("root_cause_hypothesis", ""))
                    setattr(cluster, "action_suggestion", cluster_data.get("action_suggestion", ""))
                    cluster_defects = []
                    for did in defect_ids:
                        did_str = str(did)
                        if did_str in defect_map:
                            d = defect_map[did_str]
                            d.cluster = cluster
                            cluster_defects.append(d)
                            assigned_indices.add(did_str)
                    
                    # Only add cluster if it has defects
                    if cluster_defects:
                        cluster.defects = cluster_defects # Assuming ORM allows this or we handle it later
                        clusters.append(cluster)
                
                # 3. Handle unassigned defects (Fallback)
                unassigned_defects = []
                for i in range(len(defects)):
                    if str(i) not in assigned_indices:
                        unassigned_defects.append(defect_map[str(i)])
                
                if unassigned_defects:
                    fallback_cluster = DefectCluster(
                        job_id=job_id,
                        cluster_name="待确认/孤立缺陷",
                        summary="部分缺陷描述缺失关键信息，无法可靠判断模块或根因，暂归为待确认/孤立缺陷。",
                        risk_assessment="中 - 具体风险待根据补充信息评估"
                    )
                    setattr(fallback_cluster, "root_cause_hypothesis", "当前缺陷描述信息不足，仅能判断存在异常，无法可靠推断具体根本原因。")
                    setattr(fallback_cluster, "action_suggestion", "请补充相关日志、请求参数、截图或更详细的缺陷描述后，再进行重新归类与评估。")
                    for d in unassigned_defects:
                        d.cluster = fallback_cluster
                    clusters.append(fallback_cluster)
                    
            else:
                raise ValueError("LLM response missing 'clusters' key")
                
        except Exception as e:
            logger.error(f"LLM Clustering failed: {e}")
            # Fallback: Put everything in one cluster
            fallback_cluster = DefectCluster(
                job_id=job_id,
                cluster_name="全部缺陷 (自动聚类失败)",
                summary="由于 AI 服务异常，本次未能完成自动聚类，所有缺陷暂时归为一类。",
                risk_assessment="中 - 建议人工评估各缺陷的业务影响与优先级"
            )
            setattr(fallback_cluster, "root_cause_hypothesis", "聚类阶段调用 AI 服务失败，无法生成聚类和根因假设，仅能提供缺陷原始列表。")
            setattr(fallback_cluster, "action_suggestion", "请暂时人工审阅全部缺陷列表，手工完成聚类和优先级评估，或在恢复 AI 服务后重新执行聚类。")
            for d in defects:
                d.cluster = fallback_cluster
            clusters.append(fallback_cluster)

        return clusters

defect_clusterer = DefectClusterer()
