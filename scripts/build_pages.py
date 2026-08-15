#!/usr/bin/env python3
"""
build_pages.py — 从最新 JSON 数据重新生成板块 HTML 页面的内联 window.SECTION 数据。
在 cron 管道中，采集 + 回测之后、git push 之前执行。
"""
import json, os, re, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
BT_DIR = DATA / 'backtest'
SECTORS = {
    'agri':   {'name': '农产', 'cn': '农产', 'code': '01'},
    'metals': {'name': '金属', 'cn': '金属', 'code': '02'},
    'energy': {'name': '能化', 'cn': '能化', 'code': '03'},
    'ferrous': {'name': '黑色', 'cn': '黑色', 'code': '04'},
}

def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def compute_rankings(bt_records, min_samples_formal=10):
    """从回测记录计算机构排名"""
    from collections import defaultdict
    by_company = defaultdict(list)
    for r in bt_records:
        by_company[r['company']].append(r)
    
    rankings = []
    for company, recs in by_company.items():
        hits = sum(1 for r in recs if r.get('hit'))
        samples = len(recs)
        avg_return = sum(float(r.get('strategy_return_pct', 0)) for r in recs) / samples if samples else 0
        accuracy = hits / samples * 100 if samples else 0
        # 评分: 准确率 * 0.6 + 正收益加权 * 0.4, 样本数加权
        score = accuracy * 0.5 + max(0, avg_return + 5) * 3 + min(samples, 30) * 0.5
        rankings.append({
            'company_name': company,
            'sample_count': samples,
            'hit_count': hits,
            'accuracy': round(accuracy, 2),
            'avg_return_pct': round(avg_return, 4),
            'score': round(score, 2),
            'status': '正式排名' if samples >= min_samples_formal else '观察样本',
        })
    
    rankings.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1
    return rankings

def compute_commodity_ranking(bt_records):
    """品种页排名：按准确率降序，样本数次之；附多空观点数"""
    from collections import defaultdict
    by_company = defaultdict(list)
    for r in bt_records:
        by_company[r['company']].append(r)
    rankings = []
    for company, recs in by_company.items():
        hits = sum(1 for r in recs if r.get('hit'))
        samples = len(recs)
        bull = sum(1 for r in recs if r.get('direction') == 'bullish')
        bear = sum(1 for r in recs if r.get('direction') == 'bearish')
        avg_return = sum(float(r.get('strategy_return_pct', 0)) for r in recs) / samples if samples else 0
        accuracy = hits / samples * 100 if samples else 0
        rankings.append({
            'company_name': company,
            'sample_count': samples,
            'hit_count': hits,
            'accuracy': round(accuracy, 2),
            'avg_return_pct': round(avg_return, 4),
            'bull_count': bull,
            'bear_count': bear,
        })
    rankings.sort(key=lambda x: (x['accuracy'], x['sample_count']), reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1
    return rankings

def build_commodity_pages(sector, sector_config):
    """为板块内每个品种生成独立详情页 {sector}/{CODE}.html"""
    from collections import defaultdict
    sector_dir = BASE / sector
    template_path = BASE / 'commodity-template.html'
    if not template_path.exists():
        print(f'  [WARN] commodity-template.html not found')
        return 0
    
    all_bt = load_json(BT_DIR / 'backtest_records.json') or []
    sector_bt = [r for r in all_bt if r.get('sector') == sector and r.get('status') == 'valid' and r.get('horizon_days') == 1]
    reports = load_json(DATA / 'sector_reports' / f'{sector}.json') or []
    template = template_path.read_text(encoding='utf-8')
    
    # 按品种代码分组
    by_commodity = defaultdict(list)
    for r in sector_bt:
        code = r.get('commodity')
        if code:
            by_commodity[code].append(r)
    
    generated = 0
    existing_pages = set(p.name for p in sector_dir.glob('*.html')) - {'index.html'}
    for code, recs in sorted(by_commodity.items()):
        name = recs[0].get('commodity_name') or code
        # 匹配研报：品种名出现在 matched_keywords 或 commodity_name
        com_reports = [r for r in reports if name in str(r.get('matched_keywords', '')) or r.get('commodity_name') == name]
        ranking = compute_commodity_ranking(recs)
        com_data = {
            'commodity': code,
            'commodity_name': name,
            'sector': sector,
            'sector_name': sector_config['cn'],
            'backtests': sorted(recs, key=lambda x: x.get('exit_date', '')),
            'ranking': ranking,
            'reports': com_reports,
            'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        page = (template
                .replace('__COMMODITY_NAME__', name)
                .replace('__COMMODITY__', code)
                .replace('__SECTOR_NAME__', sector_config['cn'])
                .replace('__SECTOR__', sector)
                .replace('__COMMODITY_DATA__', json.dumps(com_data, ensure_ascii=False)))
        out = sector_dir / f'{code}.html'
        out.write_text(page, encoding='utf-8')
        existing_pages.discard(f'{code}.html')
        generated += 1
        print(f'  [OK] {sector}/{code}.html — {name}: {len(recs)} 回测, {len(ranking)} 机构, {len(com_reports)} 研报')
    
    # 清理已无数据的品种页
    for stale in existing_pages:
        (sector_dir / stale).unlink()
        print(f'  [CLEAN] removed stale {sector}/{stale}')
    return generated


def build_sector_page(sector, config):
    """为一个板块构建 window.SECTION JSON 并注入 HTML"""
    sector_dir = BASE / sector
    html_path = sector_dir / 'index.html'
    if not html_path.exists():
        print(f'  [SKIP] {sector}/index.html not found')
        return False
    
    # 加载数据
    reports = load_json(DATA / 'sector_reports' / f'{sector}.json') or []
    all_bt = load_json(BT_DIR / 'backtest_records.json') or []
    sector_bt = [r for r in all_bt if r.get('sector') == sector]
    
    # 计算排名
    rankings = compute_rankings(sector_bt)
    
    # 统计
    companies = set(r.get('company', '') for r in reports)
    dates = sorted(set(r.get('publish_date', '') for r in reports if r.get('publish_date')), reverse=True)
    latest_date = dates[0] if dates else ''
    
    section_data = {
        'reports': reports,
        'backtests': sector_bt,
        'rankings': rankings,
        'companyCount': len(companies),
        'reportCount': len(reports),
        'latestDate': latest_date,
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    
    # 读取 HTML，替换 window.SECTION
    html = html_path.read_text(encoding='utf-8')
    section_json = json.dumps(section_data, ensure_ascii=False)
    
    # 匹配 window.SECTION={...};
    pattern = r'window\.SECTION\s*=\s*\{.*?\};\s*</script>'
    replacement = f'window.SECTION={section_json};</script>'
    
    new_html, count = re.subn(pattern, replacement, html, flags=re.S)
    if count == 0:
        print(f'  [WARN] {sector}: window.SECTION pattern not found, skipping')
        return False
    
    html_path.write_text(new_html, encoding='utf-8')
    print(f'  [OK] {sector}: {len(reports)} reports, {len(sector_bt)} backtests, {len(rankings)} rankings, latest={latest_date}')
    return True

def main():
    print(f'=== build_pages.py @ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===')
    updated = 0
    for sector, config in SECTORS.items():
        if build_sector_page(sector, config):
            updated += 1
        build_commodity_pages(sector, config)
    print(f'=== Done: {updated}/{len(SECTORS)} pages updated ===')

if __name__ == '__main__':
    main()
