# Contributing to autofix-dojo

Thanks for your interest in contributing! This document provides guidelines for contributing to autofix-dojo.

## Code of Conduct

Be respectful, inclusive, and constructive. We're building something useful together.

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/jamilshaikh07/autofix-dojo/issues) first
2. Use the **Bug Report** template
3. Include:
   - Python version and OS
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs (redact secrets!)

### Suggesting Features

1. Open an issue using the **Feature Request** template
2. Describe the problem you're solving
3. Propose your solution
4. Be open to discussion

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Add/update tests
5. Submit a PR

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/autofix-dojo.git
cd autofix-dojo

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if available

# Copy environment template
cp .env.example .env

# Run tests
pytest tests/
```

## Coding Guidelines

### Style

- Follow [PEP 8](https://pep8.org/)
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `black` for formatting (if available)
- Use `ruff` or `flake8` for linting

### Naming Conventions

- `snake_case` for functions and variables
- `PascalCase` for classes
- `SCREAMING_SNAKE_CASE` for constants
- Descriptive names over abbreviations

### Documentation

- Docstrings for all public functions/classes (Google style)
- Update README if adding features
- Comment complex logic

## Branch Naming

Use the following prefixes:

| Prefix | Purpose |
|--------|---------|
| `feature/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation updates |
| `refactor/` | Code refactoring |
| `test/` | Test additions/changes |
| `chore/` | Maintenance tasks |

Examples:
- `feature/gitlab-support`
- `fix/semver-parsing`
- `docs/api-examples`

## Commit Message Style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

### Examples

```
feat(fixer): add support for alpine-based images

fix(dojo-client): handle pagination edge case

docs(readme): add Docker usage section
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=autofix --cov-report=term-missing

# Run specific test file
pytest tests/test_fixer.py

# Run specific test
pytest tests/test_fixer.py::test_semver_parsing
```

## Proposing Major Changes

For significant changes:

1. Open a **Discussion** or **Issue** first
2. Describe the motivation and approach
3. Wait for maintainer feedback before implementing
4. Large PRs may be asked to split into smaller pieces

## Review Process

1. All PRs require at least one approval
2. CI checks must pass
3. Address review comments
4. Squash commits if requested

## Getting Help

- Open an issue with the `question` label
- Check existing documentation
- Be patient - maintainers are volunteers

## Recognition

Contributors will be recognized in:
- Release notes
- Contributors section (when added)
- GitHub contributors page

---

Thank you for contributing to autofix-dojo!
