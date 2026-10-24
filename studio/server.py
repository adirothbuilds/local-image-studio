import base64
import binascii
import asyncio
from contextlib import asynccontextmanager
import io
import math
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from studio.paths import ROOT, MODEL, OUTPUTS, LOGS, operation_lock
from studio.styled_text import letter_color, lettering_font, outline_width, font_points
from studio.lettering import MODES, STYLES, print_text

LAN_IP = os.environ.get('STUDIO_LAN_IP')
PASSWORD_FILE = os.environ.get('STUDIO_PASSWORD_FILE')
LAN_PASSWORD = (Path(PASSWORD_FILE).read_text().strip() if PASSWORD_FILE else os.environ.get('STUDIO_PASSWORD')) if LAN_IP else None
if LAN_IP and not LAN_PASSWORD:
    raise RuntimeError('LAN mode requires STUDIO_PASSWORD.')
TOKEN = secrets.token_urlsafe(32)
SESSION_TOKEN = secrets.token_urlsafe(32)
current = None
job_lock = asyncio.Lock()
PRESETS = {'square': (1024, 1024), 'portrait': (832, 1184), 'landscape': (1184, 832), 'draft': (512, 512)}
Image.MAX_IMAGE_PIXELS = 25_000_000

@asynccontextmanager
async def lifespan(app):
    global current
    OUTPUTS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    with operation_lock():
        # A restart may follow an interrupted job; never leave it marked as running.
        for status in OUTPUTS.glob('*/status.json'):
            data = json.loads(status.read_text())
            if data['state'] in ('running', 'queued'):
                data.update(state='interrupted', error='App stopped before this job completed.')
                status.write_text(json.dumps(data))
        yield
        if current and current.poll() is None:
            current.terminate()
            try:
                current.wait(timeout=10)
            except subprocess.TimeoutExpired:
                current.kill()
                current.wait()

app = FastAPI(lifespan=lifespan, telemetry={'tracing': False, 'metrics': False, 'logs': False, 'operation_spans': False, 'auto_configure': False})
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'] + ([LAN_IP] if LAN_IP else []))

