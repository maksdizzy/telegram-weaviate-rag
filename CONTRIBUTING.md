# 🤝 Contributing to Telegram RAG Knowledge Base

Thank you for your interest in contributing to the Telegram RAG Knowledge Base! We welcome contributions from the community and are grateful for your support.

## 🎯 How to Contribute

### 🐛 Bug Reports

If you find a bug, please create an issue with:
- **Clear description** of the problem
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Environment details** (OS, Python version, etc.)
- **Error messages** or logs if applicable

### 💡 Feature Requests

For new features, please:
- **Check existing issues** to avoid duplicates
- **Describe the feature** clearly
- **Explain the use case** and benefits
- **Consider implementation** approach if possible

### 🔧 Code Contributions

#### Areas Where Help is Needed

1. **New Embedding Providers**
   - Cohere integration
   - Hugging Face embeddings
   - Anthropic embeddings
   - Local transformer models

2. **Additional Chat Export Formats**
   - WhatsApp exports
   - Discord exports
   - Slack exports
   - Signal exports

3. **Performance Optimizations**
   - Batch processing improvements
   - Memory optimization
   - Search speed enhancements
   - Caching mechanisms

4. **UI/Frontend Development**
   - Web interface for search
   - Chat visualization
   - Configuration management UI
   - Analytics dashboard

5. **Documentation**
   - Tutorial improvements
   - API examples
   - Video guides
   - Translation to other languages

#### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/telegram-weaviate-rag.git
   cd telegram-weaviate-rag
   ```

2. **Set Up Environment**
   ```bash
   ./setup.sh
   source venv/bin/activate
   ```

3. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make Changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

5. **Test Your Changes**
   ```bash
   # Run existing tests
   python test_rag.py

   # Test specific providers
   python config.py
   python schema.py

   # Test API endpoints
   python api.py &
   curl -X GET http://localhost:8000/health
   ```

#### Code Style Guidelines

- **Python**: Follow PEP 8 style guide
- **Imports**: Use absolute imports, group logically
- **Documentation**: Add docstrings for all functions and classes
- **Type Hints**: Use type annotations where possible
- **Error Handling**: Include comprehensive error handling
- **Logging**: Use appropriate logging levels

#### Pull Request Process

1. **Ensure Tests Pass**
   - All existing functionality works
   - New features are tested
   - No breaking changes (unless discussed)

2. **Update Documentation**
   - README.md for user-facing changes
   - CLAUDE.md for developer guidance
   - Docstrings for new functions

3. **Commit Standards**
   ```
   feat: add Cohere embedding provider
   fix: resolve memory leak in batch processing
   docs: update API documentation
   test: add integration tests for upload endpoint
   ```

4. **Submit Pull Request**
   - Clear title and description
   - Reference related issues
   - Include screenshots if UI changes
   - Request review from maintainers

## 🏗️ Architecture Guidelines

### Adding New Embedding Providers

1. **Create Provider Class**
   ```python
   # providers/your_provider.py
   from .base import BaseProvider

   class YourProvider(BaseProvider):
       def __init__(self, config: Dict[str, Any]):
           super().__init__(config)
           # Initialize your provider

       def embed_text(self, text: str) -> List[float]:
           # Implement single text embedding

       def embed_batch(self, texts: List[str]) -> List[List[float]]:
           # Implement batch embedding
   ```

2. **Update Factory**
   ```python
   # providers/provider_factory.py
   from .your_provider import YourProvider

   # Add to get_provider() function
   elif provider_name == 'your_provider':
       config = {
           'api_key': os.getenv('YOUR_PROVIDER_API_KEY'),
           # Add other config
       }
       return YourProvider(config)
   ```

3. **Add Configuration**
   ```python
   # Update .env.example with new variables
   YOUR_PROVIDER_API_KEY=your_api_key_here
   YOUR_PROVIDER_MODEL=default_model_name
   ```

### Adding New Chat Export Formats

1. **Create Parser**
   ```python
   # parsers/your_format.py
   def parse_your_format(file_path: str) -> List[TelegramMessage]:
       # Parse your format into TelegramMessage objects
   ```

2. **Update Upload Handler**
   ```python
   # api.py - add format detection
   if file_extension == '.your_ext':
       messages = parse_your_format(file_path)
   ```

## 🧪 Testing

### Test Structure
- **Unit Tests**: Test individual functions
- **Integration Tests**: Test component interaction
- **End-to-End Tests**: Test complete workflows

### Adding Tests
```python
# tests/test_your_feature.py
def test_your_feature():
    # Arrange
    # Act
    # Assert
    pass
```

### Test Data
- Use small, representative datasets
- Include edge cases and error conditions
- Mock external API calls when possible

## 📚 Documentation

### Code Documentation
- **Docstrings**: Describe purpose, parameters, and return values
- **Comments**: Explain complex logic or non-obvious decisions
- **Type Hints**: Help with IDE support and debugging

### User Documentation
- **README**: Keep setup instructions current
- **Examples**: Provide working code samples
- **Troubleshooting**: Document common issues and solutions

## 🔒 Security Considerations

- **No Hardcoded Secrets**: Use environment variables
- **Input Validation**: Sanitize all user inputs
- **Error Handling**: Don't leak sensitive information
- **Dependencies**: Keep packages updated

## 📞 Getting Help

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Create issues for bugs and feature requests
- **Email**: Contact maxim.a.savelyev@gmail.com for major contributions

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be:
- Added to the project's contributor list
- Mentioned in release notes for significant contributions
- Credited in documentation for major features

---

**Thank you for helping make Telegram RAG Knowledge Base better! 🚀**