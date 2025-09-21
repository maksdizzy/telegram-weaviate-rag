"""
Data Ingestion Pipeline for Telegram RAG System

This module handles the process of importing message threads into Weaviate.
It converts threads to documents, generates embeddings, and stores them.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import weaviate
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel

from config import settings
from models import MessageThread, WeaviateDocument
from schema import WeaviateSchema
from thread_detector import process_telegram_export
import argparse

console = Console()


class DataIngestion:
    """
    Manages the ingestion of Telegram threads into Weaviate.

    Features:
    - Batch processing for efficiency
    - Progress tracking with rich UI
    - Error handling and retry logic
    - Duplicate detection
    - Resume capability
    """

    def __init__(self, client: weaviate.WeaviateClient, batch_size: int = None):
        """
        Initialize the ingestion pipeline.

        Args:
            client: Connected Weaviate client
            batch_size: Number of documents to process at once
        """
        self.client = client
        self.collection_name = settings.collection_name
        self.batch_size = batch_size or settings.batch_size

        # Statistics tracking
        self.stats = {
            "total_threads": 0,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }

        # Failed items for retry
        self.failed_threads = []

    def prepare_documents(self, threads: List[MessageThread]) -> List[WeaviateDocument]:
        """
        Convert message threads to Weaviate documents.

        Args:
            threads: List of message threads

        Returns:
            List of documents ready for insertion
        """
        console.print(f"[cyan]Preparing {len(threads)} threads for ingestion...[/cyan]")

        documents = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Converting threads", total=len(threads))

            for thread in threads:
                try:
                    # Convert thread to document
                    doc = WeaviateDocument.from_thread(thread)
                    documents.append(doc)
                    progress.update(task, advance=1)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to convert thread {thread.thread_id}: {e}[/yellow]")
                    self.stats["skipped"] += 1
                    progress.update(task, advance=1)

        console.print(f"[green]✅ Prepared {len(documents)} documents[/green]")
        return documents

    def check_existing_threads(self) -> set:
        """
        Get IDs of threads already in Weaviate to avoid duplicates.

        Returns:
            Set of existing thread IDs
        """
        console.print("[cyan]Checking for existing threads...[/cyan]")

        try:
            collection = self.client.collections.get(self.collection_name)

            # Get all thread IDs (pagination might be needed for large datasets)
            existing_ids = set()

            # Use cursor-based pagination for large collections
            cursor = None
            while True:
                results = collection.query.fetch_objects(
                    limit=1000,
                    after=cursor,
                    return_properties=["thread_id"]
                )

                if not results.objects:
                    break

                for obj in results.objects:
                    if obj.properties.get("thread_id"):
                        existing_ids.add(obj.properties["thread_id"])

                # Check if there are more results
                if len(results.objects) < 1000:
                    break

                # Get cursor for next page
                cursor = results.objects[-1].uuid

            if existing_ids:
                console.print(f"[yellow]Found {len(existing_ids)} existing threads[/yellow]")

            return existing_ids

        except Exception as e:
            console.print(f"[yellow]Could not check existing threads: {e}[/yellow]")
            return set()

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get the timestamp of the most recent message in Weaviate.
        Returns:
            Latest timestamp or None if collection is empty
        """
        try:
            collection = self.client.collections.get(self.collection_name)

            # Query for the most recent document by timestamp
            results = collection.query.fetch_objects(
                limit=1,
                sort={"path": "timestamp", "order": "desc"},
                return_properties=["timestamp"]
            )

            if results.objects:
                timestamp_str = results.objects[0].properties.get("timestamp")
                if timestamp_str:
                    # Parse RFC3339 timestamp
                    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            return None

        except Exception as e:
            console.print(f"[yellow]Could not get latest timestamp: {e}[/yellow]")
            return None

    def filter_new_threads(self, threads: List[MessageThread], since: datetime) -> List[MessageThread]:
        """
        Filter threads to only include those with messages newer than the given timestamp.

        Args:
            threads: List of message threads
            since: Only include threads with messages after this timestamp

        Returns:
            Filtered list of threads
        """
        new_threads = []

        for thread in threads:
            # Check if any message in the thread is newer than 'since'
            has_new_messages = False
            for msg in thread.messages:
                if msg.date and msg.date > since:
                    has_new_messages = True
                    break

            if has_new_messages:
                new_threads.append(thread)

        return new_threads

    def ingest_batch(self, documents: List[WeaviateDocument]) -> Dict[str, int]:
        """
        Ingest a batch of documents into Weaviate.

        Args:
            documents: List of documents to ingest

        Returns:
            Dictionary with success/failure counts
        """
        results = {"success": 0, "failed": 0}
        collection = self.client.collections.get(self.collection_name)

        # Prepare batch data
        batch_data = []
        for doc in documents:
            try:
                # Convert to Weaviate format
                obj_data = doc.to_weaviate_object()
                batch_data.append(obj_data)
            except Exception as e:
                console.print(f"[red]Error preparing document: {e}[/red]")
                results["failed"] += 1
                self.failed_threads.append(doc)

        # Insert batch
        if batch_data:
            try:
                # Use batch insertion for efficiency
                with collection.batch.dynamic() as batch:
                    for data in batch_data:
                        batch.add_object(
                            properties=data,
                            uuid=None  # Let Weaviate generate UUID
                        )

                results["success"] = len(batch_data)

            except Exception as e:
                console.print(f"[red]Batch insertion error: {e}[/red]")
                results["failed"] += len(batch_data)
                self.failed_threads.extend(documents)

        return results

    def ingest_documents(self, documents: List[WeaviateDocument], skip_existing: bool = True):
        """
        Main ingestion process with progress tracking.

        Args:
            documents: List of documents to ingest
            skip_existing: Whether to skip already indexed threads
        """
        self.stats["total_threads"] = len(documents)
        self.stats["start_time"] = datetime.now()

        # Check for existing threads if needed
        existing_ids = set()
        if skip_existing:
            existing_ids = self.check_existing_threads()

        # Filter out existing documents
        if existing_ids:
            documents = [doc for doc in documents if doc.thread_id not in existing_ids]
            skipped_count = self.stats["total_threads"] - len(documents)
            self.stats["skipped"] = skipped_count
            console.print(f"[yellow]Skipping {skipped_count} already indexed threads[/yellow]")

        if not documents:
            console.print("[yellow]No new documents to ingest[/yellow]")
            self.stats["end_time"] = datetime.now()
            return

        # Process in batches with progress bar
        console.print(f"\n[cyan]Starting ingestion of {len(documents)} documents...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:

            task = progress.add_task(
                f"Ingesting documents (batch size: {self.batch_size})",
                total=len(documents)
            )

            # Process in batches
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(documents) + self.batch_size - 1) // self.batch_size

                progress.update(
                    task,
                    description=f"Processing batch {batch_num}/{total_batches}"
                )

                # Ingest batch
                results = self.ingest_batch(batch)

                self.stats["successful"] += results["success"]
                self.stats["failed"] += results["failed"]
                self.stats["processed"] += len(batch)

                progress.update(task, advance=len(batch))

                # Small delay to avoid overwhelming the server
                time.sleep(0.1)

        self.stats["end_time"] = datetime.now()

        # Handle retries if there were failures
        if self.failed_threads and len(self.failed_threads) < 50:  # Only retry small batches
            console.print(f"\n[yellow]Retrying {len(self.failed_threads)} failed documents...[/yellow]")
            retry_results = self.ingest_batch(self.failed_threads)
            self.stats["successful"] += retry_results["success"]
            self.stats["failed"] = retry_results["failed"]  # Update final failed count

    def display_stats(self):
        """
        Display ingestion statistics in a nice table.
        """
        if not self.stats["start_time"]:
            return

        # Calculate duration
        end_time = self.stats["end_time"] or datetime.now()
        duration = (end_time - self.stats["start_time"]).total_seconds()
        docs_per_second = self.stats["processed"] / duration if duration > 0 else 0

        # Create statistics table
        table = Table(title="Ingestion Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Threads", str(self.stats["total_threads"]))
        table.add_row("Processed", str(self.stats["processed"]))
        table.add_row("Successful", str(self.stats["successful"]))
        table.add_row("Failed", str(self.stats["failed"]))
        table.add_row("Skipped (existing)", str(self.stats["skipped"]))
        table.add_row("Duration", f"{duration:.2f} seconds")
        table.add_row("Speed", f"{docs_per_second:.1f} docs/second")

        console.print(table)

        # Success rate
        if self.stats["processed"] > 0:
            success_rate = (self.stats["successful"] / self.stats["processed"]) * 100
            console.print(f"\n[green]Success Rate: {success_rate:.1f}%[/green]")

        # Show warning if there were failures
        if self.stats["failed"] > 0:
            console.print(f"[red]⚠️  {self.stats['failed']} documents failed to ingest[/red]")

    def verify_ingestion(self) -> Dict[str, Any]:
        """
        Verify that data was successfully ingested.

        Returns:
            Statistics about the ingested data
        """
        console.print("\n[cyan]Verifying ingestion...[/cyan]")

        try:
            collection = self.client.collections.get(self.collection_name)

            # Get total count
            total_count = collection.aggregate.over_all(total_count=True).total_count

            # Get some statistics
            from weaviate.classes.aggregate import Metrics
            stats = collection.aggregate.over_all(
                return_metrics=[
                    Metrics("message_count").integer(mean=True, maximum=True, minimum=True),
                    Metrics("word_count").integer(mean=True, maximum=True, minimum=True)
                ]
            )

            verification = {
                "total_documents": total_count,
                "message_stats": {
                    "mean": stats.properties.get("message_count", {}).get("mean", 0),
                    "max": stats.properties.get("message_count", {}).get("maximum", 0),
                    "min": stats.properties.get("message_count", {}).get("minimum", 0)
                },
                "word_stats": {
                    "mean": stats.properties.get("word_count", {}).get("mean", 0),
                    "max": stats.properties.get("word_count", {}).get("maximum", 0),
                    "min": stats.properties.get("word_count", {}).get("minimum", 0)
                }
            }

            # Display verification results
            console.print(f"\n[green]✅ Verification Complete:[/green]")
            console.print(f"  Total Documents in Weaviate: {verification['total_documents']}")
            console.print(f"  Average messages per thread: {verification['message_stats']['mean']:.1f}")
            console.print(f"  Average words per thread: {verification['word_stats']['mean']:.1f}")

            return verification

        except Exception as e:
            console.print(f"[red]Verification failed: {e}[/red]")
            return {}


