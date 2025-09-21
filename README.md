# 📚 Telegram RAG Knowledge Base

A production-ready Retrieval-Augmented Generation (RAG) system that transforms Telegram chat exports into a searchable knowledge base. Integrates seamlessly with Dify and supports multiple embedding providers.

## ✨ Features

- 🔍 **Hybrid Search**: Combines semantic and keyword search for optimal results
- 🧵 **Smart Threading**: Groups related messages into conversation threads
- 🤖 **Multi-Provider Support**: Works with Ollama, OpenAI, and OpenRouter
- 🔌 **Dify Integration**: Ready-to-use external knowledge base API
- 📊 **Scalable**: Handles millions of messages efficiently
- 🐳 **Docker Ready**: One-command deployment with Docker Compose

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.8+ (for local development)
- Telegram chat export (JSON format)
- At least 4GB RAM

### One-Command Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/telegram-rag
cd telegram-rag

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your settings

# Start everything with Docker
docker-compose up -d

# Run the setup script
./setup.sh
```

## 📖 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Dify Integration](#dify-integration)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

## Installation

### Option 1: Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Weaviate
docker-compose up -d weaviate

# Configure environment
cp .env.example .env
# Edit .env file

# Run setup
python setup.py
```

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```env
# Weaviate Configuration
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
WEAVIATE_SCHEME=http

# Embedding Provider (choose one)
EMBEDDING_PROVIDER=ollama  # Options: ollama, openai, openrouter

# Ollama Configuration (if using Ollama)
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_GENERATION_MODEL=llama3.2

# OpenAI Configuration (if using OpenAI)
OPENAI_API_KEY=your_api_key_here
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_GENERATION_MODEL=gpt-4-turbo-preview

# OpenRouter Configuration (if using OpenRouter)
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_EMBED_MODEL=openai/text-embedding-3-small
OPENROUTER_GENERATION_MODEL=anthropic/claude-3-haiku

# Application Settings
BATCH_SIZE=100
COLLECTION_NAME=TelegramMessages
THREAD_TIME_WINDOW_MINUTES=5
SEARCH_ALPHA=0.75

# Dify API Settings
DIFY_API_KEY=your_secure_api_key_here
DIFY_API_PORT=8000
```

### Supported Embedding Providers

| Provider | Models | Cost | Speed | Quality |
|----------|--------|------|-------|---------|
| **Ollama** | nomic-embed-text, mxbai-embed-large | Free (local) | Fast | Good |
| **OpenAI** | text-embedding-3-small, text-embedding-3-large | Paid | Fast | Excellent |
| **OpenRouter** | Multiple providers | Paid | Variable | Variable |

## Usage

### 1. Prepare Your Data

Export your Telegram chat:
1. Open Telegram Desktop
2. Settings → Advanced → Export Telegram Data
3. Select "JSON" format
4. Save as `result.json` in the project directory

### 2. Process and Ingest Data

```bash
# Process messages into threads
python thread_detector.py

# Ingest into Weaviate
python ingestion.py

# Verify ingestion
python verify.py
```

### 3. Search Your Knowledge Base

```python
# Interactive search
python search.py

# Test RAG responses
python test_rag.py
```

### 4. Start the API Server

```bash
# For Dify integration
python dify_api.py

# API will be available at http://localhost:8000
```

## Dify Integration

### Configure in Dify

1. Go to Knowledge → External Knowledge
2. Add new knowledge base with:

```yaml
Name: Telegram Knowledge Base
Type: External API
Endpoint: http://your-server:8000/retrieval
Authentication: Bearer Token
Token: your_api_key_from_env
Knowledge ID: telegram-rag
```

### Test the Integration

```bash
curl -X POST http://localhost:8000/retrieval \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_id": "telegram-rag",
    "query": "What has been discussed?",
    "retrieval_setting": {
      "top_k": 5,
      "score_threshold": 0.5
    }
  }'
```

## API Reference

### Endpoints

#### POST /retrieval
Retrieve relevant content from the knowledge base.

**Request:**
```json
{
  "knowledge_id": "telegram-rag",
  "query": "search query",
  "retrieval_setting": {
    "top_k": 5,
    "score_threshold": 0.5
  }
}
```

**Response:**
```json
{
  "records": [
    {
      "content": "Thread content",
      "score": 0.95,
      "metadata": {
        "thread_id": "thread_123",
        "participants": ["Alice", "Bob"],
        "message_count": 5
      }
    }
  ]
}
```

#### GET /health
Check API and database status.

#### GET /stats
Get knowledge base statistics.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Telegram JSON  │────▶│Thread Detector│────▶│  Documents  │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                     │
                                                     ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   Dify/Client   │◀────│   API Server │◀────│  Weaviate   │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                     ▲
                                                     │
                                              ┌─────────────┐
                                              │  Embeddings │
                                              │  Provider   │
                                              └─────────────┘
```

## Project Structure

```
telegram-rag/
├── docker-compose.yml      # Complete stack deployment
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
├── setup.py              # Automated setup script
├── config.py             # Configuration management
├── models.py             # Data models
├── schema.py             # Weaviate schema
├── thread_detector.py    # Message threading
├── ingestion.py          # Data ingestion
├── search.py             # Search interface
├── dify_api.py          # Dify integration API
├── providers/           # Embedding providers
│   ├── base.py
│   ├── ollama.py
│   ├── openai.py
│   └── openrouter.py
├── utils/               # Utility functions
│   ├── logging.py
│   └── validation.py
└── docs/                # Documentation
    ├── SETUP.md
    ├── API.md
    └── TROUBLESHOOTING.md
```

## Performance

- **Ingestion Speed**: ~60 docs/second
- **Search Latency**: <200ms
- **API Response**: <500ms
- **Storage**: ~10MB per 1000 threads
- **Memory Usage**: 2-4GB during ingestion

## Troubleshooting

### Common Issues

#### Weaviate Connection Error
```bash
# Check if Weaviate is running
docker ps | grep weaviate

# Restart Weaviate
docker-compose restart weaviate
```

#### Embedding Provider Issues
```bash
# For Ollama
ollama serve
ollama pull nomic-embed-text

# For OpenAI/OpenRouter
# Check API key and credits
```

#### Slow Performance
- Reduce `BATCH_SIZE` in .env
- Use faster embedding models
- Increase Docker memory allocation

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Weaviate](https://weaviate.io/) vector database
- Supports [Dify](https://dify.ai/) integration
- Compatible with [Ollama](https://ollama.ai/), OpenAI, and OpenRouter

## Support

- 📧 Email: maxim.a.savelyev@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/maksdizzy/telegram-rag/issues)

---

Made with ❤️ for the RAG community