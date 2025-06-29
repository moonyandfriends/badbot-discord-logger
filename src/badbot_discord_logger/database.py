"""
Database operations for Discord message and action logging.

This module provides a comprehensive interface for interacting with the Supabase database,
handling message storage, action logging, and checkpoint management with proper error handling
and retry logic.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
import json

import discord
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncpg

try:
    from loguru import logger
except ImportError:
    # Fallback logging if loguru not available
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

from .config import Config
from .models import (
    MessageModel, ActionModel, CheckpointModel, 
    GuildInfoModel, ChannelInfoModel, ActionType, MessageType
)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class RetryableError(DatabaseError):
    """Exception for errors that should trigger a retry."""
    pass


class NonRetryableError(DatabaseError):
    """Exception for errors that should not trigger a retry."""
    pass


class ConnectionError(DatabaseError):
    """Exception for connection-related errors."""
    pass


class SupabaseManager:
    """
    Manages all interactions with the Supabase database.
    
    Provides methods for storing messages, actions, checkpoints, and managing
    guild/channel information with proper error handling and retry logic.
    """
    
    def __init__(self, config: Config) -> None:
        """
        Initialize the Supabase manager.
        
        Args:
            config: Configuration object containing Supabase credentials
        """
        self.config = config
        self.client: Optional[Client] = None
        self.table_names = config.get_database_table_names()
        self._connection_lock = asyncio.Lock()
        self._initialized = False
        self._stats_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._last_cache_update = datetime.now(timezone.utc)
        
    async def initialize(self) -> None:
        """Initialize the Supabase client and verify connection."""
        async with self._connection_lock:
            if self._initialized and self.client is not None:
                return
                
            try:
                self.client = create_client(
                    self.config.supabase_url,
                    self.config.supabase_key
                )
                
                # Test connection by attempting to read from a table
                await self._test_connection()
                self._initialized = True
                logger.info("Successfully connected to Supabase database")
                
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                raise ConnectionError(f"Database initialization failed: {e}") from e
    
    def _ensure_client(self) -> Client:
        """Ensure client is initialized and return it."""
        if not self.client:
            raise ConnectionError("Database client not initialized. Call initialize() first.")
        return self.client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RetryableError)
    )
    async def _test_connection(self) -> None:
        """Test the database connection."""
        try:
            client = self._ensure_client()
            
            # Try to query the checkpoints table (should exist)
            result = client.table(self.table_names["checkpoints"]).select("*").limit(1).execute()
            logger.debug("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            # Determine if error is retryable
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise RetryableError(f"Connection test failed: {e}") from e
            else:
                raise NonRetryableError(f"Connection test failed: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RetryableError)
    )
    async def _execute_with_retry(
        self, 
        operation: Callable[..., Any], 
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a database operation with retry logic.
        
        Args:
            operation: The database operation to execute
            operation_name: Name of the operation for logging
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation
            
        Returns:
            The result of the operation
            
        Raises:
            DatabaseError: If the operation fails after all retries
        """
        try:
            if not self.client:
                await self.initialize()
                
            client = self._ensure_client()
            logger.debug(f"Executing {operation_name}")
            result = operation(client, *args, **kwargs)
            
            if hasattr(result, 'execute'):
                result = result.execute()
                
            logger.debug(f"Successfully executed {operation_name}")
            return result
            
        except Exception as e:
            logger.warning(f"{operation_name} failed: {e}")
            
            # Determine if this is a retryable error
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["connection", "timeout", "network", "503", "502", "500"]):
                raise RetryableError(f"Retryable error in {operation_name}: {e}") from e
            else:
                raise NonRetryableError(f"Non-retryable error in {operation_name}: {e}") from e
    
    async def store_message(self, message: discord.Message, is_backfilled: bool = False) -> bool:
        """
        Store a Discord message in the database.
        
        Args:
            message: The Discord message to store
            is_backfilled: Whether this message is from backfill operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            message_model = self._convert_discord_message(message, is_backfilled)
            message_dict = self._message_model_to_dict(message_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["messages"]).upsert(
                    message_dict,
                    on_conflict="message_id"
                )
            
            await self._execute_with_retry(
                operation, 
                f"store_message_{message.id}"
            )
            
            logger.debug(f"Stored message {message.id} from {message.author}")
            return True
            
        except NonRetryableError as e:
            logger.error(f"Non-retryable error storing message {message.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to store message {message.id}: {e}")
            return False
    
    async def store_messages_batch(
        self, 
        messages: List[discord.Message], 
        is_backfilled: bool = False
    ) -> int:
        """
        Store multiple messages in a single batch operation.
        
        Args:
            messages: List of Discord messages to store
            is_backfilled: Whether these messages are from backfill operation
            
        Returns:
            Number of successfully stored messages
        """
        if not messages:
            return 0
        
        try:
            message_dicts = []
            for msg in messages:
                try:
                    model = self._convert_discord_message(msg, is_backfilled)
                    message_dict = self._message_model_to_dict(model)
                    message_dicts.append(message_dict)
                except Exception as e:
                    logger.warning(f"Failed to convert message {msg.id}: {e}")
                    continue
            
            if not message_dicts:
                return 0
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["messages"]).upsert(
                    message_dicts,
                    on_conflict="message_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_messages_batch_{len(message_dicts)}"
            )
            
            logger.info(f"Stored batch of {len(message_dicts)} messages")
            return len(message_dicts)
            
        except Exception as e:
            logger.error(f"Failed to store message batch: {e}")
            return 0
    
    async def store_action(
        self, 
        action_type: ActionType, 
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        is_backfilled: bool = False
    ) -> bool:
        """
        Store a Discord action/event in the database.
        
        Args:
            action_type: Type of action being logged
            guild_id: Guild ID where action occurred
            channel_id: Channel ID where action occurred
            user_id: User ID who performed the action
            username: Username of action performer
            display_name: Display name of action performer
            target_id: ID of the target object
            target_type: Type of target object
            target_name: Name of target object
            action_data: Additional action data
            before_data: State before the action
            after_data: State after the action
            is_backfilled: Whether this action is from backfill operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            action_model = ActionModel(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                username=username,
                display_name=display_name,
                target_id=target_id,
                target_type=target_type,
                target_name=target_name,
                action_data=action_data or {},
                before_data=before_data,
                after_data=after_data,
                occurred_at=datetime.now(timezone.utc),
                is_backfilled=is_backfilled
            )
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["actions"]).insert(
                    action_model.model_dump()
                )
            
            await self._execute_with_retry(
                operation,
                f"store_action_{action_type.value}"
            )
            
            logger.debug(f"Stored action {action_type.value} for guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store action {action_type.value}: {e}")
            return False
    
    async def get_checkpoint(
        self, 
        checkpoint_type: str, 
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None
    ) -> Optional[CheckpointModel]:
        """
        Retrieve a checkpoint from the database.
        
        Args:
            checkpoint_type: Type of checkpoint to retrieve
            guild_id: Guild ID for the checkpoint
            channel_id: Channel ID for the checkpoint
            
        Returns:
            CheckpointModel if found, None otherwise
        """
        try:
            def operation(client: Client) -> Any:
                query = client.table(self.table_names["checkpoints"]).select("*")
                
                # Build query conditions
                query = query.eq("checkpoint_type", checkpoint_type)
                
                if guild_id is not None:
                    query = query.eq("guild_id", guild_id)
                else:
                    query = query.is_("guild_id", "null")
                    
                if channel_id is not None:
                    query = query.eq("channel_id", channel_id)
                else:
                    query = query.is_("channel_id", "null")
                
                return query.limit(1)
            
            result = await self._execute_with_retry(
                operation,
                f"get_checkpoint_{checkpoint_type}"
            )
            
            if result.data:
                return CheckpointModel(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint {checkpoint_type}: {e}")
            return None
    
    async def update_checkpoint(
        self,
        checkpoint_type: str,
        last_processed_id: Optional[str] = None,
        last_processed_timestamp: Optional[datetime] = None,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        total_processed: Optional[int] = None,
        backfill_in_progress: Optional[bool] = None
    ) -> bool:
        """
        Update or create a checkpoint in the database.
        
        Args:
            checkpoint_type: Type of checkpoint
            last_processed_id: ID of last processed item
            last_processed_timestamp: Timestamp of last processed item
            guild_id: Guild ID for the checkpoint
            channel_id: Channel ID for the checkpoint
            total_processed: Total number of items processed
            backfill_in_progress: Whether backfill is in progress
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate checkpoint ID
            checkpoint_id = f"{checkpoint_type}_{guild_id or 'global'}_{channel_id or 'all'}"
            
            # Check if checkpoint exists
            existing = await self.get_checkpoint(checkpoint_type, guild_id, channel_id)
            
            if existing:
                # Update existing checkpoint
                update_data: Dict[str, Union[str, int, bool]] = {
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                if last_processed_id is not None:
                    update_data["last_processed_id"] = last_processed_id
                if last_processed_timestamp is not None:
                    update_data["last_processed_timestamp"] = last_processed_timestamp.isoformat()
                if total_processed is not None:
                    update_data["total_processed"] = total_processed
                if backfill_in_progress is not None:
                    update_data["backfill_in_progress"] = backfill_in_progress
                
                def operation(client: Client) -> Any:
                    query = client.table(self.table_names["checkpoints"]).update(update_data)
                    return query.eq("checkpoint_id", existing.checkpoint_id)
                
            else:
                # Create new checkpoint
                checkpoint_model = CheckpointModel(
                    checkpoint_id=checkpoint_id,
                    checkpoint_type=checkpoint_type,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    last_processed_id=last_processed_id,
                    last_processed_timestamp=last_processed_timestamp,
                    total_processed=total_processed or 0,
                    last_backfill_completed=None,  # Set explicitly
                    backfill_in_progress=backfill_in_progress or False
                )
                
                checkpoint_dict = self._checkpoint_model_to_dict(checkpoint_model)
                
                def operation(client: Client) -> Any:
                    return client.table(self.table_names["checkpoints"]).upsert(
                        checkpoint_dict,
                        on_conflict="checkpoint_id"
                    )
            
            await self._execute_with_retry(
                operation,
                f"update_checkpoint_{checkpoint_type}"
            )
            
            logger.debug(f"Updated checkpoint {checkpoint_type} for guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update checkpoint {checkpoint_type}: {e}")
            return False
    
    async def get_last_message_id(
        self, 
        channel_id: str, 
        guild_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the ID of the last processed message in a channel.
        
        Args:
            channel_id: Channel ID to check
            guild_id: Guild ID for the channel
            
        Returns:
            Message ID if found, None otherwise
        """
        try:
            def operation(client: Client) -> Any:
                query = client.table(self.table_names["messages"]).select("message_id")
                query = query.eq("channel_id", channel_id)
                
                if guild_id:
                    query = query.eq("guild_id", guild_id)
                
                return query.order("created_at", desc=True).limit(1)
            
            result = await self._execute_with_retry(
                operation,
                f"get_last_message_id_{channel_id}"
            )
            
            if result.data:
                return result.data[0]["message_id"]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get last message ID for channel {channel_id}: {e}")
            return None
    
    async def store_guild_info(self, guild: discord.Guild) -> bool:
        """
        Store or update guild information.
        
        Args:
            guild: Discord guild object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            guild_model = GuildInfoModel(
                guild_id=str(guild.id),
                name=guild.name,
                description=guild.description,
                owner_id=str(guild.owner_id) if guild.owner_id else "0",
                member_count=guild.member_count or 0,
                created_at=guild.created_at,
                icon_url=str(guild.icon.url) if guild.icon else None,
                banner_url=str(guild.banner.url) if guild.banner else None
            )
            
            guild_dict = self._guild_info_model_to_dict(guild_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["guilds"]).upsert(
                    guild_dict,
                    on_conflict="guild_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_guild_info_{guild.id}"
            )
            
            logger.debug(f"Stored guild info for {guild.name} ({guild.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store guild info for {guild.id}: {e}")
            return False
    
    async def store_channel_info(self, channel: discord.abc.GuildChannel) -> bool:
        """
        Store or update channel information.
        
        Args:
            channel: Discord channel object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            channel_model = ChannelInfoModel(
                channel_id=str(channel.id),
                guild_id=str(channel.guild.id) if hasattr(channel, 'guild') and channel.guild else None,
                name=channel.name,
                channel_type=str(channel.type),
                topic=getattr(channel, 'topic', None),
                position=getattr(channel, 'position', None),
                category_id=str(channel.category.id) if getattr(channel, 'category', None) and channel.category else None
            )
            
            channel_dict = self._channel_info_model_to_dict(channel_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["channels"]).upsert(
                    channel_dict,
                    on_conflict="channel_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_channel_info_{channel.id}"
            )
            
            logger.debug(f"Stored channel info for {channel.name} ({channel.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store channel info for {channel.id}: {e}")
            return False
    
    def _convert_discord_message(self, message: discord.Message, is_backfilled: bool = False) -> MessageModel:
        """
        Convert a Discord message to a MessageModel for database storage.
        
        Args:
            message: Discord message object
            is_backfilled: Whether this message is being backfilled
            
        Returns:
            MessageModel instance ready for database storage
        """
        # Handle attachments
        attachments = []
        for attachment in message.attachments:
            attachment_dict = {
                "attachment_id": str(attachment.id),
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size": attachment.size,
                "url": attachment.url,
                "proxy_url": attachment.proxy_url,
                "height": attachment.height,
                "width": attachment.width
            }
            attachments.append(attachment_dict)
        
        # Handle embeds
        embeds = []
        for embed in message.embeds:
            try:
                # Safely convert embed attributes to dictionaries
                embed_dict = {
                    "title": embed.title,
                    "description": embed.description,
                    "url": embed.url,
                    "color": embed.color.value if embed.color else None,
                    "timestamp": embed.timestamp.isoformat() if embed.timestamp else None,
                    "footer": self._safe_convert_embed_attr(embed.footer),
                    "image": self._safe_convert_embed_attr(embed.image),
                    "thumbnail": self._safe_convert_embed_attr(embed.thumbnail),
                    "video": self._safe_convert_embed_attr(embed.video),
                    "provider": self._safe_convert_embed_attr(embed.provider),
                    "author": self._safe_convert_embed_attr(embed.author),
                    "fields": [self._safe_convert_embed_attr(field) for field in embed.fields]
                }
                embeds.append(embed_dict)
            except Exception as e:
                logger.warning(f"Failed to convert embed: {e}")
                continue
        
        # Convert message type string to MessageType enum
        message_type_str = str(message.type).split('.')[-1].lower()
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            # Fallback to default if unknown message type
            message_type = MessageType.DEFAULT
        
        return MessageModel(
            message_id=str(message.id),
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id) if message.guild else None,
            content=message.content or "",  # Ensure content is never None
            message_type=message_type,
            author_id=str(message.author.id),
            author_username=message.author.name,
            author_display_name=message.author.display_name,
            author_discriminator=message.author.discriminator if hasattr(message.author, 'discriminator') else None,
            author_avatar_url=str(message.author.avatar.url) if message.author.avatar else None,
            author_is_bot=message.author.bot,
            author_is_system=message.author.system,
            created_at=message.created_at,
            edited_at=message.edited_at,
            pinned=message.pinned,
            mention_everyone=message.mention_everyone,
            tts=message.tts,
            attachments=attachments,
            embeds=embeds,
            mentions=[str(user.id) for user in message.mentions],
            mention_roles=[str(role.id) for role in message.role_mentions],
            mention_channels=[str(channel.id) for channel in message.channel_mentions],
            thread_id=str(message.channel.id) if hasattr(message.channel, 'parent') and getattr(message.channel, 'parent', None) else None,
            reference_message_id=str(message.reference.message_id) if message.reference else None,
            application_id=str(getattr(message, 'application_id', None)) if hasattr(message, 'application_id') else None,
            interaction_type=str(message.interaction.type) if message.interaction else None,
            is_backfilled=is_backfilled
        )
    
    def _safe_convert_embed_attr(self, attr) -> Optional[Dict[str, Any]]:
        """
        Safely convert an embed attribute to a dictionary.
        
        Args:
            attr: The embed attribute to convert
            
        Returns:
            Dictionary representation of the attribute or None if conversion fails
        """
        if attr is None:
            return None
        
        try:
            # Check if the attribute has a to_dict method
            if hasattr(attr, 'to_dict') and callable(attr.to_dict):
                return attr.to_dict()
            
            # Check if it's already a dict-like object
            if hasattr(attr, '__dict__'):
                return {k: v for k, v in attr.__dict__.items() if not k.startswith('_')}
            
            # Try to convert using dict() if it's a mapping
            if hasattr(attr, 'items'):
                return dict(attr)
            
            # If it's a simple object, try to get its attributes
            if hasattr(attr, '__slots__'):
                return {slot: getattr(attr, slot, None) for slot in attr.__slots__}
            
            # Fallback: return None if we can't convert it
            return None
            
        except Exception:
            return None
    
    @lru_cache(maxsize=128)
    def _get_cached_stats_key(self, stat_type: str) -> str:
        """Generate cache key for statistics."""
        return f"stats_{stat_type}_{int(datetime.now(timezone.utc).timestamp() // self._cache_ttl)}"
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics with caching.
        
        Returns:
            Dictionary containing database statistics
        """
        try:
            # Check cache validity
            now = datetime.now(timezone.utc)
            if (now - self._last_cache_update).total_seconds() < self._cache_ttl and self._stats_cache:
                return self._stats_cache
            
            stats = {}
            
            # Get message count
            def get_message_count(client: Client) -> Any:
                return client.table(self.table_names["messages"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_message_count,
                "get_message_count"
            )
            stats["total_messages"] = result.count
            
            # Get action count
            def get_action_count(client: Client) -> Any:
                return client.table(self.table_names["actions"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_action_count,
                "get_action_count"
            )
            stats["total_actions"] = result.count
            
            # Get guild count
            def get_guild_count(client: Client) -> Any:
                return client.table(self.table_names["guilds"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_guild_count,
                "get_guild_count"
            )
            stats["total_guilds"] = result.count
            
            # Update cache
            self._stats_cache = stats
            self._last_cache_update = now
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return self._stats_cache if self._stats_cache else {}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database.
        
        Returns:
            Dictionary containing health check results
        """
        health_status = {
            "database_connected": False,
            "tables_accessible": False,
            "last_message_timestamp": None,
            "error": None
        }
        
        try:
            # Test basic connection
            await self._test_connection()
            health_status["database_connected"] = True
            
            # Test table access
            def test_tables(client: Client) -> Any:
                return client.table(self.table_names["messages"]).select("created_at").order("created_at", desc=True).limit(1)
            
            result = await self._execute_with_retry(test_tables, "health_check_tables")
            health_status["tables_accessible"] = True
            
            if result.data:
                health_status["last_message_timestamp"] = result.data[0]["created_at"]
            
        except Exception as e:
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return health_status
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old data from the database.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Dictionary with cleanup results
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        cleanup_results = {"messages_deleted": 0, "actions_deleted": 0}
        
        try:
            # Cleanup old messages
            def cleanup_messages(client: Client) -> Any:
                return client.table(self.table_names["messages"]).delete().lt("created_at", cutoff_date.isoformat())
            
            result = await self._execute_with_retry(cleanup_messages, "cleanup_old_messages")
            cleanup_results["messages_deleted"] = len(result.data) if result.data else 0
            
            # Cleanup old actions
            def cleanup_actions(client: Client) -> Any:
                return client.table(self.table_names["actions"]).delete().lt("occurred_at", cutoff_date.isoformat())
            
            result = await self._execute_with_retry(cleanup_actions, "cleanup_old_actions")
            cleanup_results["actions_deleted"] = len(result.data) if result.data else 0
            
            logger.info(f"Cleaned up {cleanup_results['messages_deleted']} messages and {cleanup_results['actions_deleted']} actions")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
        
        return cleanup_results
    
    async def close(self) -> None:
        """Close the database connection."""
        if self.client:
            logger.info("Closing Supabase connection")
            # Supabase client doesn't need explicit closing
            self.client = None
            self._initialized = False
    
    def _message_model_to_dict(self, message_model: MessageModel) -> Dict[str, Any]:
        """
        Convert MessageModel to a JSON-serializable dictionary for database storage.
        
        Args:
            message_model: The MessageModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = message_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('created_at'):
            data['created_at'] = data['created_at'].isoformat()
        if data.get('edited_at'):
            data['edited_at'] = data['edited_at'].isoformat()
        if data.get('logged_at'):
            data['logged_at'] = data['logged_at'].isoformat()
        
        # Convert enum values to strings
        data['message_type'] = data['message_type'].value
        
        return data
    
    def _channel_info_model_to_dict(self, channel_model: ChannelInfoModel) -> Dict[str, Any]:
        """
        Convert ChannelInfoModel to a JSON-serializable dictionary for database storage.
        
        Args:
            channel_model: The ChannelInfoModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = channel_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('first_seen'):
            data['first_seen'] = data['first_seen'].isoformat()
        if data.get('last_updated'):
            data['last_updated'] = data['last_updated'].isoformat()
        
        return data
    
    def _guild_info_model_to_dict(self, guild_model: GuildInfoModel) -> Dict[str, Any]:
        """
        Convert GuildInfoModel to a JSON-serializable dictionary for database storage.
        
        Args:
            guild_model: The GuildInfoModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = guild_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('created_at'):
            data['created_at'] = data['created_at'].isoformat()
        if data.get('first_seen'):
            data['first_seen'] = data['first_seen'].isoformat()
        if data.get('last_updated'):
            data['last_updated'] = data['last_updated'].isoformat()
        
        return data
    
    def _checkpoint_model_to_dict(self, checkpoint_model: CheckpointModel) -> Dict[str, Any]:
        """
        Convert CheckpointModel to a JSON-serializable dictionary for database storage.
        
        Args:
            checkpoint_model: The CheckpointModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = checkpoint_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('last_processed_timestamp'):
            data['last_processed_timestamp'] = data['last_processed_timestamp'].isoformat()
        if data.get('last_backfill_completed'):
            data['last_backfill_completed'] = data['last_backfill_completed'].isoformat()
        if data.get('created_at'):
            data['created_at'] = data['created_at'].isoformat()
        if data.get('updated_at'):
            data['updated_at'] = data['updated_at'].isoformat()
        
        return data 