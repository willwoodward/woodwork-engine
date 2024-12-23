from woodwork import tool_interface


class PaperSearchTool(tool_interface):
    def __init__(self):
        pass

    def search(self, query):
        return

    @property
    def description(self):
        return """Contains functionality to interact with papers on arxiv. The following functions can be used, with their inputs:
        search(query) - Returns a result
        To use these functions, specify only the function name as the action, and pass the key word arguments in the inputs dictionary.
    """

    def input(action: str, inputs: dict):
        return "Output of the input"
