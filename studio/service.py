"""macOS launchd user-session service; its plist and logs stay in this project."""
import argparse
import os
import plistlib
import subprocess
import sys
from studio.paths import ROOT, LOGS, operation_lock

LABEL='local.image-studio'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','stop','status'))
    args=parser.parse_args()
    if sys.platform!='darwin':
        parser.error('Service mode requires macOS.')
    domain=f'gui/{os.getuid()}'
    target=f'{domain}/{LABEL}'
    if args.action=='status':
        raise SystemExit(subprocess.run(['/bin/launchctl','print',target]).returncode)
    if args.action=='stop':
        raise SystemExit(subprocess.run(['/bin/launchctl','bootout',target]).returncode)
    if subprocess.run(['/bin/launchctl','print',target],capture_output=True).returncode==0:
        print('Service is already loaded. Use service stop before changing configuration.')
        return
    with operation_lock():
        pass  # Refuse background launch while terminal mode or a generation is active.
    LOGS.mkdir(exist_ok=True)
    folder=ROOT/'.runtime/service'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{LABEL}.plist'
    path.write_bytes(plistlib.dumps(dict(Label=LABEL,ProgramArguments=['/bin/bash',str(ROOT/'studio.sh'),'run'],
                                        WorkingDirectory=str(ROOT),RunAtLoad=True,
                                        KeepAlive=dict(SuccessfulExit=False),ThrottleInterval=15,
                                        StandardOutPath=str(LOGS/'service.log'),StandardErrorPath=str(LOGS/'service-error.log'))))
    subprocess.run(['/bin/launchctl','bootstrap',domain,str(path)],check=True)
    print('Service started for this login session. Logs: logs/service*.log')
    print('Reads .env. Survives closing Terminal; stops at logout. No login item installed.')

if __name__=='__main__':
    main()
