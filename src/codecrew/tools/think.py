def think(thought: str) -> str:
    """
    Record reasoning and return it unchanged.

    Args:
        thought (str): Internal reasoning before choosing another action.

    Returns:
        str: The recorded thought content.
    """
    if not thought:
        return "Thought recorded."
    return f"Thought recorded: {thought}"
