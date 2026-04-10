import ast
import os
import subprocess
import json
import re
import io
import sys
import asyncio
from contextlib import redirect_stdout
import agentscope
from agentscope.message import Msg

try:
    from agentscope.agent import UserAgent
except ImportError:
    from agentscope.agents import UserAgent

from codecrew.model_configs import build_formatter, build_role_models
from codecrew.tools import build_toolkit
from codecrew.tools.file_writer import write_file
from codecrew.rag import RAGStore
from codecrew.agents import (
    create_researcher,
    create_spec_validator,
    create_architect,
    create_file_planner,
    create_coder,
    create_qa_agent,
    create_readme_agent,
)

import inspect
import logging

logger = logging.getLogger(__name__)


class _TeeStream(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase):
        self._streams = streams

    def write(self, data):
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self._streams:
            stream.flush()

# ── Stage labels that trigger RAG indexing after they complete ────────────────
#   "text"  → index the agent's text output under this doc_id
#   "files" → bulk-index the output_dir (used after Coder)
#   None    → no automatic indexing for this stage
_RAG_INDEX: dict[str, str | None] = {
    "Researcher":   "spec",
    "SpecValidator": "spec_validated",
    "FilePlanner":  "file_plan",
    "Architect":    "files",   # ARCHITECTURE.md will be on disk; index directory
    "Coder":        "files",   # index all generated code files
}