def run_ingestion(
    json_path: Path = None,
    force_reindex: bool = False,
    verify: bool = True,
    incremental: bool = False
):
    """
    Main function to run the complete ingestion pipeline.

    Args:
        json_path: Path to Telegram JSON export
        force_reindex: Whether to skip duplicate checking
        verify: Whether to verify after ingestion
        incremental: Whether to only process new messages since last ingestion
    """
    console.print(Panel.fit(
        "[bold cyan]Telegram RAG - Data Ingestion Pipeline[/bold cyan]\n"
        "This will process your message threads and store them in Weaviate",
        title="Data Ingestion"
    ))

    # Step 1: Connect to Weaviate
    console.print("\n[cyan]Step 1: Connecting to Weaviate...[/cyan]")
    client = weaviate.connect_to_local(
        host=settings.weaviate_host,
        port=settings.weaviate_port,
        grpc_port=50051,
        headers={}
    )

    try:
        # Step 2: Verify schema exists
        console.print("[cyan]Step 2: Verifying schema...[/cyan]")
        schema_manager = WeaviateSchema(client)

        if not schema_manager.collection_exists():
            console.print("[yellow]Collection doesn't exist. Creating...[/yellow]")
            schema_manager.create_collection()
        else:
            console.print("[green]✅ Schema verified[/green]")

        # Step 3: Process Telegram export into threads
        console.print("\n[cyan]Step 3: Processing Telegram messages...[/cyan]")
        threads = process_telegram_export(
            json_path=json_path,
            display_samples=False,  # Don't show samples during ingestion
            analyze=False  # Skip analysis during ingestion
        )

        # Step 4: Filter for incremental updates if requested
        if incremental:
            console.print("\n[cyan]Step 4a: Checking for incremental updates...[/cyan]")
            ingestion = DataIngestion(client)
            latest_timestamp = ingestion.get_latest_timestamp()

            if latest_timestamp:
                console.print(f"[yellow]Latest timestamp in database: {latest_timestamp}[/yellow]")
                original_count = len(threads)
                threads = ingestion.filter_new_threads(threads, latest_timestamp)
                filtered_count = len(threads)
                console.print(f"[green]Filtered to {filtered_count} threads with new messages (from {original_count} total)[/green]")

                if filtered_count == 0:
                    console.print("[yellow]No new messages found. Ingestion complete.[/yellow]")
                    return
            else:
                console.print("[yellow]No existing data found. Performing full ingestion.[/yellow]")

        # Step 4: Prepare documents
        console.print(f"\n[cyan]Step 4: Preparing documents from {len(threads)} threads...[/cyan]")
        if not incremental:  # Create ingestion object if not already created
            ingestion = DataIngestion(client)
        documents = ingestion.prepare_documents(threads)

        # Step 5: Ingest documents
        console.print("\n[cyan]Step 5: Ingesting documents into Weaviate...[/cyan]")
        ingestion.ingest_documents(
            documents,
            skip_existing=not force_reindex
        )

        # Step 6: Display statistics
        console.print("\n[cyan]Step 6: Ingestion complete![/cyan]")
        ingestion.display_stats()

        # Step 7: Verify if requested
        if verify:
            ingestion.verify_ingestion()

        console.print("\n[bold green]✨ Data ingestion complete! Your RAG system is ready for queries.[/bold green]")

    except Exception as e:
        console.print(f"[red]Ingestion failed: {e}[/red]")
        raise

    finally:
        # Always close the client
        client.close()


if __name__ == "__main__":
    """
    Run this file directly to ingest data.
    python ingestion.py
    """
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Telegram data into Weaviate")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reindex all data (ignore existing)"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification after ingestion"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only process messages newer than the latest in database"
    )

    args = parser.parse_args()

    run_ingestion(
        force_reindex=args.force,
        verify=not args.no_verify,
        incremental=args.incremental
    )