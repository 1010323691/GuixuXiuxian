"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const storageKey = "guixu.pending.v2";
  const legacyStorageKey = "guixu.pending.v1";
  let snapshot = null;
  let busy = false;
  let pending = null;
  let expanded = false;
  let selectedGroup = "cultivation";
  let confirmation = null;
  let previousFocus = null;
  let storageAvailable = true;
  let selectedWorldPage = "world";
  let worldFieldSequence = 0;
  let worldDrafts = new Map();
  let submittedWorldKey = null;
  let historyVisible = false;
  const worldActionFilters = new Map();
  const worldSectionOpen = new Map();
  let growthAnchor = null;
  let growthRefreshing = false;
  let creditsAnchor = null;
  let creditsRefreshAt = -Infinity;
  let selectedLootUid = "";
  let selectedDungeonKey = "";
  let newRevisionObserved = false;
  // 账号与同步状态（密码与令牌从不进入脚本可读存储；会话 Cookie 为 HttpOnly）
  let account = null;
  let registrationOpen = true;
  let authLocked = true;
  let authMode = "login";
  let authSubmitting = false;
  let offline = false;
  let syncState = "idle";
  let lastSyncedAt = "";
  let syncFadeTimer = 0;
  let reconnectTimer = 0;
  let reconnectDelay = 2000;
  const retryDelays = [1000, 2000, 4000];
  const battleActionIds = new Set(["world_auto_battle", "auto_battle"]);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const svgNS = "http://www.w3.org/2000/svg";
  const qualityNames = ["凡品", "下品", "中品", "上品", "极品"];
  const reducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let previousResourceValues = null;
  let previousLogs = null;
  let previousRealm = null;

  function icon(name) {
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const use = document.createElementNS(svgNS, "use");
    use.setAttribute("href", `#i-${name}`);
    svg.append(use);
    return svg;
  }

  function qualityBadge(quality) {
    const badge = element("span", "quality", quality);
    const index = qualityNames.indexOf(quality);
    if (index >= 0) badge.dataset.q = String(index);
    return badge;
  }

  const sceneMarks = {
    world: '<path class="sb-far" d="M250 150 L330 40 L380 110 L420 60 L500 150Z"/><path class="sb-ink" d="M560 50q8-6 16 0q8-6 16 0M600 70q6-5 12 0q6-5 12 0" fill="none"/>',
    character: '<circle class="sb-moon" cx="560" cy="58" r="30"/><path class="sb-near" d="M330 170 q40-34 90-30 q40 4 60 30Z"/><path class="sb-ink" d="M404 142 q-4-16 4-26 q8 10 4 26Z M408 112 a6 6 0 1 0 .1 0"/>',
    sects: '<path class="sb-near" d="M300 175 L340 120 L470 120 L510 175Z"/><path class="sb-roof" d="M330 98 Q405 70 480 98 L470 106 Q405 86 340 106Z M352 120 V106 M458 120 V106"/><rect class="sb-wall" x="352" y="104" width="106" height="18"/><path class="sb-roof" d="M366 74 Q405 54 444 74 L436 80 Q405 66 374 80Z"/><rect class="sb-wall" x="378" y="78" width="54" height="22"/>',
    social: '<path class="sb-roof" d="M330 112 Q400 86 470 112 L462 118 Q400 100 338 118Z"/><rect class="sb-wall" x="350" y="118" width="100" height="6"/><path class="sb-ink" d="M356 124 V160 M444 124 V160" fill="none"/><path class="sb-ink" d="M380 160 q0-16 8-20 q8 4 8 20Z M410 160 q0-16 8-20 q8 4 8 20Z M392 132a5 5 0 1 0 .1 0 M422 132a5 5 0 1 0 .1 0"/>',
    craft: '<path class="sb-gold" d="M360 118 H450 L440 160 H370Z"/><path class="sb-ink" d="M352 118 H458 M378 160 l-6 14 M432 160 l6 14" fill="none"/><path class="sb-smoke" d="M390 112 q-12-16 0-30 q12-14 0-30 M420 112 q12-16 0-32 q-10-14 4-28" fill="none"/>',
    exploration: '<path class="sb-mid" d="M260 175 Q300 60 405 52 Q510 60 550 175Z"/><path class="sb-cave" d="M360 175 Q365 112 405 108 Q445 112 450 175Z"/><circle class="sb-glow" cx="405" cy="150" r="14"/>',
    estate: '<path class="sb-roof" d="M330 116 L400 88 L470 116 L462 120 L400 96 L338 120Z"/><rect class="sb-wall" x="346" y="118" width="108" height="42"/><rect class="sb-cave" x="388" y="130" width="24" height="30"/><path class="sb-bamboo" d="M500 175 V60 M520 175 V80 M540 175 V50 M500 90 l14-10 M520 110 l-14-8 M540 80 l14-10" fill="none"/>',
    market: '<path class="sb-ink" d="M250 60 Q400 100 550 60" fill="none"/><g class="sb-lantern"><ellipse cx="300" cy="86" rx="12" ry="15"/><ellipse cx="360" cy="96" rx="12" ry="15"/><ellipse cx="440" cy="96" rx="12" ry="15"/><ellipse cx="500" cy="86" rx="12" ry="15"/></g><path class="sb-roof" d="M300 140 L340 124 L380 140Z M420 140 L460 124 L500 140Z"/><rect class="sb-wall" x="310" y="140" width="60" height="22"/><rect class="sb-wall" x="430" y="140" width="60" height="22"/>',
    quests: '<path class="sb-stone" d="M378 170 V86 Q378 70 405 70 Q432 70 432 86 V170Z"/><path class="sb-ink" d="M405 88 V150 M393 96 V140" fill="none"/><rect class="sb-near" x="360" y="166" width="90" height="10"/>',
    achievements: '<path class="sb-stone" d="M350 172 V80 H460 V172Z"/><rect class="sb-plaque" x="364" y="92" width="82" height="20"/><path class="sb-ink" d="M372 128 H438 M372 142 H438 M372 156 H420" fill="none"/><rect class="sb-seal" x="430" y="150" width="14" height="14"/><path class="sb-flag" d="M330 172 V64 l22 8 -22 8 M480 172 V64 l-22 8 22 8"/>',
    arena: '<path class="sb-stone" d="M290 172 L320 136 H490 L520 172Z"/><path class="sb-flag" d="M320 136 V66 l26 9 -26 9 M490 136 V66 l-26 9 26 9"/><path class="sb-ink" d="M380 128 L430 92 M430 128 L380 92" fill="none"/>'
  };

  function sceneBanner(target, id) {
    const node = $(target);
    if (!node || node.dataset.scene === id) return;
    const changed = !!node.dataset.scene;
    node.dataset.scene = id;
    if (changed && !reducedMotion()) {
      node.classList.remove("scene-in");
      void node.offsetWidth;
      node.classList.add("scene-in");
    }
    node.innerHTML = `<svg viewBox="0 0 800 180" preserveAspectRatio="xMidYMax slice" focusable="false"><defs><linearGradient id="${target}-sky" x1="0" y1="0" x2="0" y2="1"><stop class="sb-s1" offset="0"/><stop class="sb-s2" offset="1"/></linearGradient></defs><rect width="800" height="180" fill="url(#${target}-sky)"/><circle class="sb-sun" cx="690" cy="46" r="22"/><path class="sb-cloud" d="M60 52h120M100 40h60M560 30h90M600 42h70" fill="none"/><path class="sb-far" d="M0 150 L70 88 L130 120 L200 70 L280 128 L360 92 L460 132 L560 80 L650 118 L730 84 L800 112 V180 H0Z"/><path class="sb-mid" d="M0 162 Q90 120 170 146 T340 140 T520 150 T700 132 T800 146 V180 H0Z"/>${sceneMarks[id] || sceneMarks.world}<path class="sb-near" d="M0 172 Q120 152 260 168 T560 166 T800 160 V180 H0Z"/></svg>`;
  }

  function actionKind(action, pageId) {
    const id = action.id || "";
    if (action.group === "battle" || battleActionIds.has(id) || /attack|boss|dungeon|elite|arena|duel|challenge|fight|hunt/.test(id) || pageId === "arena") return "combat";
    if (pageId === "market" || /buy|sell|auction|trade|market|shop/.test(id)) return "trade";
    if (["social", "sects"].includes(pageId) || /visit|gift|talk|friend|disciple|master|family|sect/.test(id)) return "social";
    if (["craft", "estate"].includes(pageId) || /craft|alchemy|forge|array|talisman|estate|plant/.test(id)) return "craft";
    if (pageId === "quests" || /quest|story|activity/.test(id)) return "quest";
    return "cultivate";
  }

  function logItem(text) {
    const item = element("li");
    for (const part of String(text).split(/([+＋]\d[\d.,]*|[-－]\d[\d.,]*)/)) {
      if (!part) continue;
      if (/^[+＋]\d/.test(part)) item.append(element("span", "log-gain", part));
      else if (/^[-－]\d/.test(part)) item.append(element("span", "log-loss", part));
      else item.append(part);
    }
    return item;
  }

  function showToasts(entries) {
    const layer = $("fx-layer");
    for (const text of entries.slice(-3)) {
      const toast = element("div", "toast", text);
      layer.append(toast);
      setTimeout(() => toast.remove(), 3200);
    }
    while (layer.querySelectorAll(".toast").length > 3) layer.querySelector(".toast").remove();
  }

  function showBreakthrough(realm) {
    const avatarRealm = $("realm");
    avatarRealm.classList.remove("flash");
    if (reducedMotion()) return;
    void avatarRealm.offsetWidth;
    avatarRealm.classList.add("flash");
    const layer = $("fx-layer");
    layer.querySelector(".breakthrough")?.remove();
    const overlay = element("div", "breakthrough");
    overlay.append(element("span", "breakthrough-ring"), element("span", "breakthrough-ring"), element("strong", "breakthrough-title", `突破 · ${realm}`));
    layer.append(overlay);
    fx.burst(innerWidth / 2, innerHeight / 2, token("--aura-7"), 64, 260);
    setTimeout(() => overlay.remove(), 1600);
  }

  /* ---------- 演出引擎：灵气粒子 · 获得飞入 · 点击涟漪（只用 transform/opacity/canvas，不改布局） ----------
     粒子只承载信息：舞台灵气的颜色与密度随境界递进；获得飞入从被执行的事项飞向实际增加的资源。 */
  const tokenCache = new Map();
  function token(name) {
    if (!tokenCache.has(name)) tokenCache.set(name, getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#E8B84A");
    return tokenCache.get(name);
  }

  function rgb(hex) {
    const value = hex.replace("#", "");
    const full = value.length === 3 ? [...value].map((c) => c + c).join("") : value.padEnd(6, "0");
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) || 0);
  }

  const aura = (() => {
    const canvas = element("canvas", "aura-canvas");
    canvas.setAttribute("aria-hidden", "true");
    const context = canvas.getContext("2d");
    let host = null, tier = -1, color = [63, 165, 133], width = 0, height = 0, motes = [], frameId = 0, last = 0;
    const observer = globalThis.ResizeObserver ? new ResizeObserver(() => resize()) : null;
    const visible = () => !!host && host.isConnected && !document.hidden && !reducedMotion() && !document.body.classList.contains("stage3d-on") && host.getClientRects().length > 0 && !host.closest("[hidden]");
    function mote(anywhere) {
      const speed = 1 + tier * .09;
      return { x: Math.random() * width, y: anywhere ? Math.random() * height : height + 4, r: .7 + Math.random() * 1.7, vy: -(5 + Math.random() * 12) * speed, vx: (Math.random() - .5) * 5, phase: Math.random() * 6.283, twinkle: 1.2 + Math.random() * 2 };
    }
    function seed() {
      const count = Math.round(Math.max(8, Math.min(42, width * height / 8000)) * (.55 + tier * .07));
      motes = Array.from({ length: count }, () => mote(true));
    }
    function resize() {
      if (!host) return;
      const rect = host.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const ratio = Math.min(1.5, globalThis.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(width * ratio));
      canvas.height = Math.max(1, Math.round(height * ratio));
      context?.setTransform(ratio, 0, 0, ratio, 0, 0);
      seed();
      start();
    }
    function frame(now) {
      frameId = 0;
      if (!context || !visible()) { context?.clearRect(0, 0, width, height); return; }
      if (now - last < 32) { frameId = requestAnimationFrame(frame); return; }
      const dt = Math.min(.07, (now - last) / 1000);
      last = now;
      context.clearRect(0, 0, width, height);
      const [r, g, b] = color;
      for (const m of motes) {
        m.phase += dt * m.twinkle;
        m.x += (m.vx + Math.sin(m.phase) * 3) * dt;
        m.y += m.vy * dt;
        if (m.y < -6 || m.x < -6 || m.x > width + 6) Object.assign(m, mote(false));
        const fade = Math.min(1, m.y / (height * .35));
        const alpha = (.35 + .4 * Math.sin(m.phase) ** 2) * Math.max(0, fade);
        context.fillStyle = `rgba(${r},${g},${b},${alpha * .22})`;
        context.beginPath(); context.arc(m.x, m.y, m.r * 3.2, 0, 6.283); context.fill();
        context.fillStyle = `rgba(255,253,240,${alpha})`;
        context.beginPath(); context.arc(m.x, m.y, m.r * .8, 0, 6.283); context.fill();
        context.fillStyle = `rgba(${r},${g},${b},${alpha})`;
        context.beginPath(); context.arc(m.x, m.y, m.r * 1.3, 0, 6.283); context.fill();
      }
      frameId = requestAnimationFrame(frame);
    }
    function start() {
      if (!frameId && visible()) { last = performance.now(); frameId = requestAnimationFrame(frame); }
    }
    function mount(nextHost, nextTier) {
      if (!nextHost || !context) return;
      if (host !== nextHost) {
        if (host) observer?.unobserve(host);
        host = nextHost;
        const banner = host.querySelector(":scope > .scene-banner");
        if (banner) banner.after(canvas); else host.prepend(canvas);
        observer?.observe(host);
        resize();
      }
      if (tier !== nextTier) {
        tier = nextTier;
        color = rgb(token(`--aura-${Math.max(0, Math.min(8, tier))}`));
        seed();
      }
      start();
    }
    document.addEventListener("visibilitychange", start);
    return { mount, start };
  })();

  /* 三维舞台氛围（Three.js，按需加载）：成功时接管该宿主的灵气演出，失败/无 WebGL/减少动态时保留上面的 Canvas2D。 */
  const stage3d = (() => {
    let mod = null, loading = null, failed = false;
    const load = () => loading || (loading = import("/fx3d.js").then((m) => { mod = m; return m; }).catch(() => { failed = true; return null; }));
    function mount(host, tier, page, estate) {
      if (failed || reducedMotion() || !host) { mod?.unmountStage(); return; }
      const spec = { host, tier, color: token(`--aura-${Math.max(0, Math.min(8, tier))}`), page, estate };
      if (!mod) { load().then((m) => { if (m && host.isConnected) m.mountStage(spec); }); return; }
      if (!mod.mountStage(spec)) failed = !document.body.classList.contains("stage3d-on");
    }
    return { mount };
  })();

  const fx = (() => {
    const canvas = element("canvas", "fx-canvas");
    canvas.setAttribute("aria-hidden", "true");
    const context = canvas.getContext("2d");
    let flights = [], sparks = [], frameId = 0, last = 0, ratio = 1;
    function fit() {
      ratio = Math.min(1.5, globalThis.devicePixelRatio || 1);
      canvas.width = Math.round(innerWidth * ratio);
      canvas.height = Math.round(innerHeight * ratio);
      context?.setTransform(ratio, 0, 0, ratio, 0, 0);
    }
    function ensure() {
      if (!context || reducedMotion()) return false;
      if (!canvas.isConnected) { $("fx-layer").prepend(canvas); fit(); }
      if (canvas.width !== Math.round(innerWidth * ratio)) fit();
      if (!frameId) { last = performance.now(); frameId = requestAnimationFrame(frame); }
      return true;
    }
    function frame(now) {
      frameId = 0;
      const dt = Math.min(.05, (now - last) / 1000);
      last = now;
      context.clearRect(0, 0, innerWidth, innerHeight);
      flights = flights.filter((p) => {
        p.t += dt;
        const k = Math.max(0, Math.min(1, (p.t - p.delay) / p.duration));
        if (k <= 0) return true;
        const e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
        const x = (1 - e) ** 2 * p.x0 + 2 * (1 - e) * e * p.cx + e * e * p.x1;
        const y = (1 - e) ** 2 * p.y0 + 2 * (1 - e) * e * p.cy + e * e * p.y1;
        const [r, g, b] = p.color;
        context.fillStyle = `rgba(${r},${g},${b},.25)`;
        context.beginPath(); context.arc(x, y, p.size * 2.6, 0, 6.283); context.fill();
        context.fillStyle = `rgba(${r},${g},${b},1)`;
        context.beginPath(); context.arc(x, y, p.size, 0, 6.283); context.fill();
        if (k >= 1) { p.arrive?.(); return false; }
        return true;
      });
      sparks = sparks.filter((s) => {
        s.life -= dt;
        if (s.life <= 0) return false;
        s.vy += 140 * dt;
        s.x += s.vx * dt;
        s.y += s.vy * dt;
        const [r, g, b] = s.color;
        context.fillStyle = `rgba(${r},${g},${b},${Math.min(1, s.life / s.span * 1.4)})`;
        context.beginPath(); context.arc(s.x, s.y, s.size * (s.life / s.span), 0, 6.283); context.fill();
        return true;
      });
      if (flights.length || sparks.length) frameId = requestAnimationFrame(frame);
    }
    function burst(x, y, hex, count = 16, power = 120) {
      if (!ensure()) return;
      const color = rgb(hex);
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * 6.283;
        const speed = power * (.35 + Math.random() * .65);
        const span = .5 + Math.random() * .6;
        sparks.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - power * .3, life: span, span, size: 1.5 + Math.random() * 2.2, color });
      }
    }
    function fly(from, to, hex, count, arrive) {
      if (!ensure()) { arrive?.(); return; }
      const color = rgb(hex);
      let arrived = false;
      for (let i = 0; i < count; i++) {
        const x0 = from.x + (Math.random() - .5) * 24, y0 = from.y + (Math.random() - .5) * 12;
        const x1 = to.x + (Math.random() - .5) * 8, y1 = to.y + (Math.random() - .5) * 6;
        const lift = Math.min(160, Math.abs(x1 - x0) * .25 + 60);
        flights.push({ t: 0, delay: i * .035, duration: .62 + Math.random() * .22, x0, y0, x1, y1, cx: (x0 + x1) / 2 + (Math.random() - .5) * 120, cy: Math.min(y0, y1) - lift, size: 1.8 + Math.random() * 1.6, color, arrive: () => { if (!arrived) { arrived = true; arrive?.(); } } });
      }
    }
    addEventListener("resize", () => { if (canvas.isConnected) fit(); });
    return { burst, fly };
  })();

  function resourceColor(id) {
    if (/hp/.test(id)) return token("--hp");
    if (/mp/.test(id)) return token("--mp");
    if (/xp|cultivation/.test(id)) return token("--aura-7");
    if (/stone|spirit|coin/.test(id)) return token("--gold-400");
    return token("--jade-500");
  }

  function pulse(node) {
    if (!node) return;
    node.classList.remove("pulse");
    void node.offsetWidth;
    node.classList.add("pulse");
    setTimeout(() => node.classList.remove("pulse"), 760);
  }

  function animate(node, className) {
    if (!node || reducedMotion()) return;
    node.classList.remove(className);
    void node.offsetWidth;
    node.classList.add(className);
    clearTimeout(node.animateTimer);
    node.animateTimer = setTimeout(() => node.classList.remove(className), 700);
  }

  function celebrate(source, gains) {
    if (!source || reducedMotion()) return;
    const from = { x: source.left + source.width / 2, y: source.top + source.height / 2 };
    fx.burst(from.x, from.y, token("--gold-400"), 14, 110);
    for (const id of gains) {
      const target = [...document.querySelectorAll(".resource")].find((node) => node.dataset.id === id);
      const rect = target?.getBoundingClientRect();
      if (!rect?.width) continue;
      fx.fly(from, { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }, resourceColor(id), 9, () => pulse(target));
    }
  }

  /* 点击涟漪：只加在自身裁切溢出的控件上，不影响分页测量 */
  document.addEventListener("pointerdown", (event) => {
    const target = event.target.closest?.("button, .world-action.has-fields > summary");
    if (!target || target.disabled || reducedMotion() || getComputedStyle(target).overflow !== "hidden") return;
    const rect = target.getBoundingClientRect();
    const ripple = element("span", "ripple");
    ripple.setAttribute("aria-hidden", "true");
    ripple.style.left = `${event.clientX - rect.left}px`;
    ripple.style.top = `${event.clientY - rect.top}px`;
    ripple.style.setProperty("--ripple-scale", String(Math.ceil(Math.hypot(rect.width, rect.height) / 6)));
    target.append(ripple);
    setTimeout(() => ripple.remove(), 560);
  }, { passive: true });

  let lastGains = [];
  let pressed = null;
  let writeSource = null;
  document.addEventListener("pointerdown", (event) => {
    const node = event.target.closest?.("button");
    if (node) pressed = { node, at: performance.now() };
  }, { passive: true, capture: true });
  document.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches?.("button")) pressed = { node: event.target, at: performance.now() };
  }, true);

  /* 成功回执：被执行的事项金光一闪，获得的资源由此飞入 HUD */
  function celebrateWrite(source) {
    if (!source) return;
    let card = null;
    if (source.key) {
      const form = [...document.querySelectorAll(".world-action-form")].find((node) => node.dataset.actionKey === source.key);
      const button = [...document.querySelectorAll(".action-button")].find((node) => node.dataset.actionKey === source.key);
      card = form?.closest(".world-action") || button?.closest(".action-row") || null;
    }
    const rect = card?.getClientRects().length ? card.getBoundingClientRect() : source.rect;
    if (card && !reducedMotion()) {
      card.classList.remove("just-done");
      void card.offsetWidth;
      card.classList.add("just-done");
      setTimeout(() => card.classList.remove("just-done"), 1500);
    }
    celebrate(rect, lastGains);
  }
  function floatNumbers(resources) {
    const current = new Map(resources.map((resource) => [resource.id, Number(resource.value)]));
    lastGains = [];
    if (previousResourceValues && !reducedMotion()) {
      for (const [id, value] of current) {
        const before = previousResourceValues.get(id);
        if (!Number.isFinite(before) || !Number.isFinite(value) || before === value) continue;
        const host = [...document.querySelectorAll(".resource")].find((node) => node.dataset.id === id);
        if (!host) continue;
        const delta = Math.round((value - before) * 1000) / 1000;
        if (delta > 0) lastGains.push(id);
        const float = element("span", `float-num ${delta > 0 ? "gain" : "loss"}`, `${delta > 0 ? "+" : ""}${delta}`);
        float.setAttribute("aria-hidden", "true");
        host.append(float);
        setTimeout(() => float.remove(), 1300);
      }
    }
    previousResourceValues = current;
  }

  /* 槽位：新旧值之间平滑过渡；减少时保留泥金残影，提示本次损失量 */
  function setMeter(meter, percent, previousPercent) {
    let fill = meter.querySelector(":scope > span:not(.meter-ghost)");
    if (!fill) { fill = element("span"); meter.append(fill); }
    let ghost = meter.querySelector(":scope > .meter-ghost");
    if (!ghost) { ghost = element("span", "meter-ghost"); meter.prepend(ghost); }
    const start = Number.isFinite(previousPercent) ? previousPercent : percent;
    if (reducedMotion() || start === percent) {
      fill.style.width = ghost.style.width = `${percent}%`;
      return;
    }
    if (!fill.style.width) { fill.style.width = `${start}%`; ghost.style.width = `${Math.max(start, percent)}%`; }
    else ghost.style.width = `${Math.max(start, percent)}%`;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.style.width = `${percent}%`;
      ghost.style.width = `${percent}%`;
    }));
  }

  function meterPercent(value, max) {
    return max > 0 ? Math.max(0, Math.min(100, value / max * 100)) : 0;
  }

  function syncHudHeight() {
    const hud = $("hud");
    const anchor = hud && !hud.closest("[hidden]") ? hud : document.querySelector(".masthead");
    document.documentElement.style.setProperty("--hud-h", `${Math.round(anchor?.getBoundingClientRect().bottom || 0)}px`);
  }
  if (globalThis.ResizeObserver) new ResizeObserver(syncHudHeight).observe(document.documentElement);

  /* ---------- 人物与敌人立绘：内联 SVG，自制 ---------- */
  const realmOrder = ["炼气", "筑基", "结丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"];

  function realmTier(text) {
    let tier = 0;
    realmOrder.forEach((name, index) => { if (String(text || "").includes(name)) tier = index; });
    return tier;
  }

  function portrait(tier, crop = false) {
    const crown = tier >= 1 ? '<rect class="pt-gold" x="54" y="29" width="12" height="6" rx="2"/>' : "";
    const pin = tier >= 2 ? '<path class="pt-gold-line" d="M46 38 L76 34"/>' : "";
    const orb = tier >= 2 ? '<circle class="pt-orb" cx="98" cy="54" r="7"/><circle class="pt-orb-core" cx="98" cy="54" r="3"/>' : "";
    const halo = tier >= 4 ? '<ellipse class="pt-halo" cx="60" cy="24" rx="20" ry="5"/>' : "";
    const ring = tier >= 3 ? '<circle class="pt-ring2" cx="60" cy="66" r="44"/>' : "";
    const blade = tier >= 1 ? '<path class="pt-blade" d="M20 26 L30 96"/><path class="pt-gold-line" d="M24 84 l12 -2"/>' : "";
    return `<svg class="portrait" data-tier="${tier}" viewBox="${crop ? "22 18 76 76" : "0 0 120 140"}" focusable="false"><circle class="pt-aura" cx="60" cy="66" r="54"/><circle class="pt-ring" cx="60" cy="66" r="50"/>${ring}${halo}${blade}<path class="pt-robe" d="M20 140 C22 102 38 86 60 86 C82 86 98 102 100 140Z"/><path class="pt-robe-shade" d="M60 86 C70 100 72 122 70 140 L50 140 C48 122 50 100 60 86Z"/><path class="pt-collar" d="M49 86 L60 106 L71 86Z"/><path class="pt-sash" d="M28 118 Q60 128 92 118 L92 125 Q60 135 28 125Z"/><rect class="pt-skin" x="55" y="74" width="10" height="12"/><circle class="pt-skin" cx="60" cy="62" r="16"/><path class="pt-hair" d="M43 62 C42 40 78 40 77 62 C72 51 50 50 43 62Z"/><circle class="pt-hair" cx="60" cy="40" r="8"/>${crown}${pin}<path class="pt-eye" d="M52 64 h5 M63 64 h5"/><path class="pt-mouth" d="M57 71 q3 2 6 0"/>${orb}</svg>`;
  }

  const enemyShapes = {
    ape: '<ellipse class="ep-body" cx="60" cy="98" rx="34" ry="30"/><path class="ep-body" d="M28 84 Q8 110 16 136 L26 134 Q24 112 38 96Z M92 84 Q112 110 104 136 L94 134 Q96 112 82 96Z"/><circle class="ep-body" cx="60" cy="56" r="22"/><ellipse class="ep-face" cx="60" cy="62" rx="14" ry="11"/><circle class="ep-eye" cx="54" cy="56" r="3"/><circle class="ep-eye" cx="66" cy="56" r="3"/><path class="ep-dark-line" d="M54 68 q6 4 12 0"/>',
    golem: '<rect class="ep-body" x="26" y="58" width="68" height="70" rx="10"/><rect class="ep-body2" x="38" y="22" width="44" height="38" rx="8"/><rect class="ep-eye" x="46" y="36" width="9" height="7"/><rect class="ep-eye" x="65" y="36" width="9" height="7"/><rect class="ep-body2" x="8" y="66" width="20" height="48" rx="7"/><rect class="ep-body2" x="92" y="66" width="20" height="48" rx="7"/><path class="ep-accent-line" d="M44 78 l14 16 -9 14 M74 74 l-8 12"/>',
    shade: '<path class="ep-shade" d="M60 20 C92 20 100 52 100 82 C100 104 106 120 112 136 C98 128 92 138 82 130 C74 140 66 128 60 136 C54 128 46 140 38 130 C28 138 22 128 8 136 C14 120 20 104 20 82 C20 52 28 20 60 20Z"/><ellipse class="ep-eye" cx="48" cy="62" rx="6" ry="4"/><ellipse class="ep-eye" cx="72" cy="62" rx="6" ry="4"/><path class="ep-wisp" d="M36 92 q24 14 48 0"/>',
    beast: '<path class="ep-body" d="M18 132 C20 98 34 82 60 82 C86 82 100 98 102 132Z"/><path class="ep-body" d="M30 68 L36 26 L52 50 L68 50 L84 26 L90 68 C90 92 76 102 60 102 C44 102 30 92 30 68Z"/><path class="ep-face" d="M48 78 L60 98 L72 78Z"/><path class="ep-eye" d="M42 62 l10 4 -10 2Z M78 62 l-10 4 10 2Z"/><circle class="ep-dark" cx="60" cy="92" r="4"/>',
    serpent: '<path class="ep-body-line" d="M20 128 C40 140 76 136 82 116 C88 96 40 100 38 80 C36 60 74 62 80 44"/><path class="ep-body" d="M66 22 C88 16 104 30 98 46 C94 56 78 58 70 52 C62 46 56 30 66 22Z"/><circle class="ep-eye" cx="86" cy="34" r="3.5"/><path class="ep-accent-line" d="M98 46 l10 6 M98 46 l8 10"/><path class="ep-scale" d="M34 124 h8 M52 128 h8 M70 118 h8 M58 104 h8 M44 88 h8 M58 70 h8"/>',
    fox: '<path class="ep-tail" d="M84 120 C112 112 116 80 100 66 C110 90 96 104 80 108Z M34 120 C8 112 4 82 20 68 C12 92 24 104 40 108Z"/><path class="ep-body" d="M30 136 C32 102 42 88 60 88 C78 88 88 102 90 136Z"/><path class="ep-body" d="M34 70 L38 30 L54 50 L66 50 L82 30 L86 70 C86 90 74 100 60 100 C46 100 34 90 34 70Z"/><path class="ep-face" d="M46 74 C50 92 70 92 74 74 C68 80 52 80 46 74Z"/><path class="ep-eye" d="M44 62 q6 -5 11 1 M76 62 q-6 -5 -11 1"/>',
    human: '<path class="ep-robe" d="M20 140 C22 100 38 84 60 84 C82 84 98 100 100 140Z"/><path class="ep-dark" d="M60 84 L50 140 L70 140Z"/><path class="ep-hood" d="M38 70 C36 36 84 36 82 70 C82 84 74 92 60 92 C46 92 38 84 38 70Z"/><ellipse class="ep-face-dark" cx="60" cy="68" rx="14" ry="15"/><path class="ep-eye" d="M51 66 l7 2 M69 66 l-7 2"/><path class="ep-accent-line" d="M96 30 L84 110"/>',
    spirit: '<path class="ep-flame" d="M60 16 C72 36 90 44 90 74 C90 100 76 116 60 116 C44 116 30 100 30 74 C30 54 44 50 48 30 C54 42 58 40 60 16Z"/><circle class="ep-core" cx="60" cy="82" r="18"/><circle class="ep-eye" cx="53" cy="80" r="3"/><circle class="ep-eye" cx="67" cy="80" r="3"/>'
  };

  // 敌人外形与首领判定：立绘与三维斗法台共用
  function enemyLook(name) {
    const text = String(name || "");
    const kind = /猿|猴|猩/.test(text) ? "ape" : /傀|石|岩|铁|甲/.test(text) ? "golem" : /影|魂|鬼|魅|灵体|怨/.test(text) ? "shade" : /狼|犬|虎|豹|熊|兽|彘|猪/.test(text) ? "beast" : /蛟|龙|蛇|蟒|虺/.test(text) ? "serpent" : /狐|妖|魅/.test(text) ? "fox" : /修|客|弟子|长老|魔|贼|匪|人|士|师|将|使|尊|王|主/.test(text) ? "human" : "spirit";
    return { kind, boss: /王|尊|主|守|首领|精英|劫|归墟/.test(text) };
  }

  // 战报回放的外观线索：只取展示用的境界、灵根、功法与敌人外形，不参与任何结算
  function battleLook(data) {
    const report = data.battle_report, world = report.enemy.kind === "prelude" ? null : data.state?.world;
    const look = enemyLook(report.enemy.name);
    return { tier: realmTier($("realm")?.textContent), root: world?.root?.id || null, skill: world?.skill || "origin", form: look.kind, boss: look.boss };
  }

  function enemyPortrait(name) {
    const { kind, boss } = enemyLook(name);
    return `<svg class="portrait enemy-art" data-kind="${kind}" viewBox="0 0 120 140" focusable="false"><ellipse class="ep-ground" cx="60" cy="134" rx="44" ry="6"/>${boss ? '<circle class="ep-boss" cx="60" cy="70" r="56"/>' : ""}${enemyShapes[kind]}</svg>`;
  }

  function setArt(id, markup) {
    const node = $(id);
    if (node && node.dataset.art !== markup) {
      node.dataset.art = markup;
      node.innerHTML = markup;
    }
  }

  /* ---------- 一屏翻页：内容超出区域时分页，绝不出现滚动条 ---------- */
  const atomic = ".world-action, .r3-goal, .r4-story, .world-data-row, .r3-compare-row, .r3-slot, .r4-credit-strip, .tracked-quest, .action-row, li, .world-page-stats, .field-pair, .r3-battle-statuses, form, p, h3, h4, label, select, button, input, details";
  const pagers = new Map();
  let flipAt = 0;

  function collectAtoms(node, out) {
    for (const child of node.children) {
      if (child.hidden || child.classList.contains("tab-off")) continue;
      if (child.matches(atomic) || !child.matches("section, div, dl, ol, ul") || !child.children.length) out.push(child);
      else collectAtoms(child, out);
    }
    return out;
  }

  function createPager(key, region, host) {
    const control = element("div", "pager-control");
    const prev = element("button", "pager-button");
    const next = element("button", "pager-button");
    const read = element("button", "reader-open", "阅全文");
    prev.type = next.type = read.type = "button";
    prev.setAttribute("aria-label", "上一页");
    next.setAttribute("aria-label", "下一页");
    prev.append(icon("prev"));
    next.append(icon("next"));
    const label = element("span", "pager-label", "1 / 1");
    read.hidden = true;
    control.append(read, prev, label, next);
    host.append(control);
    const pager = { key, region, control, prev, next, label, read, page: 0, pages: [[0, 0]], atoms: [], on: [], chains: [], counts: new Map(), first: new Map(), focus: null, clipped: null };
    pagers.set(key, pager);
    prev.addEventListener("click", () => turnPage(pager, -1));
    next.addEventListener("click", () => turnPage(pager, 1));
    read.addEventListener("click", () => pager.clipped && openReader(pager.clipped));
    region.addEventListener("wheel", (event) => {
      if (pager.pages.length < 2 || Math.abs(event.deltaY) < 4 || event.target.closest("select, .world-action[open]")) return;
      event.preventDefault();
      if (performance.now() - flipAt < 320) return;
      flipAt = performance.now();
      turnPage(pager, event.deltaY > 0 ? 1 : -1);
    }, { passive: false });
    region.addEventListener("keydown", (event) => {
      if (event.key === "PageDown" || event.key === "PageUp") {
        event.preventDefault();
        turnPage(pager, event.key === "PageDown" ? 1 : -1);
      }
    });
    let touch = null;
    region.addEventListener("touchstart", (event) => { touch = [event.touches[0].clientX, event.touches[0].clientY]; }, { passive: true });
    region.addEventListener("touchend", (event) => {
      if (!touch) return;
      const dx = event.changedTouches[0].clientX - touch[0];
      const dy = event.changedTouches[0].clientY - touch[1];
      touch = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) turnPage(pager, dx < 0 ? 1 : -1);
    }, { passive: true });
    region.addEventListener("toggle", (event) => {
      if (event.target.matches(".world-action")) {
        if (event.target.open) region.querySelectorAll(".world-action[open]").forEach((node) => { if (node !== event.target) node.open = false; });
        return;
      }
      paginate(pager, event.target);
    }, true);
    if (globalThis.ResizeObserver) new ResizeObserver(() => schedulePaginate(pager)).observe(region);
    return pager;
  }

  function schedulePaginate(pager) {
    if (!pager || pager.scheduled) return;
    pager.scheduled = true;
    setTimeout(() => {
      pager.scheduled = false;
      paginate(pager);
    }, 30);
  }

  function setAtom(pager, index, visible) {
    if (pager.on[index] === visible) return;
    pager.on[index] = visible;
    pager.atoms[index].classList.toggle("page-off", !visible);
    for (const group of pager.chains[index]) {
      const count = (pager.counts.get(group) || 0) + (visible ? 1 : -1);
      pager.counts.set(group, count);
      group.classList.toggle("page-off", count <= 0);
    }
  }

  function paginate(pager, focusNode) {
    if (!pager) return;
    const { region } = pager;
    if (focusNode) pager.focus = focusNode;
    const height = region.clientHeight;
    if (!region.isConnected || !region.getClientRects().length || !height) return;
    const opened = [...region.querySelectorAll(".world-action[open]")];
    opened.forEach((node) => { node.open = false; });
    region.querySelectorAll(".page-off, .clipped, .continued").forEach((node) => node.classList.remove("page-off", "clipped", "continued"));
    region.scrollTop = 0;
    const atoms = collectAtoms(region, []);
    pager.atoms = atoms;
    pager.on = atoms.map(() => true);
    pager.counts = new Map();
    pager.first = new Map();
    pager.chains = atoms.map((atom, index) => {
      const chain = [];
      for (let node = atom.parentElement; node && node !== region; node = node.parentElement) {
        if (!node.hasAttribute("data-page-group")) continue;
        chain.push(node);
        pager.counts.set(node, (pager.counts.get(node) || 0) + 1);
        if (!pager.first.has(node)) pager.first.set(node, index);
      }
      return chain;
    });
    atoms.forEach((_, index) => setAtom(pager, index, false));
    const pages = [];
    let start = 0;
    for (let index = 0; index < atoms.length; index++) {
      setAtom(pager, index, true);
      if (index > start && region.scrollHeight > height + 1) {
        for (let back = start; back <= index; back++) setAtom(pager, back, false);
        pages.push([start, index]);
        start = index;
        index--;
      }
    }
    for (let back = start; back < atoms.length; back++) setAtom(pager, back, false);
    pages.push([start, atoms.length]);
    pager.pages = pages;
    const focus = pager.focus && region.contains(pager.focus) ? pager.focus : region.contains(document.activeElement) && document.activeElement !== region ? document.activeElement : null;
    pager.focus = null;
    if (focus) {
      const index = atoms.findIndex((atom) => atom.contains(focus) || focus.contains(atom));
      if (index >= 0) pager.page = pages.findIndex(([from, to]) => index >= from && index < to);
    }
    pager.page = Math.max(0, Math.min(pages.length - 1, pager.page));
    showPage(pager);
    opened.forEach((node) => { if (!node.classList.contains("page-off")) node.open = true; });
  }

  function showPage(pager) {
    const [from, to] = pager.pages[pager.page] || [0, 0];
    pager.atoms.forEach((_, index) => setAtom(pager, index, index >= from && index < to));
    for (const [group, index] of pager.first) group.classList.toggle("continued", !pager.on[index] && (pager.counts.get(group) || 0) > 0);
    pager.clipped = null;
    if (to - from === 1 && pager.region.scrollHeight > pager.region.clientHeight + 1) {
      pager.clipped = pager.atoms[from];
      pager.clipped.classList.add("clipped");
    }
    pager.read.hidden = !pager.clipped;
    pager.label.textContent = `${pager.page + 1} / ${pager.pages.length}`;
    pager.prev.disabled = pager.page === 0;
    pager.next.disabled = pager.page >= pager.pages.length - 1;
    pager.control.classList.toggle("single", pager.pages.length < 2 && !pager.clipped);
  }

  function turnPage(pager, delta) {
    const target = Math.max(0, Math.min(pager.pages.length - 1, pager.page + delta));
    if (target === pager.page) return;
    pager.region.querySelectorAll(".world-action[open]").forEach((node) => { node.open = false; });
    const hadFocus = pager.region.contains(document.activeElement);
    pager.page = target;
    showPage(pager);
    animate(pager.region, delta > 0 ? "turn-next" : "turn-prev");
    if (hadFocus) (delta > 0 ? pager.next : pager.prev).focus({ preventScroll: true });
  }

  function guardPagers() {
    for (const pager of pagers.values()) {
      const region = pager.region;
      if (!pager.scheduled && !pager.clipped && region.clientHeight && region.getClientRects().length && region.scrollHeight > region.clientHeight + 1) schedulePaginate(pager);
    }
  }
  document.fonts?.ready.then(() => pagers.forEach(schedulePaginate));
  document.fonts?.addEventListener?.("loadingdone", () => pagers.forEach(schedulePaginate));
  setInterval(guardPagers, 500);

  function pagerFor(node) {
    return [...pagers.values()].find((pager) => pager.region.contains(node));
  }

  function openReader(source) {
    const clone = source.cloneNode(true);
    clone.querySelectorAll("button, input, select, form, .world-action-form").forEach((node) => node.remove());
    for (const node of [clone, ...clone.querySelectorAll("*")]) {
      node.removeAttribute("id");
      node.removeAttribute("hidden");
      node.removeAttribute("class");
      node.removeAttribute("style");
    }
    const parts = [];
    if (!clone.querySelector("p, div, dl, h3, h4, summary, section, ol, ul, li, dt, dd")) {
      for (const sentence of clone.textContent.split(/(?<=[。；！？\n])/)) if (sentence.trim()) parts.push(element("p", "", sentence.trim()));
    } else {
      const box = element("div");
      box.append(...clone.childNodes);
      parts.push(box);
    }
    $("reader-title").textContent = source.querySelector("h3, h4, summary, .world-action-name")?.textContent || source.closest("[data-page-group]")?.querySelector("h3")?.textContent || "全文";
    $("reader-body").replaceChildren(...parts);
    $("reader").hidden = false;
    const pager = pagers.get("reader");
    pager.page = 0;
    paginate(pager);
    $("reader-close").focus({ preventScroll: true });
  }

  function closeReader() {
    $("reader").hidden = true;
    $("reader-body").replaceChildren();
  }

  /* ---------- 舞台页签：此间可为 / 手札 / 要务 / 卷宗 ---------- */
  const stageTabs = new Map();
  const narrowLayout = globalThis.matchMedia?.("(max-width: 759px)");
  let sideTab = "quests";

  function placeAside() {
    const aside = document.querySelector(".world-aside");
    const host = narrowLayout?.matches ? document.querySelector(".side-host") : $("world-content").parentElement;
    if (aside.parentElement !== host) host.append(aside);
    schedulePaginate(pagers.get("side"));
  }

  function activePanelName(key) {
    return key.startsWith("ctx:") ? "context" : key;
  }

  function renderStageTabs(actionCount) {
    const tabs = [["actions", "事项", actionCount]];
    if ($("world-page-stats").children.length || $("world-page-sections").children.length) tabs.push(["notes", "手札"]);
    [...$("r3-page-context").children].forEach((section, index) => {
      section.dataset.tabKey ||= section.id || section.dataset.context || `ctx${index}`;
      tabs.push([`ctx:${section.dataset.tabKey}`, section.dataset.short || section.querySelector("h3")?.textContent.slice(0, 2) || "要务"]);
    });
    tabs.push(["side", "卷宗"]);
    const bar = $("stage-tabs");
    bar.replaceChildren(...tabs.map(([key, label, count]) => {
      const tab = element("button", `stage-tab${key === "side" ? " narrow-only" : ""}`, label);
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.dataset.stageTab = key;
      if (count) tab.append(element("span", "tab-count", String(count)));
      tab.addEventListener("click", () => applyStageTab(key));
      return tab;
    }));
    const stored = stageTabs.get(selectedWorldPage);
    applyStageTab(tabs.some(([key]) => key === stored) && !(stored === "side" && !narrowLayout?.matches) ? stored : "actions");
  }

  function applyStageTab(key, focusNode) {
    const changed = stageTabs.get(selectedWorldPage) !== key;
    stageTabs.set(selectedWorldPage, key);
    const panelName = activePanelName(key);
    if (changed) animate(document.querySelector(`[data-stage-panel="${panelName}"]`), "panel-in");
    document.querySelectorAll("[data-stage-panel]").forEach((panel) => panel.classList.toggle("tab-off", panel.dataset.stagePanel !== panelName));
    for (const section of $("r3-page-context").children) section.classList.toggle("tab-off", `ctx:${section.dataset.tabKey}` !== key);
    $("stage-tabs").querySelectorAll("[data-stage-tab]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.stageTab === key));
      tab.tabIndex = tab.dataset.stageTab === key ? 0 : -1;
    });
    for (const name of ["actions", "notes", "context"]) pagers.get(name).control.classList.toggle("tab-off", name !== panelName);
    $("world-action-count").classList.toggle("tab-off", panelName !== "actions");
    if (panelName === "side") applySideTab(sideTab);
    else paginate(pagers.get(panelName), focusNode);
  }

  function applySideTab(key, focusNode) {
    sideTab = key;
    document.querySelectorAll("[data-side]").forEach((section) => section.classList.toggle("tab-off", section.dataset.side !== key));
    document.querySelectorAll("[data-side-tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.sideTab === key)));
    paginate(pagers.get("side"), focusNode);
  }

  function revealNode(node) {
    if (!node?.isConnected) return;
    const group = node.closest(".action-group[hidden]");
    if (group) document.querySelector(`[data-group="${group.id.replace("group-", "")}"]`)?.click();
    const side = node.closest("[data-side]");
    if (side && side.dataset.side !== sideTab) applySideTab(side.dataset.side, node);
    const panel = node.closest("[data-stage-panel]");
    if (panel && panel.classList.contains("tab-off")) {
      const section = node.closest("#r3-page-context > *");
      applyStageTab(panel.dataset.stagePanel === "context" && section ? `ctx:${section.dataset.tabKey}` : panel.dataset.stagePanel, node);
    } else if (panel?.dataset.stagePanel === "context") {
      const section = node.closest("#r3-page-context > *");
      if (section?.classList.contains("tab-off")) applyStageTab(`ctx:${section.dataset.tabKey}`, node);
    }
    const pager = pagerFor(node);
    if (pager) paginate(pager, node);
  }
  document.addEventListener("guixu:reveal", (event) => revealNode(event.target));
  document.addEventListener("scroll", (event) => {
    const target = event.target === document ? document.scrollingElement : event.target;
    if (!target || target.matches?.("input, textarea, select")) return;
    if (target.scrollTop || target.scrollLeft) { target.scrollTop = 0; target.scrollLeft = 0; }
  }, true);

  let noticeTimer = 0;
  function notice(message, kind = "", retry = false, refresh = false) {
    clearTimeout(noticeTimer);
    // 成功回执 6 秒后自动收起（文字保留供读屏回看），错误与待确认提示保持常驻直到下一次操作
    if (message && kind === "success") noticeTimer = setTimeout(() => { $("notice").hidden = true; }, 6000);
    $("notice").hidden = !message;
    $("notice").className = `notice ${kind}`;
    $("notice-text").textContent = message;
    $("retry-button").hidden = !retry;
    $("refresh-button").hidden = !refresh;
    updateControls();
  }

  function updateControls() {
    const locked = busy || !!pending || !snapshot || !storageAvailable || offline || authLocked;
    const exists = !!snapshot?.view?.character;
    $("new-button").disabled = locked || !exists;
    $("create-button").disabled = locked;
    $("retry-button").disabled = busy || !pending;
    $("refresh-button").disabled = busy || authLocked;
    $("logout-button").disabled = busy;
    $("password-button").disabled = busy || offline;
    $("name").disabled = locked;
    $("mode").disabled = locked;
    document.querySelectorAll(".action-button").forEach((button) => {
      button.disabled = locked || button.dataset.enabled !== "true";
    });
    document.querySelectorAll(".world-write").forEach((control) => {
      control.disabled = locked || control.dataset.enabled !== "true";
    });
    $("main").setAttribute("aria-busy", String(busy));
  }

  function renderResources(resources) {
    $("resources").replaceChildren();
    for (const resource of resources) {
      const wrapper = element("div", `resource${resource.max === null || resource.max >= 9999 ? " chip" : ""}`);
      wrapper.dataset.id = resource.id;
      const top = element("div", "resource-top");
      top.append(element("span", "resource-label", resource.label.replace(/^凡界/, "")));
      const value = element("span", "resource-value", resource.value);
      if (resource.max !== null) value.append(element("small", "", `/ ${resource.max}`));
      top.append(value);
      wrapper.append(top);
      if (resource.max !== null) {
        const meter = element("div", "meter");
        meter.setAttribute("role", "progressbar");
        meter.setAttribute("aria-label", resource.label);
        meter.setAttribute("aria-valuemin", "0");
        meter.setAttribute("aria-valuemax", String(resource.max));
        meter.setAttribute("aria-valuenow", String(Math.max(0, Math.min(resource.max, resource.value))));
        meter.setAttribute("aria-valuetext", `${resource.label} ${resource.value} / ${resource.max}`);
        wrapper.append(meter);
        $("resources").append(wrapper);
        const before = previousResourceValues?.get(resource.id);
        setMeter(meter, meterPercent(resource.value, resource.max), Number.isFinite(before) ? meterPercent(before, resource.max) : undefined);
        meter.classList.toggle("low", /hp/.test(resource.id) && resource.max > 0 && resource.value / resource.max < .3);
        continue;
      }
      $("resources").append(wrapper);
    }
  }

  function setBattleMeter(meter, hp, max) {
    const previous = parseFloat(meter.querySelector(":scope > span:not(.meter-ghost)")?.style.width);
    setMeter(meter, meterPercent(hp, max), Number.isFinite(previous) ? previous : undefined);
    meter.classList.toggle("low", max > 0 && hp / max < .3);
  }

  function renderActions(actions) {
    const focusedKey = document.activeElement?.dataset?.actionKey;
    $("actions").replaceChildren();
    $("action-tabs").replaceChildren();
    const groups = new Map();
    if (snapshot.view.phase !== "battle") {
      const navigation = $("action-tabs");
      navigation.setAttribute("aria-label", "选择行动分类");
      const place = snapshot.view.location?.name || "此地";
      // 标签只写"这一栏能做什么"：地区=换地方，首领=打架，其余为日常。
      for (const [key, label, title, hint] of [
        ["cultivation", "修炼", "修炼 · 突破境界、调息、炼丹、研习功法", "突破境界、静养调息、炼丹、研习功法"],
        ["exploration", "探索", `探索 · 在${place}采集药草、探访寻宝`, "采集药草、探访此地获得灵石"],
        ["travel", "地区", `地区 · 现在身处${place}，可前往其他地方`, "切换所在地区，境界足够才能前往更深处"],
        ["challenge", "首领", `首领 · ${place}的妖兽与守关者`, "挑战当地妖兽与首领，首胜是突破的前提"],
        ["trade", "买卖", "买卖 · 出售药草、购买回春丹", "用药草与灵石买卖物资"],
      ]) {
        const group = element("section", `action-group group-${key}`);
        group.id = `group-${key}`;
        group.hidden = key !== selectedGroup;
        group.append(element("h3", "action-group-title", title));
        groups.set(key, group);
        group.dataset.pageGroup = "";
        const choice = element("button", "group-button stage-tab", label);
        choice.title = hint;
        choice.type = "button";
        choice.dataset.group = key;
        choice.setAttribute("aria-pressed", String(key === selectedGroup));
        choice.setAttribute("aria-controls", group.id);
        choice.addEventListener("click", () => {
          selectedGroup = key;
          for (const [id, section] of groups) section.hidden = id !== key;
          navigation.querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.group === key)));
          const pager = pagers.get("journey");
          pager.page = 0;
          paginate(pager);
          updateJourneyCount();
        });
        navigation.append(choice);
      }
    }
    for (const [index, action] of actions.entries()) {
      const row = element("div", `action-row${action.group === "battle" || battleActionIds.has(action.id) ? " battle-row" : ""}`);
      const copy = element("div", "action-copy");
      const title = element("h4", "action-title", action.label);
      title.id = `action-title-${index}`;
      copy.append(title);
      row.title = action.detail;
      const meta = element("p", "action-meta");
      meta.append(element("span", "cost", `消耗 · ${action.cost}`), element("span", "effect", `所得 · ${action.effect}`));
      copy.append(meta);
      const reason = element("p", "action-reason", action.reason || "");
      reason.id = `action-reason-${index}`;
      reason.hidden = action.enabled;
      copy.append(reason);
      const button = element("button", `action-button${action.primary ? " primary" : ""}`);
      button.append(element("span", "btn-label", action.group === "battle" || battleActionIds.has(action.id) ? "出手" : action.id === "challenge" ? "迎战" : action.id === "travel" ? "前往" : "施行"));
      button.setAttribute("aria-label", action.label);
      button.type = "button";
      button.dataset.enabled = String(action.enabled);
      button.dataset.action = action.id;
      button.dataset.params = JSON.stringify(action.params);
      button.dataset.actionKey = `${action.id}:${JSON.stringify(action.params)}`;
      button.setAttribute("aria-describedby", reason.id);
      button.addEventListener("click", () => beginWrite("/api/action", { action: action.id, params: action.params }));
      row.append(copy, button);
      const fallback = ["buy_pill", "sell_herbs"].includes(action.id) ? "trade" : action.id === "travel" ? "travel" : action.id === "challenge" ? "challenge" : ["explore", "gather"].includes(action.id) ? "exploration" : "cultivation";
      const group = groups.get(action.group) || groups.get(fallback);
      if (action.id === "world_enter") {
        row.classList.add("world-entry-action");
        row.hidden = !action.enabled;  // 序章未完成时不占位：目标栏已说明条件，避免每个标签顶着一张锁住的卡
        if (action.enabled) button.classList.add("primary");
        $("actions").prepend(row);
      } else if (group) group.append(row);
      else $("actions").append(row);
    }
    for (const [key, group] of groups) {
      if (group.children.length > 1) $("actions").append(group);
      // 修为圆满、可以突破时，在「修炼」标签上亮一点提示
      $("action-tabs").querySelector(`[data-group="${key}"]`)?.classList.toggle("ready", !!group.querySelector('.action-button.primary[data-action="breakthrough"]:not([data-enabled="false"])'));
    }
    if (!actions.length) $("actions").append(element("p", "muted", "此刻暂无可执行的行动。"));
    updateControls();
    paginate(pagers.get("journey"));
    updateJourneyCount();
    if (focusedKey) {
      const target = [...document.querySelectorAll(".action-button")].find((button) => button.dataset.actionKey === focusedKey && !button.disabled);
      if (target) target.focus({ preventScroll: true });
    }
  }

  function updateJourneyCount() {
    const rows = [...$("actions").querySelectorAll(".action-row")].filter((row) => !row.closest("[hidden]"));
    $("journey-count").textContent = rows.length ? `${rows.length} 项行动` : "";
  }

  function renderLogs(logs) {
    const visible = [...logs].reverse().slice(0, expanded ? logs.length : 12);
    $("logs").replaceChildren(...visible.map(logItem));
    $("empty-logs").hidden = logs.length > 0;
    $("history-button").hidden = logs.length <= 12;
    $("history-button").textContent = expanded ? "收起早先记事" : `更多记事（${logs.length - 12}）`;
    const pager = pagers.get("chronicle");
    pager.page = 0;
    paginate(pager);
  }

  function worldActionKey(page, action) {
    return `${page}:${action.id}:${JSON.stringify(action.params)}`;
  }

  function isLonglineWorld() {
    return snapshot?.view.profile?.mode === "longline" && snapshot?.view.world?.active === true;
  }

  function growthNumber(value) {
    return new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(value);
  }

  function localTime(seconds) {
    return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(seconds * 1000));
  }

  function anchorGrowth(growth) {
    if (!growth?.active) {
      growthAnchor = null;
      $("growth-panel").hidden = true;
      return;
    }
    growthAnchor = { ...growth, receivedAt: performance.now() };
    $("growth-panel").hidden = false;
    const last = growth.last_settled;
    $("growth-offline-summary").textContent = last === null || last === undefined ? "入世后开始连续潜修；查看与离线均不要求额外领取。" : `上次结算 ${localTime(last)} → 本次校正 ${localTime(growth.server_now)}，持续修为 +${growthNumber(Number(growth.offline_gain || 0))}。这是已享有的增长，下一次写入时原子保存。`;
    const sources = element("dl", "world-rows");
    const bonus = snapshot?.view.world?.loot?.speed_bonus_bp;
    for (const [label, value] of [["持续修炼", `${growthNumber(Number(growth.rate?.per_day || 0))} / 24小时`], ["当前装备增益", Number.isFinite(bonus) ? `${(bonus / 100).toFixed(2)}% · 法宝与其他来源相加` : "按服务端当前境界与已装备效果结算"], ["收益来源", "副本/活动产出装备法宝和材料，不直接发修为"]]) {
      const line = element("div", "world-data-row");
      line.append(element("dt", "", label), element("dd", "", value));
      sources.append(line);
    }
    if (growth.migrated_from) {
      const line = element("div", "world-data-row");
      line.append(element("dt", "", "旧版进度衔接"), element("dd", "", "已保留境界与资产；未封界阶段按新版目标保留完成比例，迁移时已封界的潜修储备保持原余额。"));
      sources.append(line);
    }
    $("growth-sources").replaceChildren(sources);
    tickGrowth();
  }

  function anchorCredits(credits) {
    creditsAnchor = credits ? { ...credits, receivedAt: performance.now() } : null;
    tickCredits();
  }

  function tickCredits() {
    const node = $("r4-credits");
    if (!node || !creditsAnchor) return;
    const credit = creditsAnchor;
    $("r4-credits-balance").textContent = `副本资格 ${credit.available} / ${credit.capacity} · 预约 ${credit.reserved} · 每8小时恢复1`;
    const remaining = credit.next_at === null ? null : Math.max(0, Number(credit.next_at) - Number(credit.server_now) - (performance.now() - credit.receivedAt) / 1000);
    let text = credit.status || "";
    if (credit.clock_rewound) text += " 系统时间待校正，恢复以服务端为准。";
    else if (remaining !== null) {
      const seconds = Math.ceil(remaining);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor(seconds % 3600 / 60);
      text += seconds > 0 ? ` 下次恢复 ${localTime(credit.next_at)} · 余 ${hours}时${minutes}分${seconds % 60}秒。` : " 等待服务端确认恢复。";
      if (seconds === 0 && performance.now() - creditsRefreshAt > 15000) {
        creditsRefreshAt = performance.now();
        refreshGrowth();
      }
    }
    $("r4-credits-status").textContent = text;
  }

  function tickGrowth() {
    tickCredits();
    if (!growthAnchor || $("growth-panel").hidden) return;
    const elapsed = Math.max(0, (performance.now() - growthAnchor.receivedAt) / 1000);
    const waiting = Math.max(0, Number(growthAnchor.last_settled || 0) - Number(growthAnchor.server_now));
    const seconds = growthAnchor.clock_rewound || pending ? 0 : Math.max(0, elapsed - waiting);
    const perHour = Number(growthAnchor.rate?.per_hour || 0);
    const available = Number(growthAnchor.available || 0) + seconds * perHour / 3600;
    $("growth-available").textContent = growthNumber(available);
    $("growth-rate").textContent = `${growthNumber(perHour)} / 小时 · 持续增长，无需领取`;
    const progress = snapshot?.view.world?.loot?.progress;
    const target = Number(progress?.required || 0);
    $("growth-milestone").textContent = progress ? `${progress.stage_label} · ${progress.milestone_label}` : "潜修仍在积累，目标条件以人物页为准。";
    $("growth-conditions").textContent = progress?.conditions || "等候突破时仍增长；不自动突破，不追溯应用新装备速率。";
    const meter = $("growth-progress");
    meter.hidden = !(target > 0);
    if (target > 0) {
      meter.setAttribute("aria-valuemin", "0");
      meter.setAttribute("aria-valuemax", String(target));
      meter.setAttribute("aria-valuenow", String(Math.max(0, Math.min(target, available))));
      meter.setAttribute("aria-valuetext", `${growthNumber(available)} / ${growthNumber(target)}`);
      meter.firstElementChild.style.width = `${Math.max(0, Math.min(100, available / target * 100))}%`;
      $("growth-eta").textContent = growthAnchor.clock_rewound ? "系统时间早于结算水位，待时钟恢复后再校正预计时刻。" : available >= target ? progress?.ready ? `修为与条件已齐，可前往办理${progress.next_label}。` : "修为已足；仍需核对下方材料、守关与剧情条件。" : perHour > 0 ? `按当前境界与装备速率，预计 ${localTime(Number(growthAnchor.server_now) + elapsed + (target - available) / perHour * 3600)} 修为足够；条件变化后重算。` : "当前暂无可用速率，等待服务端校正。";
    } else $("growth-eta").textContent = "潜修储备继续增长，不解锁未开放的仙界。";
    $("growth-sync-status").textContent = newRevisionObserved ? "其他页面已改变进度，请重新读取后办理事项。" : growthAnchor.clock_rewound || waiting > elapsed ? "系统时间早于结算水位；已结算修为保留，未结算预估按服务端时间校正，显示不继续外推。" : pending ? "操作结果待确认，暂保留最后校正值；使用原操作编号重试。" : elapsed > 35 ? "暂未取得最新校正，当前数字按上次速率估算；提交以服务端为准。" : "按服务端锚点平滑显示，每15秒只读校正；提交以服务端结算为准。";
    const resource = document.querySelector('.resource[data-id="world_xp"] .resource-value');
    if (resource?.firstChild?.nodeType === Node.TEXT_NODE) resource.firstChild.textContent = growthNumber(available);
  }

  function contextSection(title, intro, short) {
    const section = element("section", "r3-context-section");
    section.dataset.pageGroup = "";
    if (short) section.dataset.short = short;
    section.append(element("h3", "", title));
    if (intro) section.append(element("p", "r3-context-intro", intro));
    return section;
  }

  function contextRows(rows) {
    const list = element("dl", "world-rows");
    for (const row of rows) {
      const line = element("div", "world-data-row");
      line.append(element("dt", "", row.label), element("dd", "", row.value));
      list.append(line);
    }
    return list;
  }

  function fieldPair(label, select) {
    const pair = element("div", "field-pair");
    pair.append(label, select);
    return pair;
  }

  function findItemActions(uid) {
    worldActionFilters.set(selectedWorldPage, { query: uid });
    $("world-action-search").value = uid;
    applyStageTab("actions");
    filterWorldActions();
    $("world-actions-title").focus({ preventScroll: true });
  }

  function revealWorldAction(pageId, actionId, params = {}) {
    const page = snapshot?.view.world?.pages.find((entry) => entry.id === pageId);
    const action = page?.actions.find((entry) => entry.id === actionId && Object.entries(params).every(([key, value]) => entry.params[key] === value));
    if (!action) {
      notice("该目标事项已变化，请重新读取当前进度后查看。", "", false, true);
      return;
    }
    worldActionFilters.set(pageId, { query: "" });
    selectWorldPage(pageId);
    const form = [...document.querySelectorAll(".world-action-form")].find((entry) => entry.dataset.actionKey === worldActionKey(pageId, action));
    if (!form) return;
    revealNode(form);
    const details = form.closest("details");
    if (details) details.open = true;
    form.querySelector(".world-submit")?.focus({ preventScroll: true });
  }

  function renderR3Context(world) {
    const root = $("r3-page-context");
    root.replaceChildren();
    $("stage-chips").replaceChildren();
    const loot = world.loot;
    $("r4-dungeon-jump").hidden = !(selectedWorldPage === "exploration" && loot?.dungeons?.length);
    if (!loot || loot.mode !== "longline") return;
    if (["world", "exploration"].includes(selectedWorldPage) && loot.credits) {
      const section = element("section", "r4-credit-strip");
      section.id = "r4-credits";
      section.append(element("strong", "r4-credits-balance", ""), element("p", "quiet-note", ""));
      section.querySelector("strong").id = "r4-credits-balance";
      section.querySelector("p:last-child").id = "r4-credits-status";
      section.dataset.short = "资格";
      (selectedWorldPage === "world" ? $("stage-chips") : root).append(section);
      anchorCredits(loot.credits);
    }
    if (selectedWorldPage === "world" && world.goals?.length) {
      const section = contextSection("今日行道 · 从真实缺口出发", "以下目标按当前装备、材料与挑战条件选择。只定位真实事项，不自动接取或提交，也不是强制打卡。 ", "目标");
      section.id = "r3-goals";
      const list = element("div", "r3-goal-list");
      list.id = "r3-goal-list";
      for (const goal of world.goals) {
        const row = element("div", "r3-goal");
        row.dataset.goalId = goal.id;
        const copy = element("div");
        copy.append(element("h4", "r3-goal-title", goal.title), element("p", "r3-goal-reason", goal.reason));
        const button = element("button", "secondary-button r3-goal-button", "查看此事项 →");
        button.type = "button";
        button.dataset.goalId = goal.id;
        button.dataset.targetPage = goal.page || goal.target_page;
        button.addEventListener("click", () => {
          const current = snapshot?.view.world?.goals?.find((entry) => entry.id === goal.id);
          if (current?.action) revealWorldAction(current.page || current.target_page, current.action.id, current.action.params);
        });
        row.append(copy, button);
        list.append(row);
      }
      section.append(list);
      root.append(section);
    }
    if (["world", "quests"].includes(selectedWorldPage) && world.journey?.layers?.length) {
      const section = contextSection("初涉仙途 · 七段行纪", "建议日序用于引路，不按日历锁定；前段领奖与境界条件满足后可继续，接取后计数，完成权益不过期。", "行纪");
      section.id = "r4-journey";
      let currentStoryOpened = false;
      for (const layer of world.journey.layers) {
        const row = element("details", "r4-story");
        row.dataset.storyId = layer.id;
        const heading = element("summary", "", `${layer.recommended_day === 0 ? "建议首日" : `建议第${layer.recommended_day + 1}日`} · ${layer.title} · ${layer.status}`);
        row.append(heading, element("p", "quiet-note", layer.unlock), contextRows(layer.objectives || []), element("p", "quiet-note", `奖励：${layer.rewards}`));
        const projected = world.pages?.find((page) => page.id === "quests")?.actions?.find((action) => action.id === layer.action?.id && JSON.stringify(action.params) === JSON.stringify(layer.action?.params));
        if (projected && !currentStoryOpened) { row.classList.add("current"); currentStoryOpened = true; }
        if (projected) {
          const button = element("button", "secondary-button", "查看此段接取 / 领奖事项 →");
          button.type = "button";
          button.dataset.storyAction = layer.id;
          button.addEventListener("click", () => revealWorldAction("quests", layer.action.id, layer.action.params));
          row.append(button);
        }
        section.append(row);
      }
      root.append(section);
    }
    if (selectedWorldPage === "exploration" && world.journey?.elites?.length) {
      const section = contextSection("首周精英 · 三地试炼", "独立NPC精英，不消耗副本恢复资格；具体解锁、风险与奖励以当前投影为准。", "精英");
      section.id = "r4-elites";
      for (const elite of world.journey.elites) {
        const row = element("details", "r4-story");
        row.dataset.eliteId = elite.id;
        row.append(element("summary", "", `${elite.title} · ${elite.status}`), element("p", "quiet-note", elite.preparation), element("p", "quiet-note", `奖励：${elite.rewards}`));
        if (elite.action) {
          const button = element("button", "secondary-button", "查看精英挑战事项 →");
          button.type = "button";
          button.dataset.eliteAction = elite.id;
          button.addEventListener("click", () => revealWorldAction("exploration", elite.action.id, elite.action.params));
          row.append(button);
        }
        section.append(row);
      }
      root.append(section);
    }
    if (selectedWorldPage === "character") {
      const section = contextSection("器物与法宝", "三器奠基，两宝定道。比较来自服务端；修炼向提高未来潜修，战力向帮助挑战更高难度。 ", "器物");
      const slots = element("div", "r3-slots");
      for (const [id, label] of [["weapon", "兵器"], ["armor", "护甲"], ["pendant", "灵佩"], ["main", "本命法宝"], ["guard", "护持法宝"]]) {
        const item = loot.items.find((entry) => entry.slot === id && entry.equipped);
        const line = element("div", "r3-slot");
        line.dataset.slot = id;
        if (item && qualityNames.includes(item.quality)) line.dataset.q = String(qualityNames.indexOf(item.quality));
        const note = element("span", "quiet-note", item ? ` · 强化 ${item.enhance} · ${displayEffectType(item.effect_type)}` : "从副本掉落或四艺保底制作取得");
        if (item) note.prepend(qualityBadge(item.quality));
        line.append(element("span", "section-number", label), element("strong", "", item?.name || "当前为空槽"), note);
        slots.append(line);
      }
      section.append(slots);
      if (loot.capacity) section.append(element("p", "quiet-note", `实例背包 ${loot.capacity.used} / ${loot.capacity.max}；修炼加成 ${Number(loot.speed_bonus_bp / 100).toFixed(2)}%，最多15%。`));
      if (loot.items.length) {
        if (!loot.items.some((item) => item.uid === selectedLootUid)) selectedLootUid = loot.items[0].uid;
        const label = element("label", "", "选择物品，比较当前同槽装备");
        label.htmlFor = "r3-item-select";
        const select = element("select", "r3-select");
        select.id = "r3-item-select";
        for (const item of loot.items) {
          const option = element("option", "", `${item.name} · ${item.quality} · ${item.uid}${item.equipped ? " · 已装备" : ""}`);
          option.value = item.uid;
          select.append(option);
        }
        select.value = selectedLootUid;
        const detail = element("div", "r3-item-detail");
        const show = () => {
          const item = loot.items.find((entry) => entry.uid === select.value);
          if (!item) return;
          selectedLootUid = item.uid;
          const intro = element("p", "r3-context-intro", ` · 章节 ${item.chapter} · 强化 ${item.enhance} · ${displayEffectType(item.effect_type)} · ${item.equipped ? "已装备" : "未装备"}`);
          intro.prepend(qualityBadge(item.quality));
          detail.replaceChildren(element("h4", "", item.name), intro);
          const compare = element("div", "r3-comparison");
          for (const row of item.comparison || []) {
            const line = element("div", "r3-compare-row");
            line.append(element("span", "", row.label), element("span", "", `当前 ${row.before}`), element("strong", "", `换装后 ${row.after}`), element("span", "r3-delta", `变化 ${row.delta}`));
            compare.append(line);
          }
          detail.append(compare, element("p", "quiet-note", `来源：${item.source || "服务端未提供来源"}`));
          const jump = element("button", "secondary-button", "查看此物品的装备、强化、提质或分解事项 →");
          jump.type = "button";
          jump.addEventListener("click", () => findItemActions(item.uid));
          detail.append(jump);
        };
        select.addEventListener("change", () => { show(); paginate(pagers.get("context"), detail); });
        section.append(fieldPair(label, select), detail);
        show();
      } else section.append(element("p", "muted", "暂无实例装备。完成有掉落资格的副本，或从四艺保底制作起步。"));
      root.append(section);
    }
    if (["exploration", "world"].includes(selectedWorldPage) && loot.boss) {
      const boss = loot.boss;
      const section = contextSection("世界Boss · 十二回合试锋", "NPC模拟 · 不要求击杀。每期最多3次正式挑战，取单场最佳，不累计多场伤害；奖励只补已得权益的差额。 ", "首领");
      section.dataset.context = "world-boss";
      section.append(contextRows([{ label: "本期", value: boss.encounter }, { label: "正式尝试", value: boss.attempts }, { label: "本次有效伤害", value: boss.current_damage }, { label: "个人单场最佳", value: boss.best }, { label: "本期参考伤害", value: boss.reference }, { label: "已领奖权益", value: boss.paid }, { label: "下一档 / 差额", value: boss.next }, { label: "结算与封顶", value: boss.status }]));
      root.append(section);
    }
    if (selectedWorldPage === "exploration" && loot.dungeons?.length) {
      const section = contextSection("副本筹备 · 难度与战利品", "同章同难手战获胜后可快捷结算；无资格手战仍有普通材料与灵石。 ", "副本");
      section.id = "r4-dungeon-workbench";
      const label = element("label", "", "选择副本章节与难度，查看权威预览");
      label.htmlFor = "r3-dungeon-select";
      const select = element("select", "r3-select");
      select.id = "r3-dungeon-select";
      const keyFor = (entry) => JSON.stringify([entry.id, entry.chapter, entry.difficulty]);
      if (!loot.dungeons.some((entry) => keyFor(entry) === selectedDungeonKey)) selectedDungeonKey = keyFor(loot.dungeons[0]);
      for (const entry of loot.dungeons) {
        const option = element("option", "", `${entry.name} · 章节 ${entry.chapter} · 难度 ${entry.difficulty}`);
        option.value = keyFor(entry);
        select.append(option);
      }
      select.value = selectedDungeonKey;
      const detail = element("div", "r3-dungeon-detail");
      const show = () => {
        const entry = loot.dungeons.find((item) => keyFor(item) === select.value);
        if (!entry) return;
        selectedDungeonKey = select.value;
        detail.replaceChildren(contextRows([{ label: "条件与风险", value: entry.conditions }, { label: "有资格通关奖励", value: entry.rewards }, { label: "本次共享资格", value: entry.eligible }, { label: "确定保底", value: entry.pity }, { label: "终Boss机制与反制", value: entry.mechanic || "具体意图与状态以当前战斗权威预告为准。" }]));
        const jump = element("button", "secondary-button", "查看此难度的入场事项 →");
        jump.type = "button";
        jump.addEventListener("click", () => revealWorldAction("exploration", "world_dungeon_enter", { dungeon: entry.id, chapter: entry.chapter, difficulty: entry.difficulty }));
        detail.append(jump);
        if (entry.sweep) {
          const sweep = element("div", "r4-sweep");
          sweep.append(element("h4", "", "熟练快捷结算"), contextRows([{label: "消耗", value: entry.sweep.consume}, {label: "结算预览", value: entry.sweep.preview}, {label: "当前条件", value: entry.sweep.enabled ? "同章同难手战证明与其他条件已满足" : entry.sweep.reason}]));
          const shortcut = element("button", "secondary-button", "查看快捷结算事项 →");
          shortcut.type = "button";
          shortcut.id = "r4-sweep-jump";
          shortcut.addEventListener("click", () => {
            const current = snapshot?.view.world?.loot?.dungeons?.find((item) => keyFor(item) === selectedDungeonKey);
            if (current?.sweep?.action) revealWorldAction("exploration", current.sweep.action.id, current.sweep.action.params);
          });
          sweep.append(shortcut);
          detail.append(sweep);
        }
      };
      select.addEventListener("change", () => { show(); paginate(pagers.get("context"), detail); });
      section.append(fieldPair(label, select), detail);
      show();
      root.append(section);
    }
    if (["character", "craft", "exploration"].includes(selectedWorldPage) && loot.materials?.length) {
      const section = contextSection("养成资材", "材料、法宝与装备提高后续效率或战力，不直接兑换无限修为。 ", "资材");
      section.append(contextRows(loot.materials));
      root.append(section);
    }
    if (["character", "exploration", "market"].includes(selectedWorldPage) && loot.pending?.length) {
      const section = contextSection("待领战利品", "容量不足的完整奖励保留待领；实际领取仍由事项页对应操作原子完成。 ", "待领");
      section.append(contextRows(loot.pending.map((item) => ({ label: `${item.label} · ${item.id}`, value: item.source }))));
      root.prepend(section);
    }
    if (selectedWorldPage === "world" && $("r3-goals")) root.prepend($("r3-goals"));
    if (selectedWorldPage === "exploration" && $("r4-dungeon-workbench")) {
      root.prepend($("r4-dungeon-workbench"));
      if ($("r4-credits")) $("r4-dungeon-workbench").insertBefore($("r4-credits"), $("r4-dungeon-workbench").querySelector(".field-pair"));
    }
  }

  function displayEffectType(type) {
    return { cultivation: "修炼向", combat: "战力向", equipment: "战斗装备" }[type] || type || "普通装备";
  }

  function updateR3ReadOnly() {
    const loot = snapshot?.view.world?.loot;
    if (!loot) return;
    anchorCredits(loot.credits);
    const boss = loot.boss;
    const values = boss ? [boss.encounter, boss.attempts, boss.current_damage, boss.best, boss.reference, boss.paid, boss.next, boss.status] : [];
    document.querySelectorAll('[data-context="world-boss"] .world-data-row dd').forEach((node, index) => {
      if (values[index] !== undefined) node.textContent = values[index];
    });
    const selected = loot.dungeons?.find((entry) => JSON.stringify([entry.id, entry.chapter, entry.difficulty]) === $("r3-dungeon-select")?.value);
    const preview = selected ? [selected.conditions, selected.rewards, selected.eligible, selected.pity, selected.mechanic || "具体意图与状态以当前战斗权威预告为准。"] : [];
    document.querySelectorAll(".r3-dungeon-detail > .world-rows .world-data-row dd").forEach((node, index) => {
      if (preview[index] !== undefined) node.textContent = preview[index];
    });
    const sweepValues = selected?.sweep ? [selected.sweep.consume, selected.sweep.preview, selected.sweep.enabled ? "同章同难手战证明与其他条件已满足" : selected.sweep.reason] : [];
    document.querySelectorAll(".r4-sweep .world-data-row dd").forEach((node, index) => { if (sweepValues[index] !== undefined) node.textContent = sweepValues[index]; });
    document.querySelectorAll(".r3-goal").forEach((row) => {
      const goal = snapshot.view.world.goals?.find((entry) => entry.id === row.dataset.goalId);
      if (!goal) { row.hidden = true; return; }
      row.hidden = false;
      row.querySelector(".r3-goal-title").textContent = goal.title;
      row.querySelector(".r3-goal-reason").textContent = goal.reason;
      row.querySelector("button").dataset.targetPage = goal.page || goal.target_page;
    });
  }

  function renderWorldStats(stats) {
    const entries = (stats || []).filter((stat) => !(isLonglineWorld() && stat.label === "修为"));
    $("world-page-stats").replaceChildren();
    for (const stat of entries) {
      const block = element("div", "world-stat");
      block.append(element("dt", "", stat.label), element("dd", "", stat.value));
      $("world-page-stats").append(block);
    }
    $("world-page-stats").hidden = !entries.length;
  }

  function patchWorldText() {
    const world = snapshot?.view.world;
    const page = world?.pages.find((entry) => entry.id === selectedWorldPage);
    if (!page) return;
    $("world-page-title").textContent = page.title;
    $("world-page-description").textContent = page.description;
    renderWorldStats(page.stats);
    const blocks = [...$("world-page-sections").children];
    for (const section of page.sections || []) {
      const key = section.id || section.title;
      let block = blocks.find((node) => node.dataset.sectionKey === key);
      if (!block) {
        block = element("section", "world-section");
        block.dataset.sectionKey = key;
        block.dataset.pageGroup = "";
        if (section.id) block.dataset.sectionId = section.id;
        block.append(element("h3", "", section.title));
        $("world-page-sections").append(block);
      }
      block.hidden = false;
      block.querySelector("h3").textContent = section.title;
      let body = block.querySelector(".world-section-body");
      if (section.body && !body) {
        body = element("p", "world-section-body");
        block.append(body);
      }
      if (body) { body.textContent = section.body || ""; body.hidden = !section.body; }
      const oldRows = block.querySelector(".world-rows");
      if (oldRows) oldRows.replaceChildren(...contextRows(section.rows || []).childNodes);
      else if (section.rows?.length) block.append(contextRows(section.rows));
    }
    for (const block of blocks) if (!(page.sections || []).some((section) => (section.id || section.title) === block.dataset.sectionKey) && !block.contains(document.activeElement)) block.hidden = true;
    $("world-summary").textContent = world.summary || "观照当前进度，再择下一步修行。";
    renderGuide(world);
    const quests = world.pages.find((entry) => entry.id === "quests");
    const tracked = (quests?.sections || []).flatMap((section) => (section.rows || []).map((row) => (["状态", "奖励"].includes(row.label) ? { ...row, label: `${section.title} · ${row.label}` } : row))).slice(0, 8);
    $("world-tracked-quests").replaceChildren(...tracked.map((row) => {
      const note = element("div", "tracked-quest");
      note.append(element("h4", "", row.label), element("p", "", row.value));
      return note;
    }));
    schedulePaginate(pagers.get("notes"));
    schedulePaginate(pagers.get("side"));
    for (const resource of snapshot.view.resources || []) {
      const block = [...document.querySelectorAll(".resource")].find((node) => node.dataset.id === resource.id);
      const value = block?.querySelector(".resource-value");
      if (value?.firstChild?.nodeType === Node.TEXT_NODE) value.firstChild.textContent = resource.value;
    }
    tickGrowth();
  }

  /** “下一步”提示：服务端给出当前瓶颈与第一个可执行事项，这里只负责跳转与高亮。 */
  function renderGuide(world) {
    const guide = world.guide, button = $("world-guide-go");
    if (!guide?.page) { button.hidden = true; return; }
    const page = world.pages.find((entry) => entry.id === guide.page);
    button.hidden = false;
    button.textContent = guide.label ? `去办理 · ${guide.label}` : `前往 · ${page?.label || guide.page}`;
    button.dataset.page = guide.page;
    button.dataset.actionKey = guide.action_id ? worldActionKey(guide.page, { id: guide.action_id, params: guide.params || {} }) : "";
  }

  function followGuide() {
    const button = $("world-guide-go");
    selectWorldPage(button.dataset.page);
    const key = button.dataset.actionKey;
    if (!key) return;
    const node = [...document.querySelectorAll(".world-action")].find((entry) => entry.dataset.actionKey === key);
    if (!node) return;
    revealNode(node);
    node.classList.add("guided");
    setTimeout(() => node.classList.remove("guided"), 2400);
    (node.querySelector(".world-submit:not(:disabled)") || node.querySelector("summary"))?.focus({ preventScroll: true });
  }

  function selectWorldPage(id) {
    if (!snapshot?.view.world?.pages.some((page) => page.id === id)) return;
    const navigationFocused = !!document.activeElement?.dataset.worldPage;
    const changed = selectedWorldPage !== id;
    selectedWorldPage = id;
    renderWorld(snapshot.view.world);
    stage3d.mount(document.querySelector(".world-page-heading"), realmTier($("realm").textContent), id, snapshot.view.world.estate);
    if (changed) animate(document.querySelector(".world-page-heading .stage-copy"), "copy-in");
    if (navigationFocused) [...document.querySelectorAll("[data-world-page]")].find((button) => button.dataset.worldPage === id)?.focus({ preventScroll: true });
  }

  function renderWorldAction(action, pageId) {
    const key = worldActionKey(pageId, action);
    const fields = action.fields || [];
    const wrapper = element(fields.length ? "details" : "div", `world-action${fields.length ? " has-fields" : ""}`);
    wrapper.dataset.worldAction = action.id;
    wrapper.dataset.kind = actionKind(action, pageId);
    wrapper.dataset.params = JSON.stringify(action.params);
    wrapper.dataset.search = `${action.label} ${action.detail} ${action.cost} ${action.effect} ${action.reason} ${JSON.stringify(action.params)}`.toLocaleLowerCase();
    wrapper.title = action.detail || "";
    const heading = element(fields.length ? "summary" : "div", "world-action-heading");
    const title = element("span", "world-action-name", action.label);
    heading.append(title);
    if (fields.length) {
      heading.append(element("span", "form-indicator", action.enabled ? "填写 →" : "条件未足"));
      heading.append(element("span", "world-summary-meta", `消耗 · ${action.cost}\n所得 · ${action.effect}`));
      if (!action.enabled) heading.append(element("span", "world-summary-reason", action.reason || "当前不可执行。"));
    }
    wrapper.append(heading);
    const description = element("div", "world-action-description");
    const meta = element("p", "action-meta");
    meta.append(element("span", "cost", `消耗 · ${action.cost}`), element("span", "effect", `所得 · ${action.effect}`));
    description.append(meta);
    const reason = element("p", "action-reason", action.reason || "");
    reason.hidden = action.enabled;
    reason.id = `world-reason-${worldFieldSequence++}`;
    wrapper.append(description, reason);
    const form = element("form", "world-action-form");
    form.dataset.worldAction = action.id;
    form.dataset.actionKey = key;
    form.dataset.params = JSON.stringify(action.params);
    wrapper.dataset.actionKey = key;
    const draft = worldDrafts.get(key) || {};
    const controls = [];
    const conflict = fields.some((field) => Object.prototype.hasOwnProperty.call(action.params, field.name));
    for (const field of fields) {
      const fieldWrapper = element("div", "world-field");
      const id = `world-field-${worldFieldSequence++}`;
      const label = element("label", "", `${field.label}${field.required ? " · 必填" : ""}`);
      label.htmlFor = id;
      const control = element(field.type === "select" ? "select" : "input", "world-write");
      control.name = field.name;
      control.id = id;
      control.required = !!field.required;
      control.dataset.enabled = String(!conflict);
      control.setAttribute("aria-describedby", reason.id);
      if (field.type === "select") {
        const blank = element("option", "", field.required ? "请选择" : "不填写");
        blank.value = "";
        control.append(blank);
        for (const option of field.options || []) {
          const node = element("option", "", option.label);
          node.value = option.value;
          control.append(node);
        }
      } else if (field.type === "number") {
        control.type = "number";
        control.step = "1";
        if (field.min !== undefined) control.min = String(field.min);
        if (field.max !== undefined) control.max = String(field.max);
        control.inputMode = "numeric";
      } else {
        control.type = "text";
        if (field.maxLength !== undefined) control.maxLength = field.maxLength;
        control.autocomplete = "off";
      }
      if (draft[field.name] !== undefined) control.value = draft[field.name];
      control.addEventListener("input", () => {
        control.setCustomValidity("");
        const values = worldDrafts.get(key) || {};
        values[field.name] = control.value;
        worldDrafts.set(key, values);
      });
      fieldWrapper.append(label, control);
      form.append(fieldWrapper);
      controls.push({ field, control });
    }
    const submit = element("button", `world-write world-submit${action.primary ? " primary-button" : " secondary-button"}`);
    submit.append(element("span", "btn-label", fields.length ? action.label : battleActionIds.has(action.id) || action.group === "battle" ? "出手" : "施行"));
    if (!fields.length) submit.setAttribute("aria-label", action.label);
    submit.type = "submit";
    submit.dataset.enabled = String(action.enabled && !conflict);
    submit.dataset.action = action.id;
    submit.dataset.params = JSON.stringify(action.params);
    submit.setAttribute("aria-describedby", reason.id);
    if (action.detail) submit.setAttribute("aria-description", action.detail);
    form.append(submit);
    if (conflict) {
      reason.hidden = false;
      reason.textContent = "表单字段与动作目标冲突，请更新页面后重试。";
    }
    if (fields.length && worldDrafts.has(key)) wrapper.open = true;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (busy || pending || !action.enabled || conflict) return;
      const params = { ...action.params };
      for (const { field, control } of controls) {
        if (!control.value && !field.required) continue;
        const value = field.type === "number" ? Number(control.value) : control.value;
        if (field.type === "number" && (!Number.isFinite(value) || !Number.isInteger(value))) {
          control.setCustomValidity("请输入有效整数。");
          control.reportValidity();
          return;
        }
        if (field.type === "select" && !(field.options || []).some((option) => option.value === value)) {
          control.setCustomValidity("请选择列表中的有效选项。");
          control.reportValidity();
          return;
        }
        params[field.name] = value;
      }
      if (!form.reportValidity()) return;
      const intent = { path: "/api/action", payload: { action: action.id, params }, key };
      if (action.confirm) openWorldConfirmation(action, intent);
      else {
        submittedWorldKey = key;
        beginWrite(intent.path, intent.payload);
      }
    });
    wrapper.append(form);
    return wrapper;
  }

  function openWorldConfirmation(action, intent) {
    if (busy || pending || !snapshot) return;
    confirmation = intent;
    previousFocus = document.activeElement;
    $("confirm-title").textContent = action.label;
    $("confirm-description").textContent = `${action.confirm}\n消耗：${action.cost}\n所得：${action.effect}`;
    $("new-name-field").hidden = true;
    $("new-name").required = false;
    $("new-name").disabled = true;
    $("accept-confirm").textContent = "确认 · 执行";
    $("confirm-dialog").showModal();
    $("cancel-confirm").focus();
  }

  function renderWorld(world) {
    const pages = world.pages || [];
    if (!pages.some((page) => page.id === selectedWorldPage)) selectedWorldPage = pages[0]?.id;
    $("world-navigation").replaceChildren();
    for (const [index, page] of pages.entries()) {
      const button = element("button", "world-nav-button");
      button.type = "button";
      button.dataset.worldPage = page.id;
      button.setAttribute("aria-pressed", String(page.id === selectedWorldPage));
      button.setAttribute("aria-controls", "world-content");
      const token = element("span", "world-nav-token");
      token.append(icon(sceneMarks[page.id] ? page.id : "world"));
      button.append(token, element("span", "world-nav-number", String(index + 1).padStart(2, "0")), element("span", "world-nav-label", page.label.replace(/^NPC/, "").slice(0, 2)));
      button.setAttribute("aria-label", page.label);
      button.title = page.label;
      button.addEventListener("click", () => selectWorldPage(page.id));
      $("world-navigation").append(button);
    }
    const page = pages.find((entry) => entry.id === selectedWorldPage);
    if (!page) return;
    $("world-page-number").textContent = `卷 ${String(pages.indexOf(page) + 1).padStart(2, "0")} · ${page.label}`;
    sceneBanner("world-scene", sceneMarks[page.id] ? page.id : "world");
    $("world-page-title").textContent = page.title;
    $("world-page-description").textContent = page.description;
    renderR3Context(world);
    renderWorldStats(page.stats);
    $("world-page-sections").replaceChildren();
    const pageSections = [...(page.sections || [])].sort((left, right) => Number(String(right.id || "").startsWith("r3_")) - Number(String(left.id || "").startsWith("r3_")));
    for (const section of pageSections) {
      const block = element("section", "world-section");
      block.dataset.sectionKey = section.id || section.title;
      block.dataset.pageGroup = "";
      if (section.id) block.dataset.sectionId = section.id;
      if (String(section.id || "").startsWith("r3_")) block.classList.add("r3-featured-section");
      block.append(element("h3", "", section.title));
      if (section.body) block.append(element("p", "world-section-body", section.body));
      if (section.rows?.length) {
        const rows = element("dl", "world-rows");
        for (const row of section.rows) {
          const line = element("div", "world-data-row");
          line.append(element("dt", "", row.label), element("dd", "", row.value));
          rows.append(line);
        }
        block.append(rows);
      }
      $("world-page-sections").append(block);
    }
    const currentCombat = world.battle && world.battle.page === page.id;
    const combatActions = currentCombat ? page.actions.filter((action) => action.group === "battle" || battleActionIds.has(action.id)) : [];
    const featuredActions = page.id === "quests" ? page.actions.filter((action) => (action.id.startsWith("world_activity_") || action.id.startsWith("world_story_"))) : [];
    const regularActions = (page.actions || []).filter((action) => !combatActions.includes(action) && !featuredActions.includes(action));
    $("r3-featured-actions").hidden = !featuredActions.length;
    $("r3-featured-action-list").replaceChildren(...featuredActions.map((action) => renderWorldAction(action, page.id)));
    $("world-battle-actions").hidden = !combatActions.length;
    $("world-battle-action-list").replaceChildren(...combatActions.map((action) => renderWorldAction(action, page.id)));
    $("world-page-actions").replaceChildren(...regularActions.map((action) => renderWorldAction(action, page.id)));
    if (!regularActions.length) $("world-page-actions").append(element("p", "muted", "此页暂无其他可执行事项，条件与进度请参阅手札页。"));
    const filter = worldActionFilters.get(page.id) || { query: "" };
    worldActionFilters.set(page.id, filter);
    $("world-action-search").value = filter.query;
    filterWorldActions(false);
    $("world-battle-banner").hidden = !world.battle;
    document.querySelector(".world-page-heading").classList.toggle("in-battle", !!world.battle);
    if (world.battle) {
      $("world-battle-link").hidden = world.battle.page === page.id;
      setArt("world-hero-portrait", portrait(realmTier($("realm").textContent)));
      setArt("world-enemy-portrait", enemyPortrait(world.battle.name));
      $("world-battle-name").textContent = world.battle.name;
      $("world-battle-intent").textContent = `敌方下一意图：${world.battle.intent}`;
      $("world-battle-health").textContent = `敌方气血 ${world.battle.hp} / ${world.battle.max_hp}`;
      const battleMeter = $("world-battle-meter");
      battleMeter.setAttribute("aria-valuemin", "0");
      battleMeter.setAttribute("aria-valuemax", String(world.battle.max_hp));
      battleMeter.setAttribute("aria-valuenow", String(world.battle.hp));
      setBattleMeter(battleMeter, world.battle.hp, world.battle.max_hp);
      $("world-battle-counterplay").textContent = world.battle.counterplay || "";
      $("world-battle-statuses").replaceChildren(...(world.battle.statuses || []).map((status) => {
        const line = element("div");
        line.append(element("dt", "", status.label), element("dd", "", status.value));
        return line;
      }));
    }
    $("world-summary").textContent = world.summary || "观照当前进度，再择下一步修行。";
    renderGuide(world);
    $("world-tracked-quests").replaceChildren();
    const quests = pages.find((entry) => entry.id === "quests");
    const tracked = (quests?.sections || []).flatMap((section) => (section.rows || []).map((row) => (["状态", "奖励"].includes(row.label) ? { ...row, label: `${section.title} · ${row.label}` } : row))).slice(0, 8);
    for (const row of tracked) {
      const note = element("div", "tracked-quest");
      note.append(element("h4", "", row.label), element("p", "", row.value));
      $("world-tracked-quests").append(note);
    }
    $("world-quests-link").hidden = !quests;
    $("world-recent-logs").replaceChildren(...[...(snapshot.view.logs || [])].reverse().slice(0, 16).map(logItem));
    $("world-slot-summary").textContent = `${snapshot.sync?.summary || "尚未开始修行。"}${lastSyncedAt ? ` · 最近同步 ${lastSyncedAt}` : ""}`;
    $("legacy-history").hidden = !historyVisible;
    $("legacy-history-title").textContent = snapshot.view.ending?.title || "归墟序章";
    $("legacy-history-text").textContent = snapshot.view.ending?.text || "从初入山村，到平定归墟，这段经历已成为你的来路。";
    document.querySelector(".world-page-heading").dataset.page = page.id;
    setArt("stage-hero", page.id === "character" ? portrait(realmTier($("realm").textContent)) : "");
    updateControls();
    renderStageTabs(combatActions.length + featuredActions.length + regularActions.length);
    schedulePaginate(pagers.get("side"));
  }

  function filterWorldActions(repaginate = true) {
    const filter = worldActionFilters.get(selectedWorldPage) || { query: "" };
    const query = filter.query.trim().toLocaleLowerCase();
    const rows = [...$("world-page-actions").querySelectorAll(".world-action")];
    const matched = rows.filter((row) => !query || row.dataset.search.includes(query));
    for (const row of rows) row.hidden = !matched.includes(row);
    $("world-action-count").textContent = matched.length ? `${query ? "匹配" : "共"} ${matched.length} 项事项 · 条件以服务端为准` : rows.length ? "未找到匹配事项，请换一个关键词。" : "";
    $("world-actions-show-more").hidden = true;
    $("world-actions-show-all").hidden = true;
    if (repaginate) {
      const pager = pagers.get("actions");
      pager.page = 0;
      paginate(pager);
    }
  }

  function render(data) {
    if (!data || data.ok !== true || !Number.isInteger(data.revision) || !data.view) throw new Error("服务返回的进度格式不完整。");
    if (snapshot && data.revision < snapshot.revision) return;
    const previousBattle = snapshot?.view.world?.battle;
    snapshot = data;
    lastSyncedAt = clockText(data.sync?.saved_at);
    if (syncState !== "synced") setSync("synced");
    newRevisionObserved = false;
    $("growth-update-button").hidden = true;
    const view = data.view;
    const worldActive = view.world?.active === true;
    document.title = `${view.title} · 归墟`;
    $("loading").hidden = true;
    $("creation").hidden = view.phase !== "creation";
    $("game").hidden = view.phase === "creation";
    $("world-workbench").hidden = !worldActive;
    document.querySelector(".game-layout").hidden = worldActive;
    if (worldActive) {
      if (view.world.battle && !previousBattle) {
        selectedWorldPage = view.world.battle.page;
        stageTabs.set(selectedWorldPage, "actions");
      }
      renderWorld(view.world);
    }
    if (view.character) {
      $("character-name").textContent = view.character.name;
      const worldStage = typeof view.world?.stage === "object" ? view.world.stage?.label : view.world?.stage;
      const realmText = worldActive ? worldStage || "凡界修行" : view.character.realm;
      $("realm").textContent = realmText;
      setArt("hud-avatar", portrait(realmTier(realmText), true));
      if (worldActive) {
        setArt("stage-hero", selectedWorldPage === "character" ? portrait(realmTier(realmText)) : "");
        if (view.world.battle) setArt("world-hero-portrait", portrait(realmTier(realmText)));
      }
      if (previousRealm !== null && realmText && previousRealm !== realmText) showBreakthrough(realmText);
      previousRealm = realmText;
      sceneBanner("journey-scene", view.phase === "battle" ? "arena" : "world");
      $("objective").textContent = view.objective;
      $("location-name").textContent = view.location?.name || "修行途中";
      $("location-description").textContent = view.location?.description || "";
      $("location-description").title = view.location?.description || "";
      $("scene-kicker").textContent = view.phase === "battle" ? "此刻 · 狭路相逢" : "此刻 · 身之所在";
      $("actions-title").textContent = view.phase === "battle" ? "自动斗法 · 择定策略" : "接下来，如何行道";
      renderResources(view.resources);
      floatNumbers(view.resources);
      const logs = view.logs || [];
      if (previousLogs && logs.length > previousLogs.length) showToasts(logs.slice(previousLogs.length));
      else if (previousLogs && logs.length && logs[logs.length - 1] !== previousLogs[previousLogs.length - 1]) showToasts(logs.slice(-1));
      previousLogs = [...logs];
      $("profile-label").textContent = view.profile?.mode === "longline" ? "· 长线修行" : "· 自由历练";
      renderActions(view.actions);
      renderLogs(view.logs);
      $("battle").hidden = !view.battle;
      document.querySelector(".game-layout").classList.toggle("in-battle", !!view.battle);
      if (view.battle) {
        const battle = view.battle;
        setArt("hero-portrait", portrait(realmTier(realmText)));
        setArt("enemy-portrait", enemyPortrait(battle.name));
        $("enemy-name").textContent = battle.name;
        $("enemy-health").textContent = `${battle.hp} / ${battle.max_hp} 气血`;
        $("enemy-intent").textContent = battle.intent;
        const meter = $("enemy-meter");
        meter.setAttribute("aria-valuemin", "0");
        meter.setAttribute("aria-valuemax", String(battle.max_hp));
        meter.setAttribute("aria-valuenow", String(battle.hp));
        setBattleMeter(meter, battle.hp, battle.max_hp);
      }
      $("ending").hidden = !view.ending;
      if (view.ending) {
        $("ending-title").textContent = view.ending.title;
        $("ending-text").textContent = view.ending.text;
        $("ending-text").title = view.ending.text;
      }
    }
    anchorGrowth(view.growth);
    updateControls();
    syncHudHeight();
    const auraHost = view.phase === "creation" ? $("creation") : worldActive ? document.querySelector(".world-page-heading") : document.querySelector(".journey > .scene");
    const auraTier = realmTier($("realm").textContent);
    aura.mount(auraHost, auraTier);
    stage3d.mount(auraHost, auraTier, worldActive ? selectedWorldPage : "", view.world?.estate);
    scheduleQi();
  }

  // 序章吐纳由服务端按时间结算：每隔一个周期静默读取一次，只刷新修为与目标；
  // 若可执行的行动因此变化（如修为圆满可突破）才整体重绘，避免打断悬停与焦点。
  let qiTimer = 0;
  function scheduleQi() {
    clearTimeout(qiTimer);
    const qi = snapshot?.view?.qi;
    if (!qi || qi.value >= qi.cap || snapshot.view.world?.active || authLocked) return;
    qiTimer = setTimeout(softRefresh, Math.max(1, qi.next_in ?? qi.seconds) * 1000 + 200);
  }

  async function softRefresh() {
    if (document.hidden || busy || pending || offline || authLocked || $("confirm-dialog").open) { scheduleQi(); return; }
    const requestedRevision = snapshot.revision;
    try {
      const { response, data } = await request("/api/state");
      if (response.ok && data.ok && !busy && !pending && snapshot.revision === requestedRevision && data.revision === requestedRevision && data.view.qi) {
        const same = data.view.phase === snapshot.view.phase && JSON.stringify(data.view.actions) === JSON.stringify(snapshot.view.actions);
        if (same) {
          snapshot = data;
          $("objective").textContent = data.view.objective;
          renderResources(data.view.resources);
          floatNumbers(data.view.resources);
        } else render(data);
      }
    } catch (_) { /* 静默刷新失败无妨，下一轮再试 */ }
    scheduleQi();
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) scheduleQi(); });

  async function refreshGrowth() {
    if (growthRefreshing || busy || pending || offline || authLocked || !snapshot?.view.growth?.active || document.hidden || $("confirm-dialog").open) return;
    growthRefreshing = true;
    const requestedRevision = snapshot.revision;
    try {
      const { response, data } = await request("/api/state");
      if (!response.ok || !data.ok || busy || pending || !data.view?.growth?.active || snapshot.revision !== requestedRevision) return;
      if (data.revision !== snapshot.revision) {
        newRevisionObserved = data.revision > snapshot.revision;
        if (newRevisionObserved) {
          $("growth-sync-status").textContent = "其他页面已更新进度；输入内容已保留，重新读取后再操作。";
          $("growth-update-button").hidden = false;
        }
        return;
      }
      snapshot.view.growth = data.view.growth;
      snapshot.view.resources = data.view.resources;
      if (snapshot.view.world && data.view.world) {
        snapshot.view.world.summary = data.view.world.summary;
        snapshot.view.world.goals = data.view.world.goals;
        snapshot.view.world.journey = data.view.world.journey;
      }
      if (data.view.world?.loot && snapshot.view.world?.loot) {
        for (const key of ["progress", "boss", "dungeons", "credits"]) snapshot.view.world.loot[key] = data.view.world.loot[key];
        updateR3ReadOnly();
      }
      for (const page of snapshot.view.world?.pages || []) {
        const latest = data.view.world?.pages.find((entry) => entry.id === page.id);
        if (!latest) continue;
        page.stats = latest.stats;
        page.sections = latest.sections;
        page.title = latest.title;
        page.description = latest.description;
        for (const action of page.actions) {
          const fresh = latest.actions.find((entry) => worldActionKey(page.id, entry) === worldActionKey(page.id, action));
          if (!fresh) continue;
          action.enabled = fresh.enabled;
          action.reason = fresh.reason;
          const key = worldActionKey(page.id, action);
          const row = [...document.querySelectorAll(".world-action")].find((entry) => entry.dataset.actionKey === key);
          if (!row) continue;
          row.querySelectorAll(".world-submit").forEach((control) => { control.dataset.enabled = String(fresh.enabled); });
          const reason = row.querySelector(".action-reason");
          if (reason) { reason.textContent = fresh.reason || ""; reason.hidden = fresh.enabled; }
          const summaryReason = row.querySelector(".world-summary-reason");
          if (summaryReason) { summaryReason.textContent = fresh.reason || ""; summaryReason.hidden = fresh.enabled; }
          else if (!fresh.enabled && row.matches("details")) row.querySelector("summary")?.append(element("span", "world-summary-reason", fresh.reason || "当前不可执行。"));
        }
      }
      anchorGrowth(data.view.growth);
      patchWorldText();
      updateControls();
    } catch (_) {
      if (growthAnchor) $("growth-sync-status").textContent = "暂时无法校正潜修数值，已保留全部表单；提交以服务端为准。";
    } finally {
      growthRefreshing = false;
    }
  }

  class AuthError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "AuthError";
      this.code = code;
    }
  }

  const accountKey = (name) => String(name || "").normalize("NFKC").toLowerCase();
  const postHeaders = { "Content-Type": "application/json", "X-Game-Client": "guixu-web" };

  function clockText(value) {
    const parsed = value ? new Date(value) : new Date();
    const date = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
    return [date.getHours(), date.getMinutes(), date.getSeconds()].map((part) => String(part).padStart(2, "0")).join(":");
  }

  const syncTexts = {
    idle: "尚未开始修行",
    syncing: "进度同步中…",
    retrying: "同步失败，正在重试…",
    offline: "网络中断，正在重连…",
    failed: "进度保存失败，请稍后重试，当前操作未生效",
    auth: "请先登录",
  };

  /** 更新顶栏同步状态指示；synced 约 3 秒后淡化为常驻小标记。 */
  function setSync(state, text) {
    clearTimeout(syncFadeTimer);
    syncState = state;
    const node = $("save-status");
    node.dataset.state = state;
    node.dataset.fade = "0";
    node.textContent = text || (state === "synced" ? `进度已同步 · ${lastSyncedAt || clockText()}` : syncTexts[state]);
    node.title = node.textContent;
    if (state === "synced") {
      syncFadeTimer = setTimeout(() => {
        node.dataset.fade = "1";
        node.textContent = "进度已同步";
      }, 3000);
    }
  }

  function setAccount(name) {
    account = name;
    $("account-button").hidden = !name;
    $("account-name").textContent = name || "";
    $("account-button").title = name ? `账号：${name}` : "";
    $("account-button").setAttribute("aria-label", name ? `账号：${name}` : "账号");
    if (!name) toggleAccountMenu(false);
  }

  function networkError(cause) {
    const error = new Error(cause?.name === "AbortError" ? "服务响应超时" : "网络中断");
    error.network = true;
    return error;
  }

  /**
   * 统一请求入口。raw: 不拦截 401（登录/注册/会话探测自行处理）；
   * quiet: 网络错误只抛出，不进入全局断线重连（登录对话框内自行提示）。
   */
  async function request(path, options = {}, { raw = false, quiet = false } = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    let response;
    let data;
    try {
      response = await fetch(path, { ...options, signal: controller.signal, cache: "no-store", credentials: "same-origin" });
      try {
        data = await response.json();
      } catch (_) {
        data = { ok: false };
      }
    } catch (cause) {
      if (!quiet) markOffline();
      throw networkError(cause);
    } finally {
      clearTimeout(timeout);
    }
    if (offline && !quiet) restoreOnline();
    if (!raw && response.status === 401) {
      handleUnauthorized(data?.error?.code);
      throw new AuthError(data?.error?.code || "AUTH_REQUIRED", data?.error?.message || "请先登录。");
    }
    if (typeof data.ok !== "boolean" && response.ok) throw new Error("无法识别服务响应。");
    return { response, data };
  }

  /* ---------- 断线重连 ---------- */
  function markOffline() {
    if (offline) return;
    offline = true;
    reconnectDelay = 2000;
    setSync("offline");
    notice("网络中断，正在重连…", "error", false, false);
    scheduleReconnect(false);
  }

  function restoreOnline() {
    offline = false;
    clearTimeout(reconnectTimer);
  }

  function scheduleReconnect(immediate) {
    clearTimeout(reconnectTimer);
    const wait = immediate ? 0 : reconnectDelay * (0.8 + Math.random() * 0.4);
    reconnectDelay = Math.min(10000, reconnectDelay * 2);
    reconnectTimer = setTimeout(probeConnection, wait);
  }

  async function probeConnection() {
    if (!offline) return;
    let data;
    try {
      ({ data } = await request("/api/session", {}, { raw: true, quiet: true }));
    } catch (_) {
      scheduleReconnect(false);
      return;
    }
    restoreOnline();
    notice("");
    await applySession(data);
    if (pending && !authLocked && snapshot) await sendPending();
  }

  /* ---------- 登录 / 会话 ---------- */
  function handleUnauthorized(code) {
    clearTimeout(qiTimer);
    showAuth(code === "SESSION_EXPIRED" ? "登录已过期，请重新登录" : "请先登录");
  }

  function applyAuthMode(mode) {
    authMode = mode === "register" && registrationOpen ? "register" : "login";
    const registering = authMode === "register";
    document.querySelectorAll("[data-auth-tab]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.authTab === authMode));
      if (tab.dataset.authTab === "register") tab.hidden = !registrationOpen;
    });
    $("auth-kicker").textContent = registering ? "注 册" : "登 录";
    $("auth-submit").textContent = registering ? "注册并进入" : "登录";
    $("auth-password").autocomplete = registering ? "new-password" : "current-password";
    $("auth-username-hint").hidden = !registering;
    $("auth-password-hint").hidden = !registering;
    $("auth-confirm-label").hidden = !registering;
    $("auth-confirm").hidden = !registering;
    clearAuthErrors();
  }

  function fieldMessage(id, message) {
    const node = $(id);
    node.textContent = message || "";
    node.hidden = !message;
    const input = $(id.replace(/-error$/, ""));
    if (input) input.setAttribute("aria-invalid", String(!!message));
  }

  function clearAuthErrors() {
    for (const id of ["auth-username-error", "auth-password-error", "auth-confirm-error"]) fieldMessage(id, "");
    $("auth-error").hidden = true;
  }

  function showAuth(message) {
    authLocked = true;
    toggleAccountMenu(false);
    setSync("auth", message === "登录已过期，请重新登录" ? message : "请先登录");
    updateControls();
    const dialog = $("auth-dialog");
    if ($("password-dialog").open) $("password-dialog").close();
    if (dialog.open) return;
    applyAuthMode(authMode);
    $("auth-error").textContent = message || "";
    $("auth-error").hidden = !message;
    $("auth-password").value = "";
    $("auth-confirm").value = "";
    dialog.showModal();
    $("auth-username").focus();
  }

  function setAuthBusy(value) {
    authSubmitting = value;
    for (const id of ["auth-username", "auth-password", "auth-confirm", "auth-submit"]) $(id).disabled = value;
    document.querySelectorAll("[data-auth-tab]").forEach((tab) => { tab.disabled = value; });
  }

  function showFormError(error, fields, general) {
    const message = error?.message || "操作失败，请稍后重试。";
    const target = error?.field && fields[error.field];
    if (target) fieldMessage(target, message);
    else {
      const node = $(general);
      node.textContent = error?.code === "RATE_LIMITED" && !error?.message && error?.retry_after ? `尝试次数过多，请 ${Math.max(1, Math.ceil(error.retry_after / 60))} 分钟后再试。` : message;
      node.hidden = false;
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    if (authSubmitting) return;
    clearAuthErrors();
    const username = $("auth-username").value.trim();
    const password = $("auth-password").value;
    const registering = authMode === "register";
    if (!username) { fieldMessage("auth-username-error", "请输入用户名。"); return; }
    if (!password) { fieldMessage("auth-password-error", "请输入密码。"); return; }
    if (registering && password !== $("auth-confirm").value) { fieldMessage("auth-confirm-error", "两次输入的密码不一致。"); return; }
    setAuthBusy(true);
    try {
      const { response, data } = await request(registering ? "/api/register" : "/api/login", { method: "POST", headers: postHeaders, body: JSON.stringify({ username, password }) }, { raw: true, quiet: true });
      if (response.ok && data.ok && data.account?.username) {
        setAuthBusy(false);
        await onLoggedIn(data.account.username);
        return;
      }
      if (data.error?.code === "REGISTRATION_CLOSED") {
        registrationOpen = false;
        applyAuthMode("login");
      }
      showFormError(data.error, { username: "auth-username-error", password: "auth-password-error" }, "auth-error");
    } catch (error) {
      showFormError({ message: error.network ? "网络中断，请稍后重试。" : error.message }, {}, "auth-error");
    }
    setAuthBusy(false);
    $("auth-password").value = "";
    $("auth-confirm").value = "";
    $("auth-password").focus();
  }

  /** 登录成功：账号变化则整页重载清空界面；同账号则继续并重放待确认操作。 */
  async function onLoggedIn(name) {
    const key = accountKey(name);
    if (pending && pending.account !== key) {
      pending = null;
      persistPending(null);
    }
    if ((account && accountKey(account) !== key) || (!account && snapshot)) {
      persistPending(null);
      location.reload();
      return;
    }
    setAccount(name);
    authLocked = false;
    $("auth-password").value = "";
    $("auth-confirm").value = "";
    $("auth-dialog").close();
    updateControls();
    await readState(true);
    if (pending && !authLocked && !offline && snapshot) await sendPending();
  }

  /** 根据 /api/session 的结果进入登录面板或加载进度。 */
  async function applySession(data) {
    registrationOpen = data.registration_open !== false;
    if (!data.authenticated || !data.account?.username) {
      showAuth(data.reason === "SESSION_EXPIRED" ? "登录已过期，请重新登录" : "");
      return;
    }
    const key = accountKey(data.account.username);
    if (pending && pending.account !== key) {
      pending = null;
      persistPending(null);
    }
    if (account && accountKey(account) !== key) {
      persistPending(null);
      location.reload();
      return;
    }
    setAccount(data.account.username);
    authLocked = false;
    if ($("auth-dialog").open) $("auth-dialog").close();
    await readState(!storageAvailable);
  }

  async function logout() {
    if (busy) return;
    toggleAccountMenu(false);
    try {
      const { response } = await request("/api/logout", { method: "POST", headers: postHeaders, body: "{}" }, { raw: true, quiet: true });
      // 服务端确认前不能当作已退出：凭证仍有效时重载会直接回到登录状态；401 说明本来就未登录
      if (!response.ok && response.status !== 401) {
        notice("暂时无法退出登录，请稍后重试。", "error");
        return;
      }
    } catch (_) {
      notice("网络中断，暂时无法退出登录，请稍后重试。", "error");
      return;
    }
    // 清空待确认记录并整页重载，丢弃内存中的全部角色数据
    try { sessionStorage.removeItem(storageKey); } catch (_) { /* 无存储权限时无需清理 */ }
    location.reload();
  }

  function toggleAccountMenu(open) {
    $("account-menu").hidden = !open;
    $("account-button").setAttribute("aria-expanded", String(open));
  }

  function openPasswordDialog() {
    toggleAccountMenu(false);
    if (busy || offline || authLocked) return;
    for (const id of ["old-password", "new-password", "new-password-confirm"]) $(id).value = "";
    for (const id of ["old-password-error", "new-password-error", "new-password-confirm-error"]) fieldMessage(id, "");
    $("password-error").hidden = true;
    $("password-dialog").showModal();
    $("old-password").focus();
  }

  async function submitPassword(event) {
    event.preventDefault();
    for (const id of ["old-password-error", "new-password-error", "new-password-confirm-error"]) fieldMessage(id, "");
    $("password-error").hidden = true;
    const oldPassword = $("old-password").value;
    const newPassword = $("new-password").value;
    if (!oldPassword) { fieldMessage("old-password-error", "请输入旧密码。"); return; }
    if (!newPassword) { fieldMessage("new-password-error", "请输入新密码。"); return; }
    if (newPassword !== $("new-password-confirm").value) { fieldMessage("new-password-confirm-error", "两次输入的新密码不一致。"); return; }
    $("password-submit").disabled = true;
    try {
      const { response, data } = await request("/api/password", { method: "POST", headers: postHeaders, body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }) }, { quiet: true });
      if (response.ok && data.ok) {
        $("password-dialog").close();
        notice("密码已修改，其他设备需重新登录。", "success");
      } else showFormError(data.error, { old_password: "old-password-error", new_password: "new-password-error" }, "password-error");
    } catch (error) {
      if (!(error instanceof AuthError)) showFormError({ message: error.network ? "网络中断，请稍后重试。" : error.message }, {}, "password-error");
    } finally {
      $("password-submit").disabled = false;
      for (const id of ["old-password", "new-password", "new-password-confirm"]) $(id).value = "";
    }
  }

  async function readState(keepNotice = false) {
    if (busy) return;
    busy = true;
    if (!snapshot) setSync("idle", "正在同步你的修行进度…"); else setSync("syncing");
    updateControls();
    try {
      const { response, data } = await request("/api/state");
      if (!response.ok || !data.ok) throw new Error(data.error?.message || "暂时无法同步你的修行进度。");
      render(data);
      setSync(data.view.character ? "synced" : "idle");
      if (pending) notice("上次操作结果尚未确认。请重试原操作以安全核对，期间暂停其他行动。", "", true, false);
      else if (!keepNotice) notice("");
    } catch (error) {
      if (error instanceof AuthError || error.network) return;
      setSync("failed", "同步失败，请稍后重试");
      notice(`同步失败：${error.message}。请稍后重新同步。`, "error", !!pending, true);
    } finally {
      busy = false;
      updateControls();
    }
  }

  function persistPending(value) {
    try {
      if (value) sessionStorage.setItem(storageKey, JSON.stringify(value));
      else sessionStorage.removeItem(storageKey);
      return true;
    } catch (_) {
      storageAvailable = false;
      notice("浏览器无法记录待确认操作。为避免刷新后重复执行，已暂停写入；请允许本站使用浏览器存储后重新打开页面。", "error", false, true);
      return false;
    }
  }

  function requestId() {
    if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function beginWrite(path, payload = {}) {
    if (busy || pending || !snapshot || !storageAvailable || !account || offline || authLocked) return;
    const candidate = { path, account: accountKey(account), body: { request_id: requestId(), expected_revision: snapshot.revision, ...payload } };
    if (!persistPending(candidate)) return;
    pending = candidate;
    const active = document.activeElement;
    const source = active?.matches?.("button") ? active : pressed && performance.now() - pressed.at < 1500 && document.contains(pressed.node) ? pressed.node : null;
    writeSource = source ? { node: source, rect: source.getBoundingClientRect(), key: source.closest(".world-action-form")?.dataset.actionKey || source.dataset.actionKey || "" } : null;
    if (source && !reducedMotion()) { source.classList.add("is-pending"); source.setAttribute("aria-busy", "true"); }
    const focusKey = document.activeElement?.dataset?.actionKey;
    const worldFocusKey = document.activeElement?.closest(".world-action-form")?.dataset.actionKey;
    await sendPending();
    if (focusKey) {
      const target = [...document.querySelectorAll(".action-button")].find((button) => button.dataset.actionKey === focusKey && !button.disabled && !button.closest("[hidden]"));
      target?.focus({ preventScroll: true });
    }
    if (worldFocusKey) {
      const form = [...document.querySelectorAll(".world-action-form")].find((node) => node.dataset.actionKey === worldFocusKey);
      form?.querySelector(".world-submit:not(:disabled)")?.focus({ preventScroll: true });
    }
  }

  async function sendPending() {
    if (!pending || busy || authLocked || offline) return;
    busy = true;
    notice("");
    setSync("syncing");
    updateControls();
    let refreshConflict = false;
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    try {
      for (let attempt = 0; ; attempt += 1) {
        let result;
        try {
          result = await request(pending.path, { method: "POST", headers: postHeaders, body: JSON.stringify(pending.body) });
        } catch (error) {
          // 登录失效：保留待确认记录，登录后以同一操作编号重放；断线：由重连流程恢复后重放
          if (error instanceof AuthError || error.network) return;
          result = { response: { ok: false, status: 502 }, data: { ok: false } };
        }
        const { response, data } = result;
        if (response.ok && data.ok) {
          if (pending.path === "/api/new-game") {
            worldDrafts.clear();
            selectedWorldPage = "world";
            historyVisible = false;
            worldActionFilters.clear();
            worldSectionOpen.clear();
            $("legacy-history-button").setAttribute("aria-expanded", "false");
          }
          if (submittedWorldKey) worldDrafts.delete(submittedWorldKey);
          submittedWorldKey = null;
          render(data);
          setSync("synced");
          pending = null;
          if (persistPending(null)) notice(data.duplicate ? "该操作已处理，已同步最新进度。" : data.battle_report ? data.events.slice(0, 2).join(" · ") : data.events?.length ? data.events.join(" · ") : "进度已同步。", "success");
          if (data.battle_report && !data.duplicate) globalThis.BattleReplay?.open(data.battle_report, battleLook(data));
          else if (!data.duplicate) celebrateWrite(writeSource);
          break;
        }
        if (data.ok === false && data.error && response.status < 500) {
          // 业务错误（含 409）：操作确定未生效，清除待确认记录
          pending = null;
          submittedWorldKey = null;
          if (persistPending(null)) {
            refreshConflict = response.status === 409;
            notice(refreshConflict ? "进度已在其他页面更新，已为你刷新到最新" : data.error.message, "error", false, !refreshConflict);
          }
          if (!refreshConflict) setSync(snapshot?.view?.character ? "synced" : "idle");
          break;
        }
        // 5xx / 503 SAVE_FAILED / 响应异常：同一操作编号退避重试
        if (attempt >= retryDelays.length) {
          setSync("failed");
          notice(data.error?.message || "进度保存失败，请稍后重试，当前操作未生效。", "error", true, false);
          break;
        }
        setSync("retrying");
        await sleep(retryDelays[attempt]);
        if (authLocked || offline) return;
      }
    } finally {
      busy = false;
      if (writeSource?.node?.isConnected) { writeSource.node.classList.remove("is-pending"); writeSource.node.removeAttribute("aria-busy"); }
      writeSource = null;
      updateControls();
    }
    if (refreshConflict) await readState(true);
  }

  /** 「另起一卷」确认弹窗（世界事项的二次确认走各自的流程）。 */
  function openConfirmation(kind) {
    if (busy || pending || !snapshot || kind !== "new") return;
    confirmation = kind;
    previousFocus = document.activeElement;
    $("confirm-title").textContent = "另起一卷修行？";
    $("confirm-description").textContent = "当前角色及其进度将被新的角色替代，此操作无法撤销。修行方式只影响新角色。";
    $("new-name-field").hidden = false;
    $("new-name").required = false;
    $("new-name").disabled = false;
    $("new-name").value = "归墟客";
    $("new-mode").value = "longline";
    $("new-mode").disabled = false;
    $("accept-confirm").textContent = "确认 · 开启新卷";
    $("confirm-dialog").showModal();
    $("cancel-confirm").focus();
  }

  $("creation-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("name").value.trim() || "归墟客";
    beginWrite("/api/new-game", { name, mode: $("mode").value });
  });
  $("name").addEventListener("input", () => $("name").setCustomValidity(""));
  $("new-button").addEventListener("click", () => openConfirmation("new"));
  $("retry-button").addEventListener("click", sendPending);
  $("refresh-button").addEventListener("click", () => readState());
  $("history-button").addEventListener("click", () => { expanded = !expanded; renderLogs(snapshot.view.logs); });
  $("world-quests-link").addEventListener("click", () => selectWorldPage("quests"));
  $("world-guide-go").addEventListener("click", followGuide);
  $("world-action-search").addEventListener("input", () => {
    worldActionFilters.set(selectedWorldPage, { query: $("world-action-search").value });
    filterWorldActions();
  });
  $("world-actions-show-more").addEventListener("click", () => turnPage(pagers.get("actions"), 1));
  $("world-actions-show-all").addEventListener("click", () => applyStageTab("actions"));
  $("r4-dungeon-jump").addEventListener("click", () => {
    if (!$("r4-dungeon-workbench")) return;
    revealNode($("r4-dungeon-workbench"));
    $("r3-dungeon-select")?.focus({ preventScroll: true });
  });
  $("world-actions-jump").addEventListener("click", () => {
    applyStageTab("actions");
    $("world-actions-title").focus({ preventScroll: true });
  });
  $("world-battle-link").addEventListener("click", () => {
    const battle = snapshot?.view.world?.battle;
    if (!battle) return;
    stageTabs.set(battle.page, "actions");
    selectWorldPage(battle.page);
    revealNode($("world-battle-actions").querySelector("h3"));
    $("world-battle-actions").querySelector("h3").focus({ preventScroll: true });
  });
  function toggleLegacyHistory(open) {
    historyVisible = open;
    $("legacy-history").hidden = !historyVisible;
    $("legacy-history-button").setAttribute("aria-expanded", String(historyVisible));
  }
  $("legacy-history-button").addEventListener("click", () => toggleLegacyHistory(!historyVisible));
  $("legacy-history-close").addEventListener("click", () => { toggleLegacyHistory(false); $("legacy-history-button").focus(); });
  $("reader-close").addEventListener("click", closeReader);
  $("reader").addEventListener("click", (event) => { if (event.target === $("reader")) closeReader(); });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!$("reader").hidden) closeReader();
    else if (historyVisible) toggleLegacyHistory(false);
    else {
      const open = document.querySelector(".world-action[open], .growth-details[open]");
      if (open) { open.open = false; open.querySelector("summary")?.focus(); }
    }
  });
  document.querySelectorAll("[data-side-tab]").forEach((tab) => tab.addEventListener("click", () => applySideTab(tab.dataset.sideTab)));
  for (const bar of [$("stage-tabs"), $("action-tabs"), $("side-tabs")]) {
    bar.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...bar.querySelectorAll("button")].filter((tab) => tab.offsetParent);
      const index = tabs.indexOf(document.activeElement);
      if (index < 0) return;
      const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      next.focus();
      next.click();
    });
  }
  document.addEventListener("click", (event) => {
    const growth = $("growth-details");
    if (growth.open && !growth.contains(event.target)) growth.open = false;
  });
  createPager("actions", document.querySelector('[data-region="actions"]'), $("stage-pager"));
  createPager("notes", document.querySelector('[data-region="notes"]'), $("stage-pager"));
  createPager("context", document.querySelector('[data-region="context"]'), $("stage-pager"));
  createPager("side", document.querySelector('[data-region="side"]'), $("side-pager"));
  createPager("journey", $("actions"), $("journey-pager"));
  createPager("chronicle", document.querySelector('[data-region="chronicle"]'), $("chronicle-pager"));
  createPager("reader", $("reader-body"), $("reader-pager"));
  narrowLayout?.addEventListener?.("change", () => {
    placeAside();
    if (snapshot?.view.world?.active) renderWorld(snapshot.view.world);
  });
  placeAside();
  applySideTab("quests");
  $("cancel-confirm").addEventListener("click", () => $("confirm-dialog").close());
  $("confirm-dialog").addEventListener("close", () => { confirmation = null; previousFocus?.focus(); });
  $("confirm-dialog").querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    const kind = confirmation;
    const name = $("new-name").value.trim() || "归墟客";
    $("confirm-dialog").close();
    if (kind === "new") beginWrite("/api/new-game", { name, mode: $("new-mode").value });
    else if (kind?.path) {
      submittedWorldKey = kind.key;
      beginWrite(kind.path, kind.payload);
    }
  });
  $("new-name").addEventListener("input", () => $("new-name").setCustomValidity(""));
  $("mode").addEventListener("change", () => {
    $("mode-description").textContent = $("mode").value === "longline" ? "序章后开启持续潜修，以装备和法宝养成推进月余修行。" : "保留旧版行动成长规则，无离线增长。";
  });
  $("growth-update-button").addEventListener("click", () => readState());
  $("account-button").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleAccountMenu($("account-menu").hidden);
  });
  $("password-button").addEventListener("click", openPasswordDialog);
  $("logout-button").addEventListener("click", logout);
  document.addEventListener("click", (event) => {
    if (!$("account-menu").hidden && !event.target.closest(".account-wrap")) toggleAccountMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("account-menu").hidden) { toggleAccountMenu(false); $("account-button").focus(); }
  });
  document.querySelectorAll("[data-auth-tab]").forEach((tab) => tab.addEventListener("click", () => applyAuthMode(tab.dataset.authTab)));
  $("auth-form").addEventListener("submit", submitAuth);
  // 未登录时没有可返回的内容，登录面板不可用 Esc 关闭
  $("auth-dialog").addEventListener("cancel", (event) => event.preventDefault());
  $("password-form").addEventListener("submit", submitPassword);
  $("password-cancel").addEventListener("click", () => $("password-dialog").close());
  window.addEventListener("online", () => { if (offline) scheduleReconnect(true); });
  window.addEventListener("offline", markOffline);

  try {
    // 旧版键不含账号信息，无法校验归属，直接清除
    sessionStorage.removeItem(legacyStorageKey);
    const saved = sessionStorage.getItem(storageKey);
    if (saved) {
      const value = JSON.parse(saved);
      if (!["/api/action", "/api/new-game"].includes(value.path) || typeof value.account !== "string" || !value.account || typeof value.body?.request_id !== "string" || !Number.isInteger(value.body?.expected_revision)) throw new Error("invalid pending");
      pending = value;
    }
  } catch (_) {
    storageAvailable = false;
    notice("待确认操作记录不可读取。为保护进度，已暂停写入；请检查浏览器的存储设置。", "error", false, true);
  }
  (async () => {
    try {
      const { data } = await request("/api/session", {}, { raw: true });
      await applySession(data);
    } catch (_) {
      // 断线时由重连流程继续探测会话
    }
  })();
  setInterval(tickGrowth, 250);
  setInterval(refreshGrowth, 15000);
})();
