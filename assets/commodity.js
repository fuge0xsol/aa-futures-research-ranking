const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const data=window.COMMODITY||{};
const bt=(data.backtests||[]).filter(x=>x.horizon_days===1&&x.status==='valid').slice().sort((a,b)=>a.exit_date.localeCompare(b.exit_date));
const ranking=data.ranking||[];
const reports=data.reports||[];

// Stats
const totalHits=bt.filter(x=>x.hit===true).length;
const accuracy=bt.length?(totalHits/bt.length*100):0;
const best=ranking[0];
document.getElementById('stat-samples').textContent=bt.length||'—';
document.getElementById('stat-accuracy').textContent=bt.length?accuracy.toFixed(1)+'%':'—';
document.getElementById('stat-companies').textContent=ranking.length||'—';
document.getElementById('stat-reports').textContent=reports.length||'—';
document.getElementById('stat-best').textContent=best?`${best.company_name}（${best.accuracy}%）`:'—';

// Ranking table
document.querySelector('#company-table tbody').innerHTML=ranking.length?ranking.map((r,i)=>`<tr><td class="rank">${r.rank||i+1}</td><td><b>${esc(r.company_name||r.company)}</b></td><td>${r.sample_count??'—'}</td><td>${r.hit_count??'—'}</td><td>${r.accuracy==null?'—':r.accuracy+'%'}</td><td class="${Number(r.avg_return_pct)>=0?'positive':'negative'}">${r.avg_return_pct==null?'—':(Number(r.avg_return_pct)>0?'+':'')+r.avg_return_pct+'%'}</td><td>${r.bull_count??'—'} / ${r.bear_count??'—'}</td><td><span class="tag">${(r.sample_count||0)<5?'样本不足，仅观察':(r.sample_count||0)<10?'观察样本':'正式排名'}</span></td></tr>`).join(''):'<tr><td colspan="8" class="muted">该品种暂无有效回测数据。</td></tr>';

// Reports table
document.querySelector('#report-table tbody').innerHTML=reports.slice(0,200).map(r=>{
const m=bt.find(x=>x.report_id&&x.report_id.includes(r.title||'')&&x.company===r.company);
const dir=r.direction||m?.direction||'unknown',dc=r.direction_cn||m?.direction_cn||'暂无';
const result=m?(m.hit===true?'<span class="result-hit">命中</span>':m.hit===false?'<span class="result-miss">未命中</span>':'不评估'):'<span class="muted">未回测</span>';
return `<tr><td>${esc(r.publish_date)}</td><td><b>${esc(r.company)}</b></td><td class="opinion-${esc(dir)}">${esc(dc)}</td><td>${r.detail_url?`<a href="${esc(r.detail_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}</td><td>${result}</td></tr>`;
}).join('')||'<tr><td colspan="5" class="muted">暂无研报数据</td></tr>';

// Charts
function emptyChart(id,title){const el=document.getElementById(id);if(el)el.innerHTML=`<div class="chart-empty"><b>${title}</b><span>当前品种有效回测样本不足，暂不绘制</span></div>`}
function drawCharts(){
const base={animation:false,textStyle:{fontFamily:'Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif'},color:['#c00','#1a3a5c','#b8860b','#ef8d52','#66a6c9','#9e8dc3','#504060','#a05020','#1e5a46']};
// 1. Equity curve per company
const ec=document.getElementById('equity-chart');
if(bt.length>=2){
const dates=[...new Set(bt.map(x=>x.exit_date))].sort();
const companies=[...new Set(bt.map(x=>x.company))];
const series=companies.map(c=>{
let total=0;
const vals=dates.map(d=>{const r=bt.find(x=>x.company===c&&x.exit_date===d);if(r)total+=Number(r.strategy_return_pct||0);return total==0&&r==null?null:Number(total.toFixed(4));});
return {name:c,type:'line',smooth:true,showSymbol:false,connectNulls:true,data:vals};
});
echarts.init(ec).setOption({...base,
title:{text:'各机构累计策略收益（按研报观点做多/做空）',textStyle:{fontSize:14,color:'#17221f'}},
tooltip:{trigger:'axis',valueFormatter:v=>v==null?'—':v+'%'},
legend:{top:34,type:'scroll',icon:'rect',itemWidth:14,itemHeight:8,textStyle:{fontSize:11}},
grid:{left:48,right:18,top:76,bottom:35},
xAxis:{type:'category',data:dates},
yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},
series});
}else emptyChart(ec,'累计策略收益');

// 2. Per-trade bar
const pc=document.getElementById('trade-chart');
if(bt.length){
const colors=bt.map(x=>x.hit===true?'#c00':'#1a3a5c');
echarts.init(pc).setOption({...base,
title:{text:'逐笔回测收益（红=命中 / 蓝=未命中）',textStyle:{fontSize:14,color:'#17221f'}},
tooltip:{trigger:'axis',formatter:p=>{const x=bt[p[0].dataIndex];return `${x.exit_date}<br>${esc(x.company)} · ${x.direction_cn}<br>入场 ${x.entry_price} → 出场 ${x.exit_price}<br>策略收益 ${p[0].value}% · ${x.hit===true?'命中':'未命中'}`}},
grid:{left:48,right:18,top:45,bottom:60},
xAxis:{type:'category',data:bt.map(x=>x.exit_date),axisLabel:{rotate:45,fontSize:10}},
yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},
dataZoom:[{type:'slider',height:16,bottom:8}],
series:[{type:'bar',data:bt.map(x=>Number(x.strategy_return_pct||0).toFixed(4)),itemStyle:{color:p=>colors[p.dataIndex]}}]});
}else emptyChart(pc,'逐笔回测收益');

// 3. Scatter: accuracy x samples
const sc=document.getElementById('scatter-chart');
if(ranking.length){
echarts.init(sc).setOption({...base,
title:{text:'命中率 × 样本数',textStyle:{fontSize:14,color:'#17221f'}},
tooltip:{formatter:p=>`${p.data[3]}<br>样本数：${p.data[0]}<br>命中率：${p.data[1]}%<br>平均收益：${p.data[2]}%`},
grid:{left:48,right:18,top:45,bottom:40},
xAxis:{name:'样本数',type:'value'},
yAxis:{name:'命中率 %',type:'value',max:100},
series:[{type:'scatter',symbolSize:v=>Math.max(10,Math.min(30,Math.sqrt(v[0])*5)),data:ranking.map(r=>[r.sample_count,r.accuracy,r.avg_return_pct,r.company_name]),label:{show:true,formatter:p=>p.data[3],position:'top',fontSize:10,color:'#17221f'}}]});
}else emptyChart(sc,'命中率 × 样本数');
}
if(typeof echarts==='undefined'){['equity-chart','trade-chart','scatter-chart'].forEach(id=>emptyChart(id,'统计图表'))}else{drawCharts()}
