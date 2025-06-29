#!/usr/bin/env python3
"""
Discord Logger Bot CLI Tool

A comprehensive command-line interface for managing the Discord Logger Bot.
Provides commands for setup, monitoring, maintenance, and troubleshooting.
"""

import asyncio
import json
import sys
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import argparse

import click
try:
    import aiohttp
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("Missing required dependencies. Install with: pip install click aiohttp rich")
    sys.exit(1)

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from badbot_discord_logger.config import load_config_with_overrides, get_config
    from badbot_discord_logger.database import SupabaseManager
    from badbot_discord_logger.models import ActionType
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you've installed the dependencies with: pip install -r requirements.txt")
    sys.exit(1)

console = Console()


class DiscordLoggerCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.config = None
        self.db_manager = None
    
    async def load_config(self, **overrides):
        """Load configuration with optional overrides."""
        try:
            if overrides:
                self.config = load_config_with_overrides(**overrides)
            else:
                self.config = get_config()
            self.db_manager = SupabaseManager(self.config)
            return True
        except Exception as e:
            console.print(f"[red]Failed to load configuration: {e}[/red]")
            return False


cli = DiscordLoggerCLI()


@click.group()
@click.version_option(version="1.0.0")
def main():
    """Discord Logger Bot Management CLI"""
    pass


