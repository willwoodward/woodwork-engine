# Simple runner for the claude unit tests (does not require pytest)
import sys
from unittest.mock import patch

# Import the module under test
from woodwork.components.llms import claude as claude_mod
from woodwork.components.llms.claude import claude
import woodwork.components.llms.llm as llm_mod


class DummyResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, inputs):
        return DummyResponse("fake-answer")


class FakePrompt:
    @staticmethod
    def from_messages(msgs):
        return FakePrompt()

    def __or__(self, other):
        class Chain:
            def __init__(self, llm):
                self._llm = llm

            def invoke(self, inputs):
                if hasattr(self._llm, "invoke"):
                    return self._llm.invoke(inputs)
                return DummyResponse("no-invoke")

        return Chain(other)


def run_test_input_uses_llm():
    # Patch ChatPromptTemplate used in the llm base module
    with patch.object(llm_mod, "ChatPromptTemplate", FakePrompt):
        c = claude(api_key="test-key")
        c._llm_value = FakeLLM()
        result = c.input("What is 2+2?")
        if result != "fake-answer":
            print(f"test_claude_input_uses_llm FAILED: expected 'fake-answer', got '{result}'")
            return 1
        print("test_claude_input_uses_llm PASSED")
        return 0


def run_test_start_initializes_llm():
    # Patch ChatAnthropic in the claude module to return FakeLLM
    with patch.object(claude_mod, "ChatAnthropic", lambda *args, **kwargs: FakeLLM()):
        c = claude(api_key="test-key")
        c.start(None)
        if not isinstance(c._llm_value, FakeLLM):
            print(f"test_claude_start_initializes_llm FAILED: _llm_value is not FakeLLM: {type(c._llm_value)}")
            return 1
        print("test_claude_start_initializes_llm PASSED")
        return 0


def main():
    errors = 0
    errors += run_test_input_uses_llm()
    errors += run_test_start_initializes_llm()
    if errors == 0:
        print("All claude tests passed")
        sys.exit(0)
    else:
        print(f"{errors} test(s) failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
