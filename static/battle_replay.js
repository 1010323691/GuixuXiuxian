"use strict";
// 自动斗法战报回放：只播放服务端已结算并保存的 battle_report，不推进任何规则、不重复结算。
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const $ = (id) => document.getElementById(id);
  const make = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
  const svg = (tag, attrs = {}) => { const node = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v)); return node; };
  const OUTCOME = { victory: "胜势已定", defeat: "此战暂退", window: "十二拍 · 试锋已毕", stalemate: "交锋至限，自行撤离", retreat: "撤离战斗" };
  const ACTOR = { player: "本方", main: "本命法宝", guard: "护持法宝", enemy: "敌方", npc: "同行NPC" };
  // 舞台坐标（viewBox 1000×340）
  const POINT = { player: [200, 190], main: [120, 100], guard: [130, 262], enemy: [800, 180], npc: [300, 280] };
  const FX_TYPES = new Set(["damage", "shield", "shield_absorb", "poison", "heal", "control", "buff", "defend", "mana"]);
  let fx3d = null, fx3dToken = 0, report = null, context = {}, cursor = 0, playing = false, speed = 1, timer = null, generation = 0, opener = null, effectTimers = [];

  const reduced = () => !!globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function build() {
    if ($("battle-replay")) return;
    const root = make("div", "battle-replay");
    root.id = "battle-replay"; root.hidden = true;
    root.setAttribute("role", "dialog"); root.setAttribute("aria-modal", "true"); root.setAttribute("aria-labelledby", "replay-title");
    root.innerHTML = `
      <div class="replay-card">
        <div class="replay-head"><div><span class="section-number" id="replay-kicker">自动斗法 · 战果已结算</span><h2 id="replay-title"></h2></div><button type="button" id="replay-close" class="icon-button" aria-label="合上战报"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#i-close"/></svg></button></div>
        <div class="replay-stage" id="replay-stage" data-enemy="" aria-hidden="true"></div>
        <div class="replay-meters">
          <div class="replay-meter"><span id="replay-player-hp-text">气血</span><div class="meter hp" role="meter" id="replay-player-hp" aria-label="本方气血"><span></span></div></div>
          <div class="replay-meter"><span id="replay-player-mp-text">灵力</span><div class="meter mp" role="meter" id="replay-player-mp" aria-label="本方灵力"><span></span></div></div>
          <div class="replay-meter"><span id="replay-enemy-hp-text">敌方气血</span><div class="meter enemy-meter" role="meter" id="replay-enemy-hp" aria-label="敌方气血"><span></span></div></div>
        </div>
        <p class="replay-now" id="replay-now" role="status" aria-live="polite"></p>
        <p class="replay-intent quiet-note" id="replay-intent"></p>
        <div class="replay-controls">
          <button type="button" class="small-button" id="replay-play">暂停播放</button>
          <button type="button" class="small-button" id="replay-speed">速度 1×</button>
          <button type="button" class="small-button" id="replay-skip">跳到结果</button>
          <label class="sr-only" for="replay-timeline">回看第几拍</label><input id="replay-timeline" type="range" min="0" max="0" value="0">
          <span class="quiet-note" id="replay-round">第 0 拍</span>
        </div>
        <section class="replay-result" id="replay-result" hidden><h3 id="replay-result-title"></h3><p id="replay-result-text" class="quiet-note"></p></section>
        <ol class="replay-log logs" id="replay-log" aria-label="斗法事件"></ol>
      </div>`;
    document.body.append(root);
    $("replay-close").addEventListener("click", close);
    $("replay-play").addEventListener("click", () => (playing ? pause() : play()));
    $("replay-speed").addEventListener("click", () => { speed = speed === 1 ? 2 : 1; fx3d?.setSpeed(speed); $("replay-speed").textContent = `速度 ${speed}×`; if (playing) schedule(); });
    $("replay-skip").addEventListener("click", () => { pause(); cursor = report.frames.length - 1; render(false); });
    $("replay-timeline").addEventListener("input", () => { pause(); cursor = Number($("replay-timeline").value); render(false); });
    root.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
    root.addEventListener("click", (event) => { if (event.target === root) close(); });
    document.addEventListener("visibilitychange", () => { if (document.hidden && playing) pause(); });
  }

  // 三维斗法台：按需加载，失败/无 WebGL/上下文丢失时回到 SVG 演出（信息层不依赖三维）
  const fx3dOn = () => !!fx3d && !fx3d.lost;
  function markFx3d(on) {
    const host = $("replay-stage"); if (!host) return;
    if (on) host.dataset.fx3d = "on"; else delete host.dataset.fx3d;
    $("battle-replay")?.classList.toggle("immersive", on);
  }
  function startFx3d() {
    stopFx3d();
    if (reduced()) return;
    const token = ++fx3dToken;
    import("/fx3d.js").then((mod) => {
      if (token !== fx3dToken || !report || !$("battle-replay") || $("battle-replay").hidden) return;
      fx3d = mod.create($("replay-stage"), { ...context, report, onLost: () => markFx3d(false), onRestore: () => { markFx3d(true); render(false); } });
      if (fx3d) { fx3d.setSpeed(speed); markFx3d(true); render(false); }
    }).catch(() => { fx3d = null; });
  }
  function stopFx3d() {
    fx3dToken += 1;
    if (fx3d) { fx3d.dispose(); fx3d = null; }
    markFx3d(false);
  }

  function stage() {
    const host = $("replay-stage");
    host.replaceChildren();
    const root = svg("svg", { viewBox: "0 0 1000 340", role: "img", class: "replay-svg" });
    root.append(
      svg("rect", { x: 0, y: 0, width: 1000, height: 340, class: "sky" }),
      svg("path", { d: "M0 300 L140 230 L240 290 L380 200 L520 292 L660 214 L800 290 L1000 236 L1000 340 L0 340z", class: "peaks" }),
      svg("ellipse", { cx: 180, cy: 308, rx: 240, ry: 26, class: "cloud" }),
      svg("ellipse", { cx: 760, cy: 312, rx: 260, ry: 24, class: "cloud" }),
    );
    const layer = svg("g", { id: "replay-fx" });
    const actor = (id, extra) => { const g = svg("g", { "data-actor": id, class: `actor ${id}`, transform: `translate(${POINT[id][0]} ${POINT[id][1]})` }); g.append(...extra); return g; };
    const player = actor("player", [svg("circle", { r: 34, class: "body" }), svg("text", { y: 11, "text-anchor": "middle", class: "glyph" }), svg("circle", { r: 46, class: "ward", opacity: 0 })]);
    player.querySelector(".glyph").textContent = "印";
    const main = actor("main", [svg("path", { d: "M-20 0 L0 -7 L22 0 L0 7z", class: "body" })]);
    const guard = actor("guard", [svg("path", { d: "M0 -17 L14 -9 L11 10 L0 18 L-11 10 L-14 -9z", class: "body" })]);
    const enemy = actor("enemy", [svg("path", { d: "M0 -52 L44 0 L0 52 L-44 0z", class: "body" }), svg("circle", { r: 62, class: "barrier", opacity: 0 })]);
    const npc = actor("npc", [svg("circle", { r: 14, class: "body" })]);
    for (const [id, node] of [["player", player], ["main", main], ["guard", guard], ["enemy", enemy], ["npc", npc]]) {
      const label = svg("text", { y: id === "enemy" ? 76 : id === "player" ? 58 : 30, "text-anchor": "middle", class: "caption", "data-for": id });
      node.append(label);
    }
    root.append(enemy, player, main, guard, npc, layer);
    const floaters = make("div", "replay-floaters"); floaters.id = "replay-floaters";
    host.append(root, floaters);
  }

  function pointOf(id) { return POINT[id] || POINT.enemy; }

  // 三维开启时飘字改由 DOM 层按三维投影定位；actor 为角色 id
  function floatAt(actor, text, cls, big = false) {
    if (!fx3dOn()) return float(pointOf(actor), text, cls);
    const spot = fx3d.project(actor), layer = $("replay-floaters");
    if (!spot || !layer) return;
    const node = make("span", `floater3d ${cls}${big ? " big" : ""}`, text);
    node.style.left = `${(spot.x * 100).toFixed(2)}%`; node.style.top = `${(spot.y * 100).toFixed(2)}%`;
    node.style.setProperty("--drift", `${Math.round((Math.random() - .5) * 40)}px`);
    node.style.animationDuration = `${Math.round(1100 / speed)}ms`;
    layer.append(node);
    node.addEventListener("animationend", () => node.remove());
  }

  function intensityOf(event) {
    const max = event.target === "player" ? report.player.max_hp : report.enemy.max_hp;
    return Math.abs(event.amount || 0) / Math.max(1, max) * 3;
  }

  // 三维：事件交给斗法台演出，飘字在命中时机出现
  function show3d(event, frame) {
    const k = intensityOf(event);
    fx3d.play(event, { intensity: ["damage", "shield", "poison"].includes(event.type) ? k : .45, action: frame.action });
    const later = (ms, run) => { const token = generation; effectTimers.push(setTimeout(() => { if (token === generation) run(); }, ms / speed)); };
    const hitDelay = event.source === "main" ? 620 : event.source === "enemy" ? (/重击/.test(event.label) ? 760 : 560) : /强攻/.test(frame.action || "") ? 760 : 520;
    if (event.type === "damage" && event.amount > 0) later(hitDelay, () => floatAt(event.target, `−${event.amount}`, event.target === "enemy" ? "hit" : "hurt", k >= .35));
    else if (event.type === "shield") later(hitDelay + 80, () => floatAt("enemy", `破盾 ${event.amount}`, "guard"));
    else if (event.type === "shield_absorb") later(120, () => floatAt("player", `拦截 ${event.amount}`, "guard"));
    else if (event.type === "heal" && event.amount > 0) later(200, () => floatAt("player", `+${event.amount}`, "heal"));
    else if (event.type === "poison") later(200, () => floatAt("player", `毒 −${event.amount}`, "hurt"));
    else if (event.type === "mana") later(300, () => floatAt("player", `灵力 ${event.amount}`, "guard"));
    else if (["buff", "control", "defend"].includes(event.type)) later(300, () => floatAt(event.type === "control" ? "enemy" : "player", event.label.replace(/，.*/, ""), "note"));
  }

  function float(point, text, cls) {
    const layer = $("replay-fx"); if (!layer) return;
    const node = svg("text", { x: point[0], y: point[1] - 50, "text-anchor": "middle", class: `floater ${cls}` });
    node.textContent = text; layer.append(node);
    if (reduced()) return;
    node.animate([{ transform: "translateY(0)", opacity: 1 }, { transform: "translateY(-34px)", opacity: 0 }], { duration: 900 / speed, easing: "ease-out", fill: "forwards" }).onfinish = () => node.remove();
  }

  function show(event, animate) {
    const from = pointOf(event.source), to = pointOf(event.target);
    const layer = $("replay-fx");
    const actorNode = document.querySelector(`#replay-stage [data-actor="${event.source}"]`);
    document.querySelectorAll("#replay-stage .source-active").forEach((n) => n.classList.remove("source-active"));
    actorNode?.classList.add("source-active");
    if (event.type === "damage" || event.type === "shield") {
      const path = svg("path", { d: `M${from[0]} ${from[1]} Q${(from[0] + to[0]) / 2} ${Math.min(from[1], to[1]) - 50} ${to[0]} ${to[1]}`, class: `trace ${event.source} ${event.type}` });
      layer.append(path);
      if (animate && fx3d && !fx3d.lost) fx3d.play(event, from, to, (event.amount || 0) / Math.max(1, report.enemy.max_hp) * 3);
      else if (animate && !reduced() && (event.source === "main" || event.source === "player")) {
        const bolt = svg("circle", { r: event.source === "main" ? 7 : 9, class: `bolt ${event.source}`, cx: 0, cy: 0 });
        layer.append(bolt);
        bolt.animate([{ transform: `translate(${from[0]}px, ${from[1]}px)` }, { transform: `translate(${(from[0] + to[0]) / 2}px, ${Math.min(from[1], to[1]) - 40}px)` }, { transform: `translate(${to[0]}px, ${to[1]}px)` }], { duration: 420 / speed, easing: "ease-in", fill: "forwards" }).onfinish = () => bolt.remove();
      }
      if (animate && !reduced() && actorNode && event.source === "main") {
        actorNode.animate([{ transform: `translate(${from[0]}px, ${from[1]}px)` }, { transform: `translate(${to[0] - 40}px, ${to[1]}px)` }, { transform: `translate(${from[0]}px, ${from[1]}px)` }], { duration: 640 / speed, easing: "ease-in-out" });
      }
      if (event.type === "damage" && event.amount > 0) float(to, `−${event.amount}`, event.target === "enemy" ? "hit" : "hurt");
    } else if (event.type === "shield_absorb") {
      if (animate && fx3d && !fx3d.lost) fx3d.play(event, from, to, .5);
      const ward = document.querySelector("#replay-stage .actor.player .ward");
      if (ward) { ward.setAttribute("opacity", 1); if (!reduced()) ward.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 900 / speed, fill: "forwards" }); else ward.setAttribute("opacity", .8); }
      float(pointOf("player"), `拦截 ${event.amount}`, "guard");
    } else if (event.type === "heal" && event.amount > 0) {
      if (animate && fx3d && !fx3d.lost) fx3d.play(event, pointOf("player"), pointOf("player"), .4);
      float(pointOf("player"), `+${event.amount}`, "heal");
    }
    else if (event.type === "buff" || event.type === "control" || event.type === "defend") {
      if (animate && fx3d && !fx3d.lost) fx3d.play(event, from, to, .4);
      float(event.type === "control" ? pointOf("enemy") : pointOf("player"), event.label.replace(/，.*/, ""), "note");
    }
  }

  function sceneEffects(frame, animate) {
    for (const id of effectTimers) clearTimeout(id);
    effectTimers = [];
    const layer = $("replay-fx"); layer.replaceChildren();
    document.querySelectorAll("#replay-stage .source-active").forEach((n) => n.classList.remove("source-active"));
    const events = (frame.events || []).filter((e) => FX_TYPES.has(e.type));
    if (!events.length) return;
    if (fx3dOn()) {
      if (!animate) return;
      // 斗法台节奏：本方先手 → 法宝/同行追击 → 敌方反击，彼此错开以便看清每一招
      const token = generation; let delay = 0;
      events.forEach((event) => {
        const run = () => { if (token === generation && !document.hidden && fx3dOn()) show3d(event, frame); };
        if (!delay) run(); else effectTimers.push(setTimeout(run, delay / speed));
        delay += event.source === "main" ? 420 : event.type === "shield_absorb" ? 120 : 330;
      });
      return;
    }
    if (!animate || reduced()) { show(events.find((e) => e.type === "shield_absorb") || events.find((e) => e.source === "main") || events[0], false); return; }
    const token = generation, gap = Math.min(260, 1000 / events.length) / speed;
    events.forEach((event, index) => { const run = () => { if (token === generation && !document.hidden) show(event, true); }; if (!index) run(); else effectTimers.push(setTimeout(run, index * gap)); });
  }

  function meter(id, value, max, text) {
    const safe = Math.max(1, Number(max || 0)); const pct = Math.max(0, Math.min(100, Number(value || 0) / safe * 100));
    const node = $(id); node.firstElementChild.style.width = pct + "%";
    node.setAttribute("aria-valuemin", "0"); node.setAttribute("aria-valuemax", String(safe)); node.setAttribute("aria-valuenow", String(Math.max(0, Number(value || 0))));
    $(id + "-text").textContent = `${text} ${Math.max(0, value)} / ${max}`;
  }

  function eventText(e) {
    return `${ACTOR[e.source] || e.source || "交锋"} · ${e.label}${typeof e.amount === "number" && e.type !== "status" ? ` ${e.amount}` : ""}`;
  }

  function render(animate = true) {
    const frame = report.frames[cursor];
    const treasure = report.treasures || {};
    document.querySelector('#replay-stage [data-actor="main"]').style.display = treasure.main ? "" : "none";
    document.querySelector('#replay-stage [data-actor="guard"]').style.display = treasure.guard ? "" : "none";
    const captions = { player: "修士灵印", enemy: report.enemy.name, main: treasure.main ? `${treasure.main.quality}本命法宝` : "", guard: treasure.guard ? `${treasure.guard.quality}护持法宝` : "", npc: "同行" };
    for (const node of document.querySelectorAll("#replay-stage .caption")) node.textContent = captions[node.dataset.for] || "";
    const hasNpc = report.frames.some((f) => (f.events || []).some((e) => e.source === "npc"));
    document.querySelector('#replay-stage [data-actor="npc"]').style.display = hasNpc ? "" : "none";
    $("replay-stage").dataset.enemy = report.enemy.kind;
    $("replay-stage").classList.toggle("enemy-barrier", (frame.enemy.barrier || 0) > 0);
    document.querySelector("#replay-stage .actor.enemy .barrier")?.setAttribute("opacity", (frame.enemy.barrier || 0) > 0 ? .75 : 0);
    document.querySelector("#replay-stage .actor.enemy")?.classList.toggle("down", frame.enemy.hp <= 0);
    document.querySelector("#replay-stage .actor.player")?.classList.toggle("down", frame.player.hp <= 0 && report.outcome === "defeat" && cursor === report.frames.length - 1);
    meter("replay-player-hp", frame.player.hp, report.player.max_hp, "本方气血");
    meter("replay-player-mp", frame.player.mp, report.player.max_mp, "本方灵力");
    meter("replay-enemy-hp", frame.enemy.hp, report.enemy.max_hp, "敌方气血");
    const events = (frame.events || []).filter((e) => !e.fx_only);
    $("replay-now").textContent = cursor === 0 ? "双方就位，自动斗法即将开始。" : `第 ${frame.round} 拍 · ${frame.action}${events.length ? "：" + events.map(eventText).join("；") : ""}`;
    $("replay-intent").textContent = cursor === report.frames.length - 1 ? "" : `敌方下一意图：${frame.intent}`;
    $("replay-round").textContent = `第 ${frame.round} / ${report.rounds} 拍`;
    $("replay-timeline").value = String(cursor);
    const log = [];
    for (const f of report.frames.slice(1, cursor + 1)) for (const e of (f.events || []).filter((x) => !x.fx_only)) { const li = make("li", "", `第${f.round}拍 · ${eventText(e)}`); log.push(li); }
    $("replay-log").replaceChildren(...log.slice(-60));
    const last = cursor === report.frames.length - 1;
    $("replay-result").hidden = !last;
    if (last) {
      $("replay-result-title").textContent = OUTCOME[report.outcome] || report.outcome;
      $("replay-result-text").textContent = `共 ${report.rounds} 拍，策略：${report.strategy_label}。战果与损耗已在本次提交时结算并保存；回放只是复盘，不会重复结算。`;
    }
    $("replay-play").textContent = playing ? "暂停播放" : last ? "重新播放" : "继续播放";
    if (fx3dOn()) {
      if (!animate) { fx3d.clear(); $("replay-floaters")?.replaceChildren(); }
      fx3d.setFrame(frame, { last, outcome: report.outcome, animate });
    }
    sceneEffects(frame, animate);
  }

  function schedule() {
    clearTimeout(timer);
    const token = generation;
    timer = setTimeout(() => {
      if (!playing || token !== generation) return;
      if (cursor < report.frames.length - 1) { cursor += 1; render(true); schedule(); } else pause();
    }, (fx3dOn() ? (cursor === 0 ? 2300 : 1750) : 1300) / speed);   // 三维入场镜头与连招需要更长一拍
  }

  function play() { if (cursor >= report.frames.length - 1) cursor = 0; playing = true; render(false); schedule(); }
  function pause() { playing = false; clearTimeout(timer); for (const id of effectTimers) clearTimeout(id); effectTimers = []; if (report) $("replay-play").textContent = cursor >= report.frames.length - 1 ? "重新播放" : "继续播放"; }

  function open(data, ctx = {}) {
    if (!data?.frames?.length) return;
    build(); generation += 1; report = data; context = ctx || {}; cursor = 0; speed = 1;
    $("replay-speed").textContent = "速度 1×";
    $("replay-title").textContent = `${data.enemy.name} · ${OUTCOME[data.outcome] || ""}`;
    $("replay-timeline").max = String(data.frames.length - 1);
    stage();
    startFx3d();
    opener = document.activeElement;
    $("battle-replay").hidden = false;
    document.body.classList.add("replay-open");
    $("replay-close").focus({ preventScroll: true });
    if (reduced()) { cursor = data.frames.length - 1; render(false); playing = false; } else { play(); }
  }

  function close() {
    if (!$("battle-replay") || $("battle-replay").hidden) return;
    generation += 1; pause(); stopFx3d();
    $("battle-replay").hidden = true; document.body.classList.remove("replay-open");
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
  }

  globalThis.BattleReplay = { open, close, isOpen: () => !!$("battle-replay") && !$("battle-replay").hidden };
})();
