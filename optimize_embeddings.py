#!/usr/bin/env python3
"""
Embedding Model Optimization Utility

This utility helps optimize embedding model selection based on research findings.
Provides easy switching between embedding models and performance comparisons.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

# Research-based model performance data (MTEB 2024-2025)
EMBEDDING_MODELS = {
    "text-embedding-3-large": {
        "provider": "OpenAI",
        "mteb_score": 64.6,
        "dimensions": 3072,
        "cost_per_1k": 0.00013,
        "speed": "Fast",
        "quality": "Excellent",
        "recommended_for": "Production, High-quality search",
        "research_notes": "54.9% improvement over ada-002, strong conversational understanding"
    },
    "text-embedding-3-small": {
        "provider": "OpenAI",
        "mteb_score": 62.3,
        "dimensions": 1536,
        "cost_per_1k": 0.00002,
        "speed": "Very Fast",
        "quality": "Good",
        "recommended_for": "Development, Cost-sensitive deployments",
        "research_notes": "Good balance of speed and quality, 6.5x cheaper than large"
    },
    "nomic-embed-text": {
        "provider": "Ollama",
        "mteb_score": 62.4,
        "dimensions": 768,
        "cost_per_1k": 0.0,
        "speed": "Medium",
        "quality": "Good",
        "recommended_for": "Local deployment, Privacy-focused",
        "research_notes": "Best open-source option, runs locally"
    }
}

def display_model_comparison():
    """Display comprehensive model comparison table"""
    console.print("\n🔍 Embedding Model Performance Comparison", style="bold blue")
    console.print("Based on 2024-2025 MTEB benchmarks and research findings\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Provider", style="green")
    table.add_column("MTEB Score", justify="center")
    table.add_column("Dimensions", justify="center")
    table.add_column("Cost/1K tokens", justify="right")
    table.add_column("Speed", justify="center")
    table.add_column("Quality", justify="center")
    table.add_column("Best For", style="yellow")

    for model, data in EMBEDDING_MODELS.items():
        cost_display = f"${data['cost_per_1k']:.5f}" if data['cost_per_1k'] > 0 else "Free"
        table.add_row(
            model,
            data["provider"],
            f"{data['mteb_score']:.1f}",
            str(data["dimensions"]),
            cost_display,
            data["speed"],
            data["quality"],
            data["recommended_for"]
        )

    console.print(table)

    # Research insights
    console.print("\n📊 Key Research Findings:", style="bold green")
    console.print("• text-embedding-3-large: 30-50% better retrieval precision")
    console.print("• Best for conversational data and complex queries")
    console.print("• 6.5x more expensive but significantly better quality")
    console.print("• Recommended for production RAG systems")

def get_current_config() -> Dict[str, str]:
    """Get current embedding configuration"""
    env_file = Path(".env")
    if not env_file.exists():
        console.print("❌ .env file not found", style="red")
        return {}

    config = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('EMBEDDING_PROVIDER='):
                config['provider'] = line.split('=', 1)[1]
            elif line.startswith('OPENAI_EMBED_MODEL='):
                config['openai_model'] = line.split('=', 1)[1]
            elif line.startswith('OLLAMA_EMBED_MODEL='):
                config['ollama_model'] = line.split('=', 1)[1]

    return config

def display_current_config():
    """Display current embedding configuration"""
    config = get_current_config()
    if not config:
        return

    console.print("\n⚙️  Current Configuration:", style="bold blue")
    panel_content = f"""
