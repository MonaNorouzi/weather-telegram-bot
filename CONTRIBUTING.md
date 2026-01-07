# Contributing to Weather Route Planner

Thank you for considering contributing to this project! 

## 🤝 How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

### Suggesting Features

Feature requests are welcome! Please:
- Check existing issues first
- Describe the use case
- Explain why it would be useful
- Consider implementation complexity

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow PEP 8 style guide
   - Add tests for new features
   - Update documentation as needed

4. **Test your changes**
   ```bash
   pytest tests/ -v
   python test_h3_router.py
   ```

5. **Commit with clear messages**
   ```bash
   git commit -m "feat: add awesome feature
   
   - Detailed description of what changed
   - Why the change was needed
   - Any breaking changes"
   ```

6. **Push and create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 Code Style

- **Python**: PEP 8 (use `black` for formatting)
- **Line length**: 120 characters max
- **Imports**: Sorted with `isort`
- **Type hints**: Encouraged for new code
- **Docstrings**: Google style

### Example
```python
async def fetch_weather(lat: float, lon: float) -> Optional[Dict]:
    """Fetch weather data for coordinates.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Weather data dict or None if failed
    """
    # Implementation
```

## 🧪 Testing

- Write tests for new features
- Maintain >80% coverage
- Use meaningful test names

```python
def test_h3_cache_should_return_cached_data():
    # Arrange
    # Act  
    # Assert
```

## 📚 Documentation

- Update README.md for user-facing changes
- Add docstrings for new functions
- Update relevant docs in `docs/` folder
- Include code examples

## 🔍 Code Review Process

1. All PRs require review
2. CI must pass (tests, linting)
3. Changes should be focused and atomic
4. Discussions are welcome!

## 🚫 What Not to Do

- Don't commit secrets or API keys
- Don't commit `.env` files
- Don't commit session files (`.session`)
- Don't commit large binary files
- Don't break backward compatibility without discussion

## 📧 Questions?

Open an issue for questions or discussions.

---

**Thank you for contributing!** 🎉
