"""Repeatable end-to-end measurements; never uses personal prompts or references."""
import argparse
import datetime
import importlib.metadata
import json
import platform
import statistics
import subprocess
import time
from studio.cli import generate, PRESETS
from studio.paths import ROOT, LOGS, MODEL, operation_lock

PROMPT='A cheerful small snowman celebrating a birthday in a sparkling ice palace, lavender balloons, snowflakes, blue and purple palette, polished storybook illustration, no lettering.'

def hardware():
    def sysctl(key):
        return subprocess.check_output(['/usr/sbin/sysctl','-n',key],text=True).strip()
    return dict(chip=sysctl('machdep.cpu.brand_string'), memory_bytes=int(sysctl('hw.memsize')),
                os=platform.mac_ver()[0],architecture=platform.machine(),python=platform.python_version(),
                packages={p:importlib.metadata.version(p) for p in ('mflux','mlx','pillow','fastapi')})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=int,default=3)
    parser.add_argument('--preset',choices=PRESETS,default='portrait')
    args=parser.parse_args()
    if not 1<=args.runs<=20:
        parser.error('Use 1–20 measured runs, plus one warm-up.')
    with operation_lock():
        folder=LOGS/('benchmark-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        folder.mkdir(parents=True)
        report=dict(hardware=hardware(),model=json.loads((MODEL/'download.json').read_text()),
                    preset=args.preset,resolution=PRESETS[args.preset],steps=4,quantization=8,prompt=PROMPT,
                    methodology='One worker process per image, including model load, inference and A4 PNG/PDF exports. One warm-up excluded from summary. OS/model disk caches may be warm. No parallel generation.',runs=[])
        for index in range(args.runs+1):
            print(f'{"Warm-up" if index==0 else "Measured run "+str(index)}…',flush=True)
            start=time.perf_counter()
            result=generate(folder/f'run-{index}',PROMPT,args.preset,42+index)
            result['wall_seconds']=round(time.perf_counter()-start,3)
            result['seed']=42+index
            if index==0:
                report['warmup']=result
            else:
                report['runs'].append(result)
            (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        times=[r['wall_seconds'] for r in report['runs']]
        report['summary']=dict(median_wall_seconds=round(statistics.median(times),3),
                               min_wall_seconds=min(times),max_wall_seconds=max(times),
                               max_peak_gpu_memory_gb=max(r['peak_gpu_memory_gb'] for r in report['runs']))
        (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
    print('Report:',folder/'report.json')

if __name__=='__main__':
    main()
