import importlib.metadata
import json
import os
import platform
from pathlib import Path
from studio.paths import ROOT, MODEL

def main():
    print('Project:', ROOT)
    print('Python:', platform.python_version(), platform.machine())
    for package in ('mflux', 'mlx', 'pillow', 'fastapi'):
        print(f'{package}: {importlib.metadata.version(package)}')
    for key in ('UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR', 'HF_HOME', 'TMPDIR', 'XDG_CACHE_HOME'):
        value = Path(os.environ[key]).resolve()
        assert value.is_relative_to(ROOT), f'{key} escapes project'
        print(f'{key}: {value}')
    import mlx.core as mx
    print('Metal available:', mx.metal.is_available())
    mx.eval(mx.array([1., 2.]) * 2)
    print('MLX computation: passed')
    from PIL import features
    print('RTL text support:', features.check('raqm'))
    manifest = MODEL / 'download.json'
    print('Model:', json.loads(manifest.read_text()) if manifest.exists() else 'not downloaded')

if __name__ == '__main__':
    main()
