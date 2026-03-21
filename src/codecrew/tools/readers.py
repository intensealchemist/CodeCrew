from typing import Type
import os
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class DirectoryReadInput(BaseModel):
    """Input for DirectoryReaderTool."""
    directory_path: str = Field(
        ..., 
        description="The path to the directory to read, e.g. './output' or 'src'."
    )


class DirectoryReaderTool(BaseTool):
    name: str = "list_files_in_directory"
    description: str = "A tool to list all files and subdirectories within a given directory."
    args_schema: Type[BaseModel] = DirectoryReadInput

    def _run(self, directory_path: str) -> str:
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            return f"Error: Directory '{directory_path}' does not exist."
            
        try:
            items = os.listdir(directory_path)
            return "\n".join(items) if items else "Directory is empty."
        except Exception as e:
            return f"Error reading directory: {str(e)}"


class FileReadInput(BaseModel):
    """Input for FileReaderTool."""
    file_path: str = Field(
        ..., 
        description="The path to the file to read, e.g. './output/main.py'."
    )


class FileReaderTool(BaseTool):
    name: str = "read_file_content"
    description: str = "A tool to read the text content of a file."
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return f"Error: File '{file_path}' does not exist."
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if len(content) > 8000:
                    return content[:8000] + "\n\n...[FILE TRUNCATED TO SAVE ENORMOUS TOKEN AMOUNTS]..."
                return content
        except Exception as e:
            return f"Error reading file: {str(e)}"
