from colorama import Fore, Style

class WoodworkException(Exception):
    """Base class for all configuration errors with custom formatting."""
    def __init__(self, message, line=None, column=None, line_content=None):
        self.message = message
        self.line = line
        self.column = column
        self.line_content = line_content

    def __str__(self):
        # Basic error message
        start_bold = "\033[1m"
        end_bold = "\033[0m"
        formatted_message = f"{start_bold}{Fore.RED}{self.__class__.__name__}:{end_bold} {self.message}{Style.RESET_ALL}"

        # Add line and column details, if available
        if self.line and self.line_content:
            indicator = " " * (self.column - 1) + f"{Fore.CYAN}^{Style.RESET_ALL}"
            formatted_message += (
                f"\nLine {Fore.YELLOW}{self.line}{Style.RESET_ALL}: {self.line_content.strip()}\n"
                f"{indicator}"
            )
        
        return formatted_message

class ForbiddenVariableNameError(WoodworkException):
    pass