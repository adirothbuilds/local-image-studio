const $ = id => document.getElementById(id);
let token = '', polling = null, previewURLs = [], selectedJob = null, layerGeometry = null;
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your settings.');
  return data;
}
async function status() {
  const data = await api('/api/status'); token = data.token;
  $('model-status').textContent = data.ready ? data.model + ' · ready' : 'Model missing · run ./studio.sh download in this folder';
  $('generate').disabled = !data.ready || data.busy;
  return data;
}
async function showImage(id) {
  layerGeometry = null;
  $('canvas-controls').hidden = true;
  selectedJob = id; $('update-print').hidden = false;
  const img = document.createElement('img'); img.src = `/files/${id}/a4.png?v=${Date.now()}`; img.alt = 'Your A4 artwork preview';
  $('canvas').replaceChildren(img); $('downloads').replaceChildren();
  for (const [file, label] of [['original.png','Original'],['a4.png','A4 PNG · 300 DPI'],['a4.pdf','A4 PDF'],['settings.json','Settings'],['generation.log','Log']]) {
    const a = document.createElement('a'); a.href = `/files/${id}/${file}`; a.textContent = label; a.download = file;
    $('downloads').append(a);
  }
  const layout = await api(`/api/jobs/${id}/layers`);
  if (id !== selectedJob || !layout.editable) return;
  layerGeometry = layout;
  syncCanvasControls();
  const stage = document.createElement('div'); stage.className = 'layer-stage';
  stage.style.maxWidth = `${650 * layout.page_width / layout.page_height}px`;
  const base = document.createElement('img'); base.src = `/files/${id}/a4-base.png?v=${Date.now()}`; base.alt = 'Artwork without editable lettering'; base.draggable = false;
  const letters = document.createElement('img'); letters.id = 'editable-letters'; letters.className = 'editable-letters'; letters.src = `/files/${id}/lettering.png?v=${Date.now()}`; letters.alt = 'Drag this text layer to reposition it'; letters.draggable = false;
  stage.append(base, letters); $('canvas').replaceChildren(stage);
  let drag = null;
  letters.onpointerdown = event => {
    event.preventDefault(); letters.setPointerCapture(event.pointerId);
    drag = {x:event.clientX,y:event.clientY,cx:$('text_x').value === '' ? layout.center_x : Number($('text_x').value),cy:$('text_y').value === '' ? layout.center_y : Number($('text_y').value)};
  };
  letters.onpointermove = event => {
    if (!drag) return;
    const rect = stage.getBoundingClientRect();
    $('text_x').value = drag.cx + (event.clientX-drag.x)/rect.width;
    $('text_y').value = drag.cy + (event.clientY-drag.y)/rect.height;
    positionLayer(true);
    $('job-status').textContent = 'Layout changed · click Apply to save the new position.';
  };
  letters.onpointerup = letters.onpointercancel = () => { drag = null; };
  positionLayer();
  for (const [file,label] of [['a4-base.png','Artwork layer'],['lettering.png','Text layer']]) {
    const link=document.createElement('a');link.href=`/files/${id}/${file}`;link.download=file;link.textContent=label;$('downloads').append(link);
  }
}
async function monitor(id) {
  clearTimeout(polling);
  try {
    const data = await api(`/api/jobs/${id}`);
    $('log-panel').hidden = false; $('log').textContent = data.log;
    if (data.state === 'complete') {
      await showImage(id); await loadPrintSettings(id); $('job-status').textContent = `Ready in ${data.elapsed_seconds}s · peak GPU memory ${data.peak_gpu_memory_gb} GB`;
      await status(); await history();
    } else if (data.state === 'failed' || data.state === 'interrupted') {
      $('error').textContent = data.error; $('job-status').textContent = data.state; await status(); await history();
    } else {
      $('job-status').textContent = 'Generating locally… First runs also compile GPU kernels. See the log below.';
      polling = setTimeout(() => monitor(id), 1800);
    }
  } catch(error) { $('error').textContent = error.message; }
}
async function history() {
  const jobs = await api('/api/jobs'); $('history').replaceChildren();
  for (const job of jobs) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'history-item';
    if (job.state === 'complete') { const img = document.createElement('img'); img.src = `/files/${job.id}/original.png`; img.alt = ''; button.append(img); }
    const label = document.createElement('span'); label.textContent = job.prompt;
    const meta = document.createElement('small'); meta.textContent = `${job.state} · seed ${job.seed}`; label.append(meta); button.append(label);
    button.onclick = () => { $('error').textContent = ''; $('prompt').value = job.prompt; $('seed').value = job.seed; monitor(job.id); }; $('history').append(button);
  }
  return jobs;
}
$('generate-form').onsubmit = async event => {
  event.preventDefault(); $('error').textContent = ''; $('generate').disabled = true;
  try {
    if ($('references').files.length > 4) throw new Error('Choose at most four reference images.');
    const data = await api('/api/generate', {method: 'POST', headers: {'X-Studio-Token': token}, body: new FormData(event.target)});
    selectedJob = null; $('canvas-controls').hidden = true; $('update-print').hidden = true; $('print-message').textContent = ''; $('seed').value = data.seed; $('downloads').replaceChildren();
    const note = document.createElement('p'); note.textContent = 'Your image is taking shape…'; note.className = 'empty'; $('canvas').replaceChildren(note);
    await history(); monitor(data.id);
  } catch(error) { $('error').textContent = error.message; await status(); }
};
$('references').onchange = () => {
  previewURLs.forEach(url => URL.revokeObjectURL(url)); previewURLs = []; $('reference-preview').replaceChildren();
  for (const file of Array.from($('references').files).slice(0,4)) { const img = document.createElement('img'); img.src = URL.createObjectURL(file); previewURLs.push(img.src); img.alt = 'Reference preview'; $('reference-preview').append(img); }
};
$('preset').onchange = () => { if (['portrait','landscape'].includes($('preset').value)) $('orientation').value = $('preset').value; };
$('refresh').onclick = async () => { try { await status(); await history(); } catch(error) { $('error').textContent = error.message; } };
(async () => { try { await status(); const jobs = await history(); const running = jobs.find(j => j.state === 'running'); if (running) monitor(running.id); else if (jobs.find(j => j.state === 'complete')) { const latest = jobs.find(j => j.state === 'complete'); await showImage(latest.id); await loadPrintSettings(latest.id); } } catch(error) { $('error').textContent = error.message; } })();

