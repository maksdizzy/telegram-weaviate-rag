"""
OpenAI provider for embedding and generation
"""

import openai
from typing import List, Dict, Any
import logging
from .base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """
    OpenAI provider for embeddings and generation
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.embed_model = config.get('embed_model', 'text-embedding-3-small')
        self.generation_model = config.get('generation_model', 'gpt-4-turbo-preview')

        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        text = self.validate_text(text)
        try:
            response = self.client.embeddings.create(
                model=self.embed_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        validated_texts = [self.validate_text(text) for text in texts]
        try:
            response = self.client.embeddings.create(
                model=self.embed_model,
                input=validated_texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text response"""
        try:
            response = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 500),
                top_p=kwargs.get('top_p', 1.0)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        try:
            # Try a simple API call
            self.client.models.list()
            return True
        except:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            'provider': 'OpenAI',
            'embed_model': self.embed_model,
            'generation_model': self.generation_model,
            'api_key_configured': bool(self.api_key),
            'local': False,
            'cost': 'Paid (per token)',
            'pricing': {
                'text-embedding-3-small': '$0.00002/1K tokens',
                'text-embedding-3-large': '$0.00013/1K tokens',
                'gpt-4-turbo': '$0.01/$0.03 per 1K tokens'
            }
        }

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension based on model"""
        dimensions = {
            'text-embedding-3-small': 1536,
            'text-embedding-3-large': 3072,
            'text-embedding-ada-002': 1536
        }
        return dimensions.get(self.embed_model, 1536)

    @property
    def max_text_length(self) -> int:
        """Maximum text length for OpenAI"""
        return 8191  # Token limit, roughly 32k characters