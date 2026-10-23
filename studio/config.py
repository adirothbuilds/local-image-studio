"""Small, non-executable project-local .env configuration."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
KEYS = {'STUDIO_LAN', 'STUDIO_IP', 'STUDIO_PORT', 'STUDIO_PASSWORD'}

def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key.strip() not in KEYS:
            raise ValueError('Unsupported .env setting: ' + key)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        values[key.strip()] = value
    return values

def initialize():
    path = ROOT / '.env'
    if not path.exists():
        legacy = ROOT / '.runtime/lan-password'
        password = legacy.read_text().strip() if legacy.exists() else secrets.token_urlsafe(24)
        with open(path, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
            handle.write('STUDIO_LAN=0\nSTUDIO_IP=auto\nSTUDIO_PORT=7860\nSTUDIO_PASSWORD=' + password + '\n')
    path.chmod(0o600)
    return read_env(path)

def settings():
    values = read_env(ROOT / '.env') if (ROOT / '.env').exists() else {}
    return {key: os.environ.get(key, values.get(key, default)) for key, default in
            {'STUDIO_LAN':'0', 'STUDIO_IP':'auto', 'STUDIO_PORT':'7860', 'STUDIO_PASSWORD':''}.items()}

if __name__ == '__main__':
    initialize()
    print('Configuration ready in .env (owner-readable only).')
