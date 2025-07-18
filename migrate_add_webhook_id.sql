-- Migration: Add webhook_id support to discord_messages table
-- This migration adds webhook_id field and index for better webhook message tracking

-- Add webhook_id column to discord_messages table
ALTER TABLE discord_messages 
ADD COLUMN IF NOT EXISTS webhook_id TEXT;

-- Add index for webhook_id for efficient webhook message queries
CREATE INDEX IF NOT EXISTS idx_discord_messages_webhook_id ON discord_messages (webhook_id);

-- Add comment for documentation
COMMENT ON COLUMN discord_messages.webhook_id IS 'Discord webhook ID if message was sent by a webhook';

-- Query to check webhook messages after migration
-- SELECT COUNT(*) FROM discord_messages WHERE webhook_id IS NOT NULL;