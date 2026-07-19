#!/usr/bin/env python3
"""Merge only source-confirmed Wind financial-document hits into sector report JSON.

This is intentionally an allowlist generated from a prior manual quality test.
It does not treat a Wind search hit as source-confirmed unless the title/content
contains the named futures company or its known research-brand marker.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sector_reports"
TODAY = date.today().isoformat()
WIND_URL = "https://aifinmarket.wind.com.cn/"

# Confirmed in the test pass: company name appears in title/content, or the
# title uses a company-specific research brand (e.g. 银河农产品策略).
CONFIRMED = [
    {"company":"中信期货", "title":"中信期货2026年中策略会成功举办", "publish_date":"2026-07-03", "summary":"农业分会议：气候再起波澜，农业布局机遇。报告内容聚焦天气、棕榈油、天然橡胶、白糖、棉花、玉米和生猪等农产品市场逻辑。", "report_type":"Wind检索文档", "author":"", "varieties":[("棕榈油","P"),("白糖","SR"),("棉花","CF"),("玉米","C"),("生猪","LH")]},
    {"company":"中信期货", "title":"玉米每日简报2026年6月18日", "publish_date":"2026-06-18", "summary":"来源内容明确标注中信期货，主题为国内玉米市场供需与期货行情。", "report_type":"日报", "author":"", "varieties":[("玉米","C")]},
    {"company":"华泰期货", "title":"定向稻谷拍卖启动 短期预计玉米期货弱势震荡运行", "publish_date":"2026-06-04", "summary":"来源：华泰期货。内容包含玉米及玉米淀粉期货行情、现货和基差数据。", "report_type":"日报", "author":"", "varieties":[("玉米","C"),("淀粉","CS")]},
    {"company":"华泰期货", "title":"端午备货提振作用有限 短期内生猪易承压运行", "publish_date":"2026-06-16", "summary":"来源：华泰期货。内容包含生猪期货行情、现货和基差数据。", "report_type":"日报", "author":"", "varieties":[("生猪","LH")]},
    {"company":"华泰期货", "title":"华泰期货：生猪后续看供给，短期延磨底", "publish_date":"2026-06-26", "summary":"来源：华泰期货；作者薛钧元。内容为生猪期货观点及现货、基差数据。", "report_type":"日报", "author":"薛钧元", "varieties":[("生猪","LH")]},
    {"company":"华泰期货", "title":"华泰期货：预期变动有限，生猪价格维稳运行", "publish_date":"2026-05-22", "summary":"来源：华泰期货；作者薛钧元。内容为生猪期货观点及现货、基差数据。", "report_type":"日报", "author":"薛钧元", "varieties":[("生猪","LH")]},
    {"company":"南华期货", "title":"南华期货2026夏季策略会：农产品多品种机遇浮现", "publish_date":"2026-07-10", "summary":"内容明确标注南华期货，主题覆盖油脂油料、白糖、软商品和谷物等农产品品种及下半年策略。", "report_type":"策略会", "author":"", "varieties":[("豆粕","M"),("豆油","Y"),("棕榈油","P"),("白糖","SR"),("玉米","C")]},
    {"company":"银河期货", "title":"【银河期货期市早餐0708】玉米多重底部支撑逐步显现", "publish_date":"2026-07-08", "summary":"内容明确标注银河期货及分析师信息，主题为玉米期货供需、库存、资金和气候因素。", "report_type":"日报", "author":"高波", "varieties":[("玉米","C")]},
    {"company":"中粮期货", "title":"玉米：基差修复", "publish_date":"2026-06-10", "summary":"来源：中粮期货研究中心。内容为玉米期货基差、供应冲击和后续基差修复。", "report_type":"专题报告", "author":"", "varieties":[("玉米","C")]},
    {"company":"中粮期货", "title":"【市场聚焦】玉米：基差修复", "publish_date":"2026-06-10", "summary":"内容明确标注中粮期货研究中心，主题为玉米期货基差修复。", "report_type":"专题报告", "author":"", "varieties":[("玉米","C")]},
]

SECTOR_NAMES = {"agri":"农产", "metals":"金属", "energy":"能化", "ferrous":"黑色"}

def make_rows(item):
    rows=[]
    for name, code in item["varieties"]:
        sector = "agri" if code in {"M","RM","Y","P","OI","C","CS","SR","CF","JD","LH","PK","AP","CJ"} else "energy"
        rows.append({
            "company": item["company"], "rating_level":"AA", "sector":sector,
            "sector_name":SECTOR_NAMES[sector], "report_type":item["report_type"],
            "title":item["title"], "publish_date":item["publish_date"], "author":item["author"],
            "source_type":"Wind金融数据服务", "source_url":WIND_URL, "detail_url":"",
            "pdf_url":"", "summary":item["summary"],
            "main_varieties":[{"name":name,"code":code}], "matched_keywords":name,
            "collection_status":"wind_source_confirmed"
        })
    return rows

def main():
    additions=[]
    for item in CONFIRMED:
        additions.extend(make_rows(item))
    for path in sorted(OUT.glob("*.json")):
        if path.name == "all.json":
            continue
        payload=json.loads(path.read_text())
        existing=payload.get("reports",[])
        seen={(r.get("company"),r.get("sector"),r.get("title"),r.get("publish_date"),tuple((v.get("code"),v.get("name")) for v in r.get("main_varieties",[]))) for r in existing}
        for row in additions:
            if row["sector"] != payload.get("sector"):
                continue
            key=(row["company"],row["sector"],row["title"],row["publish_date"],tuple((v["code"],v["name"]) for v in row["main_varieties"]))
            if key not in seen:
                existing.append(row); seen.add(key)
        existing.sort(key=lambda r:(r.get("publish_date", ""),r.get("company", ""),r.get("title", "")), reverse=True)
        payload["reports"]=existing; payload["report_count"]=len(existing); payload["company_count"]=len({r.get("company") for r in existing})
        payload["wind_merge_note"]="仅合并前置质量测试中确认来源的 Wind 文档；Wind 搜索结果不等同于原始研报官方链接。"
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    all_rows=[]
    for path in sorted(OUT.glob("*.json")):
        if path.name != "all.json": all_rows.extend(json.loads(path.read_text()).get("reports",[]))
    (OUT/"all.json").write_text(json.dumps({"generated_at":TODAY,"report_count":len(all_rows),"reports":all_rows},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"wind_candidates":len(CONFIRMED),"rows_added":len(additions),"total_rows":len(all_rows)},ensure_ascii=False))

if __name__ == "__main__": main()
