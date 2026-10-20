/**
 * view.js
 *
 * Viewport + renderer. Owns the world<->screen mapping (which is what makes
 * pan and zoom possible) and knows how to paint every object type.
 *
 * World space : math coordinates, y points UP.
 * Screen space: canvas pixels, y points DOWN.
 */

import * as latex from './latex.js';

export class Viewport {
  constructor() {
    this.scale = 60;   // pixels per world unit (bigger default view)
    this.originX = 0;  // screen position of world (0, 0)
    this.originY = 0;
  }

  worldToScreen(p) {
    return { x: this.originX + p.x * this.scale,
             y: this.originY - p.y * this.scale };
  }

  screenToWorld(p) {
    return { x: (p.x - this.originX) / this.scale,
             y: (this.originY - p.y) / this.scale };
  }

  /** Pixel tolerance -> world tolerance (so hit areas stay the same size on screen). */
  pxToWorld(px) { return px / this.scale; }

  panBy(dxPixels, dyPixels) {
    this.originX += dxPixels;
    this.originY += dyPixels;
  }

  /** Zoom keeping the world point under `screenPoint` fixed (cursor-centred). */
  zoomAt(screenPoint, factor) {
    const before = this.screenToWorld(screenPoint);
    this.scale = Math.min(400, Math.max(5, this.scale * factor));
    this.originX = screenPoint.x - before.x * this.scale;
    this.originY = screenPoint.y + before.y * this.scale;
  }
}

const SELECT_COLOR = '#2a6df4';

// Highest number of digits after the decimal point the UI allows. Coordinates
// are 64-bit floats (about 15-16 significant digits), so going past ~10 decimals
// on normal-sized figures would only show floating-point noise, not real accuracy.
export const MAX_DECIMALS = 10;

/**
 * Format `value` with exactly `decimals` digits after the point.
 * Uses Intl.NumberFormat rather than Number.toFixed: toFixed rounds the raw
 * binary value, so e.g. (1.005).toFixed(2) gives "1.00"; Intl rounds the
 * decimal value the person expects and gives "1.01". Falls back to toFixed.
 */
export function formatNumber(value, decimals) {
  const d = Math.min(MAX_DECIMALS, Math.max(0, Math.round(decimals)));
  try {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
      useGrouping: false,
    }).format(value);
  } catch {
    return value.toFixed(d);
  }
}