async function loadPrintSettings(id) {
  const settings = await api(`/files/${id}/settings.json`);
  for (const field of ['text','orientation','text_position','margin_mm','text_mode','text_style','text_style_detail','text_background','text_x','text_y','text_scale']) $(field).value = settings[field] ?? ({text_mode:'overlay',text_style:'ice',text_background:'banner',text_scale:1}[field] ?? '');
  letteringMode(); positionLayer();
  $('print-message').textContent = settings.text ? `${settings.text_mode === 'integrated' ? 'AI lettering requested (check spelling)' : 'Message on this print'}: ${settings.text}` : 'This print has no message. Enter one on the left and click Apply below the downloads.';
}
$('update-print').onclick = async () => {
  if (!selectedJob) return;
  $('error').textContent = ''; $('update-print').disabled = true; $('canvas-apply').disabled = true;
  try {
    await api(`/api/jobs/${selectedJob}/print`, {method:'POST', headers:{'X-Studio-Token':token,'Content-Type':'application/json'}, body:JSON.stringify({text:$('text').value, text_mode:$('text_mode').value, text_style:$('text_style').value, text_background:$('text_background').value, text_scale:Number($('text_scale').value), text_x:$('text_x').value === '' ? null : Number($('text_x').value), text_y:$('text_y').value === '' ? null : Number($('text_y').value), text_style_detail:$('text_style_detail').value, orientation:$('orientation').value, text_position:$('text_position').value, margin_mm:Number($('margin_mm').value)})});
    await showImage(selectedJob); await loadPrintSettings(selectedJob);
    $('job-status').textContent = 'A4 print updated. Original artwork preserved; no regeneration needed.';
  } catch(error) { $('error').textContent = error.message; }
  finally { $('update-print').disabled = false; $('canvas-apply').disabled = false; }
};

