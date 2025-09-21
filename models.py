"""
Data Models for Telegram RAG System

This module defines the data structures we'll use throughout the application.
We use Pydantic for data validation and type safety.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class MessageType(str, Enum):
    """
    Enum for different types of Telegram messages.
    This helps us handle different message types consistently.
    """
    MESSAGE = "message"          # Regular user messages
    SERVICE = "service"          # System messages (joins, leaves, etc.)


class ServiceAction(str, Enum):
    """
    Common service actions in Telegram.
    We'll convert these to human-readable descriptions.
    """
    CREATE_CHANNEL = "create_channel"
    JOIN_CHANNEL = "join_channel"
    LEAVE_CHANNEL = "leave_channel"
    EDIT_GROUP_PHOTO = "edit_group_photo"
    PIN_MESSAGE = "pin_message"
    INVITE_MEMBERS = "invite_members"
    MIGRATE_FROM_GROUP = "migrate_from_group"
    MIGRATE_TO_SUPERGROUP = "migrate_to_supergroup"


class TelegramMessage(BaseModel):
    """
    Represents a single message from the Telegram export.
    This model matches the structure of messages in result.json.
    """
    id: int
    type: MessageType
    date: str
    date_unixtime: str

    # For regular messages
    from_name: Optional[str] = Field(None, alias="from")
    from_id: Optional[str] = None
    text: Optional[str] = ""
    text_entities: Optional[List[Dict[str, Any]]] = []

    # For service messages
    actor: Optional[str] = None
    actor_id: Optional[str] = None
    action: Optional[str] = None

    # Reply information (if message is a reply)
    reply_to_message_id: Optional[int] = None

    model_config = {
        "populate_by_name": True  # Allows 'from' to map to 'from_name'
    }

    @field_validator('text', mode='before')
    @classmethod
    def ensure_text_not_none(cls, v):
        """Ensure text is never None, default to empty string"""
        return v or ""

    def get_sender_name(self) -> str:
        """Get sender name regardless of message type"""
        if self.type == MessageType.MESSAGE:
            return self.from_name or "Unknown"
        else:
            return self.actor or "System"

    def get_sender_id(self) -> str:
        """Get sender ID regardless of message type"""
        if self.type == MessageType.MESSAGE:
            return self.from_id or "unknown"
        else:
            return self.actor_id or "system"

    def get_readable_content(self) -> str:
        """
        Convert message to human-readable text.
        For service messages, create a description of the action.
        """
        if self.type == MessageType.MESSAGE:
            return self.text
        else:
            # Convert service actions to readable descriptions
            action_descriptions = {
                "create_channel": f"{self.actor} created the channel",
                "join_channel": f"{self.actor} joined the channel",
                "leave_channel": f"{self.actor} left the channel",
                "edit_group_photo": f"{self.actor} changed the group photo",
                "pin_message": f"{self.actor} pinned a message",
                "invite_members": f"{self.actor} invited new members",
            }
            return action_descriptions.get(self.action, f"{self.actor} performed {self.action}")

    def to_timestamp(self) -> datetime:
        """Convert Unix timestamp to datetime object"""
        return datetime.fromtimestamp(int(self.date_unixtime))


class MessageThread(BaseModel):
    """
    Represents a conversation thread - multiple related messages grouped together.
    This is what we'll store in Weaviate for better context.
    """
    thread_id: str = Field(..., description="Unique identifier for the thread")
    messages: List[TelegramMessage] = Field(..., description="Messages in this thread")
    start_time: datetime = Field(..., description="When the thread started")
    end_time: datetime = Field(..., description="When the thread ended")
    participants: List[str] = Field(..., description="Unique participants in thread")
    message_count: int = Field(..., description="Number of messages in thread")

    def get_combined_content(self) -> str:
        """
        Combine all messages into a single text block for vectorization.
        Format: [timestamp] sender: message
        """
        lines = []
        for msg in self.messages:
            timestamp = msg.to_timestamp().strftime("%Y-%m-%d %H:%M:%S")
            sender = msg.get_sender_name()
            content = msg.get_readable_content()
            lines.append(f"[{timestamp}] {sender}: {content}")
        return "\n".join(lines)

    def get_thread_summary(self) -> Dict[str, Any]:
        """
        Create a summary of the thread for metadata.
        """
        return {
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "participant_count": len(self.participants),
            "has_questions": any("?" in msg.text for msg in self.messages if msg.text),
            "has_links": any("http" in msg.text for msg in self.messages if msg.text),
            "message_types": list(set(msg.type.value for msg in self.messages)),
        }

    @classmethod
    def from_single_message(cls, message: TelegramMessage) -> "MessageThread":
        """
        Create a thread from a single message.
        Used when a message doesn't belong to any conversation.
        """
        timestamp = message.to_timestamp()
        return cls(
            thread_id=f"single_{message.id}",
            messages=[message],
            start_time=timestamp,
            end_time=timestamp,
            participants=[message.get_sender_name()],
            message_count=1
        )


class WeaviateDocument(BaseModel):
    """
    The final structure we'll store in Weaviate.
    This combines thread content with searchable metadata.
    """
    # Primary content for vector search
    content: str = Field(..., description="Combined text content for embedding")

    # Thread information
    thread_id: str = Field(..., description="Unique thread identifier")
    message_count: int = Field(..., description="Number of messages in thread")
    participants: List[str] = Field(..., description="List of participants")

    # Temporal data
    timestamp: datetime = Field(..., description="Thread start time")
    duration_seconds: float = Field(..., description="Thread duration")

    # Message type info
    message_types: List[str] = Field(..., description="Types of messages in thread")
    has_service_messages: bool = Field(..., description="Contains system messages")

    # Content analysis
    has_questions: bool = Field(..., description="Contains questions")
    has_links: bool = Field(..., description="Contains URLs")
    word_count: int = Field(..., description="Total word count")

    # Original messages (for reference)
    raw_messages: List[Dict[str, Any]] = Field(..., description="Original message data")

    @classmethod
    def from_thread(cls, thread: MessageThread) -> "WeaviateDocument":
        """
        Convert a MessageThread to a WeaviateDocument.
        This prepares the data for insertion into Weaviate.
        """
        content = thread.get_combined_content()
        summary = thread.get_thread_summary()

        return cls(
            content=content,
            thread_id=thread.thread_id,
            message_count=thread.message_count,
            participants=thread.participants,
            timestamp=thread.start_time,
            duration_seconds=summary["duration_seconds"],
            message_types=summary["message_types"],
            has_service_messages="service" in summary["message_types"],
            has_questions=summary["has_questions"],
            has_links=summary["has_links"],
            word_count=len(content.split()),
            raw_messages=[msg.model_dump() for msg in thread.messages]
        )

    def to_weaviate_object(self) -> Dict[str, Any]:
        """
        Convert to format suitable for Weaviate insertion.
        Weaviate expects specific field types.
        """
        # Ensure RFC3339 format with timezone (Z for UTC)
        timestamp_rfc3339 = self.timestamp.isoformat() + "Z" if not self.timestamp.isoformat().endswith("Z") else self.timestamp.isoformat()

        return {
            "content": self.content,
            "thread_id": self.thread_id,
            "message_count": self.message_count,
            "participants": self.participants,
            "timestamp": timestamp_rfc3339,
            "duration_seconds": self.duration_seconds,
            "message_types": self.message_types,
            "has_service_messages": self.has_service_messages,
            "has_questions": self.has_questions,
            "has_links": self.has_links,
            "word_count": self.word_count,
            # Store raw messages as JSON string
            "raw_messages": str(self.raw_messages)
        }


class SearchResult(BaseModel):
    """
    Represents a search result from Weaviate.
    Includes the document and relevance score.
    """
    document: WeaviateDocument
    score: float = Field(..., description="Relevance score (0-1)")
    distance: float = Field(..., description="Vector distance")

    def display_summary(self) -> str:
        """
        Create a human-readable summary of the search result.
        """
        return f"""
Thread from {self.document.timestamp.strftime('%Y-%m-%d %H:%M')}
Participants: {', '.join(self.document.participants[:3])}
Messages: {self.document.message_count}
Relevance: {self.score:.2%}
Preview: {self.document.content[:200]}...
"""