import os
import sys
import uuid
import json
import asyncio
import io
import hashlib
from typing import Dict
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
import shutil
import zipfile
import re
from sqlalchemy.orm import Session

from codecrew.database import SessionLocal

# Import Database Models
from codecrew.database import engine, Base, get_db
from codecrew.models import User, Job as DBJob

load_dotenv(override=True)

# Generate SQLite Tables immediately on boot
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CodeCrew API")

# In-memory stores for streaming and state
job_queues: Dict[str, asyncio.Queue] = {}
job_status: Dict[str, dict] = {}
OUTPUT_BASE = os.path.abspath("./output")


class GenerateRequest(BaseModel):
    task: str
    llm_provider: str = "free_ha"
    token: str | None = None  # Optional initially so Next.js doesn't crash before UI updates

class AuthRequest(BaseModel):
    username: str
    password: str


def _get_user_id_from_token(token: str | None) -> int | None:
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    if not token.startswith("auth_"):
        return None
    parts = token.split("_")
    if len(parts) < 3:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class QueueStream(io.TextIOBase):
    def __init__(self, queue: asyncio.Queue, original_stdout, on_agent=None):
        self.queue = queue
        self.original_stdout = original_stdout
        self.on_agent = on_agent

    def write(self, data):
        try:
            self.original_stdout.write(data)
        except UnicodeEncodeError:
            target_encoding = getattr(self.original_stdout, "encoding", None) or "utf-8"
            safe_data = data.encode(target_encoding, errors="replace").decode(target_encoding, errors="replace")
            self.original_stdout.write(safe_data)
        marker = re.search(r"\[\[AGENT:([A-Za-z0-9_]+)\]\]", data)
        if marker:
            agent = marker.group(1)
            if self.on_agent:
                self.on_agent(agent)
            try:
                self.queue.put_nowait({"type": "agent", "agent": agent})
            except asyncio.QueueFull:
                pass
            return len(data)
        if data.strip():
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


def _list_generated_files(job_dir: str) -> list[str]:
    files_list: list[str] = []
    for root, dirs, files in os.walk(job_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "node_modules"]]
        for f in files:
            if f == "job_state.json":
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, job_dir).replace("\\", "/")
            files_list.append(rel_path)
    return files_list


async def run_pipeline_job(job_id: str, task: str, llm_provider: str):
    from codecrew.pipeline import CodeCrewPipeline

    selected_provider = llm_provider.strip() or os.getenv("LLM_PROVIDER", "free_ha").strip()
    state = {
        "status": "running",
        "task": task,
        "current_agent": None,
        "llm_provider": selected_provider,
        "requested_llm_provider": llm_provider,
    }
    job_status[job_id] = state
    _save_job_state(job_id, state)

    # Persist running status in DB (best effort)
    db = SessionLocal()
    try:
        db_job = db.query(DBJob).filter(DBJob.job_id == job_id).first()
        if db_job:
            db_job.status = "running"
            db.commit()
    finally:
        db.close()
    
    output_dir = os.path.join(OUTPUT_BASE, job_id)
    queue = job_queues[job_id]
    
    original_stdout = sys.stdout

    def handle_agent(agent: str):
        state["current_agent"] = agent
        job_status[job_id] = state
        _save_job_state(job_id, state)

    sys.stdout = QueueStream(queue, original_stdout, on_agent=handle_agent)
    
    try:
        previous_llm_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = selected_provider
        pipeline = CodeCrewPipeline(output_dir=output_dir, human_override=False)
        await pipeline.run(task=task)
        generated_files = _list_generated_files(output_dir)
        if not generated_files:
            raise RuntimeError("Pipeline completed but generated no files")
        
        state["status"] = "completed"
        job_status[job_id] = state
        _save_job_state(job_id, state)

        db = SessionLocal()
        try:
            db_job = db.query(DBJob).filter(DBJob.job_id == job_id).first()
            if db_job:
                db_job.status = "completed"
                db.commit()
        finally:
            db.close()
        
        queue.put_nowait({"type": "job_status", "status": "completed"})
        queue.put_nowait({"type": "files_ready"})
        queue.put_nowait({"type": "done"})
        
    except Exception as e:
        state["status"] = "failed"
        state["error_message"] = str(e)
        job_status[job_id] = state
        _save_job_state(job_id, state)

        db = SessionLocal()
        try:
            db_job = db.query(DBJob).filter(DBJob.job_id == job_id).first()
            if db_job:
                db_job.status = "failed"
                db.commit()
        finally:
            db.close()
        
        queue.put_nowait({"type": "job_status", "status": "failed"})
        queue.put_nowait({"type": "error", "message": str(e)})
        queue.put_nowait({"type": "done"})
    finally:
        if previous_llm_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_llm_provider
        sys.stdout = original_stdout


