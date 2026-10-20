/**
 * latex.js
 *
 * Turns LaTeX source into a drawable raster image, using MathJax (loaded
 * from a CDN in geometry.html) to typeset SVG, then rasterising that SVG
 * into an HTMLImageElement via a data: URL.
 *
 * Canvas rendering is synchronous (Renderer.render() runs once per frame,
 * drawImage() needs a ready image right now), but MathJax typesetting is
 * async. So this module is a small cache: request(source) kicks off the
 * async work in the background and returns immediately; the renderer
 * calls get(source) every frame, which returns null until the image is
 * ready, then returns the same cached Image forever after (until the
 * source string changes).
 */

// key -> { status: 'pending' | 'ready' | 'error', img, widthPx, heightPx }
const _cache = new Map();

/** True once the MathJax script (loaded via a <script> tag in the page) has initialised. */
function mathJaxReady() {
  return typeof window !== 'undefined' && window.MathJax && window.MathJax.tex2svgPromise;
}

/**
 * Ensure `source` (LaTeX, without surrounding $...$) is being rendered;
 * safe to call every frame -- it's a no-op once the entry exists.
 * `color` is baked into the cache key because MathJax colours the SVG at
 * typeset time, not at draw time.
 */
export function request(source, color = '#1c2321') {
  const key = color + '\u0000' + source;
  if (_cache.has(key)) return key;
  if (!source || !source.trim()) return null;

  _cache.set(key, { status: 'pending', img: null, widthPx: 0, heightPx: 0 });

  if (!mathJaxReady()) {
    // MathJax hasn't finished loading yet (page just opened) -- retry
    // shortly. This only affects the first LaTeX note right after load.
    setTimeout(() => { _cache.delete(key); request(source, color); }, 200);
    return key;
  }

  window.MathJax.tex2svgPromise(source, { display: true })
    .then((node) => {
      const svg = node.querySelector('svg');
      if (!svg) throw new Error('MathJax produced no <svg>');

      // MathJax reports size in 'ex' units; convert to a pixel size for a
      // crisp raster (2x oversampled, then drawn back down -- sharper on
      // high-DPI screens without changing the on-canvas layout size).
      const exToPx = 8; // ~1ex at a 16px-ish base font
      const widthEx = parseFloat(svg.getAttribute('width')) || 1;
      const heightEx = parseFloat(svg.getAttribute('height')) || 1;
      const widthPx = Math.max(1, widthEx * exToPx);
      const heightPx = Math.max(1, heightEx * exToPx);
      svg.setAttribute('width', String(widthPx * 2));
      svg.setAttribute('height', String(heightPx * 2));
      svg.style.color = color; // MathJax SVG paths use currentColor
      svg.setAttribute('color', color);

      const xml = new XMLSerializer().serializeToString(svg);
      const dataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);

      const img = new Image();
      img.onload = () => {
        _cache.set(key, { status: 'ready', img, widthPx, heightPx });
      };
      img.onerror = () => {
        _cache.set(key, { status: 'error', img: null, widthPx: 0, heightPx: 0 });
      };
      img.src = dataUrl;
    })
    .catch(() => {
      _cache.set(key, { status: 'error', img: null, widthPx: 0, heightPx: 0 });
    });

  return key;
}

/**
 * Look up a cached render. Returns { img, widthPx, heightPx } once ready,
 * or null while pending/errored (caller should fall back to plain text).
 */
export function get(source, color = '#1c2321') {
  const key = color + '\u0000' + source;
  const entry = _cache.get(key);
  if (!entry || entry.status !== 'ready') return null;
  return entry;
}

/** True if this exact (source, color) pair failed to typeset -- lets the
 *  caller show an error hint instead of silently waiting forever. */
export function failed(source, color = '#1c2321') {
  const key = color + '\u0000' + source;
  const entry = _cache.get(key);
  return !!entry && entry.status === 'error';
}
