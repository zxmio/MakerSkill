#!/usr/bin/env python3
"""
把 analysis.json（+ insights.json）渲染成单文件 HTML 仪表盘，可选再截两张 PNG。

用法：
  python3 render.py <输出目录> [--png]
读取 <输出目录>/analysis.json、<输出目录>/insights.json（没有也能出仪表盘，洞察页会提示待写）
产出 <输出目录>/finance-dashboard.html；--png 时再出 dashboard.png、insights.png（需要本机装了 Chrome / Chromium）
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "dashboard.html"

REQUIRED_INSIGHT_KEYS = ("headline", "summary", "findings", "actions")


def find_chrome():
    for p in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ):
        if Path(p).exists():
            return p
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def screenshot(chrome, html, tab, out_png, width=1280):
    """截整页：先截一张很高的图，再按底色裁掉多余的空白。"""
    raw = out_png.with_suffix(".raw.png")
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},4200",
         "--force-device-scale-factor=2", "--virtual-time-budget=3000", f"--screenshot={raw}", html.resolve().as_uri() + "#" + tab],
        check=True, capture_output=True,
    )
    try:
        from PIL import Image
    except ImportError:
        raw.replace(out_png)
        return
    im = Image.open(raw).convert("RGB")
    bg = im.getpixel((4, im.height - 4))
    px = im.load()
    y = im.height - 1
    while y > 0 and all(px[x, y] == bg for x in range(0, im.width, 9)):
        y -= 1
    im.crop((0, 0, im.width, min(im.height, y + 60))).save(out_png)
    raw.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--png", action="store_true", help="同时截图成 PNG")
    args = ap.parse_args()
    d = Path(args.dir)
    analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
    insights = None
    ip = d / "insights.json"
    if ip.exists():
        insights = json.loads(ip.read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED_INSIGHT_KEYS if k not in insights]
        if missing:
            sys.exit(f"insights.json 缺少字段：{missing}，格式见 references/insights-guide.md")
    payload = json.dumps({"analysis": analysis, "insights": insights}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)
    out = d / "finance-dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(out)
    if args.png:
        chrome = find_chrome()
        if not chrome:
            sys.exit("没找到 Chrome / Chromium / Edge，跳过截图；直接用浏览器打开 HTML 即可")
        for tab in ("dashboard", "insights"):
            png = d / f"{tab}.png"
            screenshot(chrome, out, tab, png)
            print(png)


if __name__ == "__main__":
    main()
