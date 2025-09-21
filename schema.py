"""
Weaviate Schema Definition for Telegram RAG System

This module defines and manages the Weaviate collection schema.
It handles schema creation, validation, and migration.
"""

import weaviate
from weaviate.classes.config import Configure
from weaviate.collections.classes.config_vectorizers import VectorDistances
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from config import settings

console = Console()


class WeaviateSchema:
    """
    Manages Weaviate schema for Telegram messages.

    This class handles:
    - Schema definition
    - Collection creation
    - Schema validation
    - Data migration
    """

    def __init__(self, client: weaviate.WeaviateClient):
        """
        Initialize schema manager with Weaviate client.

        Args:
            client: Connected Weaviate client instance
        """
        self.client = client
        self.collection_name = settings.collection_name

    def get_collection_properties(self):
        """
        Define properties for the Weaviate v4 collection.

        Returns the property configuration using v4 API.
        """
        from weaviate.classes.config import Property, DataType

        return [
            Property(
                name="content",
                data_type=DataType.TEXT,
                description="Combined message content for semantic search",
                index_filterable=True,
                index_searchable=True,
                vectorize_property_name=False
            ),
            Property(
                name="thread_id",
                data_type=DataType.TEXT,
                description="Unique identifier for the message thread",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="participants",
                data_type=DataType.TEXT_ARRAY,
                description="List of participants in the thread",
                index_filterable=True,
                index_searchable=True,
                skip_vectorization=True
            ),
            Property(
                name="timestamp",
                data_type=DataType.DATE,
                description="When the thread started",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="message_count",
                data_type=DataType.INT,
                description="Number of messages in thread",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="duration_seconds",
                data_type=DataType.NUMBER,
                description="Thread duration in seconds",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="word_count",
                data_type=DataType.INT,
                description="Total words in thread",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="message_types",
                data_type=DataType.TEXT_ARRAY,
                description="Types of messages in thread",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="has_service_messages",
                data_type=DataType.BOOL,
                description="Contains system/service messages",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="has_questions",
                data_type=DataType.BOOL,
                description="Thread contains questions",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="has_links",
                data_type=DataType.BOOL,
                description="Thread contains URLs",
                index_filterable=True,
                index_searchable=False,
                skip_vectorization=True
            ),
            Property(
                name="raw_messages",
                data_type=DataType.TEXT,
                description="Original message data as JSON string",
                index_filterable=False,
                index_searchable=False,
                skip_vectorization=True
            ),
        ]

    def collection_exists(self) -> bool:
        """
        Check if the collection already exists in Weaviate.

        Returns:
            True if collection exists, False otherwise
        """
        try:
            return self.client.collections.exists(self.collection_name)
        except Exception as e:
            console.print(f"[red]Error checking collection existence: {e}[/red]")
            return False

    def create_collection(self, force: bool = False) -> bool:
        """
        Create the collection in Weaviate.

        Args:
            force: If True, delete existing collection first

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if collection exists
            if self.collection_exists():
                if force:
                    console.print(f"[yellow]Deleting existing collection: {self.collection_name}[/yellow]")
                    self.client.collections.delete(self.collection_name)
                else:
                    console.print(f"[yellow]Collection already exists: {self.collection_name}[/yellow]")
                    console.print("[info]Use force=True to recreate[/info]")
                    return False

            # Create the collection
            console.print(f"[cyan]Creating collection: {self.collection_name}[/cyan]")

            # Configure vectorizer - Use host.docker.internal for Docker to host connection
            # Weaviate is in Docker, Ollama is on host machine
            ollama_endpoint = f"http://host.docker.internal:{settings.ollama_port}"
            vectorizer_config = Configure.Vectorizer.text2vec_ollama(
                api_endpoint=ollama_endpoint,
                model=settings.ollama_embed_model
            )

            # Create collection with v4 API
            self.client.collections.create(
                name=self.collection_name,
                description="Telegram message threads for RAG system",
                properties=self.get_collection_properties(),
                vectorizer_config=vectorizer_config,
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE,
                    ef=128,
                    ef_construction=256,
                    max_connections=32
                )
            )

            console.print(f"[green]✅ Collection created successfully![/green]")
            return True

        except Exception as e:
            console.print(f"[red]Error creating collection: {e}[/red]")
            return False

    def validate_schema(self) -> bool:
        """
        Validate that the existing schema matches our definition.

        Returns:
            True if schema is valid, False otherwise
        """
        if not self.collection_exists():
            console.print(f"[red]Collection does not exist: {self.collection_name}[/red]")
            return False

        try:
            # Get current collection configuration
            collection = self.client.collections.get(self.collection_name)
            config = collection.config.get()

            # Get expected property names
            expected_props = {prop.name for prop in self.get_collection_properties()}
            current_props = {prop.name for prop in config.properties}

            if current_props != expected_props:
                console.print("[yellow]Schema mismatch detected![/yellow]")
                console.print(f"Current properties: {current_props}")
                console.print(f"Expected properties: {expected_props}")
                return False

            console.print("[green]✅ Schema validation passed![/green]")
            return True

        except Exception as e:
            console.print(f"[red]Error validating schema: {e}[/red]")
            return False

    def display_schema_info(self):
        """
        Display the current schema in a readable format.
        """
        if not self.collection_exists():
            console.print(f"[red]Collection does not exist: {self.collection_name}[/red]")
            return

        try:
            collection = self.client.collections.get(self.collection_name)
            config = collection.config.get()

            # Create properties table
            table = Table(title=f"Schema: {self.collection_name}")
            table.add_column("Property", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Vectorized", style="green")
            table.add_column("Filterable", style="yellow")
            table.add_column("Searchable", style="blue")

            for prop in config.properties:
                name = prop.name
                data_type = str(prop.data_type)

                # Check if vectorized (skip_vectorization means NOT vectorized)
                skip_vec = getattr(prop, 'skip_vectorization', False)
                vectorized = "❌" if skip_vec else "✅"

                # Check if filterable and searchable
                filterable = "✅" if getattr(prop, 'index_filterable', False) else "❌"
                searchable = "✅" if getattr(prop, 'index_searchable', False) else "❌"

                table.add_row(name, data_type, vectorized, filterable, searchable)

            console.print(table)

            # Display vectorizer info
            vectorizer_info = config.vectorizer_config
            console.print(f"\n[bold]Vectorizer:[/bold] {type(vectorizer_info).__name__ if vectorizer_info else 'None'}")

            # Display index info
            vector_index_info = config.vector_index_config
            console.print(f"[bold]Vector Index:[/bold] {type(vector_index_info).__name__ if vector_index_info else 'None'}")

            # Count objects
            try:
                total = collection.aggregate.over_all(total_count=True).total_count
                console.print(f"[bold]Documents:[/bold] {total}")
            except:
                console.print("[bold]Documents:[/bold] 0")

        except Exception as e:
            console.print(f"[red]Error displaying schema: {e}[/red]")

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.client.collections.get(self.collection_name)

            # Get basic count
            total_count = collection.aggregate.over_all(total_count=True).total_count

            # Get aggregation for numeric fields
            from weaviate.classes.aggregate import Metrics
            stats = collection.aggregate.over_all(
                message_count=Metrics("message_count").integer(
                    mean=True, maximum=True, minimum=True
                ),
                word_count=Metrics("word_count").integer(
                    mean=True, maximum=True, minimum=True
                )
            )

            return {
                "total_threads": total_count,
                "message_stats": {
                    "mean": stats.properties.get("message_count", {}).get("mean"),
                    "maximum": stats.properties.get("message_count", {}).get("maximum"),
                    "minimum": stats.properties.get("message_count", {}).get("minimum")
                },
                "word_stats": {
                    "mean": stats.properties.get("word_count", {}).get("mean"),
                    "maximum": stats.properties.get("word_count", {}).get("maximum"),
                    "minimum": stats.properties.get("word_count", {}).get("minimum")
                }
            }
        except Exception:
            return {"total_threads": 0}


def initialize_weaviate_schema():
    """
    Helper function to set up Weaviate schema.
    This is the main entry point for schema creation.
    """
    # Connect to Weaviate using v4 client
    client = weaviate.connect_to_local(
        host=settings.weaviate_host,
        port=settings.weaviate_port,
        grpc_port=50051,  # Default gRPC port
        headers={}
    )

    try:
        # Create schema manager
        schema_manager = WeaviateSchema(client)

        # Display current status
        console.print("\n[bold]Weaviate Schema Setup[/bold]\n")

        if schema_manager.collection_exists():
            console.print(f"[yellow]Collection '{settings.collection_name}' already exists[/yellow]")
            schema_manager.display_schema_info()

            # Validate schema
            if not schema_manager.validate_schema():
                console.print("[red]Schema validation failed! Consider recreating.[/red]")
                return False
        else:
            # Create new collection
            if schema_manager.create_collection():
                schema_manager.display_schema_info()
            else:
                return False

        return True

    finally:
        # Always close the client connection
        client.close()


if __name__ == "__main__":
    """
    Run this file directly to set up or inspect the schema.
    python schema.py
    """
    initialize_weaviate_schema()