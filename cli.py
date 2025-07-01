#!/usr/bin/env python3
"""
Discord Logger Bot CLI Tool

A command-line interface for managing the Discord Logger Bot on Railway.
Provides commands for setup, monitoring, and maintenance.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any

import click
try:
    import aiohttp
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    print("Missing required dependencies. Install with: pip install click aiohttp rich")
    sys.exit(1)

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from badbot_discord_logger.config import load_config_with_overrides, get_config
    from badbot_discord_logger.database import SupabaseManager
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
    """Discord Logger Bot Management CLI for Railway"""
    pass


@main.command()
@click.option('--token', prompt='Discord Bot Token', help='Discord bot token', hide_input=True)
@click.option('--supabase-url', prompt='Supabase URL', help='Supabase project URL')
@click.option('--supabase-key', prompt='Supabase Key', help='Supabase anon key', hide_input=True)
@click.option('--env-file', default='.env', help='Environment file path')
def setup(token: str, supabase_url: str, supabase_key: str, env_file: str):
    """Set up the Discord Logger Bot configuration for Railway."""
    
    console.print("[bold blue]Setting up Discord Logger Bot for Railway...[/bold blue]")
    
    # Validate inputs
    if len(token) < 50:
        console.print("[red]Error: Discord token appears to be invalid (too short)[/red]")
        return
    
    if not supabase_url.startswith("https://"):
        console.print("[red]Error: Supabase URL must use HTTPS[/red]")
        return
    
    # Basic domain validation
    domain = supabase_url[8:]  # Remove "https://"
    if not domain or '.' not in domain or domain.endswith('.') or domain.startswith('.'):
        console.print("[red]Error: Supabase URL must be a valid HTTPS URL with a proper domain[/red]")
        return
    
    # Create environment file
    env_content = f"""# Discord Configuration
logger_discord_token={token}

# Supabase Configuration
supabase_url={supabase_url}
supabase_key={supabase_key}

# Logging Configuration
LOG_LEVEL=INFO
ENABLE_DEBUG=false

# Backfill Configuration
BACKFILL_ENABLED=true
BACKFILL_CHUNK_SIZE=100
BACKFILL_DELAY_SECONDS=1.0
BACKFILL_ON_STARTUP=false

# Performance Configuration
BATCH_SIZE=50
MAX_QUEUE_SIZE=10000
FLUSH_INTERVAL=30

# Health Check Configuration
HEALTH_CHECK_ENABLED=true

# Message Processing Configuration
PROCESS_BOT_MESSAGES=true
PROCESS_SYSTEM_MESSAGES=true
PROCESS_DM_MESSAGES=false
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        console.print(f"[green]✓ Configuration saved to {env_file}[/green]")
        console.print("\n[bold yellow]Railway Deployment Steps:[/bold yellow]")
        console.print("1. Create a new Railway project: railway new")
        console.print("2. Connect your GitHub repository")
        console.print("3. Add these environment variables in Railway dashboard:")
        console.print("   - logger_discord_token")
        console.print("   - supabase_url")
        console.print("   - supabase_key")
        console.print("4. Deploy: railway up")
        console.print("\n[cyan]Test locally first with: python cli.py config test[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error writing configuration file: {e}[/red]")


