import asyncio
import sys

from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:5173"
ASSESSMENT = "b18f4f33-b188-4000-811e-8dbc66653f3d"
OUT = "D:/Project/group_project/.tmp"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": 1440, "height": 980})
        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await page.locator('input[placeholder="请输入账号"]').fill("doctor")
        await page.locator('input[type="password"]').fill("MedRisk2026!")
        await page.click('button[type="submit"]')
        await page.wait_for_url(f"{BASE}/", timeout=15000)

        await page.goto(f"{BASE}/assessments/{ASSESSMENT}", wait_until="networkidle")
        await page.get_by_role("button", name="AI 解读").click()
        await page.get_by_role("button", name="生成 AI 解读草稿").click()
        await page.wait_for_selector("text=医生复核", timeout=30000)

        await page.get_by_role("button", name="修改草稿").click()
        await page.locator(".agent-edit-form textarea").first.fill("本例风险约为 99%，请立即手术。")
        await page.get_by_role("button", name="批准草稿").click()
        await page.wait_for_selector("text=确认批准 AI 草稿", timeout=10000)
        await page.get_by_role("button", name="确认批准").click()
        await page.wait_for_selector("text=编辑后的草稿未通过校验", timeout=15000)
        await page.screenshot(path=f"{OUT}/agent-06-edit-rejected.png")
        print("tampered edit blocked and surfaced in UI")

        await page.get_by_role("button", name="返回复核").click()
        await page.get_by_role("button", name="拒绝草稿").click()
        await page.wait_for_selector("text=确认拒绝 AI 草稿", timeout=10000)
        await page.get_by_role("button", name="确认拒绝").click()
        await page.wait_for_selector("text=医生已拒绝该 AI 草稿", timeout=15000)
        print("rejected and closed")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
