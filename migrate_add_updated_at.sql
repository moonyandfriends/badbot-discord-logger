-- Migration script to add updated_at fields to existing tables
-- Run this script to fix the "record 'new' has no field 'updated_at'" error

-- Add updated_at field to discord_guilds table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'discord_guilds' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE discord_guilds ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
        CREATE INDEX IF NOT EXISTS idx_discord_guilds_updated_at ON discord_guilds (updated_at);
        RAISE NOTICE 'Added updated_at column to discord_guilds table';
    ELSE
        RAISE NOTICE 'updated_at column already exists in discord_guilds table';
    END IF;
END $$;

-- Add updated_at field to discord_channels table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'discord_channels' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE discord_channels ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
        CREATE INDEX IF NOT EXISTS idx_discord_channels_updated_at ON discord_channels (updated_at);
        RAISE NOTICE 'Added updated_at column to discord_channels table';
    ELSE
        RAISE NOTICE 'updated_at column already exists in discord_channels table';
    END IF;
END $$;

-- Update existing records to have updated_at = last_updated
UPDATE discord_guilds SET updated_at = last_updated WHERE updated_at IS NULL;
UPDATE discord_channels SET updated_at = last_updated WHERE updated_at IS NULL;

-- Ensure the triggers exist and are working
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS update_discord_guilds_updated_at ON discord_guilds;
DROP TRIGGER IF EXISTS update_discord_channels_updated_at ON discord_channels;

-- Recreate the triggers
CREATE OR REPLACE TRIGGER update_discord_guilds_updated_at
    BEFORE UPDATE ON discord_guilds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_discord_channels_updated_at
    BEFORE UPDATE ON discord_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

RAISE NOTICE 'Migration completed successfully!'; 