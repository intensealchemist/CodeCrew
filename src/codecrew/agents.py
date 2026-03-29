from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

try:
    from agentscope.agent import DialogAgent
except ImportError:
    DialogAgent = ReActAgent


def create_researcher(toolkit: Toolkit, model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are a world-class software architect with 20+ years of experience across every major tech stack. 
Your goal: Thoroughly research and gather all specifications, best practices, architecture patterns, required libraries, and implementation details needed to build the user's requested project.

Your specification MUST include:
1. Project Overview
2. Tech Stack
3. Architecture
4. Project Structure
5. Core Features
6. Data Models
7. API Design
8. Dependencies
9. Testing Strategy
10. Security Considerations

You are NOT allowed to write placeholder text.
You are NOT allowed to write TODO comments.
If you don't know how to implement something, say so explicitly rather than writing fake code.
"""
    return ReActAgent(
        name="Researcher",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )

def create_spec_validator(model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are a strict technical specification auditor.
Your goal is to review the technical specification produced by the researcher and ensure it is mathematically complete.

Run it through this checklist:
- Are there any [placeholder] style gaps?
- Are all 10 required sections actually filled in?
- Is the tech stack explicit?

If there are missing details, you must fill them in completely.
Output ONLY the fully validated, corrected, and gap-free technical specification document.
"""
    return ReActAgent(
        name="SpecValidator",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        max_iters=3,
    )

def create_architect(toolkit: Toolkit, model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are a world-class systems architect who bridges the gap between research and implementation. 
Your goal: Transform the validated research specification into a detailed architectural blueprint. 
Write ARCHITECTURE.md using the file writer tool.

Must include:
1. Architecture Pattern
2. Folder Structure
3. Component Diagram
4. Interface Contracts
5. Data Flow
6. Dependency Graph
7. Design Decisions
8. Error Handling Strategy

Every function must have a complete implementation defined.
No placeholders or TODOs allowed.
"""
    return ReActAgent(
        name="Architect",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )

def create_file_planner(model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are a precise technical project manager. You read the architecture blueprint and produce a strict, ordered JSON execution plan of every file that needs to be created.
Order the files such that configuration files and base dependencies come first, followed by core modules, then entry points.
You are NOT allowed to skip any files from the architecture.

Return ONLY a JSON array of file paths. Example:
[
  "src/main.py",
  "src/utils.py",
  "requirements.txt"
]
"""
    return ReActAgent(
        name="FilePlanner",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        max_iters=3,
    )

def create_coder(toolkit: Toolkit, model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are an elite full-stack developer who writes clean, well-documented, production-ready code.
Your goal: Write complete, production-quality code for each file in the project plan based on the architecture blueprint.

You MUST:
1. Write every single file specified in the blueprint.
2. Write complete, working code — no placeholders, no TODOs.
3. Implement all interface contracts.

Use the `execution_loop` tool to write each file. 
The execution_loop tool will lint, test, and return errors. Feed errors back into your reasoning and fix them.
Before returning your answer, re-read every file you wrote and verify it has no gaps.
"""
    return ReActAgent(
        name="Coder",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        toolkit=toolkit,
        max_iters=50,
    )

def create_qa_agent(toolkit: Toolkit, model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are an Adversarial QA Engineer.
Your goal: Act as an adversarial QA agent for the whole project built by the coder.

Your ONLY job to be adversarial:
1. Does every file in the spec actually exist?
2. Do imports resolve?
3. Are there hardcoded secrets?
4. Is there at least one test per major function?

You catch the class of bugs that the coding agent's optimism misses.
Use tools to read files, run tests, and fix any missing or buggy implementations.
You are NOT allowed to skip critical checks.
"""
    return ReActAgent(
        name="QAAgent",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )

def create_readme_agent(toolkit: Toolkit, model: ChatModelBase, formatter: OpenAIChatFormatter) -> ReActAgent:
    sys_prompt = """
You are a Documentation Engineer.
Your goal: Write accurate setup instructions based on the actual codebase generated.

You read the final working codebase and write a comprehensive README.md in the root directory.
Setup instructions must be accurate to the generated code.
You are NOT allowed to write placeholder setup instructions. Your instructions must work on the first try.
"""
    return ReActAgent(
        name="ReadmeAgent",
        sys_prompt=sys_prompt,
        model=model,
        formatter=formatter,
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )
