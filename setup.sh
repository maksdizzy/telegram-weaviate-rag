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
        print_message "⚠️  Please edit .env file with your settings" "$YELLOW"

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

    # Final summary
    print_header "✨ Setup Complete!"

    echo ""
    echo "Your Telegram RAG Knowledge Base is ready!"
    echo ""
    echo "📋 Next steps:"
    echo "  1. Review and update .env file if needed"
    echo "  2. Add your Telegram export as result.json (if not done)"
    echo "  3. Run 'python ingestion.py' to process data"
    echo "  4. Access the API at http://localhost:8000"
    echo "  5. Configure your RAG integration with the API endpoint"
    echo ""
    echo "📚 Documentation:"
    echo "  - README.md - General documentation"
    echo "  - docs/ - Detailed guides"
    echo "  - claude_docs/ - Development documentation"
    echo ""
    echo "🛠️  Useful commands:"
    echo "  - ./stop.sh              # Stop all services"
    echo "  - docker-compose ps      # Check service status"
    echo "  - python test_rag.py     # Test the RAG system"
    echo "  - python api.py          # Start API server"
    echo "  - docker-compose logs -f # View logs"
    echo ""

    print_message "Happy knowledge building! 🚀" "$GREEN"
}

# Run main function
main