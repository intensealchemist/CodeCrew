"""Tests for CodeCrew crew configuration."""

import os
import pytest


class TestCrewConfig:
    """Tests for the crew configuration files."""

    def test_agents_yaml_exists(self):
        """agents.yaml config file should exist."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "codecrew", "config", "agents.yaml"
        )
        assert os.path.exists(config_path), "config/agents.yaml not found"

    def test_tasks_yaml_exists(self):
        """tasks.yaml config file should exist."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "codecrew", "config", "tasks.yaml"
        )
        assert os.path.exists(config_path), "config/tasks.yaml not found"

    def test_agents_yaml_has_all_agents(self):
        """agents.yaml should define researcher, coder, and reviewer."""
        import yaml
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "codecrew", "config", "agents.yaml"
        )
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        assert "researcher" in config, "Missing 'researcher' agent"
        assert "architect" in config, "Missing 'architect' agent"
        assert "coder" in config, "Missing 'coder' agent"
        assert "reviewer" in config, "Missing 'reviewer' agent"
        assert "devops_engineer" in config, "Missing 'devops_engineer' agent"
        assert "doc_writer" in config, "Missing 'doc_writer' agent"

        # Each agent should have role, goal, and backstory
        for agent_name in ["researcher", "architect", "coder", "reviewer", "devops_engineer", "doc_writer"]:
            agent = config[agent_name]
            assert "role" in agent, f"{agent_name} missing 'role'"
            assert "goal" in agent, f"{agent_name} missing 'goal'"
            assert "backstory" in agent, f"{agent_name} missing 'backstory'"

    def test_tasks_yaml_has_all_tasks(self):
        """tasks.yaml should define research_task, coding_task, and review_task."""
        import yaml
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "codecrew", "config", "tasks.yaml"
        )
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        assert "research_task" in config, "Missing 'research_task'"
        assert "architecture_task" in config, "Missing 'architecture_task'"
        assert "coding_task" in config, "Missing 'coding_task'"
        assert "review_task" in config, "Missing 'review_task'"
        assert "devops_task" in config, "Missing 'devops_task'"
        assert "documentation_task" in config, "Missing 'documentation_task'"

        # Each task should have description, expected_output, and agent
        for task_name in ["research_task", "architecture_task", "coding_task", "review_task", "devops_task", "documentation_task"]:
            task = config[task_name]
            assert "description" in task, f"{task_name} missing 'description'"
            assert "expected_output" in task, f"{task_name} missing 'expected_output'"
            assert "agent" in task, f"{task_name} missing 'agent'"


class TestProviders:
    """Tests for provider factory functions."""

    def test_get_search_tool_duckduckgo(self):
        """DuckDuckGo search tool should be the default."""
        os.environ["SEARCH_PROVIDER"] = "duckduckgo"
        from codecrew.providers.search_provider import get_search_tool
        tool = get_search_tool()
        assert tool is not None
        assert tool.name == "DuckDuckGo Search"

    def test_get_search_tool_invalid_provider(self):
        """Should raise ValueError for unknown search provider."""
        os.environ["SEARCH_PROVIDER"] = "nonexistent_provider"
        from codecrew.providers.search_provider import get_search_tool
        with pytest.raises(ValueError, match="Unknown SEARCH_PROVIDER"):
            get_search_tool()

    def test_get_llm_invalid_provider(self):
        """Should raise ValueError for unknown LLM provider."""
        os.environ["LLM_PROVIDER"] = "nonexistent_provider"
        from codecrew.providers.llm_provider import get_llm
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm()
