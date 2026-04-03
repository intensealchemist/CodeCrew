import os

import pytest
import yaml


class TestConfigFiles:
    def test_agents_yaml_exists(self):
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "codecrew",
            "config",
            "agents.yaml",
        )
        assert os.path.exists(config_path), "config/agents.yaml not found"

    def test_tasks_yaml_exists(self):
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "codecrew",
            "config",
            "tasks.yaml",
        )
        assert os.path.exists(config_path), "config/tasks.yaml not found"

    def test_agents_yaml_has_agentscope_pipeline_agents(self):
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "codecrew",
            "config",
            "agents.yaml",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        expected_agents = [
            "researcher",
            "spec_validator",
            "architect",
            "file_planner",
            "coder",
            "qa_agent",
            "readme_agent",
        ]

        for agent_name in expected_agents:
            assert agent_name in config, f"Missing '{agent_name}' agent"
            agent = config[agent_name]
            assert "role" in agent, f"{agent_name} missing 'role'"
            assert "goal" in agent, f"{agent_name} missing 'goal'"
            assert "backstory" in agent, f"{agent_name} missing 'backstory'"

    def test_tasks_yaml_has_agentscope_pipeline_tasks(self):
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "codecrew",
            "config",
            "tasks.yaml",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        expected_tasks = [
            "research_task",
            "spec_validation_task",
            "architecture_task",
            "file_planning_task",
            "coding_task",
            "qa_task",
            "readme_task",
        ]
        for task_name in expected_tasks:
            assert task_name in config, f"Missing '{task_name}'"
            task = config[task_name]
            assert "description" in task, f"{task_name} missing 'description'"
            assert "expected_output" in task, f"{task_name} missing 'expected_output'"
            assert "agent" in task, f"{task_name} missing 'agent'"


class TestProviders:
    def test_get_search_tool_duckduckgo(self):
        os.environ["SEARCH_PROVIDER"] = "duckduckgo"
        from codecrew.providers.search_provider import get_search_tool

        tool = get_search_tool()
        assert tool is not None
        assert tool.name == "DuckDuckGo Search"

    def test_get_search_tool_invalid_provider(self):
        os.environ["SEARCH_PROVIDER"] = "nonexistent_provider"
        from codecrew.providers.search_provider import get_search_tool

        with pytest.raises(ValueError, match="Unknown SEARCH_PROVIDER"):
            get_search_tool()

    def test_get_llm_invalid_provider(self):
        os.environ["LLM_PROVIDER"] = "nonexistent_provider"
        from codecrew.providers.llm_provider import get_llm

        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm()

    def test_resolve_provider_falls_back_from_ollama_to_free_ha(self, monkeypatch):
        import codecrew.model_configs as model_configs

        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(model_configs, "_http_endpoint_available", lambda url: False)

        assert model_configs.resolve_provider("ollama") == "free_ha"

    def test_resolve_provider_keeps_ollama_when_available(self, monkeypatch):
        import codecrew.model_configs as model_configs

        monkeypatch.setattr(model_configs, "_http_endpoint_available", lambda url: True)

        assert model_configs.resolve_provider("ollama") == "ollama"

    def test_validate_provider_setup_reports_pinggy_tunnel_failures(self, monkeypatch):
        import codecrew.model_configs as model_configs

        monkeypatch.setenv("OLLAMA_BASE_URL", "http://fygqh-34-9-238-55.a.free.pinggy.link")
        monkeypatch.setenv("OLLAMA_URL_REASONING", "http://fygqh-34-9-238-55.a.free.pinggy.link")
        monkeypatch.setenv("OLLAMA_URL_CODING", "http://iuloq-35-239-39-198.a.free.pinggy.link")
        monkeypatch.setenv("OLLAMA_URL_STRUCTURED", "http://fygqh-34-9-238-55.a.free.pinggy.link")
        monkeypatch.setattr(model_configs, "_probe_http_endpoint", lambda url: (False, "host could not be resolved"))

        with pytest.raises(ValueError, match="Pinggy/Kaggle tunnel check"):
            model_configs.validate_provider_setup("ollama")

    def test_validate_provider_setup_allows_reachable_ollama_endpoints(self, monkeypatch):
        import codecrew.model_configs as model_configs

        monkeypatch.setattr(model_configs, "_probe_http_endpoint", lambda url: (True, "HTTP 200"))

        model_configs.validate_provider_setup("ollama")
