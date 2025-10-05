"""
Minimal FastAPI server for personal productivity features.

Stores data in JSON files and integrates with Woodwork agents for workflow matching.
Run with: python personal_server.py
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory - store JSON files locally in data/ folder
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TASKS_FILE = DATA_DIR / "tasks.json"
SUGGESTIONS_FILE = DATA_DIR / "suggestions.json"
INSIGHTS_FILE = DATA_DIR / "insights.json"
TAGS_FILE = DATA_DIR / "tags.json"


# ===== Pydantic Models =====

class Task(BaseModel):
    id: str
    title: str
    tags: List[str] = []
    estimatedTime: Optional[int] = None
    priority: str = "medium"
    dateCreated: str
    dateCompleted: Optional[str] = None
    actualTime: Optional[int] = None
    effortRating: Optional[int] = None
    workflowUsed: Optional[str] = None
    notes: Optional[str] = None
    completed: bool = False


class Suggestion(BaseModel):
    id: str
    type: str  # 'workflow' | 'optimization' | 'batching'
    title: str
    description: str
    relatedTasks: Optional[List[str]] = []
    dateCreated: str
    accepted: Optional[bool] = None


class Insight(BaseModel):
    id: str
    type: str  # 'repetition' | 'bottleneck' | 'optimization'
    title: str
    description: str
    relatedTasks: Optional[List[str]] = []
    dateCreated: str


class WorkflowMatchRequest(BaseModel):
    taskTitle: str
    taskDescription: Optional[str] = None
    tags: Optional[List[str]] = []


class WorkflowMatchAction(BaseModel):
    id: str
    name: str
    description: str


class WorkflowGraphNode(BaseModel):
    id: str
    type: str  # 'prompt' | 'action'
    label: str


class WorkflowGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # 'starts' | 'next' | 'depends_on'


class WorkflowGraphData(BaseModel):
    nodes: List[WorkflowGraphNode]
    edges: List[WorkflowGraphEdge]


class WorkflowMatchResponse(BaseModel):
    canUseWorkflow: bool
    workflowId: Optional[str] = None
    workflowName: Optional[str] = None
    confidence: Optional[float] = None
    actions: Optional[List[WorkflowMatchAction]] = []
    graph: Optional[WorkflowGraphData] = None
    message: Optional[str] = None


# ===== JSON Storage =====

def load_json(file_path: Path) -> List[Dict]:
    """Load data from JSON file."""
    if not file_path.exists():
        return []
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return []


def save_json(file_path: Path, data: List[Dict]):
    """Save data to JSON file."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")
        raise


# ===== FastAPI App =====

app = FastAPI(title="Woodwork Personal Productivity Server")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Tasks Endpoints =====

@app.get("/tasks", response_model=List[Task])
async def get_tasks():
    """Get all tasks."""
    tasks = load_json(TASKS_FILE)
    return tasks


@app.post("/tasks", response_model=Task)
async def create_task(task: Task):
    """Create a new task."""
    tasks = load_json(TASKS_FILE)

    # Generate ID if not provided
    if not task.id:
        task.id = str(uuid4())

    # Set creation date if not provided
    if not task.dateCreated:
        task.dateCreated = datetime.now().isoformat()

    tasks.append(task.dict())
    save_json(TASKS_FILE, tasks)

    logger.info(f"Created task: {task.title}")
    return task


@app.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, updates: Dict[str, Any]):
    """Update a task."""
    tasks = load_json(TASKS_FILE)

    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks[i].update(updates)
            save_json(TASKS_FILE, tasks)
            logger.info(f"Updated task: {task_id}")
            return tasks[i]

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    tasks = load_json(TASKS_FILE)

    tasks = [t for t in tasks if t["id"] != task_id]
    save_json(TASKS_FILE, tasks)

    logger.info(f"Deleted task: {task_id}")
    return {"status": "success"}


# ===== Suggestions & Insights =====

@app.get("/tasks/suggestions", response_model=List[Suggestion])
async def get_suggestions():
    """Get workflow suggestions."""
    suggestions = load_json(SUGGESTIONS_FILE)
    return suggestions


@app.get("/tasks/insights", response_model=List[Insight])
async def get_insights():
    """Get pattern insights."""
    insights = load_json(INSIGHTS_FILE)
    return insights


# ===== Tags Endpoints =====

@app.get("/api/tags", response_model=List[str])
async def get_tags():
    """Get all available tags."""
    tags = load_json(TAGS_FILE)
    return tags


class AddTagRequest(BaseModel):
    tag: str


@app.post("/api/tags", response_model=List[str])
async def add_tag(request: AddTagRequest):
    """Add a new tag."""
    tags = load_json(TAGS_FILE)

    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")

    if tag not in tags:
        tags.append(tag)
        save_json(TAGS_FILE, tags)
        logger.info(f"Added tag: {tag}")

    return tags


