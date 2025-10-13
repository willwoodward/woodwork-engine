"""
Create mock workflow data in Neo4j for testing the UI.
Run this script to populate Neo4j with sample workflows.
"""
from datetime import datetime
import uuid

from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

# Connect to Neo4j
neo4j_client = neo4j(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="testpassword",
    name="mock_data_creator"
)

print("Creating mock workflows in Neo4j...")

# Mock Workflow 1: Code Review
workflow_id_1 = str(uuid.uuid4())
print(f"\n1. Creating Code Review workflow: {workflow_id_1}")

# Create workflow node
neo4j_client.run("""
CREATE (w:Workflow {
    id: $workflow_id,
    status: 'completed',
    source: 'auto',
    created_at: datetime($created_at),
    completed_at: datetime($completed_at),
    final_step: 5
})
""", {
    "workflow_id": workflow_id_1,
    "created_at": "2025-01-10T10:30:00",
    "completed_at": "2025-01-10T10:35:00"
})

# Create prompt
neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})
CREATE (p:Prompt {
    id: $prompt_id,
    text: 'Review the pull request for the new authentication feature'
})
CREATE (w)-[:CONTAINS]->(p)
""", {
    "workflow_id": workflow_id_1,
    "prompt_id": str(uuid.uuid4())
})

# Create actions
actions_1 = [
    ("Fetch PR details", "github", "fetch_pr", 0),
    ("Check CI status", "github", "check_ci", 1),
    ("Review code changes", "code_review", "analyze_diff", 2),
    ("Check test coverage", "testing", "check_coverage", 3),
    ("Post review comments", "github", "post_comments", 4),
]

for name, tool, action, seq in actions_1:
    action_id = f"{workflow_id_1}_{seq}"
    neo4j_client.run("""
    MATCH (w:Workflow {id: $workflow_id})
    CREATE (a:Action {
        id: $action_id,
        tool: $tool,
        action: $action,
        sequence: $sequence,
        inputs: '{}',
        output: ''
    })
    CREATE (w)-[:CONTAINS]->(a)
    """, {
        "workflow_id": workflow_id_1,
        "action_id": action_id,
        "tool": tool,
        "action": action,
        "sequence": seq
    })

# Connect actions with NEXT relationships
for i in range(len(actions_1) - 1):
    neo4j_client.run("""
    MATCH (a1:Action {id: $action_id_1})
    MATCH (a2:Action {id: $action_id_2})
    CREATE (a1)-[:NEXT]->(a2)
    """, {
        "action_id_1": f"{workflow_id_1}_{i}",
        "action_id_2": f"{workflow_id_1}_{i+1}"
    })

# Connect prompt to first action
neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(p:Prompt)
MATCH (a:Action {id: $first_action_id})
CREATE (p)-[:STARTS]->(a)
""", {
    "workflow_id": workflow_id_1,
    "first_action_id": f"{workflow_id_1}_0"
})

print(f"   ✅ Created {len(actions_1)} actions")

# Mock Workflow 2: Bug Fix Investigation
workflow_id_2 = str(uuid.uuid4())
print(f"\n2. Creating Bug Fix workflow: {workflow_id_2}")

neo4j_client.run("""
CREATE (w:Workflow {
    id: $workflow_id,
    status: 'completed',
    source: 'auto',
    created_at: datetime($created_at),
    completed_at: datetime($completed_at),
    final_step: 6
})
""", {
    "workflow_id": workflow_id_2,
    "created_at": "2025-01-09T14:20:00",
    "completed_at": "2025-01-09T14:45:00"
})

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})
CREATE (p:Prompt {
    id: $prompt_id,
    text: 'Fix the login timeout error happening in production'
})
CREATE (w)-[:CONTAINS]->(p)
""", {
    "workflow_id": workflow_id_2,
    "prompt_id": str(uuid.uuid4())
})

actions_2 = [
    ("Check error logs", "logging", "search_errors", 0),
    ("Reproduce bug locally", "debugging", "reproduce", 1),
    ("Analyze stack trace", "debugging", "analyze_trace", 2),
    ("Identify root cause", "code_analysis", "find_issue", 3),
    ("Implement fix", "coding", "write_fix", 4),
    ("Write regression test", "testing", "write_test", 5),
]

for name, tool, action, seq in actions_2:
    action_id = f"{workflow_id_2}_{seq}"
    neo4j_client.run("""
    MATCH (w:Workflow {id: $workflow_id})
    CREATE (a:Action {
        id: $action_id,
        tool: $tool,
        action: $action,
        sequence: $sequence,
        inputs: '{}',
        output: ''
    })
    CREATE (w)-[:CONTAINS]->(a)
    """, {
        "workflow_id": workflow_id_2,
        "action_id": action_id,
        "tool": tool,
        "action": action,
        "sequence": seq
    })

for i in range(len(actions_2) - 1):
    neo4j_client.run("""
    MATCH (a1:Action {id: $action_id_1})
    MATCH (a2:Action {id: $action_id_2})
    CREATE (a1)-[:NEXT]->(a2)
    """, {
        "action_id_1": f"{workflow_id_2}_{i}",
        "action_id_2": f"{workflow_id_2}_{i+1}"
    })

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(p:Prompt)
MATCH (a:Action {id: $first_action_id})
CREATE (p)-[:STARTS]->(a)
""", {
    "workflow_id": workflow_id_2,
    "first_action_id": f"{workflow_id_2}_0"
})

