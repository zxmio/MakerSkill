#!/usr/bin/env python3
"""
解析微信 / 支付宝账单，归类、去重、汇总，输出 analysis.json 和待归类清单。

用法：
  python3 analyze.py <账单文件或目录>... --out <输出目录> [--rules <rules.local.json>] [--from 2026-01] [--to 2026-10]

支持：
  微信：「微信支付账单流水文件」.xlsx（新版）或 .csv（旧版）
  支付宝：「支付宝交易明细」.csv（新版 GBK，表头含「交易分类」；旧版表头含「交易创建时间」）

只用 Python 标准库，账单只在本机处理，不联网。
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
RULES_FILE = HERE / "rules.json"

# ---------------------------------------------------------------- 读文件

def read_xlsx_rows(path):
    """标准库读 xlsx 第一张表，返回二维字符串列表。"""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        root = ET.fromstring(z.read(sheets[0]))
    rows = []
    for row in root.iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            for ch in re.sub(r"\d", "", ref):
                col = col * 26 + (ord(ch) - 64)
            t = c.get("t")
            v = c.find("m:v", ns)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            else:
                val = v.text if v is not None else ""
            cells[col - 1] = val or ""
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def read_csv_rows(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"{path} 编码无法识别")
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]


HEADER_KEYS = ("交易时间", "交易创建时间")

COLS = {
    "time": ("交易时间", "交易创建时间", "付款时间"),
    "type": ("交易类型", "交易分类", "类型"),
    "counterpart": ("交易对方",),
    "desc": ("商品", "商品说明", "商品名称"),
    "io": ("收/支",),
    "amount": ("金额(元)", "金额（元）", "金额"),
    "method": ("支付方式", "收/付款方式"),
    "status": ("当前状态", "交易状态"),
    "order": ("交易单号", "交易订单号", "交易号"),
    "note": ("备注",),
}


def load_file(path):
    path = Path(path)
    rows = read_xlsx_rows(path) if path.suffix.lower() == ".xlsx" else read_csv_rows(path)
    head_idx = next((i for i, r in enumerate(rows) if any(c.strip() in HEADER_KEYS for c in r)), None)
    if head_idx is None:
        raise ValueError(f"{path.name}：没找到表头（交易时间），不像微信或支付宝账单")
    preamble = " ".join(" ".join(r) for r in rows[:head_idx])
    header = [c.strip() for c in rows[head_idx]]
    idx = {}
    for key, names in COLS.items():
        for n in names:
            if n in header:
                idx[key] = header.index(n)
                break
    missing = [k for k in ("time", "io", "amount") if k not in idx]
    if missing:
        raise ValueError(f"{path.name}：缺少列 {missing}")
    if "微信" in preamble or "当前状态" in header or "交易单号" in header:
        platform = "wechat"
    else:
        platform = "alipay"
    out = []
    for r in rows[head_idx + 1:]:
        if len(r) <= idx["time"] or not r[idx["time"]].strip():
            continue  # 空行、表尾统计行
        if r[0].startswith("-") or r[0].startswith("—"):
            break  # 支付宝旧版表尾分割线
        rec = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
        rec["platform"] = platform
        rec["file"] = path.name
        out.append(rec)
    return platform, out


# ---------------------------------------------------------------- 清洗

def parse_time(s):
    s = s.strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):  # Excel 序列日期
        return datetime(1899, 12, 30) + timedelta(days=float(s))
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"无法识别的时间：{s}")


def parse_amount(s):
    s = re.sub(r"[¥￥,\s元]", "", s or "")
    try:
        return abs(float(s))
    except ValueError:
        return 0.0


def refunded_part(status):
    m = re.search(r"已退款[(（][¥￥]?([\d.,]+)[)）]", status or "")
    return parse_amount(m.group(1)) if m else 0.0


class Rules:
    def __init__(self, base, local):
        self.expense = base["expense_keywords"]
        self.income = base["income_keywords"]
        self.exclude = base["exclude_keywords"]
        self.alipay_map = base["alipay_category_map"]
        self.cats = base["categories"]
        self.local = local or {}

    def local_hit(self, text, counterpart, io):
        for k, v in self.local.get("merchants", {}).items():
            if k == counterpart or (len(k) >= 2 and k in text):
                return v
        for k, v in self.local.get("keywords", {}).items():
            if k in text:
                return v
        return None

    def classify(self, t):
        """返回 (kind, category)。kind ∈ expense / income / refund / excluded"""
        text = " ".join([t["counterpart"], t["desc"], t["type"], t["note"]])
        io_ = t["io"]
        status = t["status"]
        if any(x in status for x in ("交易关闭", "失败", "已全额退款", "对方已退还", "已撤销")):
            return "excluded", "closed"
        if io_ not in ("收入", "支出"):
            return "excluded", "internal"
        hit = self.local_hit(text, t["counterpart"], io_)
        if hit == "excluded":
            return "excluded", "manual"
        if any(k in text for k in self.exclude):
            return "excluded", "internal"
        if t["platform"] == "alipay" and self.alipay_map.get(t["type"]) == "excluded":
            return "excluded", "internal"
        if io_ == "收入" and ("退款" in t["type"] or "退款" in t["desc"] or t["type"] == "退款"):
            return "refund", hit if hit in self.cats["expense"] else self.guess_expense(text, t)
        if io_ == "收入":
            if hit in self.cats["income"]:
                return "income", hit
            for cat, kws in self.income.items():
                if any(k in text for k in kws):
                    return "income", cat
            return "income", "other_income"
        if hit in self.cats["expense"]:
            return "expense", hit
        return "expense", self.guess_expense(text, t)

    def guess_expense(self, text, t):
        for cat, kws in self.expense.items():
            if any(k.lower() in text.lower() for k in kws):
                return cat
        if t["platform"] == "alipay" and self.alipay_map.get(t["type"], "excluded") != "excluded":
            return self.alipay_map[t["type"]]
        if t["platform"] == "wechat" and ("转账" in t["type"] or "红包" in t["type"]):
            return "social"
        return "other"


# ---------------------------------------------------------------- 汇总

def norm_name(t):
    name = t["counterpart"].strip() or t["desc"].strip() or "未知"
    return re.sub(r"\s+", " ", name)[:40]


def main():
    ap = argparse.ArgumentParser(description="微信 / 支付宝账单分析")
    ap.add_argument("inputs", nargs="+", help="账单文件或所在目录")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--rules", help="本次专用的归类规则 rules.local.json")
    ap.add_argument("--from", dest="start", help="起始月份 YYYY-MM")
    ap.add_argument("--to", dest="end", help="结束月份 YYYY-MM")
    ap.add_argument("--name", default="", help="仪表盘标题里的称呼，如「轩铭」")
    args = ap.parse_args()

    base = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    local = json.loads(Path(args.rules).read_text(encoding="utf-8")) if args.rules else None
    rules = Rules(base, local)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for p in args.inputs:
        p = Path(p).expanduser()
        if p.is_dir():
            files += sorted(x for x in p.iterdir() if x.suffix.lower() in (".csv", ".xlsx") and not x.name.startswith("~$"))
        else:
            files.append(p)
    if not files:
        sys.exit("没有找到账单文件（.csv / .xlsx）")

    sources, txs, seen = [], [], set()
    for f in files:
        try:
            platform, recs = load_file(f)
        except ValueError as e:
            print(f"跳过 {e}", file=sys.stderr)
            continue
        kept = 0
        for r in recs:
            key = (r["platform"], r["order"]) if r.get("order") else (r["platform"], r["time"], r["amount"], r["counterpart"])
            if key in seen:
                continue
            seen.add(key)
            r["dt"] = parse_time(r["time"])
            r["amount_v"] = parse_amount(r["amount"]) - (refunded_part(r["status"]) if r["io"] == "支出" else 0)
            r.setdefault("type", "")
            r.setdefault("counterpart", "")
            r.setdefault("desc", "")
            r.setdefault("note", "")
            r.setdefault("status", "")
            r.setdefault("method", "")
            txs.append(r)
            kept += 1
        sources.append({"file": f.name, "platform": platform, "rows": len(recs), "kept": kept})

    if not txs:
        sys.exit("没有读到任何交易，确认文件是微信或支付宝导出的原始账单")
    if args.start:
        txs = [t for t in txs if t["dt"].strftime("%Y-%m") >= args.start]
    if args.end:
        txs = [t for t in txs if t["dt"].strftime("%Y-%m") <= args.end]
    txs.sort(key=lambda t: t["dt"])
    if not txs:
        sys.exit("筛选后没有交易")

    ecat = base["categories"]["expense"]
    icat = base["categories"]["income"]

    months = sorted({t["dt"].strftime("%Y-%m") for t in txs})
    m_income = defaultdict(float)
    m_expense = defaultdict(float)
    m_cat = defaultdict(lambda: defaultdict(float))
    cat_amt, cat_cnt = defaultdict(float), Counter()
    inc_amt, inc_cnt = defaultdict(float), Counter()
    merchants = defaultdict(lambda: {"amount": 0.0, "count": 0, "cats": Counter(), "months": defaultdict(list)})
    excluded = defaultdict(lambda: {"amount": 0.0, "count": 0})
    refunds = 0.0
    hours_amt, hours_cnt = [0.0] * 24, [0] * 24
    wd_amt = [0.0] * 7
    platform_amt = defaultdict(float)
    expenses = []
    unknown = defaultdict(lambda: {"amount": 0.0, "count": 0, "sample": ""})

    for t in txs:
        kind, cat = rules.classify(t)
        m = t["dt"].strftime("%Y-%m")
        v = round(t["amount_v"], 2)
        t["kind"], t["cat"] = kind, cat
        if kind == "excluded":
            excluded[cat]["amount"] += v
            excluded[cat]["count"] += 1
            continue
        if kind == "refund":
            m_expense[m] -= v
            m_cat[m][cat] -= v
            cat_amt[cat] -= v
            refunds += v
            continue
        if kind == "income":
            m_income[m] += v
            inc_amt[cat] += v
            inc_cnt[cat] += 1
            continue
        m_expense[m] += v
        m_cat[m][cat] += v
        cat_amt[cat] += v
        cat_cnt[cat] += 1
        hours_amt[t["dt"].hour] += v
        hours_cnt[t["dt"].hour] += 1
        wd_amt[t["dt"].weekday()] += v
        platform_amt[t["platform"]] += v
        name = norm_name(t)
        mm = merchants[name]
        mm["amount"] += v
        mm["count"] += 1
        mm["cats"][cat] += 1
        mm["months"][m].append(v)
        expenses.append(t)
        if cat == "other":
            u = unknown[name]
            u["amount"] += v
            u["count"] += 1
            u["sample"] = u["sample"] or f'{t["type"]} | {t["desc"]}'[:60]

    # 账单之外的收支（工资走银行卡、房贷等），写在 rules.local.json 的 manual 里
    manual_rows = []
    for e in (local or {}).get("manual", []):
        targets = months if e.get("month") in (None, "", "每月") else [e["month"]]
        for m in targets:
            if m not in months:
                continue
            v = float(e["amount"])
            cat = e.get("category") or ("other_income" if e.get("kind") == "income" else "other")
            if e.get("kind") == "income":
                m_income[m] += v
                inc_amt[cat] += v
                inc_cnt[cat] += 1
            else:
                m_expense[m] += v
                m_cat[m][cat] += v
                cat_amt[cat] += v
                cat_cnt[cat] += 1
            manual_rows.append({"month": m, "kind": e.get("kind", "expense"), "category": cat, "name": e.get("name", ""), "amount": v})

    total_in = sum(m_income.values())
    total_out = sum(m_expense.values())
    first, last = txs[0]["dt"], txs[-1]["dt"]
    days = max(1, (last.date() - first.date()).days + 1)

    # 固定订阅：同一商户、至少 3 个月出现、每月金额稳定
    subs = []
    for name, mm in merchants.items():
        if len(mm["months"]) < 3:
            continue
        top_cat = mm["cats"].most_common(1)[0][0]
        if top_cat in ("dining", "transport", "groceries", "shopping", "social"):
            continue
        per_month = [sum(v) for v in mm["months"].values()]
        mean = statistics.mean(per_month)
        if mean <= 0:
            continue
        cv = statistics.pstdev(per_month) / mean
        if cv <= 0.2:
            subs.append({"name": name, "category": top_cat, "months": len(per_month), "monthly": round(mean, 2), "yearly": round(mean * 12, 2)})
    subs.sort(key=lambda x: -x["monthly"])

    small_th = base.get("small_threshold", 30)
    small = [t for t in expenses if t["amount_v"] <= small_th]
    late = [t for t in expenses if t["dt"].hour >= 22 or t["dt"].hour < 5]
    weekend = [t for t in expenses if t["dt"].weekday() >= 5]
    n_weeks = max(1, days / 7)

    def cat_info(key, table):
        c = table.get(key, {"name": key, "color": "#C98BD9"})
        return c["name"], c["color"]

    expense_categories = []
    for k, v in sorted(cat_amt.items(), key=lambda x: -x[1]):
        if round(v, 2) <= 0:
            continue
        name, color = cat_info(k, ecat)
        expense_categories.append({"key": k, "name": name, "color": color, "amount": round(v, 2), "count": cat_cnt[k], "share": round(v / total_out, 4) if total_out else 0,
                                   "monthly": [round(m_cat[m].get(k, 0), 2) for m in months]})
    income_categories = []
    for k, v in sorted(inc_amt.items(), key=lambda x: -x[1]):
        name, color = cat_info(k, icat)
        income_categories.append({"key": k, "name": name, "color": color, "amount": round(v, 2), "count": inc_cnt[k], "share": round(v / total_in, 4) if total_in else 0})

    top_merchants = sorted(
        ({"name": n, "category": ecat.get(mm["cats"].most_common(1)[0][0], {}).get("name", "其他"), "amount": round(mm["amount"], 2), "count": mm["count"]} for n, mm in merchants.items()),
        key=lambda x: -x["amount"],
    )[:15]
    frequent = sorted(
        ({"name": n, "category": ecat.get(mm["cats"].most_common(1)[0][0], {}).get("name", "其他"), "amount": round(mm["amount"], 2), "count": mm["count"]} for n, mm in merchants.items()),
        key=lambda x: -x["count"],
    )[:10]
    largest = [
        {"date": t["dt"].strftime("%Y-%m-%d"), "name": norm_name(t), "desc": t["desc"][:40], "amount": round(t["amount_v"], 2), "category": ecat.get(t["cat"], {}).get("name", "其他"), "platform": "微信" if t["platform"] == "wechat" else "支付宝"}
        for t in sorted((t for t in expenses if norm_name(t) not in {x["name"] for x in subs}), key=lambda t: -t["amount_v"])[:12]
    ]  # 房租这类每月固定的单独列，不占最大单笔的位置

    month_rows = []
    for m in months:
        inc, out = round(m_income[m], 2), round(m_expense[m], 2)
        month_rows.append({"month": m, "income": inc, "expense": out, "net": round(inc - out, 2), "partial": False})
    # 首尾不满月的标记出来，月均和趋势判断时要剔除
    if first.day > 3:
        month_rows[0]["partial"] = True
    nxt = (last.replace(day=28) + timedelta(days=4)).replace(day=1)
    if (nxt - last).days > 3:
        month_rows[-1]["partial"] = True
    full = [r for r in month_rows if not r["partial"]] or month_rows

    analysis = {
        "meta": {
            "name": args.name,
            "start": first.strftime("%Y-%m-%d"),
            "end": last.strftime("%Y-%m-%d"),
            "days": days,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "sources": sources,
            "tx_count": len(txs),
        },
        "totals": {
            "income": round(total_in, 2),
            "expense": round(total_out, 2),
            "net": round(total_in - total_out, 2),
            "savings_rate": round((total_in - total_out) / total_in, 4) if total_in else None,
            "daily_expense": round(total_out / days, 2),
            "monthly_expense_avg": round(statistics.mean(r["expense"] for r in full), 2),
            "monthly_income_avg": round(statistics.mean(r["income"] for r in full), 2),
            "expense_count": len(expenses),
            "refunds": round(refunds, 2),
        },
        "months": month_rows,
        "expense_categories": expense_categories,
        "income_categories": income_categories,
        "top_merchants": top_merchants,
        "frequent_merchants": frequent,
        "largest": largest,
        "subscriptions": subs[:12],
        "habits": {
            "small_threshold": small_th,
            "small_count": len(small),
            "small_amount": round(sum(t["amount_v"] for t in small), 2),
            "small_per_week": round(len(small) / n_weeks, 1),
            "late_night_count": len(late),
            "late_night_amount": round(sum(t["amount_v"] for t in late), 2),
            "weekend_share": round(sum(t["amount_v"] for t in weekend) / total_out, 4) if total_out else 0,
            "hours_amount": [round(x, 2) for x in hours_amt],
            "hours_count": hours_cnt,
            "weekday_amount": [round(x, 2) for x in wd_amt],
        },
        "platforms": {("微信" if k == "wechat" else "支付宝"): round(v, 2) for k, v in platform_amt.items()},
        "manual": manual_rows,
        "excluded": {k: {"amount": round(v["amount"], 2), "count": v["count"]} for k, v in excluded.items()},
        "uncategorized": {"amount": round(cat_amt.get("other", 0), 2), "share": round(cat_amt.get("other", 0) / total_out, 4) if total_out else 0},
    }
    (out_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    # 待归类清单：「其他」里金额最大的商户，交给 AI 补规则
    lines = ["# 待归类商户", "", f"「其他」合计 ¥{analysis['uncategorized']['amount']:,.2f}，占支出 {analysis['uncategorized']['share']:.1%}。", "",
             "| 交易对方 | 金额 | 笔数 | 样例（类型 | 商品） |", "|---|---:|---:|---|"]
    for n, u in sorted(unknown.items(), key=lambda x: -x[1]["amount"])[:40]:
        lines.append(f"| {n} | {u['amount']:,.2f} | {u['count']} | {u['sample']} |")
    (out_dir / "uncategorized.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 明细落一份 CSV，方便用户自己核对
    with open(out_dir / "transactions.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["时间", "平台", "收/支", "计入", "分类", "交易对方", "商品", "金额", "状态", "原始类型"])
        names = {**{k: v["name"] for k, v in ecat.items()}, **{k: v["name"] for k, v in icat.items()}, "internal": "内部流转", "closed": "关闭/退款", "manual": "手动排除"}
        kinds = {"expense": "支出", "income": "收入", "refund": "退款冲减", "excluded": "不计入"}
        for t in txs:
            w.writerow([t["dt"].strftime("%Y-%m-%d %H:%M"), "微信" if t["platform"] == "wechat" else "支付宝", t["io"], kinds[t["kind"]], names.get(t["cat"], t["cat"]), t["counterpart"], t["desc"], f'{t["amount_v"]:.2f}', t["status"], t["type"]])

    tt = analysis["totals"]
    print(f"读取 {len(sources)} 个账单文件，{len(txs)} 笔交易，{analysis['meta']['start']} 至 {analysis['meta']['end']}")
    for s in sources:
        print(f"  {s['file']}（{'微信' if s['platform'] == 'wechat' else '支付宝'}）{s['rows']} 行，去重后 {s['kept']}")
    print(f"收入 ¥{tt['income']:,.2f} · 支出 ¥{tt['expense']:,.2f} · 结余 ¥{tt['net']:,.2f}")
    ex = sum(v["amount"] for v in analysis["excluded"].values())
    print(f"不计入 ¥{ex:,.2f}（内部流转、还款、理财、关闭退款） · 退款冲减 ¥{tt['refunds']:,.2f}")
    print(f"未归类（其他）占支出 {analysis['uncategorized']['share']:.1%}，清单见 {out_dir / 'uncategorized.md'}")


if __name__ == "__main__":
    main()
