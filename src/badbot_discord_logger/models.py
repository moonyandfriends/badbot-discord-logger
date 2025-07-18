"""
Database models for Discord message and action logging.

This module defines Pydantic models that represent the structure of data
stored in the Supabase database for Discord messages, actions, and processing checkpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ActionType(str, Enum):
    """Enumeration of Discord action types that can be logged."""
    
    MESSAGE_DELETE = "message_delete"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_BULK_DELETE = "message_bulk_delete"
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"
    MEMBER_UPDATE = "member_update"
    MEMBER_BAN = "member_ban"
    MEMBER_UNBAN = "member_unban"
    CHANNEL_CREATE = "channel_create"
    CHANNEL_DELETE = "channel_delete"
    CHANNEL_UPDATE = "channel_update"
    ROLE_CREATE = "role_create"
    ROLE_DELETE = "role_delete"
    ROLE_UPDATE = "role_update"
    GUILD_UPDATE = "guild_update"
    VOICE_STATE_UPDATE = "voice_state_update"
    INVITE_CREATE = "invite_create"
    INVITE_DELETE = "invite_delete"
    THREAD_CREATE = "thread_create"
    THREAD_DELETE = "thread_delete"
    THREAD_UPDATE = "thread_update"
    EMOJI_CREATE = "emoji_create"
    EMOJI_DELETE = "emoji_delete"
    EMOJI_UPDATE = "emoji_update"
    WEBHOOK_CREATE = "webhook_create"
    WEBHOOK_UPDATE = "webhook_update"
    WEBHOOK_DELETE = "webhook_delete"


class MessageType(str, Enum):
    """Enumeration of Discord message types."""
    
    DEFAULT = "default"
    RECIPIENT_ADD = "recipient_add"
    RECIPIENT_REMOVE = "recipient_remove"
    CALL = "call"
    CHANNEL_NAME_CHANGE = "channel_name_change"
    CHANNEL_ICON_CHANGE = "channel_icon_change"
    PINS_ADD = "pins_add"
    NEW_MEMBER = "new_member"
    PREMIUM_GUILD_SUBSCRIPTION = "premium_guild_subscription"
    PREMIUM_GUILD_TIER_1 = "premium_guild_tier_1"
    PREMIUM_GUILD_TIER_2 = "premium_guild_tier_2"
    PREMIUM_GUILD_TIER_3 = "premium_guild_tier_3"
    CHANNEL_FOLLOW_ADD = "channel_follow_add"
    GUILD_DISCOVERY_DISQUALIFIED = "guild_discovery_disqualified"
    GUILD_DISCOVERY_REQUALIFIED = "guild_discovery_requalified"
    GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING = "guild_discovery_grace_period_initial_warning"
    GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING = "guild_discovery_grace_period_final_warning"
    THREAD_CREATED = "thread_created"
    REPLY = "reply"
    CHAT_INPUT_COMMAND = "chat_input_command"
    THREAD_STARTER_MESSAGE = "thread_starter_message"
    GUILD_INVITE_REMINDER = "guild_invite_reminder"
    CONTEXT_MENU_COMMAND = "context_menu_command"
    AUTO_MODERATION_ACTION = "auto_moderation_action"


class AttachmentModel(BaseModel):
    """Model for Discord message attachments."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    attachment_id: str = Field(..., description="Discord attachment ID")
    filename: str = Field(..., description="Original filename")
    content_type: Optional[str] = Field(None, description="MIME content type")
    size: int = Field(..., description="File size in bytes")
    url: str = Field(..., description="Discord CDN URL")
    proxy_url: str = Field(..., description="Proxied CDN URL")
    height: Optional[int] = Field(None, description="Image height if applicable")
    width: Optional[int] = Field(None, description="Image width if applicable")


