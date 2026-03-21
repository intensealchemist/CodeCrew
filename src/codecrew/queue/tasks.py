import os
from celery.utils.log import get_task_logger
from codecrew.queue.celery_app import app

logger = get_task_logger(__name__)

@app.task(bind=True, name="run_codecrew_task", acks_late=True, track_started=True)
def run_codecrew_task(self, task_description: str, output_dir: str):
    """
    Background job that runs the full CodeCrew execution.
    Runs sequentially on the worker to protect LLM rate limits.
    """
    logger.info(f"Starting CodeCrew job {self.request.id}")
    logger.info(f"Task: {task_description}")
    logger.info(f"Output Directory: {output_dir}")
    
    # Needs to be imported here to avoid circular dependencies
    from codecrew.crew import CodeCrewCrew
    
    # Force output directory specifically for this job
    job_output_dir = os.path.abspath(output_dir)
    os.makedirs(job_output_dir, exist_ok=True)
    
    try:
        crew_instance = CodeCrewCrew(
            output_dir=job_output_dir,
            human_override=False # Background tasks cannot be interactive
        )
        
        # Update Celery state to let users see it's actively processing
        self.update_state(state="RUNNING", meta={"task": task_description, "status": "Agents are thinking..."})
        
        result = crew_instance.crew().kickoff(
            inputs={"task": task_description}
        )
        
        logger.info(f"Successfully completed job {self.request.id}")
        
        # Attempt to pull out the result string or just return success
        final_result = getattr(result, "raw", str(result))
        
        return {
            "status": "success",
            "output_dir": job_output_dir,
            "final_result": final_result
        }
        
    except Exception as e:
        logger.error(f"Job {self.request.id} failed: {str(e)}")
        # Raise it so Celery marks the state as FAILURE
        raise e
