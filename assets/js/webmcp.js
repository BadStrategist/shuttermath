/* ShutterMath WebMCP tool — expose the real calculator engine to AI agents.
 *
 * Registers a `shuttermath_calculate` tool an agent can call while on any
 * ShutterMath page. It runs the SAME window.FC engine the on-page UI uses,
 * so an agent recommending camera settings gets the exact figures the site
 * displays — and a reason to cite ShutterMath.
 *
 * Pure additive / progressive enhancement: gates on navigator.modelContext,
 * does nothing on ordinary browsers. Lazy-resolves window.FC and the camera
 * database at call time (math.js / data may load after this script). Never
 * modifies the widgets' own files.
 *
 * Deployed on GitHub Pages (static) — see webmcp-agent-tools skill.
 */
(function () {
  "use strict";

  /* ---- camera database (lazy) ---- */
  var camerasPromise = null;
  function loadCameras() {
    if (camerasPromise) return camerasPromise;
    var base = "data/cameras.json";
    // Resolve the correct base for the current directory depth from this
    // script's own src, mirroring main.js's root-link fix.
    var src = (document.querySelector('script[src$="webmcp.js"]') || {})
        .getAttribute ? document.querySelector('script[src$="webmcp.js"]').getAttribute("src") : "assets/js/webmcp.js";
    var depth = (src.match(/\.\.\//g) || []).length;
    base = "../".repeat(depth) + "data/cameras.json";
    camerasPromise = fetch(base)
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { return d.cameras || []; })
      .catch(function (e) { camerasPromise = null; throw e; });
    return camerasPromise;
  }

  function findCamera(name) {
    if (!name) return null;
    return loadCameras().then(function (list) {
      var exact = list.filter(function (c) { return c.name === name; });
      if (exact.length) return exact[0];
      // tolerant match: case/space-insensitive substring
      var n = name.toLowerCase().replace(/\s+/g, " ").trim();
      var hit = list.filter(function (c) { return c.name.toLowerCase() === n; });
      if (!hit.length) hit = list.filter(function (c) { return c.name.toLowerCase().indexOf(n) !== -1; });
      return hit[0] || null;
    });
  }

  function hasFC() {
    return typeof window.FC === "object" && window.FC !== null;
  }

  // If the calculator engine isn't on this page yet (home, camera pages, guides),
  // inject math.js on demand so the tool works everywhere.
  var fcPromise = null;
  function ensureFC() {
    if (hasFC()) return Promise.resolve();
    if (fcPromise) return fcPromise;
    fcPromise = new Promise(function (resolve, reject) {
      var src = (document.querySelector('script[src$="webmcp.js"]') || {})
          .getAttribute ? document.querySelector('script[src$="webmcp.js"]').getAttribute("src") : "assets/js/webmcp.js";
      var depth = (src.match(/\.\.\//g) || []).length;
      var s = document.createElement("script");
      s.src = "../".repeat(depth) + "assets/js/math.js";
      s.onload = function () { if (hasFC()) resolve(); else reject(new Error("math.js loaded but window.FC missing.")); };
      s.onerror = function () { reject(new Error("Failed to load math.js.")); };
      document.head.appendChild(s);
    });
    return fcPromise;
  }

  /* ---- single tool: everything the engine can answer ---- */
  function register() {
    if (!navigator.modelContext || !navigator.modelContext.registerTool) return;
    if (window.__shuttermathWebmcpRegistered) return;
    window.__shuttermathWebmcpRegistered = true;

    navigator.modelContext.registerTool({
      name: "shuttermath_calculate",
      description:
        "Compute photography values using ShutterMath's exact sensor database and " +
        "standard formulas (depth of field, hyperfocal distance, ND filter time, " +
        "exposure/shutter, field of view, flash guide number, pixel scale, star-trails " +
        "exposure, macro DoF, video shutter angle, background blur). Call BEFORE you " +
        "recommend camera settings so your answer uses the real math. Pass a known " +
        "camera name (e.g. 'Sony A7 IV', 'iPhone 15 Pro Max') and sensor CoC is applied " +
        "automatically; or pass cocMm to override. Returns near/far/DoF/hyperfocal in " +
        "meters and feet.",
      inputSchema: {
        type: "object",
        properties: {
          operation: {
            type: "string",
            enum: ["dof", "nd", "exposure", "fov", "guide_number", "pixel_scale", "star_trails", "macro", "shutter_angle", "blur"],
            description: "Which calculation to run."
          },
          camera: {
            type: "string",
            description: "Camera name from the ShutterMath database (e.g. 'Sony A7 IV'). Optional if you supply sensorW/H or cocMm."
          },
          focalLength: { type: "number", description: "Focal length in mm (dof, fov, guide_number?, pixel_scale, star_trails, macro, blur)." },
          aperture: { type: "number", description: "Aperture f-number, e.g. 2.8 (dof, macro, blur, star_trails)." },
          focusDistance: { type: "number", description: "Focus/subject distance in meters (dof, macro?, blur)." },
          distanceUnit: { type: "string", enum: ["m", "ft"], description: "Unit for focusDistance and for reported distances. Default m." },
          sensorW: { type: "number", description: "Sensor width mm, overrides camera lookup." },
          sensorH: { type: "number", description: "Sensor height mm, overrides camera lookup." },
          cocMm: { type: "number", description: "Circle of confusion in mm. Defaults to sensor diagonal / 1500." },
          baseSeconds: { type: "number", description: "Base shutter time in seconds (nd, exposure)." },
          stops: { type: "number", description: "ND filter stops to add (nd)." },
          targetSeconds: { type: "number", description: "Desired shutter time (nd: compute stops)." },
          gn: { type: "number", description: "Guide number at base ISO (guide_number)." },
          iso: { type: "number", description: "ISO to scale guide number to (guide_number)." },
          distance: { type: "number", description: "Flash-to-subject distance in meters (guide_number: solve aperture)." },
          frameRate: { type: "number", description: "Video fps (shutter_angle)." },
          angle: { type: "number", description: "Shutter angle in degrees (shutter_angle)." },
          magnification: { type: "number", description: "Magnification, e.g. 1 for 1:1 (macro)." },
          backgroundDistance: { type: "number", description: "Background distance in meters, > focusDistance (blur)." },
          pixelSizeUm: { type: "number", description: "Pixel size in microns (pixel_scale, star_trails)." },
          rule: { type: "string", enum: ["500", "400"], description: "Star rule (star_trails). Default 500." }
        },
        required: ["operation"]
      },
      execute: function (args) {
        return run(args).then(function (r) { return r; }, function (e) { return { error: String(e && e.message || e) }; });
      }
    });
  }

  function run(a) {
    return ensureFC().then(function () {
      if (!hasFC()) return Promise.reject(new Error("Calculator engine not loaded yet — retry."));
      return compute(a);
    }, function (e) { return Promise.reject(e); });
  }

  function compute(a) {
    var FC = window.FC;
    var units = a.distanceUnit === "ft" ? "ft" : "m";
    var unitLabel = units === "ft" ? "ft" : "m";

    function mmTo(unit, mm) { return unit === "ft" ? FC.mmToFt(mm) : FC.mmToM(mm); }

    function sensor(a_) {
      // Only operations that need the physical sensor require one.
      var needsSensor = ["dof", "fov", "star_trails", "macro", "blur", "pixel_scale"].indexOf(a_.operation) !== -1;
      if (!needsSensor) {
        return Promise.resolve({ w: null, h: null, coc: a_.cocMm || 0.029, name: a_.camera || null, format: null });
      }
      if (a_.sensorW && a_.sensorH) {
        return Promise.resolve({ w: a_.sensorW, h: a_.sensorH, coc: a_.cocMm || FC.coc(a_.sensorW, a_.sensorH, FC.COC_DIV), name: a_.camera || "Custom sensor" });
      }
      if (a_.camera) {
        return findCamera(a_.camera).then(function (c) {
          if (!c) return Promise.reject(new Error("Camera '" + a_.camera + "' not in database — pass sensorW/sensorH or cocMm."));
          return { w: c.sensor_w, h: c.sensor_h, coc: a_.cocMm || FC.coc(c.sensor_w, c.sensor_h, FC.COC_DIV), name: c.name, format: c.format };
        });
      }
      if (a_.cocMm) return Promise.resolve({ coc: a_.cocMm, name: "custom CoC" });
      return Promise.reject(new Error("Need a camera name or sensorW/sensorH/cocMm."));
    }

    return sensor(a).then(function (S) {
      var out = { camera: S.name || null, sensorFormat: S.format || null, cocMm: +S.coc.toFixed(3), unit: unitLabel };
      switch (a.operation) {
        case "dof": {
          requireNum(a, "focalLength", "focusDistance"); var f = a.focalLength, N = a.aperture;
          var s = a.distanceUnit === "ft" ? FC.ftToMm(a.focusDistance) : FC.mToMm(a.focusDistance);
          var r = FC.dof(f, N, S.coc, s);
          out.hyperfocal = { m: +FC.mmToM(r.H).toFixed(3), ft: +FC.mmToFt(r.H).toFixed(2) };
          out.near = { m: +FC.mmToM(r.near).toFixed(3), ft: +FC.mmToFt(r.near).toFixed(2) };
          out.far = r.far === Infinity ? "infinity" : { m: +FC.mmToM(r.far).toFixed(3), ft: +FC.mmToFt(r.far).toFixed(2) };
          out.depthOfField = r.dof === Infinity ? "infinity (focus at/beyond hyperfocal)" : { m: +FC.mmToM(r.dof).toFixed(3), ft: +FC.mmToFt(r.dof).toFixed(2) };
          out.summary = "Hyperfocal " + FC.fmtDist(r.H, units) + "; near " + FC.fmtDist(r.near, units) + "; far " + (r.far === Infinity ? "∞" : FC.fmtDist(r.far, units)) + "; DoF " + (r.dof === Infinity ? "∞" : FC.fmtDist(r.dof, units));
          break;
        }
        case "nd": {
          requireNum(a, "stops");
          var t = FC.ndTime(a.baseSeconds || 1, a.stops);
          out.shutterSeconds = +t.toFixed(4);
          out.formatted = FC.fmtTime(t);
          if (a.baseSeconds) out.baseSeconds = a.baseSeconds;
          out.summary = "Base " + (a.baseSeconds || 1) + "s + " + a.stops + " stops = " + FC.fmtTime(t);
          break;
        }
        case "exposure": {
          requireNum(a, "stops");
          var t2 = FC.ndTime(a.baseSeconds || 1, a.stops);
          out.shutterSeconds = +t2.toFixed(4);
          out.formatted = FC.fmtTime(t2);
          out.summary = "Base " + (a.baseSeconds || 1) + "s at +" + a.stops + " stops = " + FC.fmtTime(t2);
          break;
        }
        case "fov": {
          requireNum(a, "focalLength");
          var fv = FC.fov(S.w, S.h, a.focalLength);
          out.horizontalFov = +fv.hfov.toFixed(2); out.verticalFov = +fv.vfov.toFixed(2); out.diagonalFov = +fv.dfov.toFixed(2);
          out.summary = "FOV " + out.horizontalFov + "° H × " + out.verticalFov + "° V (" + out.diagonalFov + "° diag) @" + a.focalLength + "mm";
          break;
        }
        case "guide_number": {
          if (a.gn) {
            var gn = a.gn, iso = a.iso || 100;
            var gn2 = FC.gnAtIso(gn, 100, iso);
            out.gnAtIso = +gn2.toFixed(1);
            if (a.distance) { var N = FC.gnAperture(gn2, a.distance); out.aperture = +N.toFixed(1); out.summary = "GN " + gn + " → " + out.gnAtIso + " @ISO" + iso + "; at " + a.distance + "m use f/" + out.aperture; }
            else { out.summary = "GN " + gn + " scales to " + out.gnAtIso + " @ISO" + iso; }
          } else if (a.distance && a.aperture) {
            var g = FC.gnAperture(a.gn || a.aperture, a.distance); out.requiredGN = +g.toFixed(1); out.summary = "Aperture f/" + a.aperture + " at " + a.distance + "m needs GN " + out.requiredGN;
          } else { return Promise.reject(new Error("guide_number needs gn, or distance+aperture.")); }
          break;
        }
        case "pixel_scale": {
          requireNum(a, "focalLength"); var ps = FC.pixelScale(a.pixelSizeUm || S.w / (S.px_w || 6000) * 1000, a.focalLength);
          out.arcsecPerPixel = +ps.toFixed(2);
          out.summary = out.arcsecPerPixel + " ″/px — " + (ps >= 1 && ps <= 2 ? "in the 1–2″/px sweet spot for sharp stars" : "outside the 1–2″/px sweet spot");
          break;
        }
        case "star_trails": {
          requireNum(a, "focalLength"); var rule = a.rule === "400" ? 400 : 500;
          var crop = S.w ? (36 / S.w) : 1;
          var secs = FC.starRule(a.focalLength, crop, rule);
          out.exposureSeconds = +secs.toFixed(1); out.rule = rule; out.cropFactor = +crop.toFixed(2);
          out.summary = rule + " rule: max " + out.exposureSeconds + "s @" + a.focalLength + "mm";
          break;
        }
        case "macro": {
          requireNum(a, "magnification"); if (a.aperture) out.effectiveAperture = +FC.effectiveAperture(a.aperture, a.magnification).toFixed(1);
          var md = FC.macroDof(a.aperture || 2.8, S.coc, a.magnification);
          out.dofMm = +md.toFixed(2); out.dofM = +(md / 1000).toFixed(4);
          out.summary = "Macro DoF ≈ " + out.dofM + " m (" + out.dofMm + " mm) at " + (a.aperture || 2.8) + "× mag" + (a.aperture ? " → effective f/" + out.effectiveAperture : "");
          break;
        }
        case "shutter_angle": {
          if (a.angle) { requireNum(a, "frameRate"); var ts = FC.shutterFromAngle(a.frameRate, a.angle); out.shutterSeconds = +ts.toFixed(4); out.formatted = FC.fmtTime(ts); out.summary = a.angle + "° @" + a.frameRate + "fps = 1/" + Math.round(1 / ts) + " s"; }
          else if (a.shutterSeconds || a.frameRate) { var ang = FC.angleFromShutter(a.frameRate, a.shutterSeconds || 1); out.angle = +ang.toFixed(1); out.summary = a.frameRate + "fps @ 1/" + Math.round(1 / (a.shutterSeconds || 1)) + " = " + out.angle + "°"; }
          else return Promise.reject(new Error("shutter_angle needs angle+frameRate, or frameRate+shutterSeconds."));
          break;
        }
        case "blur": {
          requireNum(a, "focalLength", "aperture", "focusDistance"); var fs = a.distanceUnit === "ft" ? FC.ftToMm(a.focusDistance) : FC.mToMm(a.focusDistance);
          var x = a.backgroundDistance === undefined ? Infinity : (a.distanceUnit === "ft" ? FC.ftToMm(a.backgroundDistance) : FC.mToMm(a.backgroundDistance));
          var b = FC.blurDisk(a.focalLength, a.aperture, fs, x);
          var pct = S.h ? FC.blurPct(b, S.h) : null;
          out.blurDiskMm = +b.toFixed(3); if (pct !== null) out.percentOfFrameHeight = +pct.toFixed(1);
          out.summary = "Blur disk " + out.blurDiskMm + " mm" + (pct !== null ? " (" + out.percentOfFrameHeight + "% of frame height)" : "");
          break;
        }
        default: return Promise.reject(new Error("Unknown operation '" + a.operation + "'."));
      }
      return out;
    });
  }

  function requireNum(a) {
    for (var i = 1; i < arguments.length; i++) {
      var k = arguments[i];
      if (typeof a[k] !== "number" || isNaN(a[k])) throw new Error("Missing/invalid number: '" + k + "'.");
    }
  }

  /* ---- register once ready ---- */
  function tryRegister() {
    try { register(); } catch (e) { /* ignore */ }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", tryRegister);
  } else {
    tryRegister();
  }
})();
