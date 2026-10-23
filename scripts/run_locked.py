"""Hold the project operation lock while a child command runs."""
import fcntl
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
with (root / '.operation.lock').open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Stop the app, setup, or download before this operation.')
    sys.exit(subprocess.call(sys.argv[1:], cwd=root))
