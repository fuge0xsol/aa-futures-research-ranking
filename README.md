# AA期货研报回测榜

独立发布的 GitHub Pages 静态网站，用于展示 AA 期货公司农产品研报线索、结构化观点和历史回测排名。

## 当前状态

当前仓库是网站 MVP：已包含研报数据、总体/周度/月度/品种榜单和筛选页面。现有部分榜单仍属于原型数据，正式排名前需要继续完善观点提取、行情回测和样本量门槛。

## 本地预览

```bash
python -m http.server 8080
```

打开：<http://localhost:8080>

## GitHub Pages 部署

1. 在 GitHub 新建一个空仓库，例如 `aa-futures-research-ranking`。
2. 绑定远程仓库：

```bash
git remote add origin git@github.com:fuge0xsol/aa-futures-research-ranking.git
git push -u origin main
```

3. 仓库进入 **Settings → Pages → Build and deployment**。
4. Source 选择 **GitHub Actions**。
5. 推送后，工作流会自动部署静态网站。

预计地址：

```text
https://fuge0xsol.github.io/aa-futures-research-ranking/
```

## 数据目录

- `data/raw_reports.json`：研报原始发现数据
- `data/reports.json`：研报列表数据
- `data/rankings_overall.json`：总体榜单
- `data/rankings_weekly.json`：周度榜单
- `data/rankings_monthly.json`：月度榜单
- `data/rankings_by_commodity.json`：品种榜单
- `data/site_meta.json`：站点元数据

## 注意

- 网站只展示结构化信息和统计结果，不转载研报全文。
- 第三方检索线索必须在正式排名前完成来源核验。
- 样本量过少的机构不得宣传为具有统计意义的准确率排名。
- 内容仅用于投研辅助，不构成投资建议。
