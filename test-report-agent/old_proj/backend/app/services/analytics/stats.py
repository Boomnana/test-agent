from typing import List, Dict, Any
from app.models.testcase import TestCase
from collections import Counter

class StatsService:
    def compute_stats(self, cases: List[TestCase]) -> Dict[str, Any]:
        total = len(cases)
        if total == 0:
            return {}
            
        result_counts = Counter(c.normalized_result for c in cases)
        module_counts = Counter(c.module for c in cases)
        
        # Calculate Pass Rate
        pass_count = result_counts.get("Pass", 0)
        pass_rate = (pass_count / total) * 100 if total > 0 else 0
        
        # Top Failed Modules
        failed_cases = [c for c in cases if c.normalized_result in ["Fail", "Blocked"]]
        failed_modules = Counter(c.module for c in failed_cases)
        
        stats = {
            "total_cases": total,
            "results": dict(result_counts),
            "pass_rate": round(pass_rate, 2),
            "modules": dict(module_counts),
            "top_failed_modules": dict(failed_modules.most_common(5))
        }
        return stats

stats_service = StatsService()
