#!/usr/bin/env python3
"""Simple test script to verify browser opens correctly."""

import asyncio
from playwright.async_api import async_playwright


async def test_browser():
    """Test if browser can open."""
    try:
        print("Testing browser launch...")
        playwright = await async_playwright().start()
        
        print("Launching Chromium (visible mode)...")
        browser = await playwright.chromium.launch(headless=False)
        print("✓ Browser launched!")
        
        context = await browser.new_context()
        page = await context.new_page()
        
        print("Navigating to Google...")
        await page.goto('https://www.google.com', timeout=30000)
        print("✓ Page loaded!")
        
        title = await page.title()
        print(f"✓ Page title: {title}")
        
        print("\nBrowser is working! Press Enter to close...")
        input()
        
        await browser.close()
        print("✓ Browser closed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_browser())

