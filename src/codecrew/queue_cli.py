import argparse
import sys
import os
import uuid
from dotenv import load_dotenv

# Ensure environment is loaded so REDIS_URL is available
load_dotenv(override=True)

def submit():
    """CLI to submit a task to the queue."""
    parser = argparse.ArgumentParser(description="Submit a background CodeCrew task")
    parser.add_argument("--task", type=str, required=True, help="The task description")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save output")
    args = parser.parse_args()
    
    from codecrew.queue.tasks import run_codecrew_task
    
    # Generate a unique output dir if none provided so jobs don't clobber each other
    out_dir = args.output_dir
    if not out_dir:
        unique_id = uuid.uuid4().hex[:8]
        out_dir = os.path.join(os.getcwd(), f"output_{unique_id}")
        
    print(f"Submitting task to CodeCrew Queue...")
    print(f"Task: '{args.task}'")
    
    try:
        # Submit to Celery
        job = run_codecrew_task.delay(args.task, out_dir)
        print(f"\n✅ Job Submitted Successfully!")
        print(f"📋 Job ID: {job.id}")
        print(f"📁 Output will be saved to: {out_dir}")
        print(f"\nCheck status with: codecrew-status --job-id {job.id}")
    except Exception as e:
        print(f"\n❌ Failed to submit job. Is Redis running and REDIS_URL set in your .env?")
        print(f"Error: {e}")
        sys.exit(1)


def status():
    """CLI to check the status of a queued task."""
    parser = argparse.ArgumentParser(description="Check status of a CodeCrew background task")
    parser.add_argument("--job-id", type=str, required=True, help="The Job ID returned from codecrew-submit")
    args = parser.parse_args()
    
    # Import celery app
    from codecrew.queue.celery_app import app
    from celery.result import AsyncResult
    
    res = AsyncResult(args.job_id, app=app)
    
    print(f"📋 Job ID: {args.job_id}")
    print(f"🟢 State:  {res.state}")
    
    if res.state == "SUCCESS":
        result_data = res.result
        if isinstance(result_data, dict):
            print(f"📁 Output Directory: {result_data.get('output_dir')}")
            print(f"\n✨ Result Summary:\n{result_data.get('final_result', '')[:500]}...")
    elif res.state == "FAILURE":
        print(f"❌ Error: {res.result}")
    elif res.state == "RUNNING":
        meta = res.info or {}
        print(f"⏳ Status: {meta.get('status', 'Processing...')}")


def worker():
    """CLI to start the Celery worker."""
    print("🔥 Starting CodeCrew Background Worker...")
    print("⚠️  Ensure you only run ONE instance of this worker to protect your free API rate limits!")
    
    # We use subprocess to run the celery command properly within the user's environment
    import subprocess
    cmd = [
        "celery",
        "-A", "codecrew.queue.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=1",
        "--pool=solo" # Best for Windows compatibility and simple execution
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nWorker shutting down...")
    except FileNotFoundError:
        print("\n❌ Celery command not found. Did you install dependencies with `pip install -e .[queue]`?")
        sys.exit(1)
