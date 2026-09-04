/* commodity.js — 品种详情页逻辑。数据异步加载 {sector}/{CODE}.json（精简字段） */
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/* 五级方向标签（构建期由标题规则生成 dir5：强多/多/中性/空/强空，无则不展示） */
const DIR5_CLS = { '强多': 's-bull', '多': 'bull', '中性': 'neutral', '空': 'bear', '强空': 's-bear' };
const dirBadge = r => { const c = DIR5_CLS[r.dir5]; return c ? ` <span class="dir-tag dt-${c}">${esc(r.dir5)}</span>` : ''; };
const el = id => document.getElementById(id);

let bt = [], ranking = [], reports = [];

/* ---------- 统计卡（数字滚动） ---------- */
function renderStats() {
  const totalHits = bt.filter(x => x.hit === true).length;
  const accuracy = bt.length ? (totalHits / bt.length * 100) : 0;
  const best = ranking[0];
  UI.countUp(el('stat-samples'), bt.length);
  UI.countUp(el('stat-accuracy'), bt.length ? Number(accuracy.toFixed(1)) : null, { dec: 1, suffix: '%' });
  UI.countUp(el('stat-companies'), ranking.length);
  UI.countUp(el('stat-reports'), reports.length);
  el('stat-best').textContent = best ? `${best.company_name}（${best.accuracy}%）` : '—';
}

/* ---------- 机构排行 ---------- */
function renderRanking() {
  el('company-table').querySelector('tbody').innerHTML = ranking.length ? ranking.map((r, i) => {
    const badge = i < 3 ? `<span class="rank-badge rb-${i + 1}">${r.rank || i + 1}</span>` : `<span class="rank-num">${r.rank || i + 1}</span>`;
    const acc = r.accuracy == null ? null : Number(r.accuracy);
    const accCell = acc == null ? '—'
      : `<span class="acc-wrap"><span class="acc-val">${acc}%</span><span class="acc-bar"><i style="width:${Math.min(100, acc)}%"></i></span></span>`;
    const ret = r.avg_return_pct == null ? '—' : (Number(r.avg_return_pct) > 0 ? '+' : '') + r.avg_return_pct + '%';
    const status = (r.sample_count || 0) < 5 ? '样本不足，仅观察' : (r.sample_count || 0) < 10 ? '观察样本' : '正式排名';
    return `<tr><td class="rank">${badge}</td><td><b>${esc(r.company_name || r.co)}</b></td><td>${r.sample_count ?? '—'}</td><td>${r.hit_count ?? '—'}</td><td>${accCell}</td><td class="${Number(r.avg_return_pct) >= 0 ? 'positive' : 'negative'}">${ret}</td><td>${r.bull_count ?? '—'} / ${r.bear_count ?? '—'}</td><td><span class="tag">${status}</span></td></tr>`;
  }).join('') : '<tr><td colspan="8" class="muted">该品种暂无有效回测数据。</td></tr>';
}

/* ---------- 研报观点（回测命中为构建期预 join 字段 bh） ---------- */
function renderReports() {
  const sorted = reports.slice().sort((a, b) => String(b.publish_date || '').localeCompare(String(a.publish_date || '')));
  el('report-table').querySelector('tbody').innerHTML = sorted.slice(0, 200).map(r => {
    const dir = r.dir || 'unknown', dc = r.dcn || '暂无';
    const result = r.bh === undefined ? '<span class="muted">未回测</span>'
      : r.bh === true ? '<span class="result-hit">命中</span>'
      : r.bh === false ? '<span class="result-miss">未命中</span>'
      : '不评估';
    return `<tr><td>${esc(r.publish_date)}</td><td><b>${esc(r.company)}</b></td><td class="opinion-${esc(dir)}">${esc(dc)}</td><td>${r.detail_url ? `<a href="${esc(r.detail_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}${dirBadge(r)}</td><td>${result}</td></tr>`;
  }).join('') || '<tr><td colspan="5" class="muted">暂无研报数据</td></tr>';
}

