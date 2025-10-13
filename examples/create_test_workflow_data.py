"""
Create test workflow data in Neo4j to demonstrate the GUI integration.

This script creates sample workflows that show the workflows feature working
with the frontend display.
"""

import json
import uuid
from datetime import datetime

def create_test_workflows():
    """Create test workflow data in Neo4j."""

    try:
        from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

        # Connect to Neo4j
        neo4j_client = neo4j(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="testpassword",
            name="test_data_creator"
        )

        print("🔗 Connected to Neo4j")

        # Create test workflow 1: File Processing
        workflow_1_id = str(uuid.uuid4())
        prompt_1_id = f"prompt_{workflow_1_id}"

        print(f"\n📝 Creating workflow 1: {workflow_1_id}")

        # Create workflow and prompt nodes
        neo4j_client.run("""
        CREATE (w:Workflow {
            id: $workflow_id,
            status: 'completed',
            created_at: datetime($created_at),
            completed_at: datetime($completed_at),
            final_step: 3,
            component_id: 'demo_agent'
        })
        CREATE (p:Prompt {
            id: $prompt_id,
            text: $prompt_text,
            workflow_id: $workflow_id
        })
        CREATE (w)-[:CONTAINS]->(p)
        """, {
            "workflow_id": workflow_1_id,
            "prompt_id": prompt_1_id,
            "prompt_text": "Create a Python file and add some functions to it",
            "created_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T10:05:30Z"
        })

        # Create actions for workflow 1
        actions_1 = [
            {
                "id": f"action_{workflow_1_id}_0",
                "tool": "file_tool",
                "action": "create",
                "inputs": '{"filename": "demo.py"}',
                "output": "file_created",
                "sequence": 0
            },
            {
                "id": f"action_{workflow_1_id}_1",
                "tool": "text_tool",
                "action": "write",
                "inputs": '{"file": "file_created", "content": "def hello():\\n    print(\\"Hello World\\")"}',
                "output": "function_added",
                "sequence": 1
            },
            {
                "id": f"action_{workflow_1_id}_2",
                "tool": "text_tool",
                "action": "write",
                "inputs": '{"file": "file_created", "content": "def goodbye():\\n    print(\\"Goodbye\\")"}',
                "output": "second_function_added",
                "sequence": 2
            }
        ]

        for action in actions_1:
            neo4j_client.run("""
            MATCH (w:Workflow {id: $workflow_id})
            CREATE (a:Action {
                id: $action_id,
                tool: $tool,
                action: $action_name,
                inputs: $inputs,
                output: $output,
                sequence: $sequence,
                workflow_id: $workflow_id,
                created_at: datetime()
            })
            CREATE (w)-[:CONTAINS]->(a)
            """, {
                "workflow_id": workflow_1_id,
                "action_id": action["id"],
                "tool": action["tool"],
                "action_name": action["action"],
                "inputs": action["inputs"],
                "output": action["output"],
                "sequence": action["sequence"]
            })

        # Create relationships for workflow 1
        # Prompt starts first action
        neo4j_client.run("""
        MATCH (p:Prompt {id: $prompt_id})
        MATCH (a:Action {id: $first_action_id})
        CREATE (p)-[:STARTS]->(a)
        """, {
            "prompt_id": prompt_1_id,
            "first_action_id": actions_1[0]["id"]
        })

        # Sequential relationships
        for i in range(len(actions_1) - 1):
            neo4j_client.run("""
            MATCH (a1:Action {id: $action1_id})
            MATCH (a2:Action {id: $action2_id})
            CREATE (a1)-[:NEXT]->(a2)
            """, {
                "action1_id": actions_1[i]["id"],
                "action2_id": actions_1[i + 1]["id"]
            })

        # Dependencies (actions 1 and 2 depend on action 0's output)
        for i in [1, 2]:
            neo4j_client.run("""
            MATCH (dependent:Action {id: $dependent_id})
            MATCH (dependency:Action {id: $dependency_id})
            CREATE (dependent)-[:DEPENDS_ON]->(dependency)
            """, {
                "dependent_id": actions_1[i]["id"],
                "dependency_id": actions_1[0]["id"]
            })

        print(f"   ✅ Created workflow with {len(actions_1)} actions")

        # Create test workflow 2: Data Analysis
        workflow_2_id = str(uuid.uuid4())
        prompt_2_id = f"prompt_{workflow_2_id}"

        print(f"\n📊 Creating workflow 2: {workflow_2_id}")

        neo4j_client.run("""
        CREATE (w:Workflow {
            id: $workflow_id,
            status: 'completed',
            created_at: datetime($created_at),
            completed_at: datetime($completed_at),
            final_step: 4,
            component_id: 'demo_agent'
        })
        CREATE (p:Prompt {
            id: $prompt_id,
            text: $prompt_text,
            workflow_id: $workflow_id
        })
        CREATE (w)-[:CONTAINS]->(p)
        """, {
            "workflow_id": workflow_2_id,
            "prompt_id": prompt_2_id,
            "prompt_text": "Analyze sales data and create a report",
            "created_at": "2024-01-16T14:30:00Z",
            "completed_at": "2024-01-16T15:15:45Z"
        })

        # Create actions for workflow 2
        actions_2 = [
            {
                "id": f"action_{workflow_2_id}_0",
                "tool": "data_loader",
                "action": "read_csv",
                "inputs": '{"file": "sales_data.csv"}',
                "output": "data_loaded",
                "sequence": 0
            },
            {
                "id": f"action_{workflow_2_id}_1",
                "tool": "data_processor",
                "action": "clean",
                "inputs": '{"data": "data_loaded"}',
                "output": "data_cleaned",
                "sequence": 1
            },
            {
                "id": f"action_{workflow_2_id}_2",
                "tool": "analyzer",
                "action": "calculate_metrics",
                "inputs": '{"data": "data_cleaned"}',
                "output": "metrics_calculated",
                "sequence": 2
            },
            {
                "id": f"action_{workflow_2_id}_3",
                "tool": "report_generator",
                "action": "create_report",
                "inputs": '{"metrics": "metrics_calculated", "data": "data_cleaned"}',
                "output": "report_created",
                "sequence": 3
            }
        ]

        for action in actions_2:
            neo4j_client.run("""
            MATCH (w:Workflow {id: $workflow_id})
            CREATE (a:Action {
                id: $action_id,
                tool: $tool,
                action: $action_name,
                inputs: $inputs,
                output: $output,
                sequence: $sequence,
                workflow_id: $workflow_id,
                created_at: datetime()
            })
            CREATE (w)-[:CONTAINS]->(a)
            """, {
                "workflow_id": workflow_2_id,
                "action_id": action["id"],
                "tool": action["tool"],
                "action_name": action["action"],
                "inputs": action["inputs"],
                "output": action["output"],
                "sequence": action["sequence"]
            })

        # Create relationships for workflow 2
        neo4j_client.run("""
        MATCH (p:Prompt {id: $prompt_id})
        MATCH (a:Action {id: $first_action_id})
        CREATE (p)-[:STARTS]->(a)
        """, {
            "prompt_id": prompt_2_id,
            "first_action_id": actions_2[0]["id"]
        })

        # Linear chain of dependencies
        for i in range(len(actions_2) - 1):
            neo4j_client.run("""
            MATCH (a1:Action {id: $action1_id})
            MATCH (a2:Action {id: $action2_id})
            CREATE (a1)-[:NEXT]->(a2)
            CREATE (a2)-[:DEPENDS_ON]->(a1)
            """, {
                "action1_id": actions_2[i]["id"],
                "action2_id": actions_2[i + 1]["id"]
            })

        # Final action depends on both metrics and cleaned data
        neo4j_client.run("""
        MATCH (final:Action {id: $final_id})
        MATCH (cleaned:Action {id: $cleaned_id})
        CREATE (final)-[:DEPENDS_ON]->(cleaned)
        """, {
            "final_id": actions_2[3]["id"],
            "cleaned_id": actions_2[1]["id"]
        })

        print(f"   ✅ Created workflow with {len(actions_2)} actions")

        neo4j_client.close()

        print(f"\n🎉 Successfully created 2 test workflows!")
        print(f"   📝 Workflow 1: File Processing ({len(actions_1)} actions)")
        print(f"   📊 Workflow 2: Data Analysis ({len(actions_2)} actions)")
        print(f"\n💡 You can now view these workflows in the GUI at http://localhost:3000/workflows")

        return [workflow_1_id, workflow_2_id]

    except Exception as e:
        print(f"❌ Error creating test workflows: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    print("🚀 Creating test workflow data for GUI demonstration...")
    workflow_ids = create_test_workflows()

    if workflow_ids:
        print(f"\n✅ Test data created successfully!")
        print(f"   Workflow IDs: {workflow_ids}")
    else:
        print(f"\n❌ Failed to create test data")