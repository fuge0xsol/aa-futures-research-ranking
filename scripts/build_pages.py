#!/usr/bin/env python3
"""
build_pages.py — 从最新 JSON 数据重建站点：
  1. 每个板块生成 {sector}/index.html（纯静态模板）+ {sector}/data.json（精简字段，前端异步加载）
  2. 每个品种生成 {sector}/{CODE}.html + {sector}/{CODE}.json
  3. 研报↔回测在构建期预 join（bh/br 字段），前端不再做标题子串匹配
  4. 同步生成 sitemap.xml 与 CNAME
在 cron 管道中，采集 + 回测之后、git push 之前执行。
"""
import json, os, re, sys
from pathlib import Path
from datetime import datetime, date

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
BT_DIR = DATA / 'backtest'
SITE_URL = 'https://yanbao.de'

SECTORS = {
    'agri': {
        'name': '农产', 'cn': '农产', 'code': '01', 'cls': '',
        'desc': '油脂油料、谷物、软商品与畜牧产品研报库，优先覆盖 AA 期货公司公开日报、周报。',
        'state': '已接入公开农产品研报发现数据',
    },
    'metals': {
        'name': '金属', 'cn': '金属', 'code': '02', 'cls': 'metals',
        'desc': '有色金属与贵金属研究报告、观点跟踪及历史回测排名。',
        'state': '已完成首轮公开研报采集',
    },
    'energy': {
        'name': '能化', 'cn': '能化', 'code': '03', 'cls': 'energy',
        'desc': '原油、燃料、化工与能源化工品种研究报告、观点跟踪及历史回测排名。',
        'state': '已完成首轮公开研报采集',
    },
    'ferrous': {
        'name': '黑色', 'cn': '黑色', 'code': '04', 'cls': 'ferrous',
        'desc': '钢材、铁矿、焦煤焦炭与建材品种研究报告、观点跟踪及历史回测排名。',
        'state': '已完成首轮公开研报采集',
    },
}
NOTE = '回测结果基于已接入的历史研报与行情数据；样本不足时仅供观察。'


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def trim_report(r):
    """研报字段裁剪：只保留前端实际使用的字段，matched_keywords 拆成数组 kw"""
    detail_url = r.get('detail_url')
    if not detail_url and r.get('source_type') == 'jykc':
        # JYKC API 不提供单篇直链，退回来源聚合页（交易可查研报频道），保证标题可点击
        detail_url = r.get('source_url')
    out = {
        'company': r.get('company'),
        'report_type': r.get('report_type'),
        'title': r.get('title'),
        'publish_date': r.get('publish_date'),
        'detail_url': detail_url,
        'source_type': r.get('source_type'),
        'cn': r.get('commodity_name'),
        'kw': [k.strip() for k in re.split(r'[、,， ]', str(r.get('matched_keywords') or '')) if k.strip()],
        'dir': r.get('direction'),
        'dcn': r.get('direction_cn'),
        'dsrc': r.get('direction_source'),
    }
    return out


def trim_bt(r):
    """回测字段裁剪（仅保留 valid + 1D，由构建期过滤）"""
    return {
        'co': r.get('company'),
        'code': r.get('commodity'),
        'cn': r.get('commodity_name'),
        'dir': r.get('direction'),
        'dcn': r.get('direction_cn'),
        'exd': r.get('exit_date'),
        'ep': r.get('entry_price'),
        'xp': r.get('exit_price'),
        'ret': r.get('strategy_return_pct'),
        'hit': r.get('hit'),
    }


def attach_backtest_result(report, bt_rows):
    """构建期 join：company 精确匹配 + report_id 包含研报标题。写入 bh(命中) / br(策略收益)；
    未匹配则不写字段，前端显示「未回测」。"""
    title = str(report.get('title') or '')
    if not title:
        return
    for b in bt_rows:
        rid = str(b.get('report_id') or '')
        if b.get('company') == report.get('company') and title in rid:
            report['bh'] = b.get('hit')
            report['br'] = b.get('strategy_return_pct')
            return


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


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


# ---------------------------------------------------------------------------
# sitemap / CNAME
# ---------------------------------------------------------------------------

def write_sitemap(urls):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lastmod = date.today().isoformat()
    for u in urls:
        lines.append(f'  <url><loc>{SITE_URL}/{u}</loc><lastmod>{lastmod}</lastmod></url>')
    lines.append('</urlset>')
    (BASE / 'sitemap.xml').write_text('\n'.join(lines), encoding='utf-8')
    print(f'  [OK] sitemap.xml — {len(urls)} urls')


def ensure_cname():
    cname = BASE / 'CNAME'
    if not cname.exists():
        cname.write_text('yanbao.de\n', encoding='utf-8')
        print('  [OK] CNAME written (yanbao.de)')


# ---------------------------------------------------------------------------
# 板块页
# ---------------------------------------------------------------------------

