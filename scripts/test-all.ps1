$ErrorActionPreference = "Stop"

uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest

Push-Location frontend
try {
    corepack enable
    pnpm install --frozen-lockfile
    pnpm format:check
    pnpm lint
    pnpm typecheck
    pnpm test
    pnpm build
    pnpm test:e2e
}
finally {
    Pop-Location
}