print(f"   ✅ Created {len(actions_2)} actions")

# Mock Workflow 3: In Progress Workflow
workflow_id_3 = str(uuid.uuid4())
print(f"\n3. Creating In Progress workflow: {workflow_id_3}")

neo4j_client.run("""
CREATE (w:Workflow {
    id: $workflow_id,
    status: 'in_progress',
    source: 'auto',
    created_at: datetime($created_at),
    final_step: 0
})
""", {
    "workflow_id": workflow_id_3,
    "created_at": datetime.now().isoformat()
})

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})
CREATE (p:Prompt {
    id: $prompt_id,
    text: 'Add dark mode support to the application'
})
CREATE (w)-[:CONTAINS]->(p)
""", {
    "workflow_id": workflow_id_3,
    "prompt_id": str(uuid.uuid4())
})

actions_3 = [
    ("Research dark mode patterns", "research", "search_patterns", 0),
    ("Design color scheme", "design", "create_theme", 1),
]

for name, tool, action, seq in actions_3:
    action_id = f"{workflow_id_3}_{seq}"
    neo4j_client.run("""
    MATCH (w:Workflow {id: $workflow_id})
    CREATE (a:Action {
        id: $action_id,
        tool: $tool,
        action: $action,
        sequence: $sequence,
        inputs: '{}',
        output: ''
    })
    CREATE (w)-[:CONTAINS]->(a)
    """, {
        "workflow_id": workflow_id_3,
        "action_id": action_id,
        "tool": tool,
        "action": action,
        "sequence": seq
    })

neo4j_client.run("""
MATCH (a1:Action {id: $action_id_1})
MATCH (a2:Action {id: $action_id_2})
CREATE (a1)-[:NEXT]->(a2)
""", {
    "action_id_1": f"{workflow_id_3}_0",
    "action_id_2": f"{workflow_id_3}_1"
})

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(p:Prompt)
MATCH (a:Action {id: $first_action_id})
CREATE (p)-[:STARTS]->(a)
""", {
    "workflow_id": workflow_id_3,
    "first_action_id": f"{workflow_id_3}_0"
})

print(f"   ✅ Created {len(actions_3)} actions")

# Mock Workflow 4: Documentation Update
workflow_id_4 = str(uuid.uuid4())
print(f"\n4. Creating Documentation workflow: {workflow_id_4}")

neo4j_client.run("""
CREATE (w:Workflow {
    id: $workflow_id,
    status: 'completed',
    source: 'manual',
    created_at: datetime($created_at),
    completed_at: datetime($completed_at),
    final_step: 4
})
""", {
    "workflow_id": workflow_id_4,
    "created_at": "2025-01-08T09:00:00",
    "completed_at": "2025-01-08T09:20:00"
})

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})
CREATE (p:Prompt {
    id: $prompt_id,
    text: 'Update API documentation for v2.0 release'
})
CREATE (w)-[:CONTAINS]->(p)
""", {
    "workflow_id": workflow_id_4,
    "prompt_id": str(uuid.uuid4())
})

actions_4 = [
    ("Review API changes", "documentation", "review_changes", 0),
    ("Update endpoint docs", "documentation", "update_endpoints", 1),
    ("Add code examples", "documentation", "add_examples", 2),
    ("Generate OpenAPI spec", "documentation", "generate_spec", 3),
]

for name, tool, action, seq in actions_4:
    action_id = f"{workflow_id_4}_{seq}"
    neo4j_client.run("""
    MATCH (w:Workflow {id: $workflow_id})
    CREATE (a:Action {
        id: $action_id,
        tool: $tool,
        action: $action,
        sequence: $sequence,
        inputs: '{}',
        output: ''
    })
    CREATE (w)-[:CONTAINS]->(a)
    """, {
        "workflow_id": workflow_id_4,
        "action_id": action_id,
        "tool": tool,
        "action": action,
        "sequence": seq
    })

for i in range(len(actions_4) - 1):
    neo4j_client.run("""
    MATCH (a1:Action {id: $action_id_1})
    MATCH (a2:Action {id: $action_id_2})
    CREATE (a1)-[:NEXT]->(a2)
    """, {
        "action_id_1": f"{workflow_id_4}_{i}",
        "action_id_2": f"{workflow_id_4}_{i+1}"
    })

neo4j_client.run("""
MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(p:Prompt)
MATCH (a:Action {id: $first_action_id})
CREATE (p)-[:STARTS]->(a)
""", {
    "workflow_id": workflow_id_4,
    "first_action_id": f"{workflow_id_4}_0"
})

print(f"   ✅ Created {len(actions_4)} actions")

neo4j_client.close()

print("\n✅ Mock data creation complete!")
print("\nCreated workflows:")
print(f"  1. Code Review (completed, 5 actions)")
print(f"  2. Bug Fix Investigation (completed, 6 actions)")
print(f"  3. Dark Mode Support (in_progress, 2 actions)")
print(f"  4. API Documentation (completed, manual, 4 actions)")
print("\nNow refresh your workflow browser to see them!")
