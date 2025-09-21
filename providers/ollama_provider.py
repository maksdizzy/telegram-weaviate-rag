"""
Ollama provider for local embedding and generation
"""

import ollama
from typing import List, Dict, Any
import logging
from .base import BaseProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local LLM inference
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 11434)
        self.embed_model = config.get('embed_model', 'nomic-embed-text')
        self.generation_model = config.get('generation_model', 'llama3.2')
        self.client = ollama.Client(host=f'http://{self.host}:{self.port}')

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        text = self.validate_text(text)
        try:
            response = self.client.embeddings(
                model=self.embed_model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_text(text))
        return embeddings

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text response"""
        try:
            response = self.client.generate(
                model=self.generation_model,
                prompt=prompt,
                options=kwargs
            )
            return response['response']
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            # Try to list models
            self.client.list()
            return True
        except:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get provider information"""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models['models']]
            return {
                'provider': 'Ollama',
                'host': f'{self.host}:{self.port}',
                'embed_model': self.embed_model,
                'generation_model': self.generation_model,
                'available_models': model_names,
                'local': True,
                'cost': 'Free (local compute)'
            }
        except:
            return {
                'provider': 'Ollama',
                'status': 'Not available',
                'host': f'{self.host}:{self.port}'
            }

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension based on model"""
        dimensions = {
            'nomic-embed-text': 768,
            'mxbai-embed-large': 1024,
            'all-minilm': 384
        }
        return dimensions.get(self.embed_model, 768)

    @property
    def max_text_length(self) -> int:
        """Maximum text length for Ollama"""
        return 8192