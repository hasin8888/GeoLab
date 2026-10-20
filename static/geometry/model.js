/**
 * model.js
 *
 * The geometric "scene graph". Everything here is in WORLD coordinates
 * (math space: y grows upward, unit = 1). Nothing in this file knows about
 * pixels, the canvas, or the mouse -- that is view.js's job.
 *
 * Dependency rule: Segment / Line / Polygon / Circle do not store their own
 * coordinates. They hold references to Point objects, so dragging one Point
 * automatically updates every object built on it (this is what makes a
 * geometry app feel "alive").
 */

let _nextId = 1;

export class GeoObject {
  constructor(type) {
    this.id = _nextId++;
    this.type = type;
    this.visible = true;      // Show/Hide Object
    this.labelVisible = true; // Show/Hide Label
    this.selected = false;
    this.label = '';
    this.color = '#1c2321';
  }

  /** Objects this one is built from (used for cascade delete). */
  dependencies() { return []; }

  /** Distance from a WORLD point to this object, or Infinity. */
  distanceTo(_p) { return Infinity; }

  /** Serialise to plain JSON (references become ids). */
  toJSON() { throw new Error('toJSON not implemented for ' + this.type); }
}

export class Point extends GeoObject {
  constructor(x, y) {
    super('point');
    this.x = x;
    this.y = y;
    this.color = '#b3541e';
  }
  distanceTo(p) { return Math.hypot(this.x - p.x, this.y - p.y); }
  toJSON() {
    return { id: this.id, type: 'point', x: this.x, y: this.y,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/**
 * Text: a free-floating annotation anchored at a world point. Unlike
 * Point, its "label" IS the content the user typed -- there is no
 * separate auto-letter, and labelVisible is always true (hiding a text
 * note would just make it a useless invisible point).
 *
 * isLatex: when true, `label` holds LaTeX source (e.g. "\\frac{a}{b}")
 * instead of plain text, and the renderer draws it as typeset math
 * (via MathJax) rather than raw characters -- see view.js/tools.js.
 */
export class TextNote extends GeoObject {
  constructor(x, y, content = '', isLatex = false) {
    super('text');
    this.x = x;
    this.y = y;
    this.label = content;
    this.isLatex = isLatex;
    this.color = '#1c2321';
  }
  /**
   * Distance from a WORLD point to this note's on-screen box. `bbox` (in
   * world units) is refreshed by the Renderer every frame, because only it
   * knows how big the text actually draws. Clicking anywhere inside the
   * box counts as a hit (distance 0) -- not just next to the bottom-left
   * anchor, which is what made notes impossible to select or delete.
   * Falls back to the anchor point until the first render.
   */
  distanceTo(p) {
    const b = this.bbox;
    if (!b) return Math.hypot(this.x - p.x, this.y - p.y);
    const dx = Math.max(b.x0 - p.x, 0, p.x - b.x1);
    const dy = Math.max(b.y0 - p.y, 0, p.y - b.y1);
    return Math.hypot(dx, dy);
  }
  toJSON() {
    return { id: this.id, type: 'text', x: this.x, y: this.y,
             label: this.label, isLatex: this.isLatex, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/**
 * Angle: measures the angle at `vertex`, between rays vertex->p1 and
 * vertex->p3. Like Segment/Line, it stores references (not coordinates),
 * so dragging any of the 3 points updates the measurement live.
 */
export class Angle extends GeoObject {
  constructor(p1, vertex, p3) {
    super('angle');
    this.p1 = p1;
    this.vertex = vertex;
    this.p3 = p3;
  }
  dependencies() { return [this.p1, this.vertex, this.p3]; }
  /** Interior angle at the vertex, in degrees, range (0, 180]. */
  degrees() {
    const v1x = this.p1.x - this.vertex.x, v1y = this.p1.y - this.vertex.y;
    const v2x = this.p3.x - this.vertex.x, v2y = this.p3.y - this.vertex.y;
    const len1 = Math.hypot(v1x, v1y), len2 = Math.hypot(v2x, v2y);
    if (len1 < 1e-12 || len2 < 1e-12) return 0;
    const cos = (v1x * v2x + v1y * v2y) / (len1 * len2);
    return Math.acos(Math.max(-1, Math.min(1, cos))) * 180 / Math.PI;
  }
  // "Near" the vertex, biased slightly so the arc itself (not the whole
  // triangle) is what responds to a click.
  distanceTo(p) { return Math.hypot(this.vertex.x - p.x, this.vertex.y - p.y); }
  /**
   * Unit direction of the internal angle bisector ray, starting at the
   * vertex: the normalised sum of the two unit vectors toward p1 and p3
   * (the standard construction -- it bisects the angle between them by
   * symmetry, whichever way the angle turns). Returns null if either ray
   * is degenerate (a point sitting on the vertex).
   */
  bisectorDirection() {
    const v1x = this.p1.x - this.vertex.x, v1y = this.p1.y - this.vertex.y;
    const v2x = this.p3.x - this.vertex.x, v2y = this.p3.y - this.vertex.y;
    const len1 = Math.hypot(v1x, v1y), len2 = Math.hypot(v2x, v2y);
    if (len1 < 1e-12 || len2 < 1e-12) return null;
    let dx = v1x / len1 + v2x / len2, dy = v1y / len1 + v2y / len2;
    const len = Math.hypot(dx, dy);
    if (len < 1e-9) {
      // p1, vertex, p3 are collinear with the vertex between them (a
      // straight 180 degree angle): sum-of-unit-vectors cancels out, so
      // fall back to either perpendicular of the ray as the bisector.
      dx = -v1y / len1; dy = v1x / len1;
      return { x: dx, y: dy };
    }
    return { x: dx / len, y: dy / len };
  }
  toJSON() {
    return { id: this.id, type: 'angle', p1: this.p1.id, vertex: this.vertex.id, p3: this.p3.id,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

export class Segment extends GeoObject {
  constructor(p1, p2) {
    super('segment');
    this.p1 = p1;
    this.p2 = p2;
  }
  dependencies() { return [this.p1, this.p2]; }
  length() { return Math.hypot(this.p2.x - this.p1.x, this.p2.y - this.p1.y); }
  distanceTo(p) {
    return distToSegment(p, this.p1, this.p2);
  }
  toJSON() {
    return { id: this.id, type: 'segment', p1: this.p1.id, p2: this.p2.id,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

export class Line extends GeoObject {
  constructor(p1, p2) {
    super('line');
    this.p1 = p1;
    this.p2 = p2;
  }
  dependencies() { return [this.p1, this.p2]; }
  distanceTo(p) {
    const dx = this.p2.x - this.p1.x, dy = this.p2.y - this.p1.y;
    const len = Math.hypot(dx, dy);
    if (len < 1e-12) return this.p1.distanceTo(p);
    // Perpendicular distance to the infinite line.
    return Math.abs(dy * (p.x - this.p1.x) - dx * (p.y - this.p1.y)) / len;
  }
  toJSON() {
    return { id: this.id, type: 'line', p1: this.p1.id, p2: this.p2.id,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

export class Polygon extends GeoObject {
  constructor(vertices) {
    super('polygon');
    this.vertices = vertices; // array of Point
  }
  dependencies() { return [...this.vertices]; }
  area() {
    let s = 0;
    const n = this.vertices.length;
    for (let i = 0; i < n; i++) {
      const a = this.vertices[i], b = this.vertices[(i + 1) % n];
      s += a.x * b.y - b.x * a.y;
    }
    return Math.abs(s) / 2;
  }
  perimeter() {
    let s = 0;
    const n = this.vertices.length;
    for (let i = 0; i < n; i++) {
      const a = this.vertices[i], b = this.vertices[(i + 1) % n];
      s += Math.hypot(b.x - a.x, b.y - a.y);
    }
    return s;
  }
  contains(p) {
    // Ray casting.
    let inside = false;
    const v = this.vertices;
    for (let i = 0, j = v.length - 1; i < v.length; j = i++) {
      const xi = v[i].x, yi = v[i].y, xj = v[j].x, yj = v[j].y;
      if ((yi > p.y) !== (yj > p.y) &&
          p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  distanceTo(p) {
    // Distance to the boundary (so you select a polygon by its edges).
    let best = Infinity;
    const n = this.vertices.length;
    for (let i = 0; i < n; i++) {
      best = Math.min(best,
        distToSegment(p, this.vertices[i], this.vertices[(i + 1) % n]));
    }
    return best;
  }
  toJSON() {
    return { id: this.id, type: 'polygon',
             vertices: this.vertices.map(v => v.id),
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/** Circle with Centre through Point. Radius is derived, never stored. */
export class Circle extends GeoObject {
  constructor(center, through) {
    super('circle');
    this.center = center;
    this.through = through;
  }
  dependencies() { return [this.center, this.through]; }
  radius() {
    return Math.hypot(this.through.x - this.center.x,
                      this.through.y - this.center.y);
  }
  distanceTo(p) {
    return Math.abs(Math.hypot(p.x - this.center.x, p.y - this.center.y)
                    - this.radius());
  }
  toJSON() {
    return { id: this.id, type: 'circle',
             center: this.center.id, through: this.through.id,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/**
 * Semicircle on diameter p1-p2. Like Circle, it stores references (not
 * coordinates/radius), so dragging either endpoint keeps it live. Centre
 * and radius are always derived: centre is the midpoint of p1-p2, radius
 * is half the distance between them. `flip` picks which of the two
 * half-planes (relative to the diameter) the arc bulges into -- toggled
 * while placing it (press 'F') so either half can be built without a
 * separate tool. view.js reads flip + the diameter's direction to know
 * which 180 degrees of the circle to actually draw.
 */
export class Semicircle extends GeoObject {
  constructor(p1, p2, flip = false) {
    super('semicircle');
    this.p1 = p1;
    this.p2 = p2;
    this.flip = flip;
  }
  dependencies() { return [this.p1, this.p2]; }
  center() { return { x: (this.p1.x + this.p2.x) / 2, y: (this.p1.y + this.p2.y) / 2 }; }
  radius() { return Math.hypot(this.p2.x - this.p1.x, this.p2.y - this.p1.y) / 2; }
  /** Direction angle (radians) of the diameter p1->p2. */
  diameterAngle() { return Math.atan2(this.p2.y - this.p1.y, this.p2.x - this.p1.x); }
  distanceTo(p) {
    // A semicircle's boundary is the curved arc PLUS the straight
    // diameter, so check both and take whichever is closer.
    const c = this.center(), r = this.radius();
    if (r < 1e-12) return Math.hypot(p.x - c.x, p.y - c.y);
    const toCenter = Math.hypot(p.x - c.x, p.y - c.y);
    const arcDist = Math.abs(toCenter - r);
    const diamDist = distToSegment(p, this.p1, this.p2);
    return Math.min(arcDist, diamDist);
  }
  toJSON() {
    return { id: this.id, type: 'semicircle', p1: this.p1.id, p2: this.p2.id,
             flip: this.flip, label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/**
 * Ellipse defined by its two foci F1, F2 and one point P on the curve -- the
 * classic "sum of distances to the foci is constant" construction (the same
 * way GeoGebra's Ellipse tool works). Like Circle it stores references to Point
 * objects, never numbers: centre, semi-axes and tilt are derived on demand, so
 * dragging a focus or the through-point reshapes the ellipse live.
 *
 *   2a = |PF1| + |PF2|     length of the major axis
 *   2c = |F1F2|            distance between the foci
 *   b  = sqrt(a^2 - c^2)   semi-minor axis
 *
 * It is degenerate (nothing is drawn) when P lies on the segment F1F2: then
 * b = 0 and the "ellipse" collapses onto that segment. If both foci sit on the
 * same spot it is simply a circle.
 */
export class Ellipse extends GeoObject {
  constructor(f1, f2, through) {
    super('ellipse');
    this.f1 = f1;
    this.f2 = f2;
    this.through = through;
  }
  dependencies() { return [this.f1, this.f2, this.through]; }

  /** {cx, cy, a, b, c, phi} (phi = tilt of the major axis, radians), or null if degenerate. */
  _geom() {
    const { f1, f2, through: p } = this;
    const a = (Math.hypot(p.x - f1.x, p.y - f1.y) + Math.hypot(p.x - f2.x, p.y - f2.y)) / 2;
    const c = Math.hypot(f2.x - f1.x, f2.y - f1.y) / 2;
    const b = Math.sqrt(Math.max(0, (a - c) * (a + c)));
    if (!(a > 1e-9) || b < 1e-6 * a) return null;
    return { cx: (f1.x + f2.x) / 2, cy: (f1.y + f2.y) / 2, a, b, c,
             phi: Math.atan2(f2.y - f1.y, f2.x - f1.x) };
  }
  /** True while P is not on the segment between the foci. */
  isValid() { return this._geom() !== null; }
  center() { return { x: (this.f1.x + this.f2.x) / 2, y: (this.f1.y + this.f2.y) / 2 }; }
  /** Semi-major a and semi-minor b (both 0 while degenerate). */
  semiAxes() { const g = this._geom(); return g ? { a: g.a, b: g.b } : { a: 0, b: 0 }; }
  /** Tilt of the major axis (direction F1 -> F2), in radians. */
  rotation() { return Math.atan2(this.f2.y - this.f1.y, this.f2.x - this.f1.x); }
  eccentricity() { const g = this._geom(); return g ? g.c / g.a : 0; }
  /** World point at parameter t (t = 0 is the end of the major axis nearest F2). */
  pointAt(t) { const g = this._geom(); return g ? ellipsePointAt(g, t) : null; }
  distanceTo(p) {
    const g = this._geom();
    if (!g) return Infinity;
    const q = ellipsePointAt(g, ellipseNearestParam(g, p));
    return Math.hypot(q.x - p.x, q.y - p.y);
  }
  toJSON() {
    return { id: this.id, type: 'ellipse', f1: this.f1.id, f2: this.f2.id,
             through: this.through.id,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/** World point -> the ellipse's own frame (origin at the centre, x along the major axis). */
function ellipseLocal(g, p) {
  const dx = p.x - g.cx, dy = p.y - g.cy, c = Math.cos(g.phi), s = Math.sin(g.phi);
  return { u: dx * c + dy * s, v: -dx * s + dy * c };
}

/** World point of the ellipse at parameter t (a * cos t along the major axis, b * sin t across). */
function ellipsePointAt(g, t) {
  const u = g.a * Math.cos(t), v = g.b * Math.sin(t), c = Math.cos(g.phi), s = Math.sin(g.phi);
  return { x: g.cx + u * c - v * s, y: g.cy + u * s + v * c };
}

/** Parameter t in [-PI, PI) of the ellipse point nearest to world point w. */
function ellipseNearestParam(g, w) {
  const q = ellipseLocal(g, w);
  const f = (t) => (g.a * Math.cos(t) - q.u) ** 2 + (g.b * Math.sin(t) - q.v) ** 2;
  const tau = 2 * Math.PI, N = 96, step = tau / N;
  // Coarse scan for the nearest sample, then golden-section search around it.
  let bestT = 0, bestF = Infinity;
  for (let i = 0; i < N; i++) {
    const t = i * step, ft = f(t);
    if (ft < bestF) { bestF = ft; bestT = t; }
  }
  const gr = (Math.sqrt(5) - 1) / 2;
  let lo = bestT - step, hi = bestT + step;
  let x1 = hi - gr * (hi - lo), x2 = lo + gr * (hi - lo);
  let f1 = f(x1), f2 = f(x2);
  for (let k = 0; k < 60; k++) {
    if (f1 < f2) { hi = x2; x2 = x1; f2 = f1; x1 = hi - gr * (hi - lo); f1 = f(x1); }
    else         { lo = x1; x1 = x2; f1 = f2; x2 = lo + gr * (hi - lo); f2 = f(x2); }
  }
  const t = (lo + hi) / 2;
  return ((t + Math.PI) % tau + tau) % tau - Math.PI;
}

/**
 * DerivedCircle: a triangle-circle (incircle, circumcircle, etc.) that
 * stays LIVE -- it holds references to the 3 source vertex Points (like
 * Segment/Polygon do) and recomputes its center/radius from a formula
 * function every time they're asked for, instead of freezing them at
 * construction time. Dragging any of the 3 vertices therefore moves this
 * circle automatically, the same way dragging a Segment's endpoint moves
 * the segment.
 *
 *   formulaFn(A, B, C) -> {x, y, r} | null   (null = degenerate triangle)
 *   formulaName             -- registry key, used to re-look-up formulaFn
 *                               on load (functions can't survive JSON)
 */
export class DerivedCircle extends GeoObject {
  /**
   * index -- for formulas returning an array of circles (excircles,
   * apollonius, johnson: one per vertex), which slot to use. Left
   * undefined for formulas that already return a single {x,y,r}.
   */
  constructor(A, B, C, formulaName, index) {
    super('derivedCircle');
    this.A = A;
    this.B = B;
    this.C = C;
    this.formulaName = formulaName;
    this.index = index;
  }
  dependencies() { return [this.A, this.B, this.C]; }
  /** Current {x, y, r}, or null if the 3 vertices are currently degenerate. */
  _compute() {
    const fn = DERIVED_CIRCLE_FORMULAS[this.formulaName];
    if (!fn) return null;
    const result = fn(this.A, this.B, this.C);
    if (this.index === undefined) return result;
    return result ? (result[this.index] || null) : null;
  }
  get center() {
    const c = this._compute();
    return c ? { x: c.x, y: c.y } : { x: this.A.x, y: this.A.y }; // fallback: never undefined
  }
  radius() {
    const c = this._compute();
    return c ? c.r : 0;
  }
  /** True while the 3 current vertices form a valid (non-degenerate) triangle. */
  isValid() { return this._compute() !== null; }
  distanceTo(p) {
    const c = this._compute();
    if (!c) return Infinity;
    return Math.abs(Math.hypot(p.x - c.x, p.y - c.y) - c.r);
  }
  toJSON() {
    return { id: this.id, type: 'derivedCircle', A: this.A.id, B: this.B.id, C: this.C.id,
             formulaName: this.formulaName, index: this.index,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

/**
 * DerivedPoint: a triangle-centre point (incenter, centroid, etc.) that
 * stays LIVE, mirroring DerivedCircle above -- holds the 3 source
 * vertices and recomputes its {x, y} from a formula function on demand.
 * `index` mirrors DerivedCircle's: selects one point out of a formula
 * that returns an array (used for excircle/apollonius/johnson CENTERS,
 * where formulaName points at DERIVED_CIRCLE_FORMULAS instead of
 * DERIVED_POINT_FORMULAS -- see _compute()).
 */
export class DerivedPoint extends GeoObject {
  constructor(A, B, C, formulaName, index) {
    super('derivedPoint');
    this.A = A;
    this.B = B;
    this.C = C;
    this.formulaName = formulaName;
    this.index = index;
    this.color = '#8a4b8f';
  }
  dependencies() { return [this.A, this.B, this.C]; }
  _compute() {
    // Any verified Kimberling center X(n): formulaName 'etc', n in `index`.
    if (this.formulaName === 'etc') return etcCenterOf(this.A, this.B, this.C, this.index);
    // Plain triangle-centre point (X(1), X(2), ...): {x, y} directly.
    const pointFn = DERIVED_POINT_FORMULAS[this.formulaName];
    if (pointFn) return pointFn(this.A, this.B, this.C);
    // Circle-centre point (used to label an excircle/Apollonius/Johnson
    // circle's centre): reuse the circle formula and read off {x, y},
    // optionally picking one entry out of an array result via `index`.
    const circleFn = DERIVED_CIRCLE_FORMULAS[this.formulaName];
    if (!circleFn) return null;
    let result = circleFn(this.A, this.B, this.C);
    if (this.index !== undefined) result = result ? (result[this.index] || null) : null;
    return result ? { x: result.x, y: result.y } : null;
  }
  get x() { const p = this._compute(); return p ? p.x : this.A.x; }
  get y() { const p = this._compute(); return p ? p.y : this.A.y; }
  isValid() { return this._compute() !== null; }
  distanceTo(p) {
    const c = this._compute();
    if (!c) return Infinity;
    return Math.hypot(c.x - p.x, c.y - p.y);
  }
  toJSON() {
    return { id: this.id, type: 'derivedPoint', A: this.A.id, B: this.B.id, C: this.C.id,
             formulaName: this.formulaName, index: this.index,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

// ---------------------------------------------------------------------------
// Triangle-centre geometry (Circumcircle, Incircle, Nine-point circle,
// Excircles). Pure math -- takes 3 {x, y} points, returns a plain
// {x, y, r} (or an array of those, for the 3 excircles). No Scene/Point
// objects here, so this stays testable and reusable outside the tools.
// ---------------------------------------------------------------------------

/** Twice the signed area (shoelace). Near-zero => collinear points. */
function signedArea2(A, B, C) {
  return (B.x - A.x) * (C.y - A.y) - (C.x - A.x) * (B.y - A.y);
}

/** Throws-free validity check shared by every centre function below. */
export function isValidTriangle(A, B, C) {
  return Math.abs(signedArea2(A, B, C)) > 1e-9;
}

/** Circumcentre + circumradius: equidistant from all 3 vertices. */
export function circumcircleOf(A, B, C) {
  const D = 2 * (A.x * (B.y - C.y) + B.x * (C.y - A.y) + C.x * (A.y - B.y));
  if (Math.abs(D) < 1e-9) return null; // collinear
  const ux = ((A.x ** 2 + A.y ** 2) * (B.y - C.y) +
              (B.x ** 2 + B.y ** 2) * (C.y - A.y) +
              (C.x ** 2 + C.y ** 2) * (A.y - B.y)) / D;
  const uy = ((A.x ** 2 + A.y ** 2) * (C.x - B.x) +
              (B.x ** 2 + B.y ** 2) * (A.x - C.x) +
              (C.x ** 2 + C.y ** 2) * (B.x - A.x)) / D;
  const r = Math.hypot(A.x - ux, A.y - uy);
  return { x: ux, y: uy, r };
}

/** Incentre + inradius: weighted by opposite side lengths a, b, c. */
export function incircleOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y); // side opposite A
  const b = Math.hypot(C.x - A.x, C.y - A.y); // side opposite B
  const c = Math.hypot(A.x - B.x, A.y - B.y); // side opposite C
  const perim = a + b + c;
  if (perim < 1e-9) return null;
  const ix = (a * A.x + b * B.x + c * C.x) / perim;
  const iy = (a * A.y + b * B.y + c * C.y) / perim;
  const s = perim / 2;
  const area = Math.abs(signedArea2(A, B, C)) / 2;
  const r = area / s;
  return { x: ix, y: iy, r };
}

/**
 * Nine-point circle: passes through the 3 side-midpoints, the 3 altitude
 * feet, and the 3 Euler points (vertex-to-orthocenter midpoints). Its
 * centre is the midpoint of the circumcentre and orthocentre (X(5), the
 * Nine-Point Centre); its radius is R/2.
 */
export function ninePointCircleOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  // Orthocentre: H = A + B + C - 2 * circumcentre.
  const hx = A.x + B.x + C.x - 2 * circ.x;
  const hy = A.y + B.y + C.y - 2 * circ.y;
  const nx = (circ.x + hx) / 2;
  const ny = (circ.y + hy) / 2;
  return { x: nx, y: ny, r: circ.r / 2 };
}

/**
 * The 3 excircles: excircle_A is tangent to side a (=BC) and to the
 * extensions of the other two sides, and so on for B and C. Returned as
 * an array [exA, exB, exC], each {x, y, r, label}. A null entry means
 * that excentre is undefined for this triangle (only possible if two
 * side lengths are exactly equal in the denominator, i.e. degenerate).
 */
export function excirclesOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  const s = (a + b + c) / 2;
  const area = Math.abs(signedArea2(A, B, C)) / 2;
  if (area < 1e-9) return [null, null, null];

  const denomA = -a + b + c, denomB = a - b + c, denomC = a + b - c;
  const mk = (denom, wx, wy, dist) => {
    if (Math.abs(denom) < 1e-9) return null;
    return { x: wx / denom, y: wy / denom, r: area / Math.abs(dist) };
  };
  const exA = mk(denomA, -a * A.x + b * B.x + c * C.x, -a * A.y + b * B.y + c * C.y, s - a);
  const exB = mk(denomB, a * A.x - b * B.x + c * C.x, a * A.y - b * B.y + c * C.y, s - b);
  const exC = mk(denomC, a * A.x + b * B.x - c * C.x, a * A.y + b * B.y - c * C.y, s - c);
  return [exA, exB, exC];
}

/**
 * Spieker circle: the incircle of the medial triangle (Ma Mb Mc, joining
 * the 3 side-midpoints). Its centre is the Spieker centre X(10); its
 * radius is exactly half the ordinary inradius.
 */
export function spiekerCircleOf(A, B, C) {
  const Ma = { x: (B.x + C.x) / 2, y: (B.y + C.y) / 2 };
  const Mb = { x: (C.x + A.x) / 2, y: (C.y + A.y) / 2 };
  const Mc = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
  return incircleOf(Ma, Mb, Mc);
}

/**
 * Brocard circle: the circle with diameter OK, where O is the
 * circumcentre and K is the symmedian point (X(6), barycentric a²:b²:c²).
 * Passes through both Brocard points as well as O and K.
 */
export function brocardCircleOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  const a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2; // a², side opposite A
  const b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2; // b², side opposite B
  const c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2; // c², side opposite C
  const wsum = a2 + b2 + c2;
  if (wsum < 1e-9) return null;
  const kx = (a2 * A.x + b2 * B.x + c2 * C.x) / wsum;
  const ky = (a2 * A.y + b2 * B.y + c2 * C.y) / wsum;
  const cx = (circ.x + kx) / 2, cy = (circ.y + ky) / 2;
  const r = Math.hypot(circ.x - kx, circ.y - ky) / 2;
  return { x: cx, y: cy, r };
}

/**
 * Mandart circle: the circumcircle of the extouch triangle -- the 3
 * points where each excircle touches its corresponding side (as opposed
 * to the incircle's touch points, which give the contact triangle).
 */
export function mandartCircleOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  const s = (a + b + c) / 2;
  if (a < 1e-9 || b < 1e-9 || c < 1e-9) return null;
  const Xa = { x: B.x + (s - c) / a * (C.x - B.x), y: B.y + (s - c) / a * (C.y - B.y) };
  const Xb = { x: C.x + (s - a) / b * (A.x - C.x), y: C.y + (s - a) / b * (A.y - C.y) };
  const Xc = { x: A.x + (s - b) / c * (B.x - A.x), y: A.y + (s - b) / c * (B.y - A.y) };
  return circumcircleOf(Xa, Xb, Xc);
}

/**
 * Apollonius circles: for each vertex V, the locus of points P satisfying
 * PX/PY = VX/VY (X, Y = the other two vertices) is a circle through the
 * internal and external points dividing the opposite side in that ratio.
 * Returns [apolloniusA, apolloniusB, apolloniusC], each {x, y, r}, or null
 * for a vertex whose two adjacent sides are equal (the "circle" degenerates
 * to the perpendicular bisector -- infinite radius).
 */
export function apolloniusCirclesOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);

  // Divides segment P-Q internally (D) and externally (E) in ratio m:n
  // (PD:DQ = m:n), then returns the circle with diameter DE.
  function circleFor(P, Q, mRatio, nRatio) {
    if (mRatio < 1e-9 || nRatio < 1e-9) return null;
    if (Math.abs(mRatio - nRatio) < 1e-9) return null; // equal sides: no finite circle
    const sum = mRatio + nRatio, diff = nRatio - mRatio;
    const D = { x: (nRatio * P.x + mRatio * Q.x) / sum, y: (nRatio * P.y + mRatio * Q.y) / sum };
    const E = { x: (nRatio * P.x - mRatio * Q.x) / diff, y: (nRatio * P.y - mRatio * Q.y) / diff };
    return { x: (D.x + E.x) / 2, y: (D.y + E.y) / 2, r: Math.hypot(D.x - E.x, D.y - E.y) / 2 };
  }

  const apolloniusA = circleFor(B, C, c, b); // ratio AB:AC = c:b, on side BC
  const apolloniusB = circleFor(C, A, a, c); // ratio BC:BA = a:c, on side CA
  const apolloniusC = circleFor(A, B, b, a); // ratio CA:CB = b:a, on side AB
  return [apolloniusA, apolloniusB, apolloniusC];
}

/**
 * Conway circle: extend each side beyond each of its endpoints by the
 * length of a side meeting there; the 6 resulting endpoints lie on a
 * common circle centred at the incentre, with radius sqrt(r² + s²)
 * (r = inradius, s = semiperimeter).
 */
export function conwayCircleOf(A, B, C) {
  const inc = incircleOf(A, B, C);
  if (!inc) return null;
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  const s = (a + b + c) / 2;
  return { x: inc.x, y: inc.y, r: Math.hypot(inc.r, s) };
}

/**
 * Orthocentroidal circle: the circle with diameter GH, where G is the
 * centroid and H is the orthocentre. Notable for containing every one of
 * a triangle's classical centres located on the Euler line between the
 * nine-point centre and G (with some famous exceptions like I).
 */
export function orthocentroidalCircleOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  const gx = (A.x + B.x + C.x) / 3, gy = (A.y + B.y + C.y) / 3;
  const hx = A.x + B.x + C.x - 2 * circ.x, hy = A.y + B.y + C.y - 2 * circ.y;
  return { x: (gx + hx) / 2, y: (gy + hy) / 2, r: Math.hypot(gx - hx, gy - hy) / 2 };
}

/**
 * Tangential triangle circle: the circumcircle of the tangential triangle
 * -- the triangle formed by the 3 lines tangent to the circumcircle at
 * A, B, and C. Each tangent line is the polar of its vertex with respect
 * to the circumcircle: (X - O)·(P - O) = R².
 */
export function tangentialTriangleCircleOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  const O = { x: circ.x, y: circ.y }, R = circ.r;

  function tangentCoeffs(P) {
    const a = P.x - O.x, b = P.y - O.y;
    const c = R * R + a * O.x + b * O.y;
    return { a, b, c }; // a*x + b*y = c
  }
  function intersect(L1, L2) {
    const det = L1.a * L2.b - L2.a * L1.b;
    if (Math.abs(det) < 1e-9) return null; // parallel tangents: degenerate
    return {
      x: (L1.c * L2.b - L2.c * L1.b) / det,
      y: (L1.a * L2.c - L2.a * L1.c) / det,
    };
  }

  const tA = tangentCoeffs(A), tB = tangentCoeffs(B), tC = tangentCoeffs(C);
  const TA = intersect(tB, tC), TB = intersect(tC, tA), TC = intersect(tA, tB);
  if (!TA || !TB || !TC) return null;
  return circumcircleOf(TA, TB, TC);
}

/**
 * Bevan circle: the circumcircle of the excentral triangle (I_A, I_B,
 * I_C, the 3 excentres). Its centre is the Bevan point -- the reflection
 * of the incentre over the circumcentre -- and its radius is exactly 2R.
 */
export function bevanCircleOf(A, B, C) {
  const ex = excirclesOf(A, B, C);
  if (!ex[0] || !ex[1] || !ex[2]) return null;
  return circumcircleOf(ex[0], ex[1], ex[2]);
}

/**
 * Incentral triangle circle: the circumcircle of the incentral triangle
 * -- the 3 feet of the internal angle bisectors (each divides the
 * opposite side in the ratio of the two adjacent sides).
 */
export function incentralTriangleCircleOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  if (a < 1e-9 || b < 1e-9 || c < 1e-9) return null;
  const D = { x: (b * B.x + c * C.x) / (b + c), y: (b * B.y + c * C.y) / (b + c) }; // bisector foot on BC
  const E = { x: (c * C.x + a * A.x) / (c + a), y: (c * C.y + a * A.y) / (c + a) }; // bisector foot on CA
  const F = { x: (a * A.x + b * B.x) / (a + b), y: (a * A.y + b * B.y) / (a + b) }; // bisector foot on AB
  return circumcircleOf(D, E, F);
}

/**
 * Johnson circles: reflecting the circumcircle across each side gives 3
 * circles, all of the same radius R, each passing through 2 vertices and
 * the orthocentre H (a classical, easily-verified reflection fact).
 */
export function johnsonCirclesOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  const O = { x: circ.x, y: circ.y }, R = circ.r;

  function reflectOverLine(X, P, Q) {
    const dx = Q.x - P.x, dy = Q.y - P.y;
    const lenSq = dx * dx + dy * dy;
    if (lenSq < 1e-12) return { x: X.x, y: X.y };
    const t = ((X.x - P.x) * dx + (X.y - P.y) * dy) / lenSq;
    const px = P.x + t * dx, py = P.y + t * dy;
    return { x: 2 * px - X.x, y: 2 * py - X.y };
  }

  const OA = reflectOverLine(O, B, C);
  const OB = reflectOverLine(O, C, A);
  const OC = reflectOverLine(O, A, B);
  return [
    { x: OA.x, y: OA.y, r: R },
    { x: OB.x, y: OB.y, r: R },
    { x: OC.x, y: OC.y, r: R },
  ];
}

/** Generic line through point P with direction d, as a·x + b·y = c. */
function lineCoeffsPD(P, d) {
  const a = d.y, b = -d.x;
  return { a, b, c: a * P.x + b * P.y };
}
/** Intersection of two a·x+b·y=c lines, or null if parallel. */
function intersectLines(L1, L2) {
  const det = L1.a * L2.b - L2.a * L1.b;
  if (Math.abs(det) < 1e-9) return null;
  return {
    x: (L1.c * L2.b - L2.c * L1.b) / det,
    y: (L1.a * L2.c - L2.a * L1.c) / det,
  };
}
/** Foot of the perpendicular from X onto the INFINITE line through P, Q. */
function projectOntoLine(X, P, Q) {
  const dx = Q.x - P.x, dy = Q.y - P.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq < 1e-12) return { x: P.x, y: P.y };
  const t = ((X.x - P.x) * dx + (X.y - P.y) * dy) / lenSq;
  return { x: P.x + t * dx, y: P.y + t * dy };
}

/**
 * First Lemoine circle: through the symmedian point K, draw a line
 * parallel to each side; each meets the OTHER two sides, giving 6 points
 * that are classically concyclic. Constructed directly (parallels +
 * intersections), not from a memorised centre/radius formula.
 */
export function firstLemoineCircleOf(A, B, C) {
  const K = symmedianPointOf(A, B, C);
  if (!K) return null;

  const lineAB = lineCoeffsPD(A, { x: B.x - A.x, y: B.y - A.y });
  const lineAC = lineCoeffsPD(A, { x: C.x - A.x, y: C.y - A.y });
  const lineBC = lineCoeffsPD(B, { x: C.x - B.x, y: C.y - B.y });

  const parBC = lineCoeffsPD(K, { x: C.x - B.x, y: C.y - B.y }); // through K // BC
  const parCA = lineCoeffsPD(K, { x: A.x - C.x, y: A.y - C.y }); // through K // CA

  const P1 = intersectLines(parBC, lineAB); // on AB
  const P2 = intersectLines(parBC, lineAC); // on AC
  const P4 = intersectLines(parCA, lineBC); // on BC
  if (!P1 || !P2 || !P4) return null;
  return circumcircleOf(P1, P2, P4);
}

/**
 * Taylor circle: drop the 3 altitude feet, then project each foot
 * perpendicularly onto the OTHER two sides (6 points total); these are
 * classically concyclic. Constructed directly via perpendicular
 * projections, not a memorised formula.
 */
export function taylorCircleOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  const Ha = projectOntoLine(A, B, C); // altitude foot from A, on BC
  const Hb = projectOntoLine(B, C, A); // altitude foot from B, on CA
  const Hc = projectOntoLine(C, A, B); // altitude foot from C, on AB

  const P1 = projectOntoLine(Hb, B, C);
  const P2 = projectOntoLine(Hc, B, C);
  const P4 = projectOntoLine(Ha, C, A);
  return circumcircleOf(P1, P2, P4);
}

// ---------------------------------------------------------------------------
// Triangle-centre POINTS (as opposed to the circles above). Each returns a
// plain {x, y}, or null when undefined for a degenerate/special triangle.
// ---------------------------------------------------------------------------

/** Incentre X(1): weighted by opposite side lengths a, b, c. */
export function incenterOf(A, B, C) {
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  const perim = a + b + c;
  if (perim < 1e-9) return null;
  return { x: (a * A.x + b * B.x + c * C.x) / perim, y: (a * A.y + b * B.y + c * C.y) / perim };
}

/** Centroid X(2): the average of the 3 vertices. */
export function centroidOf(A, B, C) {
  return { x: (A.x + B.x + C.x) / 3, y: (A.y + B.y + C.y) / 3 };
}

/** Circumcentre X(3): equidistant from all 3 vertices. */
export function circumcenterOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  return circ ? { x: circ.x, y: circ.y } : null;
}

/** Orthocentre X(4): H = A + B + C - 2 * circumcentre. */
export function orthocenterOf(A, B, C) {
  const circ = circumcircleOf(A, B, C);
  if (!circ) return null;
  return { x: A.x + B.x + C.x - 2 * circ.x, y: A.y + B.y + C.y - 2 * circ.y };
}

/** Nine-point centre X(5): midpoint of the circumcentre and orthocentre. */
export function ninePointCenterOf(A, B, C) {
  const npc = ninePointCircleOf(A, B, C);
  return npc ? { x: npc.x, y: npc.y } : null;
}

/** Symmedian point X(6): barycentric a² : b² : c². */
export function symmedianPointOf(A, B, C) {
  const a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2;
  const b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2;
  const c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2;
  const wsum = a2 + b2 + c2;
  if (wsum < 1e-9) return null;
  return { x: (a2 * A.x + b2 * B.x + c2 * C.x) / wsum, y: (a2 * A.y + b2 * B.y + c2 * C.y) / wsum };
}

/** Spieker centre X(10): incentre of the medial triangle. */
export function spiekerCenterOf(A, B, C) {
  const sp = spiekerCircleOf(A, B, C);
  return sp ? { x: sp.x, y: sp.y } : null;
}

// ---------------------------------------------------------------------------
// ANY verified Kimberling center X(n), computed in the browser from its
// barycentric formula so it stays LIVE when the triangle is dragged.
// The formulas come from the server (GET /api/center-formulas, see
// routes/etc_formulas_api.py) as small JavaScript array expressions that the
// server generated from a whitelisted AST; loadEtcFormulas() compiles them
// once into the ETC_FORMULAS registry (id -> {name, fn}).
// ---------------------------------------------------------------------------
export const ETC_FORMULAS = new Map();

const _sec = (x) => 1 / Math.cos(x);
const _csc = (x) => 1 / Math.sin(x);
const _cot = (x) => 1 / Math.tan(x);
const _mod = (x, y) => ((x % y) + y) % y;

/** Fetch and compile the server's formulas. Resolves to how many loaded. */
export async function loadEtcFormulas(url = '/api/center-formulas') {
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok || data.status !== 'ok') return ETC_FORMULAS.size;
    for (const c of data.centers) {
      // Belt and braces: the server already whitelists, but never compile
      // anything that is not plain arithmetic + identifiers.
      if (!/^[0-9A-Za-z_+\-*/().,\s\[\]]*$/.test(c.js)) continue;
      try {
        const raw = new Function('a', 'b', 'c', 'A', 'B', 'C',
          'sqrt', 'sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'pi', 'pow', 'mod',
          'return ' + c.js + ';');
        ETC_FORMULAS.set(c.id, {
          name: c.name,
          fn: (a, b, cc, A, B, C) => raw(a, b, cc, A, B, C,
            Math.sqrt, Math.sin, Math.cos, Math.tan, _sec, _csc, _cot, Math.PI, Math.pow, _mod),
        });
      } catch { /* skip a formula that does not compile */ }
    }
  } catch { /* server offline: the X(n) tool simply stays unavailable */ }
  return ETC_FORMULAS.size;
}

/** Position of X(id) for triangle ABC, or null if it is undefined here
 *  (unknown id, degenerate triangle, division by zero, or at infinity). */
export function etcCenterOf(A, B, C, id) {
  const entry = ETC_FORMULAS.get(id);
  if (!entry || !isValidTriangle(A, B, C)) return null;
  const a = Math.hypot(B.x - C.x, B.y - C.y);
  const b = Math.hypot(C.x - A.x, C.y - A.y);
  const c = Math.hypot(A.x - B.x, A.y - B.y);
  if (a < 1e-9 || b < 1e-9 || c < 1e-9) return null;
  const clamp = (v) => Math.max(-1, Math.min(1, v));
  const angA = Math.acos(clamp((b * b + c * c - a * a) / (2 * b * c)));
  const angB = Math.acos(clamp((a * a + c * c - b * b) / (2 * a * c)));
  const angC = Math.PI - angA - angB;
  let w;
  try { w = entry.fn(a, b, c, angA, angB, angC); } catch { return null; }
  if (!Array.isArray(w) || w.length !== 3 || !w.every(Number.isFinite)) return null;
  const sum = w[0] + w[1] + w[2];
  const mag = Math.abs(w[0]) + Math.abs(w[1]) + Math.abs(w[2]);
  if (!Number.isFinite(sum) || Math.abs(sum) <= 1e-12 * mag) return null;
  const x = (w[0] * A.x + w[1] * B.x + w[2] * C.x) / sum;
  const y = (w[0] * A.y + w[1] * B.y + w[2] * C.y) / sum;
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

// ---------------------------------------------------------------------------
// Formula registries -- map a stable string name (stored in DerivedCircle /
// DerivedPoint, and serialised to JSON) to the actual formula function.
// Used by both the tools (to build a DerivedCircle/DerivedPoint) and by
// Scene.fromJSON (to re-look-up the function after a save/load round trip,
// since functions themselves can't survive JSON).
// ---------------------------------------------------------------------------
export const DERIVED_CIRCLE_FORMULAS = {
  circumcircle: circumcircleOf,
  incircle: incircleOf,
  ninepoint: ninePointCircleOf,
  excircles: excirclesOf,
  spieker: spiekerCircleOf,
  brocard: brocardCircleOf,
  mandart: mandartCircleOf,
  apollonius: apolloniusCirclesOf,
  conway: conwayCircleOf,
  orthocentroidal: orthocentroidalCircleOf,
  tangentialtriangle: tangentialTriangleCircleOf,
  bevan: bevanCircleOf,
  incentraltriangle: incentralTriangleCircleOf,
  johnson: johnsonCirclesOf,
  lemoine: firstLemoineCircleOf,
  taylor: taylorCircleOf,
};

export const DERIVED_POINT_FORMULAS = {
  incenter: incenterOf,
  centroid: centroidOf,
  circumcenter: circumcenterOf,
  orthocenter: orthocenterOf,
  ninepointcenter: ninePointCenterOf,
  symmedian: symmedianPointOf,
  spiekercenter: spiekerCenterOf,
};

/**
 * Short centre-label per circle formula, used to auto-label a
 * DerivedCircle's centre point (see tools.js's addDerivedCircle). Array
 * formulas (excircles/apollonius/johnson) give one label per index
 * (0=A, 1=B, 2=C); everything else is a single string.
 */
export const DERIVED_CIRCLE_CENTER_LABELS = {
  circumcircle: 'O',
  incircle: 'I',
  ninepoint: 'N',
  excircles: ['I_A', 'I_B', 'I_C'],
  spieker: 'Sp',
  brocard: 'Mid(O,K)',
  mandart: 'Ma',
  apollonius: ['Ap_A', 'Ap_B', 'Ap_C'],
  conway: 'I',
  orthocentroidal: 'Mid(G,H)',
  tangentialtriangle: 'O\u2032',
  bevan: 'Be',
  incentraltriangle: 'O\u2033',
  johnson: ['J_A', 'J_B', 'J_C'],
  lemoine: 'Le',
  taylor: 'Ty',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function distToSegment(p, a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-24) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

// ---------------------------------------------------------------------------
// Exact intersections. Used to snap a newly placed point onto the precise
// crossing of two objects (line/segment/polygon edge/circle/semicircle),
// instead of wherever the mouse happened to land.
// ---------------------------------------------------------------------------

/** Break an object into simple curves: straight pieces {kind:'line', a, b,
 *  bounded} and circles {kind:'circle', c, r, keep?}. `keep(p)` (optional)
 *  restricts a circle to part of its circumference (semicircles). */
function curvesOf(o) {
  switch (o.type) {
    case 'line':    return [{ kind: 'line', a: o.p1, b: o.p2, bounded: false }];
    case 'segment': return [{ kind: 'line', a: o.p1, b: o.p2, bounded: true }];
    case 'polygon': {
      const v = o.vertices, out = [];
      for (let i = 0; i < v.length; i++) {
        out.push({ kind: 'line', a: v[i], b: v[(i + 1) % v.length], bounded: true });
      }
      return out;
    }
    case 'circle':
      return [{ kind: 'circle', c: o.center, r: o.radius() }];
    case 'derivedCircle':
      return o.isValid() ? [{ kind: 'circle', c: o.center, r: o.radius() }] : [];
    case 'semicircle': {
      const c = o.center(), r = o.radius(), flip = o.flip;
      const dx = o.p2.x - o.p1.x, dy = o.p2.y - o.p1.y;
      const eps = 1e-9 * (r * r + 1);
      // Side of the diameter the arc bulges to (matches view.js drawing).
      const keep = (p) => {
        const s = dx * (p.y - c.y) - dy * (p.x - c.x);
        return flip ? s <= eps : s >= -eps;
      };
      return [
        { kind: 'circle', c, r, keep },
        { kind: 'line', a: o.p1, b: o.p2, bounded: true },
      ];
    }
    case 'ellipse': {
      const g = o._geom();
      return g ? [{ kind: 'ellipse', g }] : [];
    }
    default: return [];
  }
}

function crossLineLine(l1, l2) {
  const d1x = l1.b.x - l1.a.x, d1y = l1.b.y - l1.a.y;
  const d2x = l2.b.x - l2.a.x, d2y = l2.b.y - l2.a.y;
  const det = d1x * d2y - d1y * d2x;
  const scale = Math.hypot(d1x, d1y) * Math.hypot(d2x, d2y);
  if (scale < 1e-18 || Math.abs(det) < 1e-12 * scale) return []; // parallel / degenerate
  const ex = l2.a.x - l1.a.x, ey = l2.a.y - l1.a.y;
  const t = (ex * d2y - ey * d2x) / det;
  const u = (ex * d1y - ey * d1x) / det;
  const eps = 1e-9;
  if (l1.bounded && (t < -eps || t > 1 + eps)) return [];
  if (l2.bounded && (u < -eps || u > 1 + eps)) return [];
  return [{ x: l1.a.x + t * d1x, y: l1.a.y + t * d1y }];
}

function crossLineCircle(l, ci) {
  const dx = l.b.x - l.a.x, dy = l.b.y - l.a.y;
  const A = dx * dx + dy * dy;
  if (A < 1e-18) return [];
  const fx = l.a.x - ci.c.x, fy = l.a.y - ci.c.y;
  const B = 2 * (fx * dx + fy * dy);
  const C = fx * fx + fy * fy - ci.r * ci.r;
  let disc = B * B - 4 * A * C;
  const tol = 1e-9 * (B * B + Math.abs(4 * A * C) + 1e-300);
  if (disc < -tol) return [];
  disc = Math.sqrt(Math.max(0, disc));
  const ts = disc === 0 ? [-B / (2 * A)] : [(-B - disc) / (2 * A), (-B + disc) / (2 * A)];
  const out = [];
  for (const t of ts) {
    if (l.bounded && (t < -1e-9 || t > 1 + 1e-9)) continue;
    out.push({ x: l.a.x + t * dx, y: l.a.y + t * dy });
  }
  return out;
}

function crossCircleCircle(c1, c2) {
  const dx = c2.c.x - c1.c.x, dy = c2.c.y - c1.c.y;
  const d = Math.hypot(dx, dy);
  if (d < 1e-12) return []; // concentric
  const eps = 1e-9 * (c1.r + c2.r + 1);
  if (d > c1.r + c2.r + eps || d < Math.abs(c1.r - c2.r) - eps) return [];
  const a = (c1.r * c1.r - c2.r * c2.r + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, c1.r * c1.r - a * a));
  const mx = c1.c.x + a * dx / d, my = c1.c.y + a * dy / d;
  if (h === 0) return [{ x: mx, y: my }];
  return [
    { x: mx + h * dy / d, y: my - h * dx / d },
    { x: mx - h * dy / d, y: my + h * dx / d },
  ];
}

// ---------------------------------------------------------------------------
// Ellipse crossings. A line meets an ellipse in at most 2 points (a quadratic
// in the line parameter, solved exactly like line-circle). An ellipse against
// a circle or another ellipse has no simple closed form, so the crossings are
// found numerically: walk once round the ellipse, watch the other curve's
// implicit equation change sign, and bisect each sign change down to ~1e-15.
// (A curve that only touches without crossing, i.e. exact tangency between two
// round curves, is not reported.)
// ---------------------------------------------------------------------------
function crossLineEllipse(l, ci) {
  const g = ci.g;
  const p0 = ellipseLocal(g, l.a), p1 = ellipseLocal(g, l.b);
  const du = p1.u - p0.u, dv = p1.v - p0.v;
  const ia2 = 1 / (g.a * g.a), ib2 = 1 / (g.b * g.b);
  const A = du * du * ia2 + dv * dv * ib2;
  if (A < 1e-18) return [];
  const B = 2 * (p0.u * du * ia2 + p0.v * dv * ib2);
  const C = p0.u * p0.u * ia2 + p0.v * p0.v * ib2 - 1;
  let disc = B * B - 4 * A * C;
  const tol = 1e-9 * (B * B + Math.abs(4 * A * C) + 1e-300);
  if (disc < -tol) return [];
  disc = Math.sqrt(Math.max(0, disc));
  const ts = disc === 0 ? [-B / (2 * A)] : [(-B - disc) / (2 * A), (-B + disc) / (2 * A)];
  const dx = l.b.x - l.a.x, dy = l.b.y - l.a.y;
  const out = [];
  for (const t of ts) {
    if (l.bounded && (t < -1e-9 || t > 1 + 1e-9)) continue;
    out.push({ x: l.a.x + t * dx, y: l.a.y + t * dy });
  }
  return out;
}

/** f(x, y) of a circle or ellipse curve: zero on the curve, sign flips across it. */
function implicitOf(c) {
  if (c.kind === 'circle') {
    return (x, y) => (x - c.c.x) ** 2 + (y - c.c.y) ** 2 - c.r * c.r;
  }
  const g = c.g, ia2 = 1 / (g.a * g.a), ib2 = 1 / (g.b * g.b);
  return (x, y) => {
    const q = ellipseLocal(g, { x, y });
    return q.u * q.u * ia2 + q.v * q.v * ib2 - 1;
  };
}

function crossEllipseImplicit(ell, other) {
  const g = ell.g, f = implicitOf(other);
  const val = (t) => { const p = ellipsePointAt(g, t); return f(p.x, p.y); };
  const N = 720, step = 2 * Math.PI / N;
  const out = [];
  const first = val(0);
  if (first === 0) out.push(ellipsePointAt(g, 0));
  let t0 = 0, f0 = first;
  for (let i = 1; i <= N; i++) {
    const t1 = i * step;
    const f1 = i === N ? first : val(t1);
    if (f0 !== 0) {
      if (f1 === 0) {
        if (i < N) out.push(ellipsePointAt(g, t1));
      } else if ((f0 < 0) !== (f1 < 0)) {
        let lo = t0, hi = t1;
        const flo = f0;
        for (let k = 0; k < 60; k++) {
          const mid = (lo + hi) / 2;
          if ((val(mid) < 0) === (flo < 0)) lo = mid; else hi = mid;
        }
        out.push(ellipsePointAt(g, (lo + hi) / 2));
      }
    }
    t0 = t1; f0 = f1;
  }
  return out;
}

/** Crossings of an ellipse curve (c1 or c2, or both) with a line, circle or ellipse curve. */
function crossEllipse(c1, c2) {
  const e = c1.kind === 'ellipse' ? c1 : c2;
  const o = c1.kind === 'ellipse' ? c2 : c1;
  return o.kind === 'line' ? crossLineEllipse(o, e) : crossEllipseImplicit(e, o);
}

function intersectCurves(c1, c2) {
  let pts;
  if (c1.kind === 'ellipse' || c2.kind === 'ellipse') pts = crossEllipse(c1, c2);
  else if (c1.kind === 'line' && c2.kind === 'line') pts = crossLineLine(c1, c2);
  else if (c1.kind === 'line') pts = crossLineCircle(c1, c2);
  else if (c2.kind === 'line') pts = crossLineCircle(c2, c1);
  else pts = crossCircleCircle(c1, c2);
  return pts.filter(p => (!c1.keep || c1.keep(p)) && (!c2.keep || c2.keep(p)));
}

/** All exact intersection points of two scene objects (array of {x, y}). */
export function intersectionsOf(o1, o2) {
  const out = [];
  for (const c1 of curvesOf(o1)) {
    for (const c2 of curvesOf(o2)) out.push(...intersectCurves(c1, c2));
  }
  return out;
}

/**
 * IntersectionPoint: a LIVE point sitting on the crossing of two shapes
 * (line / segment / polygon / circle / semicircle / derived circle). It
 * stores the two shapes, not coordinates, and recomputes its position from
 * them every time it is read -- so when either shape moves (a point of it
 * is dragged, or the whole figure is scaled) the intersection follows
 * automatically, exactly like a Segment follows its endpoints.
 *
 * Two circles (or a line and a circle) cross in TWO places, so it remembers
 * its last position and always picks the crossing nearest to it; that keeps
 * it on the same branch while shapes are dragged. If the shapes stop
 * touching it is hidden (isValid() false) and reappears when they cross.
 */
export class IntersectionPoint extends GeoObject {
  constructor(o1, o2, x, y) {
    super('intersectionPoint');
    this.o1 = o1;
    this.o2 = o2;
    this._lx = x; // last known position (picks the right crossing)
    this._ly = y;
    this.color = '#b3541e';
  }
  dependencies() { return [this.o1, this.o2]; }
  _compute() {
    const pts = intersectionsOf(this.o1, this.o2);
    if (!pts.length) return null;
    let best = pts[0], bd = Infinity;
    for (const p of pts) {
      const d = Math.hypot(p.x - this._lx, p.y - this._ly);
      if (d < bd) { bd = d; best = p; }
    }
    this._lx = best.x;
    this._ly = best.y;
    return best;
  }
  get x() { const p = this._compute(); return p ? p.x : this._lx; }
  get y() { const p = this._compute(); return p ? p.y : this._ly; }
  isValid() { return this._compute() !== null; }
  distanceTo(p) {
    const c = this._compute();
    if (!c) return Infinity;
    return Math.hypot(c.x - p.x, c.y - p.y);
  }
  toJSON() {
    this._compute(); // refresh the remembered position before saving
    return { id: this.id, type: 'intersectionPoint', o1: this.o1.id, o2: this.o2.id,
             x: this._lx, y: this._ly,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

// ---------------------------------------------------------------------------
// ConstructedPoint: a LIVE point defined by a rule on other points, so it
// follows them whenever they move (Midpoint, the helper points behind the
// Perpendicular / Angle-bisector lines, and the apex of an isosceles or
// equilateral triangle). Like DerivedPoint it has no coordinates of its own:
// x / y are recomputed from `refs` every time they are read.
//
//   kind 'midpoint'  refs [P, Q]          halfway between P and Q
//   kind 'perp'      refs [P, B1, B2]     P + 1 unit, perpendicular to B1->B2
//   kind 'bisector'  refs [P1, V, P3]     V + 1 unit along the bisector of angle P1-V-P3
//   kind 'parallel'  refs [P, B1, B2]     P + 1 unit, parallel to B1->B2
//   kind 'offset'    refs [P, B1, B2]     P + k * (B1->B2 turned 90 degrees left), so the
//                                         offset is k times the length of B1B2 (k < 0 = right
//                                         side). Square / rectangle corner; `free` = draggable.
//   kind 'parallelogram' refs [A, B, C]   A + C - B, the 4th corner of a parallelogram
//   kind 'apex'      refs [P, Q]          on the perpendicular bisector of PQ, at
//                                         height k * |PQ| (k < 0 = other side).
//                                         `free` apexes can be dragged along it.
// ---------------------------------------------------------------------------
export const APEX_ISO_K = Math.sqrt(0.9 * 0.9 - 0.25); // fresh isosceles: legs = 0.9 x base
export const APEX_EQUI_K = Math.sqrt(3) / 2;            // equilateral

function bisectorDir(p1, vertex, p3) {
  const v1x = p1.x - vertex.x, v1y = p1.y - vertex.y;
  const v2x = p3.x - vertex.x, v2y = p3.y - vertex.y;
  const len1 = Math.hypot(v1x, v1y), len2 = Math.hypot(v2x, v2y);
  if (len1 < 1e-12 || len2 < 1e-12) return null;
  const dx = v1x / len1 + v2x / len2, dy = v1y / len1 + v2y / len2;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return { x: -v1y / len1, y: v1x / len1 }; // straight angle: perpendicular
  return { x: dx / len, y: dy / len };
}

export class ConstructedPoint extends GeoObject {
  constructor(kind, refs, opts = {}) {
    super('constructedPoint');
    this.kind = kind;
    this.refs = refs;
    this.k = opts.k ?? (kind === 'apex' ? APEX_ISO_K : kind === 'offset' ? 1 : undefined);
    this.free = !!opts.free;
    this.color = '#2f7d5a';
    if (opts.helper) this.labelVisible = false; // construction point, not worth labelling
    this._lx = 0; // last good position (used while the rule is degenerate)
    this._ly = 0;
    this._compute();
  }
  dependencies() { return [...this.refs]; }
  _compute() {
    const r = this.refs;
    let out = null;
    switch (this.kind) {
      case 'midpoint':
        out = { x: (r[0].x + r[1].x) / 2, y: (r[0].y + r[1].y) / 2 };
        break;
      case 'perp': {
        const dx = r[2].x - r[1].x, dy = r[2].y - r[1].y, len = Math.hypot(dx, dy);
        if (len > 1e-9) out = { x: r[0].x - dy / len, y: r[0].y + dx / len };
        break;
      }
      case 'parallel': {
        // P + 1 unit in the direction B1 -> B2, so the line through P and this point is parallel to B1B2.
        const dx = r[2].x - r[1].x, dy = r[2].y - r[1].y, len = Math.hypot(dx, dy);
        if (len > 1e-9) out = { x: r[0].x + dx / len, y: r[0].y + dy / len };
        break;
      }
      case 'bisector': {
        const d = bisectorDir(r[0], r[1], r[2]);
        if (d) out = { x: r[1].x + d.x, y: r[1].y + d.y };
        break;
      }
      case 'offset': {
        const dx = r[2].x - r[1].x, dy = r[2].y - r[1].y;
        if (Math.hypot(dx, dy) > 1e-9) out = { x: r[0].x - dy * this.k, y: r[0].y + dx * this.k };
        break;
      }
      case 'parallelogram':
        out = { x: r[0].x + r[2].x - r[1].x, y: r[0].y + r[2].y - r[1].y };
        break;
      case 'apex': {
        const dx = r[1].x - r[0].x, dy = r[1].y - r[0].y;
        if (Math.hypot(dx, dy) > 1e-9) {
          out = { x: (r[0].x + r[1].x) / 2 - dy * this.k, y: (r[0].y + r[1].y) / 2 + dx * this.k };
        }
        break;
      }
    }
    if (out) { this._lx = out.x; this._ly = out.y; }
    return out;
  }
  get x() { const p = this._compute(); return p ? p.x : this._lx; }
  get y() { const p = this._compute(); return p ? p.y : this._ly; }
  isValid() { return this._compute() !== null; }
  /** Only a free apex can be dragged (along the bisector, changing its height). */
  draggable() { return (this.kind === 'apex' || this.kind === 'offset') && this.free; }
  dragTo(wx, wy) {
    if (!this.draggable()) return;
    if (this.kind === 'offset') {
      // refs [P, B1, B2]: slide along the perpendicular through P, which just changes k.
      const [a, b1, b2] = this.refs;
      const bx = b2.x - b1.x, by = b2.y - b1.y, len2 = bx * bx + by * by;
      if (len2 < 1e-18) return;
      this.k = ((wx - a.x) * -by + (wy - a.y) * bx) / len2;
      return;
    }
    const [p, q] = this.refs;
    const dx = q.x - p.x, dy = q.y - p.y, len2 = dx * dx + dy * dy;
    if (len2 < 1e-18) return;
    const mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2;
    this.k = ((wx - mx) * -dy + (wy - my) * dx) / len2;
  }
  distanceTo(p) {
    const c = this._compute();
    if (!c) return Infinity;
    return Math.hypot(c.x - p.x, c.y - p.y);
  }
  toJSON() {
    this._compute();
    return { id: this.id, type: 'constructedPoint', kind: this.kind,
             refs: this.refs.map(o => o.id), k: this.k, free: this.free,
             x: this._lx, y: this._ly,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

// ---------------------------------------------------------------------------
// GliderPoint: a point that lives ON a shape (line, segment, circle, derived
// circle, semicircle, polygon edge) and stays on it when the shape moves.
// It stores the shape plus one parameter `t`, never coordinates:
//   line / segment  t = fraction along p1 -> p2 (a segment clamps to 0..1)
//   circle-like     t = angle, measured from a reference direction that turns
//                   with the circle (towards `through`, towards vertex A of a
//                   triangle circle, or along a semicircle's diameter)
//   polygon         t = edge index + fraction along that edge
// Dragging it with the Move tool slides it along the shape.
// ---------------------------------------------------------------------------
const TWO_PI = Math.PI * 2;
const wrapAngle = (a) => ((a + Math.PI) % TWO_PI + TWO_PI) % TWO_PI - Math.PI; // [-PI, PI)
const clamp01 = (t) => Math.max(0, Math.min(1, t));

function circleInfo(h) {
  if (h.type === 'circle') return { c: h.center, r: h.radius() };
  if (h.type === 'derivedCircle') return h.isValid() ? { c: h.center, r: h.radius() } : null;
  if (h.type === 'semicircle') return { c: h.center(), r: h.radius() };
  return null;
}

function hostRefAngle(h, c) {
  if (h.type === 'circle') return Math.atan2(h.through.y - c.y, h.through.x - c.x);
  if (h.type === 'derivedCircle') return Math.atan2(h.A.y - c.y, h.A.x - c.x);
  if (h.type === 'semicircle') return h.diameterAngle();
  return 0;
}

/** Where parameter t lies on host h, or null if h is not a valid host right now. */
function hostPointAt(h, t) {
  switch (h.type) {
    case 'line':
    case 'segment': {
      const u = h.type === 'segment' ? clamp01(t) : t;
      return { x: h.p1.x + u * (h.p2.x - h.p1.x), y: h.p1.y + u * (h.p2.y - h.p1.y) };
    }
    case 'circle':
    case 'derivedCircle':
    case 'semicircle': {
      const ci = circleInfo(h);
      if (!ci) return null;
      const a = hostRefAngle(h, ci.c) + t;
      return { x: ci.c.x + ci.r * Math.cos(a), y: ci.c.y + ci.r * Math.sin(a) };
    }
    case 'ellipse': {
      const g = h._geom();
      return g ? ellipsePointAt(g, t) : null;
    }
    case 'polygon': {
      const v = h.vertices, n = v.length;
      const u = ((t % n) + n) % n, i = Math.floor(u), f = u - i;
      const a = v[i], b = v[(i + 1) % n];
      return { x: a.x + f * (b.x - a.x), y: a.y + f * (b.y - a.y) };
    }
    default: return null;
  }
}

/** Parameter of the point on host h closest to world point w (null if h is not a host). */
function hostParamAt(h, w) {
  switch (h.type) {
    case 'line':
    case 'segment': {
      const dx = h.p2.x - h.p1.x, dy = h.p2.y - h.p1.y, len2 = dx * dx + dy * dy;
      if (len2 < 1e-24) return null;
      const t = ((w.x - h.p1.x) * dx + (w.y - h.p1.y) * dy) / len2;
      return h.type === 'segment' ? clamp01(t) : t;
    }
    case 'circle':
    case 'derivedCircle':
    case 'semicircle': {
      const ci = circleInfo(h);
      if (!ci) return null;
      let t = wrapAngle(Math.atan2(w.y - ci.c.y, w.x - ci.c.x) - hostRefAngle(h, ci.c));
      if (h.type === 'semicircle') {
        // stay on the drawn half: [0, PI] normally, [-PI, 0] when flipped
        if (!h.flip && t < 0) t = t < -Math.PI / 2 ? Math.PI : 0;
        else if (h.flip && t > 0) t = t > Math.PI / 2 ? -Math.PI : 0;
      }
      return t;
    }
    case 'ellipse': {
      const g = h._geom();
      return g ? ellipseNearestParam(g, w) : null;
    }
    case 'polygon': {
      const v = h.vertices, n = v.length;
      let best = null, bd = Infinity;
      for (let i = 0; i < n; i++) {
        const a = v[i], b = v[(i + 1) % n];
        const dx = b.x - a.x, dy = b.y - a.y, len2 = dx * dx + dy * dy;
        const f = len2 < 1e-24 ? 0 : clamp01(((w.x - a.x) * dx + (w.y - a.y) * dy) / len2);
        const d = Math.hypot(w.x - (a.x + f * dx), w.y - (a.y + f * dy));
        if (d < bd) { bd = d; best = i + f; }
      }
      return best;
    }
    default: return null;
  }
}

export class GliderPoint extends GeoObject {
  constructor(host, t) {
    super('glider');
    this.host = host;
    this.t = t;
    this.color = '#b3541e';
    this._lx = 0;
    this._ly = 0;
    this._compute();
  }
  dependencies() { return [this.host]; }
  _compute() {
    const p = hostPointAt(this.host, this.t);
    if (p) { this._lx = p.x; this._ly = p.y; }
    return p;
  }
  get x() { const p = this._compute(); return p ? p.x : this._lx; }
  get y() { const p = this._compute(); return p ? p.y : this._ly; }
  isValid() { return this._compute() !== null; }
  draggable() { return true; }
  dragTo(wx, wy) {
    const t = hostParamAt(this.host, { x: wx, y: wy });
    if (t !== null) this.t = t;
  }
  distanceTo(p) {
    const c = this._compute();
    if (!c) return Infinity;
    return Math.hypot(c.x - p.x, c.y - p.y);
  }
  toJSON() {
    this._compute();
    return { id: this.id, type: 'glider', host: this.host.id, t: this.t,
             x: this._lx, y: this._ly,
             label: this.label, visible: this.visible,
             labelVisible: this.labelVisible, color: this.color };
  }
}

// Fields of a serialised object that hold ids of other objects.
const REF_FIELDS = ['p1', 'p2', 'vertex', 'p3', 'center', 'through', 'f1', 'f2', 'A', 'B', 'C', 'o1', 'o2', 'host'];
function refIdsOf(d) {
  const ids = [];
  for (const k of REF_FIELDS) if (d[k] !== undefined && d[k] !== null) ids.push(d[k]);
  if (Array.isArray(d.vertices)) ids.push(...d.vertices);
  if (Array.isArray(d.refs)) ids.push(...d.refs);
  return ids;
}

/**
 * Reorder serialised objects so everything an object refers to comes before
 * it. Needed because an IntersectionPoint depends on shapes, while shapes
 * (segments, circles, ...) may in turn be built on that intersection point.
 * Keeps the incoming order wherever dependencies allow.
 */
function dependencyOrder(list) {
  const present = new Set(list.map(d => d.id));
  const done = new Set();
  const out = [];
  let rest = list.slice();
  while (rest.length) {
    const next = [];
    let progressed = false;
    for (const d of rest) {
      if (refIdsOf(d).every(id => done.has(id) || !present.has(id))) {
        out.push(d); done.add(d.id); progressed = true;
      } else next.push(d);
    }
    if (!progressed) { out.push(...next); break; } // cycle / bad data: keep the rest as-is
    rest = next;
  }
  return out;
}

/** "A", "B", ... "Z", "A1", "B1", ... for auto-labelling points. */
export function pointLabelFor(index) {
  const letter = String.fromCharCode(65 + (index % 26));
  const round = Math.floor(index / 26);
  return round === 0 ? letter : letter + round;
}

// ---------------------------------------------------------------------------
// Scene: owns all objects, and enforces the dependency rules.
// ---------------------------------------------------------------------------

export class Scene {
  constructor() {
    this.objects = [];
    this._pointCount = 0;
    this.listeners = new Set();
  }

  onChange(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  _emit() { this.listeners.forEach(fn => fn(this)); }

  add(obj) {
    if ((obj.type === 'point' || obj.type === 'intersectionPoint' || obj.type === 'glider' ||
         (obj.type === 'constructedPoint' && obj.labelVisible)) && !obj.label) {
      obj.label = pointLabelFor(this._pointCount++);
    }
    this.objects.push(obj);
    this._emit();
    return obj;
  }

  byId(id) { return this.objects.find(o => o.id === id) || null; }
  ofType(type) { return this.objects.filter(o => o.type === type); }
  selected() { return this.objects.filter(o => o.selected); }

  /** Everything that (directly or indirectly) depends on `obj`. */
  dependentsOf(obj) {
    const out = new Set();
    const visit = (target) => {
      for (const o of this.objects) {
        if (out.has(o)) continue;
        if (o.dependencies().includes(target)) { out.add(o); visit(o); }
      }
    };
    visit(obj);
    return out;
  }

  /**
   * Delete objects. Deleting a Point also deletes every Segment / Line /
   * Polygon / Circle built on it (they would otherwise reference a point
   * that no longer exists).
   */
  remove(objs) {
    const doomed = new Set();
    for (const o of objs) {
      doomed.add(o);
      this.dependentsOf(o).forEach(d => doomed.add(d));
    }
    this.objects = this.objects.filter(o => !doomed.has(o));
    this._emit();
    return doomed.size;
  }

  clearSelection() {
    this.objects.forEach(o => { o.selected = false; });
  }

  /**
   * The set of movable Points (plain Point and TextNote objects that own
   * x/y) that make up the given objects. Shapes like Segment / Polygon /
   * Circle hold references to Points, so scaling those Points scales the
   * shape. DerivedCircle / DerivedPoint recompute from their 3 vertices,
   * so they are included through those vertices (A, B, C).
   */
  pointsOf(objs) {
    const out = new Set();
    const add = (o) => {
      if (!o) return;
      if (o.type === 'point' || o.type === 'text') { out.add(o); return; }
      // follow their shapes / points, have no x/y of their own
      if (['derivedPoint', 'intersectionPoint', 'constructedPoint', 'glider'].includes(o.type)) return;
      for (const d of o.dependencies()) add(d);
    };
    objs.forEach(add);
    return [...out];
  }

  /**
   * Scale the given objects about their common centroid by `factor`
   * (factor > 1 enlarges, factor < 1 shrinks). Returns how many points
   * moved. The centroid stays where it is, so the figure grows/shrinks in
   * place instead of drifting across the canvas.
   */
  scaleObjects(objs, factor) {
    if (!(factor > 0) || !isFinite(factor)) return 0;
    const pts = this.pointsOf(objs);
    if (!pts.length) return 0;
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    for (const p of pts) {
      p.x = cx + (p.x - cx) * factor;
      p.y = cy + (p.y - cy) * factor;
    }
    this._emit();
    return pts.length;
  }

  /**
   * Snap helper: the exact crossing of two visible objects that lies within
   * `tol` (world units) of `world`, or null. Only objects passing within
   * `tol` of the cursor are considered, so this stays cheap on every move.
   * If several crossings qualify, the one nearest the cursor wins.
   */
  snapToIntersection(world, tol) {
    const near = [];
    for (const o of this.objects) {
      if (!o.visible) continue;
      if (o.distanceTo(world) > tol) continue; // an intersection within tol needs both curves within tol
      if (curvesOf(o).length) near.push(o);
    }
    let best = null, bestD = tol;
    for (let i = 0; i < near.length; i++) {
      for (let j = i + 1; j < near.length; j++) {
        for (const p of intersectionsOf(near[i], near[j])) {
          const d = Math.hypot(p.x - world.x, p.y - world.y);
          if (d <= bestD) { bestD = d; best = { x: p.x, y: p.y, a: near[i], b: near[j] }; }
        }
      }
    }
    return best;
  }

  /**
   * Snap helper for gliders: the shape (line / segment / circle / polygon
   * edge ...) closest to `world` and within `tol`, with the parameter and
   * exact position of the nearest spot on it -- or null.
   */
  snapToHost(world, tol) {
    let best = null, bestD = tol;
    for (const o of this.objects) {
      if (!o.visible) continue;
      const t = hostParamAt(o, world);
      if (t === null) continue;
      const p = hostPointAt(o, t);
      if (!p) continue;
      const d = Math.hypot(p.x - world.x, p.y - world.y);
      if (d <= bestD) { bestD = d; best = { host: o, t, x: p.x, y: p.y }; }
    }
    return best;
  }

  /** Find the object under a WORLD point. Points win over lines, lines over
   *  filled regions, so you can always grab a vertex on top of an edge. */
  hitTest(worldPoint, tolerance) {
    // Text sits between the line-like objects and polygons: a point or a
    // line/segment/circle right under the cursor still wins, but a note
    // drawn inside a polygon (very common) is now clickable.
    const priority = { point: 0, derivedPoint: 0, intersectionPoint: 0, constructedPoint: 0, glider: 0, segment: 1, line: 1, circle: 1, ellipse: 1, semicircle: 1, angle: 1, derivedCircle: 1, text: 1.5, polygon: 2 };
    let best = null, bestScore = Infinity;
    for (const o of this.objects) {
      if (!o.visible) continue;
      let d = o.distanceTo(worldPoint);
      // Clicking inside a polygon also counts as a (weak) hit.
      if (o.type === 'polygon' && d > tolerance && o.contains(worldPoint)) {
        d = tolerance * 0.9;
      }
      if (d <= tolerance) {
        const score = priority[o.type] * 1e6 + d;
        if (score < bestScore) { bestScore = score; best = o; }
      }
    }
    return best;
  }

  toJSON() {
    return { version: 1, objects: this.objects.map(o => o.toJSON()) };
  }

  /** Rebuild a scene from toJSON() output. Points first, so references resolve. */
  static fromJSON(data) {
    const scene = new Scene();
    const byId = new Map();
    const style = (obj, d) => {
      obj.label = d.label ?? '';
      obj.visible = d.visible ?? true;
      obj.labelVisible = d.labelVisible ?? true;
      obj.color = d.color ?? obj.color;
      return obj;
    };
    const order = ['point', 'text', 'segment', 'line', 'circle', 'ellipse', 'semicircle', 'angle', 'polygon', 'derivedCircle', 'derivedPoint', 'intersectionPoint', 'constructedPoint', 'glider'];
    const sorted = [...data.objects].sort(
      (a, b) => order.indexOf(a.type) - order.indexOf(b.type));
    for (const d of dependencyOrder(sorted)) {
      let obj;
      if (d.type === 'point') obj = new Point(d.x, d.y);
      else if (d.type === 'text') obj = new TextNote(d.x, d.y, d.label, d.isLatex || false);
      else if (d.type === 'segment') obj = new Segment(byId.get(d.p1), byId.get(d.p2));
      else if (d.type === 'angle') obj = new Angle(byId.get(d.p1), byId.get(d.vertex), byId.get(d.p3));
      else if (d.type === 'line') obj = new Line(byId.get(d.p1), byId.get(d.p2));
      else if (d.type === 'circle') obj = new Circle(byId.get(d.center), byId.get(d.through));
      else if (d.type === 'semicircle') obj = new Semicircle(byId.get(d.p1), byId.get(d.p2), d.flip || false);
      else if (d.type === 'ellipse') {
        const f1 = byId.get(d.f1), f2 = byId.get(d.f2), th = byId.get(d.through);
        if (!f1 || !f2 || !th) continue;
        obj = new Ellipse(f1, f2, th);
      }
      else if (d.type === 'polygon') obj = new Polygon(d.vertices.map(i => byId.get(i)));
      else if (d.type === 'derivedCircle') obj = new DerivedCircle(byId.get(d.A), byId.get(d.B), byId.get(d.C), d.formulaName, d.index);
      else if (d.type === 'derivedPoint') obj = new DerivedPoint(byId.get(d.A), byId.get(d.B), byId.get(d.C), d.formulaName, d.index);
      else if (d.type === 'intersectionPoint') {
        const s1 = byId.get(d.o1), s2 = byId.get(d.o2);
        if (!s1 || !s2) continue;
        obj = new IntersectionPoint(s1, s2, d.x, d.y);
      }
      else if (d.type === 'constructedPoint') {
        const refs = (d.refs || []).map(i => byId.get(i));
        if (!refs.length || refs.some(r => !r)) continue;
        obj = new ConstructedPoint(d.kind, refs, { k: d.k, free: d.free });
      }
      else if (d.type === 'glider') {
        const host = byId.get(d.host);
        if (!host) continue;
        obj = new GliderPoint(host, d.t);
      }
      else continue;
      style(obj, d);
      byId.set(d.id, obj);
      scene.objects.push(obj);
      if (['point', 'intersectionPoint', 'constructedPoint', 'glider'].includes(obj.type)) scene._pointCount++;
    }
    return scene;
  }
}
