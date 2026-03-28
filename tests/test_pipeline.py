import pytest
from codecrew.pipeline import CodeCrewPipeline

def test_pipeline_initialization():
    pipeline = CodeCrewPipeline(output_dir="./mock", human_override=False)
    assert pipeline.output_dir.endswith("mock")
    assert pipeline.human_override is False

# Skipping full E2E execution because it requires LLM keys, but verifying setup.
