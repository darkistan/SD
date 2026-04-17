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

    // Індивідуальне хмаро
    const pcEnabled = document.getElementById("qc-privatecloud-enabled")?.checked;
    if (pcEnabled) {
      const cost = Math.max(0, toNumber(document.getElementById("qc-privatecloud-cost")?.value, 0));
      const margin = Math.max(0, toNumber(document.getElementById("qc-privatecloud-margin")?.value, 0));
      if (cost > 0) monthlyLines.push(`- Індивідуальне хмаро (оренда ресурсів): 1 міс × ${formatNumber(cost)} = ${formatNumber(cost)} грн/міс`);
      if (margin > 0) monthlyLines.push(`- Індивідуальне хмаро (обслуговування): 1 міс × ${formatNumber(margin)} = ${formatNumber(margin)} грн/міс`);
    }

    return { monthlyLines, onceLines, migrationLines };
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

  function recalcPrivateCloud() {
    const enabled = document.getElementById("qc-privatecloud-enabled");
    const costEl = document.getElementById("qc-privatecloud-cost");
    const marginEl = document.getElementById("qc-privatecloud-margin");
    const subtotalEl = document.getElementById("qc-privatecloud-subtotal");

    const isEnabled = Boolean(enabled?.checked);
    if (!costEl || !marginEl || !subtotalEl) return 0;

    costEl.disabled = !isEnabled;
    marginEl.disabled = !isEnabled;

    if (!isEnabled) {
      costEl.value = "0";
      marginEl.value = "0";
      subtotalEl.textContent = "0";
      return 0;
    }

    const subtotal = Math.max(0, toNumber(costEl.value, 0)) + Math.max(0, toNumber(marginEl.value, 0));
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
    const privateMonthly = recalcPrivateCloud();

    const usersCount = getUsersCount();
    const usersMonthly = Math.max(0, usersCount) * Math.max(0, toNumber(prices.user_monthly, 0));

    const once = totalOnce + migrationOnce;
    const monthly = totalMonthly + privateMonthly + usersMonthly;

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
      if (monthlyLines.length) {
        if (parts.length) parts.push("");
        parts.push("Щомісяця (детально):");
        parts.push(...monthlyLines);
      }
      receiptDetailsEl.textContent = parts.length ? parts.join("\n") : "—";
    }
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

  function bindPrivateCloud() {
    const enabled = document.getElementById("qc-privatecloud-enabled");
    const costEl = document.getElementById("qc-privatecloud-cost");
    const marginEl = document.getElementById("qc-privatecloud-margin");

    enabled?.addEventListener("change", recalcAll);
    costEl?.addEventListener("input", recalcAll);
    marginEl?.addEventListener("input", recalcAll);
  }

  async function init() {
    await loadPricesFromServer();
    fillPriceInputs();

    document.querySelectorAll(".qc-item").forEach((row) => setupItemRow(row));
    bindUsersCount();
    bindMigration();
    bindPrivateCloud();

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

    recalcAll();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

