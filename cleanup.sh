find . -type d -name __pycache__ -prune -exec rm -rf {} +
uv run ruff check --fix *.py
uv run ty check --error-on-warning *.py
