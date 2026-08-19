#!/usr/bin/env python3
"""Collect futures research reports from jiaoyikecha.com (交易可查).

This source provides 14+ brokerage firms' daily reports in a single API call,
complementing the existing direct-crawl collectors (CITIC, GTJA, Huatai, Nanhua).
"""
from __future__ import annotations
import json, re, time, requests
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'sector_reports'

JYKC_URL = "https://www.jiaoyikecha.com/ajax/report_list.php"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.jiaoyikecha.com/",
    "User-Agent": "Mozilla/5.0 (compatible; AA-Futures-Research-Ranking/0.2)",
}

SECTOR_KEYWORDS = {
    'agri': ['农产品','农产','玉米','豆粕','豆油','棕榈油','菜油','菜粕','白糖','棉花','鸡蛋','生猪','花生','苹果','红枣'],
    'metals': ['金属','有色','铜','铝','锌','铅','镍','锡','氧化铝','工业硅','碳酸锂','黄金','白银'],
    'energy': ['能源化工','能化','原油','燃料油','沥青','PTA','乙二醇','苯乙烯','聚乙烯','聚丙烯','PVC','甲醇','尿素','玻璃','纯碱','纸浆','橡胶'],
    'ferrous': ['黑色','建材','螺纹钢','热卷','铁矿石','焦煤','焦炭','硅铁','锰硅','不锈钢','线材'],
}

SECTOR_NAMES = {
    'agri': '农产', 'metals': '金属', 'energy': '能化',
    'ferrous': '黑色',
}

# 品种关键词映射（与现有项目对齐）
VARIETY_KEYWORDS = {
    'agri': {'豆粕':'M','菜粕':'RM','豆油':'Y','棕榈油':'P','菜油':'OI','玉米':'C','淀粉':'CS','白糖':'SR','棉花':'CF','鸡蛋':'JD','生猪':'LH','花生':'PK','苹果':'AP','红枣':'CJ'},
    'metals': {'铜':'CU','铝':'AL','锌':'ZN','铅':'PB','镍':'NI','锡':'SN','氧化铝':'AO','工业硅':'SI','碳酸锂':'LC','黄金':'AU','白银':'AG'},
    'energy': {'原油':'SC','燃料油':'FU','沥青':'BU','PTA':'TA','乙二醇':'EG','苯乙烯':'EB','聚乙烯':'L','聚丙烯':'PP','PVC':'V','甲醇':'MA','尿素':'UR','玻璃':'FG','纯碱':'SA','橡胶':'RU','纸浆':'SP'},
    'ferrous': {'螺纹钢':'RB','热卷':'HC','铁矿石':'I','焦煤':'JM','焦炭':'J','硅铁':'SF','锰硅':'SM','不锈钢':'SS','线材':'WR'},
}

def classify_sectors(title, report_type):
    """根据标题和类型分类板块"""
    text = f"{title} {report_type}"
    sectors = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                sectors.append(sector)
                break
    return sectors if sectors else ['other']

def extract_varieties(title, sector):
    """提取品种"""
    varieties = []
    for kw, code in VARIETY_KEYWORDS.get(sector, {}).items():
        if kw in title:
            varieties.append({'name': kw, 'code': code})
    return varieties

