/**
 * main.js
 *
 * Glue only: builds the Scene / Viewport / Renderer, wires the toolbar and
 * DOM events to whichever tool is active, and talks to the Flask API for
 * save / load. No geometry logic lives here.
 */

import { Scene, loadEtcFormulas } from './model.js';
import { Viewport, Renderer, formatNumber, MAX_DECIMALS } from './view.js';
import { TOOL_REGISTRY } from './tools.js';

const canvas = document.getElementById('cv');
const wrap = document.getElementById('canvasWrap');
const hintEl = document.getElementById('hint');
const listEl = document.getElementById('objectList');
const toolbar = document.getElementById('toolbar');

let scene = new Scene();
const viewport = new Viewport();
const renderer = new Renderer(canvas, viewport, scene);

// ------------------------------------------------------------------ render
let renderQueued = false;
function requestRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => { renderQueued = false; renderer.render(); });
}

function bindScene(newScene) {
  scene = newScene;
  renderer.scene = scene;
  scene.onChange(() => { requestRender(); refreshObjectList(); syncRenameBox(); syncColorSwatches(); commitState(); });
  refreshObjectList();
  requestRender();
}

// ------------------------------------------------------------------- tools
const toolContext = () => ({
  scene, viewport, renderer, requestRender,
  setHint: (t) => { hintEl.textContent = t; },
  setCursor: (c) => { canvas.style.cursor = c; },
});

let activeTool = null;
let activeName = null;

// ------------------------------------------------------------ undo / redo
// Every finished change stores the previous scene as a JSON snapshot. A drag
// counts as ONE change (committed on pointerup), not hundreds. Undo / redo
// rebuild the scene from a snapshot, the same way Load does.
const MAX_HISTORY = 100;
const undoStack = [];
const redoStack = [];
let currentState = null;     // JSON string of the scene as of the last commit
let gestureActive = false;   // true between pointerdown and pointerup
let restoring = false;       // true while undo/redo is rebuilding the scene
const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');

function serializeScene() { return JSON.stringify(scene.toJSON()); }

function updateHistoryButtons() {
  undoBtn.disabled = !undoStack.length;
  redoBtn.disabled = !redoStack.length;
}

function commitState() {
  if (restoring || gestureActive || currentState === null) return;
  const now = serializeScene();
  if (now === currentState) return;   // e.g. selection-only change
  undoStack.push(currentState);
  if (undoStack.length > MAX_HISTORY) undoStack.shift();
  redoStack.length = 0;
  currentState = now;
  updateHistoryButtons();
}

function restoreState(stateStr) {
  restoring = true;
  try {
    bindScene(Scene.fromJSON(JSON.parse(stateStr)));
    setTool(activeName);   // tools hold a reference to the scene, so rebuild the active one
  } finally {
    restoring = false;
  }
  currentState = serializeScene();
  updateHistoryButtons();
}

function undo() {
  if (!undoStack.length) return;
  redoStack.push(currentState);
  restoreState(undoStack.pop());
}

function redo() {
  if (!redoStack.length) return;
  undoStack.push(currentState);
  restoreState(redoStack.pop());
}

undoBtn.addEventListener('click', undo);
redoBtn.addEventListener('click', redo);
canvas.addEventListener('pointercancel', () => { resetTouch(); gestureActive = false; commitState(); });

// ------------------------------------------------------------- export PNG
// Draws the current canvas onto an off-screen copy with the paper colour
// behind it (the canvas itself is transparent), then downloads it.
document.getElementById('exportPngBtn').addEventListener('click', () => {
  renderer.render();
  const out = document.createElement('canvas');
  out.width = canvas.width;
  out.height = canvas.height;
  const ctx = out.getContext('2d');
  ctx.fillStyle = '#fdfcf9';
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(canvas, 0, 0);
  const base = (document.getElementById('sceneName').value.trim() || 'geometry')
    .replace(/[^\w\-]+/g, '_');
  out.toBlob((blob) => {
    if (!blob) { hintEl.textContent = 'Export failed.'; return; }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = base + '.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    hintEl.textContent = `Exported ${base}.png`;
  }, 'image/png');
});

