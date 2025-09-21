#!/usr/bin/env python3
"""
Clear Weaviate Data Script

This script removes all data from the Weaviate collection to allow
starting the ingestion process from scratch.
"""

import weaviate
from config import settings
from rich.console import Console
from rich.prompt import Confirm

console = Console()

def clear_weaviate_data():
    """Clear all data from the Weaviate collection"""

    console.print("\n[bold red]⚠️  WARNING: This will delete ALL data from Weaviate![/bold red]")
    console.print(f"Collection: {settings.collection_name}")
    console.print(f"Weaviate URL: {settings.weaviate_url}")

    if not Confirm.ask("\nAre you sure you want to proceed?"):
        console.print("[yellow]Operation cancelled.[/yellow]")
        return

    try:
        # Connect to Weaviate
        console.print("\n[cyan]Connecting to Weaviate...[/cyan]")
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port
        )

        with client:
            # Check if collection exists
            if not client.collections.exists(settings.collection_name):
                console.print(f"[yellow]Collection '{settings.collection_name}' does not exist.[/yellow]")
                return

            # Get collection
            collection = client.collections.get(settings.collection_name)

            # Get current count
            console.print("[cyan]Counting existing documents...[/cyan]")
            count_before = collection.aggregate.over_all(total_count=True).total_count
            console.print(f"Found {count_before:,} documents in collection")

            if count_before == 0:
                console.print("[green]Collection is already empty![/green]")
                return

            # Delete all objects
            console.print(f"\n[red]Deleting all {count_before:,} documents...[/red]")

            # Method 1: Delete all objects in the collection
            collection.data.delete_many(
                where=weaviate.classes.query.Filter.by_property("thread_id").exists()
            )

            # Verify deletion
            console.print("[cyan]Verifying deletion...[/cyan]")
            count_after = collection.aggregate.over_all(total_count=True).total_count

            if count_after == 0:
                console.print(f"[green]✅ Successfully deleted all {count_before:,} documents![/green]")
                console.print("[green]The collection is now empty and ready for fresh ingestion.[/green]")
            else:
                console.print(f"[yellow]⚠️  {count_after:,} documents remain. Trying alternative deletion method...[/yellow]")

                # Method 2: Delete the entire collection and recreate schema
                console.print("[red]Deleting entire collection...[/red]")
                client.collections.delete(settings.collection_name)
                console.print("[green]✅ Collection deleted completely![/green]")
                console.print("[yellow]You'll need to recreate the schema before ingestion.[/yellow]")
                console.print("[cyan]Run: python schema.py[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise

def show_collection_stats():
    """Show current collection statistics"""
    try:
        console.print("\n[cyan]Checking current collection status...[/cyan]")
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port
        )

        with client:
            if not client.collections.exists(settings.collection_name):
                console.print(f"[yellow]Collection '{settings.collection_name}' does not exist.[/yellow]")
                return

            collection = client.collections.get(settings.collection_name)
            count = collection.aggregate.over_all(total_count=True).total_count

            console.print(f"[green]Collection '{settings.collection_name}' contains {count:,} documents[/green]")

            if count > 0:
                # Get a sample document
                result = collection.query.fetch_objects(limit=1)
                if result.objects:
                    obj = result.objects[0]
                    console.print(f"[dim]Sample document ID: {obj.uuid}[/dim]")
                    if hasattr(obj.properties, 'thread_id'):
                        console.print(f"[dim]Sample thread_id: {obj.properties.thread_id}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error checking collection: {e}[/red]")

if __name__ == "__main__":
    console.print("[bold]🗑️  Weaviate Data Cleaner[/bold]")

    # Show current status
    show_collection_stats()

    # Clear data
    clear_data = Confirm.ask("\nDo you want to clear all data?", default=False)
    if clear_data:
        clear_weaviate_data()

    # Show final status
    console.print("\n[bold]Final Status:[/bold]")
    show_collection_stats()

    console.print("\n[green]Ready for fresh ingestion![/green]")
    console.print("[cyan]Next steps:[/cyan]")
    console.print("1. python schema.py (if collection was deleted)")
    console.print("2. python ingestion.py")