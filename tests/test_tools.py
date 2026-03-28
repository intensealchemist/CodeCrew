import os
import pytest
from codecrew.tools.file_writer import write_file
from codecrew.tools.code_executor import execute_command
from codecrew.tools.readers import list_files_in_directory, read_file_content

@pytest.fixture
def temp_output_dir(tmpdir):
    return str(tmpdir)

def test_write_file(temp_output_dir):
    result = write_file("test.md", "# Hello AgentScope", base_dir=temp_output_dir)
    assert "Successfully wrote" in result
    
    file_path = os.path.join(temp_output_dir, "test.md")
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        assert f.read() == "# Hello AgentScope"

def test_code_executor(temp_output_dir):
    # Depending on OS, echo might be different, let's just use python
    cmd = "python -c \"print('Hello World')\""
    result = execute_command(cmd, working_directory=temp_output_dir)
    assert "Hello World" in result
    
def test_directory_reader(temp_output_dir):
    write_file("file1.txt", "abc", base_dir=temp_output_dir)
    result = list_files_in_directory(temp_output_dir)
    assert "file1.txt" in result

def test_file_reader(temp_output_dir):
    write_file("file1.txt", "abc", base_dir=temp_output_dir)
    file_path = os.path.join(temp_output_dir, "file1.txt")
    result = read_file_content(file_path)
    assert result == "abc"
