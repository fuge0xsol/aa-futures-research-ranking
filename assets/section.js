/* section.js — 板块页逻辑。数据改为异步加载 {sector}/data.json（精简字段） */
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const el = id => document.getElementById(id);
/* 五级方向标签（构建期由标题规则生成 dir5：强多/多/中性/空/强空，无则不展示） */
const DIR5_CLS = { '强多': 's-bull', '多': 'bull', '中性': 'neutral', '空': 'bear', '强空': 's-bear' };
const dirBadge = r => { const c = DIR5_CLS[r.dir5]; return c ? ` <span class="dir-tag dt-${c}">${esc(r.dir5)}</span>` : ''; };

let data = null;
let selectedCommodity = '';
let selectedReportCommodity = '';

/* ---------- 状态 ---------- */
function setStat(id, val, opts) { UI.countUp(el(id), val, opts); }

/* ---------- 机构回测排名 ---------- */
function renderRankings() {
  const rows = data.rankings || [];
  el('ranking-table').querySelector('tbody').innerHTML = rows.length ? rows.map((r, i) => {
    const badge = i < 3 ? `<span class="rank-badge rb-${i + 1}">${r.rank || i + 1}</span>` : `<span class="rank-num">${r.rank || i + 1}</span>`;
    const acc = r.accuracy == null ? null : Number(r.accuracy);
    const accCell = acc == null ? '—'
      : `<span class="acc-wrap"><span class="acc-val">${acc}%</span><span class="acc-bar"><i style="width:${Math.min(100, acc)}%"></i></span></span>`;
    const ret = r.avg_return_pct == null ? '—' : (Number(r.avg_return_pct) > 0 ? '+' : '') + r.avg_return_pct + '%';
    return `<tr><td class="rank">${badge}</td><td><b>${esc(r.company_name)}</b></td><td class="score">${r.score == null ? '—' : r.score}</td><td>${accCell}</td><td class="${Number(r.avg_return_pct) >= 0 ? 'positive' : 'negative'}">${ret}</td><td>${r.sample_count ?? '—'}</td><td><span class="tag">${(r.sample_count || 0) < 10 ? '观察样本' : '正式排名'}</span></td></tr>`;
  }).join('') : '<tr><td colspan="7" class="muted">对应板块暂无回测排名数据，等待研报与行情数据接入。</td></tr>';
}

/* ---------- 研报库 ---------- */
function reportMatches(report, name) {
  if (!name) return true;
  return report.cn === name || (report.kw || []).includes(name);
}
function renderReports(rows) {
  const sorted = rows.slice().sort((a, b) => String(b.publish_date || '').localeCompare(String(a.publish_date || '')));
  el('report-table').querySelector('tbody').innerHTML = sorted.slice(0, 300).map(r =>
    `<tr><td>${esc(r.publish_date)}</td><td>${esc(r.company)}</td><td>${esc(r.report_type)}</td><td>${r.detail_url ? `<a href="${esc(r.detail_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}${dirBadge(r)}</td><td>${esc(r.source_type)}</td></tr>`
  ).join('') || '<tr><td colspan="5" class="muted">暂无研报数据</td></tr>';
}
function renderReportTabs() {
  const names = [...new Set((data.reports || []).flatMap(r => [r.cn, ...(r.kw || [])]).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const active = selectedReportCommodity && names.includes(selectedReportCommodity) ? selectedReportCommodity : '';
  const tabs = el('report-commodity-tabs');
  if (!tabs) return;
  tabs.innerHTML = `<button class="commodity-tab ${!active ? 'active' : ''}" data-report-commodity="">全部品种</button>` +
    names.map(n => `<button class="commodity-tab ${n === active ? 'active' : ''}" data-report-commodity="${esc(n)}">${esc(n)}</button>`).join('');
  tabs.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    selectedReportCommodity = b.dataset.reportCommodity || '';
    renderReportTabs();
    renderReports((data.reports || []).filter(r => reportMatches(r, selectedReportCommodity)));
  }));
}

