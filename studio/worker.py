"""One ML process per job: exiting reliably releases model/GPU memory."""
import json
import os
import sys
import time
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
from studio.paths import MODEL
from studio.printing import export_print
from studio.lettering import generation_prompt, print_text

def main(folder):
    import mlx.core as mx
    from mflux.models.common.config import ModelConfig
    from mflux.models.flux2.variants import Flux2Klein, Flux2KleinEdit
    config = json.loads((folder / 'settings.json').read_text())
    started = time.monotonic()
    print('Loading FLUX.2 Klein 4B with 8-bit quantization…', flush=True)
    refs = sorted(folder.glob('reference-*.png'))
    cls = Flux2KleinEdit if refs else Flux2Klein
    model = cls(model_config=ModelConfig.flux2_klein_4b(), model_path=str(MODEL), quantize=8)
    effective_prompt = generation_prompt(config)
    (folder / 'generation-prompt.txt').write_text(effective_prompt + '\n')
    print('Generating artwork…', flush=True)
    kwargs = dict(seed=config['seed'], prompt=effective_prompt, width=config['width'], height=config['height'],
                  num_inference_steps=config['steps'], guidance=1.0)
    if refs:
        kwargs['image_paths'] = [str(p) for p in refs]
    image = model.generate_image(**kwargs)
    image.save(path=str(folder / 'original.png'), export_json_metadata=True)
    print('Preparing A4 exports…', flush=True)
    export_print(folder / 'original.png', folder, config['orientation'], print_text(config), config['text_position'], config['margin_mm'], text_mode=config.get('text_mode', 'overlay'), text_style=config.get('text_style', 'ice'), text_background=config.get('text_background', 'banner'), text_scale=config.get('text_scale',1), text_x=config.get('text_x'), text_y=config.get('text_y'), text_color=config.get('text_color',''), text_font=config.get('text_font','classic'), text_font_size=config.get('text_font_size'), text_outline_width=config.get('text_outline_width'), text_outline_color=config.get('text_outline_color',''))
    result = {'elapsed_seconds': round(time.monotonic() - started, 2),
              'peak_gpu_memory_gb': round(mx.get_peak_memory() / 1e9, 2)}
    (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)

if __name__ == '__main__':
    main(Path(sys.argv[1]))
