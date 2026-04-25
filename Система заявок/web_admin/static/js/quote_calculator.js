(() => {
  "use strict";

  /**
   * Безпечно перетворює значення у число.
   * @param {unknown} v
   * @param {number} fallback
   * @returns {number}
   */
  function toNumber(v, fallback = 0) {
    const n = typeof v === "number" ? v : Number(String(v ?? "").replace(",", "."));
    return Number.isFinite(n) ? n : fallback;
  }

  /**
   * Форматує гривні (ціле або дробове значення).
   * @param {number} n
   * @returns {string}
   */
  function formatUAH(n) {
    const rounded = Number.isFinite(n) ? n : 0;
    const isInt = Number.isInteger(rounded);
    const value = isInt ? rounded : Math.round(rounded * 100) / 100;
    return `${value.toLocaleString("uk-UA")} грн`;
  }

  /**
   * Форматує євро (2 знаки після коми за потреби).
   * @param {number} n
   * @returns {string}
   */
  function formatEUR(n) {
    const v = Number.isFinite(n) ? n : 0;
    const value = Math.round(v * 100) / 100;
    return value.toLocaleString("uk-UA", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  /**
   * @param {number} n
   * @returns {string}
   */
  function formatNumber(n) {
    const v = Number.isFinite(n) ? n : 0;
    const isInt = Number.isInteger(v);
    return isInt ? v.toLocaleString("uk-UA") : (Math.round(v * 100) / 100).toLocaleString("uk-UA");
  }

  /**
   * @returns {string}
   */
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta?.getAttribute("content") || "";
  }

  /** @type {Record<string, number>} */
  let prices = window.__QUOTE_CALC_INITIAL_PRICES__ || {};

  async function loadPricesFromServer() {
    try {
      const res = await fetch("/api/quote-calculator/prices", { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      if (data && typeof data === "object" && data.prices && typeof data.prices === "object") {
        prices = data.prices;
      }
    } catch {
      // тихо
    }
  }

  function fillPriceInputs() {
    document.querySelectorAll(".qc-price").forEach((el) => {
      const key = el.getAttribute("data-price-key");
      if (!key) return;
      el.value = String(toNumber(prices[key], toNumber(el.value, 0)));
    });
  }

  function syncRangeAndNumber(rangeEl, numberEl) {
    const min = toNumber(rangeEl.min, 0);
    const max = toNumber(rangeEl.max, 0);
    const step = toNumber(rangeEl.step || 1, 1);
    const raw = toNumber(numberEl.value, 0);
    const clipped = Math.min(max, Math.max(min, raw));
    const aligned = step > 0 ? Math.round(clipped / step) * step : clipped;
    rangeEl.value = String(aligned);
    numberEl.value = String(aligned);
  }

  function bindUsersCount() {
    const rangeEl = document.getElementById("qc-users-range");
    const numberEl = document.getElementById("qc-users-number");
    if (!rangeEl || !numberEl) return;

    rangeEl.addEventListener("input", () => {
      numberEl.value = rangeEl.value;
      recalcAll();
    });
    numberEl.addEventListener("input", () => {
      syncRangeAndNumber(rangeEl, numberEl);
      recalcAll();
    });
  }

  function getUsersCount() {
    const numberEl = document.getElementById("qc-users-number");
    return Math.max(0, toNumber(numberEl?.value, 0));
  }

  function setupItemRow(row) {
    const enabledEl = row.querySelector(".qc-enabled");
    const rangeEl = row.querySelector(".qc-qty-range");
    const numberEl = row.querySelector(".qc-qty-number");

    const setEnabled = (isEnabled) => {
      if (rangeEl) rangeEl.disabled = !isEnabled;
      if (numberEl) numberEl.disabled = !isEnabled;
      if (!isEnabled) {
        if (rangeEl) rangeEl.value = "0";
        if (numberEl) numberEl.value = "0";
      }
    };

    if (enabledEl) {
      enabledEl.addEventListener("change", () => {
        setEnabled(enabledEl.checked);
        recalcAll();
      });
      setEnabled(enabledEl.checked);
    }

    if (rangeEl && numberEl) {
      rangeEl.addEventListener("input", () => {
        numberEl.value = rangeEl.value;
        recalcAll();
      });
      numberEl.addEventListener("input", () => {
        syncRangeAndNumber(rangeEl, numberEl);
        recalcAll();
      });
    }
  }

  function getRowQuantity(row) {
    const enabledEl = row.querySelector(".qc-enabled");
    const priceKey = row.getAttribute("data-price-key") || "";

    // Аудит ІБ: чекбокс -> 1/0
    if (priceKey === "sec_audit_min") {
      return enabledEl && enabledEl.checked ? 1 : 0;
    }

    const numberEl = row.querySelector(".qc-qty-number");
    const rangeEl = row.querySelector(".qc-qty-range");
    const raw = numberEl ? toNumber(numberEl.value, 0) : rangeEl ? toNumber(rangeEl.value, 0) : 0;
    return Math.max(0, raw);
  }

  /**
   * Повертає назву позиції з рядка таблиці.
   * @param {HTMLElement} row
   * @returns {string}
   */
  function getRowLabel(row) {
    const hasCheckbox = Boolean(row.querySelector(".qc-enabled"));
    const labelCell = row.querySelector(hasCheckbox ? "td:nth-child(2)" : "td:nth-child(1)");
    return labelCell ? labelCell.textContent.trim() : "";
  }

  /**
   * Повертає одиницю виміру для позиції.
   * @param {HTMLElement} row
   * @returns {string}
   */
  function getRowUnitLabel(row) {
    return row.getAttribute("data-unit-label") || "шт";
  }

  /**
   * Кількість для детального розпису (включно з увімкненими, але 0 к-стю).
   * @param {HTMLElement} row
   * @returns {number}
   */
  function getRowQuantityForDetails(row) {
    const priceKey = row.getAttribute("data-price-key") || "";
    if (priceKey === "sec_audit_min") {
      const enabledEl = row.querySelector(".qc-enabled");
      return enabledEl && enabledEl.checked ? 1 : 0;
    }

    const enabledEl = row.querySelector(".qc-enabled");
    if (enabledEl && !enabledEl.checked) return 0;

    const numberEl = row.querySelector(".qc-qty-number");
    const rangeEl = row.querySelector(".qc-qty-range");
    const raw = numberEl ? toNumber(numberEl.value, 0) : rangeEl ? toNumber(rangeEl.value, 0) : 0;
    return Math.max(0, raw);
  }

  /**
   * Формує детальні рядки для «чеку»/копіювання.
   * @returns {{monthlyLines: string[], onceLines: string[], migrationLines: string[]}}
   */
  function buildDetailedBreakdownLines() {
    const monthlyLines = [];
    const onceLines = [];
    const migrationLines = [];
    const usersCount = getUsersCount();
    const userPrice = toNumber(prices.user_monthly, 0);
    if (usersCount > 0) {
      const subtotal = usersCount * userPrice;
      monthlyLines.push(`- Користувачі: ${formatNumber(usersCount)} корист × ${formatNumber(userPrice)} = ${formatNumber(subtotal)} грн/міс`);
    }

    document.querySelectorAll(".qc-item").forEach((row) => {
      const kind = row.getAttribute("data-kind") || "once";
      const key = row.getAttribute("data-price-key") || "";
      const unit = toNumber(prices[key], 0);
      const qty = getRowQuantityForDetails(row);

      const label = getRowLabel(row) || key;
      const unitLabel = getRowUnitLabel(row);
      const subtotal = unit * qty;
      const text = `- ${label}: ${formatNumber(qty)} ${unitLabel} × ${formatNumber(unit)} = ${formatNumber(subtotal)} грн`;

      if (kind === "monthly") {
        if (qty > 0) monthlyLines.push(text);
      } else {
        // Разові: детально показуємо все увімкнене (навіть якщо к-сть 0)
        const enabledEl = row.querySelector(".qc-enabled");
        if (enabledEl) {
          if (enabledEl.checked) onceLines.push(text);
        } else if (qty > 0) {
          onceLines.push(text);
        }
      }
    });

    // Міграція
    const migEnabled = document.getElementById("qc-migration-enabled")?.checked;
    if (migEnabled) {
      const type = document.getElementById("qc-migration-type")?.value || "base";
      const amount = toNumber(document.getElementById("qc-migration-amount")?.value, 0);
      const title =
        type === "base"
          ? "Міграція в хмару (Базова)"
          : type === "b2b"
            ? "Міграція в хмару (Стандартна B2B)"
            : "Міграція в хмару (Enterprise)";
      migrationLines.push(`- ${title}: 1 послуга × ${formatNumber(amount)} = ${formatNumber(amount)} грн`);
    }

    const vpsAll = recalcVpsAll(true);
    if (vpsAll.lines.length) {
      monthlyLines.push("");
      monthlyLines.push("VPS (детально):");
      monthlyLines.push(...vpsAll.lines);
    }

    const vdsAll = recalcVdsAll(true);
    if (vdsAll.lines.length) {
      monthlyLines.push("");
      monthlyLines.push("VDS (детально):");
      monthlyLines.push(...vdsAll.lines);
    }

    return { monthlyLines, onceLines, migrationLines };
  }

  /**
   * Повертає відформатований заголовок позиції.
   * @param {string} prefix
   * @param {number} index1
   * @param {string} desc
   * @returns {string}
   */
  function formatItemTitle(prefix, index1, desc) {
    const safeDesc = String(desc || "").trim();
    return safeDesc ? `${prefix} #${index1} (${safeDesc})` : `${prefix} #${index1}`;
  }

  /**
   * Розрахунок однієї VPS позиції.
   * @param {{desc: string, cores: number, ramGb: number, nvmeGb: number, sataGb: number, hddGb: number, ipv4: number, extraBackups: number}} item
   * @returns {{eur: number, uah: number, lines: string[]}}
   */
  function calcVpsItem(item) {
    const eurRate = Math.max(0, toNumber(prices.vps_eur_uah_rate, 0));
    const vcpuEur = Math.max(0, toNumber(prices.vps_vcpu_eur, 0));
    const ramEur = Math.max(0, toNumber(prices.vps_ram_gb_eur, 0));
    const nvme10Eur = Math.max(0, toNumber(prices.vps_nvme_10gb_eur, 0));
    const sata10Eur = Math.max(0, toNumber(prices.vps_sata_10gb_eur, 0));
    const hdd10Eur = Math.max(0, toNumber(prices.vps_hdd_10gb_eur, 0));
    const ipv4Eur = Math.max(0, toNumber(prices.vps_ipv4_eur, 0));
    const extraBackupEur = Math.max(0, toNumber(prices.vps_extra_backup_copy_eur, 0));

    const cores = Math.max(0, toNumber(item.cores, 0));
    const ramGb = Math.max(0, toNumber(item.ramGb, 0));
    const nvmeGb = Math.max(0, toNumber(item.nvmeGb, 0));
    const sataGb = Math.max(0, toNumber(item.sataGb, 0));
    const hddGb = Math.max(0, toNumber(item.hddGb, 0));
    const ipv4 = Math.max(0, toNumber(item.ipv4, 0));
    const extraBackups = Math.max(0, toNumber(item.extraBackups, 0));

    const nvmeUnits = nvmeGb > 0 ? Math.ceil(nvmeGb / 10) : 0;
    const sataUnits = sataGb > 0 ? Math.ceil(sataGb / 10) : 0;
    const hddUnits = hddGb > 0 ? Math.ceil(hddGb / 10) : 0;

    const eur =
      cores * vcpuEur +
      ramGb * ramEur +
      nvmeUnits * nvme10Eur +
      sataUnits * sata10Eur +
      hddUnits * hdd10Eur +
      ipv4 * ipv4Eur +
      extraBackups * extraBackupEur;
    const uah = eurRate > 0 ? eur * eurRate : 0;

    const lines = [];
    if (cores > 0) lines.push(`  - vCPU: ${formatNumber(cores)} яд × ${formatEUR(vcpuEur)} € = ${formatEUR(cores * vcpuEur)} €/міс`);
    if (ramGb > 0) lines.push(`  - RAM: ${formatNumber(ramGb)} ГБ × ${formatEUR(ramEur)} € = ${formatEUR(ramGb * ramEur)} €/міс`);
    if (nvmeUnits > 0) lines.push(`  - NVMe: ${formatNumber(nvmeGb)} ГБ → ${formatNumber(nvmeUnits)}×10ГБ × ${formatEUR(nvme10Eur)} € = ${formatEUR(nvmeUnits * nvme10Eur)} €/міс`);
    if (sataUnits > 0) lines.push(`  - SATA: ${formatNumber(sataGb)} ГБ → ${formatNumber(sataUnits)}×10ГБ × ${formatEUR(sata10Eur)} € = ${formatEUR(sataUnits * sata10Eur)} €/міс`);
    if (hddUnits > 0) lines.push(`  - HDD: ${formatNumber(hddGb)} ГБ → ${formatNumber(hddUnits)}×10ГБ × ${formatEUR(hdd10Eur)} € = ${formatEUR(hddUnits * hdd10Eur)} €/міс`);
    if (ipv4 > 0) lines.push(`  - IPv4: ${formatNumber(ipv4)} шт × ${formatEUR(ipv4Eur)} € = ${formatEUR(ipv4 * ipv4Eur)} €/міс`);
    if (extraBackups > 0) lines.push(`  - Extra Backup: ${formatNumber(extraBackups)} коп × ${formatEUR(extraBackupEur)} € = ${formatEUR(extraBackups * extraBackupEur)} €/міс`);
    if (eurRate > 0 && eur > 0) lines.push(`  - Курс: 1 € = ${formatNumber(eurRate)} грн`);

    return { eur, uah, lines };
  }

  /**
   * Розрахунок однієї VDS позиції.
   * @param {{desc: string, eur: number}} item
   * @returns {{eur: number, uah: number, lines: string[]}}
   */
  function calcVdsItem(item) {
    const eurRate = Math.max(0, toNumber(prices.vps_eur_uah_rate, 0));
    const eur = Math.max(0, toNumber(item.eur, 0));
    const uah = eurRate > 0 ? eur * eurRate : 0;
    const lines = [];
    if (eur > 0) {
      lines.push(`  - Оренда: 1 міс × ${formatEUR(eur)} € = ${formatEUR(eur)} €/міс`);
      if (eurRate > 0) lines.push(`  - Курс: 1 € = ${formatNumber(eurRate)} грн`);
    }
    return { eur, uah, lines };
  }

  function collectVpsItemData(cardEl) {
    return {
      desc: String(cardEl.querySelector(".qc-vps-desc")?.value ?? "").trim(),
      comment: String(cardEl.querySelector(".qc-vps-comment")?.value ?? "").trim(),
      cores: toNumber(cardEl.querySelector(".qc-vps-cores")?.value, 0),
      ramGb: toNumber(cardEl.querySelector(".qc-vps-ram-gb")?.value, 0),
      nvmeGb: toNumber(cardEl.querySelector(".qc-vps-nvme-gb")?.value, 0),
      sataGb: toNumber(cardEl.querySelector(".qc-vps-sata-gb")?.value, 0),
      hddGb: toNumber(cardEl.querySelector(".qc-vps-hdd-gb")?.value, 0),
      ipv4: toNumber(cardEl.querySelector(".qc-vps-ipv4")?.value, 0),
      extraBackups: toNumber(cardEl.querySelector(".qc-vps-extra-backup-copies")?.value, 0),
    };
  }

  function collectVdsItemData(cardEl) {
    return {
      desc: String(cardEl.querySelector(".qc-vds-desc")?.value ?? "").trim(),
      comment: String(cardEl.querySelector(".qc-vds-comment")?.value ?? "").trim(),
      eur: toNumber(cardEl.querySelector(".qc-vds-eur")?.value, 0),
    };
  }

  function recalcVpsAll(forDetails = false) {
    let totalEur = 0;
    let totalUah = 0;
    const lines = [];
    const items = Array.from(document.querySelectorAll("#qc-vps-items .card"));
    items.forEach((cardEl, idx) => {
      const data = collectVpsItemData(cardEl);
      const title = formatItemTitle("VPS", idx + 1, data.desc);
      cardEl.querySelector(".qc-vps-item-title").textContent = title;
      const res = calcVpsItem(data);
      totalEur += res.eur;
      totalUah += res.uah;
      const eurEl = cardEl.querySelector(".qc-vps-subtotal-eur");
      const uahEl = cardEl.querySelector(".qc-vps-subtotal-uah");
      if (eurEl) eurEl.textContent = formatEUR(res.eur);
      if (uahEl) uahEl.textContent = formatNumber(res.uah);

      if (forDetails && res.eur > 0) {
        lines.push(`- ${title}: ${formatEUR(res.eur)} €/міс (≈ ${formatNumber(res.uah)} грн/міс)`);
        if (data.comment) lines.push(`  - Коментар: ${data.comment}`);
        lines.push(...res.lines);
      }
    });
    return { eur: totalEur, uah: totalUah, lines };
  }

  function recalcVdsAll(forDetails = false) {
    let totalEur = 0;
    let totalUah = 0;
    const lines = [];
    const items = Array.from(document.querySelectorAll("#qc-vds-items .card"));
    items.forEach((cardEl, idx) => {
      const data = collectVdsItemData(cardEl);
      const title = formatItemTitle("VDS", idx + 1, data.desc);
      cardEl.querySelector(".qc-vds-item-title").textContent = title;
      const res = calcVdsItem(data);
      totalEur += res.eur;
      totalUah += res.uah;
      const eurEl = cardEl.querySelector(".qc-vds-subtotal-eur");
      const uahEl = cardEl.querySelector(".qc-vds-subtotal-uah");
      if (eurEl) eurEl.textContent = formatEUR(res.eur);
      if (uahEl) uahEl.textContent = formatNumber(res.uah);

      if (forDetails && res.eur > 0) {
        lines.push(`- ${title}: ${formatEUR(res.eur)} €/міс (≈ ${formatNumber(res.uah)} грн/міс)`);
        if (data.comment) lines.push(`  - Коментар: ${data.comment}`);
        lines.push(...res.lines);
      }
    });
    return { eur: totalEur, uah: totalUah, lines };
  }

  function createVpsItem(initial = null) {
    const host = document.getElementById("qc-vps-items");
    const tpl = document.getElementById("qc-vps-item-template");
    if (!host || !tpl) {
      return null;
    }
    const fragment = tpl.content.cloneNode(true);
    const card = fragment.querySelector(".card");
    if (!card) return null;

    const setVal = (sel, v) => {
      const el = card.querySelector(sel);
      if (!el) return;
      el.value = String(v ?? 0);
    };
    const setText = (sel, v) => {
      const el = card.querySelector(sel);
      if (!el) return;
      el.value = String(v ?? "").slice(0, 160);
    };
    const setTextLong = (sel, v) => {
      const el = card.querySelector(sel);
      if (!el) return;
      el.value = String(v ?? "").slice(0, 500);
    };

    setText(".qc-vps-desc", initial?.desc ?? "");
    setTextLong(".qc-vps-comment", initial?.comment ?? "");
    setVal(".qc-vps-cores", initial?.cores ?? 0);
    setVal(".qc-vps-ram-gb", initial?.ramGb ?? 0);
    setVal(".qc-vps-nvme-gb", initial?.nvmeGb ?? 0);
    setVal(".qc-vps-sata-gb", initial?.sataGb ?? 0);
    setVal(".qc-vps-hdd-gb", initial?.hddGb ?? 0);
    setVal(".qc-vps-ipv4", initial?.ipv4 ?? 0);
    setVal(".qc-vps-extra-backup-copies", initial?.extraBackups ?? 0);

    card.querySelectorAll("input, textarea").forEach((el) => el.addEventListener("input", recalcAll));
    card.querySelector(".qc-remove-item")?.addEventListener("click", () => {
      card.remove();
      ensureAtLeastOneItem();
      recalcAll();
    });

    host.appendChild(card);
    return card;
  }

  function createVdsItem(initial = null) {
    const host = document.getElementById("qc-vds-items");
    const tpl = document.getElementById("qc-vds-item-template");
    if (!host || !tpl) {
      return null;
    }
    const fragment = tpl.content.cloneNode(true);
    const card = fragment.querySelector(".card");
    if (!card) return null;

    const descEl = card.querySelector(".qc-vds-desc");
    const commentEl = card.querySelector(".qc-vds-comment");
    const eurEl = card.querySelector(".qc-vds-eur");
    if (descEl) descEl.value = String(initial?.desc ?? "").slice(0, 160);
    if (commentEl) commentEl.value = String(initial?.comment ?? "").slice(0, 500);
    if (eurEl) eurEl.value = String(initial?.eur ?? 0);

    card.querySelectorAll("input, textarea").forEach((el) => el.addEventListener("input", recalcAll));
    card.querySelector(".qc-remove-item")?.addEventListener("click", () => {
      card.remove();
      ensureAtLeastOneItem();
      recalcAll();
    });

    host.appendChild(card);
    return card;
  }

  function ensureAtLeastOneItem() {
    const vpsHost = document.getElementById("qc-vps-items");
    const vdsHost = document.getElementById("qc-vds-items");
    if (vpsHost && vpsHost.querySelectorAll(".card").length === 0) createVpsItem();
    if (vdsHost && vdsHost.querySelectorAll(".card").length === 0) createVdsItem();
  }

  const ITEMS_STORAGE_KEY = "quote_calc_items_v1";
  let _saveItemsTimer = null;

  function clampPercent(v) {
    const n = toNumber(v, 0);
    return Math.max(0, Math.min(100, n));
  }

  function getDiscounts() {
    const oncePct = clampPercent(document.getElementById("qc-discount-once")?.value);
    const monthlyPct = clampPercent(document.getElementById("qc-discount-monthly")?.value);
    return { oncePct, monthlyPct };
  }

  function saveItemsToStorageDebounced() {
    if (_saveItemsTimer) window.clearTimeout(_saveItemsTimer);
    _saveItemsTimer = window.setTimeout(() => {
      const payload = {
        vps_items: Array.from(document.querySelectorAll("#qc-vps-items .card")).map((card) => collectVpsItemData(card)),
        vds_items: Array.from(document.querySelectorAll("#qc-vds-items .card")).map((card) => collectVdsItemData(card)),
        discounts: getDiscounts(),
      };
      try {
        window.localStorage.setItem(ITEMS_STORAGE_KEY, JSON.stringify(payload));
      } catch {
        // тихо
      }
    }, 200);
  }

  function loadItemsFromStorage() {
    try {
      const raw = window.localStorage.getItem(ITEMS_STORAGE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object") return null;
      return data;
    } catch {
      return null;
    }
  }

  function recalcRows() {
    let totalOnce = 0;
    let totalMonthly = 0;

    document.querySelectorAll(".qc-item").forEach((row) => {
      const kind = row.getAttribute("data-kind") || "once";
      const priceKey = row.getAttribute("data-price-key") || "";
      const unit = toNumber(prices[priceKey], 0);
      const qty = getRowQuantity(row);
      const subtotal = unit * qty;

      const unitPriceEl = row.querySelector(".qc-unit-price");
      if (unitPriceEl) unitPriceEl.textContent = formatUAH(unit);

      const subtotalEl = row.querySelector(".qc-subtotal");
      if (subtotalEl) subtotalEl.textContent = formatNumber(subtotal);

      if (kind === "monthly") totalMonthly += subtotal;
      else totalOnce += subtotal;
    });

    return { totalOnce, totalMonthly };
  }

  function recalcMigration() {
    const enabled = document.getElementById("qc-migration-enabled");
    const typeEl = document.getElementById("qc-migration-type");
    const rangeEl = document.getElementById("qc-migration-range");
    const amountEl = document.getElementById("qc-migration-amount");
    const hintEl = document.getElementById("qc-migration-hint");
    const subtotalEl = document.getElementById("qc-migration-subtotal");

    const isEnabled = Boolean(enabled?.checked);
    if (!typeEl || !rangeEl || !amountEl || !hintEl || !subtotalEl) return 0;

    typeEl.disabled = !isEnabled;
    rangeEl.disabled = !isEnabled;
    amountEl.disabled = !isEnabled;

    if (!isEnabled) {
      rangeEl.min = "0";
      rangeEl.max = "0";
      rangeEl.value = "0";
      amountEl.value = "0";
      hintEl.textContent = "—";
      subtotalEl.textContent = "0";
      return 0;
    }

    const type = typeEl.value;
    let min = 0;
    let max = 0;
    let def = 0;
    let step = 500;

    if (type === "base") {
      min = toNumber(prices.cloud_migration_base_min, 8000);
      max = toNumber(prices.cloud_migration_base_max, 15000);
      def = toNumber(prices.cloud_migration_base_default, 12000);
      step = 500;
      hintEl.textContent = `Діапазон: ${formatNumber(min)} – ${formatNumber(max)} грн`;
    } else if (type === "b2b") {
      min = toNumber(prices.cloud_migration_b2b_min, 15000);
      max = toNumber(prices.cloud_migration_b2b_max, 35000);
      def = toNumber(prices.cloud_migration_b2b_default, 25000);
      step = 1000;
      hintEl.textContent = `Діапазон: ${formatNumber(min)} – ${formatNumber(max)} грн`;
    } else {
      min = toNumber(prices.cloud_migration_enterprise_min, 40000);
      max = Math.max(min, min * 3);
      def = min;
      step = 1000;
      hintEl.textContent = `Мінімум: від ${formatNumber(min)} грн`;
    }

    rangeEl.min = String(min);
    rangeEl.max = String(max);
    rangeEl.step = String(step);

    const rawCurrent = toNumber(amountEl.value, def);
    const current = rawCurrent <= 0 ? def : rawCurrent;
    const clipped = Math.min(max, Math.max(min, current));
    amountEl.min = String(min);
    amountEl.value = String(clipped);
    rangeEl.value = String(clipped);

    const subtotal = clipped;
    subtotalEl.textContent = formatNumber(subtotal);
    return subtotal;
  }

  function recalcAll() {
    // Оновлюємо прайс зі сторінки (але не зберігаємо автоматично)
    document.querySelectorAll(".qc-price").forEach((el) => {
      const key = el.getAttribute("data-price-key");
      if (!key) return;
      prices[key] = toNumber(el.value, toNumber(prices[key], 0));
    });

    const { totalOnce, totalMonthly } = recalcRows();
    const migrationOnce = recalcMigration();
    const vpsAll = recalcVpsAll(false);
    const vdsAll = recalcVdsAll(false);

    const usersCount = getUsersCount();
    const usersMonthly = Math.max(0, usersCount) * Math.max(0, toNumber(prices.user_monthly, 0));

    const { oncePct, monthlyPct } = getDiscounts();
    const onceRaw = totalOnce + migrationOnce;
    const monthlyRaw = totalMonthly + usersMonthly + vpsAll.uah + vdsAll.uah;
    const onceDiscount = (onceRaw * oncePct) / 100;
    const monthlyDiscount = (monthlyRaw * monthlyPct) / 100;
    const once = Math.max(0, onceRaw - onceDiscount);
    const monthly = Math.max(0, monthlyRaw - monthlyDiscount);

    const onceEl = document.getElementById("qc-total-once");
    const monthlyEl = document.getElementById("qc-total-monthly");
    const firstMonthEl = document.getElementById("qc-total-first-month");
    const receiptDetailsEl = document.getElementById("qc-receipt-details");
    if (onceEl) onceEl.textContent = formatUAH(once);
    if (monthlyEl) monthlyEl.textContent = formatUAH(monthly);
    if (firstMonthEl) firstMonthEl.textContent = formatUAH(once + monthly);

    if (receiptDetailsEl) {
      const { monthlyLines, onceLines, migrationLines } = buildDetailedBreakdownLines();
      const parts = [];
      if (onceLines.length) {
        parts.push("Разові роботи та послуги (детально):");
        parts.push(...onceLines);
      }
      if (migrationLines.length) {
        if (parts.length) parts.push("");
        parts.push("Проєктні роботи (Міграція в хмару):");
        parts.push(...migrationLines);
      }
      if (oncePct > 0) {
        if (parts.length) parts.push("");
        parts.push(`Знижка (разові): -${formatNumber(onceDiscount)} грн (${formatNumber(oncePct)}%)`);
      }
      if (monthlyLines.length) {
        if (parts.length) parts.push("");
        parts.push("Щомісяця (детально):");
        parts.push(...monthlyLines);
      }
      if (monthlyPct > 0) {
        if (parts.length) parts.push("");
        parts.push(`Знижка (щомісяця): -${formatNumber(monthlyDiscount)} грн (${formatNumber(monthlyPct)}%)`);
      }
      receiptDetailsEl.textContent = parts.length ? parts.join("\n") : "—";
    }

    saveItemsToStorageDebounced();
  }

  function buildCopyText() {
    const lines = [];
    lines.push("Калькулятор");
    lines.push("");

    const { monthlyLines, onceLines, migrationLines } = buildDetailedBreakdownLines();

    if (onceLines.length) {
      lines.push("Разові роботи та послуги (детально):");
      lines.push(...onceLines);
      lines.push("");
    }

    if (migrationLines.length) {
      lines.push("Проєктні роботи (Міграція в хмару):");
      lines.push(...migrationLines);
      lines.push("");
    }

    if (monthlyLines.length) {
      lines.push("Щомісяця (детально):");
      lines.push(...monthlyLines);
      lines.push("");
    }

    lines.push(`Єдиноразовий платіж (Впровадження): ${document.getElementById("qc-total-once")?.textContent || "0 грн"}`);
    lines.push(`Щомісячний платіж (Абонплата): ${document.getElementById("qc-total-monthly")?.textContent || "0 грн"}`);
    lines.push(`Разом (1-й місяць): ${document.getElementById("qc-total-first-month")?.textContent || "0 грн"}`);
    return lines.join("\n");
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "true");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        return true;
      } catch {
        return false;
      }
    }
  }

  async function savePrices() {
    const payload = { prices };
    const csrf = getCsrfToken();
    const res = await fetch("/api/quote-calculator/prices", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRFToken": csrf } : {}),
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data?.error || "Не вдалося зберегти ціни.";
      window.alert(msg);
      return;
    }
    if (data?.prices) prices = data.prices;
    fillPriceInputs();
    recalcAll();
    window.alert("Ціни збережено.");
  }

  function saveReceiptAsPdfLikeUI() {
    const receipt = document.querySelector(".qc-receipt");
    if (!receipt) {
      window.alert("Не знайдено блок чеку на сторінці.");
      return;
    }

    const win = window.open("", "_blank", "noopener,noreferrer");
    if (!win) {
      window.alert("Не вдалося відкрити нове вікно для друку. Перевірте блокувальник спливаючих вікон.");
      return;
    }

    const headHtml = document.head ? document.head.innerHTML : "";
    const receiptHtml = receipt.outerHTML;

    win.document.open();
    win.document.write(`<!doctype html>
<html lang="uk" data-bs-theme="dark">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Чек (Калькулятор)</title>
    ${headHtml}
    <style>
      @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      }
      body { margin: 0; padding: 24px; }
      .qc-receipt { margin: 0 auto; }
    </style>
  </head>
  <body data-bs-theme="dark">
    ${receiptHtml}
    <script>
      window.addEventListener('load', () => {
        setTimeout(() => window.print(), 50);
      });
    <\/script>
  </body>
</html>`);
    win.document.close();
  }

  function bindMigration() {
    const enabled = document.getElementById("qc-migration-enabled");
    const typeEl = document.getElementById("qc-migration-type");
    const rangeEl = document.getElementById("qc-migration-range");
    const amountEl = document.getElementById("qc-migration-amount");

    enabled?.addEventListener("change", recalcAll);
    typeEl?.addEventListener("change", () => {
      // при зміні типу скидаємо на дефолт (через recalcMigration)
      amountEl.value = "0";
      rangeEl.value = "0";
      recalcAll();
    });
    rangeEl?.addEventListener("input", () => {
      amountEl.value = rangeEl.value;
      recalcAll();
    });
    amountEl?.addEventListener("input", () => {
      rangeEl.value = amountEl.value;
      recalcAll();
    });
  }

  function bindVps() {
    const addBtn = document.getElementById("qc-vps-add");
    addBtn?.addEventListener("click", () => {
      createVpsItem();
      recalcAll();
    });
  }

  function bindVds() {
    const addBtn = document.getElementById("qc-vds-add");
    addBtn?.addEventListener("click", () => {
      createVdsItem();
      recalcAll();
    });
  }

  async function init() {
    await loadPricesFromServer();
    fillPriceInputs();

    document.querySelectorAll(".qc-item").forEach((row) => setupItemRow(row));
    bindUsersCount();
    bindMigration();
    bindVps();
    bindVds();

    document.querySelectorAll(".qc-price").forEach((el) => {
      el.addEventListener("input", () => {
        recalcAll();
      });
    });

    document.getElementById("qc-save-prices-btn")?.addEventListener("click", savePrices);
    document.getElementById("qc-copy-btn")?.addEventListener("click", async () => {
      const text = buildCopyText();
      const ok = await copyToClipboard(text);
      if (!ok) window.alert("Не вдалося скопіювати. Спробуйте ще раз.");
    });
    document.getElementById("qc-pdf-btn")?.addEventListener("click", saveReceiptAsPdfLikeUI);
    document.getElementById("qc-discount-once")?.addEventListener("input", recalcAll);
    document.getElementById("qc-discount-monthly")?.addEventListener("input", recalcAll);

    // Відновлюємо позиції VPS/VDS з localStorage
    const stored = loadItemsFromStorage();
    const vpsHost = document.getElementById("qc-vps-items");
    const vdsHost = document.getElementById("qc-vds-items");
    if (vpsHost) vpsHost.innerHTML = "";
    if (vdsHost) vdsHost.innerHTML = "";

    const vpsItems = Array.isArray(stored?.vps_items) ? stored.vps_items.slice(0, 20) : [];
    const vdsItems = Array.isArray(stored?.vds_items) ? stored.vds_items.slice(0, 20) : [];
    const discounts = stored?.discounts && typeof stored.discounts === "object" ? stored.discounts : null;
    if (vpsItems.length) vpsItems.forEach((it) => createVpsItem(it));
    if (vdsItems.length) vdsItems.forEach((it) => createVdsItem(it));
    ensureAtLeastOneItem();
    if (discounts) {
      const onceEl = document.getElementById("qc-discount-once");
      const monthlyEl = document.getElementById("qc-discount-monthly");
      if (onceEl) onceEl.value = String(clampPercent(discounts.oncePct));
      if (monthlyEl) monthlyEl.value = String(clampPercent(discounts.monthlyPct));
    }

    recalcAll();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

