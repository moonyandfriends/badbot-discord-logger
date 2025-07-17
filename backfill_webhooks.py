#!/usr/bin/env python3
"""
Backfill script to fetch all existing webhooks from Discord servers and store them in the database.
This script should be run after applying the migrate_webhook_support.sql migration.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any
import uuid

import discord
from discord.ext import commands
from supabase import create_client, Client
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

class WebhookBackfiller:
    def __init__(self):
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not all([self.bot_token, self.supabase_url, self.supabase_key]):
            raise ValueError("Missing required environment variables: DISCORD_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY")
        
        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Discord intents - we only need guilds to fetch webhooks
        intents = discord.Intents.default()
        intents.guilds = True
        
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.webhooks_processed = 0
        self.guilds_processed = 0
        self.errors = []

    async def check_migration_status(self) -> bool:
        """Check if the webhook migration has been applied."""
        try:
            # Check if webhook events view exists
            result = self.supabase.rpc('get_webhook_stats').execute()
            logger.info("Webhook migration is applied and ready")
            return True
        except Exception as e:
            logger.error(f"Webhook migration not found: {e}")
            logger.error("Please run migrate_webhook_support.sql first")
            return False

    async def get_existing_webhook_ids(self, guild_id: str) -> set:
        """Get IDs of webhooks already in the database for a guild."""
        try:
            result = self.supabase.table('discord_actions').select('action_data').eq(
                'guild_id', guild_id
            ).eq('action_type', 'webhook_create').execute()
            
            existing_ids = set()
            for row in result.data:
                webhook_id = row['action_data'].get('webhook_id')
                if webhook_id:
                    existing_ids.add(webhook_id)
            
            return existing_ids
        except Exception as e:
            logger.error(f"Error fetching existing webhooks for guild {guild_id}: {e}")
            return set()

    async def store_webhook(self, webhook: discord.Webhook, guild: discord.Guild, channel: discord.TextChannel) -> bool:
        """Store a webhook as a backfilled webhook_create event."""
        try:
            action_id = f"backfill_webhook_{webhook.id}_{uuid.uuid4().hex[:8]}"
            
            # Prepare webhook data
            webhook_data = {
                "webhook_id": str(webhook.id),
                "webhook_name": webhook.name,
                "webhook_token": "REDACTED",  # Never store tokens
                "webhook_url": "REDACTED",    # Never store URLs
                "webhook_type": webhook.type.name,
                "channel_id": str(channel.id),
                "channel_name": channel.name,
                "channel_type": str(channel.type),
                "user_id": str(webhook.user.id) if webhook.user else None,
                "user_name": webhook.user.name if webhook.user else None,
                "avatar": str(webhook.avatar) if webhook.avatar else None,
                "application_id": str(webhook.application_id) if webhook.application_id else None,
                "backfilled_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Insert as a webhook_create action
            action_record = {
                "action_id": action_id,
                "action_type": "webhook_create",
                "guild_id": str(guild.id),
                "channel_id": str(channel.id),
                "target_type": "webhook",
                "target_name": webhook.name,
                "action_data": webhook_data,
                "occurred_at": webhook.created_at.isoformat() if webhook.created_at else datetime.now(timezone.utc).isoformat(),
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "is_backfilled": True
            }
            
            self.supabase.table('discord_actions').insert(action_record).execute()
            logger.debug(f"Stored webhook: {webhook.name} (ID: {webhook.id}) in #{channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing webhook {webhook.id}: {e}")
            self.errors.append(f"Webhook {webhook.id} in guild {guild.id}: {str(e)}")
            return False

    async def backfill_guild_webhooks(self, guild: discord.Guild) -> Dict[str, int]:
        """Backfill all webhooks for a single guild."""
        stats = {"total": 0, "new": 0, "existing": 0, "failed": 0}
        
        try:
            # Get existing webhook IDs to avoid duplicates
            existing_ids = await self.get_existing_webhook_ids(str(guild.id))
            
            # Fetch all webhooks in the guild
            webhooks = await guild.webhooks()
            stats["total"] = len(webhooks)
            
            logger.info(f"Found {len(webhooks)} webhooks in guild: {guild.name} (ID: {guild.id})")
            
            for webhook in webhooks:
                # Skip if already exists
                if str(webhook.id) in existing_ids:
                    stats["existing"] += 1
                    logger.debug(f"Skipping existing webhook: {webhook.name} (ID: {webhook.id})")
                    continue
                
                # Get the channel
                channel = webhook.channel
                if not channel:
                    logger.warning(f"Webhook {webhook.id} has no channel, skipping")
                    stats["failed"] += 1
                    continue
                
                # Store the webhook
                if await self.store_webhook(webhook, guild, channel):
                    stats["new"] += 1
                    self.webhooks_processed += 1
                else:
                    stats["failed"] += 1
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
            
            return stats
            
        except discord.Forbidden:
            logger.error(f"No permission to fetch webhooks in guild: {guild.name}")
            self.errors.append(f"Guild {guild.id}: No permission to fetch webhooks")
            return stats
        except Exception as e:
            logger.error(f"Error processing guild {guild.id}: {e}")
            self.errors.append(f"Guild {guild.id}: {str(e)}")
            return stats

    async def run_backfill(self):
        """Main backfill process."""
        @self.bot.event
        async def on_ready():
            logger.info(f"Bot connected as {self.bot.user}")
            logger.info(f"Connected to {len(self.bot.guilds)} guilds")
            
            # Check migration status first
            if not await self.check_migration_status():
                logger.error("Aborting: Migration not applied")
                await self.bot.close()
                return
            
            # Process each guild
            for guild in self.bot.guilds:
                logger.info(f"\nProcessing guild: {guild.name} (ID: {guild.id})")
                stats = await self.backfill_guild_webhooks(guild)
                self.guilds_processed += 1
                
                logger.info(f"Guild stats - Total: {stats['total']}, New: {stats['new']}, "
                          f"Existing: {stats['existing']}, Failed: {stats['failed']}")
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("BACKFILL COMPLETE")
            logger.info(f"Guilds processed: {self.guilds_processed}")
            logger.info(f"Webhooks added: {self.webhooks_processed}")
            
            if self.errors:
                logger.warning(f"\nErrors encountered: {len(self.errors)}")
                for error in self.errors[:10]:  # Show first 10 errors
                    logger.warning(f"  - {error}")
                if len(self.errors) > 10:
                    logger.warning(f"  ... and {len(self.errors) - 10} more errors")
            
            # Fetch and display stats
            try:
                stats_result = self.supabase.rpc('get_webhook_stats').execute()
                if stats_result.data and len(stats_result.data) > 0:
                    stats = stats_result.data[0]
                    logger.info("\nDatabase webhook statistics:")
                    logger.info(f"  Total webhook events: {stats['total_webhook_events']}")
                    logger.info(f"  Webhook creates: {stats['webhook_creates']}")
                    logger.info(f"  Channels with webhooks: {stats['channels_with_webhooks']}")
            except Exception as e:
                logger.error(f"Could not fetch webhook stats: {e}")
            
            await self.bot.close()
        
        # Start the bot
        try:
            await self.bot.start(self.bot_token)
        except KeyboardInterrupt:
            logger.info("Backfill interrupted by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            if not self.bot.is_closed():
                await self.bot.close()

async def main():
    """Main entry point."""
    logger.info("Starting webhook backfill process...")
    logger.info("This will fetch all existing webhooks from your Discord servers")
    logger.info("and store them as backfilled webhook_create events.")
    
    # Check for auto-run environment variable
    auto_run = os.getenv("WEBHOOK_BACKFILL_AUTO_RUN", "").lower() in ["true", "1", "yes"]
    
    if not auto_run:
        # Confirm before proceeding
        print("\nThis script will:")
        print("1. Connect to Discord using your bot token")
        print("2. Fetch all webhooks from all guilds the bot has access to")
        print("3. Store them in the database as backfilled events")
        print("\nNote: Webhook tokens and URLs are NEVER stored for security.")
        print("\nTip: Set WEBHOOK_BACKFILL_AUTO_RUN=true to skip this prompt")
        
        response = input("\nProceed with backfill? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Backfill cancelled by user")
            return
    else:
        logger.info("Auto-run enabled via WEBHOOK_BACKFILL_AUTO_RUN environment variable")
        logger.info("Proceeding with backfill automatically...")
    
    backfiller = WebhookBackfiller()
    await backfiller.run_backfill()

if __name__ == "__main__":
    asyncio.run(main())