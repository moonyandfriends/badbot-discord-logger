"""
BadBot Discord Logger - A comprehensive Discord bot for logging messages and actions to Supabase.

This package provides a Discord bot that can:
- Log all messages and actions to a Supabase database
- Import historical messages and actions
- Track processing checkpoints
- Handle backfilling of missed data
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .bot import DiscordLogger
from .config import Config
from .models import MessageModel, ActionModel, CheckpointModel

__all__ = [
    "DiscordLogger",
    "Config", 
    "MessageModel",
    "ActionModel",
    "CheckpointModel",
] 