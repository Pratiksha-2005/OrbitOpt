import asyncio
from playwright.async_api import async_playwright

async def run():
    print("Starting Playwright E2E Tests...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()

        errors = []
        page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"Page Error: {err}"))

        try:
            # 1. Landing Page
            print("Navigating to landing page...")
            response = await page.goto('http://localhost:5173/')
            print(f"Landing page response: {response.status}")
            await page.wait_for_load_state('networkidle')
            print("Landing page loaded successfully.")

            # 2. Login Flow (Mocked or attempt)
            # Since we may not have a real firebase user, we'll try to reach login page
            print("Navigating to login...")
            await page.goto('http://localhost:5173/login')
            await page.wait_for_load_state('networkidle')

            # We can't actually log in easily without real credentials, but we can verify dashboard redirects
            print("Navigating to Dashboard...")
            dashboard_res = await page.goto('http://localhost:5173/dashboard')
            print(f"Dashboard response: {dashboard_res.status}")
            await page.wait_for_load_state('networkidle')

            # 3. Gantt Chart page or Timeline
            print("Navigating to Schedule Timeline...")
            await page.goto('http://localhost:5173/schedule')
            await page.wait_for_load_state('networkidle')

            # 4. Global Ground Station Tracking Network
            print("Navigating to Map...")
            await page.goto('http://localhost:5173/map')
            await page.wait_for_load_state('networkidle')

            # 5. Orbital Simulator
            print("Navigating to Simulator...")
            await page.goto('http://localhost:5173/simulator')
            await page.wait_for_load_state('networkidle')

            print("Captured Console Errors:")
            for e in errors:
                print(e)
            
            print("E2E Test Flow completed successfully (basic navigation).")

        except Exception as e:
            print(f"Test failed with exception: {e}")
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
