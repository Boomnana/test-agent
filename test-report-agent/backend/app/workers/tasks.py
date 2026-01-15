import asyncio
from celery import shared_task
from app.services.ingest.service import ingest_service
from app.services.ingest.tagging import module_tagger
from app.services.analytics.stats import stats_service
from app.services.defects.extractor import defect_extractor
from app.services.defects.clustering import defect_clusterer
from app.db.session import AsyncSessionLocal
from app.models.testcase import TestCase
from app.models.job import Job
from app.core.logging import get_logger
import os

logger = get_logger("worker")

# Helper to run async code in celery
def run_async(coro):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # This handles nested loops if needed, but usually celery workers are sync
        # Use asyncio.run() if in a fresh thread
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

@shared_task(name="process_job_pipeline")
def process_job_pipeline(job_id: str, file_path: str):
    """
    Orchestrates the entire pipeline. 
    In a real system, this would be a chain of tasks. 
    For V1 simplicity, we run steps sequentially in one task or chain them.
    Here we implement a monolithic wrapper for simplicity of the demo, 
    but ideally it should be Chained.
    """
    logger.info(f"Starting pipeline for Job {job_id}")
    
    # We need to interact with DB. Since Celery is sync, we need a sync wrapper or run async.
    # For simplicity, we will instantiate services that might use DB.
    # However, our services defined above return objects in memory.
    # We should persist them.
    
    try:
        # Step 1: Ingest
        raw_cases_dicts = ingest_service.parse_excel(file_path, job_id)
        
        # Convert dicts to ORM objects (in memory for now)
        cases = [TestCase(**d) for d in raw_cases_dicts]
        logger.info(f"Ingested {len(cases)} cases")
        
        # Step 2: Module Tagging
        cases = module_tagger.tag_cases_with_rules(cases)
        cases = module_tagger.tag_unknown_with_llm(cases)
        
        # Step 3: Stats
        stats = stats_service.compute_stats(cases)
        
        # Step 4: Defect Extraction
        defects = defect_extractor.extract_defect_facts(cases)
        
        # Step 5: Clustering
        clusters = defect_clusterer.cluster_and_summarize(defects, job_id)
        
        # Step 6: JSON Result
        result = {
            "job_id": job_id,
            "stats": stats,
            "defects": defects,
            "clusters": clusters,
        }
        logger.info(f"Job {job_id} completed.")
        return {"status": "completed", "result": result}

    except Exception as e:
        logger.error(f"Job failed: {e}")
        return {"status": "failed", "error": str(e)}
