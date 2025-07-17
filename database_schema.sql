`-- Database schema for BadBot Discord Logger
-- This file contains all the table definitions needed for the Discord logging system

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for storing Discord messages
CREATE TABLE IF NOT EXISTS discord_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id TEXT NOT NULL UNIQUE,
    channel_id TEXT NOT NULL,
    guild_id TEXT,
    content TEXT,
    message_type TEXT DEFAULT 'default',
    
    -- Author information
    author_id TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_display_name TEXT,
    author_discriminator TEXT,
    author_avatar_url TEXT,
    author_is_bot BOOLEAN DEFAULT FALSE,
    author_is_system BOOLEAN DEFAULT FALSE,
    
    -- Message metadata
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ,
    pinned BOOLEAN DEFAULT FALSE,
    mention_everyone BOOLEAN DEFAULT FALSE,
    tts BOOLEAN DEFAULT FALSE,
    
    -- Rich content (stored as JSONB for flexibility)
    attachments JSONB DEFAULT '[]'::jsonb,
    embeds JSONB DEFAULT '[]'::jsonb,
    mentions TEXT[] DEFAULT '{}',
    mention_roles TEXT[] DEFAULT '{}',
    mention_channels TEXT[] DEFAULT '{}',
    
    -- Thread and reference information
    thread_id TEXT,
    reference_message_id TEXT,
    
    -- Application/interaction info
    application_id TEXT,
    interaction_type TEXT,
    
    -- Metadata
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    is_backfilled BOOLEAN DEFAULT FALSE,
    
    -- Indexes for common queries
    CONSTRAINT discord_messages_message_id_key UNIQUE (message_id)
);

-- Indexes for messages table
CREATE INDEX IF NOT EXISTS idx_discord_messages_channel_id ON discord_messages (channel_id);
CREATE INDEX IF NOT EXISTS idx_discord_messages_guild_id ON discord_messages (guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_messages_author_id ON discord_messages (author_id);
CREATE INDEX IF NOT EXISTS idx_discord_messages_created_at ON discord_messages (created_at);
CREATE INDEX IF NOT EXISTS idx_discord_messages_logged_at ON discord_messages (logged_at);
CREATE INDEX IF NOT EXISTS idx_discord_messages_is_backfilled ON discord_messages (is_backfilled);

-- Table for storing Discord actions/events
CREATE TABLE IF NOT EXISTS discord_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_id TEXT NOT NULL UNIQUE,
    action_type TEXT NOT NULL,
    guild_id TEXT,
    channel_id TEXT,
    
    -- Actor information
    user_id TEXT,
    username TEXT,
    display_name TEXT,
    
    -- Target information
    target_id TEXT,
    target_type TEXT,
    target_name TEXT,
    
    -- Action details (stored as JSONB for flexibility)
    action_data JSONB DEFAULT '{}'::jsonb,
    before_data JSONB,
    after_data JSONB,
    
    -- Metadata
    occurred_at TIMESTAMPTZ NOT NULL,
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    is_backfilled BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT discord_actions_action_id_key UNIQUE (action_id)
);

-- Indexes for actions table
CREATE INDEX IF NOT EXISTS idx_discord_actions_action_type ON discord_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_discord_actions_guild_id ON discord_actions (guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_actions_channel_id ON discord_actions (channel_id);
CREATE INDEX IF NOT EXISTS idx_discord_actions_user_id ON discord_actions (user_id);
CREATE INDEX IF NOT EXISTS idx_discord_actions_occurred_at ON discord_actions (occurred_at);
CREATE INDEX IF NOT EXISTS idx_discord_actions_is_backfilled ON discord_actions (is_backfilled);

-- Table for tracking processing checkpoints
CREATE TABLE IF NOT EXISTS discord_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id TEXT NOT NULL UNIQUE,
    guild_id TEXT,
    channel_id TEXT,
    
    -- Checkpoint data
    checkpoint_type TEXT NOT NULL,
    last_processed_id TEXT,
    last_processed_timestamp TIMESTAMPTZ,
    
    -- Processing statistics
    total_processed INTEGER DEFAULT 0,
    last_backfill_completed TIMESTAMPTZ,
    backfill_in_progress BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT discord_checkpoints_checkpoint_id_key UNIQUE (checkpoint_id)
);

-- Indexes for checkpoints table
CREATE INDEX IF NOT EXISTS idx_discord_checkpoints_type ON discord_checkpoints (checkpoint_type);
CREATE INDEX IF NOT EXISTS idx_discord_checkpoints_guild_id ON discord_checkpoints (guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_checkpoints_channel_id ON discord_checkpoints (channel_id);
CREATE INDEX IF NOT EXISTS idx_discord_checkpoints_updated_at ON discord_checkpoints (updated_at);

-- Table for storing Discord guild information
CREATE TABLE IF NOT EXISTS discord_guilds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    owner_id TEXT NOT NULL,
    member_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    icon_url TEXT,
    banner_url TEXT,
    
    -- Metadata
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT discord_guilds_guild_id_key UNIQUE (guild_id)
);

-- Indexes for guilds table
CREATE INDEX IF NOT EXISTS idx_discord_guilds_guild_id ON discord_guilds (guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_guilds_owner_id ON discord_guilds (owner_id);
CREATE INDEX IF NOT EXISTS idx_discord_guilds_last_updated ON discord_guilds (last_updated);
CREATE INDEX IF NOT EXISTS idx_discord_guilds_updated_at ON discord_guilds (updated_at);

-- Table for storing Discord channel information
CREATE TABLE IF NOT EXISTS discord_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id TEXT NOT NULL UNIQUE,
    guild_id TEXT,
    name TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    topic TEXT,
    position INTEGER,
    category_id TEXT,
    
    -- Metadata
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT discord_channels_channel_id_key UNIQUE (channel_id)
);

-- Indexes for channels table
CREATE INDEX IF NOT EXISTS idx_discord_channels_channel_id ON discord_channels (channel_id);
CREATE INDEX IF NOT EXISTS idx_discord_channels_guild_id ON discord_channels (guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_channels_channel_type ON discord_channels (channel_type);
CREATE INDEX IF NOT EXISTS idx_discord_channels_last_updated ON discord_channels (last_updated);
CREATE INDEX IF NOT EXISTS idx_discord_channels_updated_at ON discord_channels (updated_at);

-- Function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update updated_at columns
CREATE OR REPLACE TRIGGER update_discord_checkpoints_updated_at
    BEFORE UPDATE ON discord_checkpoints
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_discord_guilds_updated_at
    BEFORE UPDATE ON discord_guilds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_discord_channels_updated_at
    BEFORE UPDATE ON discord_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies (optional, for additional security)
-- Uncomment these if you want to enable RLS

-- ALTER TABLE discord_messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE discord_actions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE discord_checkpoints ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE discord_guilds ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE discord_channels ENABLE ROW LEVEL SECURITY;

-- Create policies for service role access
-- CREATE POLICY "Service role can access discord_messages" ON discord_messages
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access discord_actions" ON discord_actions
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access discord_checkpoints" ON discord_checkpoints
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access discord_guilds" ON discord_guilds
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access discord_channels" ON discord_channels
--     FOR ALL USING (auth.role() = 'service_role');

-- Create some useful views for common queries

-- View for recent messages with author information
CREATE OR REPLACE VIEW discord_recent_messages AS
SELECT 
    m.message_id,
    m.content,
    m.author_username,
    m.author_display_name,
    m.created_at,
    g.name as guild_name,
    c.name as channel_name
FROM discord_messages m
LEFT JOIN discord_guilds g ON m.guild_id = g.guild_id
LEFT JOIN discord_channels c ON m.channel_id = c.channel_id
ORDER BY m.created_at DESC;

-- View for message statistics by channel
CREATE OR REPLACE VIEW discord_channel_message_stats AS
SELECT 
    c.channel_id,
    c.name as channel_name,
    g.name as guild_name,
    COUNT(m.id) as message_count,
    COUNT(DISTINCT m.author_id) as unique_authors,
    MIN(m.created_at) as first_message,
    MAX(m.created_at) as last_message
FROM discord_channels c
LEFT JOIN discord_messages m ON c.channel_id = m.channel_id
LEFT JOIN discord_guilds g ON c.guild_id = g.guild_id
GROUP BY c.channel_id, c.name, g.name;

-- View for action statistics
CREATE OR REPLACE VIEW discord_action_stats AS
SELECT 
    action_type,
    COUNT(*) as count,
    MIN(occurred_at) as first_occurrence,
    MAX(occurred_at) as last_occurrence
FROM discord_actions
GROUP BY action_type
ORDER BY count DESC;

-- Comments for documentation
COMMENT ON TABLE discord_messages IS 'Stores all Discord messages with full metadata and content';
COMMENT ON TABLE discord_actions IS 'Stores Discord actions and events like member joins, message edits, webhook updates, etc.';
COMMENT ON TABLE discord_checkpoints IS 'Tracks processing progress for backfill and real-time operations';
COMMENT ON TABLE discord_guilds IS 'Stores Discord guild (server) information';
COMMENT ON TABLE discord_channels IS 'Stores Discord channel information';

COMMENT ON COLUMN discord_messages.is_backfilled IS 'Indicates if this message was added during backfill process';
COMMENT ON COLUMN discord_actions.is_backfilled IS 'Indicates if this action was added during backfill process';
COMMENT ON COLUMN discord_checkpoints.backfill_in_progress IS 'Indicates if backfill is currently running for this checkpoint'; `