/* ShutterMath — shared chrome: consent gate, ad-slot renderer, analytics.
   Ad code is fully inert until ADSENSE_CLIENT is set post-approval — the site is
   self-sufficient without ads, per Google Publisher Policies. */
(function () {
  "use strict";

  const SITE = {
    name: "ShutterMath",
    tagline: "Photography calculators that know the camera you own",
    year: new Date().getFullYear()
  };

  const NAV = [
    ["Depth of Field", "/tools/depth-of-field.html"],
    ["Hyperfocal", "/tools/hyperfocal.html"],
    ["ND Filter", "/tools/nd-filter.html"],
    ["Flash GN", "/tools/flash-guide-number.html"],
    ["Pixel Scale", "/tools/pixel-scale.html"],
    ["Shutter Angle", "/tools/shutter-angle.html"],
    ["Crop Factor", "/tools/crop-factor.html"],
    ["Blur", "/tools/background-blur.html"],
    ["Guides", "/pages/guides.html"]
  ];

  const FOOT_LINKS = [
    ["Free Tools", "/pages/free-photography-calculators.html"],
    ["Field Kit", "/products.html"],
    ["About", "/pages/about.html"],
    ["Contact", "/pages/contact.html"],
    ["Privacy Policy", "/pages/privacy.html"],
    ["Terms", "/pages/terms.html"]
  ];

  /* Header and footer are static HTML in every page: crawlers and AI answer
     engines do not run JavaScript, so a JS-injected nav was invisible to them and
     (because the base-path guess failed) broken for readers too. This only fills a
     shell that is genuinely empty; it never rewrites an existing nav. */
  function injectChrome() {
    const header = document.querySelector(".site-header");
    if (header && !header.querySelector(".brand")) {
      header.innerHTML =
        '<div class="container">' +
        '<a class="brand" href="/">Shutter<span>Math</span></a>' +
        '<nav class="nav" aria-label="Main navigation">' +
        NAV.map(n => '<a href="' + n[1] + '">' + n[0] + "</a>").join("") +
        '</nav><button class="nav-toggle" aria-label="Menu" aria-expanded="false">☰</button></div>';
    }
    if (header) {
      const t = header.querySelector(".nav-toggle");
      const nav = header.querySelector(".nav");
      if (t && nav) {
        t.addEventListener("click", () => {
          const open = nav.classList.toggle("open");
          t.setAttribute("aria-expanded", open ? "true" : "false");
        });
        nav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => {
          nav.classList.remove("open");
          t.setAttribute("aria-expanded", "false");
        }));
      }
    }
    const footer = document.querySelector(".site-footer");
    if (footer && !footer.querySelector("strong")) {
      footer.innerHTML =
        '<div class="container">' +
        '<div><strong style="color:#fff">' + SITE.name + "</strong><br>" + SITE.tagline + "</div>" +
        '<nav class="fnav" aria-label="Footer navigation">' +
        FOOT_LINKS.map(l => '<a href="' + l[1] + '">' + l[0] + "</a>").join("") +
        "</nav></div>";
    }
    if (footer && !document.getElementById("ad-footer")) {
      const slot = document.createElement("div");
      slot.className = "ad-slot";
      slot.id = "ad-footer";
      slot.dataset.ad = "footer";
      footer.parentNode.insertBefore(slot, footer);
    }
  }

  /* --- consent (GDPR/EEA; Google-certified CMP script slot) --- */
  function consent() {
    const KEY = "fc-consent";
    const v = localStorage.getItem(KEY);
    if (v === "granted" || v === "denied") return v;
    return null;
  }
  function showConsent() {
    if (consent()) return;
    const bar = document.querySelector(".consent");
    if (!bar) return;
    bar.classList.add("show");
    document.body.classList.add("consent-open");
    const accept = bar.querySelector(".consent-accept");
    const deny = bar.querySelector(".consent-deny");
    const dismiss = () => { bar.classList.remove("show"); document.body.classList.remove("consent-open"); };
    if (accept) accept.addEventListener("click", () => { localStorage.setItem("fc-consent", "granted"); dismiss(); });
    if (deny) deny.addEventListener("click", () => { localStorage.setItem("fc-consent", "denied"); dismiss(); });
  }

  /* --- AdSense gate: inert until approval; renders only with consent --- */
  const ADSENSE_CLIENT = ""; // set after AdSense approval, e.g. "ca-pub-XXXXXXXXXXXXXXXX"
  window.FC_ADS = {
    enabled: () => ADSENSE_CLIENT !== "" && consent() === "granted",
    render: function (slotId) {
      const el = document.getElementById(slotId);
      if (!el) return;
      if (!window.FC_ADS.enabled()) { el.innerHTML = ""; return; }
      el.innerHTML = '<span class="ad-label">Sponsored</span>' +
        '<ins class="adsbygoogle" style="display:block" data-ad-client="' + ADSENSE_CLIENT + '" ' +
        'data-ad-slot="' + slotId + '" data-ad-format="auto" data-full-width-responsive="true"></ins>';
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) { /* noop */ }
    }
  };

  /* --- GoatCounter analytics: privacy-friendly, cookieless, GDPR-friendly. --- */
  const GOATCOUNTER_CODE = "shuttermath"; // ShutterMath's own site (kulture = BakersfieldBrief's — never mix)
  function loadAnalytics() {
    if (GOATCOUNTER_CODE === "") return;
    const s = document.createElement("script");
    s.setAttribute("data-goatcounter", "https://" + GOATCOUNTER_CODE + ".goatcounter.com/count");
    s.async = true;
    s.src = "https://gc.zgo.at/count.js";
    document.head.appendChild(s);
  }

  document.addEventListener("DOMContentLoaded", () => {
    injectChrome();
    showConsent();
    loadAnalytics();
    document.querySelectorAll("[data-ad]").forEach(el => window.FC_ADS.render(el.id || "ad-" + el.dataset.ad));
  });
})();