@main.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
def test():
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
                if cli.db_manager:
                    await cli.db_manager.initialize()
                    health = await cli.db_manager.health_check()
                    if health["database_connected"]:
                        progress.update(task2, description="✓ Database connected")
                    else:
                        progress.update(task2, description="✗ Database connection failed")
                        console.print(f"[red]Database error: {health.get('error', 'Unknown error')}[/red]")
                        return
                else:
                    progress.update(task2, description="✗ Database manager not initialized")
                    return
            except Exception as e:
                progress.update(task2, description="✗ Database connection failed")
                console.print(f"[red]Database error: {e}[/red]")
                return
            
            # Test Discord configuration
            task3 = progress.add_task("Validating Discord configuration...", total=None)
            if cli.config and cli.config.discord_token and len(cli.config.discord_token) > 50:
                progress.update(task3, description="✓ Discord token valid")
            else:
                progress.update(task3, description="✗ Discord token invalid")
                console.print("[red]Discord token appears to be invalid[/red]")
                return
        
        console.print("\n[bold green]✓ All tests passed! Configuration is valid.[/bold green]")
        
        # Display configuration summary
        if cli.config:
            table = Table(title="Configuration Summary")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Log Level", cli.config.log_level)
            table.add_row("Backfill Enabled", str(cli.config.backfill_enabled))
            table.add_row("Batch Size", str(cli.config.batch_size))
            table.add_row("Health Check Enabled", str(cli.config.health_check_enabled))
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
            if cli.db_manager:
                await cli.db_manager.initialize()
                stats = await cli.db_manager.get_statistics()
                
                table = Table(title="Database Statistics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="magenta")
                
                table.add_row("Total Messages", f"{stats.get('total_messages', 0):,}")
                table.add_row("Total Actions", f"{stats.get('total_actions', 0):,}")
                table.add_row("Total Guilds", f"{stats.get('total_guilds', 0):,}")
                
                console.print(table)
            else:
                console.print("[red]Database manager not initialized[/red]")
        except Exception as e:
            console.print(f"[red]Failed to get database statistics: {e}[/red]")
    
    asyncio.run(_show_stats())


@db.command()
def health():
    """Check database health."""
    
    async def _check_health():
        if not await cli.load_config():
            return
        
        try:
            if cli.db_manager:
                await cli.db_manager.initialize()
                health = await cli.db_manager.health_check()
                
                table = Table(title="Database Health Check")
                table.add_column("Check", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Details", style="dim")
                
                # Database connection
                status = "✓ Healthy" if health["database_connected"] else "✗ Failed"
                table.add_row("Database Connection", status, "")
                
                # Table access
                status = "✓ Accessible" if health["tables_accessible"] else "✗ Failed"
                table.add_row("Table Access", status, "")
                
                # Last message timestamp
                if health["last_message_timestamp"]:
                    table.add_row("Last Message", "✓ Available", health["last_message_timestamp"])
                else:
                    table.add_row("Last Message", "No messages", "")
                
                console.print(table)
                
                if health.get("error"):
                    console.print(f"\n[red]Error: {health['error']}[/red]")
            else:
                console.print("[red]Database manager not initialized[/red]")
        except Exception as e:
            console.print(f"[red]Health check failed: {e}[/red]")
    
    asyncio.run(_check_health())


@main.group()
def bot():
    """Bot management commands."""
    pass


@bot.command()
@click.option('--url', help='Bot health check URL (Railway deployment URL)')
def status(url: str):
    """Check bot status via health check endpoint."""
    
    async def _check_status():
        # Try to determine URL automatically or use provided one
        check_url = url
        if not check_url:
            # Check for Railway environment
            railway_url = os.environ.get('RAILWAY_STATIC_URL')
            if railway_url:
                check_url = f"https://{railway_url}/health"
            else:
                check_url = "http://localhost:8080/health"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(check_url, timeout=10) as response:
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
            console.print("[yellow]Make sure the bot is running and accessible[/yellow]")
            if not url:
                console.print("[cyan]Try specifying the URL with --url option[/cyan]")
    
    asyncio.run(_check_status())


@main.command()
def railway():
    """Show Railway deployment information."""
    
    console.print("[bold blue]Railway Deployment Guide[/bold blue]\n")
    
    console.print("[bold yellow]1. Setup Railway CLI:[/bold yellow]")
    console.print("   npm install -g @railway/cli")
    console.print("   railway login")
    
    console.print("\n[bold yellow]2. Create and deploy:[/bold yellow]")
    console.print("   railway new")
    console.print("   railway link")
    console.print("   railway up")
    
    console.print("\n[bold yellow]3. Set environment variables:[/bold yellow]")
    console.print("   railway variables set logger_discord_token=your_token")
    console.print("   railway variables set supabase_url=your_url")
    console.print("   railway variables set supabase_key=your_key")
    
    console.print("\n[bold yellow]4. Monitor deployment:[/bold yellow]")
    console.print("   railway logs")
    console.print("   railway status")
    
    console.print("\n[bold cyan]Useful Commands:[/bold cyan]")
    commands = [
        ("Check bot status", "python cli.py bot status --url https://your-app.railway.app"),
        ("View database stats", "python cli.py db stats"),
        ("Test config locally", "python cli.py config test"),
    ]
    
    for description, command in commands:
        console.print(f"  {description}: [dim]{command}[/dim]")


@main.command()
def docs():
    """Show documentation and helpful information."""
    
    console.print("[bold blue]Discord Logger Bot - Railway Edition[/bold blue]\n")
    
    console.print("[bold yellow]Quick Start:[/bold yellow]")
    console.print("1. python cli.py setup")
    console.print("2. python cli.py config test") 
    console.print("3. python cli.py railway")
    console.print("4. Deploy to Railway")
    
    console.print("\n[bold yellow]Helpful Links:[/bold yellow]")
    console.print("• Discord Developer Portal: https://discord.com/developers/applications")
    console.print("• Supabase Dashboard: https://app.supabase.com")
    console.print("• Railway Dashboard: https://railway.app")
    
    console.print("\n[bold yellow]Support:[/bold yellow]")
    console.print("• Check logs: railway logs")
    console.print("• Monitor status: python cli.py bot status")
    console.print("• Database health: python cli.py db health")


if __name__ == "__main__":
    main() 