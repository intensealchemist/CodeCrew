from codecrew.tools.file_writer import write_file
from codecrew.tools.code_executor import execute_command
from codecrew.tools.execution_loop import execution_loop
from codecrew.tools.readers import list_files_in_directory, read_file_content
from functools import partial

def build_toolkit(role: str, base_dir: str = "./output"):
    """
    Build and return a Toolkit for a given agent role.
    
    Args:
        role (str): The role of the agent ("research", "coding", "qa").
        base_dir (str): The project's root output directory.
        
    Returns:
        Toolkit: The toolkit populated with safe, pre-configured tools.
    """
    try:
        from agentscope.tool import Toolkit
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "agentscope is required to build the toolkit. Install project dependencies first."
        ) from exc

    toolkit = Toolkit()
    
    bound_write_file = partial(write_file, base_dir=base_dir)
    bound_write_file.__doc__ = write_file.__doc__
    bound_write_file.__name__ = "write_file"
    
    bound_execution_loop = partial(execution_loop, base_dir=base_dir)
    bound_execution_loop.__doc__ = execution_loop.__doc__
    bound_execution_loop.__name__ = "execution_loop"

    bound_execute_command = partial(execute_command, working_directory=base_dir)
    bound_execute_command.__doc__ = execute_command.__doc__
    bound_execute_command.__name__ = "execute_command"

    normalized_role = role.strip().lower()

    if normalized_role == "research":
        from codecrew.providers.search_provider import get_search_tool
        search_func = get_search_tool()
        toolkit.register_tool_function(search_func)
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
    
    elif normalized_role == "architect":
        from codecrew.providers.search_provider import get_search_tool
        search_func = get_search_tool()
        toolkit.register_tool_function(search_func)
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_write_file)

    elif normalized_role == "coding":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_execution_loop)
        
    elif normalized_role == "qa":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_execute_command)
        toolkit.register_tool_function(bound_write_file)

    elif normalized_role == "docs":
        toolkit.register_tool_function(list_files_in_directory)
        toolkit.register_tool_function(read_file_content)
        toolkit.register_tool_function(bound_write_file)

    else:
        raise ValueError(f"Unknown toolkit role: {role}")

    return toolkit
