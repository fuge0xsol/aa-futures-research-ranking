#!/usr/bin/env python3
"""One-pass public research report collector for the four major futures sectors."""
from __future__ import annotations
import json, re, time
from collections import defaultdict
from urllib.parse import urljoin
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote
import requests
try:
 from bs4 import BeautifulSoup
except ModuleNotFoundError:
 BeautifulSoup = None


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'sector_reports'
TODAY = date.today()
START = TODAY - timedelta(days=90)
HEADERS = {'User-Agent':'Mozilla/5.0 (compatible; AA-Futures-Research-Ranking/0.1)', 'Accept-Language':'zh-CN,zh;q=0.9'}
S = requests.Session(); S.headers.update(HEADERS)

SECTORS = {
 'agri': {'name':'农产','keywords': {'豆粕':'M','菜粕':'RM','豆油':'Y','棕榈油':'P','菜油':'OI','玉米':'C','淀粉':'CS','白糖':'SR','棉花':'CF','鸡蛋':'JD','生猪':'LH','花生':'PK','苹果':'AP','红枣':'CJ'}},
 'metals': {'name':'金属','keywords': {'铜':'CU','铝':'AL','锌':'ZN','铅':'PB','镍':'NI','锡':'SN','氧化铝':'AO','工业硅':'SI','碳酸锂':'LC','黄金':'AU','白银':'AG'}},
 'energy': {'name':'能化','keywords': {'原油':'SC','燃料油':'FU','低硫燃料油':'LU','沥青':'BU','PTA':'TA','乙二醇':'EG','苯乙烯':'EB','聚乙烯':'L','聚丙烯':'PP','PVC':'V','甲醇':'MA','尿素':'UR','玻璃':'FG','纯碱':'SA','橡胶':'RU','纸浆':'SP'}},
 'ferrous': {'name':'黑色','keywords': {'螺纹钢':'RB','热卷':'HC','铁矿石':'I','焦煤':'JM','焦炭':'J','硅铁':'SF','锰硅':'SM','不锈钢':'SS','线材':'WR'}},
}

def clean(s): return re.sub(r'\\s+', ' ', str(s or '')).strip()
def parse_date(s):
 m=re.search(r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})', str(s or ''))
 if not m: return ''
 try: return date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
 except ValueError: return ''
def sector_hits(text):
 out=[]
 for slug,cfg in SECTORS.items():
  for name,code in cfg['keywords'].items():
   if name.lower() in text.lower(): out.append((slug,name,code))
 return out

def normalize(company,title,publish,report_type,source_type,url,detail='',author='',summary=''):
 title=clean(title); text=f'{title} {summary}'
 hits=sector_hits(text)
 if not hits: return []
 # one record per sector, preserving only main varieties found in title/summary
 by=defaultdict(list)
 for slug,name,code in hits: by[slug].append({'name':name,'code':code})
 rows=[]
 for slug, varieties in by.items():
  seen=[]
  for x in varieties:
   if x not in seen: seen.append(x)
  rows.append({'company':company,'rating_level':'AA','sector':slug,'sector_name':SECTORS[slug]['name'],'report_type':report_type or '未分类','title':title,'publish_date':parse_date(publish),'author':clean(author),'source_type':source_type,'source_url':url,'detail_url':detail or url,'pdf_url':'','main_varieties':seen,'matched_keywords':'、'.join(x['name'] for x in seen),'collection_status':'discovered'})
 return rows

def collect_citic():
 rows=[]; url='https://inst.citicsf.com/icsp-data-provider/api/t0/reportsQuery'
 for page in range(1,8):
  payload={'pageNum':page,'pageSize':100,'reportTypes':['normal','vip']}
  try:
   r=S.post(url,json=payload,headers={'Referer':'https://inst.citicsf.com/research-report/researchReportQuery','Origin':'https://inst.citicsf.com','Content-Type':'application/json'},timeout=30); data=r.json()
  except Exception as e: print('CITIC page error',page,e); break
  items=data.get('data',data)
  if isinstance(items,dict): items=items.get('list',items.get('records',[]))
  if not isinstance(items,list) or not items: break
  for x in items:
   pub=x.get('rptDate') or x.get('publishDate'); title=x.get('rptAllTitle') or x.get('title'); summary=x.get('rptSummary')
   d=parse_date(pub)
   if d and d < START.isoformat(): continue
   rows += normalize('中信期货',title,pub,x.get('catName') or ({1003:'日报',1009:'周报'}.get(x.get('catId'))), '官方', 'https://inst.citicsf.com/research-report/researchReportQuery', f'https://inst.citicsf.com/research-report/researchReportQueryDetail?researchId={x.get("id","")}', summary=summary)
  time.sleep(.2)
 return rows

