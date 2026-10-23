#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
command="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
case "$command" in
  setup)
    /usr/bin/env python3 "$ROOT/scripts/run_locked.py" /bin/bash "$ROOT/scripts/setup_impl.sh" "$@"
    "$ROOT/studio.sh" download
    ;;
  clean) exec /usr/bin/env python3 "$ROOT/scripts/cleanup.py" "$@" ;;
  help|--help|-h)
    echo 'Local Image Studio · Apple Silicon'
    echo './studio.sh setup                 Install local uv/Python/packages + model (first time)'
    echo './studio.sh run [--lan]           Run website in terminal; Ctrl+C stops it'
    echo './studio.sh generate --help      Generate an image from the terminal'
    echo './studio.sh service start|stop|status   macOS user-session background mode'
    echo './studio.sh benchmark [--runs 3] Measure generation time and GPU memory'
    echo './studio.sh doctor | test | download'
    echo './studio.sh clean all [--yes]     Preview/delete local data (stop app first)'
    ;;
  run|download|doctor|test|generate|benchmark|service)
    source "$ROOT/scripts/env.sh"
    [[ -x .venv/bin/python ]] || { echo 'Run ./studio.sh setup first.'; exit 1; }
    case "$command" in
      run) export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1; exec .venv/bin/python -m studio.launch "$@" ;;
      download) exec .venv/bin/python scripts/download_model.py "$@" ;;
      doctor) exec .venv/bin/python -m studio.doctor "$@" ;;
      test) exec .venv/bin/python -m unittest discover -s tests -v ;;
      generate) exec .venv/bin/python -m studio.cli "$@" ;;
      benchmark) exec .venv/bin/python -m studio.benchmark "$@" ;;
      service) exec .venv/bin/python -m studio.service "$@" ;;
    esac
    ;;
  *) echo "Unknown command: $command. Run ./studio.sh help" >&2; exit 2 ;;
esac
