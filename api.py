"""
RAG Knowledge Base API

This module provides a FastAPI endpoint for retrieving content from your
Weaviate-based RAG system. Compatible with external integrations.

API Specification:
- POST /retrieval - Retrieve relevant content chunks
- POST /ingest - Trigger incremental data ingestion
- Authentication via Bearer token
- Returns structured content for RAG integrations
"""

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import weaviate
from config import settings
from rich.console import Console
import uvicorn
import subprocess
import asyncio
from pathlib import Path
import json
import shutil
import tempfile

app = FastAPI(
    title="Telegram RAG Knowledge Base API",
    description="RAG retrieval and ingestion API",
    version="1.0.0"
)

console = Console()
security = HTTPBearer()

# Configuration
API_KEY = settings.api_key
if not API_KEY:
    console.print("[red]❌ ERROR: API_KEY not set in environment variables[/red]")
    console.print("[yellow]💡 Please set API_KEY in your .env file[/yellow]")
    console.print("[dim]   Example: API_KEY=$(openssl rand -hex 32)[/dim]")
    exit(1)

KNOWLEDGE_ID = settings.knowledge_id    # Configurable knowledge base ID


class RetrievalSetting(BaseModel):
    """Retrieval configuration parameters"""
    top_k: int = Field(default=3, ge=1, le=20, description="Number of results to return")
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum similarity score")


class RetrievalRequest(BaseModel):
    """Request format for knowledge retrieval"""
    knowledge_id: str = Field(description="Knowledge base identifier")
    query: str = Field(description="Search query")
    retrieval_setting: RetrievalSetting = Field(description="Retrieval parameters")


class ContentChunk(BaseModel):
    """Individual content chunk returned by the API"""
    content: str = Field(description="Text content of the chunk")
    score: float = Field(description="Relevance score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RetrievalResponse(BaseModel):
    """Response format for successful retrieval"""
    records: List[ContentChunk] = Field(description="Retrieved content chunks")


class ErrorResponse(BaseModel):
    """Error response format"""
    error_code: int = Field(description="Error code")
    error_message: str = Field(description="Error description")


class IngestionRequest(BaseModel):
    """Request format for triggering ingestion"""
    incremental: bool = Field(default=True, description="Whether to only process new messages")
    force: bool = Field(default=False, description="Force reindex all data")


class IngestionResponse(BaseModel):
    """Response format for ingestion status"""
    status: str = Field(description="Status of the ingestion")
    message: str = Field(description="Detailed message")
    processed_threads: Optional[int] = Field(default=None, description="Number of threads processed")


class UploadResponse(BaseModel):
    """Response format for file upload"""
    status: str = Field(description="Status of the upload")
    message: str = Field(description="Upload details")
    filename: str = Field(description="Name of uploaded file")
    size: int = Field(description="File size in bytes")
    mode: str = Field(description="Upload mode: replace or merge")
    total_messages: int = Field(description="Total messages after upload")


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify the API key from Authorization header"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                error_code=1002,
                error_message="Authorization failed"
            ).model_dump()
        )
    return True


def search_weaviate(query: str, limit: int, score_threshold: float) -> List[ContentChunk]:
    """
    Search Weaviate for relevant content chunks

    Args:
        query: Search query
        limit: Maximum number of results
        score_threshold: Minimum similarity score

    Returns:
        List of content chunks with scores
    """
    # Connect to Weaviate
    client = weaviate.connect_to_local(
        host=settings.weaviate_host,
        port=settings.weaviate_port,
        grpc_port=50051
    )

    try:
        collection = client.collections.get(settings.collection_name)

        # Perform hybrid search (combines vector and keyword search)
        results = collection.query.hybrid(
            query=query,
            alpha=settings.search_alpha,  # Use configured alpha value
            limit=limit * 2,  # Get more results initially to filter by score
            return_properties=["content", "participants", "thread_id", "message_count", "timestamp"],
            return_metadata=["score"]
        )

        # Convert results to ContentChunk format
        chunks = []
        for result in results.objects:
            # Get the similarity score from metadata
            score = getattr(result.metadata, 'score', 0.0) if hasattr(result.metadata, 'score') else 0.0

            # Apply score threshold filter
            if score >= score_threshold:
                props = result.properties

                # Format content with context
                content = props.get('content', '')
                participants = props.get('participants', [])
                message_count = props.get('message_count', 0)

                # Add context to content
                context_info = f"[Thread with {', '.join(participants[:3])} - {message_count} messages]\n"
                full_content = context_info + content

                chunks.append(ContentChunk(
                    content=full_content,
                    score=score,
                    metadata={
                        "thread_id": props.get('thread_id'),
                        "participants": participants,
                        "message_count": message_count,
                        "timestamp": props.get('timestamp')
                    }
                ))

        # Sort by score (highest first) and limit results
        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:limit]

    finally:
        client.close()


