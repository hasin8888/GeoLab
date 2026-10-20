/**
 * tools.js
 *
 * One class per tool, all sharing the Tool interface below. main.js just
 * asks the registry for the active tool and forwards pointer events, so
 * adding an 11th tool means writing one class and one registry entry --
 * nothing else changes.
 *
 * Tools receive events already converted to both spaces:
 *     ev = { screen: {x,y}, world: {x,y}, shift: bool, ctrl: bool }
 */

import { Point, IntersectionPoint, ConstructedPoint, GliderPoint, APEX_ISO_K, APEX_EQUI_K,
         TextNote, Segment, Line, Polygon, Circle, Ellipse, Semicircle, Angle,
         DerivedCircle, DerivedPoint, DERIVED_CIRCLE_CENTER_LABELS,
         circumcircleOf, incircleOf, ninePointCircleOf, excirclesOf,
         spiekerCircleOf, brocardCircleOf, mandartCircleOf,
         apolloniusCirclesOf, conwayCircleOf,
         orthocentroidalCircleOf, tangentialTriangleCircleOf,
         bevanCircleOf, incentralTriangleCircleOf, johnsonCirclesOf,
         firstLemoineCircleOf, taylorCircleOf,
         incenterOf, centroidOf, circumcenterOf, orthocenterOf,
         ninePointCenterOf, symmedianPointOf, spiekerCenterOf,
         ETC_FORMULAS, etcCenterOf } from './model.js';

// Click tolerance in screen pixels. A fingertip is much less precise than a
// mouse pointer, so touch screens get a larger target.
const HIT_PX = (typeof window !== 'undefined' && window.matchMedia &&
                window.matchMedia('(pointer: coarse)').matches) ? 20 : 10;

export class Tool {
  constructor(ctx) {
    this.scene = ctx.scene;
    this.view = ctx.viewport;
    this.renderer = ctx.renderer;
    this.requestRender = ctx.requestRender;
    this.setHint = ctx.setHint;
    this.setCursor = ctx.setCursor;
  }
  get name() { return 'tool'; }
  get hint() { return ''; }
  activate() { this.setHint(this.hint); this.setCursor('default'); }
  deactivate() { this.cancel(); }
  cancel() { this.renderer.preview = null; this.requestRender(); }
  onPointerDown(_ev) {}
  onPointerMove(_ev) {}
  onPointerUp(_ev) {}
  onDoubleClick(_ev) {}
  onKey(_e) {}

  /** Existing object under the pointer, or null. */
  hit(ev, filterType = null) {
    const tol = this.view.pxToWorld(HIT_PX);
    const found = this.scene.hitTest(ev.world, tol);
    return found && (!filterType || found.type === filterType) ? found : null;
  }

  /** A plain Point or a live IntersectionPoint under the pointer, or null. */
  hitPoint(ev) {
    const found = this.hit(ev);
    return found && ['point', 'intersectionPoint', 'glider', 'constructedPoint'].includes(found.type) ? found : null;
  }

  /**
   * What a NEW point placed at this click should attach to: the exact crossing
   * of two shapes (green ring), a single shape it can slide along (blue ring),
   * or nothing (a free point). Returns {kind, x, y, ...} or null.
   */
  attachAt(ev) {
    const tol = this.view.pxToWorld(HIT_PX);
    const cross = this.scene.snapToIntersection(ev.world, tol);
    if (cross) return { kind: 'intersection', ...cross };
    const host = this.scene.snapToHost(ev.world, tol);
    return host ? { kind: 'glider', ...host } : null;
  }

  /** The (not yet added) point for a click: live when it lands on shapes, free otherwise. */
  makePointFor(ev) {
    const at = this.attachAt(ev);
    if (!at) return new Point(ev.world.x, ev.world.y);
    if (at.kind === 'intersection') return new IntersectionPoint(at.a, at.b, at.x, at.y);
    return new GliderPoint(at.host, at.t);
  }

  /**
   * Reuse the Point under the cursor, or create a new one. This is what
   * lets Segment / Line / Polygon / Circle attach to existing points
   * instead of always spawning duplicates on top of them.
   */
  pointAt(ev) {
    const existing = this.hitPoint(ev);
    if (existing) return { point: existing, created: false };
    // Lands exactly on a crossing / on a shape when the click is near one, as a
    // LIVE point that follows those shapes; otherwise it is an ordinary free Point.
    const p = this.scene.add(this.makePointFor(ev));
    return { point: p, created: true };
  }
}

// ---------------------------------------------------------------------------
// 1. MOVE  (pan the canvas, or drag a point)
// ---------------------------------------------------------------------------
export class MoveTool extends Tool {
  get name() { return 'move'; }
  get hint() { return 'Drag a point to move it. Drag empty space to pan. Scroll to zoom.'; }
  activate() { super.activate(); this.mode = null; }

  onPointerDown(ev) {
    const best = this.hit(ev);
    const sliding = best && typeof best.draggable === 'function' && best.draggable() ? best : null;
    const p = this.hit(ev, 'point') || this.hit(ev, 'text') || sliding;
    if (p) {
      this.mode = 'drag';
      this.target = p;
      this.grabOffset = { x: p.x - ev.world.x, y: p.y - ev.world.y };
      this.setCursor('grabbing');
    } else {
      this.mode = 'pan';
      this.last = ev.screen;
      this.setCursor('grabbing');
    }
  }

  onPointerMove(ev) {
    if (this.mode === 'drag') {
      // Every Segment/Line/Circle/Polygon on this point follows automatically,
      // because they hold a reference to it rather than their own copy.
      const nx = ev.world.x + this.grabOffset.x, ny = ev.world.y + this.grabOffset.y;
      if (this.target.dragTo) this.target.dragTo(nx, ny); // glider / free apex: slides along its shape
      else { this.target.x = nx; this.target.y = ny; }
      this.scene._emit();
    } else if (this.mode === 'pan') {
      this.view.panBy(ev.screen.x - this.last.x, ev.screen.y - this.last.y);
      this.last = ev.screen;
      this.requestRender();
    } else {
      this.setCursor((this.hit(ev, 'point') || this.hit(ev, 'text')) ? 'grab' : 'default');
    }
  }

  onPointerUp() { this.mode = null; this.setCursor('default'); }
}

// ---------------------------------------------------------------------------
// 2. POINT
// ---------------------------------------------------------------------------
export class PointTool extends Tool {
  get name() { return 'point'; }
  get hint() { return 'Click to place a point. On a crossing it snaps to the intersection; on a line or circle it slides along it.'; }
  onPointerMove(ev) {
    // Ring = where the click will attach: green on a crossing of two shapes,
    // blue when the new point will slide along a single shape.
    const att = this.hitPoint(ev) ? null : this.attachAt(ev);
    this.renderer.preview = att ? { draw: (ctx, view) => {
      const s = view.worldToScreen(att);
      ctx.save(); ctx.strokeStyle = att.kind === 'intersection' ? '#2f7d5a' : '#2a6df4'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(s.x, s.y, 9, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    } } : null;
    this.requestRender();
  }
  activate() { super.activate(); this.setCursor('crosshair'); }
  onPointerDown(ev) {
    if (this.hitPoint(ev)) return; // don't stack points on top of each other
    this.scene.add(this.makePointFor(ev));
  }
}

// ---------------------------------------------------------------------------
// Shared base for tools that collect N points then build one object
// (Segment, Line, Circle). Polygon overrides the "when am I finished" rule.
// ---------------------------------------------------------------------------
class TwoPointTool extends Tool {
  activate() { super.activate(); this.setCursor('crosshair'); this.first = null; this.created = []; }

  /** Build the resulting object from the two points. Subclasses implement this. */
  build(_p1, _p2) { throw new Error('not implemented'); }
  /** Draw the rubber-band preview while the second point is being chosen. */
  drawPreview(_ctx, _view, _a, _cursor) {}

  onPointerDown(ev) {
    const { point, created } = this.pointAt(ev);
    if (!this.first) {
      this.first = point;
      this.created = created ? [point] : [];
      this.renderer.preview = { draw: (ctx, view) =>
        this.drawPreview(ctx, view, this.first, this.cursor || ev.world) };
      this.requestRender();
      return;
    }
    if (point === this.first) return; // same point twice would be degenerate
    this.scene.add(this.build(this.first, point));
    this.first = null;
    this.created = [];
    this.renderer.preview = null;
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.first) this.requestRender();
  }

  cancel() {
    // Esc mid-construction: also remove the first point if THIS tool created it.
    if (this.first && this.created.length) this.scene.remove(this.created);
    this.first = null;
    this.created = [];
    super.cancel();
  }

  onKey(e) { if (e.key === 'Escape') this.cancel(); }
}

// ---------------------------------------------------------------------------
// TEXT (click to place a note, type its content, Enter/blur to commit)
// ---------------------------------------------------------------------------
export class TextTool extends Tool {
  get name() { return 'text'; }
  get hint() { return 'Click anywhere to place a text note, then type it.'; }
  activate() { super.activate(); this.setCursor('text'); }

  onPointerDown(ev) {
    // Clicking an existing text note edits it in place instead of
    // stacking a new one on top.
    const existing = this.hit(ev, 'text');
    if (existing) { this._openEditor(existing, ev.screen); return; }

    const note = this.scene.add(new TextNote(ev.world.x, ev.world.y, '', this._latexMode));
    // Defer to the next tick: the mousedown that triggered this can
    // otherwise steal focus right back from the input we're about to
    // create (its blur handler would fire before the person sees it).
    setTimeout(() => this._openEditor(note, ev.screen), 0);
  }

