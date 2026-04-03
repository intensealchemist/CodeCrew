from codecrew.tools.file_writer import write_file
from codecrew.tools.code_executor import execute_command
from codecrew.tools.execution_loop import execution_loop
from codecrew.tools.readers import list_files_in_directory as _list_files_in_directory
from codecrew.tools.readers import read_file_content as _read_file_content
from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codecrew.rag import RAGStore


# ---------------------------------------------------------------------------
# Decorator: ensure tool functions always return ToolResponse
# ---------------------------------------------------------------------------

def _to_tool_response(func):
    """Wrap a str-returning function so it always returns a ToolResponse."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        from agentscope.tool import ToolResponse
        from agentscope.message import TextBlock
        res = func(*args, **kwargs)
        if isinstance(res, str):
            return ToolResponse(content=[TextBlock(type="text", text=res)])
        return res
    return wrapper


# ---------------------------------------------------------------------------
# Module-level tools (no base_dir binding needed)
# ---------------------------------------------------------------------------

@_to_tool_response
def list_files_in_directory(directory_path: str) -> str:
    """
    List all files and subdirectories within a given directory.

    Args:
        directory_path (str): Path to the directory to inspect (e.g. './src').

    Returns:
        str: Newline-separated list of entries, or an error message.
    """
    return _list_files_in_directory(directory_path)


@_to_tool_response
def read_file_content(file_path: str) -> str:
    """
    Read and return the full text content of a file.

    Args:
        file_path (str): Path to the file (e.g. './src/main.py').

    Returns:
        str: File content, or an error message if the file cannot be read.
    """
    return _read_file_content(file_path)


# ---------------------------------------------------------------------------
# RAG tool factory
# ---------------------------------------------------------------------------

def build_rag_tool(rag_store: "RAGStore"):
    """Return a ``retrieve_context`` tool function bound to *rag_store*.

    The returned function is already wrapped with ``_to_tool_response`` and
    has a stable ``__name__`` so AgentScope can register it correctly.
    """

    @_to_tool_response
    def retrieve_context(query: str, n_results: int = 5) -> str:
        """
        Retrieve the most relevant context from the project knowledge base (RAG).

        Use this tool BEFORE writing any file to check:
        - Interface contracts and function signatures from the spec
        - Architecture decisions relevant to the current file
        - Content of already-written files to avoid import mismatches

        Args:
            query (str): Natural language description of what context you need.
                         Examples: "user authentication function signatures",
                                   "database schema for orders table",
                                   "error handling strategy".
            n_results (int): Number of top chunks to return (default 5, max 10).

        Returns:
            str: Relevant context chunks formatted as markdown, ready to use.
        """
        n = min(max(1, n_results), 3)
        context = rag_store.retrieve(query=query, n_results=n)
        if len(context) > 6000:
            return context[:6000] + "\n\n[retrieve_context output truncated]"
        return context

    retrieve_context.__name__ = "retrieve_context"
    return retrieve_context


# ---------------------------------------------------------------------------
# Toolkit factory
# ---------------------------------------------------------------------------

def build_toolkit(role: str, base_dir: str = "./output", rag_store: "RAGStore | None" = None):
    """Build and return a role-scoped AgentScope Toolkit.

    Args:
        role (str):      Agent role — one of: 'architect', 'coding', 'qa', 'docs'.
        base_dir (str):  Absolute or relative root output directory for the job.
        rag_store:       Optional RAGStore instance.  When provided, a
                         ``retrieve_context`` tool is added to roles that benefit
                         from semantic retrieval (coding, qa, docs).

    Returns:
        Toolkit: Pre-configured AgentScope Toolkit for the given role.
    """
    try:
        from agentscope.tool import Toolkit
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "agentscope is required. Install project dependencies first."
        ) from exc

    toolkit = Toolkit()

    # ── Bound helpers (capture base_dir in closure) ──────────────────────────

    @_to_tool_response
    def bound_write_file(filepath: str, content: str) -> str:
        """
        Write content to a file inside the project output directory.
        Parent directories are created automatically.

        Args:
            filepath (str): Relative path within the project (e.g. 'src/main.py').
            content (str):  Complete file content to write.

        Returns:
            str: Success message or error description.
        """
        return write_file(filepath=filepath, content=content, base_dir=base_dir)

    @_to_tool_response
    def bound_execution_loop(
        file_path: str,
        code_content: str,
        lint_command: str = "",
        test_command: str = "",
    ) -> str:
        """
        Write code to a file, then run optional lint and test commands.
        Prefer this over write_file when you know the lint/test commands.

        Args:
            file_path (str):    Relative path to write (e.g. 'src/utils.py').
            code_content (str): Complete source code to write.
            lint_command (str): Shell lint command (e.g. 'flake8 src/utils.py'). Empty = skip.
            test_command (str): Shell test command (e.g. 'pytest tests/'). Empty = skip.

        Returns:
            str: Success message, or failure output with fix instructions.
        """
        return execution_loop(
            file_path=file_path,
            code_content=code_content,
            lint_command=lint_command,
            test_command=test_command,
            base_dir=base_dir,
        )

    @_to_tool_response
    def bound_execute_command(command: str) -> str:
        """
        Execute a shell command inside the project output directory.

        Args:
            command (str): The command to run (e.g. 'pip install -r requirements.txt').

        Returns:
            str: Combined stdout/stderr output, or an error block.
        """
        return execute_command(command=command, working_directory=base_dir)

    bound_write_file.__name__ = "write_file"
    bound_execution_loop.__name__ = "execution_loop"
    bound_execute_command.__name__ = "execute_command"

    # ── Role → tool mapping ──────────────────────────────────────────────────

    normalized = role.strip().lower()

    if normalized == "architect":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_write_file)

    elif normalized == "coding":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_write_file)
        toolkit.register_tool_function(bound_execution_loop)
        if rag_store is not None:
            toolkit.register_tool_function(build_rag_tool(rag_store))

    elif normalized == "qa":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_execute_command)
        toolkit.register_tool_function(bound_write_file)
        if rag_store is not None:
            toolkit.register_tool_function(build_rag_tool(rag_store))

    elif normalized == "docs":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_write_file)
        if rag_store is not None:
            toolkit.register_tool_function(build_rag_tool(rag_store))

    else:
        raise ValueError(
            f"Unknown toolkit role: '{role}'. Valid roles: architect, coding, qa, docs"
        )

    return toolkit
