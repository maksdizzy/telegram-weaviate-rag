"""
Dify Integration Setup and Configuration

This script helps you set up the API endpoint for Dify integration and provides
configuration instructions.
"""

import secrets
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import subprocess
import sys

console = Console()


def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def check_dependencies():
    """Check if FastAPI and uvicorn are installed"""
    try:
        import fastapi
        import uvicorn
        return True
    except ImportError:
        return False


def install_dependencies():
    """Install required dependencies"""
    console.print("[cyan]Installing FastAPI and uvicorn...[/cyan]")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])
        console.print("[green]✅ Dependencies installed successfully[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to install dependencies: {e}[/red]")
        return False


def update_api_key():
    """Update the API key in dify_api.py"""
    api_file = Path("dify_api.py")
    if not api_file.exists():
        console.print("[red]❌ dify_api.py not found[/red]")
        return None

    # Generate new API key
    new_api_key = generate_api_key()

    # Read current content
    content = api_file.read_text()

    # Replace the API key
    updated_content = content.replace(
        'API_KEY = "your-secret-api-key"',
        f'API_KEY = "{new_api_key}"'
    )

    # Write back
    api_file.write_text(updated_content)

    console.print(f"[green]✅ Generated new API key: {new_api_key}[/green]")
    return new_api_key


def main():
    """Main setup function"""
    console.print(Panel.fit(
        "[bold cyan]Dify Integration Setup[/bold cyan]\n"
        "This will configure your RAG system for Dify integration",
        title="Setup"
    ))

    # Step 1: Check dependencies
    console.print("\n[cyan]Step 1: Checking dependencies...[/cyan]")
    if not check_dependencies():
        console.print("[yellow]FastAPI/uvicorn not found. Installing...[/yellow]")
        if not install_dependencies():
            console.print("[red]❌ Setup failed. Please install dependencies manually:[/red]")
            console.print("pip install fastapi uvicorn[standard]")
            return
    else:
        console.print("[green]✅ Dependencies are installed[/green]")

    # Step 2: Generate API key
    console.print("\n[cyan]Step 2: Generating API key...[/cyan]")
    api_key = update_api_key()
    if not api_key:
        return

    # Step 3: Create configuration info
    console.print("\n[cyan]Step 3: Configuration complete![/cyan]")

    # Display configuration table
    table = Table(title="Dify Integration Configuration")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API Endpoint", "http://localhost:8000/retrieval")
    table.add_row("API Key", api_key)
    table.add_row("Knowledge ID", "rag-knowledge-base")
    table.add_row("Health Check", "http://localhost:8000/health")

    console.print(table)

    # Instructions
    console.print("\n[bold yellow]Next Steps:[/bold yellow]")
    console.print("1. Start your Weaviate database (if not running)")
    console.print("2. Run: [bold]python dify_api.py[/bold]")
    console.print("3. In Dify, add external knowledge base with:")
    console.print(f"   • API Endpoint: [bold]http://localhost:8000/retrieval[/bold]")
    console.print(f"   • API Key: [bold]{api_key}[/bold]")
    console.print(f"   • Knowledge ID: [bold]rag-knowledge-base[/bold]")

    console.print("\n[bold green]✨ Setup complete! Your RAG system is ready for Dify.[/bold green]")


if __name__ == "__main__":
    main()