import pytest
import asyncio
import io
from pathlib import Path
from codecrew.agents import build_coder_sys_prompt
from codecrew.pipeline import CodeCrewPipeline
from codecrew.server import QueueStream, _list_generated_files

def test_pipeline_initialization():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    assert pipeline.output_dir.endswith("mock")
    assert pipeline.human_override is False

# Skipping full E2E execution because it requires LLM keys, but verifying setup.


def test_queue_stream_emits_agent_event_and_callback():
    queue = asyncio.Queue()
    sink = io.StringIO()
    received = []

    stream = QueueStream(queue, sink, on_agent=lambda label: received.append(label))
    stream.write("[[AGENT:Researcher]]\n")

    event = queue.get_nowait()
    assert event["type"] == "agent"
    assert event["agent"] == "Researcher"
    assert received == ["Researcher"]


def test_list_generated_files_excludes_metadata_and_hidden_dirs(tmp_path: Path):
    (tmp_path / "job_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")

    files = _list_generated_files(str(tmp_path))
    assert files == ["src/main.py"]


def test_build_stage_message_for_coder_uses_file_plan_not_full_spec():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    large_spec = "SPEC\n" * 5000
    stage_outputs = {
        "Researcher": large_spec,
        "SpecValidator": large_spec,
        "FilePlanner": '["pyproject.toml","src/models/calculator.py","README.md"]',
    }

    message = pipeline._build_stage_message("Coder", "Build calculator app", stage_outputs)
    content = str(message.content)

    assert "Ordered File Plan" in content
    assert 'src/models/calculator.py' in content
    assert "SPEC" not in content


def test_build_stage_message_for_user_contains_latest_stage_output():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=True)
    stage_outputs = {
        "SpecValidator": "Validated spec output",
        "FilePlanner": '["src/main.py"]',
    }

    message = pipeline._build_stage_message("User", "Build app", stage_outputs)
    content = str(message.content)

    assert "Latest Stage: FilePlanner" in content
    assert '["src/main.py"]' in content


def test_generated_files_snapshot_ignores_git_and_job_state(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    (tmp_path / "job_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculator_service.py").write_text("class CalculatorService: ...", encoding="utf-8")

    pipeline = CodeCrewPipeline(output_dir=str(tmp_path), human_override=False)
    snapshot = pipeline._generated_files_snapshot()

    assert "src/calculator_service.py" in snapshot
    assert "job_state.json" not in snapshot


def test_parse_file_plan_accepts_json_array():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    parsed = pipeline._parse_file_plan('["pyproject.toml","src/calculator_service.py"]')
    assert parsed == ["pyproject.toml", "src/calculator_service.py"]


def test_parse_file_plan_handles_markdown_wrapped_json():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    raw = "```json\n[\"src/a.py\", \"src/b.py\"]\n```"
    parsed = pipeline._parse_file_plan(raw)
    assert parsed == ["src/a.py", "src/b.py"]


def test_parse_file_plan_handles_agent_prefixed_output():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    raw = "FilePlanner: [\"pyproject.toml\", \"src/__init__.py\"]"
    parsed = pipeline._parse_file_plan(raw)
    assert parsed == ["pyproject.toml", "src/__init__.py"]


def test_parse_file_plan_normalizes_relative_and_project_root_paths():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    raw = '["./pyproject.toml", "project-root/src\\\\app.py", "src/app.py"]'
    parsed = pipeline._parse_file_plan(raw)
    assert parsed == ["pyproject.toml", "src/app.py"]


def test_parse_file_plan_fallback_to_line_extraction():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    raw = """
    Here are the files:
    * pyproject.toml
    - src/main.py
    ```python
    # models/user.py
    ```
    And a sentence with a dot. like this.
    Makefile
    """
    parsed = pipeline._parse_file_plan(raw)
    assert parsed == ["pyproject.toml", "src/main.py", "models/user.py", "Makefile"]


def test_parse_loose_write_file_action_input_handles_invalid_json_style():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    action_input = (
        '{"filepath": "pyproject.toml", '
        '"content"="[build-system]\\nrequires = [\'setuptools\', \'wheel\']\\n"}'
    )
    parsed = pipeline._parse_loose_write_file_action_input(action_input)
    assert parsed == (
        "pyproject.toml",
        "[build-system]\nrequires = ['setuptools', 'wheel']\n",
    )


def test_parse_loose_write_file_action_input_handles_extra_trailing_braces():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    action_input = (
        '{"filepath": "src/main.py", '
        '"content": "#!/usr/bin/env python\\n"}}'
    )
    parsed = pipeline._parse_loose_write_file_action_input(action_input)
    assert parsed == (
        "src/main.py",
        "#!/usr/bin/env python\n",
    )


def test_recover_coder_write_from_response_writes_missing_target_file(tmp_path: Path):
    pipeline = CodeCrewPipeline(output_dir=str(tmp_path), human_override=False)
    response_text = (
        "Thought: I will now write pyproject.toml\n"
        "Action: write_file\n"
        'Action Input: {"filepath": "pyproject.toml", '
        '"content"="[build-system]\\nrequires = [\'setuptools\', \'wheel\']\\n"}\n'
        "Observation: The file pyproject.toml has been successfully written with the provided content."
    )

    recovered = pipeline._recover_coder_write_from_response("pyproject.toml", response_text)

    assert recovered is True
    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == (
        "[build-system]\nrequires = ['setuptools', 'wheel']\n"
    )


def test_coder_prompt_uses_target_placeholder_instead_of_literal_example_path():
    prompt = build_coder_sys_prompt()

    assert "Current Target File" in prompt
    assert "<CURRENT_TARGET_FILE>" in prompt
    assert "src/models/user.py" not in prompt
    assert "Action Input MUST be valid JSON." in prompt
