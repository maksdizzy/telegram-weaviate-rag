"""
Thread Detection Algorithm for Telegram Messages

This module groups related messages into conversation threads.
It uses time windows, participant overlap, and reply chains to identify threads.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
from rich.console import Console
from rich.progress import track
from rich.table import Table

from models import TelegramMessage, MessageThread
from config import settings

console = Console()


class ThreadDetector:
    """
    Detects and groups related messages into conversation threads.

    Threading logic:
    1. Messages within time window belong to same thread
    2. Reply chains stay together
    3. Participant continuity is considered
    4. Service messages can extend threads
    """

    def __init__(
        self,
        time_window_minutes: int = None,
        max_thread_messages: int = None,
        min_thread_messages: int = None
    ):
        """
        Initialize thread detector with configuration.

        Args:
            time_window_minutes: Max minutes between messages in same thread
            max_thread_messages: Maximum messages per thread
            min_thread_messages: Minimum messages to form a thread
        """
        self.time_window = timedelta(
            minutes=time_window_minutes or settings.thread_time_window_minutes
        )
        self.max_messages = max_thread_messages or settings.thread_max_messages
        self.min_messages = min_thread_messages or settings.thread_min_messages

        # Statistics tracking
        self.stats = {
            "total_messages": 0,
            "total_threads": 0,
            "single_message_threads": 0,
            "multi_message_threads": 0,
            "largest_thread": 0,
            "average_thread_size": 0.0
        }

    def load_messages(self, json_path: Path) -> List[TelegramMessage]:
        """
        Load and parse messages from Telegram JSON export.

        Args:
            json_path: Path to the JSON file

        Returns:
            List of parsed TelegramMessage objects
        """
        console.print(f"[cyan]Loading messages from: {json_path}[/cyan]")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        messages = []
        skipped = 0

        # Parse each message
        for msg_data in track(data.get("messages", []), description="Parsing messages"):
            try:
                # Create TelegramMessage object
                message = TelegramMessage(**msg_data)
                messages.append(message)
            except Exception as e:
                # Skip messages that can't be parsed
                skipped += 1
                continue

        console.print(f"[green]✅ Loaded {len(messages)} messages[/green]")
        if skipped > 0:
            console.print(f"[yellow]⚠️  Skipped {skipped} unparseable messages[/yellow]")

        # Sort by timestamp to ensure chronological order
        messages.sort(key=lambda m: m.to_timestamp())

        self.stats["total_messages"] = len(messages)
        return messages

    def should_continue_thread(
        self,
        current_thread: List[TelegramMessage],
        new_message: TelegramMessage,
        reply_map: Dict[int, int]
    ) -> bool:
        """
        Determine if a message should be added to the current thread.

        Decision factors:
        1. Time proximity to last message
        2. Is it a reply to a message in the thread?
        3. Participant overlap
        4. Thread size limit

        Args:
            current_thread: Messages in the current thread
            new_message: Message to potentially add
            reply_map: Map of message IDs to their reply targets

        Returns:
            True if message should be added to current thread
        """
        # Check thread size limit
        if len(current_thread) >= self.max_messages:
            return False

        # Empty thread always accepts first message
        if not current_thread:
            return True

        last_message = current_thread[-1]

        # Check time window
        time_diff = new_message.to_timestamp() - last_message.to_timestamp()
        if time_diff > self.time_window:
            return False

        # Check if it's a reply to any message in the thread
        if new_message.reply_to_message_id:
            thread_ids = {msg.id for msg in current_thread}
            if new_message.reply_to_message_id in thread_ids:
                return True

        # Check if any message in thread replies to this message
        if new_message.id in reply_map:
            thread_ids = {msg.id for msg in current_thread}
            if reply_map[new_message.id] in thread_ids:
                return True

        # For service messages, be more lenient (they often relate to ongoing activity)
        if new_message.type.value == "service":
            # Service messages within time window stay in thread
            return time_diff <= self.time_window

        # Check participant continuity
        thread_participants = set()
        for msg in current_thread:
            thread_participants.add(msg.get_sender_name())

        # If the same person is continuing to talk, likely same thread
        if new_message.get_sender_name() in thread_participants:
            return True

        # If it's a different person but within 2 minutes, likely a response
        if time_diff <= timedelta(minutes=2):
            return True

        return False

    def detect_threads(self, messages: List[TelegramMessage]) -> List[MessageThread]:
        """
        Group messages into conversation threads.

        This is the main algorithm that creates threads from messages.

        Args:
            messages: List of messages sorted chronologically

        Returns:
            List of MessageThread objects
        """
        console.print("[cyan]Detecting conversation threads...[/cyan]")

        # Build reply map for faster lookup
        reply_map = {}
        for msg in messages:
            if msg.reply_to_message_id:
                reply_map[msg.id] = msg.reply_to_message_id

        threads = []
        current_thread_messages = []

        # Process each message
        for message in track(messages, description="Creating threads"):
            # Check if message should continue current thread
            if self.should_continue_thread(current_thread_messages, message, reply_map):
                current_thread_messages.append(message)
            else:
                # Save current thread if it has messages
                if current_thread_messages:
                    thread = self.create_thread(current_thread_messages)
                    threads.append(thread)

                # Start new thread with current message
                current_thread_messages = [message]

        # Don't forget the last thread
        if current_thread_messages:
            thread = self.create_thread(current_thread_messages)
            threads.append(thread)

        # Update statistics
        self.stats["total_threads"] = len(threads)
        self.calculate_thread_stats(threads)

        console.print(f"[green]✅ Created {len(threads)} threads from {len(messages)} messages[/green]")

        return threads

    def create_thread(self, messages: List[TelegramMessage]) -> MessageThread:
        """
        Create a MessageThread from a list of messages.

        Args:
            messages: Messages belonging to the thread

        Returns:
            MessageThread object
        """
        # Get unique participants
        participants = list(set(msg.get_sender_name() for msg in messages))

        # Get time range
        start_time = messages[0].to_timestamp()
        end_time = messages[-1].to_timestamp()

        # Generate thread ID based on start time and first message
        thread_id = f"thread_{start_time.strftime('%Y%m%d_%H%M%S')}_{messages[0].id}"

        return MessageThread(
            thread_id=thread_id,
            messages=messages,
            start_time=start_time,
            end_time=end_time,
            participants=participants,
            message_count=len(messages)
        )

    def calculate_thread_stats(self, threads: List[MessageThread]):
        """
        Calculate statistics about the detected threads.

        Args:
            threads: List of detected threads
        """
        if not threads:
            return

        thread_sizes = [thread.message_count for thread in threads]

        self.stats["single_message_threads"] = sum(1 for size in thread_sizes if size == 1)
        self.stats["multi_message_threads"] = sum(1 for size in thread_sizes if size > 1)
        self.stats["largest_thread"] = max(thread_sizes)
        self.stats["average_thread_size"] = sum(thread_sizes) / len(thread_sizes)

    def display_stats(self):
        """
        Display statistics about thread detection.
        """
        table = Table(title="Thread Detection Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Messages", str(self.stats["total_messages"]))
        table.add_row("Total Threads", str(self.stats["total_threads"]))
        table.add_row("Single Message Threads", str(self.stats["single_message_threads"]))
        table.add_row("Multi-Message Threads", str(self.stats["multi_message_threads"]))
        table.add_row("Largest Thread", f"{self.stats['largest_thread']} messages")
        table.add_row("Average Thread Size", f"{self.stats['average_thread_size']:.1f} messages")

        if self.stats["total_threads"] > 0:
            compression_ratio = self.stats["total_messages"] / self.stats["total_threads"]
            table.add_row("Compression Ratio", f"{compression_ratio:.1f}:1")

        console.print(table)

    def display_thread_samples(self, threads: List[MessageThread], count: int = 3):
        """
        Display sample threads for inspection.

        Args:
            threads: List of threads
            count: Number of samples to show
        """
        console.print(f"\n[bold]Sample Threads (showing {count}):[/bold]\n")

        # Show a mix of thread sizes
        samples = []

        # Get one single-message thread
        single = next((t for t in threads if t.message_count == 1), None)
        if single:
            samples.append(single)

        # Get largest thread
        largest = max(threads, key=lambda t: t.message_count)
        if largest not in samples:
            samples.append(largest)

        # Get a medium-sized thread
        medium_threads = [t for t in threads if 2 < t.message_count < 10]
        if medium_threads and len(samples) < count:
            samples.append(medium_threads[0])

        # Display each sample
        for i, thread in enumerate(samples[:count], 1):
            console.print(f"[yellow]Sample Thread {i}:[/yellow]")
            console.print(f"  Thread ID: {thread.thread_id}")
            console.print(f"  Messages: {thread.message_count}")
            console.print(f"  Duration: {(thread.end_time - thread.start_time).total_seconds():.0f} seconds")
            console.print(f"  Participants: {', '.join(thread.participants[:3])}")

            # Show preview of conversation
            preview = thread.get_combined_content()[:300]
            console.print(f"  Preview: {preview}...")
            console.print()

    def analyze_optimal_settings(self, messages: List[TelegramMessage]) -> Dict[str, Any]:
        """
        Analyze messages to suggest optimal threading parameters.

        This helps tune the time window and other settings.

        Args:
            messages: List of messages to analyze

        Returns:
            Dictionary with suggested settings
        """
        console.print("\n[cyan]Analyzing message patterns for optimal settings...[/cyan]")

        # Calculate time gaps between messages
        time_gaps = []
        for i in range(1, len(messages)):
            gap = (messages[i].to_timestamp() - messages[i-1].to_timestamp()).total_seconds()
            time_gaps.append(gap)

        if not time_gaps:
            return {}

        # Calculate statistics
        time_gaps.sort()
        median_gap = time_gaps[len(time_gaps) // 2]

        # Find natural conversation breaks (large gaps)
        # Use 75th percentile as a threshold
        percentile_75 = time_gaps[int(len(time_gaps) * 0.75)]

        # Suggest time window based on gaps
        suggested_window = min(
            max(percentile_75 / 60, 2),  # At least 2 minutes
            30  # Max 30 minutes
        )

        # Count reply chains
        reply_count = sum(1 for msg in messages if msg.reply_to_message_id)
        reply_percentage = (reply_count / len(messages)) * 100 if messages else 0

        suggestions = {
            "median_gap_seconds": median_gap,
            "75th_percentile_seconds": percentile_75,
            "suggested_time_window_minutes": round(suggested_window, 1),
            "reply_percentage": round(reply_percentage, 1),
            "total_participants": len(set(msg.get_sender_name() for msg in messages))
        }

        # Display suggestions
        console.print("\n[bold]Suggested Settings:[/bold]")
        console.print(f"  Time Window: {suggestions['suggested_time_window_minutes']} minutes")
        console.print(f"  Reply Usage: {suggestions['reply_percentage']}% of messages are replies")
        console.print(f"  Total Participants: {suggestions['total_participants']}")

        return suggestions


def process_telegram_export(
    json_path: Path = None,
    display_samples: bool = True,
    analyze: bool = True
) -> List[MessageThread]:
    """
    Main function to process Telegram export and create threads.

    Args:
        json_path: Path to Telegram JSON export
        display_samples: Whether to show sample threads
        analyze: Whether to analyze for optimal settings

    Returns:
        List of detected threads
    """
    json_path = json_path or settings.telegram_json_path

    # Create detector
    detector = ThreadDetector()

    # Load messages
    messages = detector.load_messages(json_path)

    # Analyze patterns if requested
    if analyze:
        detector.analyze_optimal_settings(messages)

    # Detect threads
    threads = detector.detect_threads(messages)

    # Display statistics
    detector.display_stats()

    # Show samples if requested
    if display_samples:
        detector.display_thread_samples(threads)

    return threads


if __name__ == "__main__":
    """
    Run this file directly to test thread detection.
    python thread_detector.py
    """
    threads = process_telegram_export()
    console.print(f"\n[green]Thread detection complete! Ready for ingestion.[/green]")