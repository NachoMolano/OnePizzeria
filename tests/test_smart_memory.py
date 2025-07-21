"""
Tests for the Smart Memory System.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage

from app.core.smart_memory import SmartMemoryManager, ConversationContext
from app.core.smart_checkpointer import ChatStateManager
from app.core.state import ChatState


@pytest.fixture
def memory_manager():
    """Create a fresh memory manager for testing."""
    return SmartMemoryManager()


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        HumanMessage(content="Hola"),
        AIMessage(content="¡Hola! Bienvenido a nuestra pizzería."),
        HumanMessage(content="¿Qué pizzas tienen?"),
        AIMessage(content="Tenemos pizzas de pepperoni, hawaiana, vegetariana...")
    ]


class TestConversationContext:
    """Test ConversationContext class."""
    
    def test_create_context(self):
        """Test creating a new conversation context."""
        context = ConversationContext("user123")
        
        assert context.thread_id == "user123"
        assert context.customer_context == {}
        assert context.recent_messages == []
        assert context.session_metadata == {}
        assert isinstance(context.last_activity, datetime)
        assert isinstance(context.created_at, datetime)
    
    def test_add_message(self, sample_messages):
        """Test adding messages to context."""
        context = ConversationContext("user123")
        
        # Add messages
        for msg in sample_messages:
            context.add_message(msg)
        
        assert len(context.recent_messages) == 4
        assert context.recent_messages[0]["role"] == "human"
        assert context.recent_messages[0]["content"] == "Hola"
        assert context.recent_messages[1]["role"] == "assistant"
        assert context.recent_messages[1]["content"] == "¡Hola! Bienvenido a nuestra pizzería."
    
    def test_sliding_window(self):
        """Test sliding window functionality."""
        context = ConversationContext("user123")
        
        # Add many messages to test sliding window
        for i in range(20):
            context.add_message(HumanMessage(content=f"Message {i}"))
        
        # Should keep only the most recent 12 messages
        assert len(context.recent_messages) == 12
        assert context.recent_messages[-1]["content"] == "Message 19"
    
    def test_update_customer_context(self):
        """Test updating customer context."""
        context = ConversationContext("user123")
        
        context.update_customer_context("name", "Juan Pérez")
        context.update_customer_context("phone", "3001234567")
        
        assert context.customer_context["name"] == "Juan Pérez"
        assert context.customer_context["phone"] == "3001234567"
    
    def test_get_messages_for_llm(self, sample_messages):
        """Test converting messages back to LangChain format."""
        context = ConversationContext("user123")
        
        for msg in sample_messages:
            context.add_message(msg)
        
        llm_messages = context.get_messages_for_llm()
        
        assert len(llm_messages) == 4
        assert isinstance(llm_messages[0], HumanMessage)
        assert isinstance(llm_messages[1], AIMessage)
        assert llm_messages[0].content == "Hola"
        assert llm_messages[1].content == "¡Hola! Bienvenido a nuestra pizzería."
    
    def test_to_dict_and_from_dict(self, sample_messages):
        """Test serialization and deserialization."""
        context = ConversationContext("user123")
        
        # Add some data
        for msg in sample_messages:
            context.add_message(msg)
        context.update_customer_context("name", "Juan Pérez")
        
        # Serialize
        data = context.to_dict()
        
        # Deserialize
        restored_context = ConversationContext.from_dict(data)
        
        assert restored_context.thread_id == "user123"
        assert len(restored_context.recent_messages) == 4
        assert restored_context.customer_context["name"] == "Juan Pérez"


class TestSmartMemoryManager:
    """Test SmartMemoryManager class."""
    
    @pytest.mark.asyncio
    async def test_get_new_conversation(self, memory_manager):
        """Test getting a new conversation."""
        context = await memory_manager.get_conversation("new_user")
        
        assert context.thread_id == "new_user"
        assert context.customer_context == {}
        assert context.recent_messages == []
    
    @pytest.mark.asyncio
    async def test_add_message(self, memory_manager):
        """Test adding a message to conversation."""
        user_id = "test_user_msg"
        message = HumanMessage(content="Hola, quiero una pizza")
        
        context = await memory_manager.add_message(user_id, message)
        
        assert len(context.recent_messages) == 1
        assert context.recent_messages[0]["content"] == "Hola, quiero una pizza"
        assert context.recent_messages[0]["role"] == "human"
    
    @pytest.mark.asyncio
    async def test_update_customer_context(self, memory_manager):
        """Test updating customer context."""
        user_id = "test_user_context"
        
        await memory_manager.update_customer_context(user_id, "name", "María González")
        await memory_manager.update_customer_context(user_id, "preferences", "vegetariana")
        
        context = await memory_manager.get_conversation(user_id)
        
        assert context.customer_context["name"] == "María González"
        assert context.customer_context["preferences"] == "vegetariana"
    
    @pytest.mark.asyncio
    async def test_conversation_stats(self, memory_manager):
        """Test getting conversation statistics."""
        user_id = "test_user_stats"
        
        # Add some messages
        await memory_manager.add_message(user_id, HumanMessage(content="Hola"))
        await memory_manager.add_message(user_id, AIMessage(content="¡Hola!"))
        await memory_manager.update_customer_context(user_id, "name", "Pedro")
        
        stats = await memory_manager.get_conversation_stats(user_id)
        
        assert stats["thread_id"] == user_id
        assert stats["message_count"] == 2
        assert "name" in stats["customer_context_keys"]
        assert "last_activity" in stats
        assert "created_at" in stats
    
    @pytest.mark.asyncio
    async def test_long_message_truncation(self, memory_manager):
        """Test truncation of very long messages."""
        user_id = "test_user_long"
        long_message = "x" * 1500  # Longer than max_message_length (1000)
        
        context = await memory_manager.add_message(user_id, HumanMessage(content=long_message))
        
        saved_content = context.recent_messages[0]["content"]
        assert len(saved_content) <= 1020  # 1000 + "... [truncated]"
        assert saved_content.endswith("... [truncated]")
    
    def test_cache_functionality(self, memory_manager):
        """Test in-memory cache functionality."""
        # Clear cache first
        memory_manager.clear_cache()
        
        # Cache should be empty
        assert len(memory_manager._cache) == 0
        
        # Add something to cache manually for testing
        from app.core.smart_memory import ConversationContext
        test_context = ConversationContext("cache_test")
        memory_manager._cache["cache_test"] = test_context
        
        assert len(memory_manager._cache) == 1
        assert memory_manager._cache["cache_test"].thread_id == "cache_test"
        
        # Clear cache
        memory_manager.clear_cache()
        assert len(memory_manager._cache) == 0


class TestChatStateManager:
    """Test ChatStateManager class."""
    
    @pytest.mark.asyncio
    async def test_load_state_new_user(self):
        """Test loading state for a new user."""
        state_manager = ChatStateManager()
        
        # Mock the tools to avoid database calls
        from unittest.mock import patch
        
        with patch('app.core.tools.get_customer') as mock_get_customer:
            with patch('app.core.tools.get_active_order') as mock_get_order:
                # Mock responses
                mock_get_customer.return_value.invoke.return_value = {}
                mock_get_order.return_value.invoke.return_value = {}
                
                state = await state_manager.load_state_for_user("new_user", "Hola")
                
                assert state["user_id"] == "new_user"
                assert state["needs_customer_info"] == True
                assert state["ready_to_order"] == False
                assert state["current_step"] == "greeting"
                assert len(state["messages"]) == 1
                assert state["messages"][0].content == "Hola"
    
    @pytest.mark.asyncio
    async def test_load_state_existing_user(self):
        """Test loading state for an existing user."""
        state_manager = ChatStateManager()
        
        # First add some conversation history
        await state_manager.memory_manager.add_message("existing_user", HumanMessage(content="Hola"))
        await state_manager.memory_manager.add_message("existing_user", AIMessage(content="¡Hola! ¿Cómo estás?"))
        
        from unittest.mock import patch
        
        with patch('app.core.tools.get_customer') as mock_get_customer:
            with patch('app.core.tools.get_active_order') as mock_get_order:
                # Mock existing customer
                mock_get_customer.return_value.invoke.return_value = {
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "phone": "3001234567"
                }
                mock_get_order.return_value.invoke.return_value = {}
                
                state = await state_manager.load_state_for_user("existing_user", "¿Tienen pizza hawaiana?")
                
                assert state["user_id"] == "existing_user"
                assert state["needs_customer_info"] == False
                assert state["ready_to_order"] == True
                assert len(state["messages"]) == 3  # 2 historical + 1 new
                assert state["customer"]["first_name"] == "Juan"
    
    @pytest.mark.asyncio
    async def test_save_state(self):
        """Test saving state to memory."""
        state_manager = ChatStateManager()
        
        # Create a test state
        state = ChatState(
            user_id="save_test",
            messages=[HumanMessage(content="Test message")],
            customer={"first_name": "Test", "last_name": "User"},
            current_step="test",
            active_order={"pizza": "pepperoni"},
            needs_customer_info=False,
            ready_to_order=True
        )
        
        # Save state
        await state_manager.save_state_for_user(state, "Test AI response")
        
        # Verify it was saved
        context = await state_manager.memory_manager.get_conversation("save_test")
        
        assert len(context.recent_messages) == 2  # Human + AI message
        assert context.recent_messages[0]["content"] == "Test message"
        assert context.recent_messages[1]["content"] == "Test AI response"
        assert context.customer_context["customer_name"] == "Test User"
        assert context.customer_context["current_order"]["pizza"] == "pepperoni"


def test_determine_current_step():
    """Test step determination logic."""
    state_manager = ChatStateManager()
    context = ConversationContext("test")
    
    # Test greeting step
    step = state_manager._determine_current_step(context, "Hola", True)
    assert step == "greeting"
    
    # Test menu step
    step = state_manager._determine_current_step(context, "¿Qué pizzas tienen?", False)
    assert step == "menu"
    
    # Test order step
    step = state_manager._determine_current_step(context, "Quiero ordenar una pizza", False)
    assert step == "order"
    
    # Test general step
    step = state_manager._determine_current_step(context, "¿Están abiertos?", False)
    assert step == "general"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 