#!/usr/bin/env python3
"""
生成一套虚构的微信 + 支付宝账单（格式与官方导出一致），用来演示和自测。

用法：python3 make_sample.py <输出目录> [--months 10] [--year 2026]
产物：微信支付账单流水文件(示例).xlsx、支付宝交易明细(示例).csv（GBK 编码）
人物设定：杭州上班族，工资走银行卡（不在账单里），副业接设计单走微信收款。
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--months", type=int, default=10)
ap.add_argument("--year", type=int, default=2026)
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()
R = random.Random(args.seed)
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)

wx, ali = [], []
oid = [10000]


def nid():
    oid[0] += R.randint(1, 9)
    return f"4200{oid[0]:014d}"


def at(day, h1, h2):
    return day.replace(hour=R.randint(h1, h2), minute=R.randint(0, 59), second=R.randint(0, 59))


def W(t, typ, who, what, io, amt, status="支付成功", method="零钱"):
    wx.append([t.strftime("%Y-%m-%d %H:%M:%S"), typ, who, what, io, f"¥{amt:.2f}", method if io != "收入" else "/", status, nid(), nid() if typ == "商户消费" else "/", "/"])


def A(t, cat, who, what, io, amt, status="交易成功", method="花呗"):
    ali.append([t.strftime("%Y-%m-%d %H:%M:%S"), cat, who, "", what, io, f"{amt:.2f}", method if io == "支出" else "余额", status, "2026" + nid(), "", ""])


start = datetime(args.year, 1, 1)
for mi in range(args.months):
    m0 = start.replace(month=mi + 1)
    nxt = (m0.replace(day=28) + timedelta(days=4)).replace(day=1)
    days = (nxt - m0).days
    for d in range(days):
        day = m0 + timedelta(days=d)
        wd = day.weekday()
        if wd < 5:
            A(at(day, 8, 8), "交通出行", "杭州地铁", "乘车码", "支出", R.choice([3, 4, 5, 6]))
            A(at(day, 18, 19), "交通出行", "杭州地铁", "乘车码", "支出", R.choice([3, 4, 5, 6]))
            if R.random() < 0.7:
                W(at(day, 9, 10), "商户消费", "瑞幸咖啡", "生椰拿铁", "支出", R.choice([9.9, 13.9, 16.9]))
            W(at(day, 11, 12), "商户消费", "美团平台商户", "美团外卖订单", "支出", round(R.uniform(22, 48), 1))
            if R.random() < 0.35 + mi * 0.03:  # 下半年加班多，晚饭外卖变多
                W(at(day, 19, 21), "商户消费", "美团平台商户", "美团外卖订单", "支出", round(R.uniform(28, 62), 1))
        else:
            if R.random() < 0.6:
                A(at(day, 12, 13), "餐饮美食", R.choice(["西贝莜面村", "太二酸菜鱼", "海底捞", "外婆家"]), "堂食", "支出", round(R.uniform(90, 320), 0))
            if R.random() < 0.7:
                A(at(day, 10, 17), "日用百货", "盒马鲜生", "盒马订单", "支出", round(R.uniform(68, 260), 1))
            if R.random() < 0.5:
                W(at(day, 14, 22), "商户消费", "滴滴出行", "快车", "支出", round(R.uniform(16, 58), 1))
        if R.random() < 0.18:
            W(at(day, 22, 23).replace(minute=R.randint(10, 59)), "商户消费", "美团平台商户", "美团外卖-夜宵", "支出", round(R.uniform(35, 88), 1))
        if R.random() < 0.25:
            W(at(day, 7, 22), "商户消费", R.choice(["全家便利店", "罗森", "7-Eleven"]), "便利店", "支出", round(R.uniform(6, 28), 1))

    mday = lambda d, h1=9, h2=21: at(m0.replace(day=min(d, days)), h1, h2)
    # 固定支出
    A(mday(5, 10, 10), "住房物业", "自如", "10 月房租".replace("10", str(mi + 1)), "支出", 4500, method="余额宝")
    A(mday(12), "充值缴费", "国家电网浙江省电力公司", "电费", "支出", round(R.uniform(90, 120) + (180 if mi in (0, 1, 6, 7) else 0), 2))
    A(mday(1), "充值缴费", "中国移动", "话费充值", "支出", 99)
    W(mday(3), "商户消费", "乐刻运动", "月卡续费", "支出", 199)
    for who, what, amt, since in [("爱奇艺", "黄金VIP会员连续包月", 25, 0), ("腾讯音乐", "QQ音乐豪华绿钻连续包月", 15, 0), ("Apple", "iCloud+ 200GB", 21, 0),
                                  ("OpenAI", "ChatGPT Plus 订阅", 145, 2), ("百度网盘", "超级会员连续包月", 30, 4), ("夸克", "SVIP 连续包月", 25, 6)]:
        if mi >= since:
            A(mday(R.randint(6, 9)), "文化休闲" if who != "OpenAI" else "其他", who, what, "支出", amt)
    # 网购
    for _ in range(R.randint(3, 7) + (6 if mi == 9 else 0)):
        plat = R.choice(["淘宝", "京东", "拼多多"])
        amt = round(R.uniform(39, 680) * (1.6 if mi == 9 else 1), 1)
        t = mday(R.randint(1, 28))
        if plat == "淘宝":
            A(t, "服饰装扮", "淘宝", "淘宝订单", "支出", amt)
        else:
            W(t, "商户消费", "京东商城" if plat == "京东" else "拼多多平台商户", f"{plat}订单", "支出", amt)
    if mi == 3:
        A(mday(22), "数码电器", "Apple Store", "iPad Air", "支出", 4799)
    # 娱乐、学习、健康
    for _ in range(R.randint(0, 2)):
        A(mday(R.randint(1, 28), 19, 20), "文化休闲", "猫眼电影", "电影票", "支出", round(R.uniform(45, 110), 0))
    if mi in (2, 7):
        W(mday(15), "商户消费", "得到", "得到App课程", "支出", 199)
    if mi == 1:
        W(mday(20), "商户消费", "知识星球", "星球年费", "支出", 299)
    if R.random() < 0.4:
        A(mday(R.randint(1, 28)), "医疗健康", "老百姓大药房", "药品", "支出", round(R.uniform(28, 160), 1))
    # 旅行
    if mi == 4:
        A(mday(1, 9, 9), "酒店旅游", "携程旅行网", "杭州-成都 机票", "支出", 1860)
        A(mday(2, 15, 15), "酒店旅游", "携程旅行网", "成都 亚朵酒店 3 晚", "支出", 1380)
    if mi == 9:
        A(mday(1, 8, 8), "酒店旅游", "飞猪", "杭州-厦门 机票", "支出", 2260)
        A(mday(1, 16, 16), "酒店旅游", "飞猪", "厦门 民宿 4 晚", "支出", 1720)
    # 人情往来
    if mi == 1:
        for _ in range(6):
            W(mday(R.randint(8, 16)), "微信红包", "家人群", "/", "支出", R.choice([200, 500, 666, 888]), status="已存入对方零钱")
    if R.random() < 0.5:
        W(mday(R.randint(1, 28)), "转账", R.choice(["小林", "阿杰", "王姐"]), "/", "支出", R.choice([50, 120, 200, 300]), status="对方已收钱")
    if mi in (5, 8):
        W(mday(18), "转账", "大学室友", "/", "支出", 1000, status="对方已收钱", method="招商银行储蓄卡(1234)")
    # 归不了类的
    if mi % 3 == 1:
        W(mday(10), "扫二维码付款", "杭州余杭区某某商贸有限公司", "/", "支出", round(R.uniform(180, 420), 0))
    if mi % 4 == 2:
        A(mday(17), "其他", "浙江小麦网络科技有限公司", "服务费", "支出", 268)
    # 收入：副业设计单、闲鱼
    for _ in range(R.randint(1, 3) + (1 if mi >= 5 else 0)):
        W(mday(R.randint(1, 28)), "转账", R.choice(["设计客户A", "设计客户B", "某工作室"]), "/", "收入", R.choice([800, 1200, 1500, 2000, 2600]), status="已收钱")
    if R.random() < 0.4:
        A(mday(R.randint(1, 28)), "收入", "闲鱼", "二手转卖", "收入", round(R.uniform(60, 380), 0))
    # 不计入：信用卡还款、余额宝、提现、退款
    W(mday(8), "信用卡还款", "招商银行信用卡", "/", "支出", round(R.uniform(2000, 5000), 2), status="支付成功", method="招商银行储蓄卡(1234)")
    A(mday(9), "投资理财", "余额宝", "余额宝-自动转入", "不计收支", round(R.uniform(500, 3000), 2))
    A(mday(9), "信用借还", "花呗", "花呗主动还款-2026年账单", "不计收支", round(R.uniform(1500, 4000), 2))
    wx.append([mday(25).strftime("%Y-%m-%d %H:%M:%S"), "零钱提现", "招商银行(1234)", "/", "/", f"¥{R.choice([1000, 2000]):.2f}", "零钱", "提现已到账", nid(), "/", "服务费¥0.00"])
    if mi == 6:
        t = mday(6)
        A(t, "服饰装扮", "淘宝", "退货的外套", "支出", 459, status="交易关闭")
        A(t + timedelta(days=3), "退款", "淘宝", "退款-退货的外套", "不计收支", 459, status="退款成功")
        W(mday(20), "商户消费", "京东商城", "京东订单", "支出", 320, status="已退款(￥120.00)")
        W(mday(23), "京东商城-退款", "京东商城", "/", "收入", 120, status="已全额退款")

wx.sort(key=lambda r: r[0], reverse=True)
ali.sort(key=lambda r: r[0], reverse=True)
end = (start.replace(month=args.months).replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)
period = f"[{start:%Y-%m-%d %H:%M:%S}] 终止时间：[{end:%Y-%m-%d %H:%M:%S}]"

wx_head = [["微信支付账单明细"], ["微信昵称：[示例用户]"], [f"起始时间：{period}"], ["导出类型：[全部]"], [f"导出时间：[{end:%Y-%m-%d %H:%M:%S}]"], [""],
           [f"共{len(wx)}笔记录"], [""], ["注："], ["1. 本明细仅展示当前账单中的交易，不包括已删除的记录"], [""], ["----------------------微信支付账单明细列表--------------------"],
           ["交易时间", "交易类型", "交易对方", "商品", "收/支", "金额(元)", "支付方式", "当前状态", "交易单号", "商户单号", "备注"]]
try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in wx_head + wx:
        ws.append(r)
    wx_path = out / "微信支付账单流水文件(示例).xlsx"
    wb.save(wx_path)
except ImportError:
    wx_path = out / "微信支付账单(示例).csv"
    with open(wx_path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(wx_head + wx)

ali_head = [["------------------------------------------------------------------------------------"], ["导出信息："], ["姓名：示例用户"], ["支付宝账户：demo@example.com"],
            [f"起始时间：{period}"], ["导出交易类型：[全部]"], [f"导出时间：[{end:%Y-%m-%d %H:%M:%S}]"], [f"共{len(ali)}笔记录"], ["特别提示："],
            ["1.本回单内容可表明支付宝受理了相关交易申请，不代表交易已经成功。"], ["------------------------支付宝（中国）网络技术有限公司  电子客户回单------------------------"],
            ["交易时间", "交易分类", "交易对方", "对方账号", "商品说明", "收/支", "金额", "收/付款方式", "交易状态", "交易订单号", "商家订单号", "备注", ""]]
ali_path = out / "支付宝交易明细(示例).csv"
with open(ali_path, "w", encoding="gb18030", newline="") as f:
    csv.writer(f).writerows(ali_head + ali)
print(f"{wx_path}（{len(wx)} 笔）\n{ali_path}（{len(ali)} 笔）")
