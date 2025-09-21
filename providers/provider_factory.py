"""
Factory for creating embedding/generation providers
"""

import os
from typing import Dict, Any, Optional
import logging
from .base import BaseProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


def get_provider(provider_name: Optional[str] = None) -> BaseProvider:
    """
    Factory function to get the appropriate provider

    Args:
        provider_name: Name of the provider (ollama, openai, openrouter)
                      If None, uses EMBEDDING_PROVIDER env variable

    Returns:
        Instance of the appropriate provider
    """
    # Get provider name from environment if not specified
    if provider_name is None:
        provider_name = os.getenv('EMBEDDING_PROVIDER', 'ollama').lower()

    logger.info(f"Initializing {provider_name} provider")

    # Create configuration from environment variables
    if provider_name == 'ollama':
        config = {
            'host': os.getenv('OLLAMA_HOST', 'localhost'),
            'port': int(os.getenv('OLLAMA_PORT', 11434)),
            'embed_model': os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text'),
            'generation_model': os.getenv('OLLAMA_GENERATION_MODEL', 'llama3.2')
        }
        return OllamaProvider(config)

    elif provider_name == 'openai':
        config = {
            'api_key': os.getenv('OPENAI_API_KEY'),
            'embed_model': os.getenv('OPENAI_EMBED_MODEL', 'text-embedding-3-small'),
            'generation_model': os.getenv('OPENAI_GENERATION_MODEL', 'gpt-4-turbo-preview')
        }
        return OpenAIProvider(config)

    elif provider_name == 'openrouter':
        config = {
            'api_key': os.getenv('OPENROUTER_API_KEY'),
            'embed_model': os.getenv('OPENROUTER_EMBED_MODEL', 'openai/text-embedding-3-small'),
            'generation_model': os.getenv('OPENROUTER_GENERATION_MODEL', 'anthropic/claude-3-haiku')
        }
        return OpenRouterProvider(config)

    else:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: ollama, openai, openrouter")


def get_provider_info() -> Dict[str, Any]:
    """
    Get information about the current provider

    Returns:
        Dictionary with provider information
    """
    try:
        provider = get_provider()
        info = provider.get_info()
        info['available'] = provider.is_available()
        return info
    except Exception as e:
        logger.error(f"Failed to get provider info: {e}")
        return {
            'error': str(e),
            'available': False
        }


def test_provider(provider_name: Optional[str] = None) -> bool:
    """
    Test if a provider is properly configured and available

    Args:
        provider_name: Name of the provider to test

    Returns:
        True if provider is working
    """
    try:
        provider = get_provider(provider_name)

        # Test availability
        if not provider.is_available():
            logger.error(f"{provider.name} is not available")
            return False

        # Test embedding
        test_text = "This is a test message"
        embedding = provider.embed_text(test_text)

        if not embedding or len(embedding) != provider.embedding_dimension:
            logger.error(f"Invalid embedding from {provider.name}")
            return False

        # Test generation
        response = provider.generate("Say 'test successful' and nothing else")

        if not response:
            logger.error(f"No generation response from {provider.name}")
            return False

        logger.info(f"{provider.name} test successful")
        return True

    except Exception as e:
        logger.error(f"Provider test failed: {e}")
        return False