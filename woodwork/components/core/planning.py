import logging
import os

from woodwork.components.core.core import core
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class planning_tools(core):
    def __init__(self, **config):
        format_kwargs(config, type="planning_tools")
        super().__init__(**config)
        fs_root = config.get("fs_root", ".woodwork/agent_fs")
        self.fs_root = os.path.abspath(os.path.normpath(fs_root))
        # Create a fresh todos.txt file on init
        todos_path = os.path.join(self.fs_root, "todos.txt")
        os.makedirs(os.path.dirname(todos_path), exist_ok=True)
        with open(todos_path, "w", encoding="utf-8") as f:
            f.write("")

    def _fs_path(self, file_path):
        return os.path.join(self.fs_root, file_path)

    def ls(self):
        """List all files in the agent filesystem."""
        files = []
        for root, _, filenames in os.walk(self.fs_root):
            for f in filenames:
                rel_path = os.path.relpath(os.path.join(root, f), self.fs_root)
                files.append(rel_path)
        return files

    def read_file(self, file_path, offset=0, limit=2000):
        """Read file contents with offset and limit."""
        abs_path = self._fs_path(file_path)
        if not os.path.exists(abs_path):
            return f"Error: File '{file_path}' not found"
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return "System reminder: File exists but has empty contents"
        lines = content.splitlines()
        start_idx = offset
        end_idx = min(start_idx + limit, len(lines))
        if start_idx >= len(lines):
            return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"
        result_lines = []
        for i in range(start_idx, end_idx):
            line_content = lines[i]
            if len(line_content) > 2000:
                line_content = line_content[:2000]
            line_number = i + 1
            result_lines.append(f"{line_number:6d}\t{line_content}")
        return "\n".join(result_lines)

    def write_file(self, file_path, content):
        """Write content to a file."""
        abs_path = self._fs_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Updated file {file_path}"

    def edit_file(self, file_path, old_string, new_string, replace_all=False):
        """Edit a file by replacing old_string with new_string."""
        abs_path = self._fs_path(file_path)
        if not os.path.exists(abs_path):
            return f"Error: File '{file_path}' not found"
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_string not in content:
            return f"Error: String not found in file: '{old_string}'"
        occurrences = content.count(old_string)
        if not replace_all:
            if occurrences > 1:
                return f"Error: String '{old_string}' appears {occurrences} times in file. Use replace_all=True to replace all instances, or provide a more specific string with surrounding context."
            elif occurrences == 0:
                return f"Error: String not found in file: '{old_string}'"
            new_content = content.replace(old_string, new_string, 1)
            result_msg = f"Successfully replaced string in '{file_path}'"
        else:
            new_content = content.replace(old_string, new_string)
            result_msg = f"Successfully replaced {occurrences} instance(s) of the string in '{file_path}'"
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return result_msg

    def write_todos(self, todos, state):
        """
        Write todos to a special file (todos.txt), supporting task states:
        pending, in_progress, completed.
        - If state is provided, mark all todos with that state. Default is pending.
        - If a todo already exists, update its state.
        - Only one todo can be in_progress at a time.
        - Prints whether each passed todo exists in the current todos.
        """
        # Normalize input
        if isinstance(todos, str):
            todos = [todos]

        abs_path = self._fs_path("todos.txt")
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # Read current todos
        current = {}
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format: [state] task
                    if line.startswith("[") and "] " in line:
                        s, t = line[1:].split("] ", 1)
                        t = t.strip()          # Remove extra whitespace
                        s = s.strip()
                        current[t] = s
                    else:
                        current[line.strip()] = "pending"
        
        if state is None:
            print("STATE NONE")
            state = "pending"

        # Check if todos exist and print
        for todo in todos:
            todo = todo.strip()
            if todo in current:
                print(f"Todo exists: '{todo}' (current state: {current[todo]})")
            else:
                print(f"Todo NOT found in current list: '{todo}'")

            # Update state
            current[todo] = state

        # Write back to file
        with open(abs_path, "w", encoding="utf-8") as f:
            for todo, st in current.items():
                f.write(f"[{st}] {todo}\n")
        
        print("DEBUG written todos:")
        with open(abs_path, "r", encoding="utf-8") as f:
            for line in f:
                print(repr(line.strip()))

        # Return updated todos
        return f"Updated todo list to {[(todo.strip(), current[todo.strip()]) for todo in todos]}"



    @property
    def description(self):
        return """
write_todos: Use this tool to create and manage a structured, stateful task list for your current work session. This tool supports explicit task states for each todo item, allowing you to track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

The functions can be called inside the inputs dictionary, with the key corresponding to the argument name and the value corresponding to the value passed as argument for that parameter.

## IMPORTANT: Research Before Planning

**Before using this tool, you MUST gather context about the task first:**

1. **Explore and understand** - Use available tools to research the task:
   - For bug fixes: Read the issue/ticket to understand what's broken
   - For features: Explore existing code patterns and architecture
   - For analysis: Locate and examine data sources
   - For general tasks: Identify constraints, requirements, and resources

2. **Assess complexity AFTER research** - Only create a plan once you understand what you're dealing with:
   - Simple (1-2 steps): Skip this tool, just execute
   - Moderate (3-5 steps): Use this tool for lightweight planning
   - Complex (6+ steps): Use this tool for detailed planning

3. **Do NOT plan blindly** - If someone says "solve issue #218", your FIRST action must be to read/fetch issue #218, NOT to create a plan.

**Examples of Research-First Approach:**
- "Solve GitHub issue #218" → First: fetch issue details. Then: assess complexity and plan if needed.
- "Add OAuth to the API" → First: explore existing auth code. Then: plan the integration.
- "Analyze sales data" → First: locate and examine data files. Then: plan analysis steps.

## Adaptive Planning: You Can Add Tasks Anytime

**This tool is not just for initial planning - use it adaptively throughout execution:**

- **Start simple**: You can begin without todos if a task seems straightforward
- **Add tasks mid-execution**: If you discover unexpected complexity or a difficult sub-task, create or add todos immediately
- **After research reveals more**: Initial research might reveal the task is bigger than expected - add todos to capture everything
- **When priorities shift**: User feedback or new information may require adding new tasks

**Examples:**
- You start fixing a bug without planning, but discover it requires changes in 5 different files → Add todos for each file
- Initial research shows the task touches authentication, database, and API layers → Create todos to track all three areas
- During execution, tests fail unexpectedly → Add a new todo: "Debug and fix failing tests"

The key: **Use todos whenever tracking would help you stay organized and not miss steps.**

## Function Signature and State Parameter

write_todos(todos, state=None)

- `todos`: List of strings (or a single string) representing tasks to track.
- `state`: String, one of "pending", "in_progress", or "completed". All todos passed as input will be marked with this state.

### Stateful Task Management

- Each todo is stored in `todos.txt` as `[state] task` (e.g., `[pending] Add dark mode toggle`).
- If a todo already exists, its state will be updated.
- Only ONE task can be marked as `in_progress` at a time. Setting a new task to `in_progress` will revert any other `in_progress` tasks to `pending`.
- Mark tasks as `completed` IMMEDIATELY after finishing them. Do not batch completions.
- Remove tasks that are no longer relevant from the list entirely.

## When to Use This Tool

Use this tool adaptively based on task complexity. You can use it at the start OR during execution:

**Always Use For:**
1. **Complex multi-step tasks** - Tasks requiring 6+ distinct steps with dependencies
2. **User explicit request** - When the user directly asks for a todo list or plan
3. **Multiple distinct deliverables** - When users provide a list of separate things to be done (numbered or comma-separated)
4. **Mid-execution discovery** - When a seemingly simple task reveals unexpected complexity

**Consider Using For (Moderate Complexity):**
1. **Multi-step tasks (3-5 steps)** - Tasks with some uncertainty or multiple operations
2. **Refactoring or debugging** - When you need to track changes across multiple locations
3. **Progress visibility** - When user would benefit from seeing step-by-step progress
4. **After research reveals scope** - When initial exploration shows more work than expected

**Do NOT Use For:**
1. **Simple tasks (1-2 steps)** - Straightforward, clear tasks with obvious approach
2. **Before research** - Never plan before understanding the task context
3. **Trivial operations** - Quick lookups, calculations, or single-action tasks
4. **Conversational requests** - Informational or explanatory requests

**Key Rule: Research → Assess → Plan (if needed) → Execute → Re-plan if complexity emerges**

Examples:
- ✅ "I need to migrate our auth system from JWT to OAuth2" → Complex, use write_todos after research
- ✅ "Help me with these 5 tasks: A, B, C, D, E" → Multiple tasks, use write_todos
- ⚠️ "Add a login form to the homepage" → Moderate, consider write_todos after exploring codebase
- ❌ "What's 2+2?" → Trivial, don't use write_todos
- ❌ "Fix issue #42" → Don't plan yet! First read issue #42, then decide

## Examples of When to Use the Todo List

<example>
User: Fix the login validation bug
Assistant: Let me first understand what the bug is.
*Reads bug report and examines the validation code*
Assistant: I see - the email regex is incorrect. This should be a simple fix.
*Fixes the regex in validators.py*
*Runs tests and discovers 15 test failures across multiple files*
Assistant: The fix revealed that the email validation is used in many places. Let me create a todo list to track fixing all the affected tests.
*Creates todo list:*
1. [in_progress] Fix email validation tests in test_auth.py
2. [pending] Fix email validation tests in test_user_profile.py
3. [pending] Fix email validation tests in test_registration.py
4. [pending] Update documentation for email validation
5. [pending] Verify all tests pass
*Begins fixing tests systematically*

<reasoning>
The assistant started without planning because it seemed like a simple bug fix. However, upon discovering the scope (15 test failures), it adaptively created a todo list mid-execution to track all the work. This demonstrates adaptive planning.
</reasoning>
</example>

<example>
User: I want to add a dark mode toggle to the application settings. Make sure you run the tests and build when you're done!
Assistant: I'll help add a dark mode toggle to your application settings. Let me create a todo list to track this implementation.
*Creates todo list with the following items:*
1. [pending] Create dark mode toggle component in Settings page
2. [pending] Add dark mode state management (context/store)
3. [pending] Implement CSS-in-JS styles for dark theme
4. [pending] Update existing components to support theme switching
5. [pending] Run tests and build process, addressing any failures or errors that occur
*Marks the first task as [in_progress] before starting work*
*Begins the first task*

<reasoning>
The assistant used the todo list because:
1. Adding dark mode is a multi-step feature requiring UI, state management, and styling changes
2. The user explicitly requested tests and build be run afterward
3. The assistant inferred that tests and build need to pass by adding "Ensure tests and build succeed" as the final task
</reasoning>
</example>

<example>
User: Help me plan a comprehensive marketing campaign for our new product launch, including social media, email marketing, and press releases.
Assistant: I'll help you plan a comprehensive marketing campaign for your product launch. Let me create a todo list to organize all the components.
*Creates todo list with the following items:*
1. [pending] Define target audience and key messaging
2. [pending] Create social media content calendar and posting schedule
3. [pending] Design email marketing sequence and automation flows
4. [pending] Draft press release and identify media contacts
5. [pending] Set up tracking and analytics for campaign performance
6. [pending] Create visual assets and brand materials
7. [pending] Coordinate launch timeline and deliverables
*Marks the first task as [in_progress] before starting work*
*Begins the first task*

<reasoning>
The assistant used the todo list because:
1. Marketing campaign planning involves multiple distinct channels and activities
2. Each component requires careful coordination and planning
3. The systematic approach ensures all aspects of the launch are covered
4. Progress tracking helps maintain timeline and deliverables
</reasoning>
</example>

<example>
User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project
Assistant: Let me first search through your codebase to find all occurrences of 'getCwd'.
*Uses search tools to locate all instances of getCwd in the codebase*
Assistant: I've found 15 instances of 'getCwd' across 8 different files. Let me create a todo list to track these changes.
*Creates todo list with specific items for each file that needs updating, all marked as [pending]*
*Marks the first item as [in_progress] before starting work*
*Begins starting work*

<reasoning>
The assistant used the todo list because:
1. First, the assistant searched to understand the scope of the task
2. Upon finding multiple occurrences across different files, it determined this was a complex task with multiple steps
3. The todo list helps ensure every instance is tracked and updated systematically
4. This approach prevents missing any occurrences and maintains consistency
</reasoning>
</example>

<example>
User: I need help organizing my home office: decluttering the desk, setting up a filing system, organizing digital files, and creating a daily workflow.
Assistant: I'll help you organize your home office systematically. Let me create a todo list to track each area of organization.
*Creates todo list with items like: [pending] Sort and declutter desk items, [pending] Set up physical filing system for documents, [pending] Organize digital files and folders, [pending] Create daily workflow and productivity systems, [pending] Establish maintenance routines*
*Marks the first task as [in_progress] before starting work*
Let's start with decluttering your desk space to create a clean foundation for the other organizational systems.

<reasoning>
The assistant used the todo list because:
1. The user provided multiple distinct organizational tasks
2. Each area requires different approaches and careful planning
3. Home organization benefits from systematic, step-by-step completion
4. Progress tracking ensures all areas are addressed thoroughly
</reasoning>
</example>

## Examples of When NOT to Use the Todo List

<example>
User: How do I print 'Hello World' in Python?
Assistant: In Python, you can print "Hello World" with this simple code:

python
print("Hello World")

This will output the text "Hello World" to the console when executed.

<reasoning>
The assistant did not use the todo list because this is a single, trivial task that can be completed in one step. There's no need to track multiple tasks or steps for such a straightforward request.
</reasoning>
</example>

<example>
User: What's the best way to water houseplants?
Assistant: The best way to water houseplants depends on the specific plant type, but here are some general guidelines:

- Check soil moisture by inserting your finger about 1-2 inches into the soil
- Water thoroughly when the top inch feels dry, allowing water to drain from the bottom
- Use room temperature water and water in the morning when possible
- Avoid overwatering, which is more harmful than underwatering for most plants

Different plants have different needs, so it's important to research your specific varieties for optimal care.

<reasoning>
The assistant did not use the todo list because this is an informational request with no actual tasks to complete. The user is simply asking for advice and explanation, not for the assistant to perform multiple steps or activities.
</reasoning>
</example>

<example>
User: Can you add a comment to the calculateTotal function to explain what it does?
Assistant: Sure, let me add a comment to the calculateTotal function to explain what it does.
* Uses the Edit tool to add a comment to the calculateTotal function *

<reasoning>
The assistant did not use the todo list because this is a single, straightforward task confined to one location. Adding a comment doesn't require tracking multiple steps or systematic organization.
</reasoning>
</example>

<example>
User: What time is it in Tokyo right now?
Assistant: I'll check the current time in Tokyo for you.

*Searches for current time in Tokyo*

The current time in Tokyo, Japan is [current time]. Tokyo is in the Japan Standard Time (JST) zone, which is UTC+9.

<reasoning>
The assistant did not use the todo list because this is a single information lookup with immediate results. There are no multiple steps to track or organize, making the todo list unnecessary for this straightforward request.
</reasoning>
</example>

## Task States and Management

1. **Task States**: Use these states to track progress:
    - pending: Task not yet started
    - in_progress: Currently working on (limit to ONE task at a time)
    - completed: Task finished successfully

2. **Task Management**:
    - Update task status in real-time as you work
    - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
    - Only have ONE task in_progress at any time
    - Complete current tasks before starting new ones
    - Remove tasks that are no longer relevant from the list entirely

3. **Task Completion Requirements**:
    - ONLY mark a task as completed when you have FULLY accomplished it
    - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
    - When blocked, create a new task describing what needs to be resolved
    - Never mark a task as completed if:
      - There are unresolved issues or errors
      - Work is partial or incomplete
      - You encountered blockers that prevent completion
      - You couldn't find necessary resources or dependencies
      - Quality standards haven't been met

4. **Task Breakdown**:
    - Create specific, actionable items
    - Break complex tasks into smaller, manageable steps
    - Use clear, descriptive task names

When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.

See docstrings and examples for more details on each tool.

These tools all come under the planning_tools namespace. To access a tool, for example write_todos, you should specify the tool as "planning_tools", and then the specific tool as the action, in this case it would be "write_todos". You can then pass the inputs in as normal, knowing that they are the inputs of write_todos.
"""

    file_mangement_prompt = """
read_file: Reads a file from the agent filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files in the agent filesystem. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be relative to the agent filesystem root
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Any lines longer than 2000 characters will be truncated
- Results are returned using cat -n format, with line numbers starting at 1
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful. 
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.

edit_file: Performs exact string replacements in files. 

Usage:
- You must use your `read_file` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. 
- When editing text from read_file output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`. 
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.

write_file: Writes content to a file in the agent filesystem.

ls: Lists all files in the agent filesystem.
"""

    def input(self, action: str, inputs: dict = {}):
        """Dispatches the requested action to the appropriate tool method."""
        # Substitute variables in action string using inputs
        for key in inputs:
            action = action.replace(f"{{{key}}}", str(inputs[key]))

        # Map action to method
        if action == "ls":
            return self.ls()
        elif action == "read_file":
            return self.read_file(inputs.get("file_path"), inputs.get("offset", 0), inputs.get("limit", 2000))
        elif action == "write_file":
            return self.write_file(inputs.get("file_path"), inputs.get("content", ""))
        elif action == "edit_file":
            return self.edit_file(
                inputs.get("file_path"),
                inputs.get("old_string"),
                inputs.get("new_string"),
                inputs.get("replace_all", False),
            )
        elif action == "write_todos":
            return self.write_todos(
                todos=inputs.get("todos", []),
                state=inputs.get("state")
            )
        else:
            return f"Error: Unknown action '{action}'"
