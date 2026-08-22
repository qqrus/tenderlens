param(
    [int]$MaxSteps = 1,
    [string]$BaseModel = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    [string]$OutputDir = "models/tenderlens-reranker-smoke"
)

$ErrorActionPreference = "Stop"
$env:HF_HUB_DISABLE_XET = "1"

uv sync --dev --extra ml
uv run --extra ml python scripts/train_reranker.py `
    --base-model $BaseModel `
    --max-steps $MaxSteps `
    --output-dir $OutputDir
