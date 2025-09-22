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
from datetime import datetime

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


class ProcessResponse(BaseModel):
    """Response format for complete upload + processing"""
    status: str = Field(description="Status of the operation")
    message: str = Field(description="Operation details")
    knowledge_id: str = Field(description="Knowledge base identifier")
    uploaded: Dict[str, Any] = Field(description="Upload details")
    processed: Dict[str, Any] = Field(description="Processing details")


class KnowledgeBaseInfo(BaseModel):
    """Information about a knowledge base"""
    knowledge_id: str = Field(description="Knowledge base identifier")
    description: Optional[str] = Field(default=None, description="Knowledge base description")
    total_threads: int = Field(description="Number of conversation threads")
    total_messages: int = Field(description="Number of messages")
    participants: List[str] = Field(description="List of participants")
    date_range: Dict[str, str] = Field(description="Date range of messages")
    storage_size: str = Field(description="Storage size")
    last_updated: str = Field(description="Last update timestamp")


class KnowledgeBaseStats(BaseModel):
    """Statistics for a knowledge base"""
    knowledge_id: str = Field(description="Knowledge base identifier")
    collection_exists: bool = Field(description="Whether the collection exists in Weaviate")
    total_documents: int = Field(description="Total documents in collection")
    total_threads: int = Field(description="Number of conversation threads")
    total_messages: int = Field(description="Number of messages")
    participants: List[str] = Field(description="List of participants")
    date_range: Dict[str, Optional[str]] = Field(description="Date range of messages")
    last_updated: Optional[str] = Field(default=None, description="Last update timestamp")


class CreateKnowledgeBaseRequest(BaseModel):
    """Request to create a new knowledge base"""
    knowledge_id: str = Field(description="Unique identifier for the knowledge base")
    description: Optional[str] = Field(default=None, description="Description of the knowledge base")


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


@app.post("/process", response_model=ProcessResponse)
async def process_telegram_data(
    file: UploadFile = File(...),
    knowledge_id: str = KNOWLEDGE_ID,
    merge: bool = False,
    chat_name: Optional[str] = None,
    incremental: bool = True,
    authorized: bool = Depends(verify_api_key)
) -> ProcessResponse:
    """
    Complete workflow: Upload + Process Telegram data in one step

    This is the main endpoint that combines upload and ingestion into a single operation.
    """
    try:
        console.print(f"[cyan]Processing Telegram data for knowledge base: {knowledge_id}[/cyan]")

        # Step 1: Upload (reuse existing upload logic)
        upload_response = await upload_telegram_export(file, merge, chat_name, authorized)

        # Step 2: Trigger ingestion automatically
        ingest_request = IngestionRequest(incremental=incremental, force=False)
        ingest_response = await trigger_ingestion(ingest_request, authorized)

        return ProcessResponse(
            status="success",
            message=f"Successfully processed {file.filename} for knowledge base '{knowledge_id}'",
            knowledge_id=knowledge_id,
            uploaded={
                "filename": upload_response.filename,
                "mode": upload_response.mode,
                "total_messages": upload_response.total_messages,
                "size": upload_response.size
            },
            processed={
                "status": ingest_response.status,
                "message": ingest_response.message,
                "processed_threads": ingest_response.processed_threads
            }
        )

    except Exception as e:
        console.print(f"[red]Error during processing: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5010,
                error_message=f"Processing failed: {str(e)}"
            ).model_dump()
        )


@app.get("/knowledge-bases", response_model=List[KnowledgeBaseStats])
async def list_knowledge_bases(authorized: bool = Depends(verify_api_key)) -> List[KnowledgeBaseStats]:
    """List all available knowledge bases"""
    try:
        # For now, return the current knowledge base
        # In the future, this would scan for multiple collections

        # Connect to Weaviate
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port,
            grpc_port=50051
        )

        try:
            collection_name = settings.collection_name
            collection_exists = client.collections.exists(collection_name)

            if not collection_exists:
                return []

            # Get basic stats for the knowledge base
            basic_stats = KnowledgeBaseStats(
                knowledge_id=KNOWLEDGE_ID,
                collection_exists=True,
                total_documents=0,
                total_threads=0,
                total_messages=0,
                participants=[],
                date_range={"start": None, "end": None},
                last_updated=datetime.now().isoformat()
            )

            return [basic_stats]

        finally:
            client.close()

    except Exception as e:
        console.print(f"[red]Error listing knowledge bases: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5020,
                error_message=f"Failed to list knowledge bases: {str(e)}"
            ).model_dump()
        )


