"""Launch local-only or authenticated home-network access."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
from studio.paths import ROOT
from studio.config import initialize, settings


def lan_ip():
    for interface in ('en0', 'en1', 'en2'):
        result = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', interface], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError('Could not find the LAN address. Use ./studio.sh run --lan --ip YOUR_MAC_LAN_IP')


def main():
    initialize()
    config = settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lan', action='store_true', default=config['STUDIO_LAN'] == '1', help='Enable password-protected home network access')
    parser.add_argument('--ip', default=None if config['STUDIO_IP'] == 'auto' else config['STUDIO_IP'], help='Mac LAN IPv4 address, if automatic detection fails')
    args = parser.parse_args()
    if args.ip and not args.lan:
        parser.error('--ip requires --lan')
    port = int(config['STUDIO_PORT'])
    if not 1024 <= port <= 65535:
        parser.error('STUDIO_PORT must be 1024–65535.')
    host = '127.0.0.1'
    os.environ.pop('STUDIO_LAN_IP', None)
    os.environ.pop('STUDIO_PASSWORD_FILE', None)
    if args.lan:
        address = args.ip or lan_ip()
        ip = ipaddress.IPv4Address(address)
        if not ip.is_private or ip.is_loopback or ip.is_link_local:
            parser.error('Use your Mac’s private home-network IPv4 address.')
        password = config['STUDIO_PASSWORD']
        if len(password) < 16:
            parser.error('Set STUDIO_PASSWORD in .env to at least 16 characters.')
        os.environ['STUDIO_LAN_IP'] = address
        os.environ['STUDIO_PASSWORD'] = password
        host = address
        print(f'Home-network address: http://{address}:{port}\nUsername: studio\nPassword: see STUDIO_PASSWORD in .env', flush=True)
        print('People with this password share the image history and one generation slot. Use trusted home Wi-Fi.', flush=True)
    else:
        print(f'Local Image Studio: http://127.0.0.1:{port}', flush=True)
    print('Stop with Ctrl+C.', flush=True)
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'studio.server:app', '--host', host,
                             '--port', str(port), '--no-access-log', '--no-proxy-headers'])

if __name__ == '__main__':
    main()
