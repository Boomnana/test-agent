import os
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from app.services.llm.client import llm_client
from typing import Dict, Any, List

class ReportGenerator:
    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate_summary(self, stats: Dict, clusters: List, suspicious_cases: List = None) -> str:
        # Use LLM to generate the executive summary text
        suspicious_info = ""
        if suspicious_cases:
            suspicious_info = f"注意：在结果审计中发现了 {len(suspicious_cases)} 个疑似'假成功'（False Positive）的用例，请在报告中提及这一点。"

        prompt = f"""
        基于以下测试数据撰写一份测试报告执行总结：
        
        统计数据: {stats}
        缺陷聚类: {[c.cluster_name for c in clusters]}
        {suspicious_info}
        
        请重点关注：
        1. 整体质量评估。
        2. 关键风险领域。
        3. 改进建议。
        4. (如果有) 数据可信度风险。
        
        【重要指令】
        - 直接输出 HTML 段落格式（例如 <p>...</p>）。
        - 必须使用中文。
        - 严禁输出 Python 代码或 Markdown。
        - 不要包含任何其他解释性文字，只输出 HTML 内容。
        """
        try:
            summary = llm_client.chat_completion([{"role": "user", "content": prompt}])
            summary = str(summary).strip()
            # Clean markdown artifacts if present
            if summary.startswith("```"):
                summary = summary.split("\n", 1)[1]
            if summary.endswith("```"):
                summary = summary.rsplit("\n", 1)[0]
            summary = summary.replace("```html", "").replace("```", "")
            return summary
        except:
            return "<p>总结生成失败。</p>"

    def render_report(self, job_id: str, stats: Dict, defects: List, clusters: List, suspicious_cases: List, all_cases: List, output_path: str):
        summary = self.generate_summary(stats, clusters, suspicious_cases)
        template = self.env.get_template('report.html')
        
        html_content = template.render(
            job_id=job_id,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary_text=summary,
            stats=stats,
            defects=defects,
            clusters=clusters,
            suspicious_cases=suspicious_cases,
            all_cases=all_cases
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path

report_generator = ReportGenerator()