// data-tool buttons live in three places: the icon toolbar at the top, the
// "Triangle circles" section in the sidebar (#triCircleBtns), and the
// "Triangle centers" section (#triCenterBtns) -- all are kept in sync with
// whichever tool is active.
const triCircleBtns = document.getElementById('triCircleBtns');
const triCenterBtns = document.getElementById('triCenterBtns');

function setTool(name) {
  if (!TOOL_REGISTRY[name]) return;
  if (activeTool) activeTool.deactivate();
  activeName = name;
  activeTool = new TOOL_REGISTRY[name](toolContext());
  activeTool.activate();
  toolbar.querySelectorAll('button[data-tool]').forEach(b =>
    b.classList.toggle('active', b.dataset.tool === name));
  if (triCircleBtns) {
    triCircleBtns.querySelectorAll('button[data-tool]').forEach(b =>
      b.classList.toggle('active', b.dataset.tool === name));
  }
  if (triCenterBtns) {
    triCenterBtns.querySelectorAll('button[data-tool]').forEach(b =>
      b.classList.toggle('active', b.dataset.tool === name));
  }
  requestRender();

  // Action tools (label / visibility / delete) apply to an existing selection
  // instantly, so once they've run, hand control back to Select.
  if (['label', 'visibility', 'delete'].includes(name) && scene.selected().length) {
    activeTool.deactivate();
    setTool('select');
  }

  // Color / Rename stay active (like GeoGebra's paint bucket) so several
  // components can be clicked one after another without reselecting the
  // tool. Re-arm whatever was already chosen in the sidebar.
  if (name === 'color') activeTool.color = colorPicker.value;
  if (name === 'rename') activeTool.text = renameInput.value.trim();
}

toolbar.addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-tool]');
  if (btn) setTool(btn.dataset.tool);
});
if (triCircleBtns) {
  triCircleBtns.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-tool]');
    if (btn) setTool(btn.dataset.tool);
  });
}
if (triCenterBtns) {
  triCenterBtns.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-tool]');
    if (btn) setTool(btn.dataset.tool);
  });
}

// ------------------------------------------------------------ pointer events
function toEvent(e) {
  const rect = canvas.getBoundingClientRect();
  const screen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  return { screen, world: viewport.screenToWorld(screen),
           shift: e.shiftKey, ctrl: e.ctrlKey || e.metaKey };
}

// Mouse and pen go straight to the active tool. Touch adds two things:
//  * two fingers = pinch-zoom + pan, with ANY tool active (a phone has no
//    wheel, and most tools can't pan);
//  * the first finger's press is held back for a moment, so a second finger
//    landing right after it becomes a pinch instead of a stray point/segment.
// A quick tap, or a finger that starts moving, is handed to the tool at once.
const TOUCH_HOLD_MS = 110;   // wait this long for a possible second finger
const TOUCH_SLOP = 8;        // px a finger may wobble before it counts as a drag
const touches = new Map();   // pointerId -> {x, y} of each finger on the canvas
let pending = null;          // { e, timer }: a touch press not yet given to the tool
let pinch = null;            // { dist, cx, cy } while two fingers are down
let ignoreTouch = false;     // after a pinch, ignore the leftover finger until all lift
let lastTouchEvent = null;   // newest event of the finger the tool is following