/* ---------- 品种卡片 ---------- */
function productName(x) { return x.cn || '未知品种'; }
function renderProductTabs() {
  const groups = {};
  (data.backtests || []).forEach(x => {
    const code = x.code || x.cn;
    groups[code] = groups[code] || { name: productName(x), code, rows: [] };
    groups[code].rows.push(x);
  });
  const cards = Object.values(groups).map(g => {
    const hits = g.rows.filter(x => x.hit === true).length;
    const acc = g.rows.length ? (hits / g.rows.length * 100) : 0;
    const comps = {};
    g.rows.forEach(x => { const h = (comps[x.co] = comps[x.co] || { h: 0, n: 0 }); h.n++; if (x.hit === true) h.h++; });
    let best = '', bestA = -1;
    Object.entries(comps).forEach(([c, v]) => { const a = v.n >= 2 ? v.h / v.n * 100 : -1; if (a > bestA) { bestA = a; best = c; } });
    return { ...g, hits, acc, best };
  }).sort((a, b) => b.rows.length - a.rows.length);
  const grid = el('commodity-tabs');
  if (!grid) return;
  if (!cards.length) { grid.innerHTML = '<span class="muted">暂无可用品种</span>'; return; }
  grid.innerHTML = cards.map(c =>
    `<a class="commodity-card" href="./${encodeURIComponent(c.code)}.html"><div class="cc-head"><b>${esc(c.name)}</b><span class="cc-code">${esc(c.code)}</span></div><div class="cc-stats"><span>回测<b>${c.rows.length}</b></span><span>命中率<b>${c.acc.toFixed(0)}%</b></span><span>机构<b>${new Set(c.rows.map(x => x.co)).size}</b></span></div><div class="cc-best">${c.best ? `最准：<b>${esc(c.best)}</b>` : '样本积累中'}</div></a>`
  ).join('');
}

/* ---------- 品种分析视图 ---------- */
function productRecords(name) { return (data.backtests || []).filter(x => productName(x) === name); }
function productReports(name) { return (data.reports || []).filter(r => reportMatches(r, name)); }
function renderProductView() {
  const name = selectedCommodity;
  if (!name) return;
  const rows = productRecords(name), reports = productReports(name);
  const byCompany = [...new Set(rows.map(x => x.co))].map(company => {
    const r = rows.filter(x => x.co === company);
    const hits = r.filter(x => x.hit === true).length;
    const avg = r.length ? r.reduce((s, x) => s + Number(x.ret || 0), 0) / r.length : 0;
    return { company, sample: r.length, hits, accuracy: r.length ? hits / r.length * 100 : 0, avg };
  }).sort((a, b) => b.accuracy - a.accuracy || b.sample - a.sample);
  const totalHits = rows.filter(x => x.hit === true).length;
  el('commodity-summary').innerHTML =
    `<span>品种<b>${esc(name)}</b></span><span>有效回测<b>${rows.length}</b></span><span>总体命中率<b>${rows.length ? (totalHits / rows.length * 100).toFixed(2) : '—'}${rows.length ? '%' : ''}</b></span><span>研报观点<b>${reports.length}</b></span>`;
  el('commodity-ranking-table').querySelector('tbody').innerHTML = byCompany.length ? byCompany.map((x, i) => {
    const badge = i < 3 ? `<span class="rank-badge rb-${i + 1}">${i + 1}</span>` : `<span class="rank-num">${i + 1}</span>`;
    return `<tr><td class="rank">${badge}</td><td><b>${esc(x.company)}</b></td><td>${x.sample}</td><td>${x.hits}</td><td>${x.accuracy.toFixed(2)}%</td><td class="${x.avg >= 0 ? 'positive' : 'negative'}">${x.avg >= 0 ? '+' : ''}${x.avg.toFixed(4)}%</td><td><span class="tag">${x.sample < 10 ? '观察样本' : '正式排名'}</span></td></tr>`;
  }).join('') : '<tr><td colspan="7" class="muted">该品种暂无有效方向回测数据。</td></tr>';
  el('commodity-report-table').querySelector('tbody').innerHTML = reports.slice(0, 200).map(r => {
    const dir = r.dir || 'unknown', dc = r.dcn || '暂无';
    const result = r.bh === undefined ? '未回测' : (r.bh === true ? '命中' : r.bh === false ? '未命中' : '不评估');
    return `<tr><td>${esc(r.publish_date)}</td><td>${esc(r.company)}</td><td class="opinion-${esc(dir)}">${esc(dc)}</td><td>${r.detail_url ? `<a href="${esc(r.detail_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}${dirBadge(r)}</td><td>${esc(r.dsrc || '标题/摘要')}</td><td class="${result === '命中' ? 'result-hit' : result === '未命中' ? 'result-miss' : 'muted'}">${result}</td></tr>`;
  }).join('') || '<tr><td colspan="6" class="muted">该品种暂无研报观点。</td></tr>';
}

