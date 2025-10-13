"""
Unit tests for API input entrypoint routing.

Following TDD - these tests verify Phase 3 implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient


class TestAPIEntrypointRouting:
    """Test API input workflow entrypoint routing."""

    @pytest.fixture
    def mock_task_master(self):
        """Mock task master with workflow executor."""
        task_master = Mock()
        task_master._workflow_executor = Mock()
        task_master._workflow_executor.execute_entrypoint = AsyncMock(
            return_value={
                'execution_id': 'exec-123',
                'workflow_id': 'w-456',
                'status': 'completed',
                'final_outputs': {'result': 'success'}
            }
        )
        return task_master

    @pytest.fixture
    def api_input_with_entrypoints(self, mock_task_master):
        """Create API input with workflow entrypoints configured."""
        from woodwork.components.inputs.api_input import api_input

        config = {
            'port': 8000,
            'workflow_entrypoints': {
                'process_data': '/workflow/process_data',
                'analyze_logs': '/workflow/analyze_logs'
            },
            'task_m': mock_task_master
        }

        return api_input(**config)

    def test_api_input_accepts_workflow_entrypoints_config(self):
        """Test that api_input accepts workflow_entrypoints in config."""
        from woodwork.components.inputs.api_input import api_input

        config = {
            'workflow_entrypoints': {
                'test_workflow': '/workflow/test'
            }
        }

        api = api_input(**config)

        assert hasattr(api, 'workflow_entrypoints')
        assert api.workflow_entrypoints == {'test_workflow': '/workflow/test'}

    def test_api_input_registers_entrypoint_routes(self, api_input_with_entrypoints):
        """Test that entrypoint routes are registered on FastAPI app."""
        # Check that routes were added to the FastAPI app
        routes = [route.path for route in api_input_with_entrypoints.app.routes]

        assert '/workflow/process_data' in routes
        assert '/workflow/analyze_logs' in routes

    @pytest.mark.asyncio
    async def test_entrypoint_route_executes_workflow(self, api_input_with_entrypoints, mock_task_master):
        """Test that calling entrypoint route executes the workflow."""
        client = TestClient(api_input_with_entrypoints.app)

        response = client.post(
            '/workflow/process_data',
            json={
                'inputs': {'file': 'data.csv'},
                'session_id': 'test-session'
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'success'
        assert data['entrypoint'] == 'process_data'
        assert 'result' in data

        # Verify workflow executor was called
        mock_task_master._workflow_executor.execute_entrypoint.assert_called_once()
        call_args = mock_task_master._workflow_executor.execute_entrypoint.call_args

        assert call_args[0][0] == 'process_data'  # entrypoint_name
        assert call_args[0][1] == {'file': 'data.csv'}  # inputs

    @pytest.mark.asyncio
    async def test_entrypoint_route_returns_execution_result(self, api_input_with_entrypoints):
        """Test that entrypoint route returns execution results."""
        client = TestClient(api_input_with_entrypoints.app)

        response = client.post(
            '/workflow/process_data',
            json={'inputs': {}, 'session_id': 'test'}
        )

        assert response.status_code == 200
        data = response.json()

        # Check that execution results are returned
        assert 'result' in data
        assert data['result']['execution_id'] == 'exec-123'
        assert data['result']['workflow_id'] == 'w-456'
        assert data['result']['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_entrypoint_route_handles_errors(self, api_input_with_entrypoints, mock_task_master):
        """Test that entrypoint route handles execution errors."""
        # Make executor raise an error
        mock_task_master._workflow_executor.execute_entrypoint = AsyncMock(
            side_effect=ValueError("Workflow not found")
        )

        client = TestClient(api_input_with_entrypoints.app)

        response = client.post(
            '/workflow/process_data',
            json={'inputs': {}}
        )

        assert response.status_code == 500
        data = response.json()

        assert data['status'] == 'error'
        assert 'Workflow not found' in data['error']

    def test_get_workflow_executor_from_task_master(self, api_input_with_entrypoints, mock_task_master):
        """Test _get_workflow_executor retrieves executor from task master."""
        executor = api_input_with_entrypoints._get_workflow_executor()

        assert executor is mock_task_master._workflow_executor

    def test_get_workflow_executor_returns_none_without_task_master(self):
        """Test _get_workflow_executor returns None without task master."""
        from woodwork.components.inputs.api_input import api_input

        api = api_input(port=8000)

        executor = api._get_workflow_executor()

        assert executor is None

    @pytest.mark.asyncio
    async def test_multiple_entrypoints_registered(self):
        """Test that multiple entrypoints can be registered."""
        from woodwork.components.inputs.api_input import api_input

        config = {
            'workflow_entrypoints': {
                'workflow1': '/workflow/one',
                'workflow2': '/workflow/two',
                'workflow3': '/workflow/three'
            }
        }

        api = api_input(**config)
        routes = [route.path for route in api.app.routes]

        assert '/workflow/one' in routes
        assert '/workflow/two' in routes
        assert '/workflow/three' in routes

    @pytest.mark.asyncio
    async def test_entrypoint_uses_provided_session_id(self, api_input_with_entrypoints, mock_task_master):
        """Test that entrypoint uses session_id from request."""
        client = TestClient(api_input_with_entrypoints.app)

        response = client.post(
            '/workflow/process_data',
            json={
                'inputs': {},
                'session_id': 'custom-session-123'
            }
        )

        # Verify session_id was passed to executor
        call_args = mock_task_master._workflow_executor.execute_entrypoint.call_args
        assert call_args[0][2] == 'custom-session-123'  # session_id

    @pytest.mark.asyncio
    async def test_entrypoint_generates_session_id_if_not_provided(self, api_input_with_entrypoints, mock_task_master):
        """Test that entrypoint generates session_id if not provided."""
        client = TestClient(api_input_with_entrypoints.app)

        response = client.post(
            '/workflow/process_data',
            json={'inputs': {}}  # No session_id
        )

        # Verify a session_id was generated and passed
        call_args = mock_task_master._workflow_executor.execute_entrypoint.call_args
        session_id = call_args[0][2]

        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0