def collect_gtja():
 rows=[]
 for slug,cfg in SECTORS.items():
  cat={'agri':'农林产品','metals':'有色金属','energy':'能源化工','ferrous':'黑色金属'}[slug]
  for page in range(1,4):
   url=f'https://www.gtjaqh.com/pc/report?page={page}&catType={quote(cat)}'
   try: html=S.get(url,timeout=30).text; node=re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S)
   except Exception as e: print('GTJA error',cat,page,e); break
   if not node: break
   try: obj=json.loads(node.group(1)); items=obj['props']['pageProps'].get('TYBREPORT',[])
   except Exception: break
   if isinstance(items,dict): items=items.get('data',items.get('list',[]))
   for x in items or []:
    title=x.get('title') or x.get('name'); pub=x.get('time') or x.get('publishTime'); rid=x.get('id','')
    d=parse_date(pub)
    if d and d < START.isoformat(): continue
    # category page is a sector assertion; keyword filter still limits to major varieties
    rows += normalize('国泰君安期货',title,pub,x.get('imagetxt') or ({'102413':'日报','102414':'周报','104663':'合集'}.get(str(x.get('reporttype')))), '官方',url,f'https://www.gtjaqh.com/pc/reportDetail/{rid}',x.get('authors'),x.get('imagetxt',''))
   if not items: break
   time.sleep(.2)
 return rows

def collect_huatai():
 rows=[]; url='https://www.htfc.com/servlet/json'
 for page in range(1,8):
  try:
   r=S.post(url,data={'funcNo':'944351','catalogId':'11452','pageNum':page,'pageSize':100},timeout=30); obj=r.json()
  except Exception as e: print('HUATAI page error',page,e); break
  items=obj if isinstance(obj,list) else obj.get('data',obj.get('list',obj.get('rows',[])))
  if isinstance(items,dict): items=items.get('list',items.get('rows',[]))
  if not items: break
  for x in items:
   title=x.get('title') or x.get('article_title'); pub=x.get('publish_date') or x.get('create_date'); link=x.get('link_url') or url
   d=parse_date(pub)
   if d and d < START.isoformat(): continue
   rows += normalize('华泰期货',title,pub,x.get('report_type') or x.get('type') or '研究资讯','官方','https://www.htfc.com/main/yjzx/zxzx/htqh_yzx/index.shtml?id=10031',link,x.get('author'))
  time.sleep(.2)
 return rows

def collect_nanhua():
 """南华期货公开研报接口：日报、周报、专题报告。"""
 rows=[]
 base='https://mall.nanhua.net/mall/nh/api'
 page_url='https://mall.nanhua.net/mall/r/w/reportNew/report-list.html'
 headers={'Referer':page_url,'Origin':'https://mall.nanhua.net','Content-Type':'application/json'}
 # 以公开农产品分类为主；其余板块使用同一接口的分类代码。
 categories={'agri':['DAY_agri','WEEK_agri','PRO_agri','HOT_agri'],
             'metals':['DAY_nonfe','WEEK_nonfe','PRO_nonfe','HOT_nonfe'],
             'energy':['DAY_enchem','WEEK_enchem','PRO_enchem','HOT_enchem'],
             'ferrous':['DAY_black','WEEK_black','PRO_black','HOT_black']}
 type_names={'DAY':'日报','WEEK':'周报','PRO':'专题报告','HOT':'热点报告'}
 for slug,codes in categories.items():
  for code in codes:
   type1,_,suffix=code.partition('_')
   for page in range(1,6):
    try:
     r=S.post(f'{base}/report/getPage.json',json={'type1Code':type1,'type2Code':code,'pageNo':page,'pageSize':100},headers=headers,timeout=30)
     obj=r.json(); data=obj.get('data') or {}; items=data.get('result') or []
    except Exception as e:
     print('NANHUA error',code,page,e); break
    if not items: break
    for x in items:
     title=x.get('title') or x.get('fileName','')
     pub=x.get('date') or x.get('createTime') or x.get('updateTime')
     d=parse_date(pub)
     if d and d < START.isoformat(): continue
     detail=x.get('detailUrl') or f"https://mall.nanhua.net/mall/r/w/reportNew/report-list-page.html?id={x.get('id','')}"
     rows += normalize('南华期货',title,pub,type_names.get(type1,type1),'官方',page_url,detail,x.get('personName') or x.get('person',''))
    if len(items)<100: break
    time.sleep(.1)
 return rows


def dedup(rows):
 seen=set(); out=[]
 for r in rows:
  key=(r['company'],r['sector'],r['title'],r['publish_date'])
  if key in seen: continue
  seen.add(key); out.append(r)
 return sorted(out,key=lambda x:(x['sector'],x['publish_date'],x['company']),reverse=True)

def main():
 print(f'window={START}..{TODAY}')
 all_rows=[]
 for fn in (collect_citic,collect_gtja,collect_huatai,collect_nanhua):
  before=len(all_rows); got=fn(); all_rows += got; print(fn.__name__,len(got),'rows')
 all_rows=dedup(all_rows)
 OUT.mkdir(parents=True,exist_ok=True)
 for slug,cfg in SECTORS.items():
  data=[x for x in all_rows if x['sector']==slug]
  payload={'sector':slug,'sector_name':cfg['name'],'generated_at':TODAY.isoformat(),'window_start':START.isoformat(),'report_count':len(data),'company_count':len(set(x['company'] for x in data)),'reports':data,'note':'仅采集标题/摘要中命中的主要期货品种；未命中品种的板块研报不纳入本轮数据。'}
  (OUT/f'{slug}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
  print(slug,cfg['name'],len(data),payload['company_count'])
 (OUT/'all.json').write_text(json.dumps({'generated_at':TODAY.isoformat(),'window_start':START.isoformat(),'report_count':len(all_rows),'reports':all_rows},ensure_ascii=False,indent=2))
 print('TOTAL',len(all_rows))
if __name__=='__main__': main()
