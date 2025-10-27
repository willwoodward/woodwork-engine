class ChatPromptTemplate:
    """Minimal stub of langchain_core.prompts.ChatPromptTemplate used in tests.

    from_messages(...) -> returns an instance. Using the '|' operator with an LLM-like
    object returns a Chain whose invoke(...) calls the wrapped llm.invoke(...) and
    returns that result.
    """

    def __init__(self, messages=None):
        self.messages = messages or []

    @classmethod
    def from_messages(cls, msgs):
        return cls(messages=msgs)

    def __or__(self, other):
        # Return a chain that calls other.invoke(inputs) when invoked
        class Chain:
            def __init__(self, prompt, llm):
                self.prompt = prompt
                self.llm = llm

            def invoke(self, inputs):
                # If the underlying llm has invoke, call it
                if hasattr(self.llm, "invoke"):
                    return self.llm.invoke(inputs)
                # Otherwise, try calling as a callable
                if callable(self.llm):
                    return self.llm(inputs)
                # Fallback: return a simple object with .content attribute
                class Resp:
                    def __init__(self, content):
                        self.content = content
                return Resp(str(inputs))

        return Chain(self, other)
