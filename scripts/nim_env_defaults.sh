# Source from repo root: source scripts/nim_env_defaults.sh
# Loads .env from repo root first (gitignored). See .env.example.
# NVIDIA integrate API (OpenAI-compatible chat/completions). Critic path uses stream=false JSON.
# Rate limit: SIMULA_NIM_MAX_RPM=40 (~1.5s between calls). Never commit API keys.

_SCRIPT_SELF="${BASH_SOURCE[0]:-${(%):-%x}}"
_SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT_SELF")" && pwd)"
# shellcheck source=load_env.sh
source "$_SCRIPT_DIR/load_env.sh"
unset _SCRIPT_SELF _SCRIPT_DIR

export SIMULA_CRITIC_BACKEND="${SIMULA_CRITIC_BACKEND:-nim}"
export SIMULA_NIM_BASE_URL="${SIMULA_NIM_BASE_URL:-https://integrate.api.nvidia.com/v1/chat/completions}"
export SIMULA_NIM_MODEL="${SIMULA_NIM_MODEL:-mistralai/mistral-large-3-675b-instruct-2512}"
export SIMULA_CRITIC_MODEL_A="${SIMULA_CRITIC_MODEL_A:-$SIMULA_NIM_MODEL}"
export SIMULA_CRITIC_MODEL_B="${SIMULA_CRITIC_MODEL_B:-$SIMULA_NIM_MODEL}"
export SIMULA_NIM_MAX_RPM="${SIMULA_NIM_MAX_RPM:-40}"
export SIMULA_HTTP_TIMEOUT_SECONDS="${SIMULA_HTTP_TIMEOUT_SECONDS:-60}"
export SIMULA_HTTP_MAX_RETRIES="${SIMULA_HTTP_MAX_RETRIES:-3}"
export SIMULA_HTTP_BACKOFF_BASE_SECONDS="${SIMULA_HTTP_BACKOFF_BASE_SECONDS:-2.0}"
export SIMULA_NVIDIA_MAX_TOKENS="${SIMULA_NVIDIA_MAX_TOKENS:-16}"
