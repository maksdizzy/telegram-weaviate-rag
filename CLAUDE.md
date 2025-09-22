# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a production-ready Telegram RAG (Retrieval-Augmented Generation) Knowledge Base system that processes Telegram chat exports into a searchable vector database. It uses Weaviate for vector storage, supports multiple embedding providers (Ollama, OpenAI, OpenRouter), and provides Dify integration.

## Commands

### Development Setup
```bash
# Initial setup (creates venv, installs deps, configures environment)
./setup.sh

# Stop all services
./stop.sh

# Manual setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
```

### Data Processing Pipeline
```bash
# Process Telegram export into conversation threads
python thread_detector.py

# Ingest processed data into Weaviate
python ingestion.py

# Re-run ingestion without verification (faster)
python ingestion.py --no-verify

# Incremental ingestion (only new messages)
python ingestion.py --incremental

# Test the search functionality
python test_rag.py
```

### API and Services
```bash
# Start RAG Knowledge Base API server
python api.py

# Start with custom port
python api.py --port 8001

# Check configuration and service availability
python config.py

# Check system readiness
python quickstart_check_readiness.py
```

### Docker Operations
```bash
# Start only Weaviate
docker-compose up -d weaviate

# Start full stack (includes monitoring)
docker-compose -f docker-compose.full.yml up -d

# View logs
docker-compose logs -f weaviate
```

### RAG Enhancements
```bash
# Interactive embedding model optimization
python optimize_embeddings.py

# Enable contextual information injection (49% better retrieval)
# Set in .env file:
USE_CONTEXTUAL_CONTENT=true

# Or configure during setup
./setup.sh
```

**Available Enhancements:**
- **Enhanced Metadata**: 16+ new conversation analysis fields
- **Contextual Injection**: Research-backed 49% improvement in retrieval
- **Advanced Embedding Models**: text-embedding-3-large support (64.6 MTEB score)
- **Interactive Optimization**: Easy model switching and performance comparison

### Testing and Validation
```bash
# Interactive search testing
python test_rag.py

# Run comprehensive test suite
python test_data/run_comprehensive_tests.py

# Generate test data
python test_data/generate_large_file.py

# Manual API testing - retrieval
curl -X POST http://localhost:8000/retrieval \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"knowledge_id": "telegram-rag", "query": "test query"}'

# Manual API testing - file upload (replace mode)
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer your_api_key" \
  -F "file=@/path/to/result.json"

# Upload with merge (multi-chat support)
curl -X POST "http://localhost:8000/upload?merge=true&chat_name=family_chat" \
  -H "Authorization: Bearer your_api_key" \
  -F "file=@family_chat.json"

# Manual API testing - ingestion
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true, "force": false}'
```

## Architecture

### Core Components

1. **Configuration System** (`config.py`): Centralized settings management using Pydantic. Loads from environment variables and provides validation.

2. **Data Models** (`models.py`): Pydantic V2 models for:
   - `TelegramMessage`: Raw Telegram message structure
   - `MessageThread`: Grouped conversation threads
   - `WeaviateDocument`: Vector database documents
   - `SearchResult`: Search response format

3. **Thread Detection** (`thread_detector.py`): Groups related messages into conversation threads using:
   - Time-based windows (configurable, default 5 minutes)
   - Reply chain analysis
   - User participation patterns
   - Configurable max messages per thread (default 50)

4. **Schema Management** (`schema.py`): Weaviate V4 schema with:
   - Hybrid search configuration (vector + keyword)
   - Optimized property settings
   - Multi-provider embedding support
   - Automatic schema creation and validation

5. **Provider System** (`providers/`): Abstracted embedding providers:
   - `base.py`: Abstract interface
   - `provider_factory.py`: Factory pattern for provider selection
   - `ollama_provider.py`: Local Ollama integration
   - `openai_provider.py`: OpenAI API integration
   - `openrouter_provider.py`: OpenRouter multi-provider access

6. **Data Ingestion** (`ingestion.py`): Batch processing pipeline:
   - Processes threads into Weaviate documents
   - Configurable batch sizes
   - Progress tracking with Rich
   - Duplicate detection and handling
   - Error handling with statistics

