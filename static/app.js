"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const storageKey = "guixu.pending.v1";
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
  const battleActionIds = new Set(["world_attack", "world_power", "world_defend", "world_pill", "world_fire", "world_guard", "world_soul", "world_flee"]);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function notice(message, kind = "", retry = false, refresh = false) {
    $("notice").hidden = !message;
    $("notice").className = `notice ${kind}`;
    $("notice-text").textContent = message;
    $("retry-button").hidden = !retry;
    $("refresh-button").hidden = !refresh;
    updateControls();
  }

  function updateControls() {
    const locked = busy || !!pending || !snapshot || !storageAvailable;
    const exists = !!snapshot?.view?.character;
    $("save-button").textContent = isLonglineWorld() ? "保存位置" : "手动存档";
    $("load-button").textContent = isLonglineWorld() ? "返回检查点" : "载入手札";
    $("save-button").disabled = locked || !exists;
    $("load-button").disabled = locked || !snapshot?.save?.exists;
    $("load-button").title = snapshot?.save?.exists ? savePolicy() : "尚无手动存档";
    $("new-button").disabled = locked || !exists;
    $("create-button").disabled = locked;
    $("retry-button").disabled = busy || !pending;
    $("refresh-button").disabled = busy;
    $("name").disabled = locked;
    $("mode").disabled = locked;
    document.querySelectorAll(".action-button").forEach((button) => {
      button.disabled = locked || button.dataset.enabled !== "true";
    });
    document.querySelectorAll(".world-write").forEach((control) => {
      control.disabled = locked || control.dataset.enabled !== "true";
    });
    $("main").setAttribute("aria-busy", String(busy));
    $("save-status").textContent = busy ? "正在落笔…" : pending ? "操作结果尚未确认" : !snapshot ? "尚未读取进度" : snapshot.view.character ? "当前进度已自动保存" : "等待写下第一笔";
  }

  function renderResources(resources) {
    $("resources").replaceChildren();
    for (const resource of resources) {
      const wrapper = element("div", "resource");
      wrapper.dataset.id = resource.id;
      const top = element("div", "resource-top");
      top.append(element("span", "resource-label", resource.label));
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
        const fill = element("span");
        fill.style.width = `${resource.max > 0 ? Math.max(0, Math.min(100, resource.value / resource.max * 100)) : 0}%`;
        meter.append(fill);
        wrapper.append(meter);
      }
      $("resources").append(wrapper);
    }
  }

  function renderActions(actions) {
    const focusedKey = document.activeElement?.dataset?.actionKey;
    $("actions").replaceChildren();
    const groups = new Map();
    if (snapshot.view.phase !== "battle") {
      const navigation = element("div", "action-navigation");
      navigation.setAttribute("aria-label", "选择行动分类");
      for (const [key, label] of [["cultivation", "修行 · 养身问道"], ["exploration", "游历 · 寻缘历练"], ["travel", "山海 · 择地而行"], ["trade", "行囊 · 以物济行"]]) {
        const group = element("section", `action-group group-${key}`);
        group.id = `group-${key}`;
        group.hidden = key !== selectedGroup;
        group.append(element("h3", "action-group-title", label));
        groups.set(key, group);
        const choice = element("button", "group-button", label.split(" · ")[0]);
        choice.type = "button";
        choice.dataset.group = key;
        choice.setAttribute("aria-pressed", String(key === selectedGroup));
        choice.setAttribute("aria-controls", group.id);
        choice.addEventListener("click", () => {
          selectedGroup = key;
          for (const [id, section] of groups) section.hidden = id !== key;
          navigation.querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.group === key)));
        });
        navigation.append(choice);
      }
      $("actions").append(navigation);
    }
    for (const [index, action] of actions.entries()) {
      const row = element("div", "action-row");
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
      const button = element("button", `action-button${action.primary ? " primary" : ""}`, action.label);
      button.type = "button";
      button.dataset.enabled = String(action.enabled);
      button.dataset.action = action.id;
      button.dataset.params = JSON.stringify(action.params);
      button.dataset.actionKey = `${action.id}:${JSON.stringify(action.params)}`;
      button.setAttribute("aria-describedby", reason.id);
      button.addEventListener("click", () => beginWrite("/api/action", { action: action.id, params: action.params }));
      row.append(copy, button);
      const fallback = ["buy_pill", "sell_herbs"].includes(action.id) ? "trade" : action.id === "travel" ? "travel" : ["explore", "gather", "challenge"].includes(action.id) ? "exploration" : "cultivation";
      const group = groups.get(action.group) || groups.get(fallback);
      if (action.id === "world_enter") {
        row.classList.add("world-entry-action");
        if (action.enabled) button.classList.add("primary");
        $("actions").prepend(row);
      } else if (group) group.append(row);
      else $("actions").append(row);
    }
    for (const group of groups.values()) if (group.children.length > 1) $("actions").append(group);
    if (!actions.length) $("actions").append(element("p", "muted", "此刻暂无可执行的行动。"));
    updateControls();
    if (focusedKey) {
      const target = [...document.querySelectorAll(".action-button")].find((button) => button.dataset.actionKey === focusedKey && !button.disabled);
      if (target) target.focus({ preventScroll: true });
    }
  }

  function renderLogs(logs) {
    const visible = [...logs].reverse().slice(0, expanded ? logs.length : 6);
    $("logs").replaceChildren(...visible.map((text) => element("li", "", text)));
    $("empty-logs").hidden = logs.length > 0;
    $("history-button").hidden = logs.length <= 6;
    $("history-button").textContent = expanded ? "收起早先记事" : `展开更多记事（${logs.length - 6}）`;
  }

  function worldActionKey(page, action) {
    return `${page}:${action.id}:${JSON.stringify(action.params)}`;
  }

  function isLonglineWorld() {
    return snapshot?.view.profile?.mode === "longline" && snapshot?.view.world?.active === true;
  }

  function savePolicy() {
    return snapshot?.view.profile?.load_policy || (isLonglineWorld() ? "长线位置检查点：只恢复安全位置，成长、境界、资产、物品及奖励权益不回退。完整进度由自动保存与重启恢复。" : "自由行动/序章存档：载入恢复整个世界快照，版本与请求记录不回退。");
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
      line.append(element("dt", "", "旧档衔接"), element("dd", "", "已保留境界与资产；未封界阶段按新版目标保留完成比例，迁移时已封界的潜修储备保持原余额。"));
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

  function contextSection(title, intro) {
    const section = element("section", "r3-context-section");
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

  function findItemActions(uid) {
    const filter = { query: uid, limit: Infinity };
    worldActionFilters.set(selectedWorldPage, filter);
    $("world-action-search").value = uid;
    filterWorldActions();
    $("world-actions-title").scrollIntoView({ block: "start" });
    $("world-actions-title").focus({ preventScroll: true });
  }

  function revealWorldAction(pageId, actionId, params = {}) {
    const page = snapshot?.view.world?.pages.find((entry) => entry.id === pageId);
    const action = page?.actions.find((entry) => entry.id === actionId && Object.entries(params).every(([key, value]) => entry.params[key] === value));
    if (!action) {
      notice("该目标事项已变化，请重新读取当前进度后查看。", "", false, true);
      return;
    }
    worldActionFilters.set(pageId, { query: "", limit: Infinity });
    selectWorldPage(pageId);
    const form = [...document.querySelectorAll(".world-action-form")].find((entry) => entry.dataset.actionKey === worldActionKey(pageId, action));
    const details = form?.closest("details");
    if (details) details.open = true;
    form?.scrollIntoView({ block: "center" });
    form?.querySelector(".world-submit")?.focus({ preventScroll: true });
  }

  function renderR3Context(world) {
    const root = $("r3-page-context");
    root.replaceChildren();
    const loot = world.loot;
    $("r4-dungeon-jump").hidden = !(selectedWorldPage === "exploration" && loot?.dungeons?.length);
    if (!loot || loot.mode !== "longline") return;
    if (["world", "exploration"].includes(selectedWorldPage) && loot.credits) {
      const section = element("section", "r4-credit-strip");
      section.id = "r4-credits";
      section.append(element("strong", "r4-credits-balance", ""), element("p", "quiet-note", ""));
      section.querySelector("strong").id = "r4-credits-balance";
      section.querySelector("p:last-child").id = "r4-credits-status";
      root.append(section);
      anchorCredits(loot.credits);
    }
    if (selectedWorldPage === "world" && world.goals?.length) {
      const section = contextSection("今日行道 · 从真实缺口出发", "以下目标按当前装备、材料与挑战条件选择。只定位真实事项，不自动接取或提交，也不是强制打卡。 ");
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
      const section = contextSection("初涉仙途 · 七段行纪", "建议日序用于引路，不按日历锁定；前段领奖与境界条件满足后可继续，接取后计数，完成权益不过期。");
      section.id = "r4-journey";
      let currentStoryOpened = false;
      for (const layer of world.journey.layers) {
        const row = element("details", "r4-story");
        row.dataset.storyId = layer.id;
        const heading = element("summary", "", `${layer.recommended_day === 0 ? "建议首日" : `建议第${layer.recommended_day + 1}日`} · ${layer.title} · ${layer.status}`);
        row.append(heading, element("p", "quiet-note", layer.unlock), contextRows(layer.objectives || []), element("p", "quiet-note", `奖励：${layer.rewards}`));
        const projected = world.pages?.find((page) => page.id === "quests")?.actions?.find((action) => action.id === layer.action?.id && JSON.stringify(action.params) === JSON.stringify(layer.action?.params));
        if (projected && !currentStoryOpened) { row.open = true; currentStoryOpened = true; }
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
      const section = contextSection("首周精英 · 三地试炼", "独立NPC精英，不消耗副本恢复资格；具体解锁、风险与奖励以当前投影为准。");
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
      const section = contextSection("器物与法宝", "三器奠基，两宝定道。比较来自服务端；修炼向提高未来潜修，战力向帮助挑战更高难度。 ");
      const slots = element("div", "r3-slots");
      for (const [id, label] of [["weapon", "兵器"], ["armor", "护甲"], ["pendant", "灵佩"], ["main", "本命法宝"], ["guard", "护持法宝"]]) {
        const item = loot.items.find((entry) => entry.slot === id && entry.equipped);
        const line = element("div", "r3-slot");
        line.dataset.slot = id;
        line.append(element("span", "section-number", label), element("strong", "", item?.name || "当前为空槽"), element("span", "quiet-note", item ? `${item.quality} · 强化 ${item.enhance} · ${displayEffectType(item.effect_type)}` : "从副本掉落或四艺保底制作取得"));
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
          detail.replaceChildren(element("h4", "", item.name), element("p", "r3-context-intro", `${item.quality} · 章节 ${item.chapter} · 强化 ${item.enhance} · ${displayEffectType(item.effect_type)} · ${item.equipped ? "已装备" : "未装备"}`));
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
        select.addEventListener("change", show);
        section.append(label, select, detail);
        show();
      } else section.append(element("p", "muted", "暂无实例装备。完成有掉落资格的副本，或从四艺保底制作起步。"));
      root.append(section);
    }
    if (["exploration", "world"].includes(selectedWorldPage) && loot.boss) {
      const boss = loot.boss;
      const section = contextSection("世界Boss · 十二回合试锋", "本地NPC模拟 · 不要求击杀。每期最多3次正式挑战，取单场最佳，不累计多场伤害；奖励只补已得权益的差额。 ");
      section.dataset.context = "world-boss";
      section.append(contextRows([{ label: "本期", value: boss.encounter }, { label: "正式尝试", value: boss.attempts }, { label: "本次有效伤害", value: boss.current_damage }, { label: "个人单场最佳", value: boss.best }, { label: "本期参考伤害", value: boss.reference }, { label: "已领奖权益", value: boss.paid }, { label: "下一档 / 差额", value: boss.next }, { label: "结算与封顶", value: boss.status }]));
      root.append(section);
    }
    if (selectedWorldPage === "exploration" && loot.dungeons?.length) {
      const section = contextSection("副本筹备 · 难度与战利品", "同章同难手战获胜后可快捷结算；无资格手战仍有普通材料与灵石。 ");
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
      select.addEventListener("change", show);
      section.append(label, select, detail);
      show();
      root.append(section);
    }
    if (["character", "craft", "exploration"].includes(selectedWorldPage) && loot.materials?.length) {
      const section = contextSection("养成资材", "材料、法宝与装备提高后续效率或战力，不直接兑换无限修为。 ");
      section.append(contextRows(loot.materials));
      root.append(section);
    }
    if (["character", "exploration", "market"].includes(selectedWorldPage) && loot.pending?.length) {
      const section = contextSection("待领战利品", "容量不足的完整奖励保留待领；实际领取仍由下方对应事项原子完成。 ");
      section.append(contextRows(loot.pending.map((item) => ({ label: `${item.label} · ${item.id}`, value: item.source }))));
      root.prepend(section);
    }
    if (selectedWorldPage === "world" && $("r3-goals")) root.prepend($("r3-goals"));
    if (selectedWorldPage === "exploration" && $("r4-dungeon-workbench")) {
      root.prepend($("r4-dungeon-workbench"));
      if ($("r4-credits")) $("r4-dungeon-workbench").insertBefore($("r4-credits"), $("r4-dungeon-workbench").querySelector(".r3-dungeon-detail"));
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
    const quests = world.pages.find((entry) => entry.id === "quests");
    const tracked = (quests?.sections || []).flatMap((section) => section.rows || []).slice(0, 3);
    $("world-tracked-quests").replaceChildren(...tracked.map((row) => {
      const note = element("div", "tracked-quest");
      note.append(element("h4", "", row.label), element("p", "", row.value));
      return note;
    }));
    for (const resource of snapshot.view.resources || []) {
      const block = [...document.querySelectorAll(".resource")].find((node) => node.dataset.id === resource.id);
      const value = block?.querySelector(".resource-value");
      if (value?.firstChild?.nodeType === Node.TEXT_NODE) value.firstChild.textContent = resource.value;
    }
    tickGrowth();
  }

  function selectWorldPage(id) {
    if (!snapshot?.view.world?.pages.some((page) => page.id === id)) return;
    const navigationFocused = !!document.activeElement?.dataset.worldPage;
    selectedWorldPage = id;
    renderWorld(snapshot.view.world);
    if (navigationFocused) [...document.querySelectorAll("[data-world-page]")].find((button) => button.dataset.worldPage === id)?.focus({ preventScroll: true });
  }

  function renderWorldAction(action, pageId) {
    const key = worldActionKey(pageId, action);
    const fields = action.fields || [];
    const wrapper = element(fields.length ? "details" : "div", `world-action${fields.length ? " has-fields" : ""}`);
    wrapper.dataset.worldAction = action.id;
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
    const submit = element("button", `world-write world-submit${action.primary ? " primary-button" : " secondary-button"}`, action.label);
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
      button.append(element("span", "world-nav-number", String(index + 1).padStart(2, "0")), element("span", "", page.label));
      button.addEventListener("click", () => selectWorldPage(page.id));
      $("world-navigation").append(button);
    }
    const page = pages.find((entry) => entry.id === selectedWorldPage);
    if (!page) return;
    $("world-page-number").textContent = `卷 ${String(pages.indexOf(page) + 1).padStart(2, "0")} · ${page.label}`;
    $("world-page-title").textContent = page.title;
    $("world-page-description").textContent = page.description;
    renderR3Context(world);
    renderWorldStats(page.stats);
    $("world-page-sections").replaceChildren();
    const pageSections = [...(page.sections || [])].sort((left, right) => Number(String(right.id || "").startsWith("r3_")) - Number(String(left.id || "").startsWith("r3_")));
    for (const [index, section] of pageSections.entries()) {
      const featured = String(section.id || "").startsWith("r3_");
      const foldable = page.sections.length > 3 && !featured;
      const block = element(foldable ? "details" : "section", foldable ? "world-section world-section-fold" : "world-section");
      block.dataset.sectionKey = section.id || section.title;
      if (section.id) block.dataset.sectionId = section.id;
      if (featured) block.classList.add("r3-featured-section");
      if (foldable) {
        const sectionKey = `${page.id}:${section.title}`;
        block.open = worldSectionOpen.has(sectionKey) ? worldSectionOpen.get(sectionKey) : index < 2;
        const summary = element("summary");
        summary.append(element("h3", "", section.title));
        block.append(summary);
        block.addEventListener("toggle", () => worldSectionOpen.set(sectionKey, block.open));
      } else block.append(element("h3", "", section.title));
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
    if (!regularActions.length) $("world-page-actions").append(element("p", "muted", "此页暂无其他可执行事项，条件与进度请参阅上方手札。"));
    const filter = worldActionFilters.get(page.id) || { query: "", limit: 8 };
    worldActionFilters.set(page.id, filter);
    $("world-action-search").value = filter.query;
    filterWorldActions();
    $("world-battle-banner").hidden = !world.battle;
    if (world.battle) {
      $("world-battle-name").textContent = world.battle.name;
      $("world-battle-intent").textContent = `敌方下一意图：${world.battle.intent}`;
      $("world-battle-health").textContent = `敌方气血 ${world.battle.hp} / ${world.battle.max_hp}`;
      $("world-battle-counterplay").textContent = world.battle.counterplay || "";
      $("world-battle-statuses").replaceChildren(...(world.battle.statuses || []).map((status) => {
        const line = element("div");
        line.append(element("dt", "", status.label), element("dd", "", status.value));
        return line;
      }));
    }
    $("world-summary").textContent = world.summary || "观照当前进度，再择下一步修行。";
    $("world-tracked-quests").replaceChildren();
    const quests = pages.find((entry) => entry.id === "quests");
    const tracked = (quests?.sections || []).flatMap((section) => section.rows || []).slice(0, 3);
    for (const row of tracked) {
      const note = element("div", "tracked-quest");
      note.append(element("h4", "", row.label), element("p", "", row.value));
      $("world-tracked-quests").append(note);
    }
    $("world-quests-link").hidden = !quests;
    $("world-recent-logs").replaceChildren(...[...(snapshot.view.logs || [])].reverse().slice(0, 4).map((text) => element("li", "", text)));
    $("world-slot-summary").textContent = snapshot.save?.summary || "尚未留下手动存档。";
    $("world-save-semantics").textContent = savePolicy();
    $("legacy-history").hidden = !historyVisible;
    $("legacy-history-title").textContent = snapshot.view.ending?.title || "归墟序章";
    $("legacy-history-text").textContent = snapshot.view.ending?.text || "从初入山村，到平定归墟，这段经历已成为你的来路。";
    updateControls();
  }

  function filterWorldActions() {
    const filter = worldActionFilters.get(selectedWorldPage) || { query: "", limit: 8 };
    const query = filter.query.trim().toLocaleLowerCase();
    const rows = [...$("world-page-actions").querySelectorAll(".world-action")];
    const matched = rows.filter((row) => !query || row.dataset.search.includes(query));
    for (const row of rows) row.hidden = true;
    for (const row of matched.slice(0, filter.limit)) row.hidden = false;
    const shown = Math.min(filter.limit, matched.length);
    $("world-action-count").textContent = matched.length ? `已显示 ${shown} / ${matched.length} 项${query ? "匹配事项" : "事项"}；所有条件以服务端为准。` : "未找到匹配事项，请换一个关键词。";
    $("world-actions-show-more").hidden = shown >= matched.length;
    $("world-actions-show-all").hidden = shown >= matched.length;
    $("world-actions-show-all").textContent = `展开全部（${matched.length}）`;
  }

  function render(data) {
    if (!data || data.ok !== true || !Number.isInteger(data.revision) || !data.view) throw new Error("服务返回的手札格式不完整。");
    if (snapshot && data.revision < snapshot.revision) return;
    const previousBattle = snapshot?.view.world?.battle;
    snapshot = data;
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
      if (view.world.battle && !previousBattle) selectedWorldPage = view.world.battle.page;
      renderWorld(view.world);
    }
    if (view.character) {
      $("character-name").textContent = view.character.name;
      const worldStage = typeof view.world?.stage === "object" ? view.world.stage?.label : view.world?.stage;
      $("realm").textContent = worldActive ? worldStage || "凡界修行" : view.character.realm;
      $("objective").textContent = view.objective;
      $("location-name").textContent = view.location?.name || "修行途中";
      $("location-description").textContent = view.location?.description || "";
      $("scene-kicker").textContent = view.phase === "battle" ? "此刻 · 狭路相逢" : "此刻 · 身之所在";
      $("actions-title").textContent = view.phase === "battle" ? "一招一式，皆有抉择" : "接下来，如何行道";
      renderResources(view.resources);
      $("profile-label").textContent = view.profile?.mode === "longline" ? "· 长线修行" : "· 自由历练";
      renderActions(view.actions);
      renderLogs(view.logs);
      $("battle").hidden = !view.battle;
      if (view.battle) {
        const battle = view.battle;
        $("enemy-name").textContent = battle.name;
        $("enemy-health").textContent = `${battle.hp} / ${battle.max_hp} 气血`;
        $("enemy-intent").textContent = battle.intent;
        const meter = $("enemy-meter");
        meter.setAttribute("aria-valuemin", "0");
        meter.setAttribute("aria-valuemax", String(battle.max_hp));
        meter.setAttribute("aria-valuenow", String(battle.hp));
        meter.firstElementChild.style.width = `${battle.max_hp > 0 ? Math.max(0, Math.min(100, battle.hp / battle.max_hp * 100)) : 0}%`;
      }
      $("ending").hidden = !view.ending;
      if (view.ending) {
        $("ending-title").textContent = view.ending.title;
        $("ending-text").textContent = view.ending.text;
      }
    }
    $("slot-summary").textContent = data.save?.summary || "尚未留下手动存档。";
    anchorGrowth(view.growth);
    updateControls();
  }

  async function refreshGrowth() {
    if (growthRefreshing || busy || pending || !snapshot?.view.growth?.active || document.hidden || $("confirm-dialog").open) return;
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

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal, cache: "no-store" });
      const data = await response.json();
      if (typeof data.ok !== "boolean") throw new Error("无法识别服务响应。");
      return { response, data };
    } finally {
      clearTimeout(timeout);
    }
  }

  async function readState(keepNotice = false) {
    if (busy) return;
    busy = true;
    updateControls();
    try {
      const { response, data } = await request("/api/state");
      if (!response.ok || !data.ok) throw new Error(data.error?.message || "暂时无法读取手札。");
      render(data);
      if (pending) notice("上次操作结果尚未确认。请重试原操作以安全核对，期间暂停其他行动。", "", true, false);
      else if (!keepNotice) notice("");
    } catch (error) {
      notice(`读取失败：${error.name === "AbortError" ? "服务响应超时" : error.message}。请检查服务后重新读取。`, "error", !!pending, true);
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
      notice("浏览器无法保存待确认操作。为避免刷新后重复执行，已暂停写入；请允许本站本地存储后重新打开页面。", "error", false, true);
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
    if (busy || pending || !snapshot || !storageAvailable) return;
    const candidate = { path, body: { request_id: requestId(), expected_revision: snapshot.revision, ...payload } };
    if (!persistPending(candidate)) return;
    pending = candidate;
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
    if (!pending || busy) return;
    busy = true;
    notice("");
    updateControls();
    let refreshConflict = false;
    try {
      const { response, data } = await request(pending.path, { method: "POST", headers: { "Content-Type": "application/json", "X-Game-Client": "guixu-web" }, body: JSON.stringify(pending.body) });
      if (response.ok && data.ok) {
        if (pending.path === "/api/new-game" || pending.path === "/api/load") worldDrafts.clear();
        if (pending.path === "/api/new-game") {
          selectedWorldPage = "world";
          historyVisible = false;
          worldActionFilters.clear();
          worldSectionOpen.clear();
          $("legacy-history-button").setAttribute("aria-expanded", "false");
        }
        if (submittedWorldKey) worldDrafts.delete(submittedWorldKey);
        submittedWorldKey = null;
        render(data);
        pending = null;
        if (persistPending(null)) notice(data.duplicate ? "该操作已处理，已同步最新进度。" : data.events?.length ? data.events.join(" · ") : "手札已保存。", "success");
      } else if (data.ok === false && data.error) {
        pending = null;
        submittedWorldKey = null;
        const cleared = persistPending(null);
        if (cleared) {
          refreshConflict = response.status === 409;
          notice(refreshConflict ? `${data.error.message} 已重新读取进度，请确认后重新选择行动。` : data.error.message, "error", false, !refreshConflict);
        }
      } else throw new Error("服务响应不完整");
    } catch (error) {
      notice(`操作结果尚未确认（${error.name === "AbortError" ? "连接超时" : "连接中断或响应异常"}）。重试将使用同一操作编号，不会重复结算。`, "error", true, false);
    } finally {
      busy = false;
      updateControls();
    }
    if (refreshConflict) await readState(true);
  }

  function openConfirmation(kind) {
    if (busy || pending || !snapshot) return;
    confirmation = kind;
    previousFocus = document.activeElement;
    const isNew = kind === "new";
    $("confirm-title").textContent = isNew ? "另起一卷修行？" : "回到手动留卷之时？";
    $("confirm-description").textContent = isNew ? "当前角色与手动存档将被新的角色替代，此操作无法撤销。修行方式只影响新角色，不会自动转换旧档。" : `${savePolicy()}\n${snapshot.save.summary || ""}\n${isLonglineWorld() ? "只恢复兼容的安全位置；进行中的战斗与探索不会被旧档重置。" : "当前世界进度将由手动存档覆盖，自动保存不能撤销此次载入。"}`;
    $("new-name-field").hidden = !isNew;
    $("new-name").required = false;
    $("new-name").disabled = !isNew;
    $("new-name").value = "归墟客";
    $("new-mode").value = "longline";
    $("new-mode").disabled = !isNew;
    $("accept-confirm").textContent = isNew ? "确认 · 开启新卷" : "确认 · 载入手札";
    $("confirm-dialog").showModal();
    $("cancel-confirm").focus();
  }

  $("creation-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("name").value.trim() || "归墟客";
    beginWrite("/api/new-game", { name, mode: $("mode").value });
  });
  $("name").addEventListener("input", () => $("name").setCustomValidity(""));
  $("save-button").addEventListener("click", () => beginWrite("/api/save"));
  $("load-button").addEventListener("click", () => openConfirmation("load"));
  $("new-button").addEventListener("click", () => openConfirmation("new"));
  $("retry-button").addEventListener("click", sendPending);
  $("refresh-button").addEventListener("click", () => readState());
  $("history-button").addEventListener("click", () => { expanded = !expanded; renderLogs(snapshot.view.logs); });
  $("world-quests-link").addEventListener("click", () => selectWorldPage("quests"));
  $("world-action-search").addEventListener("input", () => {
    worldActionFilters.set(selectedWorldPage, { query: $("world-action-search").value, limit: 8 });
    filterWorldActions();
  });
  $("world-actions-show-more").addEventListener("click", () => {
    const filter = worldActionFilters.get(selectedWorldPage);
    filter.limit += 8;
    filterWorldActions();
  });
  $("world-actions-show-all").addEventListener("click", () => {
    const filter = worldActionFilters.get(selectedWorldPage);
    filter.limit = Infinity;
    filterWorldActions();
  });
  $("r4-dungeon-jump").addEventListener("click", () => {
    $("r4-dungeon-workbench")?.scrollIntoView({ block: "start" });
    $("r3-dungeon-select")?.focus({ preventScroll: true });
  });
  $("world-actions-jump").addEventListener("click", () => {
    $("world-actions-title").scrollIntoView({ block: "start" });
    $("world-actions-title").focus({ preventScroll: true });
  });
  $("world-battle-link").addEventListener("click", () => {
    const battle = snapshot?.view.world?.battle;
    if (!battle) return;
    selectWorldPage(battle.page);
    $("world-battle-actions").scrollIntoView({ block: "start" });
    $("world-battle-actions").querySelector("h3").focus({ preventScroll: true });
  });
  $("legacy-history-button").addEventListener("click", () => {
    historyVisible = !historyVisible;
    $("legacy-history").hidden = !historyVisible;
    $("legacy-history-button").setAttribute("aria-expanded", String(historyVisible));
  });
  $("cancel-confirm").addEventListener("click", () => $("confirm-dialog").close());
  $("confirm-dialog").addEventListener("close", () => { confirmation = null; previousFocus?.focus(); });
  $("confirm-dialog").querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    const kind = confirmation;
    const name = $("new-name").value.trim() || "归墟客";
    $("confirm-dialog").close();
    if (kind === "new") beginWrite("/api/new-game", { name, mode: $("new-mode").value });
    else if (kind === "load") beginWrite("/api/load");
    else if (kind?.path) {
      submittedWorldKey = kind.key;
      beginWrite(kind.path, kind.payload);
    }
  });
  $("new-name").addEventListener("input", () => $("new-name").setCustomValidity(""));
  $("mode").addEventListener("change", () => {
    $("mode-description").textContent = $("mode").value === "longline" ? "序章后开启持续潜修，以装备和法宝养成推进月余修行。" : "保留旧版行动成长与完整世界存档规则，无离线增长。";
  });
  $("growth-update-button").addEventListener("click", () => readState());
  try {
    const saved = sessionStorage.getItem(storageKey);
    if (saved) {
      const value = JSON.parse(saved);
      if (!["/api/action", "/api/save", "/api/load", "/api/new-game"].includes(value.path) || typeof value.body?.request_id !== "string" || !Number.isInteger(value.body?.expected_revision)) throw new Error("invalid pending");
      pending = value;
    }
  } catch (_) {
    storageAvailable = false;
    notice("本地待确认操作记录不可读取。为保护进度，已暂停写入；请保留本站存储并检查浏览器设置。", "error", false, true);
  }
  readState(!storageAvailable);
  setInterval(tickGrowth, 250);
  setInterval(refreshGrowth, 15000);
})();