function letteringMode() {
  const integrated = $('text_mode').value === 'integrated';
  const styled = $('text_mode').value === 'styled';
  $('lettering-options').hidden = !(integrated || styled);
  $('ai-art-direction').hidden = !integrated;
  $('exact-text-background').hidden = !styled;
  $('manual-layout').hidden = integrated;
  syncCanvasControls();
  $('text-size-label').textContent = `${Math.round(Number($('text_scale').value)*100)}%`;
  $('lettering-hint').textContent = integrated ? 'The AI designs the message into the scene. Inspect every letter before printing: Hebrew and names can be misspelled. Changing AI lettering requires a new generation.' : styled ? 'Exact Hebrew letters with decorative ice, ribbon, or gold styling. Change the message, style, or placement and Apply; no regeneration needed. AI-drawn misspelled text already in a picture requires a new clean generation.' : 'Exact typed text is added to the A4 export. You can change it later without regenerating the picture.';
  $('update-print').textContent = integrated ? 'Apply paper settings · lettering changes need Generate' : 'Apply message & print settings to this image';
}
$('text_mode').onchange = letteringMode;
letteringMode();

function positionLayer(saveClamped = false) {
  const image = document.getElementById('editable-letters');
  if (!image || !layerGeometry) return;
  const g = layerGeometry, ratio = Number($('text_scale').value) / g.scale;
  const w = g.width * ratio / g.page_width, h = g.height * ratio / g.page_height;
  const mx = g.margin/g.page_width, my = g.margin/g.page_height;
  let cx = $('text_x').value === '' ? g.center_x : Number($('text_x').value);
  let cy = $('text_y').value === '' ? g.center_y : Number($('text_y').value);
  cx = Math.max(mx+w/2,Math.min(1-mx-w/2,cx));
  cy = Math.max(my+h/2,Math.min(1-my-h/2,cy));
  image.style.left = `${(cx-w/2)*100}%`; image.style.top = `${(cy-h/2)*100}%`; image.style.width = `${w*100}%`;
  if (saveClamped) { $('text_x').value=cx; $('text_y').value=cy; }
}
$('text_scale').oninput = () => { letteringMode(); positionLayer(true); $('job-status').textContent='Text size changed · click Apply to save.'; };
$('text_position').onchange = () => {
  $('text_x').value=''; $('text_y').value='';
  if (layerGeometry) {
    const g=layerGeometry, h=g.height*Number($('text_scale').value)/g.scale;
    $('text_x').value=.5;
    $('text_y').value = $('text_position').value === 'top' ? (g.margin+35+h/2)/g.page_height : ($('text_position').value === 'center' ? .5 : 1-(g.margin+35+h/2)/g.page_height);
    positionLayer(true);
  }
};

function syncCanvasControls() {
  $('canvas-controls').hidden = !layerGeometry || $('text_mode').value === 'integrated';
  $('canvas-text-scale').value = $('text_scale').value;
  $('canvas-size-label').textContent = `${Math.round(Number($('text_scale').value)*100)}%`;
  $('canvas-text-background').value = $('text_background').value;
  $('canvas-background-controls').hidden = $('text_mode').value !== 'styled';
}
$('canvas-text-scale').oninput = () => {
  $('text_scale').value = $('canvas-text-scale').value;
  $('text_scale').oninput();
};
$('text_background').onchange = () => {
  syncCanvasControls();
  $('job-status').textContent = 'Background changed · click Apply to update the preview and downloads.';
};
$('canvas-text-background').onchange = () => {
  $('text_background').value = $('canvas-text-background').value;
  $('text_background').onchange();
};
$('canvas-apply').onclick = () => $('update-print').click();
