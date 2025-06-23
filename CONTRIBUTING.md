# Contributing to Kubernetes & Istio AI Troubleshooting Agent

Thank you for your interest in contributing to the Kubernetes & Istio AI Troubleshooting Agent! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites
- Python 3.11+
- kubectl configured with cluster access
- Docker (for container builds)
- Git

### Development Setup
```bash
# Clone the repository
git clone <repository-url>
cd k8s-istio-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Install pre-commit hooks
pre-commit install
```

## Project Structure

```
k8s-istio-agent/
├── agent/                 # Core agent logic
│   └── controller.py     # Main orchestration
├── llm/                  # LLM provider abstractions
│   ├── provider.py       # Base provider interface
│   └── providers/        # Specific implementations
├── tools/                # Tool system
│   ├── base.py          # Tool abstractions
│   ├── registry.py      # Tool management
│   ├── kubernetes/      # K8s-specific tools
│   ├── istio/           # Istio-specific tools
│   └── observability/   # Monitoring tools
├── web/                  # Web interface
│   ├── app.py           # FastAPI application
│   └── templates/       # HTML templates
├── k8s/                  # Kubernetes manifests
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes
- Follow the coding standards below
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes
```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run all tests with coverage
pytest --cov=agent --cov=llm --cov=tools tests/
```

### 4. Submit a Pull Request
- Create a descriptive PR title
- Include a detailed description of changes
- Reference any related issues
- Ensure all tests pass

## Coding Standards

### Python Style Guide
- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Keep functions focused and under 50 lines when possible
- Use descriptive variable and function names

### Example Code Style
```python
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    output: str
    error: Optional[str] = None

def execute_kubectl_command(
    command: str, 
    namespace: Optional[str] = None
) -> ToolResult:
    """
    Execute a kubectl command safely.
    
    Args:
        command: The kubectl command to execute
        namespace: Optional namespace context
        
    Returns:
        ToolResult with execution status and output
    """
    # Implementation here
    pass
```

### Documentation Standards
- Use docstrings for all public functions and classes
- Follow Google-style docstring format
- Include examples for complex functions
- Update README.md for user-facing changes

## Testing Guidelines

### Unit Tests
- Test individual functions and classes
- Mock external dependencies (kubectl, API calls)
- Aim for >90% code coverage
- Place tests in `tests/unit/`

### Integration Tests
- Test component interactions
- Use real kubectl commands (in test environment)
- Test end-to-end workflows
- Place tests in `tests/integration/`

### Test Example
```python
import pytest
from unittest.mock import patch, MagicMock
from tools.kubernetes.kubectl import KubectlTool

class TestKubectlTool:
    def test_get_pods_success(self):
        """Test successful pod retrieval."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=b'NAME READY STATUS\npod1 1/1 Running'
            )
            
            tool = KubectlTool()
            result = tool.get_pods('default')
            
            assert result.success is True
            assert 'pod1' in result.output
```

## Adding New Features

### Adding a New Tool
1. Create a new file in the appropriate `tools/` subdirectory
2. Inherit from `BaseTool` class
3. Implement required methods
4. Register the tool in `tools/registry.py`
5. Add tests in `tests/unit/tools/`

### Adding a New LLM Provider
1. Create a new file in `llm/providers/`
2. Inherit from `BaseProvider` class
3. Implement required methods
4. Add configuration examples to README.md
5. Add tests in `tests/unit/llm/`

### Example Tool Implementation
```python
from tools.base import BaseTool, ToolResult
from typing import Optional

class MyCustomTool(BaseTool):
    """Custom tool for specific functionality."""
    
    name = "my_custom_tool"
    description = "Performs custom operations"
    
    def execute(self, params: dict) -> ToolResult:
        """Execute the custom tool."""
        try:
            # Implementation here
            return ToolResult(success=True, output="Success!")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

## Bug Reports

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

## Feature Requests

When requesting features, please include:
- Clear description of the desired functionality
- Use cases and examples
- Potential implementation approach (if you have ideas)
- Priority level

## Pull Request Checklist

Before submitting a PR, ensure:
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] No sensitive data is committed
- [ ] Commit messages are descriptive

## Code Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Review**: At least one maintainer reviews the PR
3. **Feedback**: Address any review comments
4. **Merge**: PR is merged once approved