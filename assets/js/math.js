/* ShutterMath — core photography math. Standard published formulas.
   All DoF math in millimetres internally; helpers convert for display.
   Formulas:
     Hyperfocal:  H = f^2 / (N * c) + f
     Near:        s >= H ? H/2 : H*s / (H + (s - f))
     Far:         s >= H ? inf : H*s / (H - (s - f))
     CoC:         sensor diagonal / 1500 (standard "circle of confusion" convention)
     ND:          t_out = t_base * 2^stops
     Flash GN:    GN = distance * aperture  (ISO-scaled: GN2 = GN1 * sqrt(ISO2/ISO1))
     Pixel scale: arcsec/px = 206.265 * pixel_um / focal_mm
     FOV:         fov = 2 * atan(sensor / (2 * focal))
*/
(function () {
  "use strict";
  const FC = {
    MM_PER_M: 1000,
    MM_PER_FT: 304.8,
    stops: [1.0,1.1,1.2,1.4,1.6,1.8,2.0,2.2,2.5,2.8,3.2,3.5,4.0,4.5,5.0,5.6,6.3,7.1,8.0,9.0,10.0,11.0,13.0,14.0,16.0,18.0,20.0,22.0,25.0,29.0,32.0],
    isos: [50,100,200,400,800,1600,3200,6400,12800,25600],
    // --- circle of confusion ---
    sensorDiagonal: (w, h) => Math.hypot(w, h),
    coc: (w, h, div) => { const d = div || 1500; return Math.round((FC.sensorDiagonal(w, h) / d) * 1000) / 1000; },
    // --- hyperfocal (mm) ---
    hyperfocal: (f_mm, N, coc_mm) => (f_mm * f_mm) / (N * coc_mm) + f_mm,
    // --- depth of field: all inputs mm; returns mm (Infinity where unbounded) ---
    dof: function (f_mm, N, coc_mm, s_mm) {
      const H = FC.hyperfocal(f_mm, N, coc_mm);
      /* General thin-lens limits. They hold on both sides of the hyperfocal
         distance: the old shortcut of clamping the near limit to H/2 whenever the
         focus distance passed H understated the near limit badly (16 mm f/8 at
         3 m claimed 0.56 m sharp when the true near limit is 0.82 m). */
      const near = (H * s_mm) / (H + (s_mm - f_mm));
      const denom = H - (s_mm - f_mm);
      const far = denom > 0 ? (H * s_mm) / denom : Infinity;
      const front = s_mm - near;
      const back = far === Infinity ? Infinity : far - s_mm;
      return { H: H, near: near, far: far, front: front, back: back, dof: far === Infinity ? Infinity : far - near };
    },
    // --- ND filter ---
    ndTime: (base_s, stops) => base_s * Math.pow(2, stops),
    ndStopsForTime: (base_s, target_s) => Math.log2(target_s / base_s),
    // --- flash guide number ---
    gnAperture: (gn, dist) => gn / dist,
    gnDistance: (gn, N) => gn / N,
    gnAtIso: (gn, isoFrom, isoTo) => gn * Math.sqrt(isoTo / isoFrom),
    gnIsoFor: (gn, isoFrom, targetGn) => isoFrom * Math.pow(targetGn / gn, 2),
    // --- astro pixel scale (arcsec per pixel) ---
    pixelScale: (px_um, f_mm) => (206.265 * px_um) / f_mm,
    // --- field of view (deg) ---
    fov: (w_mm, h_mm, f_mm) => ({
      hfov: 2 * Math.atan(w_mm / (2 * f_mm)) * (180 / Math.PI),
      vfov: 2 * Math.atan(h_mm / (2 * f_mm)) * (180 / Math.PI),
      dfov: 2 * Math.atan(FC.sensorDiagonal(w_mm, h_mm) / (2 * f_mm)) * (180 / Math.PI)
    }),
    // --- format helpers ---
    mmToM: (mm) => mm / 1000,
    mToMm: (m) => m * 1000,
    mmToFt: (mm) => mm / 304.8,
    ftToMm: (ft) => ft * 304.8,
    mmToIn: (mm) => mm / 25.4,
    // --- pretty printers ---
    fmtDist: function (mm, unit) {
      if (!isFinite(mm)) return unit === "ft" ? "∞" : "∞";
      if (unit === "ft") {
        const ft = mm / 304.8;
        if (ft < 0.2) return Math.round(mm / 25.4 * 100) / 100 + " in";
        if (ft >= 100) return Math.round(ft) + " ft";
        return Math.round(ft * 100) / 100 + " ft";
      }
      const m = mm / 1000;
      if (m < 0.05) return Math.round(mm) + " mm";
      if (m >= 100) return Math.round(m) + " m";
      return Math.round(m * 100) / 100 + " m";
    },
    fmtTime: function (s) {
      if (s >= 60) { const m = Math.floor(s / 60); const r = Math.round((s - m * 60) * 10) / 10; return r > 0 ? m + " min " + r + " s" : m + " min"; }
      if (s >= 1) return Math.round(s * 10) / 10 + " s";
      return Math.round(s * 1000) + " ms";
    },
    fmtStops: function (x) { return Math.round(x * 100) / 100; },
    // --- exposure value (EV100 = log2(N^2 / t); standard convention) ---
    ev100: (N, t_s) => Math.log2((N * N) / t_s),
    evAtIso: (ev100, iso) => ev100 - Math.log2(iso / 100),
    shutterFor: (N, ev) => (N * N) / Math.pow(2, ev),
    apertureFor: (t_s, ev) => Math.sqrt(Math.pow(2, ev) * t_s),
    // --- print resolution ---
    dpiFrom: (px, inches) => px / inches,
    inchesFrom: (px, dpi) => px / dpi,
    maxPrint: (w, h, dpi) => ({ wIn: w / dpi, hIn: h / dpi }),
    // --- astro star-exposure rules (seconds) ---
    starRule: (focal, crop, rule) => rule / (focal * crop),
    npfRule: (focal, crop, N, px_um) => (35 * N + 30 * px_um) / (focal * crop),
    // --- macro (approx; m = magnification, e.g. 1:1 => 1) ---
    macroDof: (N, coc_mm, m) => (2 * N * coc_mm * (m + 1)) / (m * m), // mm
    effectiveAperture: (N, m) => N * (1 + m),
    // --- video shutter angle ---
    shutterFromAngle: (fps, angle) => 1 / (fps * 360 / angle),
    angleFromShutter: (fps, t_s) => 360 * t_s * fps,
    // --- default CoC div (standard) ---
    COC_DIV: 1500,
    // --- background blur (bokeh) ---
    // Blur disk diameter on the sensor (mm) for a background point at distance x,
    // focus at s, focal f, aperture N. Standard geometric formula (all lengths in mm).
    blurDisk: (f, N, s, x) => {
      if (x <= s) return 0;               // background at/behind focus plane not applicable
      if (!isFinite(x)) return f * f / (N * s);  // background at infinity
      return f * f * (x - s) / (N * s * (x - f));
    },
    blurInfinity: (f, N, s) => f * f / (N * s),
    blurPct: (b, sensorH) => b / sensorH * 100
  };
  window.FC = FC;
})();
