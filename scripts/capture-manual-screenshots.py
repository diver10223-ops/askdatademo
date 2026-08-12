"""Capture actual POC pages used by the phase-2 delivery manuals."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "deliverables" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:18081"


def shot(page, name, full=False):
    page.screenshot(path=str(OUT / name), full_page=full)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 920}, device_scale_factor=1)
    page.goto(BASE, wait_until="networkidle")
    shot(page, "01-user-home.png")
    page.get_by_role("button", name="场景1：基础查数（机构/指标权限）").click()
    page.wait_for_selector(".result-bubble", timeout=20000)
    page.wait_for_timeout(1200)
    shot(page, "02-user-query-result.png", full=True)
    page.goto(BASE + "/admin", wait_until="networkidle")
    shot(page, "03-admin-home.png")

    targets = [
        ("用户权限", "用户管理", "04-admin-users.png"),
        ("数据字典", "指标字典", "05-admin-metrics.png"),
        ("模型配置", "模型对接", "06-admin-models.png"),
        ("数据源配置", "数据源对接", "07-admin-datasources.png"),
        ("查询日志", "执行轨迹", "08-admin-query-logs.png"),
        ("系统运维", "备份重置", "09-admin-recovery.png"),
    ]
    for parent, child, filename in targets:
        page.locator(".menu-parent", has_text=parent).click()
        page.locator(".sub-menu button", has_text=child).click()
        page.wait_for_timeout(450)
        shot(page, filename)
    browser.close()
