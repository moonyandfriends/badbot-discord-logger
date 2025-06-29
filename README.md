# Discord Logger Bot

A production-ready Discord bot that logs all messages and server activities to a Supabase database. Optimized for Railway deployment with automatic scaling and built-in health monitoring.

## ✨ Features

### Core Functionality
- **Complete Message Logging**: Captures all Discord messages with full metadata, attachments, embeds, and mentions
- **Comprehensive Action Tracking**: Logs member events, message edits/deletes, role changes, voice state updates, and more
- **Historical Backfill**: Imports previous messages from channels with resumable progress tracking
- **Smart Checkpoint Management**: Tracks processing state to resume from interruptions
- **Real-time Processing**: Handles new events as they happen with minimal latency

### Production Features
- **Railway Optimized**: Designed specifically for Railway's hosting platform
- **Memory Management**: Automatic cleanup and garbage collection for long-running deployments
- **Robust Error Handling**: Exponential backoff retry logic with comprehensive error classification
- **Health Monitoring**: Built-in health check endpoints for Railway's monitoring
- **Guild/Channel Filtering**: Configurable allow/ignore lists for targeted monitoring
- **Configuration Validation**: Comprehensive validation with helpful error messages

### Developer Experience
- **CLI Management**: Rich command-line interface for setup and maintenance
- **Easy Deployment**: One-click Railway deployment with automatic scaling
- **Type Safety**: Full type annotations and validation with Pydantic

## 🚀 Quick Start (Railway Deployment)

### 1. Setup Configuration

Use the CLI tool to generate your configuration:

```bash
python cli.py setup
```

This will prompt you for:
- Discord bot token
- Supabase URL
- Supabase key

### 2. Test Configuration

Verify your setup works locally:

```bash
python cli.py config test
```

### 3. Deploy to Railway

Follow the Railway deployment guide:

```bash
python cli.py railway
```

Or manually:

1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Create project: `railway new`
4. Deploy: `railway up`
5. Set environment variables in Railway dashboard

## 🛠️ Local Development

### Prerequisites

- Python 3.10+
- A Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- A Supabase project with PostgreSQL database

### Installation

```bash
# Clone the repository
git clone https://github.com/moonyandfriends/badbot-discord-logger.git
cd badbot-discord-logger

# Install dependencies
pip install -r requirements.txt

# Setup configuration
python cli.py setup

# Test configuration
python cli.py config test

# Run locally
python main.py
```

## ⚙️ Configuration

### Required Environment Variables

Set these in your Railway project or `.env` file:

```env
# Discord Configuration
logger_discord_token=your_discord_bot_token_here

# Supabase Configuration  
supabase_url=https://your-project.supabase.co
supabase_key=your_supabase_anon_key_here
```

### Optional Configuration

Customize behavior with additional settings:

```env
# Logging
LOG_LEVEL=INFO
ENABLE_DEBUG=false

# Backfill Settings (set BACKFILL_ON_STARTUP=false for initial deployment)
BACKFILL_ENABLED=true
BACKFILL_CHUNK_SIZE=100
BACKFILL_DELAY_SECONDS=1.0
BACKFILL_ON_STARTUP=false

# Performance Tuning
BATCH_SIZE=50
MAX_QUEUE_SIZE=10000
FLUSH_INTERVAL=30

# Message Processing
PROCESS_BOT_MESSAGES=true
PROCESS_SYSTEM_MESSAGES=true
PROCESS_DM_MESSAGES=false

# Filtering (comma-separated IDs)
ALLOWED_GUILDS=123456789,987654321  # Leave empty for all guilds
IGNORED_GUILDS=111111111
ALLOWED_CHANNELS=channel_id_1,channel_id_2
IGNORED_CHANNELS=channel_id_3
```

## 🗄️ Database Setup

### 1. Create Supabase Tables

Run the provided SQL schema in your Supabase database:

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Execute the content of `database_schema.sql`

### 2. Verify Setup

The following tables will be created:
- `discord_messages` - All message data
- `discord_actions` - Action/event logs  
- `discord_checkpoints` - Processing state tracking
- `discord_guilds` - Guild information
- `discord_channels` - Channel information

Check your setup with:

```bash
python cli.py db health
```

## 📊 Monitoring

### Railway Integration

The bot includes health check endpoints that Railway uses for monitoring:

- `GET /` - Basic bot information
- `GET /health` - Comprehensive health status
- `GET /stats` - Processing statistics

### CLI Commands

Monitor your deployment with these commands:

```bash
# Check bot status (replace URL with your Railway app URL)
python cli.py bot status --url https://your-app.railway.app

# View database statistics
python cli.py db stats

# Check database health
python cli.py db health
```

### Railway Logs

Monitor your bot through Railway:

```bash
railway logs           # View recent logs
railway status         # Check deployment status
```

## 🔧 CLI Reference

The included CLI tool provides comprehensive management:

```bash
# Setup and configuration
python cli.py setup              # Interactive configuration setup
python cli.py config test        # Test configuration and connections

# Database management
python cli.py db stats           # Show database statistics
python cli.py db health          # Check database health

# Bot monitoring
python cli.py bot status         # Check bot status
python cli.py railway            # Railway deployment guide
python cli.py docs               # Show documentation
```

## 📋 Bot Permissions

Your Discord bot needs these permissions:

- Read Messages/View Channels
- Read Message History  
- Send Messages (for commands)
- Use Slash Commands
- View Guild Insights (for member events)

Generate an invite link with these permissions from the Discord Developer Portal.

## 🚨 Important Notes

### Initial Deployment

For your first Railway deployment:

1. Set `BACKFILL_ON_STARTUP=false` to avoid overwhelming the database
2. Monitor the deployment logs with `railway logs`
3. Once stable, you can enable backfill: `railway variables set BACKFILL_ENABLED=true`

### Rate Limiting

The bot respects Discord's rate limits and includes:
- Automatic retry with exponential backoff
- Queue management to prevent overwhelming
- Graceful degradation under heavy load

### Memory Management  

For large servers, the bot includes:
- Automatic memory cleanup every 10 minutes
- Configurable queue sizes to prevent memory issues
- Garbage collection to maintain stable memory usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Railway Logs**: Use `railway logs` to troubleshoot deployment issues
- **CLI Help**: Run `python cli.py --help` for available commands
- **Database Issues**: Use `python cli.py db health` to diagnose problems