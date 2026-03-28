import os
import subprocess
import agentscope
from agentscope.pipeline import SequentialPipeline
from agentscope.message import Msg

from codecrew.model_configs import build_model_configs
from codecrew.tools import build_toolkit
from codecrew.agents import (
    create_researcher,
    create_spec_validator,
    create_architect,
    create_file_planner,
    create_coder,
    create_qa_agent,
    create_readme_agent
)

class CodeCrewPipeline:
    def __init__(self, output_dir: str = "./output", human_override: bool = False):
        self.output_dir = os.path.abspath(output_dir)
        self.human_override = human_override

    def run(self, task: str) -> dict:
        studio_url = os.getenv("STUDIO_URL", "http://127.0.0.1:5000")
        
        # Extract init args. Only include studio_url if running agent scope studio.
        agentscope.init(
            project="CodeCrew",
            name="Implementation",
            model_configs=build_model_configs(),
            studio_url=studio_url
        )

        research_toolkit = build_toolkit("research", self.output_dir)
        coding_toolkit = build_toolkit("coding", self.output_dir)
        qa_toolkit = build_toolkit("qa", self.output_dir)

        researcher = create_researcher(research_toolkit)
        spec_validator = create_spec_validator()
        architect = create_architect(research_toolkit)
        file_planner = create_file_planner()
        coder = create_coder(coding_toolkit)
        qa_agent = create_qa_agent(qa_toolkit)
        readme_agent = create_readme_agent(qa_toolkit)

        agents = [
            researcher, spec_validator, architect,
            file_planner, coder, qa_agent, readme_agent
        ]
        
        # Insert human-in-the-loop validation via AgentScope UserAgent
        if self.human_override:
            from agentscope.agents import UserAgent
            user_agent = UserAgent(name="User")
            agents = [
                researcher, spec_validator, user_agent, 
                architect, file_planner, user_agent, 
                coder, qa_agent, user_agent, readme_agent
            ]

        pipeline = SequentialPipeline(agents=agents)

        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  🚀 CodeCrew — Starting up")
        print(f"  📁 Output directory: {self.output_dir}")
        print(f"  🧑 Human Override: {'ON' if self.human_override else 'OFF'}")
        print(f"{'='*60}\n")
        
        initial_msg = Msg(name="user", content=f"Build the following project: {task}", role="user")
        
        # Execute pipeline
        result = pipeline(initial_msg)
        
        self._finalize_project()
        
        # Serialize result logic (as pipeline result is usually a Msg or similar)
        if isinstance(result, Msg):
            return {"content": result.content}
        return {"content": str(result)}

    def _finalize_project(self):
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
