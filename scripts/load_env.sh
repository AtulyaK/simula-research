# Load repo-root .env into the shell (export all assignments). Gitignored; no secrets in repo.
# Works when sourced from bash or zsh (repo root: source scripts/nim_env_defaults.sh).
_SCRIPT_SELF="${BASH_SOURCE[0]:-${(%):-%x}}"
_SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT_SELF")" && pwd)"
_REPO_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
if [[ -f "$_REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$_REPO_ROOT/.env"
  set +a
fi
unset _SCRIPT_SELF _SCRIPT_DIR _REPO_ROOT