export class Renderer {
  constructor(canvas, viewport, scene) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.viewport = viewport;
    this.scene = scene;
    this.preview = null; // set by the active tool: { draw(ctx, view) }
    // Single master switch for the "show every segment's length" toggle
    // in the toolbar -- off by default so a bare Segment stays unlabeled
    // until the person turns it on.
    this.showLengths = false;
    // HD rendering: the canvas bitmap is dpr x larger than its on-screen (CSS)
    // size, and every draw call is scaled by dpr, so all the drawing code
    // keeps working in plain CSS pixels. width/height below are CSS pixels.
    this.dpr = 1;
    this.width = 0;
    this.height = 0;
    // Digits after the decimal point shown for segment lengths (toolbar +/- buttons).
    this.decimals = 2;
  }

  resize(width, height) {
    const first = this.canvas.width === 0 || this.canvas.height === 0;
    // At least 2x so edges are smooth even on a normal-density screen;
    // capped at 3x to keep drawing fast.
    this.dpr = Math.min(3, Math.max(window.devicePixelRatio || 1, 2));
    this.width = width;
    this.height = height;
    this.canvas.width = Math.round(width * this.dpr);
    this.canvas.height = Math.round(height * this.dpr);
    this.canvas.style.width = width + 'px';
    this.canvas.style.height = height + 'px';
    if (first) {
      // Put world (0,0) in the middle the first time.
      this.viewport.originX = width / 2;
      this.viewport.originY = height / 2;
    }
  }

  render() {
    const { ctx, viewport: vp, scene } = this;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.width, this.height);
    this._drawAxes();

    // Painting order: filled regions, then curves/lines, then points and text on top.
    const order = ['polygon', 'circle', 'ellipse', 'derivedCircle', 'semicircle', 'line', 'segment', 'angle', 'point', 'derivedPoint', 'intersectionPoint', 'constructedPoint', 'glider', 'text'];
    for (const type of order) {
      for (const o of scene.objects) {
        if (o.type !== type || !o.visible) continue;
        this._drawObject(o);
      }
    }
    for (const o of scene.objects) {
      if (o.visible && o.labelVisible && o.type !== 'text') this._drawLabel(o);
    }
    if (this.preview) this.preview.draw(ctx, vp);
  }

  // ------------------------------------------------------------------ axes
  _drawAxes() {
    const { ctx, viewport: vp } = this;
    const o = vp.worldToScreen({ x: 0, y: 0 });
    ctx.save();
    ctx.strokeStyle = 'rgba(28,35,33,0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, o.y); ctx.lineTo(this.width, o.y);
    ctx.moveTo(o.x, 0); ctx.lineTo(o.x, this.height);
    ctx.stroke();
    ctx.restore();
  }

  // --------------------------------------------------------------- objects
  _stroke(o) {
    const { ctx } = this;
    ctx.strokeStyle = o.selected ? SELECT_COLOR : o.color;
    ctx.lineWidth = o.selected ? 3.8 : 2.4;
  }

  _drawObject(o) {
    const { ctx, viewport: vp } = this;
    ctx.save();
    switch (o.type) {
      case 'text': {
        if (o.isLatex) { this._drawLatexNote(o); break; }
        const s = vp.worldToScreen(o);
        ctx.font = '15px "Iowan Old Style", "Palatino Linotype", Georgia, serif';
        const text = o.label || '';
        const metrics = ctx.measureText(text);
        const padX = 6, padY = 4;
        const w = metrics.width + padX * 2;
        const h = 15 + padY * 2;
        // Remember where this note actually is (world units) so a click
        // anywhere on it -- not just its anchor -- can select/delete it.
        o.bbox = {
          x0: o.x - padX / vp.scale,
          x1: o.x + (metrics.width + padX) / vp.scale,
          y0: o.y - padY / vp.scale,
          y1: o.y + (h - padY) / vp.scale,
        };
        ctx.fillStyle = o.selected ? 'rgba(42,109,244,0.14)' : 'rgba(253,252,249,0.88)';
        ctx.fillRect(s.x - padX, s.y - h + padY, w, h);
        if (o.selected) {
          ctx.strokeStyle = SELECT_COLOR; ctx.lineWidth = 1.5;
          ctx.strokeRect(s.x - padX, s.y - h + padY, w, h);
        }
        ctx.fillStyle = o.color;
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(text, s.x, s.y);
        break;
      }
      case 'point': {
        const s = vp.worldToScreen(o);
        if (o.selected) {
          ctx.beginPath(); ctx.arc(s.x, s.y, 13, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(42,109,244,0.22)'; ctx.fill();
        }
        ctx.beginPath(); ctx.arc(s.x, s.y, 6.5, 0, Math.PI * 2);
        ctx.fillStyle = o.selected ? SELECT_COLOR : o.color; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = '#fdfcf9'; ctx.stroke();
        break;
      }
      case 'intersectionPoint':
      case 'constructedPoint':
      case 'glider':
      case 'derivedPoint': {
        if (!o.isValid()) break; // degenerate source triangle right now: skip drawing
        const s = vp.worldToScreen(o);
        if (o.selected) {
          ctx.beginPath(); ctx.arc(s.x, s.y, 13, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(42,109,244,0.22)'; ctx.fill();
        }
        ctx.beginPath(); ctx.arc(s.x, s.y, 6.5, 0, Math.PI * 2);
        ctx.fillStyle = o.selected ? SELECT_COLOR : o.color; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = '#fdfcf9'; ctx.stroke();
        break;
      }
      case 'segment': {
        const a = vp.worldToScreen(o.p1), b = vp.worldToScreen(o.p2);
        this._stroke(o);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        break;
      }
      case 'angle': {
        const arc = this._angleArcGeometry(o);
        if (!arc) break;
        ctx.beginPath();
        ctx.arc(arc.screenVertex.x, arc.screenVertex.y, arc.screenRadius, arc.startAngle, arc.endAngle, arc.ccw);
        this._stroke(o);
        ctx.stroke();
        break;
      }
      case 'line': {
        const seg = this._clipInfiniteLine(o.p1, o.p2);
        if (!seg) break;
        this._stroke(o);
        ctx.beginPath(); ctx.moveTo(seg[0].x, seg[0].y); ctx.lineTo(seg[1].x, seg[1].y);
        ctx.stroke();
        break;
      }
      case 'polygon': {
        const pts = o.vertices.map(v => vp.worldToScreen(v));
        ctx.beginPath();
        pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
        ctx.closePath();
        ctx.fillStyle = o.selected ? 'rgba(42,109,244,0.16)' : 'rgba(47,93,80,0.10)';
        ctx.fill();
        this._stroke(o); ctx.stroke();
        break;
      }
      case 'circle': {
        const c = vp.worldToScreen(o.center);
        const r = o.radius() * vp.scale;
        ctx.beginPath(); ctx.arc(c.x, c.y, r, 0, Math.PI * 2);
        this._stroke(o); ctx.stroke();
        break;
      }
      case 'derivedCircle': {
        if (!o.isValid()) break; // degenerate source triangle right now: skip drawing
        const c = vp.worldToScreen(o.center);
        const r = o.radius() * vp.scale;
        ctx.beginPath(); ctx.arc(c.x, c.y, r, 0, Math.PI * 2);
        this._stroke(o); ctx.stroke();
        break;
      }
      case 'ellipse': {
        const g = o._geom();
        if (!g) break; // P is between the foci right now: nothing to draw
        const c = vp.worldToScreen({ x: g.cx, y: g.cy });
        // The world tilt is counter-clockwise (y up); canvas rotation is clockwise (y down).
        ctx.beginPath();
        ctx.ellipse(c.x, c.y, g.a * vp.scale, g.b * vp.scale, -g.phi, 0, Math.PI * 2);
        this._stroke(o); ctx.stroke();
        break;
      }
      case 'semicircle': {
        const c = vp.worldToScreen(o.center());
        const r = o.radius() * vp.scale;
        // world diameter angle -> screen angle (y flips sign), then the arc
        // spans 180 degrees on one side of it; `flip` picks which side.
        const worldAngle = o.diameterAngle();
        const screenAngle = -worldAngle;
        const start = o.flip ? screenAngle : screenAngle + Math.PI;
        const end = o.flip ? screenAngle + Math.PI : screenAngle + 2 * Math.PI;
        ctx.beginPath();
        ctx.arc(c.x, c.y, r, start, end);
        ctx.closePath(); // draws the straight diameter edge too
        ctx.fillStyle = o.selected ? 'rgba(42,109,244,0.14)' : 'rgba(47,93,80,0.07)';
        ctx.fill();
        this._stroke(o); ctx.stroke();
        break;
      }
    }
    ctx.restore();
  }

  /**
   * Draw a LaTeX TextNote: request the typeset image (no-op once cached),
   * then either draw it (once ready) or fall back to a lightweight
   * placeholder -- raw source while MathJax is still working, or a red
   * error chip if typesetting failed (e.g. malformed LaTeX). The world
   * anchor (o.x, o.y) is the image's top-left corner, matching where a
   * plain TextNote's baseline sits, so switching a note in/out of LaTeX
   * mode doesn't jump its position.
   */
  _drawLatexNote(o) {
    const { ctx, viewport: vp } = this;
    const source = o.label || '';
    latex.request(source, o.color);
    const entry = latex.get(source, o.color);
    const s = vp.worldToScreen(o);

    if (entry) {
      // Draw at half the oversampled pixel size (see latex.js) so it reads
      // at a similar on-screen scale to the plain-text note's 15px font.
      const w = entry.widthPx, h = entry.heightPx;
      o.bbox = {
        x0: o.x - 4 / vp.scale,
        x1: o.x + (w + 4) / vp.scale,
        y0: o.y - 4 / vp.scale,
        y1: o.y + (h + 4) / vp.scale,
      };
      if (o.selected) {
        ctx.save();
        ctx.strokeStyle = SELECT_COLOR; ctx.lineWidth = 1.5;
        ctx.strokeRect(s.x - 4, s.y - h - 4, w + 8, h + 8);
        ctx.restore();
      }
      ctx.drawImage(entry.img, s.x, s.y - h, w, h);
      return;
    }

    // Not ready yet (or failed): small placeholder chip so the note is
    // still visible and clickable while MathJax works or if it errored.
    const failed = latex.failed(source, o.color);
    ctx.save();
    ctx.font = '13px ui-monospace, "Cascadia Code", Consolas, monospace';
    const shown = failed ? '\u26a0 LaTeX error' : (source || '\u2026');
    const metrics = ctx.measureText(shown);
    const padX = 6, padY = 4, h = 15 + padY * 2, w = metrics.width + padX * 2;
    o.bbox = {
      x0: o.x - padX / vp.scale,
      x1: o.x + (w - padX) / vp.scale,
      y0: o.y,
      y1: o.y + h / vp.scale,
    };
    ctx.fillStyle = failed ? 'rgba(200,60,50,0.12)' : 'rgba(253,252,249,0.88)';
    ctx.fillRect(s.x - padX, s.y - h, w, h);
    ctx.strokeStyle = failed ? '#c83c32' : 'rgba(28,35,33,0.25)';
    ctx.lineWidth = 1; ctx.strokeRect(s.x - padX, s.y - h, w, h);
    ctx.fillStyle = failed ? '#c83c32' : o.color;
    ctx.textBaseline = 'alphabetic';
    ctx.fillText(shown, s.x, s.y - padY);
    ctx.restore();
  }

  /**
   * Clip the infinite line through world points p1, p2 to the canvas
   * rectangle (Liang-Barsky), returning two screen points or null.
   */
  _clipInfiniteLine(p1, p2) {
    const { viewport: vp } = this;
    const a = vp.worldToScreen(p1), b = vp.worldToScreen(p2);
    const dx = b.x - a.x, dy = b.y - a.y;
    if (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9) return null;

    // Parametrise as a + t*(dx,dy) and clip t against the canvas box,
    // extended generously so the line reaches both edges.
    let t0 = -1e6, t1 = 1e6;
    const clip = (p, q) => {
      if (Math.abs(p) < 1e-12) return q >= 0;
      const r = q / p;
      if (p < 0) { if (r > t1) return false; if (r > t0) t0 = r; }
      else       { if (r < t0) return false; if (r < t1) t1 = r; }
      return true;
    };
    const ok =
      clip(-dx, a.x - 0) && clip(dx, this.width - a.x) &&
      clip(-dy, a.y - 0) && clip(dy, this.height - a.y);
    if (!ok) return null;
    return [{ x: a.x + t0 * dx, y: a.y + t0 * dy },
            { x: a.x + t1 * dx, y: a.y + t1 * dy }];
  }

  /**
   * Screen-space geometry for an Angle's arc: a fixed screen-pixel radius
   * (so the arc reads the same size at any zoom level, unlike a
   * world-space radius which would shrink/grow with the shapes around
   * it), the canvas start/end angles for the two rays, and which
   * direction sweeps through the SHORTER (interior) arc -- canvas angles
   * increase clockwise (since screen y points down), so "shorter way
   * round" has to be decided explicitly rather than just picking a fixed
   * winding direction.
   */
  _angleArcGeometry(o) {
    const { viewport: vp } = this;
    const v1x = o.p1.x - o.vertex.x, v1y = o.p1.y - o.vertex.y;
    const v2x = o.p3.x - o.vertex.x, v2y = o.p3.y - o.vertex.y;
    const len1 = Math.hypot(v1x, v1y), len2 = Math.hypot(v2x, v2y);
    if (len1 < 1e-9 || len2 < 1e-9) return null;

    const screenVertex = vp.worldToScreen(o.vertex);
    // atan2 on SCREEN-space vectors (world y flips sign going to screen),
    // so these angles are directly usable with ctx.arc().
    const s1 = vp.worldToScreen(o.p1), s2 = vp.worldToScreen(o.p3);
    const startAngle = Math.atan2(s1.y - screenVertex.y, s1.x - screenVertex.x);
    const endAngle = Math.atan2(s2.y - screenVertex.y, s2.x - screenVertex.x);
    let delta = endAngle - startAngle;
    while (delta <= -Math.PI) delta += 2 * Math.PI;
    while (delta > Math.PI) delta -= 2 * Math.PI;
    const ccw = delta < 0; // sweep the SHORT way round, whichever direction that is

    const screenRadius = 26; // fixed on-screen size regardless of zoom
    const mid = startAngle + delta / 2;
    return { screenVertex, screenRadius, startAngle, endAngle, ccw,
             labelAngle: mid, labelScreen: {
               x: screenVertex.x + (screenRadius + 14) * Math.cos(mid),
               y: screenVertex.y + (screenRadius + 14) * Math.sin(mid),
             } };
  }

  // ---------------------------------------------------------------- labels
  _drawLabelDefault(o) {
    const { ctx, viewport: vp } = this;
    const anchor = this._labelAnchor(o);
    if (!anchor) return;
    const s = vp.worldToScreen(anchor);
    let text = this._labelText(o);
    if (!text) return;
    ctx.save();
    // The Greek keys insert Mathematical Italic letters (U+1D6FC..). Only
    // math-aware fonts carry that block, so "Cambria Math" (Windows) and
    // "STIX Two Math" / "Noto Sans Math" / "Segoe UI Symbol" come first. They
    // are already italic, so we deliberately do NOT add CSS 'italic' here --
    // that would slant Latin labels (A, B, ...) only, which is what we want
    // to keep upright and readable.
    ctx.font = '18px "Cambria Math", "STIX Two Math", "Noto Sans Math", "Segoe UI Symbol", "Times New Roman", -apple-system, "Segoe UI", serif';
    ctx.fillStyle = o.selected ? SELECT_COLOR : '#1c2321';
    ctx.fillText(text, s.x + 9, s.y - 9);
    ctx.restore();
  }

  /**
   * Text shown for an object's label. A person's own typed label always
   * wins; a bare Segment with no label instead shows its live length
   * (Euclidean distance between its two endpoints) ONLY while the
   * toolbar's "Lengths" switch (this.showLengths) is on -- recomputed
   * every frame, so dragging either endpoint updates the number
   * instantly with no separate "on drag" event needed.
   *
   * The displayed form is "AB = 6.14" when both endpoints have their own
   * label (A, B, ...); if either endpoint is unlabeled it falls back to
   * the bare number, since "= 6.14" alone would be confusing.
   */
  _labelText(o) {
    if (o.label) return o.label;
    if (o.type === 'segment' && this.showLengths) {
      const value = formatNumber(o.length(), this.decimals);
      const n1 = o.p1.label, n2 = o.p2.label;
      return (n1 && n2) ? `${n1}${n2} = ${value}` : value;
    }
    if (o.type === 'angle') return o.degrees().toFixed(1) + '\u00b0'; // e.g. "57.3\u00b0"
    return '';
  }

  _labelAnchor(o) {
    switch (o.type) {
      case 'point':   return o;
      case 'derivedPoint':
      case 'constructedPoint':
      case 'glider':
      case 'intersectionPoint': return o.isValid() ? o : null;
      case 'segment':
      case 'line':    return { x: (o.p1.x + o.p2.x) / 2, y: (o.p1.y + o.p2.y) / 2 };
      case 'circle':  return { x: o.center.x + o.radius(), y: o.center.y };
      case 'derivedCircle': return o.isValid() ? { x: o.center.x + o.radius(), y: o.center.y } : null;
      case 'ellipse': return o.pointAt(0); // end of the major axis (null while degenerate)
      case 'semicircle': {
        const c = o.center();
        return { x: c.x + o.radius() * Math.cos(o.diameterAngle() + (o.flip ? Math.PI / 2 : -Math.PI / 2)),
                 y: c.y + o.radius() * Math.sin(o.diameterAngle() + (o.flip ? Math.PI / 2 : -Math.PI / 2)) };
      }
      case 'polygon': {
        const n = o.vertices.length;
        return { x: o.vertices.reduce((s, v) => s + v.x, 0) / n,
                 y: o.vertices.reduce((s, v) => s + v.y, 0) / n };
      }
      default: return null;
    }
  }

  /**
   * Angle's label sits just outside its arc, at a fixed screen-space
   * position already computed by _angleArcGeometry (the arc has a fixed
   * screen radius, so its label position is naturally screen-space too,
   * unlike every other object's world-space anchor). Handled as a special
   * case up front; everything else falls through to the normal path.
   */
  _drawLabel(o) {
    if (o.type === 'angle') {
      const arc = this._angleArcGeometry(o);
      if (!arc) return;
      const text = this._labelText(o);
      if (!text) return;
      const { ctx } = this;
      ctx.save();
      ctx.font = '13px "Cambria Math", "STIX Two Math", "Noto Sans Math", "Segoe UI Symbol", "Times New Roman", -apple-system, "Segoe UI", serif';
      ctx.fillStyle = o.selected ? SELECT_COLOR : '#1c2321';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, arc.labelScreen.x, arc.labelScreen.y);
      ctx.restore();
      return;
    }
    this._drawLabelDefault(o);
  }
}
