from langchain_core.tools import tool

@tool
def flow_tool():
    """
    Revisar el flow de conversacion ideal
    """
    with open("flows.md", "r", encoding="utf-8") as f:
        return f.read()