class EmbedModel(BaseModel):
    """Model for Discord message embeds."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    title: Optional[str] = Field(None, description="Embed title")
    description: Optional[str] = Field(None, description="Embed description")
    url: Optional[str] = Field(None, description="Embed URL")
    color: Optional[int] = Field(None, description="Embed color as integer")
    timestamp: Optional[datetime] = Field(None, description="Embed timestamp")
    footer: Optional[Dict[str, Any]] = Field(None, description="Embed footer data")
    image: Optional[Dict[str, Any]] = Field(None, description="Embed image data")
    thumbnail: Optional[Dict[str, Any]] = Field(None, description="Embed thumbnail data")
    video: Optional[Dict[str, Any]] = Field(None, description="Embed video data")
    provider: Optional[Dict[str, Any]] = Field(None, description="Embed provider data")
    author: Optional[Dict[str, Any]] = Field(None, description="Embed author data")
    fields: List[Dict[str, Any]] = Field(default_factory=list, description="Embed fields")


class MessageModel(BaseModel):
    """Model for Discord messages stored in Supabase."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Primary identifiers
    message_id: str = Field(..., description="Discord message ID")
    channel_id: str = Field(..., description="Discord channel ID")
    guild_id: Optional[str] = Field(None, description="Discord guild ID (None for DMs)")
    
    # Message content
    content: Optional[str] = Field(None, description="Message text content")
    message_type: MessageType = Field(MessageType.DEFAULT, description="Type of message")
    
    # Author information
    author_id: str = Field(..., description="Discord user ID of message author")
    author_username: str = Field(..., description="Username of message author")
    author_display_name: Optional[str] = Field(None, description="Display name of message author")
    author_discriminator: Optional[str] = Field(None, description="Author discriminator (legacy)")
    author_avatar_url: Optional[str] = Field(None, description="Author avatar URL")
    author_is_bot: bool = Field(False, description="Whether author is a bot")
    author_is_system: bool = Field(False, description="Whether author is system")
    
    # Message metadata
    created_at: datetime = Field(..., description="When message was created")
    edited_at: Optional[datetime] = Field(None, description="When message was last edited")
    pinned: bool = Field(False, description="Whether message is pinned")
    mention_everyone: bool = Field(False, description="Whether message mentions everyone")
    tts: bool = Field(False, description="Whether message is text-to-speech")
    
    # Rich content
    attachments: List[AttachmentModel] = Field(default_factory=list, description="Message attachments")
    embeds: List[EmbedModel] = Field(default_factory=list, description="Message embeds")
    mentions: List[str] = Field(default_factory=list, description="User IDs mentioned in message")
    mention_roles: List[str] = Field(default_factory=list, description="Role IDs mentioned in message")
    mention_channels: List[str] = Field(default_factory=list, description="Channel IDs mentioned in message")
    
    # Thread information
    thread_id: Optional[str] = Field(None, description="Thread ID if message is in thread")
    
    # Reference information (for replies)
    reference_message_id: Optional[str] = Field(None, description="Referenced message ID for replies")
    
    # Application/interaction info
    application_id: Optional[str] = Field(None, description="Application ID for slash commands")
    interaction_type: Optional[str] = Field(None, description="Type of interaction")
    
    # Webhook information
    webhook_id: Optional[str] = Field(None, description="Webhook ID if message was sent by a webhook")
    
    # Metadata
    logged_at: datetime = Field(default_factory=datetime.utcnow, description="When message was logged to database")
    is_backfilled: bool = Field(False, description="Whether this message was backfilled")


class ActionModel(BaseModel):
    """Model for Discord actions/events stored in Supabase."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Primary identifiers
    action_id: str = Field(..., description="Unique action ID (UUID)")
    action_type: ActionType = Field(..., description="Type of action/event")
    guild_id: Optional[str] = Field(None, description="Discord guild ID")
    channel_id: Optional[str] = Field(None, description="Discord channel ID if applicable")
    
    # Actor information
    user_id: Optional[str] = Field(None, description="User ID who performed the action")
    username: Optional[str] = Field(None, description="Username of action performer")
    display_name: Optional[str] = Field(None, description="Display name of action performer")
    
    # Target information
    target_id: Optional[str] = Field(None, description="ID of target object (user, channel, role, etc.)")
    target_type: Optional[str] = Field(None, description="Type of target object")
    target_name: Optional[str] = Field(None, description="Name of target object")
    
    # Action details
    action_data: Dict[str, Any] = Field(default_factory=dict, description="Additional action data")
    before_data: Optional[Dict[str, Any]] = Field(None, description="State before action")
    after_data: Optional[Dict[str, Any]] = Field(None, description="State after action")
    
    # Metadata
    occurred_at: datetime = Field(..., description="When the action occurred")
    logged_at: datetime = Field(default_factory=datetime.utcnow, description="When action was logged to database")
    is_backfilled: bool = Field(False, description="Whether this action was backfilled")


class CheckpointModel(BaseModel):
    """Model for tracking processing checkpoints."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Identifiers
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    guild_id: Optional[str] = Field(None, description="Guild ID (None for global checkpoints)")
    channel_id: Optional[str] = Field(None, description="Channel ID (None for guild-wide checkpoints)")
    
    # Checkpoint data
    checkpoint_type: str = Field(..., description="Type of checkpoint (message, action, etc.)")
    last_processed_id: Optional[str] = Field(None, description="Last processed item ID")
    last_processed_timestamp: Optional[datetime] = Field(None, description="Last processed timestamp")
    
    # Processing statistics
    total_processed: int = Field(0, description="Total items processed")
    last_backfill_completed: Optional[datetime] = Field(None, description="When last backfill completed")
    backfill_in_progress: bool = Field(False, description="Whether backfill is currently running")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When checkpoint was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When checkpoint was last updated")


class GuildInfoModel(BaseModel):
    """Model for Discord guild information."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    guild_id: str = Field(..., description="Discord guild ID")
    name: str = Field(..., description="Guild name")
    description: Optional[str] = Field(None, description="Guild description")
    owner_id: str = Field(..., description="Guild owner user ID")
    member_count: int = Field(0, description="Number of members")
    created_at: datetime = Field(..., description="When guild was created")
    icon_url: Optional[str] = Field(None, description="Guild icon URL")
    banner_url: Optional[str] = Field(None, description="Guild banner URL")
    
    # Metadata
    first_seen: datetime = Field(default_factory=datetime.utcnow, description="When bot first joined guild")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When guild info was last updated")


class ChannelInfoModel(BaseModel):
    """Model for Discord channel information."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    channel_id: str = Field(..., description="Discord channel ID")
    guild_id: Optional[str] = Field(None, description="Discord guild ID (None for DMs)")
    name: str = Field(..., description="Channel name")
    channel_type: str = Field(..., description="Type of channel")
    topic: Optional[str] = Field(None, description="Channel topic")
    position: Optional[int] = Field(None, description="Channel position")
    category_id: Optional[str] = Field(None, description="Parent category ID")
    
    # Metadata
    first_seen: datetime = Field(default_factory=datetime.utcnow, description="When bot first saw channel")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When channel info was last updated") 