function canvasPos(e) {
  const rect = canvas.getBoundingClientRect();
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

function sendDown(e) {
  gestureActive = true;
  activeTool && activeTool.onPointerDown(toEvent(e));
  requestRender();
}

function flushPending() {
  if (!pending) return;
  clearTimeout(pending.timer);
  const e = pending.e;
  pending = null;
  lastTouchEvent = e;
  sendDown(e);
}

function resetTouch() {
  if (pending) clearTimeout(pending.timer);
  pending = null; pinch = null; ignoreTouch = false; lastTouchEvent = null;
  touches.clear();
}

function pinchState() {
  const [a, b] = [...touches.values()];
  return { dist: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
}

function startPinch() {
  if (pending) { clearTimeout(pending.timer); pending = null; }   // drop the held press
  if (gestureActive && lastTouchEvent) {
    // The tool already got the first finger's press: finish that gesture cleanly.
    activeTool && activeTool.onPointerUp(toEvent(lastTouchEvent));
    gestureActive = false;
    commitState();
  }
  ignoreTouch = true;
  pinch = pinchState();
}

function updatePinch() {
  const now = pinchState();
  if (pinch.dist > 0 && now.dist > 0) {
    viewport.zoomAt({ x: pinch.cx, y: pinch.cy }, now.dist / pinch.dist);   // zoom about the old centre
  }
  viewport.panBy(now.cx - pinch.cx, now.cy - pinch.cy);                    // then follow the centre
  pinch = now;
  requestRender();
}

canvas.addEventListener('pointerdown', (e) => {
  canvas.setPointerCapture(e.pointerId);
  if (e.pointerType !== 'touch') { sendDown(e); return; }

  touches.set(e.pointerId, canvasPos(e));
  if (touches.size === 2) { startPinch(); return; }
  if (touches.size > 2 || ignoreTouch) return;
  pending = { e, start: canvasPos(e), timer: setTimeout(flushPending, TOUCH_HOLD_MS) };
});

canvas.addEventListener('pointermove', (e) => {
  if (e.pointerType === 'touch') {
    if (!touches.has(e.pointerId)) return;
    const pos = canvasPos(e);
    touches.set(e.pointerId, pos);
    if (pinch) { if (touches.size === 2) updatePinch(); return; }
    if (ignoreTouch || touches.size > 1) return;
    if (pending) {
      if (Math.hypot(pos.x - pending.start.x, pos.y - pending.start.y) < TOUCH_SLOP) return;
      flushPending();   // it is a drag: give the tool the press first
    }
    lastTouchEvent = e;
  }
  activeTool && activeTool.onPointerMove(toEvent(e));
});

canvas.addEventListener('pointerup', (e) => {
  if (e.pointerType === 'touch') {
    touches.delete(e.pointerId);
    if (pinch) {
      if (touches.size < 2) pinch = null;
      if (touches.size === 0) ignoreTouch = false;
      return;
    }
    if (ignoreTouch) { if (touches.size === 0) ignoreTouch = false; return; }
    if (pending) flushPending();   // a quick tap: deliver the press before the release
    lastTouchEvent = null;
  }
  activeTool && activeTool.onPointerUp(toEvent(e));
  gestureActive = false;
  commitState();
  requestRender();
});

// A long press would otherwise open the browser's context menu over the drawing.
canvas.addEventListener('contextmenu', (e) => e.preventDefault());
canvas.addEventListener('dblclick', (e) => {
  activeTool && activeTool.onDoubleClick(toEvent(e));
});

// Wheel zoom works no matter which tool is active.
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const at = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  viewport.zoomAt(at, e.deltaY < 0 ? 1.1 : 1 / 1.1);
  requestRender();
}, { passive: false });

// ---------------------------------------------------------------- keyboard
window.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;

  // Ctrl+Z = undo, Ctrl+Y or Ctrl+Shift+Z = redo.
  if ((e.ctrlKey || e.metaKey) && !e.altKey) {
    const k = e.key.toLowerCase();
    if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
    if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); return; }
  }

  // Delete / Backspace always removes the current selection.
  if ((e.key === 'Delete' || e.key === 'Backspace') && scene.selected().length) {
    e.preventDefault();
    scene.remove(scene.selected());
    return;
  }
  activeTool && activeTool.onKey(e);
});