@app.middleware('http')
async def local_requests(request: Request, call_next):
    public_login = request.url.path in ('/login', '/static/style.css', '/static/login.js')
    if LAN_PASSWORD and not public_login:
        credentials = request.headers.get('authorization', '')
        try:
            scheme, encoded = credentials.split(' ', 1)
            username, password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
            authenticated = (scheme.lower() == 'basic' and secrets.compare_digest(username.encode(), b'studio')
                             and secrets.compare_digest(password.encode(), LAN_PASSWORD.encode()))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            authenticated = False
        authenticated = authenticated or secrets.compare_digest(request.cookies.get('studio_session', '').encode(), SESSION_TOKEN.encode())
        if not authenticated:
            if request.method == 'GET' and 'text/html' in request.headers.get('accept', ''):
                return RedirectResponse('/login', status_code=303)
            return JSONResponse({'detail': 'Sign in to the home image studio.'}, status_code=401,
                                headers={'Cache-Control': 'no-store'})
    if request.method not in ('GET', 'HEAD'):
        if request.url.path != '/login' and request.headers.get('x-studio-token') != TOKEN:
            return JSONResponse({'detail': 'Reload the local app before submitting.'}, status_code=403)
        origin = request.headers.get('origin')
        # Navigation form POSTs may send Origin:null under no-referrer. Login
        # validates its hidden CSRF token before credentials; API calls require
        # both the custom token header and a matching origin when supplied.
        if request.url.path != '/login' and origin and origin != f'{request.url.scheme}://{request.headers.get("host", "")}':
            return JSONResponse({'detail': 'Only this studio interface may submit jobs.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response


def login_page(error=''):
    source = (ROOT / 'studio' / 'static' / 'login.html').read_text()
    return source.replace('__TOKEN__', TOKEN).replace('__ERROR__', error)

@app.get('/login')
def sign_in_page():
    if not LAN_PASSWORD:
        return RedirectResponse('/', status_code=303)
    return HTMLResponse(login_page())

@app.post('/login')
async def sign_in(request: Request):
    if not LAN_PASSWORD:
        return RedirectResponse('/', status_code=303)
    wants_json = 'application/json' in request.headers.get('accept', '')
    form = await request.form(max_fields=3, max_files=0)
    if not secrets.compare_digest(str(form.get('csrf', '')).encode(), TOKEN.encode()):
        if wants_json:
            return JSONResponse({'detail':'The sign-in form expired after a server restart. Reload this page and try again.'}, status_code=403)
        return HTMLResponse(login_page('This form expired. Please enter your password again.'), status_code=403)
    valid = (secrets.compare_digest(str(form.get('username', '')).encode(), b'studio')
             and secrets.compare_digest(str(form.get('password', '')).encode(), LAN_PASSWORD.encode()))
    if not valid:
        if wants_json:
            return JSONResponse({'detail':'Username or password is incorrect.'}, status_code=401)
        return HTMLResponse(login_page('Username or password is incorrect.'), status_code=401)
    response = JSONResponse({'redirect':'/'}) if wants_json else RedirectResponse('/', status_code=303)
    response.set_cookie('studio_session', SESSION_TOKEN, httponly=True, samesite='strict', max_age=43200)
    return response

@app.get('/')
def home():
    return FileResponse(ROOT / 'studio' / 'static' / 'index.html')

@app.get('/api/status')
def info():
    return {'token': TOKEN, 'ready': (MODEL / 'download.json').exists(), 'model': 'FLUX.2 Klein 4B · MLX · 8-bit',
            'busy': job_lock.locked()}

def job_path(job_id):
    try:
        if str(uuid.UUID(job_id)) != job_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, 'Unknown image')
    folder = OUTPUTS / job_id
    if not folder.is_dir() or folder.is_symlink():
        raise HTTPException(404, 'Unknown image')
    return folder

def write_status(folder, **data):
    temp = folder / 'status.tmp'
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(folder / 'status.json')

async def run_job(folder):
    global current
    started = time.monotonic()
    try:
        with (folder / 'generation.log').open('w') as log:
            env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            current = subprocess.Popen([sys.executable, '-u', '-m', 'studio.worker', str(folder)], cwd=ROOT,
                                       stdout=log, stderr=subprocess.STDOUT, env=env)
            while current.poll() is None:
                await asyncio.sleep(0.5)
            if current.returncode:
                write_status(folder, state='failed', error='Generation failed. Open the job log for details.',
                             seconds=round(time.monotonic() - started))
            else:
                write_status(folder, state='complete', **json.loads((folder / 'result.json').read_text()))
    except Exception as exc:
        write_status(folder, state='failed', error=str(exc))
    finally:
        current = None
        job_lock.release()


def layer_controls(scale=1.0, x=None, y=None):
    try:
        scale=float(scale)
        x=None if x in (None, '') else float(x)
        y=None if y in (None, '') else float(y)
    except (TypeError,ValueError):
        raise HTTPException(422,'Text size and placement must be numbers.') from None
    if not math.isfinite(scale) or not 0.4<=scale<=1 or any(v is not None and (not math.isfinite(v) or not 0<=v<=1) for v in (x,y)):
        raise HTTPException(422,'Text size: 40–100%; placement must be inside the page.')
    return scale,x,y

@app.post('/api/generate')
async def generate(request: Request):
    if not (MODEL / 'download.json').exists():
        raise HTTPException(409, 'Download the model first: ./studio.sh download')
    # Multipart parser caps each field; total request is additionally bounded below.
    if int(request.headers.get('content-length', '0')) > 45_000_000:
        raise HTTPException(413, 'Upload limit is 40 MB total.')
    async with request.form(max_files=4, max_fields=24, max_part_size=40_000_000) as form:
        prompt = str(form.get('prompt', '')).strip()
        text = str(form.get('text', '')).strip()
        text_scale,text_x,text_y=layer_controls(form.get('text_scale',1),form.get('text_x'),form.get('text_y'))
        text_mode = str(form.get('text_mode', 'overlay'))
        text_style = str(form.get('text_style', 'ice'))
        try:
            text_color = letter_color(form.get('text_color', ''))
            text_font = lettering_font(form.get('text_font', 'classic'))
            text_font_size = font_points(form.get('text_font_size'))
            text_outline_width = outline_width(form.get('text_outline_width'))
            text_outline_color = letter_color(form.get('text_outline_color', ''))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        text_background = str(form.get('text_background', 'banner'))
        if text_background not in ('banner', 'none'):
            raise HTTPException(422, 'Choose banner or transparent text background.')
        text_style_detail = str(form.get('text_style_detail', '')).strip()
        if text_mode not in MODES or text_style not in STYLES or len(text_style_detail) > 300:
            raise HTTPException(422, 'Choose a supported lettering mode/style; custom directions: up to 300 characters.')
        preset = str(form.get('preset', 'portrait'))
        orientation = str(form.get('orientation', 'portrait'))
        position = str(form.get('text_position', 'bottom'))
        try:
            seed_string = str(form.get('seed', '')).strip()
            seed = int(seed_string) if seed_string else secrets.randbelow(2**32)
            steps = int(str(form.get('steps', '4')))
            margin = int(str(form.get('margin_mm', '5')))
        except ValueError:
            raise HTTPException(422, 'Seed, steps, and margin must be whole numbers.')
        if not prompt or len(prompt) > 4000 or len(text) > 200:
            raise HTTPException(422, 'Enter a prompt up to 4000 characters and overlay text up to 200 characters.')
        if preset not in PRESETS or orientation not in ('portrait', 'landscape', 'square20') or position not in ('top', 'center', 'bottom'):
            raise HTTPException(422, 'Choose a supported layout.')
        if not (0 <= seed < 2**32 and 1 <= steps <= 12 and 0 <= margin <= 20):
            raise HTTPException(422, 'Seed: 0–4294967295; steps: 1–12; margin: 0–20 mm.')
        references = []
        total = 0
        for upload in form.getlist('references'):
            if not getattr(upload, 'filename', ''):
                continue
            data = await upload.read(10_000_001)
            total += len(data)
            if len(data) > 10_000_000 or total > 40_000_000:
                raise HTTPException(413, 'Each reference must be under 10 MB; at most four images.')
            try:
                with Image.open(io.BytesIO(data)) as image:
                    image = ImageOps.exif_transpose(image).convert('RGBA')
                    background = Image.new('RGBA', image.size, 'white')
                    image = Image.alpha_composite(background, image).convert('RGB')
                    image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
                    references.append(image.copy())
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise HTTPException(422, 'Reference must be a valid image under 25 megapixels.')
        if job_lock.locked():
            raise HTTPException(409, 'An image is already generating. Wait for it to finish.')
        await job_lock.acquire()
        folder = OUTPUTS / str(uuid.uuid4())
        try:
            folder.mkdir(parents=True)
            width, height = PRESETS[preset]
            settings = dict(prompt=prompt, text=text, text_font_size=text_font_size, text_outline_width=text_outline_width, text_outline_color=text_outline_color, text_font=text_font, text_color=text_color, text_mode=text_mode, text_style=text_style, text_background=text_background, text_scale=text_scale, text_x=text_x, text_y=text_y, text_style_detail=text_style_detail, seed=seed, steps=steps, width=width, height=height,
                            orientation=orientation, text_position=position, margin_mm=margin,
                            model='black-forest-labs/FLUX.2-klein-4B', quantization=8,
                            model_revision=json.loads((MODEL / 'download.json').read_text())['revision'])
            (folder / 'settings.json').write_text(json.dumps(settings, indent=2, ensure_ascii=False) + '\n')
            for i, image in enumerate(references):
                image.save(folder / f'reference-{i}.png')
            write_status(folder, state='running', seed=seed)
            asyncio.create_task(run_job(folder))
            return {'id': folder.name, 'seed': seed}
        except Exception:
            job_lock.release()
            raise

@app.get('/api/jobs')
def jobs():
    items = []
    for status in sorted(OUTPUTS.glob('*/status.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        settings = json.loads((status.parent / 'settings.json').read_text())
        items.append({'id': status.parent.name, 'prompt': settings['prompt'], 'seed': settings['seed'], 'text': settings.get('text', ''),
                      **json.loads(status.read_text())})
    return items

@app.get('/api/jobs/{job_id}')
def job(job_id: str):
    folder = job_path(job_id)
    data = json.loads((folder / 'status.json').read_text())
    log = folder / 'generation.log'
    data['log'] = log.read_text(errors='replace')[-6000:] if log.exists() else 'Starting…'
    return data


@app.post('/api/jobs/{job_id}/print')
async def reprint(job_id: str, request: Request):
    from studio.printing import export_print
    folder = job_path(job_id)
    if json.loads((folder / 'status.json').read_text())['state'] != 'complete':
        raise HTTPException(409, 'Finish generating this image before updating its print.')
    body = await request.json()
    settings = json.loads((folder / 'settings.json').read_text())
    mode = body.get('text_mode', settings.get('text_mode', 'overlay'))
    style = body.get('text_style', settings.get('text_style', 'ice'))
    try:
        text_color = letter_color(body.get('text_color', settings.get('text_color', '')))
        text_font = lettering_font(body.get('text_font', settings.get('text_font', 'classic')))
        text_font_size = font_points(body.get('text_font_size',settings.get('text_font_size')))
        text_outline_width = outline_width(body.get('text_outline_width',settings.get('text_outline_width')))
        text_outline_color = letter_color(body.get('text_outline_color',settings.get('text_outline_color','')))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    background = body.get('text_background', settings.get('text_background', 'banner'))
    if background not in ('banner', 'none'):
        raise HTTPException(422, 'Choose banner or transparent text background.')
    detail = body.get('text_style_detail', settings.get('text_style_detail', ''))
    text = body.get('text', '')
    orientation = body.get('orientation', 'portrait')
    position = body.get('text_position', 'bottom')
    margin = body.get('margin_mm', 5)
    if (not isinstance(text, str) or len(text) > 200 or orientation not in ('portrait', 'landscape', 'square20')
            or position not in ('top', 'center', 'bottom') or not isinstance(margin, int) or not 0 <= margin <= 20):
        raise HTTPException(422, 'Check your birthday message, orientation, position, and margin.')
    text_scale,text_x,text_y=layer_controls(body.get('text_scale',settings.get('text_scale',1)),body.get('text_x',settings.get('text_x')),body.get('text_y',settings.get('text_y')))
    original_mode = settings.get('text_mode', 'overlay')
    if mode not in MODES or style not in STYLES or not isinstance(detail, str) or len(detail) > 300:
        raise HTTPException(422, 'Choose a supported lettering mode/style.')
    if (mode != original_mode and 'integrated' in (mode, original_mode)) or (original_mode == 'integrated' and any((text_font_size != settings.get('text_font_size'), text_outline_width != settings.get('text_outline_width'), text_outline_color != settings.get('text_outline_color',''), text_font != settings.get('text_font', 'classic'), text_color != settings.get('text_color', ''), text != settings.get('text', ''), position != settings.get('text_position', 'bottom'), style != settings.get('text_style', 'ice'), detail != settings.get('text_style_detail', '')))):
        raise HTTPException(409, 'Model-rendered lettering needs a new generation. Use Generate artwork to change its message, style, position, or mode.')
    if job_lock.locked():
        raise HTTPException(409, 'Wait for the current image operation to finish.')
    async with job_lock:
        try:
            await asyncio.to_thread(export_print, folder / 'original.png', folder, orientation, '' if mode == 'integrated' else text, position, margin, text_mode=mode, text_style=style, text_background=background, text_scale=text_scale, text_x=text_x, text_y=text_y, text_color=text_color, text_font=text_font, text_font_size=text_font_size, text_outline_width=text_outline_width, text_outline_color=text_outline_color)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        settings = json.loads((folder / 'settings.json').read_text())
        settings.update(text=text, text_font_size=text_font_size, text_outline_width=text_outline_width, text_outline_color=text_outline_color, text_font=text_font, text_color=text_color, text_mode=mode, text_style=style, text_background=background, text_scale=text_scale, text_x=text_x, text_y=text_y, text_style_detail=detail, orientation=orientation, text_position=position, margin_mm=margin)
        (folder / 'settings.json').write_text(json.dumps(settings, indent=2, ensure_ascii=False) + '\n')
    saved_status=json.loads((folder/'status.json').read_text())
    write_status(folder,**{**saved_status,'print_updated_at':time.time()})
    return {'id': job_id, 'text': text}


@app.get('/api/jobs/{job_id}/layers')
def layers(job_id: str):
    folder=job_path(job_id)
    path=folder/'lettering-layout.json'
    return json.loads(path.read_text()) if path.exists() else {'editable':False}

@app.get('/files/{job_id}/{filename}')
def files(job_id: str, filename: str):
    if filename not in {'original.png', 'original.json', 'a4.png', 'a4.pdf', 'print.png', 'print.pdf', 'settings.json', 'generation.log', 'generation-prompt.txt', 'a4-base.png', 'lettering.png', 'lettering-layout.json'}:
        raise HTTPException(404)
    stored_name = {'print.png':'a4.png', 'print.pdf':'a4.pdf'}.get(filename, filename)
    path = job_path(job_id) / stored_name
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404)
    return FileResponse(path, filename=filename)

app.mount('/static', StaticFiles(directory=ROOT / 'studio' / 'static'), name='static')