@app.delete("/api/tags/{tag}", response_model=List[str])
async def remove_tag(tag: str):
    """Remove a tag."""
    tags = load_json(TAGS_FILE)

    if tag in tags:
        tags.remove(tag)
        save_json(TAGS_FILE, tags)
        logger.info(f"Removed tag: {tag}")

    return tags


# ===== Workflow Matching (Agent Integration) =====

@app.post("/tasks/match-workflow", response_model=WorkflowMatchResponse)
async def match_workflow(request: WorkflowMatchRequest):
    """
    Check if a task can be solved with an existing workflow.

    For testing: Returns mock workflow matches with graph data.
    TODO: Integrate with Woodwork agents and Neo4j for real workflow matching.
    """
    task_lower = request.taskTitle.lower()

    # Mock workflow matching based on keywords
    if any(keyword in task_lower for keyword in ['review', 'pr', 'pull request', 'code review']):
        return WorkflowMatchResponse(
            canUseWorkflow=True,
            workflowId="workflow-code-review",
            workflowName="Code Review Workflow",
            confidence=0.92,
            actions=[
                WorkflowMatchAction(id="a1", name="Checkout PR branch", description="git: checkout pr/branch"),
                WorkflowMatchAction(id="a2", name="Run tests locally", description="npm: test"),
                WorkflowMatchAction(id="a3", name="Check test coverage", description="coverage: check minimum 80%"),
                WorkflowMatchAction(id="a4", name="Review code changes", description="Read through diff, check for issues"),
                WorkflowMatchAction(id="a5", name="Verify documentation", description="Ensure README and docs are updated"),
            ],
            graph=WorkflowGraphData(
                nodes=[
                    WorkflowGraphNode(id="n1", type="prompt", label="Review pull request"),
                    WorkflowGraphNode(id="n2", type="action", label="git:checkout pr/branch"),
                    WorkflowGraphNode(id="n3", type="action", label="npm:test"),
                    WorkflowGraphNode(id="n4", type="action", label="coverage:check"),
                    WorkflowGraphNode(id="n5", type="action", label="review:code-diff"),
                    WorkflowGraphNode(id="n6", type="action", label="docs:verify-updated"),
                ],
                edges=[
                    WorkflowGraphEdge(id="e1", source="n1", target="n2", type="starts"),
                    WorkflowGraphEdge(id="e2", source="n2", target="n3", type="next"),
                    WorkflowGraphEdge(id="e3", source="n3", target="n4", type="next"),
                    WorkflowGraphEdge(id="e4", source="n4", target="n5", type="next"),
                    WorkflowGraphEdge(id="e5", source="n5", target="n6", type="next"),
                ]
            ),
            message="Found matching workflow used 8 times"
        )

    elif any(keyword in task_lower for keyword in ['bug', 'fix', 'issue', 'error', 'debug']):
        return WorkflowMatchResponse(
            canUseWorkflow=True,
            workflowId="workflow-bug-fix",
            workflowName="Bug Fix Investigation Workflow",
            confidence=0.88,
            actions=[
                WorkflowMatchAction(id="a1", name="Reproduce the bug", description="Follow steps to consistently trigger the issue"),
                WorkflowMatchAction(id="a2", name="Check error logs", description="Review application and server logs"),
                WorkflowMatchAction(id="a3", name="Add debug logging", description="Insert strategic console.log statements"),
                WorkflowMatchAction(id="a4", name="Identify root cause", description="Trace the issue to its source"),
                WorkflowMatchAction(id="a5", name="Implement fix", description="Write code to resolve the issue"),
                WorkflowMatchAction(id="a6", name="Write regression test", description="Ensure bug doesn't come back"),
            ],
            graph=WorkflowGraphData(
                nodes=[
                    WorkflowGraphNode(id="n1", type="prompt", label="Fix bug"),
                    WorkflowGraphNode(id="n2", type="action", label="reproduce:bug"),
                    WorkflowGraphNode(id="n3", type="action", label="logs:check-errors"),
                    WorkflowGraphNode(id="n4", type="action", label="debug:add-logging"),
                    WorkflowGraphNode(id="n5", type="action", label="investigate:root-cause"),
                    WorkflowGraphNode(id="n6", type="action", label="code:implement-fix"),
                    WorkflowGraphNode(id="n7", type="action", label="test:write-regression"),
                ],
                edges=[
                    WorkflowGraphEdge(id="e1", source="n1", target="n2", type="starts"),
                    WorkflowGraphEdge(id="e2", source="n2", target="n3", type="next"),
                    WorkflowGraphEdge(id="e3", source="n3", target="n4", type="next"),
                    WorkflowGraphEdge(id="e4", source="n4", target="n5", type="next"),
                    WorkflowGraphEdge(id="e5", source="n5", target="n6", type="next"),
                    WorkflowGraphEdge(id="e6", source="n6", target="n7", type="next"),
                    WorkflowGraphEdge(id="e7", source="n3", target="n5", type="depends_on"),
                ]
            ),
            message="Found matching workflow for bug fixes"
        )

    elif any(keyword in task_lower for keyword in ['doc', 'documentation', 'readme', 'guide']):
        return WorkflowMatchResponse(
            canUseWorkflow=True,
            workflowId="workflow-docs",
            workflowName="Documentation Update Workflow",
            confidence=0.95,
            actions=[
                WorkflowMatchAction(id="a1", name="Review current docs", description="Read existing documentation to understand context"),
                WorkflowMatchAction(id="a2", name="Update content", description="Make necessary changes to markdown files"),
                WorkflowMatchAction(id="a3", name="Add examples", description="Include code examples and usage patterns"),
                WorkflowMatchAction(id="a4", name="Run spell check", description="Check for typos and grammar issues"),
                WorkflowMatchAction(id="a5", name="Preview locally", description="Build and review docs site locally"),
            ],
            graph=WorkflowGraphData(
                nodes=[
                    WorkflowGraphNode(id="n1", type="prompt", label="Update documentation"),
                    WorkflowGraphNode(id="n2", type="action", label="docs:review-current"),
                    WorkflowGraphNode(id="n3", type="action", label="edit:update-content"),
                    WorkflowGraphNode(id="n4", type="action", label="docs:add-examples"),
                    WorkflowGraphNode(id="n5", type="action", label="spellcheck:run"),
                    WorkflowGraphNode(id="n6", type="action", label="preview:build-local"),
                ],
                edges=[
                    WorkflowGraphEdge(id="e1", source="n1", target="n2", type="starts"),
                    WorkflowGraphEdge(id="e2", source="n2", target="n3", type="next"),
                    WorkflowGraphEdge(id="e3", source="n3", target="n4", type="next"),
                    WorkflowGraphEdge(id="e4", source="n4", target="n5", type="next"),
                    WorkflowGraphEdge(id="e5", source="n5", target="n6", type="next"),
                ]
            ),
            message="Found documentation workflow"
        )

    else:
        # No matching workflow found
        return WorkflowMatchResponse(
            canUseWorkflow=False,
            message="No matching workflow found for this task"
        )


