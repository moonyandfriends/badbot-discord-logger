"""
Unit tests for the configuration module.

This module tests the configuration loading, validation, and various settings
to ensure the bot operates correctly with different configurations.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from badbot_discord_logger.config import (
    Config, LogLevel, load_config, load_config_with_overrides, 
    get_config, reload_config, reset_config
)


class TestLogLevel:
    """Test the LogLevel enum."""
    
    def test_log_levels(self):
        """Test all log levels are available."""
        assert LogLevel.CRITICAL == "CRITICAL"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.DEBUG == "DEBUG"


class TestConfig:
    """Test the Config class and its validation."""
    
    def setup_method(self):
        """Reset configuration before each test."""
        reset_config()
    
    def test_config_with_valid_data(self):
        """Test creating config with valid data."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        config = Config(**config_data)
        
        assert config.discord_token == config_data["discord_token"]
        assert config.supabase_url == config_data["supabase_url"]
        assert config.supabase_key == config_data["supabase_key"]
        assert config.log_level == LogLevel.INFO
        assert config.backfill_enabled is True
    
    def test_discord_token_validation(self):
        """Test Discord token validation."""
        base_config = {
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        # Test valid token
        valid_config = {
            **base_config,
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        config = Config(**valid_config)
        assert config.discord_token is not None
        
        # Test invalid token (too short)
        with pytest.raises(ValidationError, match="Discord token appears to be invalid"):
            Config(**{**base_config, "discord_token": "short"})
        
        # Test empty token
        with pytest.raises(ValidationError, match="Discord token appears to be invalid"):
            Config(**{**base_config, "discord_token": ""})
    
    def test_supabase_url_validation(self):
        """Test Supabase URL validation."""
        base_config = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        # Test valid URL
        valid_config = {
            **base_config,
            "supabase_url": "https://test-project.supabase.co"
        }
        config = Config(**valid_config)
        assert config.supabase_url is not None
        
        # Test invalid URL (invalid domain)
        with pytest.raises(ValidationError, match="Supabase URL must be a valid HTTPS URL with a proper domain"):
            Config(**{**base_config, "supabase_url": "https://invalid."})
        
        # Test invalid URL (no https)
        with pytest.raises(ValidationError, match="Supabase URL must use HTTPS"):
            Config(**{**base_config, "supabase_url": "http://test-project.supabase.co"})
    
    def test_batch_size_validation(self):
        """Test batch size validation."""
        base_config = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        # Test valid batch size
        config = Config(**{**base_config, "batch_size": 50})
        assert config.batch_size == 50
        
        # Test invalid batch size (too small)
        with pytest.raises(ValidationError, match="Batch size must be between 1 and 500"):
            Config(**{**base_config, "batch_size": 0})
        
        # Test invalid batch size (too large)
        with pytest.raises(ValidationError, match="Batch size must be between 1 and 500"):
            Config(**{**base_config, "batch_size": 600})
    
    def test_port_validation(self):
        """Test port validation."""
        base_config = {
            "discord_token": "OTk9OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        # Test valid port
        config = Config(**{**base_config, "health_check_port": 8080})
        assert config.health_check_port == 8080
        
        # Test invalid port (too small)
        with pytest.raises(ValidationError, match="Port must be between 1024 and 65535"):
            Config(**{**base_config, "health_check_port": 80})
        
        # Test invalid port (too large)
        with pytest.raises(ValidationError, match="Port must be between 1024 and 65535"):
            Config(**{**base_config, "metrics_port": 70000})
    
    def test_guild_filtering_properties(self):
        """Test guild filtering properties."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "allowed_guilds": "123456789,987654321",
            "ignored_guilds": "111111111,222222222"
        }
        
        config = Config(**config_data)
        
        assert config.allowed_guilds_list == ["123456789", "987654321"]
        assert config.ignored_guilds_list == ["111111111", "222222222"]
        
        # Test empty lists
        config_empty = Config(**{
            **config_data,
            "allowed_guilds": "",
            "ignored_guilds": ""
        })
        assert config_empty.allowed_guilds_list == []
        assert config_empty.ignored_guilds_list == []
    
    def test_should_process_guild(self):
        """Test guild processing logic."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "allowed_guilds": "123456789",
            "ignored_guilds": "999999999"
        }
        
        config = Config(**config_data)
        
        # Test allowed guild
        assert config.should_process_guild("123456789") is True
        
        # Test ignored guild
        assert config.should_process_guild("999999999") is False
        
        # Test guild not in allowed list
        assert config.should_process_guild("555555555") is False
        
        # Test with no filters
        config_no_filter = Config(**{
            **config_data,
            "allowed_guilds": "",
            "ignored_guilds": ""
        })
        assert config_no_filter.should_process_guild("any_guild") is True
    
    def test_should_process_channel(self):
        """Test channel processing logic."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "allowed_channels": "123456789",
            "ignored_channels": "999999999"
        }
        
        config = Config(**config_data)
        
        # Test allowed channel
        assert config.should_process_channel("123456789") is True
        
        # Test ignored channel
        assert config.should_process_channel("999999999") is False
        
        # Test channel not in allowed list
        assert config.should_process_channel("555555555") is False
    
    def test_database_table_names(self):
        """Test database table names configuration."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        config = Config(**config_data)
        table_names = config.get_database_table_names()
        
        expected_tables = {
            "messages": "discord_messages",
            "actions": "discord_actions",
            "checkpoints": "discord_checkpoints",
            "guilds": "discord_guilds",
            "channels": "discord_channels"
        }
        
        assert table_names == expected_tables
    
    def test_is_production_property(self):
        """Test production mode detection."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        # Test production mode
        config_prod = Config(**{**config_data, "enable_debug": False, "log_level": LogLevel.INFO})
        assert config_prod.is_production is True
        
        # Test development mode
        config_dev = Config(**{**config_data, "enable_debug": True, "log_level": LogLevel.DEBUG})
        assert config_dev.is_production is False
    
    def test_create_directories(self):
        """Test directory creation."""
        config_data = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "log_file_path": "/tmp/test_logs/bot.log"
        }
        
        config = Config(**config_data)
        
        # This should not raise an exception
        config.create_directories()
        
        # Check that directory was created
        assert Path("/tmp/test_logs").exists()


class TestConfigLoading:
    """Test configuration loading functions."""
    
    def setup_method(self):
        """Reset configuration before each test."""
        reset_config()
    
    @patch.dict(os.environ, {
        "logger_discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "supabase_url": "https://test-project.supabase.co",
        "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    })
    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        config = load_config()
        
        assert config.discord_token == "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        assert config.supabase_url == "https://test-project.supabase.co"
    
    def test_load_config_with_overrides(self):
        """Test loading configuration with overrides."""
        overrides = {
            "discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "batch_size": 25,
            "enable_debug": True
        }
        
        config = load_config_with_overrides(**overrides)
        
        assert config.batch_size == 25
        assert config.enable_debug is True
    
    def test_load_config_validation_error(self):
        """Test configuration loading with validation errors."""
        overrides = {
            "discord_token": "invalid_token",
            "supabase_url": "https://test-project.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            load_config_with_overrides(**overrides)
    
    @patch.dict(os.environ, {
        "logger_discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "supabase_url": "https://test-project.supabase.co",
        "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    })
    def test_get_config_singleton(self):
        """Test configuration singleton behavior."""
        config1 = get_config()
        config2 = get_config()
        
        # Should return the same instance
        assert config1 is config2
    
    @patch.dict(os.environ, {
        "logger_discord_token": "OTk5OTk5OTk5OTk5OTk5OTk5.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "supabase_url": "https://test-project.supabase.co",
        "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QtcHJvamVjdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE5MTU2MjQwMDB9.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    })
    def test_reload_config(self):
        """Test configuration reloading."""
        config1 = get_config()
        config2 = reload_config()
        
        # Should return a new instance
        assert config1 is not config2
        assert config2.discord_token == config1.discord_token


if __name__ == "__main__":
    pytest.main([__file__]) 