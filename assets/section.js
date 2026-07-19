const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const data=window.SECTION||{};
const allReports=data.reports||[];
document.getElementById('company-count').textContent=data.companyCount??'—';
document.getElementById('report-count').textContent=data.reportCount??'—';
document.getElementById('latest-date').textContent=data.latestDate||'—';
document.getElementById('backtest-state').textContent=data.rankings?.length?'原型榜单':'待接入';
function renderRankings(){const rows=data.rankings||[];document.querySelector('#ranking-table tbody').innerHTML=rows.length?rows.map((r,i)=>`<tr><td class="rank">${r.rank||i+1}</td><td><b>${esc(r.company_name||r.company)}</b></td><td class="score">${r.score==null?'—':r.score}</td><td>${r.accuracy==null?'—':r.accuracy+'%'}</td><td class="${Number(r.avg_return_pct)>=0?'positive':'negative'}">${r.avg_return_pct==null?'—':(Number(r.avg_return_pct)>0?'+':'')+r.avg_return_pct+'%'}</td><td>${r.sample_count??'—'}</td><td><span class="tag">${(r.sample_count||0)<10?'观察样本':'正式排名'}</span></td></tr>`).join(''):'<tr><td colspan="7" class="muted">对应板块暂无回测排名数据，等待研报与行情数据接入。</td></tr>'}
function renderReports(rows){document.querySelector('#report-table tbody').innerHTML=rows.slice(0,300).map(r=>`<tr><td>${esc(r.publish_date)}</td><td>${esc(r.company)}</td><td>${esc(r.report_type)}</td><td>${r.detail_url?`<a href="${esc(r.detail_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}</td><td>${esc(r.source_type)}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">暂无研报数据</td></tr>'}
renderRankings();renderReports(allReports);document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase().trim();renderReports(allReports.filter(r=>`${r.title||''} ${r.company||''} ${r.matched_keywords||''}`.toLowerCase().includes(q)))})
