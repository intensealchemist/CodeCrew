"""
File Writer Tool.

Allows agents to create and write files to the output workspace directory.
Handles nested directory creation automatically.
"""

import os
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FileWriterInput(BaseModel):
    """Input schema for FileWriterTool."""
    filepath: str = Field(
        ...,
        description="Relative file path within the project (e.g., 'src/app.py', 'README.md')."
    )
    content: str = Field(
        ...,
        description="The complete file content to write."
    )


class FileWriterTool(BaseTool):
    """Write files to the output project workspace."""
    name: str = "file_writer"
    description: str = (
        "Write content to a file in the project output directory. "
        "Creates parent directories automatically. "
        "Input requires 'filepath' (relative path like 'src/app.py') and 'content' (complete file content). "
        "Use this tool whenever you need to create or overwrite a project file."
    )
    args_schema: Type[BaseModel] = FileWriterInput
    base_dir: str = "./output"

    def _run(self, filepath: str, content: str) -> str:
        try:
            # Resolve the full path
            full_path = os.path.join(self.base_dir, filepath)
            full_path = os.path.normpath(full_path)

            # Security: ensure we don't write outside base_dir
            abs_base = os.path.abspath(self.base_dir)
            abs_target = os.path.abspath(full_path)
            if not abs_target.startswith(abs_base):
                return f"Error: Cannot write outside the output directory. Attempted: {filepath}"

            # Create parent directories
            parent_dir = os.path.dirname(full_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Write the file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote {len(content)} characters to: {filepath}"

        except Exception as e:
            return f"Error writing file '{filepath}': {str(e)}"
