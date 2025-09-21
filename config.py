"""
Configuration Management for Telegram RAG System

This module loads settings from environment variables and provides
a centralized configuration object for the entire application.
"""

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic's BaseSettings automatically reads from environment variables.
    Field names match env var names (case-insensitive by default).
    """

    # Weaviate Configuration
    weaviate_host: str = Field(
        default="localhost",
        description="Weaviate server hostname"
    )
    weaviate_port: int = Field(
        default=8080,
        description="Weaviate server port"
    )
    weaviate_scheme: str = Field(
        default="http",
        description="Connection scheme (http/https)"
    )

    # Ollama Configuration
    ollama_host: str = Field(
        default="localhost",
        description="Ollama server hostname"
    )
    ollama_port: int = Field(
        default=11434,
        description="Ollama server port"
    )

    # Model Configuration
    ollama_embed_model: str = Field(
        default="nomic-embed-text",
        description="Model for creating embeddings"
    )
    ollama_generation_model: str = Field(
        default="llama3.2",
        description="Model for generating responses"
    )

    # Application Settings
    batch_size: int = Field(
        default=100,
        description="Number of messages to process in one batch"
    )
    collection_name: str = Field(
        default="TelegramMessages",
        description="Weaviate collection name for storing messages"
    )

    # API Settings
    api_key: str = Field(
        default="",
        description="API key for authentication (REQUIRED - set in .env file)"
    )
    knowledge_id: str = Field(
        default="rag-knowledge-base",
        description="Knowledge base identifier"
    )

    # Thread Detection Settings (not in .env, but configurable)
    thread_time_window_minutes: int = Field(
        default=5,
        description="Max minutes between messages to be in same thread"
    )
    thread_min_messages: int = Field(
        default=1,
        description="Minimum messages to create a thread"
    )
    thread_max_messages: int = Field(
        default=50,
        description="Maximum messages in a single thread"
    )

    # Search Settings
    search_limit: int = Field(
        default=5,
        description="Default number of search results to return"
    )
    search_alpha: float = Field(
        default=0.75,
        description="Hybrid search weight (0=keyword only, 1=vector only)"
    )

    # File Paths
    telegram_json_path: Path = Field(
        default=Path("result.json"),
        description="Path to Telegram JSON export file"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,  # WEAVIATE_HOST or weaviate_host both work
        "extra": "allow"  # Allow extra environment variables
    }

    @field_validator("telegram_json_path", mode="before")
    @classmethod
    def validate_json_path(cls, v):
        """Ensure the Telegram JSON file exists"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Telegram JSON file not found: {path}")
        return path

    @field_validator("thread_time_window_minutes")
    @classmethod
    def validate_time_window(cls, v):
        """Ensure time window is reasonable"""
        if v < 1 or v > 60:
            raise ValueError("Thread time window should be between 1 and 60 minutes")
        return v

    @field_validator("search_alpha")
    @classmethod
    def validate_alpha(cls, v):
        """Ensure alpha is between 0 and 1"""
        if v < 0 or v > 1:
            raise ValueError("Search alpha must be between 0 and 1")
        return v

    @property
    def weaviate_url(self) -> str:
        """Construct full Weaviate URL"""
        return f"{self.weaviate_scheme}://{self.weaviate_host}:{self.weaviate_port}"

    @property
    def ollama_url(self) -> str:
        """Construct full Ollama URL"""
        return f"http://{self.ollama_host}:{self.ollama_port}"

    @property
    def thread_time_window_seconds(self) -> int:
        """Convert time window to seconds for easier calculation"""
        return self.thread_time_window_minutes * 60

    def display_config(self) -> str:
        """
        Return a formatted string of current configuration.
        Useful for debugging and verification.
        """
        return f"""
╔══════════════════════════════════════════════╗
║         Telegram RAG Configuration           ║
╚══════════════════════════════════════════════╝

📦 Weaviate Settings:
  • URL: {self.weaviate_url}
  • Collection: {self.collection_name}
  • Batch Size: {self.batch_size}

🤖 Ollama Settings:
  • URL: {self.ollama_url}
  • Embedding Model: {self.ollama_embed_model}
  • Generation Model: {self.ollama_generation_model}

🔍 Thread Detection:
  • Time Window: {self.thread_time_window_minutes} minutes
  • Min Messages: {self.thread_min_messages}
  • Max Messages: {self.thread_max_messages}

🔎 Search Settings:
  • Default Limit: {self.search_limit} results
  • Hybrid Alpha: {self.search_alpha:.2f} (vector weight)

📁 Data Source:
  • Telegram JSON: {self.telegram_json_path}
"""

    def validate_connections(self) -> dict:
        """
        Test connections to external services.
        Returns a dict with service names and their status.
        """
        import requests

        results = {}

        # Test Weaviate
        try:
            response = requests.get(f"{self.weaviate_url}/v1/.well-known/ready", timeout=2)
            results["weaviate"] = response.status_code == 200
        except:
            results["weaviate"] = False

        # Test Ollama
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            results["ollama"] = response.status_code == 200
        except:
            results["ollama"] = False

        # Check if models are available in Ollama
        if results["ollama"]:
            try:
                response = requests.get(f"{self.ollama_url}/api/tags")
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]

                results["embed_model"] = self.ollama_embed_model in model_names
                results["generation_model"] = any(
                    self.ollama_generation_model in name
                    for name in model_names
                )
            except:
                results["embed_model"] = False
                results["generation_model"] = False

        return results


# Create a singleton instance
settings = Settings()


def check_environment() -> bool:
    """
    Verify that all required services are available.
    Prints status and returns True if everything is ready.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print("\n[bold]Checking Environment...[/bold]\n")

    # Get connection status
    status = settings.validate_connections()

    # Create status table
    table = Table(title="Service Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    # Weaviate
    weaviate_status = "✅ Connected" if status.get("weaviate") else "❌ Not Available"
    table.add_row(
        "Weaviate",
        weaviate_status,
        f"URL: {settings.weaviate_url}"
    )

    # Ollama
    ollama_status = "✅ Connected" if status.get("ollama") else "❌ Not Available"
    table.add_row(
        "Ollama",
        ollama_status,
        f"URL: {settings.ollama_url}"
    )

    # Embedding Model
    embed_status = "✅ Available" if status.get("embed_model") else "⚠️ Not Found"
    table.add_row(
        "Embedding Model",
        embed_status,
        settings.ollama_embed_model
    )

    # Generation Model
    gen_status = "✅ Available" if status.get("generation_model") else "⚠️ Not Found"
    table.add_row(
        "Generation Model",
        gen_status,
        settings.ollama_generation_model
    )

    console.print(table)

    # Check if everything is ready
    all_ready = all([
        status.get("weaviate"),
        status.get("ollama"),
        status.get("embed_model"),
        status.get("generation_model")
    ])

    if not all_ready:
        console.print("\n[yellow]⚠️ Some services are not available![/yellow]")

        if not status.get("weaviate"):
            console.print("[red]• Start Weaviate:[/red] docker-compose up -d")

        if not status.get("ollama"):
            console.print("[red]• Start Ollama:[/red] ollama serve")

        if not status.get("embed_model"):
            console.print(f"[red]• Pull embedding model:[/red] ollama pull {settings.ollama_embed_model}")

        if not status.get("generation_model"):
            console.print(f"[red]• Pull generation model:[/red] ollama pull {settings.ollama_generation_model}")

    else:
        console.print("\n[green]✅ All services are ready![/green]")

    return all_ready


if __name__ == "__main__":
    """
    When run directly, display configuration and check connections.
    Useful for testing: python config.py
    """
    print(settings.display_config())
    check_environment()