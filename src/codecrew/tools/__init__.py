from agentscope.service import ServiceToolkit
from codecrew.tools.file_writer import write_file
from codecrew.tools.code_executor import execute_command
from codecrew.tools.execution_loop import execution_loop
from codecrew.tools.readers import list_files_in_directory, read_file_content
from codecrew.providers.search_provider import get_search_tool
from functools import partial

def build_toolkit(role: str, base_dir: str = "./output") -> ServiceToolkit:
    """
    Build and return a ServiceToolkit for a given agent role.
    
    Args:
        role (str): The role of the agent ("research", "coding", "qa").
        base_dir (str): The project's root output directory.
        
    Returns:
        ServiceToolkit: The toolkit populated with safe, pre-configured tools.
    """
    toolkit = ServiceToolkit()
    # Bind base_dir to the file operations using functools.partial so agents don't have to provide it.
    
    bound_write_file = partial(write_file, base_dir=base_dir)
    bound_write_file.__doc__ = write_file.__doc__
    bound_write_file.__name__ = "write_file"
    
    bound_execution_loop = partial(execution_loop, base_dir=base_dir)
    bound_execution_loop.__doc__ = execution_loop.__doc__
    bound_execution_loop.__name__ = "execution_loop"

    bound_execute_command = partial(execute_command, working_directory=base_dir)
    bound_execute_command.__doc__ = execute_command.__doc__
    bound_execute_command.__name__ = "execute_command"

    if role == "research":
        search_func = get_search_tool()
        toolkit.add(search_func)
    
    elif role == "coding":
        toolkit.add(list_files_in_directory)
        toolkit.add(read_file_content)
        toolkit.add(bound_execution_loop)
        
    elif role == "qa":
        toolkit.add(list_files_in_directory)
        toolkit.add(read_file_content)
        toolkit.add(bound_execute_command)
        toolkit.add(bound_write_file) # README agent needs write access

    return toolkit