// -------------------------------------------------------------- object list
function refreshObjectList() {
  listEl.innerHTML = '';
  if (!scene.objects.length) {
    listEl.innerHTML = '<div class="empty">No objects yet.</div>';
    return;
  }
  for (const o of scene.objects) {
    const row = document.createElement('div');
    row.className = 'obj-row' + (o.selected ? ' sel' : '') + (o.visible ? '' : ' hidden');
    let detail = '';
    if (o.type === 'point') detail = `(${o.x.toFixed(2)}, ${o.y.toFixed(2)})`;
    else if (o.type === 'text') detail = '';
    else if (o.type === 'segment') detail = `length ${formatNumber(o.length(), renderer.decimals)}`;
    else if (o.type === 'circle') detail = `r = ${o.radius().toFixed(3)}`;
    else if (o.type === 'derivedCircle') detail = o.isValid() ? `r = ${o.radius().toFixed(3)}` : 'degenerate';
    else if (o.type === 'derivedPoint') detail = o.isValid() ? `(${o.x.toFixed(2)}, ${o.y.toFixed(2)})` : 'degenerate';
    else if (o.type === 'intersectionPoint') detail = o.isValid() ? `(${o.x.toFixed(2)}, ${o.y.toFixed(2)})` : 'no crossing';
    else if (o.type === 'semicircle') detail = `r = ${o.radius().toFixed(3)}`;
    else if (o.type === 'ellipse') detail = o.isValid() ? `a = ${o.semiAxes().a.toFixed(3)}, b = ${o.semiAxes().b.toFixed(3)}` : 'degenerate';
    else if (o.type === 'polygon') detail = `area ${o.area().toFixed(3)}`;
    // textContent (never innerHTML): labels are user-typed or come from a
    // loaded scene file, so they must not be parsed as HTML.
    const nameEl = document.createElement('span');
    nameEl.className = 'obj-name';
    nameEl.textContent = `${o.type} ${o.label || '#' + o.id}`;
    const detailEl = document.createElement('span');
    detailEl.className = 'obj-detail';
    detailEl.textContent = detail;
    row.append(nameEl, detailEl);
    // Clicking a row toggles visibility -- the only way to bring back a
    // hidden object, since you can't click something you can't see.
    row.addEventListener('click', () => { o.visible = !o.visible; scene._emit(); });
    listEl.appendChild(row);
  }
}

// ------------------------------------------------------------- side buttons
document.getElementById('showAllBtn').addEventListener('click', () => {
  scene.objects.forEach(o => { o.visible = true; });
  scene._emit();
});
document.getElementById('clearBtn').addEventListener('click', () => {
  if (!scene.objects.length || confirm('Remove everything from the canvas?')) {
    scene.remove([...scene.objects]);
  }
});

// --------------------------------------------------------- lengths toggle
const lengthsBtn = document.getElementById('lengthsToggle');
lengthsBtn.addEventListener('click', () => {
  renderer.showLengths = !renderer.showLengths;
  lengthsBtn.textContent = 'Lengths: ' + (renderer.showLengths ? 'On' : 'Off');
  lengthsBtn.classList.toggle('on', renderer.showLengths);
  requestRender();
});

// ------------------------------------------------------ length decimals
// +/- buttons set how many digits after the decimal point segment lengths
// show (canvas labels and the Objects list). 0 .. MAX_DECIMALS. The stored
// geometry is never rounded -- only the displayed text -- so changing this
// loses no accuracy. The choice is remembered between visits.
const decDownBtn = document.getElementById('decDownBtn');
const decUpBtn = document.getElementById('decUpBtn');
const decLabel = document.getElementById('decLabel');

function setDecimals(n, save = true) {
  const d = Math.min(MAX_DECIMALS, Math.max(0, Math.round(n)));
  renderer.decimals = d;
  decLabel.textContent = 'Decimals: ' + d;
  decDownBtn.disabled = d <= 0;
  decUpBtn.disabled = d >= MAX_DECIMALS;
  if (save) { try { localStorage.setItem('geometryDecimals', String(d)); } catch { /* private mode: ignore */ } }
  refreshObjectList();
  requestRender();
}
decDownBtn.addEventListener('click', () => setDecimals(renderer.decimals - 1));
decUpBtn.addEventListener('click', () => setDecimals(renderer.decimals + 1));
{
  let saved = NaN;
  try { saved = parseInt(localStorage.getItem('geometryDecimals'), 10); } catch { /* ignore */ }
  setDecimals(Number.isFinite(saved) ? saved : renderer.decimals, false);
}

// --------------------------------------------------------------- rename
// GeoGebra-style: type a name, then click any component on the canvas to
// apply it -- no need to select first. If something is already selected
// when a name is typed, it applies immediately (handy for the common case
// of "I just clicked a point, now let me name it").
const renameInput = document.getElementById('renameInput');
const renameHint = document.getElementById('renameHint');

function armRename() {
  const name = renameInput.value.trim();
  if (activeName !== 'rename') setTool('rename');
  activeTool.text = name;
  if (!name) { renameHint.textContent = 'Type a name, then click a component.'; return; }

  const sel = scene.selected();
  if (sel.length) {
    activeTool.apply(sel);
    renameHint.textContent = `Renamed ${sel.length} object(s) to "${name}".`;
  } else {
    renameHint.textContent = `Click a component to name it "${name}".`;
  }
}

