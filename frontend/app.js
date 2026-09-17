const API_BASE = "";

const COMPLIANCE_LABELS_AR = {
  compliant: "متوافق شرعياً",
  non_compliant: "غير متوافق",
  needs_review: "يتطلب مراجعة",
};

const dailyGrid = document.getElementById("daily-grid");
const dailyMeta = document.getElementById("daily-meta");
const dailyStatus = document.getElementById("daily-status");
const detailPanel = document.getElementById("detail-panel");
const detailContent = document.getElementById("detail-content");
const cardTemplate = document.getElementById("daily-card-template");
const searchForm = document.getElementById("search-form");
const tickerInput = document.getElementById("ticker-input");
const refreshBtn = document.getElementById("refresh-daily");
const backtestForm = document.getElementById("backtest-form");
const backtestTickerInput = document.getElementById("backtest-ticker-input");
const backtestStatus = document.getElementById("backtest-status");
const backtestContent = document.getElementById("backtest-content");
const runUniverseBacktestBtn = document.getElementById("run-universe-backtest");

function formatMoney(value, currency) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPct(value) {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

function formatCompactMarketCap(value) {
  if (!value) return "—";
  const units = [
    { threshold: 1e12, suffix: "ت", divisor: 1e12 },
    { threshold: 1e9, suffix: "مليار", divisor: 1e9 },
    { threshold: 1e6, suffix: "مليون", divisor: 1e6 },
  ];
  for (const unit of units) {
    if (value >= unit.threshold) {
      return `${(value / unit.divisor).toFixed(2)} ${unit.suffix}`;
    }
  }
  return value.toFixed(0);
}

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = null;
    try {
      const body = await response.json();
      detail = body.detail;
    } catch (_) {
      // ignore parse errors
    }
    const message = detail?.error_ar || `تعذّر الاتصال بالخادم (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function renderDailyCard(pick) {
  const node = cardTemplate.content.cloneNode(true);
  const article = node.querySelector(".pick-card");
  node.querySelector(".pick-ticker").textContent = pick.ticker;
  node.querySelector(".pick-name").textContent = pick.name;
  node.querySelector(".pick-sector").textContent = pick.sector || "";
  node.querySelector(".pick-price").textContent = formatMoney(pick.price, "USD");

  const changeEl = node.querySelector(".pick-change");
  changeEl.textContent = formatPct(pick.change_pct);
  changeEl.classList.add(pick.change_pct >= 0 ? "positive" : "negative");

  const complianceBadge = node.querySelector(".compliance-badge");
  complianceBadge.textContent = COMPLIANCE_LABELS_AR[pick.compliance_status] || pick.compliance_status;
  complianceBadge.classList.add(pick.compliance_status);

  const recBadge = node.querySelector(".recommendation-badge");
  recBadge.textContent = pick.recommendation_ar;
  recBadge.classList.add(pick.recommendation);

  node.querySelector(".pick-score").textContent = `النقاط: ${pick.composite_score.toFixed(1)}`;

  article.addEventListener("click", () => loadStockDetail(pick.ticker));
  article.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      loadStockDetail(pick.ticker);
    }
  });

  return node;
}

async function loadDaily(refresh = false) {
  dailyStatus.classList.remove("error");
  dailyGrid.innerHTML = "";
  const startedAt = Date.now();
  dailyStatus.textContent = "جاري فحص الأسهم وتحليلها... قد يستغرق هذا حتى دقيقة عند أول تحميل";
  const tickInterval = setInterval(() => {
    const seconds = Math.floor((Date.now() - startedAt) / 1000);
    dailyStatus.textContent = `جاري فحص الأسهم وتحليلها... (${seconds} ثانية)`;
  }, 1000);
  try {
    const url = `${API_BASE}/api/recommendations/daily?limit=12${refresh ? "&refresh=true" : ""}`;
    const data = await fetchJSON(url);
    clearInterval(tickInterval);
    dailyMeta.textContent = `من أصل ${data.universe_size} سهماً تمت مراجعته، ${data.compliant_count} سهماً متوافقاً شرعياً`;
    if (data.picks.length === 0) {
      dailyStatus.textContent = "لا توجد توصيات متاحة حالياً.";
      return;
    }
    dailyStatus.textContent = "";
    data.picks.forEach((pick) => dailyGrid.appendChild(renderDailyCard(pick)));
  } catch (error) {
    clearInterval(tickInterval);
    dailyStatus.textContent = error.message;
    dailyStatus.classList.add("error");
  }
}

function ratioBarColor(passed) {
  if (passed === null || passed === undefined) return "#8d9bbf";
  return passed ? "#22c55e" : "#ef4444";
}

function renderRatioItem(check) {
  const pct = check.value === null ? 0 : Math.min(150, (check.value / check.threshold) * 100);
  const valueText = check.value === null ? "بيانات غير متوفرة" : `${(check.value * 100).toFixed(1)}%`;
  return `
    <div class="ratio-item">
      <div class="ratio-item-top">
        <span>${check.name_ar}</span>
        <span>${valueText} / حد ${(check.threshold * 100).toFixed(0)}%</span>
      </div>
      <div class="ratio-bar-track">
        <div class="ratio-bar-fill" style="width:${Math.min(100, pct)}%; background:${ratioBarColor(check.passed)}"></div>
      </div>
    </div>
  `;
}

function drawLineChart(canvas, points) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);

  if (!points || points.length < 2) return;

  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const padding = 10;
  const w = rect.width - padding * 2;
  const h = rect.height - padding * 2;

  const toX = (i) => padding + (i / (points.length - 1)) * w;
  const toY = (v) => padding + h - ((v - min) / range) * h;

  const gradient = ctx.createLinearGradient(0, 0, 0, rect.height);
  gradient.addColorStop(0, "rgba(212, 175, 55, 0.35)");
  gradient.addColorStop(1, "rgba(212, 175, 55, 0.02)");

  ctx.beginPath();
  ctx.moveTo(toX(0), toY(closes[0]));
  closes.forEach((c, i) => ctx.lineTo(toX(i), toY(c)));
  ctx.lineTo(toX(closes.length - 1), rect.height - padding);
  ctx.lineTo(toX(0), rect.height - padding);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.beginPath();
  ctx.moveTo(toX(0), toY(closes[0]));
  closes.forEach((c, i) => ctx.lineTo(toX(i), toY(c)));
  ctx.strokeStyle = "#d4af37";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function renderDetail(analysis, historyPoints) {
  const q = analysis.quote;
  const c = analysis.compliance;
  const t = analysis.technicals;
  const f = analysis.fundamentals;
  const r = analysis.recommendation;

  const changeClass = q.change_pct >= 0 ? "positive" : "negative";
  const scorePct = Math.round(((r.score.composite_score + 100) / 200) * 100);

  detailContent.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h2><span class="ticker-tag">${q.ticker}</span>${q.name}</h2>
        <p>${q.sector || "—"} • ${q.industry || "—"}</p>
      </div>
      <div class="price-block">
        <div class="price">${formatMoney(q.price, q.currency)}</div>
        <div class="pick-change ${changeClass}">${formatPct(q.change_pct)}</div>
      </div>
      <button class="close-detail" id="close-detail" aria-label="إغلاق">×</button>
    </div>

    <div class="chart-wrap"><canvas id="price-chart"></canvas></div>

    <div class="recommendation-hero">
      <div class="score-gauge" style="--pct:${scorePct}"><span>${r.score.composite_score.toFixed(0)}</span></div>
      <div>
        <span class="badge ${r.label}" style="font-size:14px;padding:8px 16px;">${r.label_ar}</span>
        <p class="muted" style="margin-top:8px;">
          النقاط الفنية: ${r.score.technical_score.toFixed(1)} (وزن ${(r.score.technical_weight * 100).toFixed(0)}%) •
          النقاط الأساسية: ${r.score.fundamental_score.toFixed(1)} (وزن ${(r.score.fundamental_weight * 100).toFixed(0)}%)
        </p>
      </div>
    </div>
    <ul class="rationale-list">
      ${r.rationale_ar.map((item) => `<li>${item}</li>`).join("")}
    </ul>

    <div class="detail-grid">
      <div class="detail-card">
        <h3>الفحص الشرعي <span class="badge ${c.status}" style="margin-inline-start:8px;">${COMPLIANCE_LABELS_AR[c.status]}</span></h3>
        ${renderRatioItem(c.financial_screen.debt_to_market_cap)}
        ${renderRatioItem(c.financial_screen.cash_and_securities_to_market_cap)}
        ${renderRatioItem(c.financial_screen.receivables_to_market_cap)}
        ${renderRatioItem(c.financial_screen.impure_income_to_revenue)}
        ${c.business_screen.matched_exclusions.length
          ? `<p class="muted" style="margin-top:8px;color:#ef4444;">استبعاد نشاط: ${c.business_screen.matched_exclusions.join("، ")}</p>`
          : ""}
      </div>

      <div class="detail-card">
        <h3>المؤشرات الفنية</h3>
        <div class="metric-row"><span>المتوسط المتحرك 20 يوم</span><span>${formatMoney(t.sma_20, q.currency)}</span></div>
        <div class="metric-row"><span>المتوسط المتحرك 50 يوم</span><span>${formatMoney(t.sma_50, q.currency)}</span></div>
        <div class="metric-row"><span>المتوسط المتحرك 200 يوم</span><span>${formatMoney(t.sma_200, q.currency)}</span></div>
        <div class="metric-row"><span>مؤشر القوة النسبية RSI</span><span>${formatNumber(t.rsi_14, 1)}</span></div>
        <div class="metric-row"><span>MACD</span><span>${formatNumber(t.macd, 3)}</span></div>
        <div class="metric-row"><span>أعلى سعر (52 أسبوع)</span><span>${formatMoney(t.week52_high, q.currency)}</span></div>
        <div class="metric-row"><span>أدنى سعر (52 أسبوع)</span><span>${formatMoney(t.week52_low, q.currency)}</span></div>
      </div>

      <div class="detail-card">
        <h3>المؤشرات الأساسية</h3>
        <div class="metric-row"><span>مكرر الربحية (P/E)</span><span>${formatNumber(f.trailing_pe, 1)}</span></div>
        <div class="metric-row"><span>مكرر الربحية المتوقع</span><span>${formatNumber(f.forward_pe, 1)}</span></div>
        <div class="metric-row"><span>هامش الربح</span><span>${f.profit_margin !== null ? (f.profit_margin * 100).toFixed(1) + "%" : "—"}</span></div>
        <div class="metric-row"><span>نمو الإيرادات</span><span>${f.revenue_growth !== null ? (f.revenue_growth * 100).toFixed(1) + "%" : "—"}</span></div>
        <div class="metric-row"><span>القيمة السوقية</span><span>${formatCompactMarketCap(f.market_cap)}</span></div>
      </div>
    </div>

    <div class="disclaimer-box">${analysis.disclaimer_ar}</div>
  `;

  document.getElementById("close-detail").addEventListener("click", () => {
    detailPanel.hidden = true;
  });

  const canvas = document.getElementById("price-chart");
  if (canvas && historyPoints) {
    requestAnimationFrame(() => drawLineChart(canvas, historyPoints));
  }
}

