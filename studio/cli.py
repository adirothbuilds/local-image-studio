"""Terminal generation, sharing the website's worker and output format."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import uuid
from PIL import Image, ImageOps
from studio.paths import ROOT, MODEL, OUTPUTS, operation_lock

PRESETS = {'draft': (512,512), 'portrait': (832,1184), 'landscape': (1184,832), 'square': (1024,1024)}

def generate(folder, prompt, preset='portrait', seed=42, steps=4, text='', references=()):
    manifest = MODEL / 'download.json'
    if not manifest.exists():
        raise RuntimeError('Run ./studio.sh setup to download the model.')
    width, height = PRESETS[preset]
    folder.mkdir(parents=True)
    config = dict(prompt=prompt, seed=seed, steps=steps, width=width, height=height,
                  text=text, text_mode='styled', text_style='ice', text_background='none',
                  text_position='top', text_scale=1, text_x=None, text_y=None,
                  orientation='landscape' if preset=='landscape' else 'portrait', margin_mm=5,
                  model='black-forest-labs/FLUX.2-klein-4B', quantization=8,
                  model_revision=json.loads(manifest.read_text())['revision'])
    (folder/'settings.json').write_text(json.dumps(config, indent=2, ensure_ascii=False)+'\n')
    Image.MAX_IMAGE_PIXELS = 25_000_000
    for index, path in enumerate(references):
        if path.stat().st_size > 10_000_000:
            raise ValueError('Each reference must be under 10 MB.')
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGBA')
            image = Image.alpha_composite(Image.new('RGBA',image.size,'white'),image).convert('RGB')
            image.thumbnail((1536,1536), Image.Resampling.LANCZOS)
            image.save(folder/f'reference-{index}.png')
    (folder/'status.json').write_text('{"state":"running"}')
    with (folder/'generation.log').open('w') as log:
        result = subprocess.run([sys.executable,'-u','-m','studio.worker',str(folder)], cwd=ROOT,
                                stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        (folder/'status.json').write_text('{"state":"failed"}')
        raise RuntimeError('Generation failed; see '+str(folder/'generation.log'))
    data = json.loads((folder/'result.json').read_text())
    (folder/'status.json').write_text(json.dumps(dict(state='complete',**data)))
    return data

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prompt')
    parser.add_argument('--preset',choices=PRESETS,default='portrait')
    parser.add_argument('--seed',type=int,default=None)
    parser.add_argument('--steps',type=int,choices=range(1,13),default=4)
    parser.add_argument('--text',default='',help='Exact styled message; supports Hebrew')
    parser.add_argument('--reference',type=Path,action='append',default=[])
    args=parser.parse_args()
    if not args.prompt.strip() or len(args.prompt)>4000 or len(args.text)>200 or len(args.reference)>4:
        parser.error('Prompt: 1–4000 characters; message: up to 200; references: up to four.')
    seed=args.seed if args.seed is not None else secrets.randbelow(2**32)
    if not 0<=seed<2**32:
        parser.error('Seed must be 0–4294967295.')
    with operation_lock():
        folder=OUTPUTS/str(uuid.uuid4())
        data=generate(folder,args.prompt,args.preset,seed,args.steps,args.text,args.reference)
    print(json.dumps(data,indent=2))
    print('Artwork and A4 exports:',folder)

if __name__=='__main__':
    main()