@app.post("/api/register")
async def register(request: AuthRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user = User(
        username=request.username,
        hashed_password=get_password_hash(request.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User successfully registered", "user_id": user.id}

@app.post("/api/login")
async def login(request: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or user.hashed_password != get_password_hash(request.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    # In a full setup this would issue a JWT, for now it returns a pseudo-token mapping to the UID
    token = f"auth_{user.id}_{hashlib.md5(user.username.encode()).hexdigest()}"
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/me/jobs")
async def list_my_jobs(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")
    user_id = _get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    jobs = (
        db.query(DBJob)
        .filter(DBJob.user_id == user_id)
        .order_by(DBJob.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "task": j.task_prompt,
                "llm_provider": j.llm_provider,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@app.get("/api/me")
async def get_me(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")
    user_id = _get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    running = db.query(DBJob).filter(DBJob.user_id == user_id, DBJob.status == "running").count()
    completed = db.query(DBJob).filter(DBJob.user_id == user_id, DBJob.status == "completed").count()
    failed = db.query(DBJob).filter(DBJob.user_id == user_id, DBJob.status == "failed").count()
    pending = db.query(DBJob).filter(DBJob.user_id == user_id, DBJob.status == "pending").count()

    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "job_summary": {
            "running": running,
            "completed": completed,
            "failed": failed,
            "pending": pending,
        },
    }


@app.post("/api/generate")
async def generate(request: Request, payload: GenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job_queues[job_id] = asyncio.Queue()
    
    # Resolve the pseudo-user if a token is provided
    user_id = None
    if payload.token and payload.token.startswith("auth_"):
        try:
            user_id = int(payload.token.split("_")[1])
        except ValueError:
            pass

    if user_id is None:
        auth = request.headers.get("Authorization")
        user_id = _get_user_id_from_token(auth)

    # Log Job Creation in Database
    db_job = DBJob(
        job_id=job_id,
        user_id=user_id,
        task_prompt=payload.task,
        llm_provider=payload.llm_provider,
        status="pending"
    )
    db.add(db_job)
    db.commit()
    
    background_tasks.add_task(run_pipeline_job, job_id, payload.task, payload.llm_provider)
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
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                # Send an SSE comment ping to prevent proxy connection timeouts (Undici 300s timeout)
                yield ": keep-alive\n\n"
            except Exception:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

@app.get("/api/jobs/{job_id}/files")
async def get_files(job_id: str):
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found")

    files_list = _list_generated_files(job_dir)
    return {"files": files_list}


@app.get("/api/jobs/{job_id}/files/{file_path:path}")
async def get_file_content(job_id: str, file_path: str):
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found")

    target_path = os.path.abspath(os.path.join(job_dir, file_path))
    if os.path.commonpath([job_dir, target_path]) != job_dir:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not UTF-8 text")

    return {"content": content}

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


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    db_job = db.query(DBJob).filter(DBJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If this job is tied to a user, require matching token.
    if db_job.user_id is not None:
        user_id = _get_user_id_from_token(request.headers.get("Authorization"))
        if not user_id or user_id != db_job.user_id:
            raise HTTPException(status_code=403, detail="Not allowed")

    # Best-effort: remove in-memory queues/status.
    job_queues.pop(job_id, None)
    job_status.pop(job_id, None)

    # Delete output artifacts.
    job_dir = os.path.join(OUTPUT_BASE, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)

    zip_path = os.path.join(OUTPUT_BASE, f"{job_id}.zip")
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except OSError:
            pass

    db.delete(db_job)
    db.commit()
    return {"deleted": True, "job_id": job_id}

def serve():
    # Helper to start uvicorn
    uvicorn.run("codecrew.server:app", host="0.0.0.0", port=8000, reload=True)