async function loadStockDetail(rawTicker) {
  const ticker = rawTicker.trim().toUpperCase();
  if (!ticker) return;

  detailPanel.hidden = false;
  detailContent.innerHTML = `<p class="status-line"><span class="spinner"></span>جاري تحليل السهم ${ticker}...</p>`;
  detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const [analysis, history] = await Promise.all([
      fetchJSON(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}`),
      fetchJSON(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/history?days=180`).catch(() => []),
    ]);
    renderDetail(analysis, history);
  } catch (error) {
    detailContent.innerHTML = `<p class="status-line error">${error.message}</p>`;
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadStockDetail(tickerInput.value);
});

refreshBtn.addEventListener("click", () => loadDaily(true));

function renderBacktestTrades(trades) {
  if (!trades.length) {
    return `<p class="muted">لم تُنفَّذ أي صفقة خلال فترة الاختبار.</p>`;
  }
  const rows = trades
    .map((trade) => {
      const changeClass = trade.return_pct >= 0 ? "positive" : "negative";
      return `
        <div class="metric-row">
          <span dir="ltr" style="unicode-bidi:isolate;">${trade.entry_date} → ${trade.exit_date || "لا يزال مفتوحاً"}</span>
          <span class="pick-change ${changeClass}">${formatPct(trade.return_pct)} (${trade.hold_days} يوم)</span>
        </div>
      `;
    })
    .join("");
  return `<div style="margin-top:8px;">${rows}</div>`;
}

