-- Smart Conversation Memory Schema for Pizzeria Chatbot
-- This table stores conversation context using hybrid approach

-- Create the main table for smart conversation memory
CREATE TABLE IF NOT EXISTS smart_conversation_memory (
    thread_id TEXT PRIMARY KEY,                    -- User ID for the conversation
    customer_context JSONB DEFAULT '{}',           -- Key customer information (name, preferences, etc)
    recent_messages JSONB DEFAULT '[]',            -- Array of recent messages (sliding window)
    session_metadata JSONB DEFAULT '{}',           -- Additional session data
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),  -- Last time conversation was updated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()      -- When conversation started
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_smart_memory_last_activity 
ON smart_conversation_memory(last_activity);

CREATE INDEX IF NOT EXISTS idx_smart_memory_created_at 
ON smart_conversation_memory(created_at);

-- Optional: Create index on customer context for queries
CREATE INDEX IF NOT EXISTS idx_smart_memory_customer_context 
ON smart_conversation_memory USING GIN (customer_context);

-- Function to automatically update last_activity when record is modified
CREATE OR REPLACE FUNCTION update_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update last_activity
DROP TRIGGER IF EXISTS trigger_update_last_activity ON smart_conversation_memory;
CREATE TRIGGER trigger_update_last_activity
    BEFORE UPDATE ON smart_conversation_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_last_activity();

-- Example data structure for reference:
/*
INSERT INTO smart_conversation_memory (thread_id, customer_context, recent_messages) VALUES (
    'user123',
    '{"name": "Juan Pérez", "phone": "3001234567", "current_order": "pizza_pepperoni_medium"}',
    '[
        {"role": "human", "content": "Hola", "timestamp": "2024-01-07T10:00:00Z"},
        {"role": "assistant", "content": "¡Hola! Bienvenido a nuestra pizzería", "timestamp": "2024-01-07T10:00:01Z"},
        {"role": "human", "content": "Quiero una pizza", "timestamp": "2024-01-07T10:01:00Z"}
    ]'
);
*/

-- Query examples for reference:

-- Get conversation for a specific user
-- SELECT * FROM smart_conversation_memory WHERE thread_id = 'user123';

-- Get all active conversations (last 24 hours)
-- SELECT thread_id, last_activity, jsonb_array_length(recent_messages) as message_count 
-- FROM smart_conversation_memory 
-- WHERE last_activity > NOW() - INTERVAL '24 hours';

-- Clean up old conversations (older than 7 days)
-- DELETE FROM smart_conversation_memory 
-- WHERE last_activity < NOW() - INTERVAL '7 days';

-- Get conversation statistics
-- SELECT 
--     COUNT(*) as total_conversations,
--     AVG(jsonb_array_length(recent_messages)) as avg_messages,
--     COUNT(*) FILTER (WHERE last_activity > NOW() - INTERVAL '1 day') as active_today
-- FROM smart_conversation_memory; 