@main.command()
@click.option('--token', prompt='Discord Bot Token', help='Discord bot token', hide_input=True)
@click.option('--app-id', prompt='Discord Application ID', help='Discord application ID')
@click.option('--supabase-url', prompt='Supabase URL', help='Supabase project URL')
@click.option('--supabase-key', prompt='Supabase Key', help='Supabase anon key', hide_input=True)
@click.option('--env-file', default='.env', help='Environment file path')
def setup(token: str, app_id: str, supabase_url: str, supabase_key: str, env_file: str):
    """Set up the Discord Logger Bot configuration."""
    
    console.print("[bold blue]Setting up Discord Logger Bot...[/bold blue]")
    
    # Validate inputs
    if len(token) < 50:
        console.print("[red]Error: Discord token appears to be invalid (too short)[/red]")
        return
    
    if not supabase_url.startswith("https://") or not supabase_url.endswith(".supabase.co"):
        console.print("[red]Error: Supabase URL must be in format: https://xxx.supabase.co[/red]")
        return
    
    # Create environment file
    env_content = f"""# Discord Configuration
DISCORD_TOKEN={token}
DISCORD_APPLICATION_ID={app_id}

# Supabase Configuration
SUPABASE_URL={supabase_url}
SUPABASE_KEY={supabase_key}

# Logging Configuration
LOG_LEVEL=INFO
ENABLE_DEBUG=false

# Backfill Configuration
BACKFILL_ENABLED=true
BACKFILL_CHUNK_SIZE=100
BACKFILL_DELAY_SECONDS=1.0

# Performance Configuration
BATCH_SIZE=50
MAX_QUEUE_SIZE=10000
FLUSH_INTERVAL=30

# Health Check Configuration
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_PORT=8080

# Metrics Configuration
METRICS_ENABLED=false
METRICS_PORT=9090
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        console.print(f"[green]✓ Configuration saved to {env_file}[/green]")
        console.print("[yellow]Next steps:[/yellow]")
        console.print("1. Set up your Supabase database schema with: python cli.py db setup")
        console.print("2. Test the configuration with: python cli.py config test")
        console.print("3. Start the bot with: python main.py")
        
    except Exception as e:
        console.print(f"[red]Error writing configuration file: {e}[/red]")


@main.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
@click.option('--env-file', default='.env', help='Environment file to test')
def test(env_file: str):
    """Test the configuration and connections."""
    
    async def _test_config():
        console.print("[bold blue]Testing Discord Logger Bot configuration...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Test configuration loading
            task1 = progress.add_task("Loading configuration...", total=None)
            if not await cli.load_config():
                return
            progress.update(task1, description="✓ Configuration loaded")
            
            # Test database connection
            task2 = progress.add_task("Testing database connection...", total=None)
            try:
                await cli.db_manager.initialize()
                health = await cli.db_manager.health_check()
                if health["database_connected"]:
                    progress.update(task2, description="✓ Database connected")
                else:
                    progress.update(task2, description="✗ Database connection failed")
                    console.print(f"[red]Database error: {health.get('error', 'Unknown error')}[/red]")
                    return
            except Exception as e:
                progress.update(task2, description="✗ Database connection failed")
                console.print(f"[red]Database error: {e}[/red]")
                return
            
            # Test Discord configuration
            task3 = progress.add_task("Validating Discord configuration...", total=None)
            if cli.config.discord_token and len(cli.config.discord_token) > 50:
                progress.update(task3, description="✓ Discord token valid")
            else:
                progress.update(task3, description="✗ Discord token invalid")
                console.print("[red]Discord token appears to be invalid[/red]")
                return
        
        console.print("\n[bold green]✓ All tests passed! Configuration is valid.[/bold green]")
        
        # Display configuration summary
        table = Table(title="Configuration Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Log Level", cli.config.log_level)
        table.add_row("Backfill Enabled", str(cli.config.backfill_enabled))
        table.add_row("Batch Size", str(cli.config.batch_size))
        table.add_row("Health Check Port", str(cli.config.health_check_port))
        table.add_row("Production Mode", str(cli.config.is_production))
        
        console.print(table)
    
    asyncio.run(_test_config())


@main.group()
def db():
    """Database management commands."""
    pass


@db.command()
def stats():
    """Show database statistics."""
    
    async def _show_stats():
        if not await cli.load_config():
            return
        
        try:
            await cli.db_manager.initialize()
            stats = await cli.db_manager.get_statistics()
            
            table = Table(title="Database Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Messages", f"{stats.get('total_messages', 0):,}")
            table.add_row("Total Actions", f"{stats.get('total_actions', 0):,}")
            table.add_row("Total Guilds", f"{stats.get('total_guilds', 0):,}")
            
            console.print(table)
        except Exception as e:
            console.print(f"[red]Failed to get database statistics: {e}[/red]")
    
    asyncio.run(_show_stats())


@main.group()
def bot():
    """Bot management commands."""
    pass


@bot.command()
@click.option('--host', default='localhost', help='Bot health check host')
@click.option('--port', default=8080, help='Bot health check port')
def status(host: str, port: int):
    """Check bot status via health check endpoint."""
    
    async def _check_status():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://{host}:{port}/health', timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        console.print("[bold green]✓ Bot is running[/bold green]")
                        
                        table = Table(title="Bot Status")
                        table.add_column("Metric", style="cyan")
                        table.add_column("Value", style="magenta")
                        
                        for key, value in data.items():
                            if isinstance(value, dict):
                                value = json.dumps(value, indent=2)
                            table.add_row(key.replace('_', ' ').title(), str(value))
                        
                        console.print(table)
                    else:
                        console.print(f"[red]✗ Bot health check failed (HTTP {response.status})[/red]")
        except Exception as e:
            console.print(f"[red]✗ Bot is not responding: {e}[/red]")
            console.print("[yellow]Make sure the bot is running and health checks are enabled[/yellow]")
    
    asyncio.run(_check_status())


@main.command()
def docs():
    """Show documentation and helpful information."""
    
    console.print("[bold blue]Discord Logger Bot Documentation & Links[/bold blue]\n")
    
    console.print(f"[bold yellow]Common Commands:[/bold yellow]")
    commands = [
        ("Setup configuration", "python cli.py setup"),
        ("Test configuration", "python cli.py config test"),
        ("Check bot status", "python cli.py bot status"),
        ("View database stats", "python cli.py db stats"),
    ]
    
    for description, command in commands:
        console.print(f"  {description}: [cyan]{command}[/cyan]")


if __name__ == "__main__":
    main() 