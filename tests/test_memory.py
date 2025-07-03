import pytest
from unittest.mock import Mock, patch
from app.memory import PersistedBufferMemory
from datetime import datetime

@pytest.fixture
def mock_supabase_client():
    """Fixture to provide a mock Supabase client."""
    mock_client = Mock()
    mock_client.table.return_value.insert.return_value.execute.return_value = Mock(data=[{"id": "test_id"}])
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(data=[])
    return mock_client

from langchain_core.language_models.chat_models import BaseChatModel

@pytest.fixture
def mock_llm():
    """Fixture to provide a mock LLM."""
    class MockChatModel(BaseChatModel):
        def _generate(self, messages, stop=None, callbacks=None, **kwargs):
            # Implement a dummy generate method
            pass

        @property
        def _llm_type(self) -> str:
            return "mock_chat_model"

        def invoke(self, input, config=None, **kwargs):
            return "summarized content"

    return MockChatModel()

def test_save_context_saves_to_supabase(mock_supabase_client, mock_llm):
    """
    Test that save_context correctly saves the conversation summary to Supabase.
    """
    memory = PersistedBufferMemory(
        supabase_client=mock_supabase_client,
        llm=mock_llm,
        memory_key="summary",
        input_key="input",
        output_key="output",
        max_token_limit=1500,
    )

    user_id = "test_user_123"
    inputs = {"user_id": user_id, "input": "Hello"}
    outputs = {"output": "Hi there!"}

    # Simulate the internal state of ConversationSummaryBufferMemory
    # after super().save_context is called.
    # In a real scenario, this would be populated by the LLM.
    memory.moving_summary_buffer = "This is a summarized conversation."

    # Patch datetime.utcnow to return a fixed value for predictable testing
    with patch('app.memory.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.side_effect = lambda: datetime(2025, 1, 1, 12, 0, 0) # For isoformat()

        memory.save_context(inputs, outputs)

        expected_payload = {
            "user_id": user_id,
            "key": "summary",
            "value": "This is a summarized conversation.",
            "created_at": "2025-01-01T12:00:00",
        }

        mock_supabase_client.table.assert_called_once_with("chat_memory")
        mock_supabase_client.table.return_value.insert.assert_called_once_with(expected_payload)
        mock_supabase_client.table.return_value.insert.return_value.execute.assert_called_once()

def test_load_memory_variables_loads_from_supabase(mock_supabase_client, mock_llm):
    """
    Test that load_memory_variables correctly loads the conversation summary from Supabase.
    """
    memory = PersistedBufferMemory(
        supabase_client=mock_supabase_client,
        llm=mock_llm,
        memory_key="summary",
        input_key="input",
        output_key="output",
        max_token_limit=1500,
    )

    user_id = "test_user_456"
    inputs = {"user_id": user_id, "input": "How are you?"}
    
    # Configure the mock Supabase client to return some data
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(data=[{"value": "Loaded summary from DB."}])

    loaded_memory = memory.load_memory_variables(inputs)

    mock_supabase_client.table.assert_called_with("chat_memory") # Can be called multiple times
    mock_supabase_client.table.return_value.select.assert_called_once_with("value")
    mock_supabase_client.table.return_value.select.return_value.eq.assert_any_call("user_id", user_id)
    mock_supabase_client.table.return_value.select.return_value.eq.assert_any_call("key", "summary")
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.assert_called_once_with("created_at", desc=True)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_once_with(1)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.assert_called_once()

    assert memory.buffer == "Loaded summary from DB."
    assert "history" in loaded_memory # Ensure LangChain's internal history is handled
    assert loaded_memory["history"] == "Loaded summary from DB." # Or whatever the expected format is after super().load_memory_variables
