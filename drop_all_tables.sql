-- Drop all tables, views, functions, and triggers for BadBot Discord Logger
-- WARNING: This will permanently delete all data!

-- Drop views first (they depend on tables)
DROP VIEW IF EXISTS action_stats CASCADE;
DROP VIEW IF EXISTS channel_message_stats CASCADE;
DROP VIEW IF EXISTS recent_messages CASCADE;

-- Drop triggers (they depend on tables)
DROP TRIGGER IF EXISTS update_discord_channels_updated_at ON discord_channels;
DROP TRIGGER IF EXISTS update_discord_guilds_updated_at ON discord_guilds;
DROP TRIGGER IF EXISTS update_discord_checkpoints_updated_at ON discord_checkpoints;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Drop tables (in reverse order of dependencies)
DROP TABLE IF EXISTS discord_channels CASCADE;
DROP TABLE IF EXISTS discord_guilds CASCADE;
DROP TABLE IF EXISTS discord_checkpoints CASCADE;
DROP TABLE IF EXISTS discord_actions CASCADE;
DROP TABLE IF EXISTS discord_messages CASCADE;

-- Drop indexes (they should be dropped with tables, but just in case)
-- Note: Indexes are automatically dropped when their parent table is dropped

-- Optional: Drop the UUID extension if you want to remove it completely
-- DROP EXTENSION IF EXISTS "uuid-ossp";

-- Verify all objects are dropped
SELECT 'Tables remaining:' as info;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'discord_%';

SELECT 'Views remaining:' as info;
SELECT viewname FROM pg_views WHERE schemaname = 'public' AND viewname LIKE '%';

SELECT 'Functions remaining:' as info;
SELECT proname FROM pg_proc WHERE proname LIKE '%discord%' OR proname LIKE '%update_updated_at%';

SELECT 'Triggers remaining:' as info;
SELECT tgname FROM pg_trigger WHERE tgname LIKE '%discord%' OR tgname LIKE '%update_updated_at%'; 