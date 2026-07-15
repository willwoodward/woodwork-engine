"""Life Assistant — Python API example.

Python equivalent of examples/life-assistant/main.ww.

Run (deployed / interactive CLI mode):
    python main.py

Run (programmatic):
    python main.py --query "What's the weather in London?"
"""

import asyncio
import sys

from woodwork import Runtime, File, Env, Event
from woodwork.llms import OpenAI
from woodwork.tools import MCP
from woodwork.agents import Agent
from woodwork.inputs import CommandLine
from woodwork.utils import configure_logging, load_envfile, LogLevel

# ── Setup ────────────────────────────────────────────────────────────────────

load_envfile()                          # read .env in the current directory
configure_logging(LogLevel.INFO)       # change to LogLevel.INFO for verbose output

# ── Components ───────────────────────────────────────────────────────────────

model = OpenAI(
    name="model",
    api_key=Env("OPENAI_API_KEY"),
    model="gpt-4o-mini",
)

search = MCP(
    name="search",
    server="duckduckgo/mcp-server",
)

cli = CommandLine(name="cli")

assistant = Agent(
    name="assistant",
    model=model,
    tools=[search],
    input=cli,
    prompt=File("prompts/life-assistant.txt"),
)

# ── Observability (optional) ─────────────────────────────────────────────────

@assistant.hook(Event.Agent.TOOL_CALL)
def log_tool_call(payload):
    print(f"[tool] {payload}")


@assistant.pipe(Event.Agent.ACTION)
def transform_action(payload):
    # Passthrough — add custom transformation logic here if needed
    return payload


# ── Entry points ─────────────────────────────────────────────────────────────

def run_deployed():
    """Blocking CLI loop — mirrors the .ww deployed mode."""
    Runtime([model, search, cli, assistant]).start()


async def run_programmatic(query: str):
    """Single-query programmatic mode."""
    async with Runtime(assistant) as rt:
        result = await assistant.send(query)
        print(result)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--query":
        query = " ".join(sys.argv[2:]) or "Hello!"
        asyncio.run(run_programmatic(query))
    else:
        run_deployed()
