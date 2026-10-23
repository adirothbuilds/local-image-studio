from contextlib import contextmanager
import fcntl
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models' / 'flux2-klein-4b'
OUTPUTS = ROOT / 'outputs'
LOGS = ROOT / 'logs'

@contextmanager
def operation_lock():
    # The persistent lock file must not be unlinked while another process may hold it.
    with (ROOT / '.operation.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Stop the running app, setup, or download before this operation.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
