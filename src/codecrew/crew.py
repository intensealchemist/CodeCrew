"""
CodeCrew - Crew Orchestration.

Wires together agents, tasks, tools, and the LLM provider into a CrewAI Crew
that runs sequentially with shared memory.
"""

import os
import sys
import subprocess
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# Fix Windows event loop hang: force WindowsSelectorEventLoop instead of ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff

from codecrew.providers.llm_provider import get_llm
from codecrew.providers.search_provider import get_search_tool
from codecrew.tools.file_writer import FileWriterTool
from codecrew.tools.code_executor import CodeExecutorTool
from codecrew.tools.readers import DirectoryReaderTool, FileReaderTool
from codecrew.tools.think import ThinkTool
from codecrew.tools.execution_loop import ExecutionLoopTool

# --- Structured Memory Models ---

class SpecContext(BaseModel):
    content: str = Field(description="The complete, comprehensive technical specification written in Markdown. Include all details, features, and text here.")
    tech_requirements: List[str] = Field(description="A lightweight list of critical technologies, frameworks, or dependencies needed.")

class ArchitectureContext(BaseModel):
    content: str = Field(description="The complete architectural blueprint written in Markdown, including folder structures, data flow, and logic.")

class FilePlanContext(BaseModel):
    files_pending: List[str] = Field(description="Strictly ordered list of file paths to be created")


@CrewBase
class CodeCrewCrew:
    """CodeCrew: Multi-agent system for autonomous code generation."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, output_dir: str = "./output", human_override: bool = False):
        self.output_dir = os.path.abspath(output_dir)
        self.human_override = human_override

        # Initialize shared tools
        self._file_writer = FileWriterTool(base_dir=self.output_dir)
        self._code_executor = CodeExecutorTool()
        self._search_tool = get_search_tool()
        self._dir_reader = DirectoryReaderTool()
        self._file_reader = FileReaderTool()
        self._think = ThinkTool()
        self._execution_loop = ExecutionLoopTool(base_dir=self.output_dir)

        # Get the configured LLMs locally specialized by role
        # Each role can point to a different GPU instance via env vars
        self._reasoning_llm = get_llm(role="reasoning")    # Kaggle #1 — deepseek-r1:14b
        self._coding_llm = get_llm(role="coding")          # Kaggle #2 — qwen2.5-coder:14b
        self._structured_llm = get_llm(role="structured")  # Colab    — qwen2.5:7b (fast JSON)
        self._qa_llm = get_llm(role="qa")                  # Colab    — qwen2.5:7b

    @before_kickoff
    def setup_workspace(self, inputs):
        """Create the output directory before the crew starts."""
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  🚀 CodeCrew — Starting up")
        print(f"  📁 Output directory: {self.output_dir}")
        print(f"  🧑 Human Override: {'ON' if self.human_override else 'OFF'}")
        print(f"{'='*60}\n")
        return inputs

    @after_kickoff
    def finalize_project(self, result):
        """Initialize a Git repo in the output dir and commit all generated files."""
        print(f"\n{'='*60}")
        print(f"  📦 Finalizing project...")
        print(f"{'='*60}\n")

        try:
            subprocess.run(["git", "init"], cwd=self.output_dir, capture_output=True, text=True)
            subprocess.run(["git", "add", "."], cwd=self.output_dir, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "Initial commit by CodeCrew 🚀"], cwd=self.output_dir, capture_output=True, text=True)
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
        return result

    # ----- Agents -----

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            verbose=True,
            llm=self._reasoning_llm,
            tools=[self._search_tool, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def spec_validator(self) -> Agent:
        return Agent(
            config=self.agents_config["spec_validator"],
            verbose=True,
            llm=self._structured_llm,
            tools=[self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def architect(self) -> Agent:
        return Agent(
            config=self.agents_config["architect"],
            verbose=True,
            llm=self._structured_llm,
            tools=[self._search_tool, self._file_writer, self._dir_reader, self._file_reader, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def file_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["file_planner"],
            verbose=True,
            llm=self._structured_llm,
            tools=[self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def coder(self) -> Agent:
        return Agent(
            config=self.agents_config["coder"],
            verbose=True,
            llm=self._coding_llm,
            tools=[self._execution_loop, self._dir_reader, self._file_reader, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 25)),  # Higher iteration for multiple files
        )

    @agent
    def qa_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["qa_agent"],
            verbose=True,
            llm=self._qa_llm,
            tools=[self._file_writer, self._code_executor, self._dir_reader, self._file_reader, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def readme_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["readme_agent"],
            verbose=True,
            llm=self._qa_llm,
            tools=[self._file_writer, self._dir_reader, self._file_reader, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    # ----- Tasks -----

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
        )

    @task
    def spec_validation_task(self) -> Task:
        return Task(
            config=self.tasks_config["spec_validation_task"],
            output_pydantic=SpecContext,
        )

    @task
    def architecture_task(self) -> Task:
        return Task(
            config=self.tasks_config["architecture_task"],
            output_pydantic=ArchitectureContext,
        )

    @task
    def file_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config["file_planning_task"],
            output_pydantic=FilePlanContext,
        )

    @task
    def coding_task(self) -> Task:
        return Task(
            config=self.tasks_config["coding_task"],
        )

    @task
    def qa_task(self) -> Task:
        return Task(
            config=self.tasks_config["qa_task"],
            output_file=os.path.join(self.output_dir, "QA_REPORT.md"),
        )

    @task
    def readme_task(self) -> Task:
        return Task(
            config=self.tasks_config["readme_task"],
        )

    # ----- Crew -----

    @crew
    def crew(self) -> Crew:
        # Free embedding alternative: Google Gemini
        use_memory = os.getenv("USE_MEMORY", "False").lower() in ("true", "1", "yes")
        embedder_config = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        if use_memory and gemini_key:
            embedder_config = {
                "provider": "google",
                "config": {
                    "model": "models/text-embedding-004",
                    "api_key": gemini_key
                }
            }
        
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=use_memory,
            embedder=embedder_config
        )