/* ---------- 统计图 ---------- */
function emptyChart(id, title) {
  const node = el(id);
  if (node) node.innerHTML = `<div class="chart-empty"><b>${title}</b><span>当前板块有效回测样本不足，暂不绘制统计图</span></div>`;
}
function drawCharts() {
  if (typeof echarts === 'undefined') { ['return-chart', 'scatter-chart', 'heatmap-chart'].forEach(id => emptyChart(id, '统计图表')); return; }
  const backtests = data.backtests || [];
  const base = { animation: false, textStyle: { fontFamily: 'Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif' }, color: ['#1e5a46', '#ef8d52', '#66a6c9', '#9e8dc3'] };
  /* 累计收益曲线 */
  const returns = {};
  backtests.slice().sort((a, b) => String(a.exd).localeCompare(String(b.exd))).forEach(x => { returns[x.exd] = (returns[x.exd] || 0) + Number(x.ret || 0); });
  let total = 0;
  const dates = Object.keys(returns).sort(), curve = dates.map(d => { total += returns[d]; return Number(total.toFixed(4)); });
  const rc = UI.reg(echarts.init(el('return-chart')));
  rc.setOption({ ...base, title: { text: '累计策略收益', textStyle: { fontSize: 15, color: '#17221f' } }, tooltip: { trigger: 'axis', valueFormatter: v => `${v}%` }, grid: { left: 45, right: 18, top: 45, bottom: 35 }, xAxis: { type: 'category', data: dates }, yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } }, series: [{ type: 'line', smooth: true, showSymbol: false, data: curve, areaStyle: { opacity: .12 } }] });
  /* 命中率 × 样本数 */
  const companies = [...new Set(backtests.map(x => x.co))];
  const sc = UI.reg(echarts.init(el('scatter-chart')));
  sc.setOption({ ...base, title: { text: '命中率 × 样本数', textStyle: { fontSize: 15, color: '#17221f' } }, tooltip: { formatter: p => `${p.data[3]}<br>样本数：${p.data[0]}<br>命中率：${p.data[1]}%` }, grid: { left: 48, right: 18, top: 45, bottom: 40 }, xAxis: { name: '样本数', type: 'value' }, yAxis: { name: '命中率 %', type: 'value', max: 100 }, series: [{ type: 'scatter', symbolSize: v => Math.max(10, Math.min(28, Math.sqrt(v[0]) * 4)), data: companies.map(c => { const rows = backtests.filter(x => x.co === c), hits = rows.filter(x => x.hit).length; return [rows.length, Number((hits / rows.length * 100).toFixed(2)), rows.reduce((s, x) => s + Number(x.ret || 0), 0), c]; }) }] });
  /* 机构 × 品种热力图 */
  const commodities = [...new Set(backtests.map(productName))];
  const hm = UI.reg(echarts.init(el('heatmap-chart')));
  const hmData = companies.flatMap((c, yi) => commodities.map((v, xi) => {
    const r = backtests.filter(x => x.co === c && productName(x) === v);
    return [xi, yi, r.length ? Number((r.reduce((s, x) => s + Number(x.ret || 0), 0) / r.length).toFixed(2)) : null];
  }));
  hm.setOption({ ...base, title: { text: '机构 × 品种 平均策略收益', textStyle: { fontSize: 15, color: '#17221f' } }, tooltip: { formatter: p => `${companies[p.data[1]]} × ${commodities[p.data[0]]}<br>平均收益：${p.data[2] == null ? '无样本' : p.data[2] + '%'}` }, grid: { left: 110, right: 18, top: 45, bottom: 60 }, xAxis: { type: 'category', data: commodities, axisLabel: { rotate: 45, fontSize: 10 } }, yAxis: { type: 'category', data: companies, axisLabel: { fontSize: 10 } }, visualMap: { min: -3, max: 3, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#1a3a5c', '#f5f6f8', '#c00'] } }, series: [{ type: 'heatmap', data: hmData, label: { show: true, fontSize: 9, formatter: p => p.data[2] == null ? '' : p.data[2] } }] });
}

/* ---------- 搜索（防抖） ---------- */
function bindSearch() {
  const input = el('search');
  input.addEventListener('input', UI.debounce(e => {
    const q = e.target.value.toLowerCase().trim();
    const active = selectedReportCommodity;
    renderReports((data.reports || []).filter(r =>
      (!active || reportMatches(r, active)) &&
      `${r.title || ''} ${r.company || ''} ${(r.kw || []).join(' ')}`.toLowerCase().includes(q)
    ));
  }, 180));
}

/* ---------- 初始化 ---------- */
UI.reveal();
(async function init() {
  try {
    const res = await fetch(window.PAGE.dataUrl);
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch (err) {
    ['company-count', 'report-count', 'latest-date'].forEach(id => { const n = el(id); if (n) n.textContent = '加载失败'; });
    document.querySelectorAll('.table-wrap tbody').forEach(tb => { tb.innerHTML = '<tr><td colspan="8" class="muted">数据加载失败，请刷新重试。</td></tr>'; });
    console.error('data.json load failed', err);
    return;
  }
  setStat('company-count', data.companyCount);
  setStat('report-count', data.reportCount);
  el('latest-date').textContent = data.latestDate || '—';
  el('backtest-state').textContent = data.rankings && data.rankings.length ? '原型榜单' : '待接入';
  renderRankings();
  renderReports(data.reports || []);
  renderReportTabs();
  renderProductTabs();
  bindSearch();
  /* 默认选中样本量最大的品种 */
  const firstCard = document.querySelector('#commodity-tabs .commodity-card .cc-code');
  if (firstCard) { selectedCommodity = firstCard.textContent.trim(); renderProductView(); }
  drawCharts();
})();
