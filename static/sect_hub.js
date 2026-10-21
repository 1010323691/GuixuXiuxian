"use strict";

// 三维宗门主界面：PC HUD、建筑入口标记、二维降级图录与快捷键。
// 只读 app.js 派发的快照（guixu:render / guixu:growth），从不发请求、不写进度；
// 建筑点击与菜单入口都派发 guixu:open，由 app.js 打开同一套卷目，写操作仍走原事项卡的提交、确认与同步流程。
(() => {
  const $ = (id) => document.getElementById(id);
  const body = document.body;
  // 与 src/sect/layout.ts 的 ENTRIES 保持一致（tests/test_sect3d.py 校验）；降级图录在三维包加载失败时也要能用
  const ENTRIES = [
    { id: "main-hall", label: "主殿 · 宗门", page: "sects" },
    { id: "gate", label: "山门 · 九州行旅", page: "world" },
    { id: "plaza", label: "迎仙广场 · 闻道", page: "quests" },
    { id: "scripture", label: "藏经阁 · 功法", page: "character", action: "world_skill_learn" },
    { id: "alchemy", label: "炼丹阁 · 四艺", page: "craft" },
    { id: "portal", label: "秘境传送阵 · 副本", page: "exploration" },
    { id: "forge", label: "炼器阁 · 四艺", page: "craft" },
    { id: "sword-platform", label: "试剑台 · NPC演武", page: "arena" },
    { id: "pavilion", label: "观剑亭 · 名录", page: "achievements" },
    { id: "disciples", label: "弟子居所 · 人物", page: "character" },
    { id: "elders", label: "长老居所 · 同道", page: "social" },
    { id: "cave", label: "修炼洞府 · 洞府", page: "estate" },
    { id: "market", label: "坊市亭 · NPC坊市", page: "market" },
  ];
  const params = new URLSearchParams(location.search);
  const reducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let snapshot = null, growth = null, active = false, controller = null, loading = null, sceneFailed = false, hadBattle = false;
  let markerNodes = new Map(), lastMarkerAt = 0, restoreFocus = null;
  let view = "page";         // 小窗当前内容：page 卷目 / dossier 卷宗 / growth 潜修 / legacy 序章旧事
  const moved = [];          // [node, parent, nextSibling] 宗门模式下迁移的节点：账号与同步进设置菜单，潜修栏进小窗

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  const number = (value) => new Intl.NumberFormat("zh-CN").format(value);
  const page = (id) => snapshot?.view.world?.pages?.find((entry) => entry.id === id) || null;
  function row(pageId, title, label) {
    const section = page(pageId)?.sections?.find((entry) => entry.title === title);
    return section?.rows?.find((entry) => entry.label === label)?.value;
  }
  const replayOpen = () => body.classList.contains("replay-open");
  const panelOpen = () => body.classList.contains("sect-panel-open");

  // ------------------------------------------------------------------ 小窗：打开卷目（建筑与菜单共用）、卷宗、潜修与序章旧事
  function open(pageId, detail = {}, fromScene = false) {
    if (!page(pageId)) return;
    // 从 HUD 打开时镜头也飞向对应建筑，与点击建筑看到的是同一处
    if (!fromScene) { const entry = ENTRIES.find((item) => item.page === pageId); if (entry) controller?.focus(entry.id, false); }
    setPanel(true, "page");
    document.dispatchEvent(new CustomEvent("guixu:open", { detail: { page: pageId, ...detail } }));
    renderWindow();
  }
  function openDossier(tab, from) {
    restoreFocus = from || null;
    setPanel(true, "dossier");
    document.querySelector(`#side-tabs [data-side-tab="${tab}"]`)?.click();     // 原卷宗页签的切换与分页
  }
  function openGrowth(from) {
    restoreFocus = from || null;
    setPanel(true, "growth");
    $("growth-details").open = true;
  }
  function openLegacy(from) {
    restoreFocus = from || null;
    setPanel(true, "legacy");
    if ($("legacy-history").hidden) $("legacy-history-button").click();       // 原“序章旧事”开合逻辑
  }
  const WINDOWS = {
    dossier: ["卷宗", "任务 · 回执 · 本卷进度", "#i-scroll"],
    growth: ["潜修", "在线离线同速 · 无需领取 · 详情以服务端为准", "#i-lotus"],
    legacy: ["序章旧事", "旧卷 · 只读，不执行序章行动", "#i-scroll"],
  };
  function renderWindow() {
    if (!panelOpen()) return;
    let [title, sub, icon] = WINDOWS[view] || [];
    if (view === "page") {
      const nav = document.querySelector("[data-world-page][aria-pressed='true']");
      title = nav?.title || $("world-page-title").textContent;
      sub = [$("world-page-number").textContent, "NPC 模拟 · 无真人"].filter(Boolean).join(" · ");
      icon = nav?.querySelector("use")?.getAttribute("href") || "#i-scroll";
    }
    $("sect-window-title").textContent = title;
    $("sect-window-sub").textContent = sub;
    $("sect-window-icon").setAttribute("href", icon);
  }
  function openFrom(button) {
    const detail = {};
    if (button.dataset.action) detail.action = button.dataset.action;
    if (button.dataset.section) detail.section = button.dataset.section;
    restoreFocus = button;
    open(button.dataset.open, detail);
  }
  function setPanel(on, nextView = "page") {
    const was = panelOpen(), previous = view;
    if (on) { view = nextView; $("world-workbench").dataset.sectView = view; }
    if (on === was && view === previous) return;
    body.classList.toggle("sect-panel-open", on);
    $("sect-window-bar").hidden = !on;
    // 离开“序章旧事”时按原关闭按钮收起旧卷（其监听只在仍停留于该视图时才合上小窗）
    if (previous === "legacy" && (!on || view !== "legacy") && !$("legacy-history").hidden) $("legacy-history-close").click();
    renderWindow();
    syncPause();
    updateShift();
    document.dispatchEvent(new CustomEvent("guixu:panel", { detail: { open: on && view === "page" } }));
    if (on && !was) $("sect-panel-close").focus({ preventScroll: true });
    else if (!on) { (restoreFocus?.isConnected && restoreFocus.offsetParent ? restoreFocus : $("sh-home"))?.focus({ preventScroll: true }); restoreFocus = null; }
  }
  // 小窗只占右侧，场景与 HUD 仍可操作，因此不再暂停场景；只有战报回放与离开宗门模式时暂停
  function syncPause() { controller?.setPaused(replayOpen() || !active); }
  /** 小窗打开时把画面中心移到左侧空地（任务追踪与小窗之间），聚焦的建筑不被小窗遮住。 */
  function updateShift() {
    if (!controller) return;
    let shift = 0;
    if (panelOpen()) {
      const win = $("world-workbench").getBoundingClientRect();
      const tracker = document.querySelector(".sh-tracker")?.getBoundingClientRect();
      const free = tracker?.width ? tracker.right : 0;
      if (win.width && win.width < innerWidth * .8 && win.left > free + 120) shift = innerWidth / 2 - (free + win.left) / 2;
    }
    controller.setViewShift(shift);
  }

  // ------------------------------------------------------------------ 模式切换
  function setMode(on) {
    active = on;
    body.classList.toggle("sect-mode", on);
    $("sect-hub").hidden = !on;
    if (on) {
      if (!moved.length) for (const [node, target] of [[$("save-status"), $("sh-settings-slot")], [document.querySelector(".masthead .toolbar"), $("sh-settings-slot")], [$("growth-panel"), $("world-workbench")]]) {
        if (!node) continue;
        moved.push([node, node.parentNode, node.nextSibling]);
        target.append(node);
      }
      ensureScene();
    } else {
      for (const [node, parent, next] of moved.splice(0)) parent.insertBefore(node, next);
      setPanel(false);
      toggleSettings(false);
      if (controller) { controller.dispose(); controller = null; }
      $("sect-markers").replaceChildren(); markerNodes = new Map();
    }
    syncPause();
  }

  // ------------------------------------------------------------------ 三维场景与降级
  function showFallback(reason) {
    sceneFailed = true;
    body.classList.add("sect-fallback-on");
    $("sect-fallback").hidden = false;
    $("sect-fallback-note").textContent = reason;
    const grid = $("sect-fallback-grid");
    if (!grid.childElementCount) for (const entry of ENTRIES) {
      const button = element("button", "sect-fallback-entry");
      button.type = "button";
      const [name, func] = entry.label.split(" · ");
      button.append(element("strong", "", name), element("span", "", func));
      button.addEventListener("click", () => { restoreFocus = button; open(entry.page, entry.action ? { action: entry.action } : {}); });
      grid.append(button);
    }
    $("sect-markers").replaceChildren(); markerNodes = new Map();
    $("sh-home").disabled = true;
    $("sh-home-view").disabled = true;
  }
  function webgl() {
    try { const canvas = document.createElement("canvas"); const gl = canvas.getContext("webgl2") || canvas.getContext("webgl"); gl?.getExtension("WEBGL_lose_context")?.loseContext(); return !!gl; } catch { return false; }
  }
  function ensureScene() {
    if (controller || loading || sceneFailed) return;
    if (params.has("no3d")) return showFallback("已按调试参数关闭三维宗门，以下入口打开同一套功能。");
    if (!webgl()) return showFallback("当前浏览器或设备未开启 WebGL，无法显示三维宗门；以下入口打开同一套功能。");
    loading = import("/sect3d.js").then((mod) => {
      loading = null;
      if (!active) return;
      try {
        controller = mod.createSect($("sect-stage"), {
          quality: reducedMotion() ? 1 : 2,
          reducedMotion: reducedMotion(),
          onSelect: (entry) => { const def = ENTRIES.find((item) => item.id === entry.id); open(entry.page, def?.action ? { action: def.action } : {}, true); },
          onHover: (entry) => hoverTip(entry),
          onFrame: placeMarkers,
          onLost: () => { controller?.dispose(); controller = null; showFallback("三维宗门渲染中断（显卡上下文丢失），已切换为图录入口。"); },
        });
        window.__sect3d = controller;          // 浏览器验收读取帧率/绘制调用/三角形与释放结果
        syncPause();
        updateShift();
      } catch (error) {
        console.warn("三维宗门初始化失败，改用图录入口", error);
        controller = null;
        showFallback("三维宗门初始化失败，已切换为图录入口；功能不受影响。");
      }
    }).catch((error) => { loading = null; console.warn("三维宗门脚本加载失败", error); showFallback("三维宗门脚本未能加载，已切换为图录入口；功能不受影响。"); });
  }

  // ------------------------------------------------------------------ 入口标记：投影、遮挡、边缘与重叠
  function hoverTip(entry) {
    const tip = $("sect-tip");
    for (const [id, node] of markerNodes) node.classList.toggle("hot", id === entry?.id);
    if (!entry) { tip.hidden = true; return; }
    const [name, func] = entry.label.split(" · ");
    tip.textContent = `${name} — 点击打开「${func}」`;
    tip.hidden = false;
  }
  function placeMarkers() {
    const now = performance.now();
    if (!controller || now - lastMarkerAt < 50) return;          // 20Hz 足够跟随镜头
    lastMarkerAt = now;
    const host = $("sect-markers");
    const width = host.clientWidth, height = host.clientHeight;
    const list = controller.markers().sort((a, b) => b.priority - a.priority || a.distance - b.distance);
    const placed = [];
    // HUD 占位：标记不压在 HUD 面板下
    const blocked = [...document.querySelectorAll(".sh-player, .sh-top, .sh-corner, .sh-tracker, .sh-plays, .sh-cultivate, .sh-dock, .sh-view")].map((node) => node.getBoundingClientRect());
    if (panelOpen()) blocked.push($("world-workbench").getBoundingClientRect());     // 也不压在小窗下
    for (const marker of list) {
      let node = markerNodes.get(marker.id);
      if (!node) {
        node = element("button", "sect-marker");
        node.type = "button";
        const [name, func] = marker.label.split(" · ");
        node.append(element("span", "sect-marker-name", name), element("span", "sect-marker-func", func));
        node.setAttribute("aria-label", `${marker.label}，打开对应功能`);
        node.addEventListener("click", () => { restoreFocus = node; if (!controller?.focus(marker.id)) open(marker.page); });
        node.addEventListener("pointerenter", () => hoverTip(marker));
        node.addEventListener("pointerleave", () => hoverTip(null));
        host.append(node);
        markerNodes.set(marker.id, node);
      }
      const w = node.offsetWidth || 90, h = node.offsetHeight || 34;
      const x = Math.max(16 + w / 2, Math.min(width - 16 - w / 2, marker.x));
      const y = Math.max(16 + h, Math.min(height - 16, marker.y));
      const rect = { left: x - w / 2, right: x + w / 2, top: y - h, bottom: y };
      const hit = (r) => rect.left < r.right + 4 && rect.right > r.left - 4 && rect.top < r.bottom + 4 && rect.bottom > r.top - 4;
      const visible = marker.onScreen && !placed.some(hit) && !blocked.some(hit) && marker.distance < 1500;
      node.hidden = !visible;
      node.classList.toggle("occluded", marker.occluded);
      node.tabIndex = visible && !marker.occluded ? 0 : -1;
      if (visible) { placed.push(rect); node.style.transform = `translate(${Math.round(x - w / 2)}px, ${Math.round(y - h)}px)`; }
    }
  }

  // ------------------------------------------------------------------ HUD 真实数据
  function setBar(id, value, max, text) {
    const percent = max > 0 ? Math.max(0, Math.min(100, value / max * 100)) : 0;
    const bar = $(`sh-${id}-bar`);
    bar.firstElementChild.style.width = `${percent}%`;
    bar.setAttribute("aria-valuenow", String(Math.round(percent)));
    bar.setAttribute("aria-valuetext", text);
    $(`sh-${id}-text`).textContent = text;
  }
  function render() {
    const view = snapshot.view, world = view.world;
    const resources = Object.fromEntries((world.resources || view.resources || []).map((entry) => [entry.id, entry]));
    $("sh-name").textContent = view.character?.name || "";
    const progress = world.loot?.progress;
    const stage = typeof world.stage === "object" ? world.stage?.label : world.stage;
    $("sh-realm").textContent = progress ? `${progress.stage_label}${progress.milestone_label || ""}` : stage || "";
    const attack = page("character")?.stats?.find((entry) => entry.label === "攻击")?.value;
    $("sh-attack").textContent = attack === undefined ? "攻击 —" : `攻击 ${attack}`;
    const avatar = $("hud-avatar");
    if (avatar && $("sh-avatar").innerHTML !== avatar.innerHTML) $("sh-avatar").innerHTML = avatar.innerHTML;
    for (const [key, id] of [["mp", "world_mp"], ["hp", "world_hp"]]) {
      const entry = resources[id];
      if (entry) setBar(key, entry.value, entry.max, `${number(entry.value)}/${number(entry.max)}`);
    }
    $("sh-stone").textContent = resources.world_stone ? number(resources.world_stone.value) : "—";
    const contribution = row("sects", "宗门身份", "可用贡献");
    $("sh-contrib").textContent = contribution ?? "—";
    const herb = snapshot.state?.world?.inventory?.herb;
    $("sh-herb").textContent = Number.isFinite(herb) ? number(herb) : "—";
    // 修行指引：服务端的 guide 与 goals，「前往」走同一开卷路径
    $("sh-guide").textContent = world.guide?.text || world.summary || "";
    const goals = $("sh-goals");
    goals.replaceChildren();
    for (const goal of (world.goals || []).slice(0, 2)) {
      const item = element("li", "sh-goal");
      const copy = element("span", "sh-goal-title", goal.title);
      copy.title = goal.reason || goal.title;
      const go = element("button", "sh-go", "前往");
      go.type = "button";
      go.addEventListener("click", () => { restoreFocus = go; open(goal.target_page || goal.page, goal.action ? { action: { id: goal.action.id, params: goal.action.params || {} } } : {}); });
      item.append(copy, go);
      goals.append(item);
    }
    if (world.guide?.page && !(world.goals || []).length) {
      const item = element("li", "sh-goal");
      const go = element("button", "sh-go", "前往");
      go.type = "button";
      go.addEventListener("click", () => open(world.guide.page, world.guide.action_id ? { action: { id: world.guide.action_id, params: world.guide.params || {} } } : {}));
      item.append(element("span", "sh-goal-title", world.guide.label || page(world.guide.page)?.label || ""), go);
      goals.append(item);
    }
    renderCultivation();
    // 每个入口按钮只在服务端返回该卷目时可用
    document.querySelectorAll("#sect-hub [data-open]").forEach((button) => { button.disabled = !page(button.dataset.open); });
    if (world.battle && !hadBattle) open(world.battle.page);
    hadBattle = !!world.battle;
  }
  function renderCultivation() {
    if (!snapshot) return;
    const view = snapshot.view, world = view.world;
    const progress = world.loot?.progress;
    const longline = view.growth?.active === true;
    const advance = page("character")?.actions?.find((action) => action.id === "world_advance");
    $("sh-cultivate-title").textContent = longline ? (growth?.held ? "持续修炼 · 待校正" : "持续修炼中") : "自由历练";
    let value, target;
    if (longline && growth) { value = growth.available; target = growth.target; }
    else {
      value = Number((world.resources || []).find((entry) => entry.id === "world_xp")?.value || 0);
      target = Number(progress?.required || 0);
    }
    const perHour = Number(growth?.perHour ?? view.growth?.rate?.per_hour ?? 0);
    $("sh-rate").textContent = longline ? `修为 +${(perHour / 60).toFixed(2)} / 分 · 无需领取` : "按行动成长 · 无离线增长";
    if (target > 0) {
      const percent = Math.max(0, Math.min(100, value / target * 100));
      setBar("xp", value, target, `${percent.toFixed(0)}%`);
      setBreak(percent, `距离${progress?.next_label || "突破"} ${percent.toFixed(1)}% · ${growth?.text ?? number(value)} / ${number(target)}`);
    } else {
      setBar("xp", 1, 1, growth?.text ?? number(value));
      setBreak(100, progress?.conditions || "当前境界已达凡界上限条件，详见人物卷。");
    }
    const button = $("sh-break");
    button.disabled = !advance?.enabled;
    button.title = advance ? (advance.enabled ? `${advance.label}：${advance.cost}` : advance.reason || "") : "当前无可突破的境界";
    button.dataset.ready = String(!!advance?.enabled);
    // 潜修详情只在长线持续修炼时存在；待校正时提示玩家打开详情处理
    $("sh-growth-open").hidden = !longline;
    $("sh-growth-open").dataset.attention = String(!!growth?.held);
  }
  function setBreak(percent, text) {
    const bar = $("sh-break-bar");
    bar.firstElementChild.style.width = `${percent}%`;
    bar.setAttribute("aria-valuenow", String(Math.round(percent)));
    $("sh-break-text").textContent = text;
  }

  // ------------------------------------------------------------------ 设置菜单（账号、同步、视角）
  function toggleSettings(openMenu) {
    $("sh-settings-menu").hidden = !openMenu;
    $("sh-settings-button").setAttribute("aria-expanded", String(openMenu));
  }
  const syncObserver = new MutationObserver(() => {
    const status = $("save-status");
    $("sh-sync-dot").dataset.state = status.dataset.state || "idle";
    $("sh-settings-button").title = `设置与账号 · ${status.textContent}`;
  });

  // ------------------------------------------------------------------ 事件
  document.addEventListener("guixu:render", (event) => {
    snapshot = event.detail;
    const on = snapshot?.view?.phase !== "creation" && snapshot?.view?.world?.active === true;
    if (on !== active) setMode(on);
    if (on) { render(); renderWindow(); }
  });
  document.addEventListener("guixu:growth", (event) => { growth = event.detail; if (active) renderCultivation(); });
  document.addEventListener("DOMContentLoaded", () => {
    syncObserver.observe($("save-status"), { attributes: true, childList: true, characterData: true, subtree: true });
    new MutationObserver(syncPause).observe(body, { attributes: true, attributeFilter: ["class"] });
    document.querySelectorAll("#sect-hub [data-open]").forEach((button) => button.addEventListener("click", () => openFrom(button)));
    $("sect-panel-close").addEventListener("click", () => setPanel(false));
    document.querySelectorAll("#sect-hub [data-dossier]").forEach((button) => button.addEventListener("click", () => { toggleSettings(false); openDossier(button.dataset.dossier, button); }));
    $("sh-growth-open").addEventListener("click", () => openGrowth($("sh-growth-open")));
    $("sh-legacy").addEventListener("click", () => { toggleSettings(false); openLegacy($("sh-settings-button")); });
    $("legacy-history-close").addEventListener("click", () => { if (panelOpen() && view === "legacy") setPanel(false); });
    // 潜修小窗里详情保持展开（app.js 点到详情外会收起它）
    $("growth-details").addEventListener("toggle", () => { if (panelOpen() && view === "growth" && !$("growth-details").open) $("growth-details").open = true; });
    addEventListener("resize", updateShift);
    $("sh-home").addEventListener("click", () => controller?.home());
    $("sh-home-view").addEventListener("click", () => { controller?.home(); toggleSettings(false); });
    $("sh-break").addEventListener("click", () => { restoreFocus = $("sh-break"); open("character", { action: "world_advance", submit: true }); });
    $("sh-settings-button").addEventListener("click", (event) => { event.stopPropagation(); toggleSettings($("sh-settings-menu").hidden); });
    document.addEventListener("click", (event) => { if (!$("sh-settings-menu").hidden && !event.target.closest(".sh-settings")) toggleSettings(false); });
  });
  document.addEventListener("keydown", (event) => {
    if (!active || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target.closest?.("input, select, textarea, [contenteditable]") || document.querySelector("dialog[open]") || !$("reader").hidden || replayOpen()) return;
    if (event.key === "Escape") {
      if (!$("sh-settings-menu").hidden) { toggleSettings(false); $("sh-settings-button").focus(); return; }
      if (!panelOpen()) return;
      // 卷宗/潜修/旧事小窗一次 Esc 即合上（不让 app.js 再去收起详情）；卷目小窗里展开的事项卡先由 app.js 收起，再按一次 Esc 才合上
      if (view !== "page") { event.preventDefault(); event.stopPropagation(); setPanel(false); return; }
      if (!document.querySelector(".world-action[open]")) { event.preventDefault(); setPanel(false); }
      return;
    }
    if (event.key === "Home") { event.preventDefault(); controller?.home(); return; }
    const slot = document.querySelector(`.sh-slot[data-key="${event.key.toLowerCase()}"]`);
    if (slot && !slot.disabled) { event.preventDefault(); openFrom(slot); }
  }, true);   // 捕获阶段：在 app.js 收起事项卡之前判断，避免一次 Esc 同时收卡又关面板
})();