def build_sector_page(sector, config):
    """生成 {sector}/index.html（静态模板）+ {sector}/data.json（异步数据）"""
    sector_dir = BASE / sector
    html_path = sector_dir / 'index.html'
    template_path = BASE / 'section-template.html'
    if not html_path.exists() or not template_path.exists():
        print(f'  [SKIP] {sector}: index.html or template missing')
        return False

    reports_raw = load_json(DATA / 'sector_reports' / f'{sector}.json') or []
    all_bt = load_json(BT_DIR / 'backtest_records.json') or []
    sector_bt = [r for r in all_bt if r.get('sector') == sector and r.get('status') == 'valid' and r.get('horizon_days') == 1]

    rankings = compute_rankings(sector_bt)

    companies = set(r.get('company', '') for r in reports_raw)
    dates = sorted(set(r.get('publish_date', '') for r in reports_raw if r.get('publish_date')), reverse=True)
    latest_date = dates[0] if dates else ''

    # 精简研报 + 构建 join
    reports = []
    for r in reports_raw:
        t = trim_report(r)
        attach_backtest_result(t, sector_bt)
        reports.append(t)

    section_data = {
        'reports': reports,
        'backtests': [trim_bt(r) for r in sector_bt],
        'rankings': rankings,
        'companyCount': len(companies),
        'reportCount': len(reports_raw),
        'latestDate': latest_date,
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    (sector_dir / 'data.json').write_text(dump(section_data), encoding='utf-8')

    actives = {s.upper() + '_ACTIVE': ('active' if s == sector else '') for s in SECTORS}
    page = (template_path.read_text(encoding='utf-8')
            .replace('{{TITLE}}', config['cn'])
            .replace('{{DESC}}', config['desc'])
            .replace('{{STATE}}', config['state'])
            .replace('{{NOTE}}', NOTE)
            .replace('{{CLASS}}', config['cls'])
            .replace('{{CODE}}', config['code'])
            .replace('{{CANONICAL}}', f'{SITE_URL}/{sector}/')
            .replace('{{ROOT}}', '../')
            .replace('{{DATA_URL}}', 'data.json'))
    for k, v in actives.items():
        page = page.replace('{{' + k + '}}', v)
    # 清理未替换的占位符，防止遗留
    page = re.sub(r'\{\{[A-Z_]+\}\}', '', page)
    html_path.write_text(page, encoding='utf-8')

    kb = (sector_dir / 'data.json').stat().st_size / 1024
    print(f'  [OK] {sector}: {len(reports_raw)} reports, {len(sector_bt)} backtests, {len(rankings)} rankings, data.json={kb:.0f}KB, latest={latest_date}')
    return True


# ---------------------------------------------------------------------------
# 品种页
# ---------------------------------------------------------------------------

def build_commodity_pages(sector, sector_config):
    """为板块内每个品种生成 {sector}/{CODE}.html + {sector}/{CODE}.json"""
    from collections import defaultdict
    sector_dir = BASE / sector
    template_path = BASE / 'commodity-template.html'
    if not template_path.exists():
        print('  [WARN] commodity-template.html not found')
        return 0

    all_bt = load_json(BT_DIR / 'backtest_records.json') or []
    sector_bt = [r for r in all_bt if r.get('sector') == sector and r.get('status') == 'valid' and r.get('horizon_days') == 1]
    reports_raw = load_json(DATA / 'sector_reports' / f'{sector}.json') or []
    template = template_path.read_text(encoding='utf-8')

    by_commodity = defaultdict(list)
    for r in sector_bt:
        code = r.get('commodity')
        if code:
            by_commodity[code].append(r)

    generated = 0
    keep_html = {'index.html'}
    keep_json = {'data.json'}
    for code, recs in sorted(by_commodity.items()):
        name = recs[0].get('commodity_name') or code
        com_reports_raw = [r for r in reports_raw
                           if r.get('commodity_name') == name or name in str(r.get('matched_keywords') or '')]
        com_reports = []
        for r in com_reports_raw:
            t = trim_report(r)
            attach_backtest_result(t, recs)
            com_reports.append(t)

        ranking = compute_commodity_ranking(recs)
        com_data = {
            'code': code,
            'name': name,
            'sector': sector,
            'sectorName': sector_config['cn'],
            'backtests': [trim_bt(r) for r in sorted(recs, key=lambda x: x.get('exit_date', ''))],
            'ranking': ranking,
            'reports': com_reports,
            'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        (sector_dir / f'{code}.json').write_text(dump(com_data), encoding='utf-8')

        page = (template
                .replace('__COMMODITY_NAME__', name)
                .replace('__COMMODITY__', code)
                .replace('__SECTOR_NAME__', sector_config['cn'])
                .replace('__SECTOR__', sector))
        (sector_dir / f'{code}.html').write_text(page, encoding='utf-8')
        keep_html.add(f'{code}.html')
        keep_json.add(f'{code}.json')
        generated += 1
        print(f'  [OK] {sector}/{code}.html — {name}: {len(recs)} 回测, {len(ranking)} 机构, {len(com_reports)} 研报')

    # 清理已无数据的品种页与孤儿 json
    for p in sector_dir.glob('*.html'):
        if p.name not in keep_html:
            p.unlink()
            print(f'  [CLEAN] removed stale {sector}/{p.name}')
    for p in sector_dir.glob('*.json'):
        if p.name not in keep_json:
            p.unlink()
            print(f'  [CLEAN] removed stale {sector}/{p.name}')
    return generated


def main():
    print(f'=== build_pages.py @ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===')
    updated = 0
    sitemap_urls = ['', ]
    for sector, config in SECTORS.items():
        if build_sector_page(sector, config):
            updated += 1
        build_commodity_pages(sector, config)
        sitemap_urls.append(f'{sector}/')
        for p in sorted((BASE / sector).glob('*.html')):
            if p.name != 'index.html':
                sitemap_urls.append(f'{sector}/{p.name}')
    write_sitemap(sitemap_urls)
    ensure_cname()
    print(f'=== Done: {updated}/{len(SECTORS)} pages updated ===')


if __name__ == '__main__':
    main()
