#!/usr/bin/env python3
"""Extract simple title-level directions and run reproducible daily-bar backtests."""
from __future__ import annotations
import json, re, subprocess, sys, itertools
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; SRC=DATA/'sector_reports'; OUT=DATA/'backtest'
PYTHON='/home/ubuntu/agri_futures_alert_mvp/.venv/bin/python'

BULL=['看涨','偏强','偏多','做多','上涨','上行','反弹','逢低买入','震荡偏强','强势','有望走强']
BEAR=['看跌','偏弱','偏空','做空','下跌','下行','回落','逢高卖出','震荡偏弱','弱势','压制','承压']
NEUTRAL=['震荡','区间运行','观望','等待','横盘','稳定']

def direction(title):
 t=str(title or '')
 bull=sum(t.count(x) for x in BULL); bear=sum(t.count(x) for x in BEAR); neutral=sum(t.count(x) for x in NEUTRAL)
 # explicit mixed/neutral language wins when it dominates
 if bull and bear and abs(bull-bear)<=1: return 'neutral','中性',0.45,'标题规则'
 if neutral and not bull and not bear: return 'neutral','中性',0.55,'标题规则'
 if bull>bear and bull: return 'bullish','偏多',0.62,'标题规则'
 if bear>bull and bear: return 'bearish','偏空',0.62,'标题规则'
 return 'unknown','暂无',0.0,'未识别'

def load_bars(symbol):
 code=f'{symbol}0'
 script=f'''import akshare as ak, json
try:
 d=ak.futures_zh_daily_sina(symbol={code!r})
 print(json.dumps(d.to_dict("records"),ensure_ascii=False))
except Exception as e:
 print(json.dumps({{"error":str(e)}}))
'''
 p=subprocess.run([PYTHON,'-c',script],capture_output=True,text=True,timeout=120)
 if p.returncode: raise RuntimeError(p.stderr[-500:])
 return json.loads(p.stdout)

def norm_bars(records):
 out={}
 for r in records:
  d=str(r.get('date',''))[:10];
  if not d: continue
  try: out[d]=float(r['close'])
  except (TypeError,ValueError): pass
 return out

def backtest_one(report,bars,horizon):
 d=report.get('publish_date',''); dates=sorted(x for x in bars if x>=d)
 if not dates: return None
 entry_date=dates[0]; i=dates.index(entry_date); exit_i=i+horizon
 if exit_i>=len(dates): return None
 entry=bars[entry_date]; exit_date=dates[exit_i]; exit=bars[exit_date]
 direction=report['direction']; market=(exit/entry-1)*100
 strategy=market if direction=='bullish' else -market if direction=='bearish' else 0
 return {'report_id':report['report_id'],'company':report['company'],'sector':report['sector'],'sector_name':report['sector_name'],'commodity':report['commodity'],'commodity_name':report['commodity_name'],'direction':direction,'direction_cn':report['direction_cn'],'horizon_days':horizon,'entry_date':entry_date,'exit_date':exit_date,'entry_price':round(entry,4),'exit_price':round(exit,4),'market_return_pct':round(market,4),'strategy_return_pct':round(strategy,4),'hit': strategy>0 if direction!='neutral' else None,'data_source':'AKShare futures_zh_daily_sina continuous symbol 0','status':'valid'}

def main():
 OUT.mkdir(exist_ok=True)
 all_norm=[]; all_bt=[]; bar_cache={}
 for file in sorted(SRC.glob('*.json')):
  if file.name=='all.json': continue
  payload=json.loads(file.read_text())
  for idx,r in enumerate(payload.get('reports',[])):
   vars=r.get('main_varieties') or []
   if not vars: continue
   v=vars[0]; d,dc,conf,source=direction(r.get('title'))
   nr=dict(r); nr.update({'report_id':f"{r['company']}|{r['sector']}|{r.get('publish_date','')}|{r.get('title','')}",'commodity':v['code'],'commodity_name':v['name'],'contract_reference':'主力连续','direction':d,'direction_cn':dc,'direction_confidence':conf,'direction_source':source,'holding_period':'1D/5D/20D','needs_review':d=='unknown' or conf<0.6})
   all_norm.append(nr)
   if d in ('bullish','bearish') and r.get('publish_date'):
    try:
     bars=bar_cache.setdefault(v['code'],norm_bars(load_bars(v['code'])))
    except Exception as e: print('market error',v['code'],e); continue
    for h in (1,5,20):
     bt=backtest_one(nr,bars,h)
     if bt: all_bt.append(bt)
 print('normalized',len(all_norm),'backtests',len(all_bt))
 (OUT/'normalized_reports.json').write_text(json.dumps(all_norm,ensure_ascii=False,indent=2))
 (OUT/'backtest_records.json').write_text(json.dumps(all_bt,ensure_ascii=False,indent=2))
 for h in (1,5,20):
  rec=[x for x in all_bt if x['horizon_days']==h]
  ranks=[]
  for company, rows in sorted(((k,list(g)) for k,g in itertools.groupby(sorted(rec,key=lambda x:x['company']),lambda x:x['company'])),key=lambda x:x[0]):
   hits=sum(bool(x['hit']) for x in rows); returns=[x['strategy_return_pct'] for x in rows]
   acc=hits/len(rows)*100; avg=sum(returns)/len(returns)
   score=round(0.6*acc+0.4*max(0,min(100,50+avg*10)),2)
   ranks.append({'company_name':company,'sample_count':len(rows),'hit_count':hits,'accuracy':round(acc,2),'avg_return_pct':round(avg,4),'score':score,'status':'正式排名' if len(rows)>=10 else '观察样本'})
  ranks.sort(key=lambda x:(x['score'],x['sample_count']),reverse=True)
  for i,x in enumerate(ranks,1): x['rank']=i
  (OUT/f'rankings_{h}d.json').write_text(json.dumps(ranks,ensure_ascii=False,indent=2))
 print('rankings written')
if __name__=='__main__': main()