  // Remembers the last LaTeX-toggle state across notes in this session,
  // so placing several formulas in a row doesn't require re-clicking the
  // toggle each time. Starts off (plain text) so the ordinary case (a
  // one-off label) stays a single click.
  _latexMode = false;

  // Same math-italic Greek block used by the sidebar's Greek keyboard
  // (Mathematical Alphanumeric Symbols, U+1D6FC..), plus a row of common
  // trig/root symbols -- everything a person might want to drop into a
  // text note while annotating a diagram.
  static GREEK_KEYS = [
    '\u{1D6FC}', '\u{1D6FD}', '\u{1D6FE}', '\u{1D6FF}', '\u{1D700}', '\u{1D703}',
    '\u{1D704}', '\u{1D705}', '\u{1D706}', '\u{1D707}', '\u{1D708}', '\u{1D709}',
    '\u{1D70B}', '\u{1D70C}', '\u{1D70E}', '\u{1D70F}', '\u{1D711}', '\u{1D712}',
    '\u{1D713}', '\u{1D714}', '\u{1D6E5}',
  ];
  static MATH_KEYS = [
    'sin', 'cos', 'tan', 'sin\u207b\u00b9', 'cos\u207b\u00b9', 'tan\u207b\u00b9',
    '\u221a', '\u221b', 'log', 'ln',
    '\u00b2', '\u00b3', '^', '\u00b1', '\u00d7', '\u00f7',
    '\u2264', '\u2265', '\u2260', '\u2245', '\u2192', '\u00b0',
  ];

  // Quick-insert LaTeX commands for the palette when the LaTeX toggle is
  // on. `caret` is where the cursor lands after insertion (relative to
  // the start of `token`), so e.g. clicking \frac{}{} drops the cursor
  // inside the first braces, ready to type the numerator.
  static LATEX_KEYS = [
    { label: '\u00bd', token: '\\frac{}{}', caret: 6 },
    { label: '\u221a', token: '\\sqrt{}', caret: 6 },
    { label: 'x\u00b2', token: '^{}', caret: 2 },
    { label: 'x\u2099', token: '_{}', caret: 2 },
    { label: '\u03b1\u03b2\u03b3', token: '\\alpha \\beta \\gamma', caret: 22 },
    { label: '\u03b8', token: '\\theta', caret: 6 },
    { label: '\u2211', token: '\\sum_{}^{}', caret: 6 },
    { label: '\u222b', token: '\\int_{}^{}', caret: 6 },
    { label: '\u00b1', token: '\\pm', caret: 3 },
    { label: '\u2264', token: '\\le', caret: 3 },
    { label: '\u2265', token: '\\ge', caret: 3 },
    { label: '\u2260', token: '\\ne', caret: 3 },
    { label: '\u2192', token: '\\to', caret: 3 },
    { label: 'sin', token: '\\sin', caret: 4 },
    { label: 'cos', token: '\\cos', caret: 4 },
    { label: 'tan', token: '\\tan', caret: 4 },
    { label: '\u00b0', token: '^\\circ', caret: 6 },
    { label: '\u25b3', token: '\\triangle ', caret: 10 },
  ];

  _openEditor(note, screenPos) {
    const existingEditor = document.getElementById('geoTextEditor');
    if (existingEditor) existingEditor.remove();
    const existingPad = document.getElementById('geoTextPad');
    if (existingPad) existingPad.remove();
    const existingBar = document.getElementById('geoTextBar');
    if (existingBar) existingBar.remove();

    const wrap = this.renderer.canvas.parentElement; // #canvasWrap
    let latexMode = note.isLatex;

    // Small toolbar above the input: a "LaTeX" checkbox toggle. Checking it
    // switches the input to a LaTeX-friendly font and swaps the symbol
    // palette below for a row of backslash-commands, since Unicode Greek
    // glyphs (the normal palette) aren't valid inside \frac{}, \sqrt{}, etc.
    const bar = document.createElement('label');
    bar.id = 'geoTextBar';
    bar.style.position = 'absolute';
    bar.style.left = screenPos.x + 'px';
    bar.style.top = (screenPos.y - 34) + 'px';
    bar.style.zIndex = '5';
    bar.style.display = 'inline-flex';
    bar.style.alignItems = 'center';
    bar.style.gap = '4px';
    bar.style.font = '11px -apple-system, sans-serif';
    bar.style.background = '#fdfcf9';
    bar.style.border = '1px solid #cfc9ba';
    bar.style.borderRadius = '3px';
    bar.style.padding = '2px 6px';
    bar.style.cursor = 'pointer';
    bar.style.userSelect = 'none';
    const latexCheck = document.createElement('input');
    latexCheck.type = 'checkbox';
    latexCheck.checked = latexMode;
    latexCheck.style.margin = '0';
    bar.appendChild(latexCheck);
    bar.appendChild(document.createTextNode('LaTeX (e.g. \\frac{a}{b})'));

    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'geoTextEditor';
    input.value = note.label || '';
    input.style.position = 'absolute';
    input.style.left = screenPos.x + 'px';
    input.style.top = (screenPos.y - 12) + 'px';
    input.style.padding = '3px 7px';
    input.style.border = '1px solid #2f5d50';
    input.style.borderRadius = '3px';
    input.style.background = '#fdfcf9';
    input.style.zIndex = '5';
    input.style.minWidth = '160px';

    // Small click-to-insert palette. Two sets share the same slot: plain
    // mode gets Greek letters + trig/root symbols (as before); LaTeX mode
    // gets common backslash-commands, inserted with the cursor placed
    // inside the first {} so typing continues right where it's needed.
    const pad = document.createElement('div');
    pad.id = 'geoTextPad';
    pad.style.position = 'absolute';
    pad.style.zIndex = '5';
    pad.style.display = 'grid';
    pad.style.gap = '2px';
    pad.style.padding = '5px';
    pad.style.background = '#fdfcf9';
    pad.style.border = '1px solid #cfc9ba';
    pad.style.borderRadius = '4px';
    pad.style.boxShadow = '0 2px 8px rgba(0,0,0,0.12)';
    pad.style.maxWidth = '260px';

    const insert = (token, caretOffset) => {
      const start = input.selectionStart ?? input.value.length;
      const end = input.selectionEnd ?? start;
      input.value = input.value.slice(0, start) + token + input.value.slice(end);
      input.focus();
      const caret = start + (caretOffset ?? token.length);
      input.setSelectionRange(caret, caret);
    };
    const addKey = (label, mathFont, onClick) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = label;
      b.title = label;
      b.style.font = mathFont
        ? '1rem "Cambria Math","STIX Two Math","Noto Sans Math","Segoe UI Symbol",serif'
        : '0.7rem ui-monospace, "Cascadia Code", Consolas, monospace';
      b.style.padding = '4px 2px';
      b.style.border = '1px solid #cfc9ba';
      b.style.borderRadius = '3px';
      b.style.background = '#fff';
      b.style.cursor = 'pointer';
      b.addEventListener('mousedown', (e) => e.preventDefault());
      b.addEventListener('click', onClick);
      pad.appendChild(b);
    };

    const rebuildPad = () => {
      pad.innerHTML = '';
      if (latexMode) {
        pad.style.gridTemplateColumns = 'repeat(6, 1fr)';
        TextTool.LATEX_KEYS.forEach(({ label, token, caret }) =>
          addKey(label, false, () => insert(token, caret)));
      } else {
        pad.style.gridTemplateColumns = 'repeat(10, 1fr)';
        TextTool.GREEK_KEYS.forEach((ch) => addKey(ch, true, () => insert(ch)));
        TextTool.MATH_KEYS.forEach((ch) => addKey(ch, false, () => insert(ch)));
      }
    };
    rebuildPad();

    const applyMode = () => {
      input.style.font = latexMode
        ? '14px ui-monospace, "Cascadia Code", Consolas, monospace'
        : '15px "Iowan Old Style", "Palatino Linotype", Georgia, serif';
      input.placeholder = latexMode ? '\\frac{a}{b} + \\sqrt{c}\u2026' : 'Type text\u2026';
    };
    applyMode();
    latexCheck.addEventListener('change', () => {
      latexMode = latexCheck.checked;
      applyMode();
      rebuildPad();
      input.focus();
    });
    // Keep the checkbox interactive without stealing focus from the input
    // (same pattern as the palette buttons below).
    bar.addEventListener('mousedown', (e) => {
      if (e.target !== latexCheck) e.preventDefault();
    });

    let settled = false;
    const commit = () => {
      if (settled) return;
      settled = true;
      const content = input.value.trim();
      input.remove();
      pad.remove();
      bar.remove();
      if (!content) {
        this.scene.remove([note]); // empty note: discard rather than leave a blank bubble
      } else {
        note.label = content;
        note.isLatex = latexMode;
        this._latexMode = latexMode; // remember for the next note this session
        this.scene._emit();
      }
    };
    const cancelEdit = () => {
      if (settled) return;
      settled = true;
      input.remove();
      pad.remove();
      bar.remove();
      if (!note.label) this.scene.remove([note]);
    };
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); commit(); }
      else if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
    });
    // Commit only when focus leaves the input, the palette, AND the LaTeX
    // checkbox -- otherwise clicking any of those (which blurs the input
    // first) would close the editor before its own click handler runs.
    const scheduleBlurCheck = () => {
      setTimeout(() => {
        if (document.activeElement !== input &&
            !pad.contains(document.activeElement) &&
            !bar.contains(document.activeElement)) commit();
      }, 0);
    };
    input.addEventListener('blur', scheduleBlurCheck);

    wrap.appendChild(bar);
    wrap.appendChild(input);
    wrap.appendChild(pad);
    // Position the pad after appending, once its real size is known, so it
    // stays inside the canvas area instead of overflowing off the edge.
    const wrapRect = wrap.getBoundingClientRect();
    const padW = pad.offsetWidth || 260;
    let padLeft = screenPos.x;
    if (padLeft + padW > wrapRect.width) padLeft = Math.max(0, wrapRect.width - padW);
    pad.style.left = padLeft + 'px';
    pad.style.top = (screenPos.y + 14) + 'px';

    input.focus();
    input.select();
  }
}