@app.post("/retrieval", response_model=RetrievalResponse)
async def retrieve_knowledge(
    request: RetrievalRequest,
    authorized: bool = Depends(verify_api_key)
) -> RetrievalResponse:
    """
    Retrieve relevant content chunks from the knowledge base

    This endpoint provides RAG retrieval functionality for external integrations.
    """
    try:
        # Validate knowledge ID
        if request.knowledge_id != KNOWLEDGE_ID:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code=2001,
                    error_message="The knowledge base does not exist"
                ).model_dump()
            )

        # Validate query
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code=1003,
                    error_message="Query cannot be empty"
                ).model_dump()
            )

        console.print(f"[cyan]API Request:[/cyan] {request.query}")
        console.print(f"[dim]Parameters: top_k={request.retrieval_setting.top_k}, threshold={request.retrieval_setting.score_threshold}[/dim]")

        # Search for relevant content
        chunks = search_weaviate(
            query=request.query,
            limit=request.retrieval_setting.top_k,
            score_threshold=request.retrieval_setting.score_threshold
        )

        console.print(f"[green]Found {len(chunks)} relevant chunks[/green]")

        return RetrievalResponse(records=chunks)

    except HTTPException:
        raise
    except Exception as e:
        console.print(f"[red]Error during retrieval: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5000,
                error_message=f"Internal server error: {str(e)}"
            ).model_dump()
        )


