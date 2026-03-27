"""
Execution Loop Tool for Coder Agent.

Handles the writing, testing, linting loop with a max of 3 retries.
"""

from typing import Type
import subprocess
import os
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from codecrew.tools.file_writer import FileWriterTool

class ExecutionLoopInput(BaseModel):
    """Input schema for ExecutionLoopTool."""
    file_path: str = Field(..., description="The absolute or relative path to the file to write.")
    code_content: str = Field(..., description="The complete code to write.")
    lint_command: str = Field(..., description="A command to lint the code (e.g. 'flake8 file.py' or 'eslint file.js'). Blank if not applicable.")
    test_command: str = Field(..., description="A command to test the code (e.g. 'pytest file.py' or 'npm test'). Blank if not applicable.")


class ExecutionLoopTool(BaseTool):
    """Execution Loop tool for Coder agent."""
    name: str = "Execution_Loop"
    description: str = (
        "Write code to a file and automatically run a lint and test command "
        "up to 3 times to ensure the code works before continuing."
    )
    args_schema: Type[BaseModel] = ExecutionLoopInput
    base_dir: str = "./output"

    def __init__(self, base_dir: str = "./output", **data):
        super().__init__(**data)
        self.base_dir = base_dir

    def _run(self, file_path: str, code_content: str, lint_command: str = "", test_command: str = "") -> str:
        writer = FileWriterTool(base_dir=self.base_dir)
        full_path = os.path.join(self.base_dir, file_path)
        
        # Max 3 attempts
        for attempt in range(1, 4):
            # Write file
            writer._run(filepath=file_path, content=code_content)
            
            output = f"Attempt {attempt}/3:\n"
            success = True
            
            error_msgs = []
            if lint_command:
                try:
                    res = subprocess.run(lint_command, shell=True, cwd=self.base_dir, capture_output=True, text=True, timeout=15)
                    if res.returncode != 0:
                        success = False
                        error_msgs.append(f"Linting failed:\n{res.stdout}\n{res.stderr}")
                    else:
                        output += f"Linting passed: {lint_command}\n"
                except Exception as e:
                    success = False
                    error_msgs.append(f"Lint execution error: {str(e)}")

            if test_command:
                try:
                    res = subprocess.run(test_command, shell=True, cwd=self.base_dir, capture_output=True, text=True, timeout=30)
                    if res.returncode != 0:
                        success = False
                        error_msgs.append(f"Tests failed:\n{res.stdout}\n{res.stderr}")
                    else:
                        output += f"Tests passed: {test_command}\n"
                except Exception as e:
                    success = False
                    error_msgs.append(f"Test execution error: {str(e)}")
                    
            if success:
                return f"Successfully wrote and verified {file_path}.\n{output}"
                
            error_report = f"Errors on attempt {attempt}:\n" + "\n".join(error_msgs)
            
            if attempt < 3:
                # To simulate loop within tool, we would have to prompt the LLM to fix it.
                # However, this tool is run by the LLM. 
                # If we want the LLM to fix it, we should just return the error to the LLM
                # and the LLM will call this tool again. 
                # Oh wait, the prompt says "Feed errors back into the agent... coding_loop(file_spec): ... return code". 
                # But since we are giving the ExecutionLoopTool to an LLM, returning the error
                # will naturally prompt the LLM to fix it. We just need to return the error!
                return f"FAILURE on {file_path}:\n{error_report}\nPlease fix the errors and run Execution_Loop again."

        return f"FAILURE on {file_path} after 3 attempts:\n{error_report}\nPlease fix the errors and try again."

