#!/bin/bash

# Telegram RAG Knowledge Base - Stop Script
# This script stops all running services for the RAG system

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

# Main stop function
main() {
    print_header "🛑 Stopping Telegram RAG Knowledge Base"

    # Stop API server
    print_message "\n🌐 Stopping API server..." "$BLUE"

    # Kill API server processes
    if pkill -f "api.py"; then
        print_message "✅ API server stopped" "$GREEN"
    else
        print_message "⚠️  No API server processes found" "$YELLOW"
    fi

    # Stop Docker services
    print_message "\n🐳 Stopping Docker services..." "$BLUE"

    # Check for different compose files and stop them
    services_stopped=false

    if [ -f docker-compose.yml ]; then
        docker-compose down
        print_message "✅ Basic Docker services stopped" "$GREEN"
        services_stopped=true
    fi

    if [ -f docker-compose.full.yml ]; then
        docker-compose -f docker-compose.full.yml down
        print_message "✅ Full stack Docker services stopped" "$GREEN"
        services_stopped=true
    fi

    if [ "$services_stopped" = false ]; then
        print_message "⚠️  No docker-compose files found" "$YELLOW"
    fi

    # Stop Ollama if running
    print_message "\n🤖 Stopping Ollama..." "$BLUE"

    if pkill -f "ollama serve"; then
        print_message "✅ Ollama stopped" "$GREEN"
    else
        print_message "⚠️  No Ollama processes found" "$YELLOW"
    fi

    # Show remaining processes (optional cleanup check)
    print_message "\n🔍 Checking for remaining processes..." "$BLUE"

    remaining=$(ps aux | grep -E "(api\.py|ollama|weaviate)" | grep -v grep | wc -l)
    if [ "$remaining" -gt 0 ]; then
        print_message "⚠️  Some processes may still be running:" "$YELLOW"
        ps aux | grep -E "(api\.py|ollama|weaviate)" | grep -v grep || true
        echo ""
        print_message "💡 Use 'docker ps' to check Docker containers" "$BLUE"
        print_message "💡 Use 'ps aux | grep api.py' to check API processes" "$BLUE"
    else
        print_message "✅ All processes stopped" "$GREEN"
    fi

    # Final summary
    print_header "✅ Shutdown Complete!"

    echo ""
    echo "All Telegram RAG services have been stopped."
    echo ""
    echo "📋 What was stopped:"
    echo "  ✅ API server (api.py)"
    echo "  ✅ Weaviate database"
    echo "  ✅ Docker services"
    echo "  ✅ Ollama (if running)"
    echo ""
    echo "🔄 To restart the system:"
    echo "  ./setup.sh        # Full setup and start"
    echo "  docker-compose up # Just start services"
    echo "  python api.py     # Just start API"
    echo ""

    print_message "System stopped successfully! 🛑" "$GREEN"
}

# Run main function
main "$@"