7. **RAG API Server** (`api.py`): FastAPI server providing:
   - `/retrieval` endpoint for content search
   - `/upload` endpoint for new Telegram export files
   - `/ingest` endpoint for triggering data updates
   - Bearer token authentication
   - Health checks and status endpoints
   - Compatible with external RAG integrations

### Data Flow

```
Telegram Export (result.json)
    ↓
Thread Detection (groups related messages)
    ↓
Document Creation (converts to searchable format)
    ↓
Embedding Generation (via selected provider)
    ↓
Weaviate Storage (vector + metadata)
    ↓
RAG API (Search & Ingestion endpoints)
```

### Provider Architecture

The system uses a factory pattern for embedding providers:
- All providers implement `BaseProvider` abstract class
- Provider selection via `EMBEDDING_PROVIDER` environment variable
- Each provider handles its own configuration and error management
- Supports switching providers without code changes

### Configuration Management

Uses Pydantic V2 settings with:
- Environment variable loading (`.env` file support)
- Field validation and type checking
- Connection testing utilities
- Human-readable configuration display

## Key File Relationships

- `config.py` → Imported by all modules for settings
- `models.py` → Used by `thread_detector.py`, `ingestion.py`, `api.py`
- `providers/` → Used by `schema.py` and `ingestion.py` for embeddings
- `schema.py` → Creates Weaviate schema, used by `ingestion.py`
- `thread_detector.py` → Processes raw data for `ingestion.py`
- `api.py` → Provides search and ingestion endpoints

## Environment Variables

Critical environment variables (see `.env.example`):
- `EMBEDDING_PROVIDER`: Choose between ollama/openai/openrouter
- `WEAVIATE_HOST/PORT/SCHEME`: Weaviate connection
- Provider-specific API keys and models
- `BATCH_SIZE`: Processing batch size (affects memory usage)
- `API_KEY`: Authentication for API access (REQUIRED - generate with `openssl rand -hex 32`)

## Important Implementation Details

### Weaviate V4 Client
- Uses `weaviate.connect_to_local()` instead of deprecated `weaviate.Client()`
- Schema creation uses V4 syntax
- Context managers for proper connection handling

### Pydantic V2 Migration
- Uses `@field_validator` decorator (not `@validator`)
- `model_config` dict instead of `Config` class
- `.model_dump()` instead of `.dict()`

### Docker Networking
- Use `host.docker.internal` for container-to-host communication
- Ollama endpoint adjusted for Docker environments in `schema.py`

### Date Handling
- RFC3339 format required for Weaviate timestamps
- Automatic "Z" suffix addition for timezone compliance

### Thread Detection Algorithm
- Time-based grouping with configurable windows
- Handles reply chains and conversation flow
- Maintains participant lists and message counts
- Optimized for performance with large datasets

### File Updates & Multi-Chat Support
- **File upload**: `/upload` endpoint accepts new Telegram export files
- **Multi-chat support**:
  - `merge=true` parameter combines multiple chat exports
  - `chat_name` parameter labels messages by source chat
  - Automatic backup before merging/replacing
- **Replace vs Merge modes**:
  - Replace: Overwrites existing data (default)
  - Merge: Combines new messages with existing ones
- **Validation**: Checks JSON format and Telegram export structure
- **Incremental detection**: `--incremental` flag only processes new messages
- **Timestamp tracking**: Uses latest message timestamp from Weaviate
- **API integration**: `/ingest` endpoint for remote triggering
- **Efficient processing**: Filters threads before expensive embedding generation

## Performance Considerations

- Batch processing: Default 100 documents per batch
- Memory usage: ~2-4GB during ingestion
- Processing speed: ~60 docs/second
- Search latency: <200ms for vector queries
- Thread compression: Typically 2.4:1 ratio (messages to threads)

## Error Handling Patterns

- Rich progress bars for user feedback
- Comprehensive logging with configurable levels
- Graceful degradation for missing services
- Validation errors with helpful messages
- Connection retry logic in providers

Use `python config.py` to verify all services are running before starting development work.