function renderBacktestResult(result) {
  const strategyClass = result.total_return_pct >= 0 ? "positive" : "negative";
  const beatBuyHold = result.total_return_pct > result.buy_and_hold_return_pct;

  backtestContent.innerHTML = `
    <div class="chart-wrap"><canvas id="backtest-chart"></canvas></div>
    <div class="detail-grid">
      <div class="detail-card">
        <h3>${result.ticker} — من <span dir="ltr" style="unicode-bidi:isolate;">${result.start_date}</span> إلى <span dir="ltr" style="unicode-bidi:isolate;">${result.end_date}</span></h3>
        <div class="metric-row"><span>العائد الإجمالي (الاستراتيجية)</span><span class="pick-change ${strategyClass}">${formatPct(result.total_return_pct)}</span></div>
        <div class="metric-row"><span>عائد الشراء والاحتفاظ (Buy &amp; Hold)</span><span>${formatPct(result.buy_and_hold_return_pct)}</span></div>
        <div class="metric-row"><span>معدل النمو السنوي المركب (CAGR)</span><span>${formatPct(result.cagr_pct)}</span></div>
        <div class="metric-row"><span>أقصى تراجع (Max Drawdown)</span><span>${formatPct(result.max_drawdown_pct)}</span></div>
        <div class="metric-row"><span>عدد الصفقات</span><span>${result.num_trades}</span></div>
        <div class="metric-row"><span>نسبة الصفقات الرابحة</span><span>${result.win_rate_pct !== null ? result.win_rate_pct.toFixed(1) + "%" : "—"}</span></div>
        <div class="metric-row"><span>رأس المال الابتدائي → النهائي</span><span dir="ltr" style="unicode-bidi:isolate;">${formatMoney(result.initial_capital, "USD")} → ${formatMoney(result.final_capital, "USD")}</span></div>
      </div>
      <div class="detail-card">
        <h3>${beatBuyHold ? "الاستراتيجية تفوقت على الشراء والاحتفاظ" : "الشراء والاحتفاظ كان أفضل من الاستراتيجية"}</h3>
        <p class="muted">سجل الصفقات:</p>
        ${renderBacktestTrades(result.trades)}
      </div>
    </div>
    <div class="disclaimer-box">${result.methodology_note_ar}</div>
  `;

  const canvas = document.getElementById("backtest-chart");
  const points = result.equity_curve.map((p) => ({ close: p.value }));
  requestAnimationFrame(() => drawLineChart(canvas, points));
}