document.getElementById('renameBtn').addEventListener('click', armRename);
renameInput.addEventListener('input', armRename);
renameInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); armRename(); }
});

// Show the current label of the selected object in the box, so it is easy to edit.
function syncRenameBox() {
  const sel = scene.selected();
  if (document.activeElement === renameInput) return; // don't overwrite while typing
  renameInput.value = sel.length === 1 ? sel[0].label : '';
}

// ---------------------------------------------------------------- color
// A small curated palette (swatches) plus a native <input type=color> for
// anything else. Applies to every currently selected object -- points,
// segments, lines, circles, semicircles, polygons, angles, text -- since
// they all share GeoObject's `color` field.
const PALETTE = [
  '#1c2321', // ink (default)
  '#b3541e', // point orange
  '#c0392b', // red
  '#e07b00', // orange
  '#d4a72c', // gold
  '#2f5d50', // accent green
  '#1f8a5f', // green
  '#2a6df4', // blue
  '#6a4fc2', // purple
  '#c23b8f', // magenta
];

const colorSwatchesEl = document.getElementById('colorSwatches');
const colorPicker = document.getElementById('colorPicker');
const colorHint = document.getElementById('colorHint');

PALETTE.forEach((hex) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'swatch';
  b.style.background = hex;
  b.title = hex;
  b.dataset.color = hex;
  b.addEventListener('click', () => { colorPicker.value = hex; armColor(hex); });
  colorSwatchesEl.appendChild(b);
});

// GeoGebra-style: pick a color (swatch or the native picker), then click
// any component on the canvas to apply it -- no need to select first. If
// something is already selected, the color applies immediately.
function armColor(hex) {
  if (activeName !== 'color') setTool('color');
  activeTool.color = hex;

  const sel = scene.selected();
  if (sel.length) {
    activeTool.apply(sel);
    colorHint.textContent = `Colored ${sel.length} object(s).`;
  } else {
    colorHint.textContent = 'Click a component to color it.';
  }
  syncColorSwatches();
}

document.getElementById('colorApplyBtn').addEventListener('click', () => armColor(colorPicker.value));
colorPicker.addEventListener('input', () => armColor(colorPicker.value));

// Highlight the swatch matching the selected object's current color (if any).
function syncColorSwatches() {
  const sel = scene.selected();
  const current = sel.length === 1 ? sel[0].color : null;
  colorSwatchesEl.querySelectorAll('.swatch').forEach((b) => {
    b.classList.toggle('active', !!current && b.dataset.color.toLowerCase() === current.toLowerCase());
  });
  if (current) colorPicker.value = current;
}

// ---------------------------------------------------------------- scale
// Resize the WHOLE construction about its common centre, ALWAYS -- the
// current selection is ignored on purpose. (An earlier version scaled only
// the selection when there was one, so a stray selected point made the
// buttons look broken.) Shapes are built on Point objects, so segments /
// polygons / circles and the derived circles/centers follow automatically.
const scaleFactorEl = document.getElementById('scaleFactor');
const scaleHintEl = document.getElementById('scaleHint');

function applyScale(factor) {
  if (!(factor > 0) || !isFinite(factor)) {
    scaleHintEl.textContent = 'Enter a number greater than 0 (e.g. 0.5 to shrink, 2 to enlarge).';
    return;
  }
  if (!scene.objects.length) {
    scaleHintEl.textContent = 'Canvas is empty -- draw something first.';
    return;
  }
  const moved = scene.scaleObjects(scene.objects, factor);
  scaleHintEl.textContent = moved
    ? `Scaled the whole construction by ${+factor.toFixed(4)} (${moved} points).`
    : 'Nothing to scale (no movable points).';
}

document.getElementById('scaleDownBtn').addEventListener('click', () => applyScale(0.8));
document.getElementById('scaleUpBtn').addEventListener('click', () => applyScale(1.25));
document.getElementById('scaleApplyBtn').addEventListener('click', () =>
  applyScale(parseFloat(scaleFactorEl.value)));
scaleFactorEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); applyScale(parseFloat(scaleFactorEl.value)); }
});

// -------------------------------------------------------------- save / load
const saveNameEl = document.getElementById('sceneName');
const sceneListEl = document.getElementById('sceneList');

