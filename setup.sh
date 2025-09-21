#!/bin/bash

# Telegram RAG Knowledge Base - Setup Script
# This script automates the setup process for the RAG system

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    echo -e "${2}${1}${NC}"
}

# Print header
print_header() {
    echo ""
    echo "================================================"
    echo "$1"
    echo "================================================"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup function
main() {
    print_header "📚 Telegram RAG Knowledge Base Setup"

    # Step 1: Check prerequisites
    print_message "\n🔍 Checking prerequisites..." "$BLUE"

    if ! command_exists docker; then
        print_message "❌ Docker is not installed. Please install Docker first." "$RED"
        exit 1
    fi

    if ! command_exists python3; then
        print_message "❌ Python 3 is not installed. Please install Python 3.8+ first." "$RED"
        exit 1
    fi

    print_message "✅ Prerequisites check passed" "$GREEN"

    # Step 2: Setup environment file
    print_message "\n📝 Setting up environment configuration..." "$BLUE"

    if [ ! -f .env ]; then
        cp .env.example .env
        print_message "Created .env file from template" "$GREEN"

        # Generate secure API key
        if command_exists openssl; then
            api_key=$(openssl rand -hex 32)
            sed -i "s/API_KEY=.*/API_KEY=$api_key/" .env
            print_message "✅ Generated secure API key" "$GREEN"
        else
            print_message "⚠️  OpenSSL not found. Please manually set API_KEY in .env" "$YELLOW"
        fi

        # Ask user for provider choice
        echo ""
        echo "Which embedding provider would you like to use?"
        echo "1) Ollama (Local, Free)"
        echo "2) OpenAI (Cloud, Paid)"
        echo "3) OpenRouter (Multiple providers)"
        read -p "Enter choice [1-3]: " provider_choice

        case $provider_choice in
            1)
                sed -i 's/EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=ollama/' .env
                print_message "Set provider to Ollama" "$GREEN"
                ;;
            2)
                sed -i 's/EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=openai/' .env
                print_message "Set provider to OpenAI" "$GREEN"
                print_message "⚠️  Remember to add your OpenAI API key to .env" "$YELLOW"
                ;;
            3)
                sed -i 's/EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=openrouter/' .env
                print_message "Set provider to OpenRouter" "$GREEN"
                print_message "⚠️  Remember to add your OpenRouter API key to .env" "$YELLOW"
                ;;
            *)
                print_message "Invalid choice. Defaulting to Ollama" "$YELLOW"
                sed -i 's/EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=ollama/' .env
                ;;
        esac
    else
        print_message ".env file already exists" "$GREEN"
    fi

    # Step 3: Create Python virtual environment
    print_message "\n🐍 Setting up Python environment..." "$BLUE"

    if [ ! -d venv ]; then
        python3 -m venv venv
        print_message "Created virtual environment" "$GREEN"
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    print_message "Installing Python dependencies..." "$BLUE"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    print_message "✅ Python dependencies installed" "$GREEN"

    # Step 4: Start services with Docker
    print_message "\n🐳 Starting Docker services..." "$BLUE"

    docker-compose up -d

    # Wait for services to be ready
    print_message "Waiting for services to be ready..." "$YELLOW"
    sleep 5

    # Check Weaviate
    if curl -s http://localhost:8080/v1/.well-known/ready > /dev/null; then
        print_message "✅ Weaviate is running" "$GREEN"
    else
        print_message "⚠️  Weaviate is not responding. Check Docker logs." "$YELLOW"
    fi

    # Step 5: Setup Ollama (if selected)
    if grep -q "EMBEDDING_PROVIDER=ollama" .env; then
        print_message "\n🤖 Setting up Ollama..." "$BLUE"

        if command_exists ollama; then
            # Start Ollama service
            ollama serve > /dev/null 2>&1 &
            sleep 2

            # Pull required models
            print_message "Pulling embedding model..." "$BLUE"
            ollama pull nomic-embed-text || true

            print_message "Pulling generation model..." "$BLUE"
            ollama pull llama3.2 || true

            print_message "✅ Ollama setup complete" "$GREEN"
        else
            print_message "⚠️  Ollama is not installed. Please install from https://ollama.ai" "$YELLOW"
        fi
    fi

    # Step 6: Initialize Weaviate schema
    print_message "\n📊 Initializing database schema..." "$BLUE"

    python schema.py

    if [ $? -eq 0 ]; then
        print_message "✅ Schema initialized successfully" "$GREEN"
    else
        print_message "❌ Schema initialization failed" "$RED"
        exit 1
    fi

    # Step 7: Check for data file
    print_message "\n📁 Checking for Telegram data..." "$BLUE"

    if [ -f result.json ]; then
        print_message "✅ Found result.json" "$GREEN"

        read -p "Would you like to process and ingest the data now? (y/n): " ingest_choice

        if [ "$ingest_choice" = "y" ] || [ "$ingest_choice" = "Y" ]; then
            print_message "\n🔄 Processing messages into threads..." "$BLUE"
            python thread_detector.py

            print_message "\n📤 Ingesting data into Weaviate..." "$BLUE"
            python ingestion.py

            print_message "✅ Data ingestion complete" "$GREEN"
        fi
    else
        print_message "⚠️  No result.json found. Please add your Telegram export." "$YELLOW"
    fi

    # Step 8: Start API server
    print_message "\n🌐 Starting API server..." "$BLUE"

    # Kill existing server if running
    pkill -f "api.py" || true

    # Start API server in background
    nohup python api.py > api.log 2>&1 &

    sleep 2

    # Check if API is running
    if curl -s http://localhost:8000/health > /dev/null; then
        print_message "✅ API server is running at http://localhost:8000" "$GREEN"
    else
        print_message "⚠️  API server failed to start. Check api.log for errors." "$YELLOW"
    fi

    # Extract API key for display
    api_key=$(grep "^API_KEY=" .env | cut -d'=' -f2)

    # Final summary
    print_header "✨ Setup Complete!"

    echo ""
    print_message "🎉 Your Telegram RAG Knowledge Base is ready!" "$GREEN"
    echo ""

    print_message "🌐 Access your services:" "$BLUE"
    echo "  📊 Weaviate Database UI:    http://localhost:3000"
    echo "  🚀 FastAPI Documentation:  http://localhost:8000/docs"
    echo "  🔧 Weaviate REST API:      http://localhost:8080"
    echo "  📈 API Health Check:       http://localhost:8000/health"
    echo ""

    print_message "🔑 Your API Key:" "$BLUE"
    if [ -n "$api_key" ]; then
        echo "  $api_key"
        echo ""
        print_message "⚠️  Save this API key securely - you'll need it for API requests!" "$YELLOW"
    else
        print_message "  No API key found. Check your .env file." "$RED"
    fi
    echo ""

    print_message "📋 Next steps:" "$BLUE"
    echo "  1. Open the Weaviate UI at http://localhost:3000 to explore your database"
    echo "  2. Add your Telegram export as result.json (if not done)"
    echo "  3. Run 'python ingestion.py' to process data"
    echo "  4. Test searches at http://localhost:8000/docs"
    echo "  5. Use the API key above for authentication"
    echo ""

    print_message "📚 Documentation & Testing:" "$BLUE"
    echo "  - README.md               # Complete setup guide"
    echo "  - http://localhost:8000/docs  # Interactive API testing"
    echo "  - python test_rag.py     # Command-line testing"
    echo ""

    print_message "🛠️  Management commands:" "$BLUE"
    echo "  - ./stop.sh              # Stop all services"
    echo "  - docker-compose ps      # Check service status"
    echo "  - docker-compose logs -f # View logs"
    echo "  - python config.py       # Verify configuration"
    echo ""

    print_message "Happy knowledge building! 🚀" "$GREEN"
}

# Run main function
main