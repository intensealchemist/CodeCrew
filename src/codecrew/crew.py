"""
Backward-compatible Crew entrypoint.

The project runtime now uses AgentScope through `CodeCrewPipeline`.
This module preserves the legacy `CodeCrewCrew().crew().kickoff(...)` shape.
"""

from dataclasses import dataclass

from codecrew.pipeline import CodeCrewPipeline


@dataclass
class _CrewRunner:
    pipeline: CodeCrewPipeline

    def kickoff(self, inputs: dict[str, str] | None = None):
        payload = inputs or {}
        task = payload.get("task", "").strip()
        if not task:
            raise ValueError("Missing required input: task")
        return self.pipeline.run(task=task)


class CodeCrewCrew:
    def __init__(self, output_dir: str = "./output", human_override: bool = False):
        self._pipeline = CodeCrewPipeline(output_dir=output_dir, human_override=human_override)

    def crew(self) -> _CrewRunner:
        return _CrewRunner(pipeline=self._pipeline)
