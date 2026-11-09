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
        page.on("console", lambda msg: print(f"[console.{msg.type}] {msg.text}") if msg.type == "error" else None)
        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await page.locator('input[placeholder="请输入账号"]').fill("doctor")
        await page.locator('input[type="password"]').fill("MedRisk2026!")
        await page.click('button[type="submit"]')
        await page.wait_for_url(f"{BASE}/", timeout=15000)
        print("logged in")

        await page.goto(f"{BASE}/assessments/{ASSESSMENT}", wait_until="networkidle")
        await page.wait_for_selector("text=风险评估报告", timeout=15000)
        await page.screenshot(path=f"{OUT}/agent-01-report.png", full_page=True)

        await page.get_by_role("button", name="AI 解读").click()
        await page.wait_for_selector("text=AI 临床解读", timeout=10000)
        await page.wait_for_timeout(600)
        await page.screenshot(path=f"{OUT}/agent-02-drawer-idle.png")

        await page.get_by_role("button", name="生成 AI 解读草稿").click()
        await page.wait_for_selector("text=医生复核", timeout=30000)
        await page.wait_for_timeout(600)
        await page.screenshot(path=f"{OUT}/agent-03-waiting.png")
        print("waiting state reached")

        await page.get_by_role("button", name="批准草稿").click()
        await page.wait_for_selector("text=确认批准 AI 草稿", timeout=10000)
        await page.fill("textarea", "复核通过：数值与引用一致。")
        await page.screenshot(path=f"{OUT}/agent-04-confirm.png")
        await page.get_by_role("button", name="确认批准").click()
        await page.wait_for_selector("text=医生已批准该 AI 草稿", timeout=20000)
        await page.wait_for_timeout(600)
        await page.screenshot(path=f"{OUT}/agent-05-approved.png")
        print("approved")

        await page.click(".agent-drawer .ant-drawer-close")
        await page.goto(f"{BASE}/models", wait_until="networkidle")
        await page.wait_for_selector("text=模型与规则", timeout=15000)
        await page.screenshot(path=f"{OUT}/models.png", full_page=True)
        print("models captured")

        errors = await page.locator(".ant-message-error").count()
        print("error toasts:", errors)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