// ---------------------------------------------------------------------------
// 3. SEGMENT
// ---------------------------------------------------------------------------
export class SegmentTool extends TwoPointTool {
  get name() { return 'segment'; }
  get hint() { return 'Click two points to draw a segment between them.'; }
  build(p1, p2) { return new Segment(p1, p2); }
  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y); ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// 4. LINE (infinite)
// ---------------------------------------------------------------------------
export class LineTool extends TwoPointTool {
  get name() { return 'line'; }
  get hint() { return 'Click two points; the line extends infinitely through both.'; }
  build(p1, p2) { return new Line(p1, p2); }
  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    const dx = c.x - s.x, dy = c.y - s.y;
    if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) return;
    const L = 5000 / Math.hypot(dx, dy); // long enough to leave the canvas
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x - dx * L, s.y - dy * L); ctx.lineTo(s.x + dx * L, s.y + dy * L);
    ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// MIDPOINT
//   Click an existing segment for its midpoint in one click, or click two
//   points (existing or new) to get the midpoint between them. Like the
//   triangle-centre tools, the result is LIVE (a ConstructedPoint): it stays
//   at the midpoint when either source point is moved afterwards.
// ---------------------------------------------------------------------------
export class MidpointTool extends Tool {
  get name() { return 'midpoint'; }
  get hint() { return 'Click a segment for its midpoint, or click two points.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.first = null; this.created = []; }

  onPointerDown(ev) {
    // One-click shortcut: clicking an existing segment gives its midpoint
    // directly, without needing to pick its two endpoints separately.
    if (!this.first) {
      const seg = this.hit(ev, 'segment');
      if (seg) { this.addMidpoint(seg.p1, seg.p2); return; }
    }

    const { point, created } = this.pointAt(ev);
    if (!this.first) {
      this.first = point;
      this.created = created ? [point] : [];
      this.renderer.preview = { draw: (ctx, view) =>
        this.drawPreview(ctx, view, this.first, this.cursor || ev.world) };
      this.requestRender();
      return;
    }
    if (point === this.first) return; // same point twice: ignore
    this.addMidpoint(this.first, point);
    this.first = null;
    this.created = [];
    this.renderer.preview = null;
    this.requestRender();
  }

  addMidpoint(p1, p2) {
    const m = this.scene.add(new ConstructedPoint('midpoint', [p1, p2]));
    m.color = '#2f7d5a'; // distinct colour: flags it as a derived/construction point
    this.scene._emit();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.first) this.requestRender();
  }