def collect_jykc():
    """从交易可查拉取研报列表"""
    print("[JYKC] 开始采集交易可查研报...")
    
    all_reports = []
    # 交易可查每次最多200条，覆盖最近3天
    try:
        resp = requests.post(JYKC_URL, headers=HEADERS, data="page=1&limit=200", timeout=15)
        data = resp.json()
        raw_reports = data.get('data', [])
        print(f"[JYKC] 拉取到 {len(raw_reports)} 条原始研报")
    except Exception as e:
        print(f"[JYKC] 拉取失败: {e}")
        return []
    
    for r in raw_reports:
        title = r.get('title', '').strip()
        broker = r.get('broker_name', '').strip()
        report_type = r.get('type', '').strip()
        report_date = r.get('report_date', '').strip()
        
        if not title or not broker:
            continue
        
        # 日期补全年份
        year = str(date.today().year)
        full_date = f"{year}-{report_date}" if report_date else ""
        
        sectors = classify_sectors(title, report_type)
        
        for sector in sectors:
            if sector == 'other':
                continue  # 跳过无法分类的
            
            varieties = extract_varieties(title, sector)
            
            all_reports.append({
                'company': broker,
                'rating_level': 'AA',
                'sector': sector,
                'sector_name': SECTOR_NAMES.get(sector, sector),
                'report_type': report_type or '未分类',
                'title': title,
                'publish_date': full_date,
                'author': '',
                'source_type': 'jykc',
                'source_url': 'https://www.jiaoyikecha.com/#/reports/ai',
                'detail_url': '',
                'pdf_url': '',
                'main_varieties': varieties,
                'matched_keywords': '、'.join(v['name'] for v in varieties),
                'collection_status': 'discovered',
            })
    
    print(f"[JYKC] 标准化后 {len(all_reports)} 条（含多板块拆分）")
    
    # 统计
    companies = defaultdict(int)
    for r in all_reports:
        companies[r['company']] += 1
    print(f"[JYKC] 覆盖 {len(companies)} 家期货公司:")
    for c, n in sorted(companies.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")
    
    return all_reports

def merge_with_existing(new_reports):
    """合并到现有数据"""
    existing_file = OUT / 'all.json'
    
    existing_reports = []
    existing_meta = {}
    if existing_file.exists():
        with open(existing_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    existing_reports = data.get('reports', [])
                    existing_meta = {k: v for k, v in data.items() if k != 'reports'}
                elif isinstance(data, list):
                    existing_reports = data
            except:
                existing_reports = []
    
    # 去重键: company + title + sector
    existing_keys = set()
    for r in existing_reports:
        if isinstance(r, dict):
            key = (r.get('company',''), r.get('title',''), r.get('sector',''))
            existing_keys.add(key)
    
    added = 0
    for r in new_reports:
        key = (r['company'], r['title'], r['sector'])
        if key not in existing_keys:
            existing_reports.append(r)
            existing_keys.add(key)
            added += 1
    
    # 保存（保留原有meta结构）
    OUT.mkdir(parents=True, exist_ok=True)
    merged_data = {
        'generated_at': str(date.today()),
        'window_start': existing_meta.get('window_start', str(date.today() - timedelta(days=90))),
        'report_count': len(existing_reports),
        'reports': existing_reports,
    }
    # 保留 wind_merge_note 等额外字段
    for k, v in existing_meta.items():
        if k not in merged_data:
            merged_data[k] = v
    
    with open(existing_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"[JYKC] 合并完成: 新增 {added} 条, 总计 {len(existing_reports)} 条")
    
    # 按板块保存
    by_sector = defaultdict(list)
    for r in existing_reports:
        if isinstance(r, dict):
            by_sector[r.get('sector','other')].append(r)
    
    for sector, rows in by_sector.items():
        sf = OUT / f'{sector}.json'
        with open(sf, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    
    # 更新公司统计
    stats_file = ROOT / 'data' / 'company_stats.json'
    company_stats = defaultdict(lambda: {'total': 0, 'sectors': set(), 'sources': set()})
    for r in existing_reports:
        if isinstance(r, dict):
            c = r.get('company', '')
            company_stats[c]['total'] += 1
            company_stats[c]['sectors'].add(r.get('sector', ''))
            company_stats[c]['sources'].add(r.get('source_type', ''))
    
    stats_list = []
    for c, s in sorted(company_stats.items()):
        stats_list.append({
            'company': c,
            'total_reports': s['total'],
            'sectors': sorted(list(s['sectors'])),
            'sources': sorted(list(s['sources'])),
        })
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_list, f, ensure_ascii=False, indent=2)
    
    print(f"[JYKC] 公司统计: {len(stats_list)} 家, 已保存到 company_stats.json")
    
    return added

if __name__ == '__main__':
    reports = collect_jykc()
    if reports:
        merge_with_existing(reports)
