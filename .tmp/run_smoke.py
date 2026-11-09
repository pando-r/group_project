import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        await page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        print("before-login:", page.url)
        await page.get_by_role("button", name="安全登录").click()
        await page.get_by_role("heading", name="临床工作台", exact=True).wait_for(
            timeout=20000
        )
        await page.wait_for_timeout(1500)
        print("after-login:", page.url)
        print("heading:", await page.get_by_role("heading", name="临床工作台", exact=True).inner_text())
        print("login-form-visible:", await page.get_by_role("button", name="安全登录").is_visible())
        await page.screenshot(path=".tmp/run-dashboard.png", full_page=True)
        print("console_errors:", console_errors[:5])
        await browser.close()


asyncio.run(main())
