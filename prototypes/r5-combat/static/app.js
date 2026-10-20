"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const make = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
  let config = null;
  let run = null;
  let cursor = 0;
  let playing = false;
  let speed = 1;
  let timer = null;
  let generation = 0;
  let controller = null;
  let loading = false;
  let effectTimers = [];
  let effectGeneration = 0;
  const outcomeLabels = { win: "胜势已定", loss: "此战暂退", window: "十二拍 · 试锋已毕", stalemate: "交锋至限" };
  const scenarioDescriptions = { den: "毒巢妖兽：关注重击、防御与残毒。", forge: "炉甲守卫：关注护盾吸收与焚火破盾。", tower: "沉星守卫：关注常击汲灵与灵力压力。", boss: "十二拍个人评分，同行NPC输出单独统计。", dungeon: "混合机制连战实验：毒 → 护盾 → 汲灵，非正式副本配置。" };
  function error(message) { $("error").hidden = !message; $("error").textContent = message; }
  function option(select, entries, selected) {
    select.replaceChildren(...entries.map((entry) => { const node = make("option", "", entry.label); node.value = entry.value; return node; }));
    select.value = selected;
    select.disabled = false;
  }
  function stopPlayback() { playing = false; clearTimeout(timer); timer = null; cancelSceneEffects(false); $("play-pause").textContent = cursor >= (run?.frames.length || 1) - 1 ? "从头播放" : "继续播放"; }
  function controls() {
    $("simulate").disabled = loading || !config;
    $("quick-simulate").disabled = loading || !config;
    $("simulate").firstChild.textContent = loading ? "正在演算… " : "预备 · 自动交锋 ";
    document.body.classList.toggle("busy", loading);
    for (const id of ["play-pause", "speed", "skip", "timeline"]) $(id).disabled = !run || loading;
    $("phase").textContent = loading ? "后端演算中" : !run ? "等待整备" : cursor === run.frames.length - 1 ? "实验结算" : playing ? "自动观战中" : "播放已暂停";
  }
  function currentInput() {
    const data = new FormData($("setup-form"));
    return { scenario: data.get("scenario"), build: data.get("build"), strategy: data.get("strategy"), pill_budget: Number(data.get("pill_budget")), fire_budget: Number(data.get("fire_budget")), guard_budget: Number(data.get("guard_budget")), soul_budget: Number(data.get("soul_budget")), npc: data.has("npc") };
  }
  function previewConfig() {
    if (!config || run) return;
    const input = currentInput();
    $("arena").dataset.enemy = input.scenario === "dungeon" ? "den" : input.scenario;
    $("arena").dataset.build = input.build;
    $("scene-title").textContent = config.scenarios.find((entry) => entry.value === input.scenario)?.label || "试炼场景";
    $("scene-label").textContent = "云海御空 · 场景预览";
    $("enemy-name").textContent = $("enemy-caption").textContent = ({ den: "毒巢妖兽", forge: "炉甲守卫", tower: "沉星守卫", boss: "界门巨影", dungeon: "三战试炼" })[input.scenario];
    $("companion").hidden = !input.npc;
    updateTreasures(input, null);
    $("enemy-intent").textContent = scenarioDescriptions[input.scenario];
  }
  function configDescription() {
    $("scenario-description").textContent = config.scenarios.find((entry) => entry.value === $("scenario").value)?.description || "";
    $("strategy-description").textContent = config.strategies.find((entry) => entry.value === $("strategy").value)?.description || "";
    renderPreparationRules();
    previewConfig();
  }
  function renderPreparationRules() {
    const root = $("preparation-rule-content");
    root.replaceChildren();
    const selected = $("setup-form").elements.build.value;
    const detail = config.build_details?.find((entry) => entry.value === selected);
    if (detail) {
      root.append(make("h3", "", detail.label));
      const rows = make("dl");
      for (const [label, value] of [["效果", detail.effect], ["冷却", detail.cd], ["起手预热", detail.initial_delay]]) {
        const row = make("div"); row.append(make("dt", "", label), make("dd", "", String(value ?? "—"))); rows.append(row);
      }
      root.append(rows);
    }
    for (const [title, lines] of [["共同战斗规则", config.preparation_rules?.common], ["虚拟补给规则", config.preparation_rules?.consumables]]) {
      if (!lines?.length) continue;
      root.append(make("h4", "", title));
      const list = make("ul");
      for (const line of lines) list.append(make("li", "", line));
      root.append(list);
    }
    if (!root.childElementCount) root.append(make("p", "hint", "实验后端尚未提供规则说明。"));
  }
  function setMeter(id, value, max, label) {
    const safeMax = Math.max(1, Number(max || 0));
    const percentage = Math.max(0, Math.min(100, Number(value || 0) / safeMax * 100));
    const fill = $(id + "-fill");
    fill.style.width = percentage + "%";
    const meter = fill.parentElement;
    meter.setAttribute("role", "meter"); meter.setAttribute("aria-label", label);
    meter.setAttribute("aria-valuemin", "0"); meter.setAttribute("aria-valuemax", String(safeMax)); meter.setAttribute("aria-valuenow", String(Math.max(0, Math.min(safeMax, Number(value || 0)))));
    $(id).textContent = `${label} ${value} / ${max}`;
  }
  function renderRoute(frame) {
    const nodes = frame.nodes || run.nodes || [];
    $("route").replaceChildren(...nodes.map((node) => {
      const complete = node.status === "complete";
      const li = make("li", complete ? "cleared" : node.id === frame.node ? "current" : "");
      const button = make("button"); button.type = "button"; button.dataset.node = String(node.id);
      const label = complete ? "已通过" : node.id === frame.node ? "当前" : "尚未播放";
      button.setAttribute("aria-label", `${node.label}，${label}，回看实验轨迹`);
      button.append(make("span", "node-number", complete ? "✓" : String(node.id)), make("span", "", node.label));
      const target = run.frames.findIndex((entry) => entry.node === node.id);
      button.disabled = target < 0;
      button.addEventListener("click", () => { stopPlayback(); cursor = target; renderFrame(false); });
      li.append(button); return li;
    }));
  }
  function cancelSceneEffects(reset) {
    effectGeneration += 1;
    for (const timerId of effectTimers) clearTimeout(timerId);
    effectTimers = [];
    if (!reset) { $("air-effects").pauseAnimations?.(); return; }
    $("air-effects").unpauseAnimations?.();
    $("arena").dataset.flight = "false";
    $("air-effects").replaceChildren();
    $("air-impact").classList.remove("visible");
    document.querySelectorAll(".source-active").forEach((node) => node.classList.remove("source-active"));
    for (const key of ["currentSource", "currentTarget", "eventId", "eventTick", "effect"]) delete $("arena").dataset[key];
    $("source-caption").textContent = "云海御空 · 两宝随身";
  }
  function updateTreasures(input, frame) {
    for (const slot of ["main", "secondary"]) {
      const mode = input.build === "burst" ? "burst" : input.build === "guard" && slot === "secondary" ? "guard" : "sustain";
      const treasure = $(slot + "-treasure");
      treasure.dataset.mode = mode;
      const skill = frame?.cooldowns?.find((entry) => entry.id === slot);
      const charging = mode === "burst" && !!skill && skill.remaining > 0 && skill.remaining <= 2;
      treasure.classList.toggle("charging", charging);
      treasure.dataset.charge = charging ? String(skill.remaining) : "0";
      $(slot + "-treasure-name").textContent = `${slot === "main" ? "本命" : "护持"} · ${{ sustain: "持续", burst: "蓄势", guard: "屏障" }[mode]}`;
      $(slot + "-treasure-cd").textContent = skill ? skill.remaining ? `冷却余${skill.remaining}拍${charging ? " · 聚光" : ""}` : "冷却就绪" : "等待演算";
    }
    if (frame) {
      const shield = frame.statuses?.find((entry) => entry.label === "玩家护盾");
      $("player-ward").hidden = !(Number(shield?.value || 0) > 0);
    } else $("player-ward").hidden = true;
  }
  function displaySceneEvent(event, frame, animate) {
    $("air-effects").replaceChildren();
    $("air-impact").classList.remove("visible");
    document.querySelectorAll(".source-active").forEach((node) => node.classList.remove("source-active"));
    const arena = $("arena");
    arena.dataset.currentSource = event.source;
    arena.dataset.currentTarget = event.target;
    arena.dataset.eventId = event.id;
    arena.dataset.eventTick = String(event.tick);
    const sourceNode = event.source === "main" || event.source === "secondary" ? $(event.source + "-treasure") : document.querySelector(`[data-actor="${event.source}"]`);
    sourceNode?.classList.add("source-active");
    const mode = sourceNode?.dataset.mode;
    const hostileShield = event.type === "shield" && event.target === "enemy";
    const effect = event.type === "shield_absorb" ? "absorb" : hostileShield ? "break" : event.type === "shield" && event.target === "player" ? "ward" : event.type === "damage" && mode === "burst" ? "burst" : event.type === "damage" && ["main", "secondary"].includes(event.source) ? "sustain" : event.type === "damage" && event.source === "player" && frame.decision === "skill" ? "skill" : event.type;
    arena.dataset.effect = effect;
    $("source-caption").textContent = eventText(event);
    const bounds = arena.getBoundingClientRect();
    const position = (node) => {
      const rect = node?.getBoundingClientRect();
      return rect ? [(rect.left + rect.width / 2 - bounds.left) / bounds.width * 1000, (rect.top + rect.height / 2 - bounds.top) / bounds.height * 365] : null;
    };
    const points = Object.fromEntries(["player", "enemy", "npc"].map((actor) => [actor, position(document.querySelector(`[data-actor="${actor}"]`))]));
    points.main = position($("main-treasure")); points.secondary = position($("secondary-treasure"));
    let start = points[event.source], end = points[event.target];
    if (effect === "absorb") { start = points.enemy; end = [points.player[0] + (document.querySelector("[data-actor=player]").getBoundingClientRect().width / 2 + 12) / bounds.width * 1000, points.player[1]]; }
    if (start && end && (event.type === "damage" || hostileShield || ["absorb", "ward", "control"].includes(effect))) {
      const curveY = effect === "burst" ? (start[1] + end[1]) / 2 : Math.min(start[1], end[1]) - (event.source === "secondary" ? -30 : 45);
      const d = `M${start[0]} ${start[1]} Q${(start[0] + end[0]) / 2} ${curveY} ${end[0]} ${end[1]}`;
      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
      for (const [name, value] of Object.entries({ id: "energy-arrow", markerWidth: "9", markerHeight: "9", refX: "7", refY: "4", orient: "auto", markerUnits: "userSpaceOnUse" })) marker.setAttribute(name, value);
      const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
      arrow.setAttribute("d", "M0 0 8 4 0 8 2 4z"); arrow.setAttribute("fill", "currentColor"); marker.append(arrow); defs.append(marker); $("air-effects").append(defs);
      for (const className of ["energy-underlay", `energy-trace ${effect}`]) {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d); path.setAttribute("class", className); path.setAttribute("pathLength", "200");
        if (className.startsWith("energy-trace")) path.setAttribute("marker-end", "url(#energy-arrow)");
        if (!animate) path.style.animation = "none";
        $("air-effects").append(path);
      }
      if (animate && ["main", "secondary"].includes(event.source) && ["sustain", "burst", "break", "ward"].includes(effect)) {
        const ns = "http://www.w3.org/2000/svg";
        const flyer = document.createElementNS(ns, "g");
        flyer.setAttribute("class", `flying-artifact ${mode}`);
        flyer.dataset.flightSource = event.source;
        flyer.dataset.eventId = event.id;
        const shape = sourceNode.querySelector(`.artifact-${mode}`).cloneNode(true);
        shape.removeAttribute("class");
        const sourceBounds = sourceNode.getBoundingClientRect();
        shape.setAttribute("transform", `scale(${sourceBounds.width / bounds.width * 1000 / 60} ${sourceBounds.height / bounds.height * 365 / 60}) translate(-30 -30)`);
        flyer.append(shape);
        const motion = document.createElementNS(ns, "animateMotion");
        motion.setAttribute("path", `${d} Q${(start[0] + end[0]) / 2} ${curveY + 25} ${start[0]} ${start[1]}`);
        motion.setAttribute("dur", `${Math.min(200, 1000 / Math.max(1, frame.events.filter((entry) => ["damage", "shield", "shield_absorb", "poison", "heal", "control", "buff", "defend"].includes(entry.type)).length)) / speed / 1000 * .82}s`);
        motion.setAttribute("rotate", "auto"); motion.setAttribute("fill", "freeze");
        motion.setAttribute("keyPoints", "0;.5;.5;1"); motion.setAttribute("keyTimes", "0;.4;.6;1"); motion.setAttribute("calcMode", "linear");
        flyer.append(motion); $("air-effects").append(flyer); motion.beginElement();
        arena.dataset.flight = "true";
      } else arena.dataset.flight = "false";
      $("air-impact").style.left = `${end[0] / 10}%`;
      $("air-impact").style.top = `${end[1] / 365 * 100}%`;
      $("air-impact").classList.add("visible");
    }
  }
  function sceneEvents(frame, animate) {
    cancelSceneEffects(true);
    $("arena").dataset.frameTick = String(frame.tick);
    $("arena").dataset.simulationId = run.simulation_id;
    updateTreasures(run.input, frame);
    const events = (frame.events || []).filter((event) => ["damage", "shield", "shield_absorb", "poison", "heal", "control", "buff", "defend"].includes(event.type));
    if (!events.length) return;
    if (!animate || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const selected = events.find((event) => event.type === "shield_absorb") || events.find((event) => ["main", "secondary"].includes(event.source) && event.type === "damage") || events.find((event) => ["main", "secondary"].includes(event.source)) || events[0];
      displaySceneEvent(selected, frame, false);
      return;
    }
    const token = effectGeneration;
    const runToken = generation;
    const delay = Math.min(200, 1000 / events.length) / speed;
    events.forEach((event, index) => {
      const show = () => { if (effectGeneration === token && generation === runToken) displaySceneEvent(event, frame, true); };
      if (!index) show(); else effectTimers.push(setTimeout(show, index * delay));
    });
  }
  function renderSkills(frame) {
    const input = run.input;
    const budgetFor = { pill: input.pill_budget, fire: input.fire_budget, guard: input.guard_budget, soul: input.soul_budget };
    const symbols = { skill: "斩", main: "命", secondary: "护", pill: "丹", fire: "火", guard: "御", soul: "镇" };
    $("skills").replaceChildren(...(frame.cooldowns || []).filter((skill) => !Object.hasOwn(budgetFor, skill.id) || budgetFor[skill.id] > 0).map((skill) => {
      const block = make("div", "skill"); block.dataset.skill = skill.id;
      const mark = make("span", "skill-mark", symbols[skill.id] || "术"); mark.setAttribute("aria-hidden", "true");
      mark.style.setProperty("--cd", `${Math.max(0, Math.min(100, Number(skill.remaining) / Math.max(1, Number(skill.total)) * 100))}%`);
      const copy = make("div", "skill-copy"); copy.append(make("strong", "", skill.name), make("small", "", skill.remaining ? `冷却余 ${skill.remaining} 拍` : "冷却就绪"));
      block.append(mark, copy); return block;
    }));
  }
  function eventText(event) {
    const actor = { player: "本方", main: "本命法宝", secondary: "护持法宝", enemy: "敌方", npc: "同行NPC", companion: "同行NPC" };
    return `${actor[event.source] || event.source || "交锋"} · ${event.label}${typeof event.amount === "number" ? ` ${event.amount}` : ""}`;
  }
  function renderLog(frame) {
    const events = (run.events || []).filter((event) => event.tick <= frame.tick);
    $("event-count").textContent = `${events.length} 条已播放事件`;
    $("event-log").replaceChildren(...events.slice(-200).map((event) => { const li = make("li", "", `第${event.tick}拍 / 节点${event.node} · ${eventText(event)}`); li.dataset.eventId = event.id; return li; }));
  }
  function renderBossScore(frame) {
    const boss = run.input.scenario === "boss";
    $("boss-score").hidden = !boss;
    if (!boss) return;
    const events = (run.events || []).filter((event) => event.tick <= frame.tick && event.type === "damage" && event.target === "enemy");
    const personal = events.filter((event) => ["player", "main", "secondary"].includes(event.source)).reduce((sum, event) => sum + Number(event.amount || 0), 0);
    const npc = events.filter((event) => ["npc", "companion"].includes(event.source)).reduce((sum, event) => sum + Number(event.amount || 0), 0);
    $("boss-window").textContent = `已播放 ${frame.tick} / ${config.limits.boss_ticks} 拍 · 仅回放进度`;
    $("boss-personal").textContent = String(personal);
    $("boss-npc").textContent = String(npc);
    $("boss-reference").textContent = `参考输出 ${run.metrics.boss_reference} · 本人已达 ${Math.floor(personal / Math.max(1, run.metrics.boss_reference) * 100)}%（实验，无正式奖励）`;
    $("boss-score-fill").style.width = `${Math.max(0, Math.min(100, personal / Math.max(1, run.metrics.boss_reference) * 100))}%`;
  }
  function renderResult() {
    const final = cursor === run.frames.length - 1;
    $("result").hidden = !final;
    if (!final) return;
    const metrics = run.metrics;
    $("result-title").textContent = outcomeLabels[metrics.outcome] || metrics.outcome;
    $("end-reason").textContent = metrics.end_reason;
    const rows = [["个人总伤害", metrics.player_damage], ["其中法宝", metrics.treasure_damage], ["同行NPC伤害", metrics.npc_damage], ["交锋拍数", metrics.rounds], ["承受伤害", metrics.damage_taken], ["减免伤害", metrics.damage_prevented], ["丹药实际使用", metrics.pills_used], ["火 / 护 / 魂符", `${metrics.fire_used} / ${metrics.guard_used} / ${metrics.soul_used}`]];
    if (run.input.scenario === "boss") rows.push(["个人评分封顶值", metrics.boss_capped_score], ["参考伤害", metrics.boss_reference]);
    $("metrics").replaceChildren(...rows.map(([label, value]) => { const row = make("div"); row.append(make("dt", "", label), make("dd", "", String(value ?? "—"))); return row; }));
  }
  function renderFrame(animate = true) {
    if (!run) return;
    const frame = run.frames[cursor];
    const player = frame.player, enemy = frame.enemy;
    $("arena").dataset.enemy = enemy.type;
    $("arena").dataset.build = run.input.build;
    $("arena").dataset.enemyDefeated = String(enemy.hp <= 0);
    $("arena").dataset.playerDefeated = String(player.hp <= 0);
    $("companion").hidden = !run.input.npc;
    $("scene-title").textContent = config.scenarios.find((entry) => entry.value === run.input.scenario)?.label || "自动交锋";
    $("scene-label").textContent = `云海斗法 · ${run.input.scenario === "dungeon" ? "混合机制连战" : "实验轨迹"} · 第${frame.node}节点`;
    $("round-label").textContent = `第 ${frame.tick} 拍 / ${run.frames.at(-1).tick} 拍`;
    $("enemy-name").textContent = $("enemy-caption").textContent = enemy.name;
    setMeter("player-hp", player.hp, player.max_hp, "气血"); setMeter("player-mp", player.mp, player.max_mp, "灵力"); setMeter("enemy-hp", enemy.hp, enemy.max_hp, "气血");
    $("enemy-shield").hidden = !enemy.barrier; $("enemy-shield").textContent = `护盾 ${enemy.barrier}`; $("barrier-ring").hidden = !enemy.barrier;
    $("enemy-intent").textContent = enemy.hp <= 0 ? "敌方气血归零 · 本节点结束" : player.hp <= 0 ? "本方气血归零 · 查看战后复盘" : `敌方下一意图 · ${enemy.intent}`;
    $("statuses").replaceChildren(...(frame.statuses || []).filter((entry) => entry.value !== "0" && entry.value !== 0).map((entry) => make("span", "", `${entry.label} ${entry.value}`)));
    const events = frame.events || [];
    $("current-event").textContent = events.length ? events.map(eventText).join("；") : frame.tick === 0 ? "双方就位，准备交锋。" : "本拍无额外事件。";
    $("timeline").value = String(cursor); $("frame-label").textContent = `${cursor + 1} / ${run.frames.length}`;
    $("decision-reason").textContent = frame.decision_reason || "";
    sceneEvents(frame, animate);
    renderBossScore(frame); renderSkills(frame); renderRoute(frame); renderLog(frame); renderResult(); controls();
  }
  function schedule() {
    clearTimeout(timer);
    const token = generation;
    if (run && cursor === run.frames.length - 1) {
      timer = setTimeout(() => {
        if (token !== generation || !playing) return;
        stopPlayback(); controls();
      }, 1100 / speed);
      return;
    }
    timer = setTimeout(() => {
      if (!playing || token !== generation || !run) return;
      if (cursor < run.frames.length - 1) { cursor += 1; renderFrame(); }
      schedule();
    }, 1300 / speed);
  }
  function play() {
    if (!run) return;
    if (cursor === run.frames.length - 1) cursor = 0;
    playing = true; $("play-pause").textContent = "暂停播放"; renderFrame(false); schedule();
  }
  $("setup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!config || !$("setup-form").reportValidity()) return;
    const input = currentInput();
    stopPlayback(); cancelSceneEffects(true); generation += 1; const token = generation;
    controller?.abort(); const requestController = new AbortController(); controller = requestController;
    loading = true; error(""); controls();
    const timeout = setTimeout(() => requestController.abort(), 15000);
    try {
      const response = await fetch("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input), signal: requestController.signal });
      const data = await response.json();
      if (token !== generation) return;
      if (!response.ok || !data.ok || !data.experimental || !data.frames?.length) throw new Error(data.error?.message || data.error || "实验返回无有效帧，请重试。");
      run = data; cursor = 0; loading = false;
      $("timeline").max = String(run.frames.length - 1);
      if (matchMedia("(max-width: 760px)").matches) $("preparation-details").open = false;
      play();
      if (matchMedia("(max-width: 760px)").matches) document.querySelector(".workspace-heading").scrollIntoView({ block: "start", behavior: "instant" });
    } catch (failure) {
      if (token !== generation) return;
      error(failure.name === "AbortError" ? "实验请求中断或超时；没有连接正式存档，可重新演算。" : String(failure.message));
    } finally { clearTimeout(timeout); if (token === generation) { loading = false; controls(); } }
  });
  $("quick-simulate").addEventListener("click", () => $("setup-form").requestSubmit());
  $("play-pause").addEventListener("click", () => { if (playing) { stopPlayback(); controls(); } else play(); });
  $("speed").addEventListener("click", () => { speed = speed === 1 ? 2 : 1; $("speed").textContent = `速度 ${speed}×`; if (playing) schedule(); });
  $("skip").addEventListener("click", () => { stopPlayback(); cursor = run.frames.length - 1; renderFrame(false); $("result").scrollIntoView({ block: "nearest" }); });
  $("replay").addEventListener("click", () => { stopPlayback(); cursor = 0; play(); });
  $("timeline").addEventListener("input", () => { stopPlayback(); cursor = Number($("timeline").value); renderFrame(false); });
  $("setup-form").addEventListener("change", () => { configDescription(); if (run) $("phase").textContent = "新整备待演算"; });
  document.addEventListener("visibilitychange", () => { if (document.hidden && playing) { stopPlayback(); controls(); } });
  window.addEventListener("resize", () => { if (run) sceneEvents(run.frames[cursor], false); });
  window.addEventListener("pagehide", () => { generation += 1; stopPlayback(); controller?.abort(); });
  (async () => {
    try {
      const response = await fetch("/api/config"); if (!response.ok) throw new Error("无法读取实验配置。"); config = await response.json();
      option($("scenario"), config.scenarios, config.defaults.scenario); option($("strategy"), config.strategies, config.defaults.strategy);
      $("build-options").replaceChildren(...config.builds.map((build) => {
        const label = make("label", "build-choice"); const radio = make("input"); radio.type = "radio"; radio.name = "build"; radio.value = build.value; radio.checked = build.value === config.defaults.build; radio.required = true;
        label.append(radio, make("strong", "", build.label)); return label;
      }));
      for (const name of ["pill_budget", "fire_budget", "guard_budget", "soul_budget"]) { const field = $("setup-form").elements[name]; field.max = String(config.limits[name]); field.value = String(config.defaults[name]); }
      $("setup-form").elements.npc.checked = config.defaults.npc;
      if (matchMedia("(max-width: 760px)").matches) $("preparation-details").open = false;
      configDescription(); controls();
    } catch (failure) { error(String(failure.message)); }
  })();
})();