  cancel() {
    if (this.first && this.created.length) this.scene.remove(this.created);
    this.first = null;
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y); ctx.stroke();
    // Preview badge at the would-be midpoint, so the person can see where
    // it will land before committing to the second click.
    const mx = (s.x + c.x) / 2, my = (s.y + c.y) / 2;
    ctx.setLineDash([]);
    ctx.beginPath(); ctx.arc(mx, my, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#2f7d5a'; ctx.fill();
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// PERPENDICULAR LINE
//   Click an existing segment or line (the base), then click the point the
//   perpendicular should pass through (existing, or empty space to drop a
//   new one). Builds an infinite Line, exactly like the manual Line tool.
//   The line is LIVE: it stays perpendicular to the base and through the
//   chosen point when either is moved afterwards (its direction comes from
//   a hidden ConstructedPoint of kind 'perp').
// ---------------------------------------------------------------------------
export class PerpendicularLineTool extends Tool {
  get name() { return 'perpendicular'; }
  get hint() { return 'Click a segment or line, then click the point to pass through.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.base = null; }

  onPointerDown(ev) {
    if (!this.base) {
      const base = this.hit(ev, 'segment') || this.hit(ev, 'line');
      if (base) {
        this.base = base;
        this.setHint('Now click the point the perpendicular should pass through.');
      }
      return;
    }

    const { point } = this.pointAt(ev);
    const dx = this.base.p2.x - this.base.p1.x;
    const dy = this.base.p2.y - this.base.p1.y;
    const len = Math.hypot(dx, dy);
    if (len < 1e-9) { this.base = null; this.setHint(this.hint); return; } // degenerate base

    // A hidden, LIVE construction point one unit from `point`, at 90 degrees to
    // the base; the Line through both stays perpendicular as things move.
    const q = this.scene.add(new ConstructedPoint('perp', [point, this.base.p1, this.base.p2], { helper: true }));
    q.labelVisible = false;
    this.scene.add(new Line(point, q));

    this.base = null;
    this.renderer.preview = null;
    this.setHint(this.hint);
    this.requestRender();
  }

  cancel() { this.base = null; super.cancel(); }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }
}

// ---------------------------------------------------------------------------
// PERPENDICULAR BISECTOR
//   Click an existing segment for its perpendicular bisector in one click, or
//   click two points (existing or new). Builds an infinite Line through the
//   midpoint of the two points, at 90 degrees to the line joining them.
//   LIVE: the midpoint is a ConstructedPoint of kind 'midpoint' and the
//   line's direction comes from a hidden ConstructedPoint of kind 'perp'
//   (anchored at that midpoint), so the whole construction follows when
//   either source point is moved afterwards. Nothing new is needed in
//   model.js: it reuses the same kinds as the Midpoint and Perpendicular
//   Line tools, so it also saves / loads / undoes like they do.
// ---------------------------------------------------------------------------
export class PerpendicularBisectorTool extends Tool {
  get name() { return 'perpbisector'; }
  get hint() { return 'Click a segment for its perpendicular bisector, or click two points.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.first = null; this.created = []; }

  onPointerDown(ev) {
    // One-click shortcut: clicking an existing segment uses its two endpoints.
    if (!this.first) {
      const seg = this.hit(ev, 'segment');
      if (seg) { this.addBisector(seg.p1, seg.p2); return; }
    }

    const { point, created } = this.pointAt(ev);
    if (!this.first) {
      this.first = point;
      this.created = created ? [point] : [];
      this.setHint('Now click the second point.');
      this.renderer.preview = { draw: (ctx, view) =>
        this.drawPreview(ctx, view, this.first, this.cursor || ev.world) };
      this.requestRender();
      return;
    }
    if (point === this.first) return; // same point twice: ignore
    this.addBisector(this.first, point);
    this.first = null;
    this.created = [];
    this.setHint(this.hint);
    this.renderer.preview = null;
    this.requestRender();
  }

  addBisector(p1, p2) {
    if (Math.hypot(p2.x - p1.x, p2.y - p1.y) < 1e-9) return; // coincident points: no bisector
    // The midpoint stays visible (green dot, no label) so it can be used for
    // further constructions; it must be added BEFORE the point that refers to it.
    const m = this.scene.add(new ConstructedPoint('midpoint', [p1, p2], { helper: true }));
    // Hidden, LIVE direction point: one unit from the midpoint, perpendicular to p1->p2.
    const q = this.scene.add(new ConstructedPoint('perp', [m, p1, p2], { helper: true }));
    q.visible = false;
    this.scene.add(new Line(m, q));
    this.scene._emit();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.first) this.requestRender();
  }

  cancel() {
    if (this.first && this.created.length) this.scene.remove(this.created);
    this.first = null;
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    const dx = c.x - s.x, dy = c.y - s.y, len = Math.hypot(dx, dy);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y); ctx.stroke();
    if (len > 1) {
      // Preview of the would-be bisector: through the midpoint, at 90 degrees.
      const mx = (s.x + c.x) / 2, my = (s.y + c.y) / 2;
      const px = -dy / len, py = dx / len, L = 4000;
      ctx.beginPath(); ctx.moveTo(mx - px * L, my - py * L); ctx.lineTo(mx + px * L, my + py * L); ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath(); ctx.arc(mx, my, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#2f7d5a'; ctx.fill();
    }
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// 6. CIRCLE with centre through point
// ---------------------------------------------------------------------------
export class CircleTool extends TwoPointTool {
  get name() { return 'circle'; }
  get hint() { return 'Click the centre, then a point on the circle.'; }
  build(center, through) { return new Circle(center, through); }
  drawPreview(ctx, view, center, cursor) {
    const c = view.worldToScreen(center), m = view.worldToScreen(cursor);
    const r = Math.hypot(m.x - c.x, m.y - c.y);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(c.x, c.y, r, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// ELLIPSE
//   Click the two foci, then a point ON the ellipse (existing points, or empty
//   space to drop new ones). The ellipse is the set of points whose distances
//   to the two foci add up to |PF1| + |PF2|. A labelled centre point O is added
//   too, so the result reads as a proper ellipse diagram. Everything is LIVE:
//   drag a focus or the third point and the ellipse reshapes. If the third
//   point lies on the segment between the foci the ellipse would collapse to
//   that segment, so it is refused and the two foci are kept for another try.
// ---------------------------------------------------------------------------
export class EllipseTool extends Tool {
  get name() { return 'ellipse'; }
  get hint() { return 'Click the two foci, then a point on the ellipse.'; }
  activate() {
    super.activate();
    this.setCursor('crosshair');
    this.verts = [];
    this.created = [];
    this._updateHint();
  }

  _updateHint() {
    const labels = ['the first focus', 'the second focus', 'a point ON the ellipse'];
    const n = this.verts.length;
    this.setHint(n < 3 ? `Click ${labels[n]} (${n + 1} of 3).` : this.hint);
  }

  onPointerDown(ev) {
    const { point, created } = this.pointAt(ev);
    if (this.verts.includes(point)) return; // same point twice: ignore
    this.verts.push(point);
    if (created) this.created.push(point);

    if (this.verts.length < 3) {
      this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
      this._updateHint();
      this.requestRender();
      return;
    }

    const [f1, f2, p] = this.verts;
    const ellipse = new Ellipse(f1, f2, p);
    if (!ellipse.isValid()) {
      // Drop only the bad third point; keep the foci so another click can retry.
      this.verts.pop();
      if (created) { this.scene.remove([point]); this.created.pop(); }
      this.setHint('That point is between the two foci, so there is no ellipse. Click a point outside the segment joining the foci, or Esc to cancel.');
      this.requestRender();
      return;
    }
    this.scene.add(ellipse);
    const center = new ConstructedPoint('midpoint', [f1, f2]); // live centre of the ellipse
    center.label = 'O';
    this.scene.add(center);

    this.verts = [];
    this.created = [];
    this.renderer.preview = null;
    this._updateHint();
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = [];
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view) {
    if (!this.verts.length) return;
    const pts = this.verts.map(v => view.worldToScreen(v));
    const cur = this.cursor ? view.worldToScreen(this.cursor) : null;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    if (this.verts.length === 2 && this.cursor) {
      // Live ellipse through the cursor, so the shape is visible before the 3rd click.
      const g = new Ellipse(this.verts[0], this.verts[1], { x: this.cursor.x, y: this.cursor.y })._geom();
      if (g) {
        const c = view.worldToScreen({ x: g.cx, y: g.cy });
        ctx.beginPath();
        ctx.ellipse(c.x, c.y, g.a * view.scale, g.b * view.scale, -g.phi, 0, Math.PI * 2);
        ctx.stroke();
      }
    } else if (cur) {
      ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); ctx.lineTo(cur.x, cur.y); ctx.stroke();
    }
    // Numbered badges so it is clear which click is which focus.
    const badge = ['F1', 'F2'];
    pts.forEach((p, i) => {
      ctx.beginPath(); ctx.arc(p.x, p.y, 10, 0, Math.PI * 2);
      ctx.fillStyle = '#2a6df4'; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 9px -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(badge[i], p.x, p.y + 0.5);
    });
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// SEMICIRCLE
//   Click the two ends of a diameter (existing points, or empty space to
//   drop new ones); the semicircle on that diameter is added. Press 'F'
//   while placing the second point to flip which side the arc bulges
//   toward (handy since it's otherwise easy to get the "wrong" half).
// ---------------------------------------------------------------------------
export class SemicircleTool extends TwoPointTool {
  get name() { return 'semicircle'; }
  get hint() { return "Click the two ends of a diameter. Press 'F' to flip which side the arc is drawn on."; }
  activate() { super.activate(); this._flip = false; }
  build(p1, p2) { return new Semicircle(p1, p2, this._flip); }
  onKey(e) {
    if (e.key === 'f' || e.key === 'F') {
      this._flip = !this._flip;
      this.requestRender();
      return;
    }
    super.onKey(e);
  }
  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    const mx = (s.x + c.x) / 2, my = (s.y + c.y) / 2;
    const r = Math.hypot(c.x - s.x, c.y - s.y) / 2;
    const worldAngle = Math.atan2(cursor.y - a.y, cursor.x - a.x);
    const screenAngle = -worldAngle;
    const start = this._flip ? screenAngle : screenAngle + Math.PI;
    const end = this._flip ? screenAngle + Math.PI : screenAngle + 2 * Math.PI;
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(mx, my, r, start, end); ctx.closePath(); ctx.stroke();
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// 5. POLYGON
//   Click vertices one by one. Finish by clicking the FIRST vertex again,
//   double-clicking, or pressing Enter. Esc cancels.
// ---------------------------------------------------------------------------
export class PolygonTool extends Tool {
  get name() { return 'polygon'; }
  get hint() { return 'Click vertices. Click the first vertex, double-click, or press Enter to close. Esc cancels.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.verts = []; this.created = []; }

  onPointerDown(ev) {
    const { point, created } = this.pointAt(ev);

    // Clicking the first vertex again closes the polygon.
    if (this.verts.length >= 3 && point === this.verts[0]) { this.finish(); return; }
    if (this.verts.includes(point)) return; // ignore repeats

    this.verts.push(point);
    if (created) this.created.push(point);

    this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  onDoubleClick() { this.finish(); }

  onKey(e) {
    if (e.key === 'Enter') this.finish();
    else if (e.key === 'Escape') this.cancel();
  }

  finish() {
    if (this.verts.length < 3) { this.cancel(); return; }
    this.scene.add(new Polygon([...this.verts]));
    this.verts = []; this.created = [];
    this.renderer.preview = null;
    this.requestRender();
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = []; this.created = [];
    super.cancel();
  }

  drawPreview(ctx, view) {
    if (!this.verts.length) return;
    const pts = this.verts.map(v => view.worldToScreen(v));
    const cur = this.cursor ? view.worldToScreen(this.cursor) : null;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    if (cur) ctx.lineTo(cur.x, cur.y);
    ctx.stroke();
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// ISOSCELES TRIANGLE
//   Click the two ends of the base (existing points, or empty space to
//   drop new ones); the apex is placed automatically above the midpoint
//   so the two legs come out equal (leg length = 0.9 x the base, a
//   pleasant-looking starting ratio -- drag the apex afterward with the
//   Move tool to make the legs longer/shorter (it slides along the
//   perpendicular bisector, so the triangle always stays isosceles, and it
//   follows the base when either base point moves).
// ---------------------------------------------------------------------------
export class IsoscelesTriangleTool extends TwoPointTool {
  get name() { return 'isosceles'; }
  get hint() { return 'Click the two ends of the base; the apex is placed automatically to make an isosceles triangle.'; }
  build(p1, p2) {
    // Live apex: sits on the perpendicular bisector of the base, so both legs
    // stay equal when either base point moves. Drag it along that bisector to
    // change the height; otherwise it keeps its height/base ratio.
    const apex = new ConstructedPoint('apex', [p1, p2], { k: APEX_ISO_K, free: true });
    apex.color = '#b3541e';
    apex.label = 'Apex';
    this.scene.add(apex);
    return new Polygon([p1, p2, apex]);
  }
  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y); ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// EQUILATERAL TRIANGLE
//   Click the two ends of a side; the third vertex is placed automatically
//   so all three sides are equal (the classic compass-and-straightedge
//   construction: swing two arcs of the same radius from the side's
//   endpoints, they meet at the apex).
// ---------------------------------------------------------------------------
export class EquilateralTriangleTool extends TwoPointTool {
  get name() { return 'equilateral'; }
  get hint() { return 'Click the two ends of a side; the third vertex is placed automatically to make an equilateral triangle.'; }
  build(p1, p2) {
    // Live apex at height side * sqrt(3)/2: stays equilateral when a base point moves.
    const apex = new ConstructedPoint('apex', [p1, p2], { k: APEX_EQUI_K, free: false });
    apex.color = '#b3541e';
    apex.label = 'Apex';
    this.scene.add(apex);
    return new Polygon([p1, p2, apex]);
  }
  drawPreview(ctx, view, a, cursor) {
    const s = view.worldToScreen(a), c = view.worldToScreen(cursor);
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y); ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// ANGLE
//   Click 3 points in order: the ray-start point, the VERTEX, then the
//   other ray-end point. The angle is always measured AT THE SECOND
//   click (the middle point) -- matches how you'd read "angle ABC" off
//   paper, where B (the middle letter) is the vertex.
// ---------------------------------------------------------------------------
export class AngleTool extends Tool {
  get name() { return 'angle'; }
  get hint() { return 'Click the vertex\'s angle: first point, then the VERTEX, then the last point.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.verts = []; this.created = []; this._updateHint(); }

  _updateHint() {
    const labels = ['first point', 'the VERTEX', 'last point'];
    const n = this.verts.length;
    this.setHint(n < 3 ? `Click ${labels[n]} (${n + 1} of 3).` : this.hint);
  }

  onPointerDown(ev) {
    const { point, created } = this.pointAt(ev);
    if (this.verts.includes(point)) return; // same point twice: ignore
    this.verts.push(point);
    if (created) this.created.push(point);

    if (this.verts.length < 3) {
      this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
      this._updateHint();
      this.requestRender();
      return;
    }

    const [p1, vertex, p3] = this.verts;
    this.scene.add(new Angle(p1, vertex, p3));
    this.verts = [];
    this.created = [];
    this.renderer.preview = null;
    this._updateHint();
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = [];
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view) {
    if (!this.verts.length) return;
    const pts = this.verts.map(v => view.worldToScreen(v));
    const cur = this.cursor ? view.worldToScreen(this.cursor) : null;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    if (cur) ctx.lineTo(cur.x, cur.y);
    ctx.stroke();
    // Badge the SECOND click distinctly (it's the vertex the angle will
    // be measured at), same visual language as the triangle-centre tools.
    const badgeLabels = ['1', 'VERTEX', '3'];
    pts.forEach((p, i) => {
      ctx.beginPath(); ctx.arc(p.x, p.y, i === 1 ? 11 : 9, 0, Math.PI * 2);
      ctx.fillStyle = i === 1 ? '#b3541e' : '#2a6df4'; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 9px -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(badgeLabels[i], p.x, p.y + 0.5);
    });
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// ANGLE BISECTOR
//   Same 3-click pattern as the Angle tool: first point, then the VERTEX,
//   then the last point. Instead of measuring the angle, this constructs
//   the internal bisector as an infinite Line through the vertex -- built
//   as "vertex" + a second construction point along the bisector direction
//   (unlabelled, like the Perpendicular Line tool), so it's a real Line
//   object: it pans/zooms/clips like any other line, and saves/loads with
//   the scene. LIVE: it re-aims when the 3 original points move afterward
//   (its second point is a hidden ConstructedPoint of kind 'bisector').
// ---------------------------------------------------------------------------
export class AngleBisectorTool extends Tool {
  get name() { return 'anglebisector'; }
  get hint() { return "Click the angle's rays: first point, then the VERTEX, then the last point."; }
  activate() { super.activate(); this.setCursor('crosshair'); this.verts = []; this.created = []; this._updateHint(); }

  _updateHint() {
    const labels = ['first point', 'the VERTEX', 'last point'];
    const n = this.verts.length;
    this.setHint(n < 3 ? `Click ${labels[n]} (${n + 1} of 3).` : this.hint);
  }

  onPointerDown(ev) {
    const { point, created } = this.pointAt(ev);
    if (this.verts.includes(point)) return; // same point twice: ignore
    this.verts.push(point);
    if (created) this.created.push(point);

    if (this.verts.length < 3) {
      this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
      this._updateHint();
      this.requestRender();
      return;
    }

    const [p1, vertex, p3] = this.verts;
    const angle = new Angle(p1, vertex, p3);
    const dir = angle.bisectorDirection();
    if (!dir) {
      this.setHint('Those points are degenerate (two coincide) -- no bisector exists. Pick again, or Esc to cancel.');
    } else {
      // Hidden, LIVE construction point along the bisector (re-aims when the 3 points move).
      const q = this.scene.add(new ConstructedPoint('bisector', [p1, vertex, p3], { helper: true }));
      this.scene.add(new Line(vertex, q));
    }
    this.verts = [];
    this.created = [];
    this.renderer.preview = null;
    this._updateHint();
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = [];
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view) {
    if (!this.verts.length) return;
    const pts = this.verts.map(v => view.worldToScreen(v));
    const cur = this.cursor ? view.worldToScreen(this.cursor) : null;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    if (cur) ctx.lineTo(cur.x, cur.y);
    ctx.stroke();
    // Badge the SECOND click distinctly (it's the vertex), same visual
    // language as the Angle tool.
    const badgeLabels = ['1', 'VERTEX', '3'];
    pts.forEach((p, i) => {
      ctx.beginPath(); ctx.arc(p.x, p.y, i === 1 ? 11 : 9, 0, Math.PI * 2);
      ctx.fillStyle = i === 1 ? '#b3541e' : '#2a6df4'; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 9px -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(badgeLabels[i], p.x, p.y + 0.5);
    });
    // Once the vertex is placed (2nd click), preview the bisector ray
    // itself toward the current cursor position, using p1 as the known
    // ray so the preview updates live as the 3rd point is chosen.
    if (this.verts.length === 2 && this.cursor) {
      const [p1, vertex] = this.verts;
      const angle = new Angle(p1, vertex, { x: this.cursor.x, y: this.cursor.y });
      const dir = angle.bisectorDirection();
      if (dir) {
        const v = view.worldToScreen(vertex);
        const far = view.worldToScreen({ x: vertex.x + dir.x * 1000, y: vertex.y + dir.y * 1000 });
        ctx.setLineDash([3, 4]); ctx.strokeStyle = '#2f7d5a';
        ctx.beginPath(); ctx.moveTo(v.x, v.y); ctx.lineTo(far.x, far.y); ctx.stroke();
      }
    }
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// 11-14. TRIANGLE-CENTRE CIRCLES (Circumcircle, Incircle, Nine-point
// circle, Excircles). Click 3 existing points (or empty space to drop new
// ones) for vertices A, B, C; the matching circle(s) are added to the
// scene automatically. See model.js for the underlying formulas.
//
// State machine: each tool just accumulates up to 3 Points in this.verts,
// giving a running "Select vertex N of 3" hint (visual feedback comes for
// free from the existing point-selection highlight plus a rubber-band
// triangle preview with numbered A/B/C badges). Once the 3rd point lands,
// build() computes the circle(s) and the tool resets to pick another
// triangle, so several triangles' circles can be built one after another
// without reselecting the tool.
// ---------------------------------------------------------------------------
class TriangleCircleTool extends Tool {
  get vertexLabels() { return ['A', 'B', 'C']; }
  activate() {
    super.activate();
    this.setCursor('crosshair');
    this.verts = [];
    this.created = [];
    this._updateHint();
  }
  _updateHint() {
    const n = this.verts.length;
    this.setHint(n < 3
      ? this.hint + ' Select vertex ' + this.vertexLabels[n] + ' (' + (n + 1) + ' of 3).'
      : this.hint);
  }

  onPointerDown(ev) {
    const picked = this.pointAt(ev);
    const point = picked.point, created = picked.created;
    if (this.verts.includes(point)) return; // same point twice: ignore
    this.verts.push(point);
    if (created) this.created.push(point);

    if (this.verts.length < 3) {
      this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
      this._updateHint();
      this.requestRender();
      return;
    }

    const A = this.verts[0], B = this.verts[1], C = this.verts[2];
    const ok = this.build(A, B, C);
    if (!ok) {
      // Collinear / degenerate: keep the 3 points (still useful on their
      // own), just skip adding a circle, and say why.
      this.setHint(this.failMessage ||
        'Those 3 points are collinear -- no circle exists. Pick 3 points again, or Esc to cancel.');
      this.failMessage = null;
    }
    this.verts = [];
    this.created = [];
    this.renderer.preview = null;
    if (ok) this._updateHint();
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  /** Compute and add the circle(s) for vertices A, B, C. Return false if
   *  the triangle is degenerate (nothing was added). */
  build(_A, _B, _C) { throw new Error('not implemented'); }

  /**
   * Add one LIVE DerivedCircle, referencing the 3 source vertices (A, B, C)
   * and a named formula (see model.js's DERIVED_CIRCLE_FORMULAS registry)
   * instead of a frozen {x, y, r} snapshot. This is what makes the circle
   * follow the triangle when any of A/B/C is dragged afterward, exactly
   * like a Segment following its endpoints. `formulaName` must be a key in
   * DERIVED_CIRCLE_FORMULAS; `index` selects one circle out of a formula
   * that returns an array (excircles/apollonius/johnson each return 3).
   * `checkSpec` is the already-computed {x,y,r} (or array) used only to
   * decide right now whether this vertex arrangement is degenerate --
   * the DerivedCircle itself recomputes independently every frame.
   */
  addDerivedCircle(A, B, C, formulaName, label, index, checkSpec) {
    if (!checkSpec) return false;
    const circle = new DerivedCircle(A, B, C, formulaName, index);
    // A name is mandatory -- fall back to the formula key itself if the
    // caller somehow didn't provide one, so no circle is ever unlabelled.
    circle.label = label || formulaName;
    this.scene.add(circle);

    // Also add a small LIVE labelled dot at the circle's centre (e.g. "I"
    // for the incentre), so every circle's centre is visibly marked, not
    // just its boundary. Uses the same formulaName/index, so it tracks
    // the circle automatically when A/B/C move.
    const centerLabels = DERIVED_CIRCLE_CENTER_LABELS[formulaName];
    const centerLabel = index !== undefined
      ? (Array.isArray(centerLabels) ? centerLabels[index] : undefined)
      : centerLabels;
    if (centerLabel) {
      const centerPoint = new DerivedPoint(A, B, C, formulaName, index);
      centerPoint.label = centerLabel;
      centerPoint.color = circle.color;
      this.scene.add(centerPoint);
    }
    return true;
  }

  /**
   * Legacy path: add one FROZEN Circle object from a {x, y, r} spec (two
   * real Points, exactly like the manual Circle tool). Kept only for tools
   * that don't yet have a DERIVED_CIRCLE_FORMULAS entry; prefer
   * addDerivedCircle above so the result stays live when the triangle moves.
   */
  addCircleFrom(centerSpec, label) {
    if (!centerSpec) return false;
    const centerPoint = this.scene.add(new Point(centerSpec.x, centerSpec.y));
    const throughPoint = this.scene.add(new Point(centerSpec.x + centerSpec.r, centerSpec.y));
    throughPoint.labelVisible = false; // a construction point, not a vertex worth labelling
    const circle = new Circle(centerPoint, throughPoint);
    if (label) circle.label = label;
    this.scene.add(circle);
    return true;
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = [];
    this.created = [];
    super.cancel();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view) {
    if (!this.verts.length) return;
    const pts = this.verts.map(v => view.worldToScreen(v));
    const cur = this.cursor ? view.worldToScreen(this.cursor) : null;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    if (cur) ctx.lineTo(cur.x, cur.y);
    ctx.stroke();
    // Small numbered badges at each picked vertex, so "which one is A/B/C"
    // is visible even before any label is assigned.
    pts.forEach((p, i) => {
      ctx.beginPath(); ctx.arc(p.x, p.y, 9, 0, Math.PI * 2);
      ctx.fillStyle = '#2a6df4'; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 10px -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(this.vertexLabels[i], p.x, p.y + 0.5);
    });
    ctx.restore();
  }
}

export class CircumcircleTool extends TriangleCircleTool {
  get name() { return 'circumcircle'; }
  get hint() { return 'Click 3 points to build a triangle; its circumcircle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'circumcircle', 'circumcircle', undefined, circumcircleOf(A, B, C)); }
}

export class IncircleTool extends TriangleCircleTool {
  get name() { return 'incircle'; }
  get hint() { return 'Click 3 points to build a triangle; its incircle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'incircle', 'incircle', undefined, incircleOf(A, B, C)); }
}

export class NinePointCircleTool extends TriangleCircleTool {
  get name() { return 'ninepoint'; }
  get hint() { return 'Click 3 points to build a triangle; its nine-point circle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'ninepoint', 'nine-point circle', undefined, ninePointCircleOf(A, B, C)); }
}

export class ExcirclesTool extends TriangleCircleTool {
  get name() { return 'excircles'; }
  get hint() { return 'Click 3 points to build a triangle; all 3 excircles are added automatically.'; }
  build(A, B, C) {
    const ex = excirclesOf(A, B, C);
    // Add whichever excentres are defined; a fully degenerate triangle
    // returns [null, null, null], so all three calls return false and the
    // caller correctly reports "no circle added".
    const okA = this.addDerivedCircle(A, B, C, 'excircles', 'excircle A', 0, ex[0]);
    const okB = this.addDerivedCircle(A, B, C, 'excircles', 'excircle B', 1, ex[1]);
    const okC = this.addDerivedCircle(A, B, C, 'excircles', 'excircle C', 2, ex[2]);
    return okA || okB || okC;
  }
}

export class SpiekerCircleTool extends TriangleCircleTool {
  get name() { return 'spieker'; }
  get hint() { return "Click 3 points to build a triangle; its Spieker circle (the medial triangle's incircle) is added automatically."; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'spieker', 'Spieker circle', undefined, spiekerCircleOf(A, B, C)); }
}

export class BrocardCircleTool extends TriangleCircleTool {
  get name() { return 'brocard'; }
  get hint() { return 'Click 3 points to build a triangle; its Brocard circle (diameter from circumcentre to symmedian point) is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'brocard', 'Brocard circle', undefined, brocardCircleOf(A, B, C)); }
}

export class MandartCircleTool extends TriangleCircleTool {
  get name() { return 'mandart'; }
  get hint() { return 'Click 3 points to build a triangle; its Mandart circle (circumcircle of the extouch triangle) is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'mandart', 'Mandart circle', undefined, mandartCircleOf(A, B, C)); }
}

export class ApolloniusCirclesTool extends TriangleCircleTool {
  get name() { return 'apollonius'; }
  get hint() { return 'Click 3 points to build a triangle; all 3 Apollonius circles (one per vertex ratio) are added automatically.'; }
  build(A, B, C) {
    const ap = apolloniusCirclesOf(A, B, C);
    const okA = this.addDerivedCircle(A, B, C, 'apollonius', 'Apollonius circle A', 0, ap[0]);
    const okB = this.addDerivedCircle(A, B, C, 'apollonius', 'Apollonius circle B', 1, ap[1]);
    const okC = this.addDerivedCircle(A, B, C, 'apollonius', 'Apollonius circle C', 2, ap[2]);
    return okA || okB || okC;
  }
}

export class ConwayCircleTool extends TriangleCircleTool {
  get name() { return 'conway'; }
  get hint() { return 'Click 3 points to build a triangle; its Conway circle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'conway', 'Conway circle', undefined, conwayCircleOf(A, B, C)); }
}

export class OrthocentroidalCircleTool extends TriangleCircleTool {
  get name() { return 'orthocentroidal'; }
  get hint() { return 'Click 3 points to build a triangle; its orthocentroidal circle (diameter from centroid to orthocenter) is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'orthocentroidal', 'orthocentroidal circle', undefined, orthocentroidalCircleOf(A, B, C)); }
}

export class TangentialTriangleCircleTool extends TriangleCircleTool {
  get name() { return 'tangentialtriangle'; }
  get hint() { return 'Click 3 points to build a triangle; the circumcircle of its tangential triangle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'tangentialtriangle', 'tangential triangle circle', undefined, tangentialTriangleCircleOf(A, B, C)); }
}

export class BevanCircleTool extends TriangleCircleTool {
  get name() { return 'bevan'; }
  get hint() { return 'Click 3 points to build a triangle; its Bevan circle (circumcircle of the excentral triangle) is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'bevan', 'Bevan circle', undefined, bevanCircleOf(A, B, C)); }
}

export class IncentralTriangleCircleTool extends TriangleCircleTool {
  get name() { return 'incentraltriangle'; }
  get hint() { return 'Click 3 points to build a triangle; the circumcircle of its incentral triangle (angle-bisector feet) is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'incentraltriangle', 'incentral triangle circle', undefined, incentralTriangleCircleOf(A, B, C)); }
}

export class JohnsonCirclesTool extends TriangleCircleTool {
  get name() { return 'johnson'; }
  get hint() { return 'Click 3 points to build a triangle; all 3 Johnson circles (circumcircle reflected over each side) are added automatically.'; }
  build(A, B, C) {
    const jc = johnsonCirclesOf(A, B, C);
    if (!jc) return false;
    const okA = this.addDerivedCircle(A, B, C, 'johnson', 'Johnson circle A', 0, jc[0]);
    const okB = this.addDerivedCircle(A, B, C, 'johnson', 'Johnson circle B', 1, jc[1]);
    const okC = this.addDerivedCircle(A, B, C, 'johnson', 'Johnson circle C', 2, jc[2]);
    return okA || okB || okC;
  }
}

export class FirstLemoineCircleTool extends TriangleCircleTool {
  get name() { return 'lemoine'; }
  get hint() { return 'Click 3 points to build a triangle; its first Lemoine circle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'lemoine', 'first Lemoine circle', undefined, firstLemoineCircleOf(A, B, C)); }
}

export class TaylorCircleTool extends TriangleCircleTool {
  get name() { return 'taylor'; }
  get hint() { return 'Click 3 points to build a triangle; its Taylor circle is added automatically.'; }
  build(A, B, C) { return this.addDerivedCircle(A, B, C, 'taylor', 'Taylor circle', undefined, taylorCircleOf(A, B, C)); }
}

// ---------------------------------------------------------------------------
// 15-21. TRIANGLE-CENTRE POINTS (Incenter, Centroid, Circumcenter,
// Orthocenter, Nine-point center, Symmedian point, Spieker center). Same
// 3-click state machine as the circle tools above, but adds a single
// labelled Point instead of a Circle -- see model.js for the formulas.
// ---------------------------------------------------------------------------
class TriangleCenterTool extends TriangleCircleTool {
  /**
   * Add one LIVE DerivedPoint, referencing the 3 source vertices and a
   * named formula (see model.js's DERIVED_POINT_FORMULAS registry) instead
   * of a frozen {x, y} snapshot -- so it follows the triangle when any of
   * A/B/C is dragged afterward, exactly like DerivedCircle above.
   */
  addDerivedCenterPoint(A, B, C, formulaName, label, checkSpec) {
    if (!checkSpec) return false;
    const p = new DerivedPoint(A, B, C, formulaName);
    p.label = label;
    this.scene.add(p);
    return true;
  }
  /** Legacy path: add one FROZEN Point at a {x, y} spec. Kept only as a
   *  fallback; prefer addDerivedCenterPoint so it stays live. */
  addCenterPoint(spec, label) {
    if (!spec) return false;
    const p = this.scene.add(new Point(spec.x, spec.y));
    p.label = label;
    p.color = '#8a4b8f';
    return true;
  }
  // Reuse the same 3-point picking machinery, but build() below adds a
  // live DerivedPoint instead of a circle -- subclasses only implement
  // centerOf() (used here purely to detect a degenerate triangle) and
  // formulaName (the DERIVED_POINT_FORMULAS registry key).
  build(A, B, C) {
    return this.addDerivedCenterPoint(A, B, C, this.formulaName, this.centerLabel, this.centerOf(A, B, C));
  }
  centerOf(_A, _B, _C) { throw new Error('not implemented'); }
  get formulaName() { throw new Error('not implemented'); }
}

export class IncenterTool extends TriangleCenterTool {
  get name() { return 'incenter'; }
  get hint() { return 'Click 3 points to build a triangle; its incenter X(1) is added automatically.'; }
  get centerLabel() { return 'X(1)'; }
  get formulaName() { return 'incenter'; }
  centerOf(A, B, C) { return incenterOf(A, B, C); }
}

export class CentroidTool extends TriangleCenterTool {
  get name() { return 'centroid'; }
  get hint() { return 'Click 3 points to build a triangle; its centroid X(2) is added automatically.'; }
  get centerLabel() { return 'X(2)'; }
  get formulaName() { return 'centroid'; }
  centerOf(A, B, C) { return centroidOf(A, B, C); }
}

export class CircumcenterTool extends TriangleCenterTool {
  get name() { return 'circumcenter'; }
  get hint() { return 'Click 3 points to build a triangle; its circumcenter X(3) is added automatically.'; }
  get centerLabel() { return 'X(3)'; }
  get formulaName() { return 'circumcenter'; }
  centerOf(A, B, C) { return circumcenterOf(A, B, C); }
}

export class OrthocenterTool extends TriangleCenterTool {
  get name() { return 'orthocenter'; }
  get hint() { return 'Click 3 points to build a triangle; its orthocenter X(4) is added automatically.'; }
  get centerLabel() { return 'X(4)'; }
  get formulaName() { return 'orthocenter'; }
  centerOf(A, B, C) { return orthocenterOf(A, B, C); }
}

export class NinePointCenterTool extends TriangleCenterTool {
  get name() { return 'ninepointcenter'; }
  get hint() { return 'Click 3 points to build a triangle; its nine-point center X(5) is added automatically.'; }
  get centerLabel() { return 'X(5)'; }
  get formulaName() { return 'ninepointcenter'; }
  centerOf(A, B, C) { return ninePointCenterOf(A, B, C); }
}

export class SymmedianPointTool extends TriangleCenterTool {
  get name() { return 'symmedian'; }
  get hint() { return 'Click 3 points to build a triangle; its symmedian point X(6) is added automatically.'; }
  get centerLabel() { return 'X(6)'; }
  get formulaName() { return 'symmedian'; }
  centerOf(A, B, C) { return symmedianPointOf(A, B, C); }
}

export class SpiekerCenterTool extends TriangleCenterTool {
  get name() { return 'spiekercenter'; }
  get hint() { return 'Click 3 points to build a triangle; its Spieker center X(10) is added automatically.'; }
  get centerLabel() { return 'X(10)'; }
  get formulaName() { return 'spiekercenter'; }
  centerOf(A, B, C) { return spiekerCenterOf(A, B, C); }
}

// ---------------------------------------------------------------------------
// ANY verified center X(n). The number is typed in the sidebar (main.js arms
// it, the same way Rename/Color are armed); this tool then uses the usual
// 3-click triangle picking and adds a LIVE DerivedPoint whose position is
// computed from X(n)'s barycentric formula (model.js: etcCenterOf), so it
// follows the triangle when a vertex is dragged.
// ---------------------------------------------------------------------------
export class EtcCenterTool extends TriangleCenterTool {
  get name() { return 'etc'; }
  get hint() {
    return this.number
      ? 'Click 3 points to build a triangle; X(' + this.number + ') is added automatically.'
      : 'Type a center number in the sidebar first, then click 3 points.';
  }
  get centerLabel() { return 'X(' + this.number + ')'; }
  get formulaName() { return 'etc'; }
  centerOf(A, B, C) { return etcCenterOf(A, B, C, this.number); }

  onPointerDown(ev) {
    if (!ETC_FORMULAS.has(this.number)) {
      this.setHint('Type a verified center number in the sidebar first (e.g. 13), then click 3 points.');
      return;
    }
    super.onPointerDown(ev);
  }

  build(A, B, C) {
    if (!etcCenterOf(A, B, C, this.number)) {
      this.failMessage = 'X(' + this.number + ') cannot be placed for these points (collinear, or the center is at infinity). Pick 3 points again, or Esc to cancel.';
      return false;
    }
    const p = new DerivedPoint(A, B, C, 'etc', this.number);
    p.label = 'X(' + this.number + ')';
    this.scene.add(p);
    return true;
  }
}

// ---------------------------------------------------------------------------
// 7. SELECT OBJECTS
//   Click = select one. Shift/Ctrl+click = add/remove from selection.
//   Drag on empty space = rubber-band (box) select.
// ---------------------------------------------------------------------------
export class SelectTool extends Tool {
  get name() { return 'select'; }
  get hint() { return 'Click to select. Shift/Ctrl+click to add more. Drag a box to select several.'; }
  activate() { super.activate(); this.box = null; }

  onPointerDown(ev) {
    const target = this.hit(ev);
    const additive = ev.shift || ev.ctrl;

    if (target) {
      if (additive) target.selected = !target.selected;
      else if (!target.selected) { this.scene.clearSelection(); target.selected = true; }
      this.scene._emit();
      return;
    }
    if (!additive) this.scene.clearSelection();
    this.box = { start: ev.screen, end: ev.screen, additive };
    this.renderer.preview = { draw: (ctx) => this.drawBox(ctx) };
    this.scene._emit();
  }

  onPointerMove(ev) {
    if (!this.box) return;
    this.box.end = ev.screen;
    this.requestRender();
  }

  onPointerUp() {
    if (!this.box) return;
    const { start, end } = this.box;
    const w0 = this.view.screenToWorld(start), w1 = this.view.screenToWorld(end);
    const minX = Math.min(w0.x, w1.x), maxX = Math.max(w0.x, w1.x);
    const minY = Math.min(w0.y, w1.y), maxY = Math.max(w0.y, w1.y);
    const inside = (p) => p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY;

    // Only meaningful if the user actually dragged (not a stray click).
    if (Math.abs(end.x - start.x) > 3 || Math.abs(end.y - start.y) > 3) {
      for (const o of this.scene.objects) {
        if (!o.visible) continue;
        let hit = false;
        if (o.type === 'point' || o.type === 'text') hit = inside(o);
        else if (o.type === 'segment') hit = inside(o.p1) && inside(o.p2);
        else if (o.type === 'polygon') hit = o.vertices.every(inside);
        else if (o.type === 'circle') hit = inside(o.center) && inside(o.through);
        else if (o.type === 'ellipse') hit = inside(o.f1) && inside(o.f2) && inside(o.through);
        // Infinite lines have no bounding box, so only click-selection applies to them.
        if (hit) o.selected = true;
      }
    }
    this.box = null;
    this.renderer.preview = null;
    this.scene._emit();
  }

  onKey(e) {
    if (e.key === 'Escape') { this.scene.clearSelection(); this.scene._emit(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      this.scene.objects.forEach(o => { if (o.visible) o.selected = true; });
      this.scene._emit();
    }
  }

  drawBox(ctx) {
    if (!this.box) return;
    const { start, end } = this.box;
    ctx.save();
    ctx.fillStyle = 'rgba(42,109,244,0.10)';
    ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
    ctx.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
    ctx.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// 8 / 9 / 10.  ACTION TOOLS: Show/Hide Label, Show/Hide Object, Delete
//
// These act on the current selection instantly. If nothing is selected they
// fall back to "click an object to apply it", which is how GeoGebra behaves.
// ---------------------------------------------------------------------------
class ActionTool extends Tool {
  activate() {
    super.activate();
    this.setCursor('pointer');
    // If the user already has a selection, apply immediately and stay in
    // the tool so they can keep clicking further objects.
    const sel = this.scene.selected();
    if (sel.length) { this.apply(sel); }
  }
  apply(_objs) {}
  onPointerDown(ev) {
    const target = this.hit(ev);
    if (target) this.apply([target]);
  }
}

export class ToggleLabelTool extends ActionTool {
  get name() { return 'label'; }
  get hint() { return 'Click an object (or select several first) to show/hide its label.'; }
  apply(objs) {
    // If any is visible, hide all; otherwise show all -- predictable for mixed selections.
    const anyShown = objs.some(o => o.labelVisible);
    objs.forEach(o => { o.labelVisible = !anyShown; });
    this.scene._emit();
  }
}

export class ToggleVisibilityTool extends ActionTool {
  get name() { return 'visibility'; }
  get hint() { return 'Click an object (or select several first) to hide it. Use "Show all" to restore.'; }
  apply(objs) {
    objs.forEach(o => { o.visible = !o.visible; o.selected = false; });
    this.scene._emit();
  }
}

export class DeleteTool extends ActionTool {
  get name() { return 'delete'; }
  get hint() { return 'Click an object to delete it (deleting a point also removes shapes built on it).'; }
  apply(objs) { this.scene.remove(objs); }
}

// ---------------------------------------------------------------------------
// COLOR (click a swatch, then click a component -- no selection needed first)
//   Holds the currently-armed color; every click on a component applies it
//   immediately. Picking a new swatch while the tool is active just swaps
//   the armed color, so several objects can be colored one after another
//   without reactivating the tool.
// ---------------------------------------------------------------------------
export class ColorTool extends ActionTool {
  get name() { return 'color'; }
  get hint() { return 'Click a swatch, then click a component to color it.'; }
  activate() {
    // Skip ActionTool's "apply to current selection immediately" behaviour --
    // this tool colors whatever is clicked next, selection or not.
    Tool.prototype.activate.call(this);
    this.setCursor('pointer');
  }
  apply(objs) {
    if (!this.color) { this.setHint('Pick a color swatch first.'); return; }
    objs.forEach((o) => { o.color = this.color; });
    this.scene._emit();
  }
}

// ---------------------------------------------------------------------------
// RENAME (type a name, then click a component -- no selection needed first)
//   Holds the currently-armed name; clicking a component applies it and
//   makes the label visible immediately.
// ---------------------------------------------------------------------------
export class RenameTool extends ActionTool {
  get name() { return 'rename'; }
  get hint() { return 'Type a name, then click a component to rename it.'; }
  activate() {
    Tool.prototype.activate.call(this);
    this.setCursor('pointer');
  }
  apply(objs) {
    if (!this.text) { this.setHint('Type a name first.'); return; }
    objs.forEach((o) => { o.label = this.text; o.labelVisible = true; });
    this.scene._emit();
  }
}

// ---------------------------------------------------------------------------
// SQUARE
//   Click the two ends of one side; the other two corners are built
//   automatically, so all four sides are equal and every angle is 90 degrees.
//   The corners are LIVE (ConstructedPoints), so the square stays a square
//   when either base point is dragged. Press 'F' (the Flip button on a touch
//   screen) before the second click to put it on the other side of the line.
// ---------------------------------------------------------------------------
export class SquareTool extends TwoPointTool {
  get name() { return 'square'; }
  get hint() { return "Click the two ends of one side; the other two corners are placed automatically. Press 'F' to flip the side."; }
  activate() { super.activate(); this._flip = false; }

  build(p1, p2) {
    const k = this._flip ? -1 : 1;
    // Corner next to p2: p2 moved one side-length away at 90 degrees.
    const c = this.scene.add(new ConstructedPoint('offset', [p2, p1, p2], { k }));
    // Corner next to p1: p1 + (c - p2), which completes the parallelogram (here a square).
    const d = this.scene.add(new ConstructedPoint('parallelogram', [p1, p2, c]));
    return new Polygon([p1, p2, c, d]);
  }

  onKey(e) {
    if (e.key === 'f' || e.key === 'F') {
      this._flip = !this._flip;
      this.requestRender();
      return;
    }
    super.onKey(e);
  }

  drawPreview(ctx, view, a, cursor) {
    const k = this._flip ? -1 : 1;
    const dx = cursor.x - a.x, dy = cursor.y - a.y;
    const corners = [
      { x: a.x, y: a.y },
      { x: cursor.x, y: cursor.y },
      { x: cursor.x - dy * k, y: cursor.y + dx * k },
      { x: a.x - dy * k, y: a.y + dx * k },
    ].map(p => view.worldToScreen(p));
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    corners.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    ctx.closePath(); ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// RECTANGLE
//   Click the two ends of one side, then click anywhere on the side the
//   rectangle should grow towards: the distance of that click from the first
//   side becomes the width (the third click does not create a point). The two
//   far corners are LIVE, so the shape always stays a rectangle; drag the
//   corner next to the second point with the Move tool to change the width.
// ---------------------------------------------------------------------------
export class RectangleTool extends Tool {
  get name() { return 'rectangle'; }
  get hint() { return 'Click the two ends of one side, then click to set the width.'; }
  activate() {
    super.activate();
    this.setCursor('crosshair');
    this.verts = [];
    this.created = [];
    this.cursor = null;
    this._updateHint();
  }

  _updateHint() {
    const labels = ['the first corner', 'the second corner (end of the first side)', 'anywhere to set the width'];
    const n = this.verts.length;
    this.setHint(`Click ${labels[n]} (${n + 1} of 3).`);
  }

  /** Width as a multiple of |PQ|, signed: positive = left of P->Q. */
  _kFor(p, q, w) {
    const dx = q.x - p.x, dy = q.y - p.y, len2 = dx * dx + dy * dy;
    return len2 < 1e-18 ? 0 : ((w.x - q.x) * -dy + (w.y - q.y) * dx) / len2;
  }

  onPointerDown(ev) {
    this.cursor = ev.world;
    if (this.verts.length < 2) {
      const { point, created } = this.pointAt(ev);
      if (this.verts.includes(point)) return; // same point twice: ignore
      this.verts.push(point);
      if (created) this.created.push(point);
      this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
      this._updateHint();
      this.requestRender();
      return;
    }

    const [p, q] = this.verts;
    const k = this._kFor(p, q, ev.world);
    if (Math.abs(k) < 1e-6) {
      this.setHint('Click away from the first side to give the rectangle some width.');
      return;
    }
    // Same construction as the square, but with a free width k.
    const c = this.scene.add(new ConstructedPoint('offset', [q, p, q], { k, free: true }));
    const d = this.scene.add(new ConstructedPoint('parallelogram', [p, q, c]));
    this.scene.add(new Polygon([p, q, c, d]));

    this.verts = [];
    this.created = [];
    this.renderer.preview = null;
    this._updateHint();
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.verts.length) this.requestRender();
  }

  cancel() {
    if (this.created.length) this.scene.remove(this.created);
    this.verts = [];
    this.created = [];
    super.cancel();
    this._updateHint();
  }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  drawPreview(ctx, view) {
    if (!this.verts.length || !this.cursor) return;
    const [p, q] = this.verts;
    ctx.save();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    if (this.verts.length === 1) {
      const s = view.worldToScreen(p), c = view.worldToScreen(this.cursor);
      ctx.moveTo(s.x, s.y); ctx.lineTo(c.x, c.y);
    } else {
      const k = this._kFor(p, q, this.cursor);
      const dx = q.x - p.x, dy = q.y - p.y;
      const corners = [
        { x: p.x, y: p.y },
        { x: q.x, y: q.y },
        { x: q.x - dy * k, y: q.y + dx * k },
        { x: p.x - dy * k, y: p.y + dx * k },
      ].map(pt => view.worldToScreen(pt));
      corners.forEach((pt, i) => (i ? ctx.lineTo(pt.x, pt.y) : ctx.moveTo(pt.x, pt.y)));
      ctx.closePath();
    }
    ctx.stroke();
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// PARALLEL LINE
//   Click an existing segment or line (the base), then click the point the
//   parallel should pass through (existing, or empty space to drop a new one).
//   Builds an infinite Line. LIVE: its direction comes from a hidden
//   ConstructedPoint of kind 'parallel', so it stays parallel to the base and
//   through the chosen point when either is moved afterwards.
// ---------------------------------------------------------------------------
export class ParallelLineTool extends Tool {
  get name() { return 'parallel'; }
  get hint() { return 'Click a segment or line, then click the point to pass through.'; }
  activate() { super.activate(); this.setCursor('crosshair'); this.base = null; this.cursor = null; }

  onPointerDown(ev) {
    if (!this.base) {
      const base = this.hit(ev, 'segment') || this.hit(ev, 'line');
      if (base) {
        this.base = base;
        this.setHint('Now click the point the parallel line should pass through.');
        this.renderer.preview = { draw: (ctx, view) => this.drawPreview(ctx, view) };
        this.requestRender();
      }
      return;
    }

    const dx = this.base.p2.x - this.base.p1.x;
    const dy = this.base.p2.y - this.base.p1.y;
    if (Math.hypot(dx, dy) < 1e-9) { this.cancel(); this.setHint(this.hint); return; } // degenerate base

    const { point } = this.pointAt(ev);
    // A hidden, LIVE construction point one unit from `point`, along the base's
    // direction; the Line through both stays parallel as things move.
    const q = this.scene.add(new ConstructedPoint('parallel', [point, this.base.p1, this.base.p2], { helper: true }));
    q.labelVisible = false;
    this.scene.add(new Line(point, q));

    this.base = null;
    this.renderer.preview = null;
    this.setHint(this.hint);
    this.requestRender();
  }

  onPointerMove(ev) {
    this.cursor = ev.world;
    if (this.base) this.requestRender();
  }

  cancel() { this.base = null; super.cancel(); }
  onKey(e) { if (e.key === 'Escape') this.cancel(); }

  /** Dashed preview of the parallel through the cursor. */
  drawPreview(ctx, view) {
    if (!this.base || !this.cursor) return;
    const a = view.worldToScreen(this.base.p1), b = view.worldToScreen(this.base.p2);
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
    if (len < 1e-6) return;
    const c = view.worldToScreen(this.cursor), L = 5000 / len;
    ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = '#2a6df4'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(c.x - dx * L, c.y - dy * L); ctx.lineTo(c.x + dx * L, c.y + dy * L);
    ctx.stroke(); ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// Registry -- the single place main.js looks tools up.
// ---------------------------------------------------------------------------
export const TOOL_REGISTRY = {
  move: MoveTool,
  point: PointTool,
  text: TextTool,
  segment: SegmentTool,
  line: LineTool,
  midpoint: MidpointTool,
  perpendicular: PerpendicularLineTool,
  parallel: ParallelLineTool,
  perpbisector: PerpendicularBisectorTool,
  polygon: PolygonTool,
  isosceles: IsoscelesTriangleTool,
  equilateral: EquilateralTriangleTool,
  square: SquareTool,
  rectangle: RectangleTool,
  circle: CircleTool,
  ellipse: EllipseTool,
  semicircle: SemicircleTool,
  angle: AngleTool,
  anglebisector: AngleBisectorTool,
  circumcircle: CircumcircleTool,
  incircle: IncircleTool,
  ninepoint: NinePointCircleTool,
  excircles: ExcirclesTool,
  spieker: SpiekerCircleTool,
  brocard: BrocardCircleTool,
  mandart: MandartCircleTool,
  apollonius: ApolloniusCirclesTool,
  conway: ConwayCircleTool,
  orthocentroidal: OrthocentroidalCircleTool,
  tangentialtriangle: TangentialTriangleCircleTool,
  bevan: BevanCircleTool,
  incentraltriangle: IncentralTriangleCircleTool,
  johnson: JohnsonCirclesTool,
  lemoine: FirstLemoineCircleTool,
  taylor: TaylorCircleTool,
  incenter: IncenterTool,
  centroid: CentroidTool,
  circumcenter: CircumcenterTool,
  orthocenter: OrthocenterTool,
  ninepointcenter: NinePointCenterTool,
  symmedian: SymmedianPointTool,
  spiekercenter: SpiekerCenterTool,
  etc: EtcCenterTool,
  select: SelectTool,
  label: ToggleLabelTool,
  visibility: ToggleVisibilityTool,
  delete: DeleteTool,
  color: ColorTool,
  rename: RenameTool,
};
