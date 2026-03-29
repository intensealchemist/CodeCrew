import os
import sys
import uuid
import json
import asyncio
import io
from typing import Dict
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import uvicorn
import shutil
import zipfile

app = FastAPI(title="CodeCrew API")

# In-memory stores for streaming and state
job_queues: Dict[str, asyncio.Queue] = {}
job_status: Dict[str, dict] = {}
OUTPUT_BASE = os.path.abspath("./output")


class GenerateRequest(BaseModel):
    task: str
    llm_provider: str = "free_ha"


class QueueStream(io.TextIOBase):
    def __init__(self, queue: asyncio.Queue, original_stdout):
        self.queue = queue
        self.original_stdout = original_stdout

    def write(self, data):
        self.original_stdout.write(data)
        if data.strip():
            # Send standard stdout lines as 'log' events
            try:
                self.queue.put_nowait({"type": "log", "message": data})
            except asyncio.QueueFull:
                pass
        return len(data)

    def flush(self):
        self.original_stdout.flush()


def _save_job_state(job_id: str, state: dict):
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    os.makedirs(job_dir, exist_ok=True)
    with open(os.path.join(job_dir, "job_state.json"), "w") as f:
        json.dump(state, f)


async def run_pipeline_job(job_id: str, task: str, llm_provider: str):
    from codecrew.pipeline import CodeCrewPipeline
    
    state = {"status": "running", "task": task, "current_agent": None, "llm_provider": llm_provider}
    job_status[job_id] = state
    _save_job_state(job_id, state)
    
    output_dir = os.path.join(OUTPUT_BASE, job_id)
    queue = job_queues[job_id]
    
    original_stdout = sys.stdout
    sys.stdout = QueueStream(queue, original_stdout)
    
    try:
        previous_llm_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = llm_provider
        pipeline = CodeCrewPipeline(output_dir=output_dir, human_override=False)
        pipeline.run(task=task)
        
        state["status"] = "completed"
        job_status[job_id] = state
        _save_job_state(job_id, state)
        
        queue.put_nowait({"type": "job_status", "status": "completed"})
        queue.put_nowait({"type": "files_ready"})
        queue.put_nowait({"type": "done"})
        
    except Exception as e:
        state["status"] = "failed"
        state["error_message"] = str(e)
        job_status[job_id] = state
        _save_job_state(job_id, state)
        
        queue.put_nowait({"type": "job_status", "status": "failed"})
        queue.put_nowait({"type": "error", "message": str(e)})
        queue.put_nowait({"type": "done"})
    finally:
        if previous_llm_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_llm_provider
        sys.stdout = original_stdout


@app.post("/api/generate")
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job_queues[job_id] = asyncio.Queue()
    
    background_tasks.add_task(run_pipeline_job, job_id, request.task, request.llm_provider)
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id in job_status:
        return job_status[job_id]
    
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    state_file = os.path.join(job_dir, "job_state.json")
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
            
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request):
    # If job is already done and not in memory, just return done
    if job_id not in job_queues:
        job_dir = os.path.join(OUTPUT_BASE, job_id)
        if os.path.exists(job_dir):
            async def single_event():
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(single_event(), media_type="text/event-stream")
        raise HTTPException(status_code=404, detail="Job not found")

    queue = job_queues[job_id]

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "done":
                    break
            except Exception:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

@app.get("/api/jobs/{job_id}/files")
async def get_files(job_id: str):
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found")
        
    files_list = []
    for root, dirs, files in os.walk(job_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "node_modules"]]
        for f in files:
            if f == "job_state.json":
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, job_dir).replace("\\", "/")
            files_list.append(rel_path)
            
    return {"files": files_list}

@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id: str):
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found")
        
    zip_path = os.path.join(OUTPUT_BASE, f"{job_id}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(job_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "node_modules"]]
            for f in files:
                if f == "job_state.json":
                    continue
                file_path = os.path.join(root, f)
                archive_name = os.path.relpath(file_path, job_dir)
                zipf.write(file_path, archive_name)
                
    return FileResponse(zip_path, media_type="application/zip", filename=f"codecrew_{job_id}.zip")

def serve():
    # Helper to start uvicorn
    uvicorn.run("codecrew.server:app", host="0.0.0.0", port=8000, reload=True)
