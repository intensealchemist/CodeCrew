import os
import subprocess
from codecrew.tools.file_writer import write_file

def execution_loop(file_path: str, code_content: str, lint_command: str = "", test_command: str = "", base_dir: str = "./output") -> str:
    """
    Write code to a file and automatically run a lint and test command.
    Use this tool to ensure the code you wrote works before continuing.
    
    Args:
        file_path (str): The absolute or relative path to the file to write.
        code_content (str): The complete code to write.
        lint_command (str): A command to lint the code (e.g. 'flake8 file.py' or 'eslint file.js'). Blank if not applicable.
        test_command (str): A command to test the code (e.g. 'pytest file.py' or 'npm test'). Blank if not applicable.
        base_dir (str): Base working directory. Default is './output'.
    
    Returns:
        str: Success message or failure errors with instructions to fix.
    """
    
    write_result = write_file(filepath=file_path, content=code_content, base_dir=base_dir)
    
    if "Error" in write_result and "Successfully" not in write_result:
        return write_result # Return write error
        
    output = "Execution results:\n"
    success = True
    error_msgs = []
    
    if lint_command:
        try:
            res = subprocess.run(lint_command, shell=True, cwd=base_dir, capture_output=True, text=True, timeout=15)
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
            res = subprocess.run(test_command, shell=True, cwd=base_dir, capture_output=True, text=True, timeout=30)
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
        
    error_report = "Errors encountered:\n" + "\n".join(error_msgs)
    
    return f"FAILURE on {file_path}:\n{error_report}\nPlease fix the errors and run execution_loop again."
