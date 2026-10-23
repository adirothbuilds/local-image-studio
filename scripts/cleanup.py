"""Remove only known project data; default is a preview."""
import argparse
import fcntl
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'cache': ['.cache'],
    'models': ['models', '.cache/huggingface'],
    'outputs': ['outputs'],
    'runtime': ['.venv', '.runtime', '.cache', 'logs'],
    'all': ['.venv', '.runtime', '.cache', 'models', 'outputs', 'logs', '.env'],
}

def clean(root, group, yes=False):
    root = root.resolve()
    planned = [root / relative for relative in GROUPS[group]]
    # Reject symlinked ancestors before any deletion. A leaf symlink is unlinked, never followed.
    for path in planned:
        for parent in path.parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise RuntimeError(f'Refusing to follow symlink: {parent}')
    with (root / '.operation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Stop the app, setup, or download before cleaning.') from None
        for path in planned:
            if path.exists() or path.is_symlink():
                print(('Remove: ' if yes else 'Would remove: ') + str(path))
                if yes:
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    else:
                        shutil.rmtree(path)
    if not yes:
        print('Preview only. Add --yes to delete these files.')
    else:
        print('Done. Source code, scripts, lockfile, and work log are preserved.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('group', choices=GROUPS, nargs='?', default='cache')
    parser.add_argument('--yes', action='store_true', help='Actually delete the listed data')
    args = parser.parse_args()
    try:
        clean(ROOT, args.group, args.yes)
    except RuntimeError as exc:
        parser.exit(1, f'{exc}\n')