async function runTickerBacktest(rawTicker) {
  const ticker = rawTicker.trim().toUpperCase();
  if (!ticker) return;

  backtestStatus.textContent = "جاري تشغيل الاختبار الخلفي... قد يستغرق بضع ثوانٍ";
  backtestStatus.classList.remove("error");
  backtestContent.innerHTML = "";

  try {
    const result = await fetchJSON(`${API_BASE}/api/backtest/${encodeURIComponent(ticker)}`);
    backtestStatus.textContent = "";
    renderBacktestResult(result);
  } catch (error) {
    backtestStatus.textContent = error.message;
    backtestStatus.classList.add("error");
  }
}

function renderUniverseBacktest(summary) {
  const rows = summary.results
    .map((entry) => {
      const strategyClass = entry.total_return_pct >= 0 ? "positive" : "negative";
      return `
        <div class="metric-row">
          <span>${entry.ticker} ${entry.beat_buy_and_hold ? "✅" : ""}</span>
          <span class="pick-change ${strategyClass}">${formatPct(entry.total_return_pct)} مقابل ${formatPct(entry.buy_and_hold_return_pct)} (Buy&amp;Hold)</span>
        </div>
      `;
    })
    .join("");

  backtestContent.innerHTML = `
    <div class="detail-card">
      <h3>ملخص الاختبار على ${summary.tested_count} سهماً (فشل ${summary.failed_count})</h3>
      <div class="metric-row"><span>متوسط عائد الاستراتيجية</span><span>${formatPct(summary.average_strategy_return_pct)}</span></div>
      <div class="metric-row"><span>متوسط عائد الشراء والاحتفاظ</span><span>${formatPct(summary.average_buy_and_hold_return_pct)}</span></div>
      <div class="metric-row"><span>نسبة الأسهم التي تفوقت فيها الاستراتيجية</span><span>${summary.pct_beating_buy_and_hold.toFixed(1)}%</span></div>
      <div style="margin-top:10px;">${rows}</div>
    </div>
    <div class="disclaimer-box">${summary.methodology_note_ar}</div>
  `;
}

async function runUniverseBacktest() {
  backtestStatus.textContent = "جاري اختبار مجموعة الأسهم... قد يستغرق دقيقة تقريباً";
  backtestStatus.classList.remove("error");
  backtestContent.innerHTML = "";

  try {
    const summary = await fetchJSON(`${API_BASE}/api/backtest/universe?limit=20`);
    backtestStatus.textContent = "";
    renderUniverseBacktest(summary);
  } catch (error) {
    backtestStatus.textContent = error.message;
    backtestStatus.classList.add("error");
  }
}

backtestForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runTickerBacktest(backtestTickerInput.value);
});

runUniverseBacktestBtn.addEventListener("click", () => runUniverseBacktest());

loadDaily();
