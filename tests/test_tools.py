"""Tests for custom CodeCrew tools."""

import os
import tempfile

import pytest

from codecrew.tools.file_writer import FileWriterTool
from codecrew.tools.code_executor import CodeExecutorTool


class TestFileWriterTool:
    """Tests for the FileWriterTool."""

    def test_creates_file(self):
        """File writer should create a file with the given content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriterTool(base_dir=tmpdir)
            result = tool._run(filepath="hello.txt", content="Hello, World!")

            assert "Successfully wrote" in result
            filepath = os.path.join(tmpdir, "hello.txt")
            assert os.path.exists(filepath)
            with open(filepath, "r") as f:
                assert f.read() == "Hello, World!"

    def test_creates_nested_directories(self):
        """File writer should create parent directories automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriterTool(base_dir=tmpdir)
            result = tool._run(
                filepath="src/utils/helper.py",
                content="def helper(): pass",
            )

            assert "Successfully wrote" in result
            filepath = os.path.join(tmpdir, "src", "utils", "helper.py")
            assert os.path.exists(filepath)

    def test_overwrites_existing_file(self):
        """File writer should overwrite existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriterTool(base_dir=tmpdir)
            tool._run(filepath="test.txt", content="Version 1")
            tool._run(filepath="test.txt", content="Version 2")

            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "r") as f:
                assert f.read() == "Version 2"

    def test_blocks_path_traversal(self):
        """File writer should reject paths that escape the base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriterTool(base_dir=tmpdir)
            result = tool._run(
                filepath="../../etc/passwd",
                content="malicious content",
            )
            assert "Error" in result or "Cannot write outside" in result

    def test_reports_character_count(self):
        """File writer should report the number of characters written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriterTool(base_dir=tmpdir)
            content = "x" * 42
            result = tool._run(filepath="file.txt", content=content)
            assert "42" in result


class TestCodeExecutorTool:
    """Tests for the CodeExecutorTool."""

    def test_runs_simple_command(self):
        """Code executor should run a simple command and return output."""
        tool = CodeExecutorTool()
        result = tool._run(command='python -c "print(123)"', working_directory=".")
        assert "123" in result
        assert "Return code: 0" in result

    def test_captures_stderr(self):
        """Code executor should capture stderr output."""
        tool = CodeExecutorTool()
        result = tool._run(
            command='python -c "import sys; sys.stderr.write(\'err\\n\')"',
            working_directory=".",
        )
        assert "err" in result

    def test_returns_nonzero_exit_code(self):
        """Code executor should report nonzero exit codes."""
        tool = CodeExecutorTool()
        result = tool._run(command='python -c "exit(1)"', working_directory=".")
        assert "Return code: 1" in result

    def test_blocks_dangerous_commands(self):
        """Code executor should block dangerous commands."""
        tool = CodeExecutorTool()
        result = tool._run(command="rm -rf /", working_directory=".")
        assert "Blocked" in result or "dangerous" in result.lower()

    def test_handles_timeout(self):
        """Code executor should handle command timeout."""
        tool = CodeExecutorTool(timeout=2)
        result = tool._run(
            command='python -c "import time; time.sleep(10)"',
            working_directory=".",
        )
        assert "timed out" in result.lower()

    def test_handles_invalid_working_directory(self):
        """Code executor should handle a nonexistent working directory."""
        tool = CodeExecutorTool()
        result = tool._run(
            command="echo hello",
            working_directory="/nonexistent/dir/abc123",
        )
        # Should either get a FileNotFoundError or an error from the shell
        assert "Error" in result or "Return code:" in result
