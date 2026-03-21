"""
CodeCrew - Crew Orchestration.

Wires together agents, tasks, tools, and the LLM provider into a CrewAI Crew
that runs sequentially with shared memory.
"""

import os
import sys
import subprocess
import asyncio

# Fix Windows event loop hang: force WindowsSelectorEventLoop instead of ProactorEventLoop
# ProactorEventLoop can deadlock with aiohttp on Windows
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

        # Get the configured LLM
        self._llm = get_llm()

    @before_kickoff
    def setup_workspace(self, inputs):
        """Create the output directory before the crew starts."""
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  🚀 CodeCrew — Starting up")
        print(f"  📁 Output directory: {self.output_dir}")
        print(f"  🔧 LLM Provider: {os.getenv('LLM_PROVIDER', 'ollama')}")
        print(f"  🔍 Search Provider: {os.getenv('SEARCH_PROVIDER', 'duckduckgo')}")
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
            # Initialize git repo
            subprocess.run(
                ["git", "init"],
                cwd=self.output_dir,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=self.output_dir,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit by CodeCrew 🚀"],
                cwd=self.output_dir,
                capture_output=True,
                text=True,
            )
            print("  ✅ Git repository initialized with initial commit")
        except FileNotFoundError:
            print("  ⚠️  Git not found — skipping repo initialization")

        # List generated files
        print(f"\n  📂 Generated files in {self.output_dir}:")
        for root, dirs, files in os.walk(self.output_dir):
            # Skip .git directory
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
            config=self.agents_config["researcher"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[self._search_tool, self._think],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def architect(self) -> Agent:
        return Agent(
            config=self.agents_config["architect"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[
                self._search_tool,
                self._file_writer,
                self._dir_reader,
                self._file_reader,
                self._think,
            ],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def coder(self) -> Agent:
        return Agent(
            config=self.agents_config["coder"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[
                self._file_writer,
                self._code_executor,
                self._dir_reader,
                self._file_reader,
                self._think,
            ],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config["reviewer"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[
                self._file_writer,
                self._code_executor,
                self._dir_reader,
                self._file_reader,
                self._think,
            ],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def devops_engineer(self) -> Agent:
        return Agent(
            config=self.agents_config["devops_engineer"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[
                self._file_writer,
                self._code_executor,
                self._dir_reader,
                self._file_reader,
                self._think,
            ],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    @agent
    def doc_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["doc_writer"],  # type: ignore[index]
            verbose=True,
            llm=self._llm,
            tools=[
                self._file_writer,
                self._dir_reader,
                self._file_reader,
                self._search_tool,
                self._think,
            ],
            human_input=self.human_override,
            max_rpm=int(os.getenv("MAX_RPM", 15)),
            max_iter=int(os.getenv("MAX_ITER", 15)),
        )

    # ----- Tasks -----

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
        )

    @task
    def architecture_task(self) -> Task:
        return Task(
            config=self.tasks_config["architecture_task"],  # type: ignore[index]
        )

    @task
    def coding_task(self) -> Task:
        return Task(
            config=self.tasks_config["coding_task"],  # type: ignore[index]
        )

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_task"],  # type: ignore[index]
            output_file=os.path.join(self.output_dir, "QUALITY_REPORT.md"),
        )

    @task
    def devops_task(self) -> Task:
        return Task(
            config=self.tasks_config["devops_task"],  # type: ignore[index]
        )

    @task
    def documentation_task(self) -> Task:
        return Task(
            config=self.tasks_config["documentation_task"],  # type: ignore[index]
            output_file=os.path.join(self.output_dir, "DOCS_REPORT.md"),
        )

    # ----- Crew -----

    @crew
    def crew(self) -> Crew:
        """Creates the CodeCrew crew."""
        # Memory requires an OpenAI API key for embeddings by default. 
        # Since we use free_ha, we default memory to False to prevent ChromaDB crashes.
        use_memory = os.getenv("USE_MEMORY", "False").lower() in ("true", "1", "yes")
        
        # Free embedding alternative: Google Gemini
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
            agents=self.agents,   # type: ignore[attr-defined]
            tasks=self.tasks,     # type: ignore[attr-defined]
            process=Process.sequential,
            verbose=True,
            memory=use_memory,
            embedder=embedder_config
        )
