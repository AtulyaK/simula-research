# Shell helpers when SIMULA_VERBOSE=1 or SIMULA_LOG=1 (bash/zsh).
_simula_verbose_enabled() {
  case "${SIMULA_VERBOSE:-}${SIMULA_LOG:-}" in
    1 | true | yes | on | TRUE | YES | ON) return 0 ;;
    *) return 1 ;;
  esac
}

simula_log() {
  if _simula_verbose_enabled; then
    printf '[simula %s] %s\n' "$(date -u '+%H:%M:%S' 2>/dev/null || date '+%H:%M:%S')" "$*" >&2
  fi
}
