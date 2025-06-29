"""
Main Discord bot implementation for logging messages and actions.

This module contains the DiscordLogger bot class that handles all Discord events,
message logging, action tracking, and backfill capabilities with checkpoint management.
"""

import asyncio
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque

import discord
from discord.ext import commands, tasks
from loguru import logger

from .config import Config, get_config
from .database import SupabaseManager, DatabaseError
from .models import ActionType


class DiscordLogger(commands.Bot):
    """
    Discord bot for comprehensive message and action logging.
    
    This bot logs all messages and actions to a Supabase database with
    support for backfilling historical data and checkpoint management.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """
        Initialize the Discord Logger bot.
        
        Args:
            config: Configuration object, defaults to loading from environment
        """
        self.config = config or get_config()
        
        # Initialize bot with intents
        intents = discord.Intents.all()
        
        super().__init__(
            command_prefix=self.config.bot_prefix,
            intents=intents,
            help_command=None,
            description="Discord message and action logging bot"
        )
        
        # Initialize components
        self.db_manager = SupabaseManager(self.config)
        
        # Queues for batch processing
        self.message_queue: deque = deque(maxlen=self.config.max_queue_size)
        self.action_queue: deque = deque(maxlen=self.config.max_queue_size)
        
        # Tracking sets for processed items
        self.processed_messages: Set[str] = set()
        self.processed_actions: Set[str] = set()
        
        # Backfill tracking
        self.backfill_in_progress: Dict[str, bool] = {}
        self.backfill_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.stats = {
            "messages_processed": 0,
            "actions_processed": 0,
            "errors": 0,
            "start_time": datetime.now(timezone.utc)
        }
        
        # Setup logging
        self._setup_logging()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = self.config.log_level.upper()
        
        # Remove default logger
        logger.remove()
        
        # Add console logger
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # Add file logger if configured
        if self.config.log_file_path:
            logger.add(
                self.config.log_file_path,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation=self.config.log_max_size,
                retention=self.config.log_backup_count,
                compression="gz"
            )
    
    def _register_event_handlers(self) -> None:
        """Register all Discord event handlers."""
        
        @self.event
        async def on_ready() -> None:
            """Called when the bot is ready."""
            logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} guilds")
            
            # Initialize database
            try:
                await self.db_manager.initialize()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                await self.close()
                return
            
            # Start background tasks
            self.process_queues.start()
            
            # Store guild and channel information
            await self._store_guild_info()
            
            # Start backfill if enabled
            if self.config.backfill_enabled and self.config.backfill_on_startup:
                logger.info("Starting backfill process...")
                asyncio.create_task(self._start_backfill_all_guilds())
        
        @self.event
        async def on_message(message: discord.Message) -> None:
            """Handle new messages."""
            if not await self._should_process_message(message):
                return
            
            # Add to processing queue
            await self._queue_message(message)
            
            # Process bot commands
            await self.process_commands(message)
        
        @self.event
        async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
            """Handle message edits."""
            if not await self._should_process_message(after):
                return
            
            # Store the edited message
            await self._queue_message(after)
            
            # Store edit action
            await self._queue_action(
                ActionType.MESSAGE_EDIT,
                guild_id=str(after.guild.id) if after.guild else None,
                channel_id=str(after.channel.id),
                user_id=str(after.author.id),
                target_id=str(after.id),
                before_data={"content": before.content, "edited_at": before.edited_at.isoformat() if before.edited_at else None},
                after_data={"content": after.content, "edited_at": after.edited_at.isoformat() if after.edited_at else None}
            )
        
        @self.event
        async def on_message_delete(message: discord.Message) -> None:
            """Handle message deletions."""
            if not await self._should_process_message(message):
                return
            
            # Store delete action
            await self._queue_action(
                ActionType.MESSAGE_DELETE,
                guild_id=str(message.guild.id) if message.guild else None,
                channel_id=str(message.channel.id),
                user_id=str(message.author.id),
                target_id=str(message.id),
                before_data={
                    "content": message.content,
                    "author_id": str(message.author.id),
                    "created_at": message.created_at.isoformat()
                }
            )
        
        @self.event
        async def on_bulk_message_delete(messages: List[discord.Message]) -> None:
            """Handle bulk message deletions."""
            if not messages:
                return
            
            # Filter messages we should process
            filtered_messages = []
            for message in messages:
                if await self._should_process_message(message):
                    filtered_messages.append(message)
            
            if not filtered_messages:
                return
            
            # Store bulk delete action
            await self._queue_action(
                ActionType.MESSAGE_BULK_DELETE,
                guild_id=str(filtered_messages[0].guild.id) if filtered_messages[0].guild else None,
                channel_id=str(filtered_messages[0].channel.id),
                action_data={
                    "message_count": len(filtered_messages),
                    "message_ids": [str(msg.id) for msg in filtered_messages]
                }
            )
        
        @self.event
        async def on_member_join(member: discord.Member) -> None:
            """Handle member joins."""
            if not self.config.should_process_guild(str(member.guild.id)):
                return
            
            await self._queue_action(
                ActionType.MEMBER_JOIN,
                guild_id=str(member.guild.id),
                user_id=str(member.id),
                action_data={
                    "username": member.name,
                    "display_name": member.display_name,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None
                }
            )
        
        @self.event
        async def on_member_remove(member: discord.Member) -> None:
            """Handle member leaves."""
            if not self.config.should_process_guild(str(member.guild.id)):
                return
            
            await self._queue_action(
                ActionType.MEMBER_LEAVE,
                guild_id=str(member.guild.id),
                user_id=str(member.id),
                action_data={
                    "username": member.name,
                    "display_name": member.display_name,
                    "roles": [str(role.id) for role in member.roles]
                }
            )
        
        @self.event
        async def on_guild_join(guild: discord.Guild) -> None:
            """Handle joining a new guild."""
            logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
            
            # Store guild information
            await self.db_manager.store_guild_info(guild)
            
            # Store channel information
            for channel in guild.channels:
                await self.db_manager.store_channel_info(channel)
            
            # Start backfill for new guild if enabled
            if self.config.backfill_enabled:
                asyncio.create_task(self._start_backfill_guild(guild))
        
        @self.event
        async def on_guild_remove(guild: discord.Guild) -> None:
            """Handle leaving a guild."""
            logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
            
            # Cancel any ongoing backfill for this guild
            if str(guild.id) in self.backfill_tasks:
                self.backfill_tasks[str(guild.id)].cancel()
                del self.backfill_tasks[str(guild.id)]
        
        @self.event
        async def on_error(event: str, *args, **kwargs) -> None:
            """Handle Discord API errors."""
            logger.error(f"Discord error in event {event}: {args}")
            self.stats["errors"] += 1
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            asyncio.create_task(self.close())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _should_process_message(self, message: discord.Message) -> bool:
        """
        Check if a message should be processed.
        
        Args:
            message: Discord message to check
            
        Returns:
            True if message should be processed, False otherwise
        """
        # Skip if message is None
        if not message:
            return False
        
        # Skip if message ID already processed
        if str(message.id) in self.processed_messages:
            return False
        
        # Check if we should process bot messages
        if message.author.bot and not self.config.process_bot_messages:
            return False
        
        # Check if we should process system messages
        if message.author.system and not self.config.process_system_messages:
            return False
        
        # Check if we should process DM messages
        if not message.guild and not self.config.process_dm_messages:
            return False
        
        # Check guild filtering
        if message.guild and not self.config.should_process_guild(str(message.guild.id)):
            return False
        
        # Check channel filtering
        if not self.config.should_process_channel(str(message.channel.id)):
            return False
        
        return True
    
    async def _queue_message(self, message: discord.Message) -> None:
        """
        Add a message to the processing queue.
        
        Args:
            message: Discord message to queue
        """
        self.message_queue.append(message)
        self.processed_messages.add(str(message.id))
        
        # Process immediately if queue is full
        if len(self.message_queue) >= self.config.batch_size:
            await self._process_message_queue()
    
    async def _queue_action(
        self,
        action_type: ActionType,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        target_id: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an action to the processing queue.
        
        Args:
            action_type: Type of action
            guild_id: Guild ID where action occurred
            channel_id: Channel ID where action occurred
            user_id: User ID who performed the action
            target_id: ID of the target object
            action_data: Additional action data
            before_data: State before the action
            after_data: State after the action
        """
        action = {
            "action_type": action_type,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "user_id": user_id,
            "target_id": target_id,
            "action_data": action_data,
            "before_data": before_data,
            "after_data": after_data
        }
        
        self.action_queue.append(action)
        
        # Process immediately if queue is full
        if len(self.action_queue) >= self.config.batch_size:
            await self._process_action_queue()
    
    @tasks.loop(seconds=30)
    async def process_queues(self) -> None:
        """Process message and action queues periodically."""
        try:
            await self._process_message_queue()
            await self._process_action_queue()
        except Exception as e:
            logger.error(f"Error processing queues: {e}")
            self.stats["errors"] += 1
    
    async def _process_message_queue(self) -> None:
        """Process all messages in the queue."""
        if not self.message_queue:
            return
        
        # Get messages from queue
        messages = []
        while self.message_queue and len(messages) < self.config.batch_size:
            messages.append(self.message_queue.popleft())
        
        if not messages:
            return
        
        try:
            # Store messages in batch
            stored_count = await self.db_manager.store_messages_batch(messages)
            self.stats["messages_processed"] += stored_count
            
            # Update checkpoints
            for message in messages:
                await self.db_manager.update_checkpoint(
                    "message",
                    last_processed_id=str(message.id),
                    last_processed_timestamp=message.created_at,
                    guild_id=str(message.guild.id) if message.guild else None,
                    channel_id=str(message.channel.id)
                )
            
            logger.debug(f"Processed {stored_count} messages from queue")
            
        except Exception as e:
            logger.error(f"Failed to process message queue: {e}")
            self.stats["errors"] += 1
    
    async def _process_action_queue(self) -> None:
        """Process all actions in the queue."""
        if not self.action_queue:
            return
        
        # Process actions one by one (they're smaller than messages)
        actions_processed = 0
        while self.action_queue:
            action = self.action_queue.popleft()
            
            try:
                success = await self.db_manager.store_action(**action)
                if success:
                    actions_processed += 1
                    
            except Exception as e:
                logger.error(f"Failed to store action: {e}")
                self.stats["errors"] += 1
        
        if actions_processed > 0:
            self.stats["actions_processed"] += actions_processed
            logger.debug(f"Processed {actions_processed} actions from queue")
    
    async def _store_guild_info(self) -> None:
        """Store information about all guilds and channels."""
        for guild in self.guilds:
            try:
                # Store guild info
                await self.db_manager.store_guild_info(guild)
                
                # Store channel info
                for channel in guild.channels:
                    await self.db_manager.store_channel_info(channel)
                    
            except Exception as e:
                logger.error(f"Failed to store info for guild {guild.name}: {e}")
    
    async def _start_backfill_all_guilds(self) -> None:
        """Start backfill process for all guilds."""
        for guild in self.guilds:
            if self.config.should_process_guild(str(guild.id)):
                task = asyncio.create_task(self._start_backfill_guild(guild))
                self.backfill_tasks[str(guild.id)] = task
    
    async def _start_backfill_guild(self, guild: discord.Guild) -> None:
        """
        Start backfill process for a specific guild.
        
        Args:
            guild: Discord guild to backfill
        """
        guild_id = str(guild.id)
        
        if guild_id in self.backfill_in_progress and self.backfill_in_progress[guild_id]:
            logger.warning(f"Backfill already in progress for guild {guild.name}")
            return
        
        self.backfill_in_progress[guild_id] = True
        
        try:
            # Mark backfill as starting
            await self.db_manager.update_checkpoint(
                "backfill",
                guild_id=guild_id,
                backfill_in_progress=True
            )
            
            logger.info(f"Starting backfill for guild {guild.name} ({guild_id})")
            
            # Backfill each channel
            for channel in guild.text_channels:
                if self.config.should_process_channel(str(channel.id)):
                    await self._backfill_channel(channel)
            
            # Mark backfill as completed
            await self.db_manager.update_checkpoint(
                "backfill",
                guild_id=guild_id,
                backfill_in_progress=False,
                last_processed_timestamp=datetime.now(timezone.utc)
            )
            
            logger.info(f"Completed backfill for guild {guild.name}")
            
        except Exception as e:
            logger.error(f"Backfill failed for guild {guild.name}: {e}")
            
        finally:
            self.backfill_in_progress[guild_id] = False
            if guild_id in self.backfill_tasks:
                del self.backfill_tasks[guild_id]
    
    async def _backfill_channel(self, channel: discord.TextChannel) -> None:
        """
        Backfill messages from a specific channel.
        
        Args:
            channel: Discord text channel to backfill
        """
        channel_id = str(channel.id)
        guild_id = str(channel.guild.id) if channel.guild else None
        
        logger.info(f"Starting backfill for channel #{channel.name} ({channel_id})")
        
        try:
            # Get the last processed message ID from database
            last_message_id = await self.db_manager.get_last_message_id(channel_id, guild_id)
            
            # Determine cutoff date for backfill
            cutoff_date = None
            if self.config.backfill_max_age_days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.backfill_max_age_days)
            
            # Backfill messages
            total_processed = 0
            
            # Start from the last processed message or from the beginning
            after = discord.Object(id=int(last_message_id)) if last_message_id else None
            
            async for message in channel.history(
                limit=None,
                after=after,
                oldest_first=True
            ):
                # Check cutoff date
                if cutoff_date and message.created_at < cutoff_date:
                    continue
                
                # Skip if we've already processed this message
                if str(message.id) in self.processed_messages:
                    continue
                
                # Check if we should process this message
                if not await self._should_process_message(message):
                    continue
                
                # Store message as backfilled
                try:
                    success = await self.db_manager.store_message(message, is_backfilled=True)
                    if success:
                        total_processed += 1
                        self.processed_messages.add(str(message.id))
                        
                        # Update checkpoint periodically
                        if total_processed % self.config.backfill_chunk_size == 0:
                            await self.db_manager.update_checkpoint(
                                "backfill",
                                last_processed_id=str(message.id),
                                last_processed_timestamp=message.created_at,
                                guild_id=guild_id,
                                channel_id=channel_id,
                                total_processed=total_processed
                            )
                            
                            # Delay to avoid rate limiting
                            await asyncio.sleep(self.config.backfill_delay_seconds)
                            
                except Exception as e:
                    logger.error(f"Failed to store backfilled message {message.id}: {e}")
            
            logger.info(f"Backfilled {total_processed} messages from #{channel.name}")
            
        except Exception as e:
            logger.error(f"Error during backfill of channel #{channel.name}: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get bot statistics.
        
        Returns:
            Dictionary containing bot statistics
        """
        uptime = datetime.now(timezone.utc) - self.stats["start_time"]
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "messages_processed": self.stats["messages_processed"],
            "actions_processed": self.stats["actions_processed"],
            "errors": self.stats["errors"],
            "guilds": len(self.guilds),
            "queue_sizes": {
                "messages": len(self.message_queue),
                "actions": len(self.action_queue)
            },
            "backfill_status": {
                guild_id: status for guild_id, status in self.backfill_in_progress.items()
            }
        }
    
    async def close(self) -> None:
        """Close the bot and cleanup resources."""
        logger.info("Shutting down bot...")
        
        # Cancel all backfill tasks
        for task in self.backfill_tasks.values():
            task.cancel()
        
        # Process remaining queues
        try:
            await self._process_message_queue()
            await self._process_action_queue()
        except Exception as e:
            logger.error(f"Error processing final queues: {e}")
        
        # Stop background tasks
        if hasattr(self, 'process_queues'):
            self.process_queues.cancel()
        
        # Close database connection
        if self.db_manager:
            await self.db_manager.close()
        
        # Close Discord connection
        await super().close()
        
        logger.info("Bot shutdown complete")


async def main() -> None:
    """Main entry point for the bot."""
    try:
        config = get_config()
        bot = DiscordLogger(config)
        
        logger.info("Starting Discord Logger Bot...")
        await bot.start(config.discord_token)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 