class CodeCrewPipeline:
    def __init__(self, output_dir: str = "./output", human_override: bool = False):
        self.output_dir = os.path.abspath(output_dir)
        self.human_override = human_override

    def _build_stage_message(self, stage_label: str, task: str, stage_outputs: dict[str, str]) -> Msg:
        researcher_output = stage_outputs.get("Researcher", "")
        validated_spec = stage_outputs.get("SpecValidator", researcher_output)
        architecture_output = stage_outputs.get("Architect", "")
        file_plan = stage_outputs.get("FilePlanner", "")
        qa_output = stage_outputs.get("QAAgent", "")

        if stage_label == "Researcher":
            content = f"Original Task: {task}"
        elif stage_label == "SpecValidator":
            content = (
                f"Original Task: {task}\n\n"
                "Draft Technical Specification:\n"
                f"{researcher_output}"
            )
        elif stage_label == "Architect":
            content = (
                f"Original Task: {task}\n\n"
                "Validated Technical Specification:\n"
                f"{validated_spec}"
            )
        elif stage_label == "FilePlanner":
            # Try to read ARCHITECTURE.md if it exists, otherwise fallback to the raw output
            arch_file = os.path.join(self.output_dir, "ARCHITECTURE.md")
            if os.path.exists(arch_file):
                try:
                    with open(arch_file, "r", encoding="utf-8") as f:
                        architecture_content = f.read()
                except Exception:
                    architecture_content = architecture_output
            else:
                architecture_content = architecture_output

            content = (
                f"Original Task: {task}\n\n"
                "Validated Technical Specification:\n"
                f"{validated_spec}\n\n"
                f"Architecture Blueprint:\n{architecture_content}\n\n"
                "CRITICAL: You MUST output ONLY a valid JSON array of file paths. No conversation, no code, no questions."
            )
        elif stage_label == "Coder":
            content = (
                f"Original Task: {task}\n\n"
                f"Ordered File Plan (JSON array):\n{file_plan}\n\n"
                "Relevant architecture/spec context is available through retrieve_context."
            )
        elif stage_label == "QAAgent":
            content = (
                f"Original Task: {task}\n\n"
                f"Ordered File Plan (JSON array):\n{file_plan}\n\n"
                "Run full QA checks against generated files."
            )
        elif stage_label == "ReadmeAgent":
            content = (
                f"Original Task: {task}\n\n"
                f"Ordered File Plan (JSON array):\n{file_plan}\n\n"
                f"QA Summary:\n{qa_output}"
            )
        elif stage_label == "User":
            if stage_outputs:
                latest_stage, latest_output = list(stage_outputs.items())[-1]
                content = (
                    f"Original Task: {task}\n\n"
                    f"Latest Stage: {latest_stage}\n"
                    f"Output:\n{latest_output}\n\n"
                    "Provide approval or revision instructions."
                )
            else:
                content = f"Original Task: {task}"
        else:
            content = f"Original Task: {task}"

        return Msg(name="user", content=content, role="user")

    def _generated_files_snapshot(self) -> set[str]:
        tracked: set[str] = set()
        for root, dirs, files in os.walk(self.output_dir):
            dirs[:] = [d for d in dirs if d != ".git"]
            for file_name in files:
                if file_name == "job_state.json":
                    continue
                full_path = os.path.join(root, file_name)
                rel = self._normalize_project_path(os.path.relpath(full_path, self.output_dir))
                tracked.add(rel)
        return tracked

    def _normalize_project_path(self, path: str) -> str:
        normalized = str(path or "").strip().replace("\\", "/")
        if not normalized:
            return ""
        normalized = normalized.lstrip("./")
        normalized = normalized.removeprefix("project-root/")
        normalized = re.sub(r"/{2,}", "/", normalized)
        if not normalized or normalized == ".":
            return ""
        return normalized

    def _build_coder_file_message(
        self,
        task: str,
        file_plan: list[str],
        target_file: str,
        context: str = "",
        attempt: int = 1,
        previous_response: str = "",
    ) -> Msg:
        content = (
            f"Original Task: {task}\n\n"
            f"Ordered File Plan (JSON array):\n{json.dumps(file_plan, ensure_ascii=False)}\n\n"
            f"Current Target File: {target_file}\n\n"
        )
        if context:
            content += f"=== AUTO-RETRIEVED CONTEXT ===\n{context}\n============================\n\n"
        
        content += (
            "Implement exactly this one file in this call based on the retrieved context above. "
            "You may call retrieve_context once ONLY if the auto-retrieved context is insufficient. "
            f"Your primary action must be calling write_file or execution_loop for {target_file}. Do not move to any other file."
        )
        if attempt > 1:
            content += (
                f"\n\nPrevious attempt {attempt - 1} did not write {target_file}. "
                "Do not call retrieve_context again unless you have not already used it for this file. "
                f"Your next tool action must create {target_file}."
            )
        if previous_response:
            content += f"\n\nPrevious coder output for this file:\n{previous_response}"
        return Msg(name="user", content=content, role="user")

    def _parse_file_plan_layers(self, raw_plan: str) -> list[list[str]]:
        text = (raw_plan or "").strip()
        if not text:
            return []
        candidates: list[str] = [text]
        if "```" in text:
            candidates.extend(part.strip() for part in text.split("```") if part.strip())
        candidates.extend(match.group(0) for match in re.finditer(r"\[[\s\S]*?\]", text))

        best: list[list[str]] = []
        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, list):
                continue
            
            # Check if it's already an array of arrays
            if data and isinstance(data[0], list):
                parsed_layers: list[list[str]] = []
                seen: set[str] = set()
                for layer in data:
                    if not isinstance(layer, list):
                        continue
                    parsed_layer: list[str] = []
                    for item in layer:
                        if not isinstance(item, str):
                            continue
                        normalized = self._normalize_project_path(item)
                        if normalized and normalized not in seen:
                            parsed_layer.append(normalized)
                            seen.add(normalized)
                    if parsed_layer:
                        parsed_layers.append(parsed_layer)
                
                flat_len = sum(len(layer) for layer in parsed_layers)
                if flat_len > sum(len(layer) for layer in best):
                    best = parsed_layers
            else:
                # Fallback: it's a flat list, put everything in one layer (or distinct layers to keep order)
                # To be safe, we'll put them in strict sequential layers if they didn't follow instructions
                parsed_layers: list[list[str]] = []
                seen: set[str] = set()
                for item in data:
                    if not isinstance(item, str):
                        continue
                    normalized = self._normalize_project_path(item)
                    if normalized and normalized not in seen:
                        parsed_layers.append([normalized])
                        seen.add(normalized)
                        
                if len(parsed_layers) > sum(len(layer) for layer in best):
                    best = parsed_layers

        if not best:
            fallback_layers: list[list[str]] = []
            seen_fallback: set[str] = set()
            for line in text.splitlines():
                line = line.strip().strip('`"-*,# ')
                if not line:
                    continue
                if re.match(r'^/?([a-zA-Z0-9_\-\.]+/)+[a-zA-Z0-9_\-\.]+$|^[a-zA-Z0-9_\-\.]*\.[a-zA-Z0-9_\-]+$', line) or line in ("Makefile", "Dockerfile"):
                    normalized = self._normalize_project_path(line)
                    if normalized and normalized not in seen_fallback:
                        fallback_layers.append([normalized])
                        seen_fallback.add(normalized)
            if fallback_layers:
                best = fallback_layers
                
        return best

    def _parse_file_plan(self, raw_plan: str) -> list[str]:
        return [
            path
            for layer in self._parse_file_plan_layers(raw_plan)
            for path in layer
        ]

    def _extract_coder_action_input_block(self, response_text: str, action_name: str) -> str:
        if not response_text:
            return ""
        pattern = re.compile(
            rf"Action:\s*{re.escape(action_name)}\s*[\r\n]+Action Input:\s*(.*?)(?=(?:[\r\n]+(?:Observation|Thought|Action):)|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(response_text)
        if not match:
            return ""
        return match.group(1).strip()

    def _decode_loose_string_literal(self, raw_value: str) -> str:
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            quote = value[0]
            try:
                return ast.literal_eval(value)
            except Exception:
                inner = value[1:-1]
                inner = inner.replace(f"\\{quote}", quote)
                inner = inner.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
                return inner
        return value

    def _parse_loose_write_file_action_input(self, action_input: str) -> tuple[str, str] | None:
        block = (action_input or "").strip()
        if not block:
            return None

        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            filepath = self._normalize_project_path(data.get("filepath", ""))
            content = data.get("content")
            if filepath and isinstance(content, str):
                return filepath, content

        filepath_match = re.search(
            r'["\']filepath["\']\s*[:=]\s*(["\'])(?P<filepath>.*?)\1',
            block,
            re.DOTALL,
        )
        content_match = re.search(
            r'["\']content["\']\s*[:=]\s*(?P<content>"[\s\S]*"|\'[\s\S]*\')\s*[\}\]]*\s*$',
            block,
            re.DOTALL,
        )
        if not filepath_match or not content_match:
            return None

        filepath = self._normalize_project_path(filepath_match.group("filepath"))
        content = self._decode_loose_string_literal(content_match.group("content"))
        if not filepath:
            return None
        return filepath, content

    def _recover_coder_write_from_response(self, target_file: str, response_text: str) -> bool:
        action_input = self._extract_coder_action_input_block(response_text, "write_file")
        if not action_input:
            return False

        parsed = self._parse_loose_write_file_action_input(action_input)
        if not parsed:
            return False

        filepath, content = parsed
        normalized_target = self._normalize_project_path(target_file)
        if filepath != normalized_target:
            logger.warning(
                "Skipping coder write recovery because response targeted %s instead of %s.",
                filepath,
                normalized_target,
            )
            return False

        result = write_file(filepath=filepath, content=content, base_dir=self.output_dir)
        if "Successfully wrote" not in result:
            logger.warning("Recovered coder write failed for %s: %s", normalized_target, result)
            return False

        logger.info("Recovered missing coder write for %s from response text.", normalized_target)
        return True

    def _extract_response_text(self, response, stage_log: str = "") -> str:
        raw_content = response.content if hasattr(response, "content") else response
        if isinstance(raw_content, str):
            response_text = raw_content
        else:
            try:
                response_text = json.dumps(raw_content, ensure_ascii=False)
            except Exception:
                response_text = str(raw_content)
        response_text = (response_text or "").strip()
        stage_log = (stage_log or "").strip()
        if stage_log and (not response_text or response_text in {"null", "{}", "[]", '""'}):
            return stage_log
        if stage_log and stage_log not in response_text:
            return f"{response_text}\n{stage_log}".strip()
        return response_text

    async def run(self, task: str) -> dict:
        studio_url = os.getenv("STUDIO_URL", "http://127.0.0.1:5000")
        use_studio = os.getenv("AGENTSCOPE_USE_STUDIO", "false").strip().lower() == "true"

        init_kwargs = {"project": "CodeCrew", "name": "Implementation"}
        if use_studio:
            init_kwargs["studio_url"] = studio_url

        agentscope.init(**init_kwargs)

        models = build_role_models()
        formatter = build_formatter()

        embed_url = os.getenv(
            "OLLAMA_EMBED_URL",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        rag = RAGStore.from_env(output_dir=self.output_dir)
        logger.info("RAGStore initialised: %s", rag)

        # ── Build toolkits (pass rag_store to roles that benefit) ────────────
        architect_toolkit = build_toolkit("architect", self.output_dir)
        coding_toolkit    = build_toolkit("coding",    self.output_dir, rag_store=rag)
        qa_toolkit        = build_toolkit("qa",        self.output_dir, rag_store=rag)
        docs_toolkit      = build_toolkit("docs",      self.output_dir, rag_store=rag)

        # ── Create agents ─────────────────────────────────────────────────────
        researcher     = create_researcher(models["reasoning"], formatter)
        spec_validator = create_spec_validator(models["structured"], formatter)
        architect      = create_architect(architect_toolkit, models["structured"], formatter)
        file_planner   = create_file_planner(models["structured"], formatter)
        coder          = create_coder(coding_toolkit, models["coding"], formatter)
        qa_agent       = create_qa_agent(qa_toolkit, models["qa"], formatter)
        readme_agent   = create_readme_agent(docs_toolkit, models["fast"], formatter)

        stage_agents = [
            ("Researcher",   researcher),
            ("SpecValidator", spec_validator),
            ("Architect",    architect),
            ("FilePlanner",  file_planner),
            ("Coder",        coder),
            ("QAAgent",      qa_agent),
            ("ReadmeAgent",  readme_agent),
        ]

        if self.human_override:
            user_agent = UserAgent(name="User")
            stage_agents = [
                ("Researcher",   researcher),
                ("SpecValidator", spec_validator),
                ("User",         user_agent),
                ("Architect",    architect),
                ("FilePlanner",  file_planner),
                ("User",         user_agent),
                ("Coder",        coder),
                ("QAAgent",      qa_agent),
                ("User",         user_agent),
                ("ReadmeAgent",  readme_agent),
            ]

        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  🚀 CodeCrew — Starting up")
        print(f"  📁 Output directory: {self.output_dir}")
        print(f"  🔍 RAG embed model : {embed_model} @ {embed_url}")
        print(f"  🧑 Human Override  : {'ON' if self.human_override else 'OFF'}")
        print(f"{'='*60}\n")

        stage_outputs: dict[str, str] = {}

        for stage_label, agent in stage_agents:
            print(f"[[AGENT:{stage_label}]]")
            if stage_label == "Coder":
                file_plan_layers = self._parse_file_plan_layers(stage_outputs.get("FilePlanner", ""))
                if not file_plan_layers:
                    raise RuntimeError("Could not parse file plan from FilePlanner output.")

                coder_logs: list[str] = []
                
                # We need a helper to run one file.
                async def _generate_single_file(target_file: str, flat_file_plan: list[str]):
                    current_files = self._generated_files_snapshot()
                    if target_file in current_files:
                        return f"## {target_file}\nFile already exists."
                        
                    # Pre-fetch semantic context
                    context_data = ""
                    if rag:
                        try:
                            # Using retrieve_structured to run RAG search in a background thread to prevent blocking
                            res = await asyncio.to_thread(rag.retrieve_structured, query=f"Implementation details and interfaces for {target_file}", n_results=3)
                            if res and res.hits:
                                context_data = "\n\n".join(hit.text for hit in res.hits)
                        except Exception as e:
                            logger.warning(f"Failed to pre-fetch context for {target_file}: {e}")

                    previous_response = ""
                    wrote_target = False
                    logs = []
                    for attempt in range(1, 4):
                        message = self._build_coder_file_message(
                            task=task,
                            file_plan=flat_file_plan,
                            target_file=target_file,
                            context=context_data,
                            attempt=attempt,
                            previous_response=previous_response,
                        )
                        stage_buffer = io.StringIO()
                        with redirect_stdout(_TeeStream(sys.stdout, stage_buffer)):
                            try:
                                response = agent(message)
                                if inspect.iscoroutine(response):
                                    response = await response
                            except Exception as e:
                                logger.error("Coder agent failed on %s: %s", target_file, str(e))
                                response = Msg(name="Coder", content=f"ERROR: {str(e)}", role="assistant")
                        response_text = self._extract_response_text(response, stage_buffer.getvalue())

                        previous_response = response_text
                        logs.append(f"## {target_file} (attempt {attempt})\n{response_text}")

                        current_files = self._generated_files_snapshot()
                        if target_file not in current_files and self._recover_coder_write_from_response(target_file, response_text):
                            current_files = self._generated_files_snapshot()
                        if target_file in current_files:
                            wrote_target = True
                            break

                        logger.warning(
                            "Coder attempt %d did not write target file %s.",
                            attempt,
                            target_file,
                        )

                    if not wrote_target:
                        raise RuntimeError(
                            "Coder stage ended before writing required files. "
                            f"Missing: {target_file}"
                        )
                    return "\n\n".join(logs)

                # Flatten the plan just for the prompt context, so the model sees the big picture
                flat_file_plan = [f for layer in file_plan_layers for f in layer]
                
                for layer_idx, current_layer in enumerate(file_plan_layers):
                    print(f"  -> Executing layer {layer_idx + 1}/{len(file_plan_layers)} in parallel: {current_layer}")
                    
                    tasks = [_generate_single_file(target, flat_file_plan) for target in current_layer]
                    results = await asyncio.gather(*tasks)
                    
                    for r in results:
                        coder_logs.append(r)
                    
                    # Optional: Run a light indexing here so the next layer has fresh context? 
                    # The files are on disk, but not in RAG. Let's rely on standard text-based read_file for now or minimal indexing
                    # if needed.
                    
                stage_outputs[stage_label] = "\n\n".join(coder_logs) if coder_logs else "No pending files."
                await self._index_stage(rag, stage_label, stage_outputs[stage_label])
                continue

            attempts = 4 if stage_label == "Coder" else 1
            snapshot_before = self._generated_files_snapshot() if stage_label == "Coder" else set()
            expected_files = self._parse_file_plan(stage_outputs.get("FilePlanner", "")) if stage_label == "Coder" else []
            response_text = ""
            final_missing_files: list[str] = []
            for attempt in range(attempts):
                message = self._build_stage_message(stage_label, task, stage_outputs)
                if stage_label == "Coder" and attempt > 0:
                    missing_hint = ""
                    if final_missing_files:
                        missing_hint = f" Missing files: {json.dumps(final_missing_files, ensure_ascii=False)}."
                    retry_hint = (
                        "Previous coder attempt did not complete writing files. Continue the same file plan and "
                        f"execute write_file/execution_loop tool calls until every planned file exists.{missing_hint}"
                    )
                    message = Msg(
                        name="user",
                        content=f"{message.content}\n\n{retry_hint}",
                        role="user",
                    )
                stage_buffer = io.StringIO()
                with redirect_stdout(_TeeStream(sys.stdout, stage_buffer)):
                    try:
                        response = agent(message)
                        if inspect.iscoroutine(response):
                            response = await response
                    except Exception as e:
                        logger.error("Agent %s failed: %s", stage_label, str(e))
                        response = Msg(name=stage_label, content=f"ERROR: {str(e)}", role="assistant")

                response_text = self._extract_response_text(response, stage_buffer.getvalue())

                if stage_label != "Coder":
                    break

                snapshot_after = self._generated_files_snapshot()
                if expected_files:
                    final_missing_files = [path for path in expected_files if path not in snapshot_after]
                else:
                    created = snapshot_after - snapshot_before
                    final_missing_files = [] if created else ["<unknown-from-plan>"]

                if not final_missing_files:
                    break
                logger.warning(
                    "Coder attempt %d incomplete; %d planned file(s) still missing.",
                    attempt + 1,
                    len(final_missing_files),
                )

            stage_outputs[stage_label] = response_text

            if stage_label == "Coder" and final_missing_files:
                missing_preview = ", ".join(final_missing_files[:8])
                if len(final_missing_files) > 8:
                    missing_preview += ", ..."
                raise RuntimeError(
                    "Coder stage ended before writing required files. "
                    f"Missing: {missing_preview}"
                )

            await self._index_stage(rag, stage_label, response_text)

        result = Msg(
            name="user",
            content="\n\n".join(
                f"=== Output from {label} ===\n{text}"
                for label, text in stage_outputs.items()
            ),
            role="user",
        )

        self._finalize_project()

        if isinstance(result, Msg):
            return {"content": result.content}
        return {"content": str(result)}

    # -------------------------------------------------------------------------
    # RAG indexing helper
    # -------------------------------------------------------------------------

    async def _index_stage(self, rag: RAGStore, stage_label: str, output_text: str) -> None:
        """Index the output of a completed stage into the RAG store."""
        action = _RAG_INDEX.get(stage_label)
        if action is None:
            return

        if action == "files":
            # Index all files currently in the output directory via thread to prevent blocking
            n = await asyncio.to_thread(rag.index_directory, self.output_dir)
            logger.info("RAG: indexed %d chunks from output dir after %s", n, stage_label)
        else:
            # Index the agent's text output via thread
            n = await asyncio.to_thread(rag.index, doc_id=action, text=output_text)
            logger.info("RAG: indexed %d chunks for '%s' after %s", n, action, stage_label)

    # -------------------------------------------------------------------------
    # Project finalizer
    # -------------------------------------------------------------------------

    def _finalize_project(self):
        """Initialize a Git repo in the output dir and commit all generated files."""
        print(f"\n{'='*60}")
        print(f"  📦 Finalizing project...")
        print(f"{'='*60}\n")

        try:
            subprocess.run(["git", "init"], cwd=self.output_dir, capture_output=True, text=True)
            subprocess.run(["git", "add", "."], cwd=self.output_dir, capture_output=True, text=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit by CodeCrew 🚀"],
                cwd=self.output_dir,
                capture_output=True,
                text=True,
            )
            print("  ✅ Git repository initialized with initial commit")
        except FileNotFoundError:
            print("  ⚠️  Git not found — skipping repo initialization")

        print(f"\n  📂 Generated files in {self.output_dir}:")
        for root, dirs, files in os.walk(self.output_dir):
            dirs[:] = [d for d in dirs if d != ".git"]
            level = root.replace(self.output_dir, "").count(os.sep)
            indent = "  " + "    " * level
            folder_name = os.path.basename(root)
            if level > 0:
                print(f"{indent}📁 {folder_name}/")
            for file in files:
                file_indent = "  " + "    " * (level + 1)
                print(f"{file_indent}📄 {file}")

        print(f"\n{'='*60}")
        print(f"  ✨ CodeCrew finished! Your project is ready at:")
        print(f"     {self.output_dir}")
        print(f"{'='*60}\n")
