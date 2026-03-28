import os

def list_files_in_directory(directory_path: str) -> str:
    """
    A tool to list all files and subdirectories within a given directory.
    
    Args:
        directory_path (str): The path to the directory to read, e.g. './output' or 'src'.
        
    Returns:
        str: List of files separated by newlines, or error message.
    """
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return f"Error: Directory '{directory_path}' does not exist."
        
    try:
        items = os.listdir(directory_path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error reading directory: {str(e)}"

def read_file_content(file_path: str) -> str:
    """
    A tool to read the text content of a file.
    
    Args:
        file_path (str): The path to the file to read, e.g. './output/main.py'.
    
    Returns:
        str: The content of the file.
    """
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