@app.get("/knowledge-bases/{knowledge_id}/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    knowledge_id: str,
    authorized: bool = Depends(verify_api_key)
) -> KnowledgeBaseStats:
    """Get detailed statistics for a specific knowledge base"""
    try:
        console.print(f"[cyan]Getting stats for knowledge base: {knowledge_id}[/cyan]")

        # Connect to Weaviate
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port,
            grpc_port=50051
        )

        try:
            # Check if collection exists
            collection_name = settings.collection_name
            collection_exists = client.collections.exists(collection_name)

            if not collection_exists:
                return KnowledgeBaseStats(
                    knowledge_id=knowledge_id,
                    collection_exists=False,
                    total_documents=0,
                    total_threads=0,
                    total_messages=0,
                    participants=[],
                    date_range={"start": None, "end": None},
                    last_updated=None
                )

            collection = client.collections.get(collection_name)

            # Get total document count
            result = collection.aggregate.over_all(total_count=True)
            total_documents = result.total_count or 0

            # Get sample data for statistics
            sample_results = collection.query.fetch_objects(
                limit=100,
                return_properties=["participants", "message_count", "timestamp"]
            )

            # Calculate statistics
            all_participants = set()
            total_messages = 0
            dates = []

            for obj in sample_results.objects:
                props = obj.properties
                if props.get('participants'):
                    all_participants.update(props['participants'])
                if props.get('message_count'):
                    total_messages += props['message_count']
                if props.get('timestamp'):
                    dates.append(props['timestamp'])

            # Estimate total messages (extrapolate from sample)
            if len(sample_results.objects) > 0 and total_documents > 100:
                avg_messages_per_thread = total_messages / len(sample_results.objects)
                total_messages = int(avg_messages_per_thread * total_documents)

            date_range = {"start": None, "end": None}
            if dates:
                dates.sort()
                # Convert datetime objects to strings if needed
                start_date = dates[0]
                end_date = dates[-1]
                if hasattr(start_date, 'isoformat'):
                    start_date = start_date.isoformat()
                if hasattr(end_date, 'isoformat'):
                    end_date = end_date.isoformat()
                date_range = {"start": start_date, "end": end_date}

            return KnowledgeBaseStats(
                knowledge_id=knowledge_id,
                collection_exists=True,
                total_documents=total_documents,
                total_threads=total_documents,  # Each document is a thread
                total_messages=total_messages,
                participants=sorted(list(all_participants)),
                date_range=date_range,
                last_updated=datetime.now().isoformat()
            )

        finally:
            client.close()

    except Exception as e:
        console.print(f"[red]Error getting stats: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5021,
                error_message=f"Failed to get stats: {str(e)}"
            ).model_dump()
        )


@app.delete("/knowledge-bases/{knowledge_id}")
async def delete_knowledge_base(
    knowledge_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Delete a knowledge base (clears all data)"""
    try:
        console.print(f"[cyan]Deleting knowledge base: {knowledge_id}[/cyan]")

        # Connect to Weaviate and delete collection
        client = weaviate.connect_to_local(
            host=settings.weaviate_host,
            port=settings.weaviate_port,
            grpc_port=50051
        )

        try:
            collection_name = settings.collection_name
            if client.collections.exists(collection_name):
                client.collections.delete(collection_name)
                console.print(f"[green]Deleted collection: {collection_name}[/green]")

            # Also delete the local result.json file
            result_file = Path(__file__).parent / "result.json"
            if result_file.exists():
                result_file.unlink()
                console.print(f"[green]Deleted result.json file[/green]")

            return {
                "status": "success",
                "message": f"Knowledge base '{knowledge_id}' deleted successfully",
                "knowledge_id": knowledge_id
            }

        finally:
            client.close()

    except Exception as e:
        console.print(f"[red]Error deleting knowledge base: {e}[/red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code=5022,
                error_message=f"Failed to delete knowledge base: {str(e)}"
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
            "process": "/process (NEW - Upload + Process in one step)",
            "retrieval": "/retrieval",
            "knowledge_bases": "/knowledge-bases",
            "stats": "/knowledge-bases/{knowledge_id}/stats",
            "upload": "/upload (Legacy - use /process instead)",
            "ingest": "/ingest (Legacy - use /process instead)",
            "health": "/health",
            "docs": "/docs"
        },
        "recommended_workflow": "Use /process for uploading new data, /retrieval for searching, /knowledge-bases/{id}/stats for monitoring"
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