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
            defect_text_list.append(f"ID: {i} | 现象: {phenomenon}")
        
        defect_input = "\n".join(defect_text_list)

        prompt = f"""
        作为测试专家，请分析以下测试缺陷列表，并将它们根据语义相似性归类到不同的聚类中。
        
        【缺陷列表】
        {defect_input}
        
        【要求】
        1. 识别具有共同特征或根因的缺陷，将其归为一类。
        2. 每个缺陷必须且只能属于一个聚类。
        3. 如果某个缺陷无法归类，可以单独成一类。
        4. 请使用中文回答。
        
        【输出格式】
        请仅输出合法的 JSON 字符串，格式如下：
        {{
            "clusters": [
                {{
                    "cluster_name": "聚类名称 (简短)",
                    "summary": "聚类总结 (描述该类缺陷的共同特征)",
                    "risk_assessment": "风险评估 (该类缺陷对系统的潜在影响)",
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
                    
                    # Create Cluster Object
                    cluster = DefectCluster(
                        job_id=job_id,
                        cluster_name=cluster_data.get("cluster_name", "未知聚类"),
                        summary=cluster_data.get("summary", ""),
                        risk_assessment=cluster_data.get("risk_assessment", "")
                    )
                    
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
                        cluster_name="未分类缺陷",
                        summary="未能自动归类的其他缺陷。",
                        risk_assessment="需人工确认"
                    )
                    for d in unassigned_defects:
                        d.cluster = fallback_cluster
                    # fallback_cluster.defects = unassigned_defects # This relationship is usually managed by appending to list or setting attribute
                    clusters.append(fallback_cluster)
                    
            else:
                raise ValueError("LLM response missing 'clusters' key")
                
        except Exception as e:
            logger.error(f"LLM Clustering failed: {e}")
            # Fallback: Put everything in one cluster
            fallback_cluster = DefectCluster(
                job_id=job_id,
                cluster_name="全部缺陷 (自动聚类失败)",
                summary="由于AI服务异常，所有缺陷暂时归为一类。",
                risk_assessment="需人工评估"
            )
            for d in defects:
                d.cluster = fallback_cluster
            clusters.append(fallback_cluster)

        return clusters

defect_clusterer = DefectClusterer()
