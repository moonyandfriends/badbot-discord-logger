#!/usr/bin/env python3
"""
Main entry point for the BadBot Discord Logger.

This script initializes and runs the Discord bot for logging messages and actions
to a Supabase database with comprehensive backfill and checkpoint capabilities.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from badbot_discord_logger import DiscordLogger
from badbot_discord_logger.config import load_config


async def main() -> None:
    """Main entry point for the Discord Logger Bot."""
    try:
        # Run webhook backfill if needed (one-time operation)
        import os
        if os.getenv("RUN_WEBHOOK_BACKFILL", "").lower() == "true":
            print("Running webhook backfill script...")
            try:
                import subprocess
                result = subprocess.run([sys.executable, "backfill_webhooks.py"], 
                                      capture_output=True, text=True)
                print(f"Backfill output: {result.stdout}")
                if result.stderr:
                    print(f"Backfill errors: {result.stderr}")
                print("Webhook backfill completed")
            except Exception as e:
                print(f"Error running backfill: {e}")
        
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        print(f"Configuration loaded successfully")
        print(f"Bot will connect to {len(config.allowed_guilds_list) if config.allowed_guilds_list else 'all'} guilds")
        print(f"Backfill enabled: {config.backfill_enabled}")
        
        # Initialize and start bot
        print("Initializing Discord bot...")
        bot = DiscordLogger(config)
        
        print("Starting bot...")
        print("Press Ctrl+C to stop the bot gracefully")
        
        await bot.start(config.discord_token)
        
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("Bot shutdown complete")


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main()) 