Provider: {config.get('provider', 'Not set')}
OpenAI Model: {config.get('openai_model', 'Not set')}
Ollama Model: {config.get('ollama_model', 'Not set')}
"""
    console.print(Panel(panel_content, title="Current Settings", border_style="blue"))

def backup_env_file():
    """Create backup of .env file"""
    env_file = Path(".env")
    backup_file = Path(".env.backup")

    if env_file.exists():
        shutil.copy2(env_file, backup_file)
        console.print(f"✅ Backup created: {backup_file}", style="green")

def update_embedding_model(new_model: str, provider: str = "openai"):
    """Update embedding model in .env file"""
    env_file = Path(".env")
    if not env_file.exists():
        console.print("❌ .env file not found", style="red")
        return False

    # Read current content
    with open(env_file, 'r') as f:
        lines = f.readlines()

    # Update the appropriate line
    updated = False
    for i, line in enumerate(lines):
        if provider == "openai" and line.startswith('OPENAI_EMBED_MODEL='):
            lines[i] = f"OPENAI_EMBED_MODEL={new_model}\n"
            updated = True
        elif provider == "ollama" and line.startswith('OLLAMA_EMBED_MODEL='):
            lines[i] = f"OLLAMA_EMBED_MODEL={new_model}\n"
            updated = True

    if updated:
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(lines)
        console.print(f"✅ Updated {provider.upper()}_EMBED_MODEL to {new_model}", style="green")
        return True
    else:
        console.print(f"❌ Could not find {provider.upper()}_EMBED_MODEL in .env", style="red")
        return False

def recommend_model_for_use_case():
    """Provide model recommendations based on use case"""
    console.print("\n🎯 Model Recommendation Wizard", style="bold blue")

    use_cases = {
        "1": ("Production deployment with high quality requirements", "text-embedding-3-large"),
        "2": ("Development and testing", "text-embedding-3-small"),
        "3": ("Cost-sensitive production deployment", "text-embedding-3-small"),
        "4": ("Local/private deployment", "nomic-embed-text"),
        "5": ("Maximum search quality (cost not a concern)", "text-embedding-3-large")
    }

    console.print("\nSelect your use case:")
    for key, (description, _) in use_cases.items():
        console.print(f"  {key}. {description}")

    choice = Prompt.ask("\nEnter your choice", choices=list(use_cases.keys()))
    description, recommended_model = use_cases[choice]

    model_info = EMBEDDING_MODELS[recommended_model]

    console.print(f"\n🎯 Recommended: {recommended_model}", style="bold green")
    console.print(f"Reason: {model_info['research_notes']}")
    console.print(f"Quality: {model_info['quality']} (MTEB: {model_info['mteb_score']})")
    console.print(f"Cost: ${model_info['cost_per_1k']:.5f} per 1K tokens" if model_info['cost_per_1k'] > 0 else "Cost: Free (local)")

    return recommended_model

def main():
    """Main optimization utility"""
    console.print("🚀 Telegram RAG Embedding Optimization Utility", style="bold cyan")
    console.print("Based on 2024-2025 research findings for optimal RAG performance\n")

    while True:
        console.print("\n📋 Available Actions:", style="bold")
        console.print("1. 📊 View model comparison")
        console.print("2. ⚙️  Show current configuration")
        console.print("3. 🎯 Get model recommendation")
        console.print("4. 🔄 Switch to text-embedding-3-large (recommended)")
        console.print("5. 🔄 Switch to text-embedding-3-small (cost-effective)")
        console.print("6. 🏠 Switch to local Ollama model")
        console.print("7. ❌ Exit")

        choice = Prompt.ask("\nSelect an action", choices=["1", "2", "3", "4", "5", "6", "7"])

        if choice == "1":
            display_model_comparison()
        elif choice == "2":
            display_current_config()
        elif choice == "3":
            recommended = recommend_model_for_use_case()
            if Confirm.ask(f"\nWould you like to switch to {recommended}?"):
                backup_env_file()
                provider = "openai" if "text-embedding" in recommended else "ollama"
                update_embedding_model(recommended, provider)
        elif choice == "4":
            if Confirm.ask("Switch to text-embedding-3-large for better quality?"):
                backup_env_file()
                update_embedding_model("text-embedding-3-large", "openai")
        elif choice == "5":
            if Confirm.ask("Switch to text-embedding-3-small for cost efficiency?"):
                backup_env_file()
                update_embedding_model("text-embedding-3-small", "openai")
        elif choice == "6":
            if Confirm.ask("Switch to local Ollama model (nomic-embed-text)?"):
                backup_env_file()
                update_embedding_model("nomic-embed-text", "ollama")
                console.print("⚠️  Remember to set EMBEDDING_PROVIDER=ollama", style="yellow")
        elif choice == "7":
            break

    console.print("\n✨ Optimization complete! Restart your services to apply changes.", style="bold green")

if __name__ == "__main__":
    main()