async def query_neo4j_workflows(task_title: str) -> List[Dict]:
    """
    Query Neo4j for workflows matching the task.

    Uses the same Neo4j instance as the main Woodwork system.
    """
    try:
        from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

        neo4j_client = neo4j(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="testpassword",
            name="personal_workflow_match"
        )

        # Search for workflows with similar prompts
        query = """
        MATCH (w:Workflow)-[:CONTAINS]->(p:Prompt)
        WHERE w.status = 'completed'
        AND (toLower(p.text) CONTAINS toLower($keyword)
             OR toLower(p.text) CONTAINS toLower($task_title))
        OPTIONAL MATCH (w)-[:CONTAINS]->(a:Action)
        WITH w, p, collect({
            id: a.id,
            name: a.action,
            description: a.tool + ': ' + a.action
        }) as actions
        RETURN w.id as id,
               p.text as name,
               actions,
               w.final_step as steps_count
        ORDER BY w.completed_at DESC
        LIMIT 3
        """

        # Extract keywords from task title for better matching
        keywords = task_title.lower().split()
        main_keyword = max(keywords, key=len) if keywords else task_title

        results = neo4j_client.run(query, {
            "keyword": main_keyword,
            "task_title": task_title
        })

        workflows = []
        for record in results:
            workflows.append({
                "id": record.get("id"),
                "name": record.get("name", "Unnamed Workflow")[:100],
                "actions": [
                    WorkflowMatchAction(
                        id=action.get("id", str(uuid4())),
                        name=action.get("name", "Unknown"),
                        description=action.get("description", "")
                    )
                    for action in record.get("actions", [])[:5]  # Limit to 5 actions
                ],
                "confidence": 0.75,  # Could be calculated based on similarity
                "usage_count": 1
            })

        neo4j_client.close()
        logger.info(f"Found {len(workflows)} matching workflows for: {task_title}")
        return workflows

    except Exception as e:
        logger.warning(f"Neo4j query failed: {e}")
        return []


# ===== Server Startup =====

@app.on_event("startup")
async def startup_event():
    """Initialize data files on startup."""
    for file_path in [TASKS_FILE, SUGGESTIONS_FILE, INSIGHTS_FILE, TAGS_FILE]:
        if not file_path.exists():
            save_json(file_path, [])
            logger.info(f"Created {file_path}")

    logger.info(f"Personal server data directory: {DATA_DIR}")
    logger.info("Server ready!")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Woodwork Personal Productivity Server",
        "status": "running",
        "data_dir": str(DATA_DIR)
    }


if __name__ == "__main__":
    logger.info("Starting Woodwork Personal Productivity Server...")
    logger.info(f"Data will be stored in: {DATA_DIR}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
