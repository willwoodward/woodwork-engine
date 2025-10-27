import pytest

from woodwork.components.llms.claude import claude
import woodwork.components.llms.llm as llm_mod


class DummyResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, *args, **kwargs):
        # simulate an LLM object that supports invoke
        pass

    def invoke(self, inputs):
        # Return a dummy response object similar to langchain's response
        return DummyResponse("fake-answer")


class FakePrompt:
    @staticmethod
    def from_messages(msgs):
        return FakePrompt()

    def __or__(self, other):
        # Create a simple chain object that calls the wrapped llm.invoke
        class Chain:
            def __init__(self, llm):
                self._llm = llm

            def invoke(self, inputs):
                if hasattr(self._llm, "invoke"):
                    return self._llm.invoke(inputs)
                return DummyResponse("no-invoke")

        return Chain(other)


def test_claude_input_uses_llm(monkeypatch):
    """Ensure claude.input uses the underlying LLM invoke via the prompt|llm chain."""
    # Patch ChatPromptTemplate used in the llm base module
    monkeypatch.setattr(llm_mod, "ChatPromptTemplate", FakePrompt)

    c = claude(api_key="test-key")
    # Inject a fake llm value that returns a predictable response
    c._llm_value = FakeLLM()

    result = c.input("What is 2+2?")
    assert result == "fake-answer"


def test_claude_start_initializes_llm(monkeypatch):
    """Ensure claude.start constructs a ChatAnthropic instance and assigns it to _llm_value."""
    import woodwork.components.llms.claude as claude_mod

    # Patch ChatAnthropic in the claude module to return our FakeLLM
    monkeypatch.setattr(claude_mod, "ChatAnthropic", lambda *args, **kwargs: FakeLLM())

    c = claude(api_key="test-key")
    # Call start (no actual multiprocessing queue needed here)
    c.start(None)

    assert isinstance(c._llm_value, FakeLLM)