async function refreshSceneList() {
  try {
    const res = await fetch('/api/scenes');
    const data = await res.json();
    sceneListEl.innerHTML = '<option value="">-- saved scenes --</option>';
    (data.scenes || []).forEach(n => {
      const opt = document.createElement('option');
      opt.value = n; opt.textContent = n;
      sceneListEl.appendChild(opt);
    });
  } catch { /* server offline: leave the list empty */ }
}

document.getElementById('saveBtn').addEventListener('click', async () => {
  const name = saveNameEl.value.trim();
  if (!name) { hintEl.textContent = 'Enter a name to save this scene.'; return; }
  const res = await fetch('/api/scenes/' + encodeURIComponent(name), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scene.toJSON()),
  });
  const data = await res.json();
  hintEl.textContent = res.ok ? `Saved "${name}".` : `Save failed: ${data.message}`;
  refreshSceneList();
});

document.getElementById('loadBtn').addEventListener('click', async () => {
  const name = sceneListEl.value;
  if (!name) return;
  const res = await fetch('/api/scenes/' + encodeURIComponent(name));
  const data = await res.json();
  if (!res.ok) { hintEl.textContent = `Load failed: ${data.message}`; return; }
  bindScene(Scene.fromJSON(data.scene));
  setTool(activeName);   // re-point the active tool at the newly loaded scene
  commitState();         // loading is undoable too
  saveNameEl.value = name;
  hintEl.textContent = `Loaded "${name}".`;
});

// -------------------------------------------------------------------- boot
// ------------------------------------------------------- phone / tablet UI
// On a narrow screen the side panel is a drawer: the Panel button opens it,
// and picking a tool from it closes it again so the drawing is visible.
const sidebarEl = document.getElementById('sidebar');
const backdropEl = document.getElementById('sidebarBackdrop');
const narrowScreen = window.matchMedia('(max-width: 860px)');

function setPanel(open) {
  sidebarEl.classList.toggle('open', open);
  backdropEl.classList.toggle('open', open);
}
document.getElementById('panelToggle').addEventListener('click', () =>
  togglePanel());
document.getElementById('sidebarClose').addEventListener('click', () => setPanel(false));
backdropEl.addEventListener('click', () => setPanel(false));

// Phone: the panel is a drawer. Desktop: the same button hides / shows the side
// panel so the drawing area gets the full width (choice is remembered).
function togglePanel() {
  if (narrowScreen.matches) { setPanel(!sidebarEl.classList.contains('open')); return; }
  const hidden = document.body.classList.toggle('panel-hidden');
  try { localStorage.setItem('geometryPanelHidden', hidden ? '1' : '0'); } catch { /* ignore */ }
  resize();
}
try {
  const savedPanel = localStorage.getItem('geometryPanelHidden');
  // Inside the /app page (an iframe) the panel starts hidden so the drawing gets the room.
  if (savedPanel === '1' || (savedPanel === null && window.self !== window.top)) document.body.classList.add('panel-hidden');
} catch { /* ignore */ }
sidebarEl.addEventListener('click', (e) => {
  if (narrowScreen.matches && e.target.closest('button[data-tool]')) setPanel(false);
});

// Done / Cancel / Flip stand in for the Enter / Esc / F keys, which a touch
// screen does not have. They feed the same key handling the tools already use.
function sendKey(key) {
  if (!activeTool) return;
  activeTool.onKey({ key, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false,
                     preventDefault() {} });
  requestRender();
}
document.getElementById('keyDoneBtn').addEventListener('click', () => sendKey('Enter'));
document.getElementById('keyCancelBtn').addEventListener('click', () => sendKey('Escape'));
document.getElementById('keyFlipBtn').addEventListener('click', () => sendKey('f'));

function resize() {
  renderer.resize(wrap.clientWidth, wrap.clientHeight);
  requestRender();
}
window.addEventListener('resize', resize);

bindScene(scene);
resize();
refreshSceneList();
setTool('point');
currentState = serializeScene();
updateHistoryButtons();

// Load the X(n) formulas in the background; a scene that already contains
// X(n) points redraws as soon as they arrive (this does not touch undo).
loadEtcFormulas().then(() => { scene._emit(); });