/* ---------- 图表 ---------- */
function emptyChart(id, title) {
  const node = el(id);
  if (node) node.innerHTML = `<div class="chart-empty"><b>${title}</b><span>当前品种有效回测样本不足，暂不绘制</span></div>`;
}
function drawCharts() {
  if (typeof echarts === 'undefined') { ['equity-chart', 'trade-chart', 'scatter-chart'].forEach(id => emptyChart(id, '统计图表')); return; }
  const base = { animation: false, textStyle: { fontFamily: 'Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif' }, color: ['#c00', '#1a3a5c', '#b8860b', '#ef8d52', '#66a6c9', '#9e8dc3', '#504060', '#a05020', '#1e5a46'] };
  /* 1. 各机构累计收益曲线 */
  const ec = el('equity-chart');
  if (bt.length >= 2) {
    const dates = [...new Set(bt.map(x => x.exd))].sort();
    const companies = [...new Set(bt.map(x => x.co))];
    const series = companies.map(c => {
      let total = 0;
      const vals = dates.map(d => { const r = bt.find(x => x.co === c && x.exd === d); if (r) total += Number(r.ret || 0); return total == 0 && r == null ? null : Number(total.toFixed(4)); });
      return { name: c, type: 'line', smooth: true, showSymbol: false, connectNulls: true, data: vals };
    });
    UI.reg(echarts.init(ec)).setOption({ ...base,
      title: { text: '各机构累计策略收益（按研报观点做多/做空）', textStyle: { fontSize: 14, color: '#17221f' } },
      tooltip: { trigger: 'axis', valueFormatter: v => v == null ? '—' : v + '%' },
      legend: { top: 34, type: 'scroll', icon: 'rect', itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 } },
      grid: { left: 48, right: 18, top: 76, bottom: 35 },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
      series });
  } else emptyChart(ec, '累计策略收益');

  /* 2. 逐笔收益柱状图 */
  const pc = el('trade-chart');
  if (bt.length) {
    const colors = bt.map(x => x.hit === true ? '#c00' : '#1a3a5c');
    UI.reg(echarts.init(pc)).setOption({ ...base,
      title: { text: '逐笔回测收益（红=命中 / 蓝=未命中）', textStyle: { fontSize: 14, color: '#17221f' } },
      tooltip: { trigger: 'axis', formatter: p => { const x = bt[p[0].dataIndex]; return `${x.exd}<br>${esc(x.co)} · ${x.dcn}<br>入场 ${x.ep} → 出场 ${x.xp}<br>策略收益 ${p[0].value}% · ${x.hit === true ? '命中' : '未命中'}`; } },
      grid: { left: 48, right: 18, top: 45, bottom: 60 },
      xAxis: { type: 'category', data: bt.map(x => x.exd), axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
      dataZoom: [{ type: 'slider', height: 16, bottom: 8 }],
      series: [{ type: 'bar', data: bt.map(x => Number(x.ret || 0).toFixed(4)), itemStyle: { color: p => colors[p.dataIndex] } }] });
  } else emptyChart(pc, '逐笔回测收益');

  /* 3. 命中率 × 样本数散点 */
  const sc = el('scatter-chart');
  if (ranking.length) {
    UI.reg(echarts.init(sc)).setOption({ ...base,
      title: { text: '命中率 × 样本数', textStyle: { fontSize: 14, color: '#17221f' } },
      tooltip: { formatter: p => `${p.data[3]}<br>样本数：${p.data[0]}<br>命中率：${p.data[1]}%<br>平均收益：${p.data[2]}%` },
      grid: { left: 48, right: 18, top: 45, bottom: 40 },
      xAxis: { name: '样本数', type: 'value' },
      yAxis: { name: '命中率 %', type: 'value', max: 100 },
      series: [{ type: 'scatter', symbolSize: v => Math.max(10, Math.min(30, Math.sqrt(v[0]) * 5)), data: ranking.map(r => [r.sample_count, r.accuracy, r.avg_return_pct, r.company_name]), label: { show: true, formatter: p => p.data[3], position: 'top', fontSize: 10, color: '#17221f' } }] });
  } else emptyChart(sc, '命中率 × 样本数');
}

/* ---------- 初始化 ---------- */
UI.reveal();
(async function init() {
  try {
    const res = await fetch(window.PAGE.dataUrl);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    bt = (data.backtests || []).slice().sort((a, b) => String(a.exd).localeCompare(String(b.exd)));
    ranking = data.ranking || [];
    reports = data.reports || [];
  } catch (err) {
    ['stat-samples', 'stat-accuracy', 'stat-companies', 'stat-reports'].forEach(id => { const n = el(id); if (n) n.textContent = '加载失败'; });
    document.querySelectorAll('.table-wrap tbody').forEach(tb => { tb.innerHTML = '<tr><td colspan="8" class="muted">数据加载失败，请刷新重试。</td></tr>'; });
    console.error('commodity data load failed', err);
    return;
  }
  renderStats();
  renderRanking();
  renderReports();
  drawCharts();
})();