@app.post("/upload", response_model=UploadResponse)
async def upload_telegram_export(
    file: UploadFile = File(...),
    merge: bool = False,
    chat_name: Optional[str] = None,
    authorized: bool = Depends(verify_api_key)
) -> UploadResponse:
    """
    Upload a new Telegram export file

    Args:
        file: Telegram chat export JSON file
        merge: If True, merge with existing data. If False, replace existing data.
        chat_name: Optional chat identifier for metadata (helps distinguish sources)

    This endpoint accepts a Telegram chat export JSON file and either replaces
    or merges with the existing result.json file used for ingestion.
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code=4001,
                    error_message="File must be a JSON file (.json extension required)"
                ).model_dump()
            )

        # Read and validate JSON content
        content = await file.read()

        try:
            json_data = json.loads(content)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code=4002,
                    error_message=f"Invalid JSON format: {str(e)}"
                ).model_dump()
            )

        # Basic validation - check if it looks like a Telegram export
        if not isinstance(json_data, dict) or 'messages' not in json_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code=4003,
                    error_message="File does not appear to be a Telegram chat export (missing 'messages' field)"
                ).model_dump()
            )

        # Get the target path
        target_path = Path(__file__).parent / "result.json"

        # Handle merge vs replace logic
        if merge and target_path.exists():
            # Load existing data
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=ErrorResponse(
                        error_code=5004,
                        error_message=f"Could not read existing data for merge: {str(e)}"
                    ).model_dump()
                )

            # Merge messages
            existing_messages = existing_data.get('messages', [])
            new_messages = json_data.get('messages', [])

            # Add chat_name to new messages for identification
            if chat_name:
                for msg in new_messages:
                    if isinstance(msg, dict):
                        msg['_source_chat'] = chat_name

            # Combine messages and sort by date
            all_messages = existing_messages + new_messages

            # Create merged data structure
            merged_data = existing_data.copy()
            merged_data['messages'] = all_messages

            # Update metadata
            merged_data['_multi_chat'] = True
            merged_data['_last_updated'] = datetime.now().isoformat()

            final_data = merged_data
            mode = "merge"
            console.print(f"[green]Merging {len(new_messages):,} messages with {len(existing_messages):,} existing[/green]")
        else:
            # Replace mode
            if chat_name:
                # Add chat identifier to all messages
                for msg in json_data.get('messages', []):
                    if isinstance(msg, dict):
                        msg['_source_chat'] = chat_name

            final_data = json_data
            mode = "replace"
            console.print(f"[green]Replacing existing data[/green]")

        # Create backup of existing file if it exists
        if target_path.exists():
            backup_path = target_path.with_suffix('.json.backup')
            shutil.copy2(target_path, backup_path)
            console.print(f"[yellow]Created backup: {backup_path}[/yellow]")

        # Write the final file
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        file_size = len(content)
        total_messages = len(final_data.get('messages', []))
        uploaded_messages = len(json_data.get('messages', []))

        console.print(f"[green]Uploaded {file.filename} ({mode} mode)[/green]")
        console.print(f"[dim]Uploaded: {uploaded_messages:,} messages, Total: {total_messages:,}[/dim]")

        return UploadResponse(
            status="success",
            message=f"Successfully {mode}d {file.filename}: {uploaded_messages:,} messages uploaded, {total_messages:,} total",
            filename=file.filename,
            size=file_size,
            mode=mode,
            total_messages=total_messages
        )

    except HTTPException:
        raise
    except Exception as e:
        console.print(f"[red]Error during file upload: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5003,
                error_message=f"Upload failed: {str(e)}"
            ).model_dump()
        )


@app.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(
    request: IngestionRequest,
    authorized: bool = Depends(verify_api_key)
) -> IngestionResponse:
    """
    Trigger data ingestion from Telegram export

    This endpoint runs the ingestion pipeline to update the knowledge base
    with new or all messages from the Telegram export file.
    """
    try:
        console.print(f"[cyan]API Ingestion Request:[/cyan] incremental={request.incremental}, force={request.force}")

        # Build the command to run ingestion
        cmd = ["python", "ingestion.py"]

        if request.force:
            cmd.append("--force")

        if request.incremental:
            cmd.append("--incremental")

        # Always skip verification for API calls to avoid hanging
        cmd.append("--no-verify")

        console.print(f"[dim]Running command: {' '.join(cmd)}[/dim]")

        # Run the ingestion process
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=Path(__file__).parent
        )

        if result.returncode == 0:
            console.print("[green]Ingestion completed successfully[/green]")

            # Parse output to extract useful information
            output_lines = result.stdout.split('\n')
            processed_info = "Ingestion completed"

            # Look for thread count information in output
            for line in output_lines:
                if "threads" in line.lower() and ("processing" in line.lower() or "prepared" in line.lower()):
                    processed_info = line.strip()
                    break

            return IngestionResponse(
                status="success",
                message=f"Data ingestion completed. {processed_info}",
                processed_threads=None  # Could parse this from output if needed
            )
        else:
            error_msg = result.stderr or result.stdout or "Unknown error occurred"
            console.print(f"[red]Ingestion failed: {error_msg}[/red]")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorResponse(
                    error_code=5001,
                    error_message=f"Ingestion failed: {error_msg}"
                ).model_dump()
            )

    except subprocess.TimeoutExpired:
        console.print("[red]Ingestion timed out[/red]")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=ErrorResponse(
                error_code=4081,
                error_message="Ingestion process timed out"
            ).model_dump()
        )
    except Exception as e:
        console.print(f"[red]Error during ingestion: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5002,
                error_message=f"Internal server error: {str(e)}"
            ).model_dump()
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "knowledge_id": KNOWLEDGE_ID}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Telegram RAG Knowledge Base API",
        "knowledge_id": KNOWLEDGE_ID,
        "endpoints": {
            "retrieval": "/retrieval",
            "upload": "/upload",
            "ingest": "/ingest",
            "health": "/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    """
    Run the API server
    Usage: python api.py
    """
    console.print("[bold cyan]Starting RAG Knowledge Base API Server...[/bold cyan]")
    console.print(f"Knowledge ID: {KNOWLEDGE_ID}")
    console.print(f"API Key required for authentication")
    console.print(f"Connecting to Weaviate at: {settings.weaviate_url}")

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )