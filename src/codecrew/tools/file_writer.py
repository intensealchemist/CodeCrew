import os

def write_file(filepath: str, content: str, base_dir: str = "./output") -> str:
    """
    Write content to a file in the project output directory. Creates parent directories automatically.
    Use this tool whenever you need to create or overwrite a project file.
    
    Args:
        filepath (str): Relative file path within the project (e.g., 'src/app.py', 'README.md').
        content (str): The complete file content to write.
        base_dir (str): The base output directory. Default is './output'.
        
    Returns:
        str: Success or error message.
    """
    try:
        full_path = os.path.join(base_dir, filepath)
        full_path = os.path.normpath(full_path)

        abs_base = os.path.abspath(base_dir)
        abs_target = os.path.abspath(full_path)
        if not abs_target.startswith(abs_base):
            return f"Error: Cannot write outside the output directory. Attempted: {filepath}"

        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to: {filepath}"

    except Exception as e:
        return f"Error writing file '{filepath}': {str(e)}"
