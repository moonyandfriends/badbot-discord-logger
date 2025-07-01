# Changelog

All notable changes to the Discord Logger Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed
- Database views now use `discord_` prefix for consistency with tables
  - `recent_messages` → `discord_recent_messages`
  - `channel_message_stats` → `discord_channel_message_stats`
  - `action_stats` → `discord_action_stats`
- **Simplified Docker configuration**: Lightweight single-stage Dockerfile for Railway
- **Railway-specific environment template**: `env.railway` file with Railway environment variables
- **Railway CLI commands**: Added Railway-specific deployment and monitoring commands
- **PORT environment variable support**: Automatic detection of Railway's PORT environment variable
- **Root endpoint (`/`)**: Basic bot information endpoint for Railway health checks
- **Comprehensive testing infrastructure**: Added unit tests for configuration module with 100% coverage
- **CLI management tool**: Feature-rich command-line interface for setup, monitoring, and maintenance
- **Health check server**: HTTP endpoints for health monitoring and statistics at `/health` and `/stats`
- **Memory management**: Automatic memory cleanup and garbage collection to prevent memory leaks
- **Enhanced error handling**: Better type safety and error handling throughout the codebase
- **Performance optimizations**: Database caching, connection pooling, and batch operation improvements
- **Additional Discord events**: Voice state updates, channel operations, member updates
- **Statistics collection**: Real-time bot performance metrics and database statistics

### Enhanced
- **Database module**: Added retry logic, connection management, health checks, and data cleanup utilities
- **Configuration validation**: More flexible Supabase URL validation supporting custom domains while maintaining security
- **Configuration validation**: Stricter validation with better error messages and type checking
- **Bot architecture**: Improved queue management, task coordination, and graceful shutdown handling
- Comprehensive pydantic field validators for configuration validation
- Tenacity-based retry logic with exponential backoff for database operations
- Proper async context management for database connections
- Memory-efficient deque-based message queues with size limits
- Garbage collection and memory cleanup tasks
- Enhanced error handling with retryable vs non-retryable error classification
- Additional Discord event handlers (voice state updates, bulk message deletes, channel operations)
- Database statistics collection and monitoring
- Graceful shutdown handling with signal handlers
- Comprehensive type hints throughout the codebase
- Connection pooling and initialization state management
- Batch message processing with upsert operations to handle duplicates
- Enhanced checkpoint management system
- Configuration override support for testing
- Improved logging with both console and file output options

### Changed
- **Environment variable names**: Changed to lowercase for consistency:
  - `DISCORD_TOKEN` → `logger_discord_token`
  - `SUPABASE_URL` → `supabase_url` 
  - `SUPABASE_KEY` → `supabase_key`
- **Simplified deployment stack**: Removed complex monitoring services for Railway deployment
- **Updated README**: Focused on Railway deployment with simplified installation instructions
- **Streamlined CLI tool**: Removed Docker-specific commands, added Railway-focused commands
- **Simplified docker-compose.yml**: Single service configuration without monitoring stack
- Upgraded configuration system to use pydantic-settings with proper BaseSettings
- Improved database operations to use upsert instead of insert for idempotency
- Enhanced message conversion with better error handling for individual message failures
- Refactored retry logic to use tenacity library for more robust error handling
- Improved queue processing with better batch handling and error recovery
- Enhanced checkpoint updates with proper timestamp handling
- Better memory management with tracked message limits to prevent memory leaks
- Improved guild and channel filtering logic with validation

### Fixed
- Configuration instantiation issues with BaseSettings
- Database connection state management and initialization
- Type annotation issues in database operations
- Memory leaks in processed message tracking
- Error handling in batch operations
- Checkpoint update data type issues
- Missing imports and dependency management
- Message content null handling
- Proper async context management

### Removed
- **Multi-service Docker stack**: Removed Redis, Loki, Grafana, Prometheus, and Nginx services
- **Complex monitoring configuration**: Simplified to focus on Railway's built-in monitoring
- **Multi-stage Dockerfile**: Replaced with single-stage lightweight Dockerfile
- **Docker-specific CLI commands**: Removed in favor of Railway-focused commands

### Security
- Added validation for Discord tokens and Supabase credentials
- Enhanced error logging to avoid exposing sensitive information
- Proper sanitization of user input in database operations

## [1.0.0] - 2024-01-XX

### Added
- Initial Discord bot implementation
- Supabase database integration
- Message logging and action tracking
- Backfill capabilities for historical data
- Checkpoint management system
- Configuration management with environment variables
- Basic retry logic for database operations
- PostgreSQL database schema
- Documentation and setup instructions 