import subprocess
import sys

def execute_command(command: str, working_directory: str = "./output") -> str:
    """
    Execute a shell command in a subprocess and return stdout/stderr.
    Use this to run tests, lint checks, syntax validation, or any other shell commands.
    Commands have a 60-second timeout. IMPORTANT: Only run safe, non-destructive commands.
    
    Args:
        command (str): The shell command to execute (e.g., 'python -c "print(1+1)"', 'pytest tests/').
        working_directory (str): The working directory for the command. Defaults to the output project directory.
        
    Returns:
        str: Output logs of the command execution, or error message.
    """
    timeout = 60
    dangerous_patterns = [
        "rm -rf /", "format ", "del /f /s /q",
        "mkfs", ":(){", "shutdown", "reboot",
    ]
    cmd_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern in cmd_lower:
            return f"Error: Blocked potentially dangerous command containing '{pattern}'."

    try:
        normalized_command = command.strip()
        if normalized_command.lower() == "python":
            command = f"\"{sys.executable}\""
        elif normalized_command.lower().startswith("python "):
            command = f"\"{sys.executable}\"{normalized_command[6:]}"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_directory,
        )

        output_parts = []
        if result.stdout:
            output_parts.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output_parts.append(f"STDERR:\n{result.stderr}")

        output_parts.append(f"Return code: {result.returncode}")

        output = "\n\n".join(output_parts)

        if len(output) > 5000:
            output = output[:5000] + "\n\n... [output truncated at 5000 chars]"

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds: {command}"
    except FileNotFoundError:
        return f"Error: Working directory not found: {working_directory}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
