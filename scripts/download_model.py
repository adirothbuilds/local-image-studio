"""Fetch only the approved model; generation never downloads weights."""
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models' / 'flux2-klein-4b'
REPO = 'black-forest-labs/FLUX.2-klein-4B'
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    from studio.paths import operation_lock
    with operation_lock():
        MODEL.mkdir(parents=True, exist_ok=True)
        manifest = MODEL / 'download.json'
        revision = json.loads(manifest.read_text())['revision'] if manifest.exists() else 'e7b7dc27f91deacad38e78976d1f2b499d76a294'
        snapshot_download(REPO, revision=revision, local_dir=MODEL,
                          allow_patterns=['model_index.json', 'scheduler/*.json', 'transformer/*.json', 'transformer/*.safetensors', 'text_encoder/*.json', 'text_encoder/*.safetensors', 'vae/*.json', 'vae/*.safetensors', 'tokenizer/**', 'LICENSE*', 'README.md'],
                          max_workers=3)
        manifest.write_text(json.dumps({'repo': REPO, 'revision': revision}, indent=2) + '\n')
        print(f'Model ready: {MODEL}\nRevision: {revision}')
