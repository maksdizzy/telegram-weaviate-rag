"""
Quick RAG Test - Demonstrates the system working with your Telegram data
"""

import weaviate
from config import settings
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import ollama as ollama_client

console = Console()

def search_threads(query: str, limit: int = 3):
    """
    Search for relevant threads using hybrid search
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
            alpha=0.75,  # 75% vector, 25% keyword
            limit=limit,
            return_properties=["content", "participants", "thread_id", "message_count"]
        )

        return results.objects

    finally:
        client.close()

def generate_response(query: str, context: str):
    """
    Generate a response using Ollama with the retrieved context
    """
    # Create the prompt with context
    prompt = f"""You are a helpful assistant answering questions about a Telegram chat.

Based on the following context from the chat history, answer the user's question.
If the answer cannot be found in the context, say so.

Context from Telegram chat:
{context}

User Question: {query}

Answer:"""

    # Generate response using Ollama
    response = ollama_client.generate(
        model=settings.ollama_generation_model,
        prompt=prompt
    )

    return response['response']

def test_rag(query: str):
    """
    Complete RAG pipeline test
    """
    console.print(Panel.fit(
        f"[bold cyan]RAG Query: {query}[/bold cyan]",
        title="Testing RAG System"
    ))

    # Step 1: Search for relevant threads
    console.print("\n[yellow]Step 1: Searching for relevant threads...[/yellow]")
    results = search_threads(query)

    if not results:
        console.print("[red]No relevant threads found![/red]")
        return

    console.print(f"[green]Found {len(results)} relevant threads[/green]\n")

    # Display search results
    for i, result in enumerate(results, 1):
        props = result.properties
        console.print(f"[cyan]Result {i}:[/cyan]")
        console.print(f"  Participants: {', '.join(props.get('participants', [])[:3])}")
        console.print(f"  Messages: {props.get('message_count', 0)}")
        console.print(f"  Preview: {props.get('content', '')[:200]}...")
        console.print()

    # Step 2: Combine context
    console.print("[yellow]Step 2: Combining context from top results...[/yellow]")
    context = "\n\n---\n\n".join([
        f"Thread {i}:\n{result.properties.get('content', '')}"
        for i, result in enumerate(results, 1)
    ])

    context_preview = context[:500] + "..." if len(context) > 500 else context
    console.print(f"[dim]Context length: {len(context)} characters[/dim]\n")

    # Step 3: Generate response
    console.print("[yellow]Step 3: Generating response with Ollama...[/yellow]")
    response = generate_response(query, context)

    # Display the response
    console.print("")
    console.print(Panel(
        Markdown(response),
        title="[bold green]RAG Response[/bold green]",
        border_style="green"
    ))

def main():
    """
    Run interactive RAG tests
    """
    console.print(Panel.fit(
        "[bold cyan]Telegram RAG System - Quick Test[/bold cyan]\n"
        "This demonstrates the complete RAG pipeline with your data",
        title="RAG Test"
    ))

    # Example queries to test
    test_queries = [
        "What has been discussed about Guru Network?",
        "What are people saying about economics?",
        "Has anyone talked about databases or Weaviate?",
        "What questions have people asked recently?",
    ]

    console.print("\n[bold]Example queries you can try:[/bold]")
    for i, q in enumerate(test_queries, 1):
        console.print(f"  {i}. {q}")

    console.print("\n[bold]Enter 'quit' to exit[/bold]\n")

    while True:
        query = console.input("[bold cyan]Enter your question:[/bold cyan] ")

        if query.lower() in ['quit', 'exit', 'q']:
            console.print("[yellow]Goodbye![/yellow]")
            break

        if query.strip():
            try:
                test_rag(query)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        console.print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()