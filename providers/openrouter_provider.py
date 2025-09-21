"""
OpenRouter provider for multiple AI model providers
"""

import requests
from typing import List, Dict, Any
import logging
from .base import BaseProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseProvider):
    """
    OpenRouter provider for access to multiple AI models
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")

        self.embed_model = config.get('embed_model', 'openai/text-embedding-3-small')
        self.generation_model = config.get('generation_model', 'anthropic/claude-3-haiku')
        self.base_url = 'https://openrouter.ai/api/v1'

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        text = self.validate_text(text)
        try:
            response = requests.post(
                f'{self.base_url}/embeddings',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/your-username/your-repo',
                    'X-Title': 'RAG Knowledge Base'
                },
                json={
                    'model': self.embed_model,
                    'input': text
                }
            )
            response.raise_for_status()
            if response.text.strip() == '':
                logger.error(f"OpenRouter returned empty response. Status: {response.status_code}")
                raise ValueError("Empty response from OpenRouter API")
            data = response.json()
            return data['data'][0]['embedding']
        except Exception as e:
            logger.error(f"OpenRouter embedding failed: {e}")
            logger.error(f"Response status: {getattr(response, 'status_code', 'unknown')}")
            logger.error(f"Response text: {getattr(response, 'text', 'unknown')}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        validated_texts = [self.validate_text(text) for text in texts]
        try:
            response = requests.post(
                f'{self.base_url}/embeddings',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/your-username/your-repo',
                    'X-Title': 'RAG Knowledge Base'
                },
                json={
                    'model': self.embed_model,
                    'input': validated_texts
                }
            )
            response.raise_for_status()
            data = response.json()
            return [item['embedding'] for item in data['data']]
        except Exception as e:
            logger.error(f"OpenRouter batch embedding failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text response"""
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/your-username/your-repo',
                    'X-Title': 'RAG Knowledge Base'
                },
                json={
                    'model': self.generation_model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': kwargs.get('temperature', 0.7),
                    'max_tokens': kwargs.get('max_tokens', 500),
                    'top_p': kwargs.get('top_p', 1.0)
                }
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if OpenRouter API is available"""
        try:
            response = requests.get(
                f'{self.base_url}/models',
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            'provider': 'OpenRouter',
            'embed_model': self.embed_model,
            'generation_model': self.generation_model,
            'api_key_configured': bool(self.api_key),
            'local': False,
            'cost': 'Paid (varies by model)',
            'benefits': [
                'Access to multiple providers',
                'Automatic failover',
                'Cost optimization',
                'No vendor lock-in'
            ],
            'supported_providers': [
                'OpenAI', 'Anthropic', 'Google', 'Meta',
                'Mistral', 'Perplexity', 'Cohere'
            ]
        }

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension based on model"""
        # OpenRouter supports various models with different dimensions
        if 'text-embedding-3-small' in self.embed_model:
            return 1536
        elif 'text-embedding-3-large' in self.embed_model:
            return 3072
        elif 'voyage' in self.embed_model:
            return 1024
        else:
            return 1536  # Default

    @property
    def max_text_length(self) -> int:
        """Maximum text length for OpenRouter"""
        return 8192