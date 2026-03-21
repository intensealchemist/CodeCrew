"""
Code Executor Tool.

Allows agents to run shell commands in a subprocess with a timeout.
Used by the Reviewer agent to run tests, linters, and syntax checks.
"""

import subprocess
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CodeExecutorInput(BaseModel):
    """Input schema for CodeExecutorTool."""
    command: str = Field(
        ...,
        description="The shell command to execute (e.g., 'python -c \"print(1+1)\"', 'pytest tests/')."
    )
    working_directory: str = Field(
        default="./output",
        description="The working directory for the command. Defaults to the output project directory."
    )


class CodeExecutorTool(BaseTool):
    """Execute shell commands to test and validate code."""
    name: str = "code_executor"
    description: str = (
        "Execute a shell command in a subprocess and return stdout/stderr. "
        "Use this to run tests, lint checks, syntax validation, or any other shell commands. "
        "Input requires 'command' (the shell command string) and optional 'working_directory'. "
        "Commands have a 60-second timeout. "
        "IMPORTANT: Only run safe, non-destructive commands."
    )
    args_schema: Type[BaseModel] = CodeExecutorInput
    timeout: int = 60

    def _run(self, command: str, working_directory: str = "./output") -> str:
        # Block dangerous commands
        dangerous_patterns = [
            "rm -rf /", "format ", "del /f /s /q",
            "mkfs", ":(){", "shutdown", "reboot",
        ]
        cmd_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in cmd_lower:
                return f"Error: Blocked potentially dangerous command containing '{pattern}'."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=working_directory,
            )

            output_parts = []
            if result.stdout:
                output_parts.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr}")

            output_parts.append(f"Return code: {result.returncode}")

            output = "\n\n".join(output_parts)

            # Truncate very long outputs
            if len(output) > 5000:
                output = output[:5000] + "\n\n... [output truncated at 5000 chars]"

            return output

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.timeout} seconds: {command}"
        except FileNotFoundError:
            return f"Error: Working directory not found: {working_directory}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
