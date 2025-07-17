-- Migration script to add webhook logging support
-- Run this script on your existing database to enable webhook event logging
-- 
-- This migration adds support for webhook events without requiring new tables
-- since webhook actions are stored in the existing discord_actions table.

-- Check if the migration has already been applied
DO $$
BEGIN
    -- Check if webhook action types already exist in the database
    IF NOT EXISTS (
        SELECT 1 FROM discord_actions 
        WHERE action_type IN ('webhook_create', 'webhook_update', 'webhook_delete')
    ) THEN
        -- Migration has not been applied yet, safe to proceed
        RAISE NOTICE 'Applying webhook support migration...';
    ELSE
        -- Migration might already be applied, but continue anyway
        RAISE NOTICE 'Webhook actions already exist in database, continuing migration...';
    END IF;
END
$$;

-- Update the table comment to reflect webhook support
COMMENT ON TABLE discord_actions IS 'Stores Discord actions and events like member joins, message edits, webhook updates, etc.';

-- Add an index specifically for webhook actions for better query performance
CREATE INDEX IF NOT EXISTS idx_discord_actions_webhook_events 
ON discord_actions (action_type, guild_id, channel_id) 
WHERE action_type IN ('webhook_create', 'webhook_update', 'webhook_delete');

-- Create a view for webhook events specifically
CREATE OR REPLACE VIEW discord_webhook_events AS
SELECT 
    action_id,
    action_type,
    guild_id,
    channel_id,
    target_name as channel_name,
    action_data,
    occurred_at,
    logged_at,
    is_backfilled
FROM discord_actions
WHERE action_type IN ('webhook_create', 'webhook_update', 'webhook_delete')
ORDER BY occurred_at DESC;

-- Add a comment to the new view
COMMENT ON VIEW discord_webhook_events IS 'View showing all webhook-related events (create, update, delete)';

-- Update the existing action stats view to include webhook events
CREATE OR REPLACE VIEW discord_action_stats AS
SELECT 
    action_type,
    COUNT(*) as count,
    MIN(occurred_at) as first_occurrence,
    MAX(occurred_at) as last_occurrence,
    CASE 
        WHEN action_type IN ('webhook_create', 'webhook_update', 'webhook_delete') THEN 'webhook'
        WHEN action_type IN ('message_delete', 'message_edit', 'message_bulk_delete') THEN 'message'
        WHEN action_type IN ('member_join', 'member_leave', 'member_update', 'member_ban', 'member_unban') THEN 'member'
        WHEN action_type IN ('channel_create', 'channel_delete', 'channel_update') THEN 'channel'
        WHEN action_type IN ('role_create', 'role_delete', 'role_update') THEN 'role'
        ELSE 'other'
    END as category
FROM discord_actions
GROUP BY action_type
ORDER BY count DESC;

-- Create a function to get webhook statistics
CREATE OR REPLACE FUNCTION get_webhook_stats(guild_id_param TEXT DEFAULT NULL)
RETURNS TABLE(
    total_webhook_events BIGINT,
    webhook_creates BIGINT,
    webhook_updates BIGINT,
    webhook_deletes BIGINT,
    channels_with_webhooks BIGINT,
    first_webhook_event TIMESTAMPTZ,
    last_webhook_event TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_webhook_events,
        COUNT(*) FILTER (WHERE action_type = 'webhook_create') as webhook_creates,
        COUNT(*) FILTER (WHERE action_type = 'webhook_update') as webhook_updates,
        COUNT(*) FILTER (WHERE action_type = 'webhook_delete') as webhook_deletes,
        COUNT(DISTINCT channel_id) as channels_with_webhooks,
        MIN(occurred_at) as first_webhook_event,
        MAX(occurred_at) as last_webhook_event
    FROM discord_actions
    WHERE action_type IN ('webhook_create', 'webhook_update', 'webhook_delete')
    AND (guild_id_param IS NULL OR guild_id = guild_id_param);
END;
$$ LANGUAGE plpgsql;

-- Add comment to the function
COMMENT ON FUNCTION get_webhook_stats(TEXT) IS 'Get webhook statistics for a guild (or all guilds if no guild_id provided)';

-- Insert a test record to validate the migration (optional)
-- This will be cleaned up after validation
INSERT INTO discord_actions (
    action_id,
    action_type,
    guild_id,
    channel_id,
    target_type,
    target_name,
    action_data,
    occurred_at,
    logged_at,
    is_backfilled
) VALUES (
    'migration_test_webhook_' || gen_random_uuid(),
    'webhook_update',
    'test_guild_id',
    'test_channel_id',
    'channel',
    'test-channel',
    '{"channel_type": "text", "webhook_event": "update", "migration_test": true}'::jsonb,
    NOW(),
    NOW(),
    false
);

-- Validate the migration by checking if webhook actions can be inserted and queried
DO $$
DECLARE
    test_count INTEGER;
BEGIN
    -- Check if the test record was inserted
    SELECT COUNT(*) INTO test_count
    FROM discord_actions
    WHERE action_type = 'webhook_update' 
    AND action_data->>'migration_test' = 'true';
    
    IF test_count > 0 THEN
        RAISE NOTICE 'Migration validation successful: webhook actions can be stored and queried';
        
        -- Clean up the test record
        DELETE FROM discord_actions 
        WHERE action_type = 'webhook_update' 
        AND action_data->>'migration_test' = 'true';
        
        RAISE NOTICE 'Test record cleaned up';
    ELSE
        RAISE EXCEPTION 'Migration validation failed: webhook actions cannot be stored';
    END IF;
END
$$;

-- Final success message
DO $$
BEGIN
    RAISE NOTICE 'Webhook support migration completed successfully!';
    RAISE NOTICE 'The Discord logger can now capture webhook events.';
    RAISE NOTICE 'New webhook events will be stored in the discord_actions table.';
    RAISE NOTICE 'Use the discord_webhook_events view to query webhook-specific data.';
    RAISE NOTICE 'Use SELECT * FROM get_webhook_stats() to get webhook statistics.';
END
$$;