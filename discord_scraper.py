#!/usr/bin/env python3
"""
Discord Web Scraper
Scrapes messages from Discord web application across all channels
and filters messages by a specific user.
"""

import asyncio
import json
import re
import time
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser


class DiscordScraper:
    def __init__(
        self, 
        target_username: str = "consτ [τ, τ]", 
        target_server: str = "bittensor", 
        headless: bool = False, 
        scrape_unread_only: bool = True,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ):
        """
        Initialize the Discord scraper.
        
        Args:
            target_username: The username to filter messages for (default: "consτ [τ, τ]")
            target_server: The server name to scrape (default: "bittensor")
            headless: Whether to run browser in headless mode
            scrape_unread_only: Only scrape unread messages (default: True) - faster and avoids duplicates
            telegram_bot_token: Telegram Bot API token (from @BotFather)
            telegram_chat_id: Telegram chat/channel ID to send messages to
        """
        self.target_username = target_username
        self.target_server = target_server.lower()
        self.headless = headless
        self.scrape_unread_only = scrape_unread_only
        self.messages: List[Dict] = []
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._channel_list_container = None  # Cached channel list container
        
        # Telegram configuration
        self.telegram_bot_token = "8218166853:AAFVYr5y3yK-dPCM_89d4Te8pXraSWskyiM"
        self.telegram_chat_id = "7665326469"
        
        if scrape_unread_only:
            print(f"📬 Mode: Only scraping UNREAD messages (faster, avoids duplicates)")
        else:
            print(f"📬 Mode: Scraping all messages")
        
        if telegram_bot_token and telegram_chat_id:
            print(f"📱 Telegram: Will send results to chat {telegram_chat_id}")
        
    async def setup_browser(self):
        """Initialize browser and navigate to Discord."""
        try:
            print("Initializing Playwright...")
            playwright = await async_playwright().start()
            
            print(f"Launching browser (headless={self.headless})...")
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            print("✓ Browser launched successfully")
            
            # Create a new context with realistic viewport
            print("Creating browser context...")
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            print("✓ Browser context created")
            
            self.page = await context.new_page()
            print("✓ New page created")
            
            # Give browser time to open if not headless
            if not self.headless:
                print("Waiting for browser window to open...")
                await asyncio.sleep(2)
            
            print("Navigating to Discord...")
            await self.page.goto('https://discord.com/login', wait_until='networkidle', timeout=60000)
            print("✓ Discord page loaded")
            
            # Verify page is accessible
            title = await self.page.title()
            print(f"✓ Page title: {title}")
        except Exception as e:
            print(f"✗ Error setting up browser: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        print("\n" + "="*60)
        print("Please log in to Discord in the browser window.")
        print("Waiting for you to complete login...")
        print("="*60 + "\n")
        
        # Wait for login to complete (check for presence of server list or channels)
        await self.wait_for_login()
        
        # Navigate to the target server
        await self.navigate_to_server()
        
    async def navigate_to_server(self, timeout: int = 60):
        """Navigate to the target server (Bittensor)."""
        print(f"\n{'='*60}")
        print(f"Looking for '{self.target_server}' server...")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        target_lower = self.target_server.lower()
        
        # Wait a bit for Discord to fully load
        await asyncio.sleep(2)  # Reduced from 3s
        
        while time.time() - start_time < timeout:
            try:
                print("Attempting to find server list...")
                
                # Method 1: Find server list container (most reliable)
                server_elements = []
                server_list_selectors = [
                    'nav[aria-label*="Servers"]',
                    'nav[aria-label*="servers"]',
                    'div[class*="guilds"]',
                    'div[class*="guildsWrapper"]',
                    'div[class*="guilds-"]',
                    '[aria-label*="Servers"]',
                    '[aria-label*="servers"]'
                ]
                
                for selector in server_list_selectors:
                    try:
                        containers = await self.page.query_selector_all(selector)
                        for container in containers:
                            # Find all clickable elements within container
                            elements = await container.query_selector_all('a, button, div[role="button"], div[class*="guild"], div[class*="wrapper"]')
                            if elements:
                                server_elements = elements
                                print(f"✓ Found server list container with {len(elements)} elements using: {selector}")
                                break
                        if server_elements:
                            break
                    except Exception as e:
                        continue
                
                # Method 2: Find server icons directly by various selectors
                if not server_elements:
                    print("Trying alternative selectors...")
                    server_icon_selectors = [
                        'div[class*="guild"][class*="wrapper"]',
                        'div[class*="guildIcon"]',
                        'a[href^="/channels/"]',
                        'div[class*="guild"]',
                        'div[data-list-item-id*="guild"]',
                        'div[class*="wrapper"][class*="guild"]',
                        'div[aria-label]',  # Many server icons have aria-label
                    ]
                    for selector in server_icon_selectors:
                        try:
                            elements = await self.page.query_selector_all(selector)
                            if elements and len(elements) > 2:  # Should have multiple servers
                                server_elements = elements
                                print(f"✓ Found {len(elements)} potential servers using: {selector}")
                                break
                        except:
                            continue
                
                # Method 3: Find all elements with aria-label that might be servers
                if not server_elements:
                    print("Trying to find elements with aria-label...")
                    try:
                        all_elements = await self.page.query_selector_all('[aria-label]')
                        # Filter for elements that look like server icons (have aria-label with server-like text)
                        for elem in all_elements:
                            aria = await elem.get_attribute('aria-label') or ""
                            if aria and ('server' in aria.lower() or len(aria.split()) < 10):
                                server_elements.append(elem)
                        if server_elements:
                            print(f"✓ Found {len(server_elements)} elements with aria-label")
                    except:
                        pass
                
                if not server_elements:
                    print("⚠ No server elements found, waiting...")
                    await asyncio.sleep(1)  # Reduced from 2s
                    continue
                
                print(f"\nAnalyzing {len(server_elements)} potential server elements...")
                
                # Collect all servers with their names - try multiple methods
                found_servers = []
                seen_names = set()
                
                for server_elem in server_elements:
                    try:
                        server_name = None
                        methods_used = []
                        
                        # Method 1: aria-label (most reliable for Discord)
                        aria_label = await server_elem.get_attribute('aria-label')
                        if aria_label:
                            # Discord format: "Server Name, 1 unread" or "Server Name, muted" or just "Server Name"
                            server_name = aria_label.split(',')[0].strip()
                            if server_name:
                                methods_used.append("aria-label")
                        
                        # Method 2: title attribute
                        if not server_name:
                            title = await server_elem.get_attribute('title')
                            if title and len(title.strip()) > 0:
                                server_name = title.strip()
                                methods_used.append("title")
                        
                        # Method 3: data attributes
                        if not server_name:
                            data_name = await server_elem.get_attribute('data-name')
                            if data_name:
                                server_name = data_name.strip()
                                methods_used.append("data-name")
                        
                        # Method 4: text content (for server icons with abbreviations)
                        if not server_name:
                            text = await server_elem.inner_text()
                            if text and len(text.strip()) > 0 and len(text.strip()) < 50:
                                server_name = text.strip()
                                methods_used.append("text")
                        
                        # Method 5: Check child elements for name
                        if not server_name:
                            name_elem = await server_elem.query_selector('[class*="name"], span, div[class*="name"]')
                            if name_elem:
                                name_text = await name_elem.inner_text()
                                if name_text and len(name_text.strip()) > 0:
                                    server_name = name_text.strip()
                                    methods_used.append("child-element")
                        
                        # Skip if no name found or if it's a duplicate
                        if not server_name or server_name.lower() in seen_names:
                            continue
                        
                        seen_names.add(server_name.lower())
                        
                        # Check if element is clickable (has href or is button-like)
                        is_clickable = False
                        href = await server_elem.get_attribute('href')
                        role = await server_elem.get_attribute('role')
                        tag_name = await server_elem.evaluate('el => el.tagName.toLowerCase()')
                        
                        if href or role == 'button' or tag_name in ['a', 'button']:
                            is_clickable = True
                        
                        found_servers.append({
                            'name': server_name,
                            'element': server_elem,
                            'name_lower': server_name.lower(),
                            'methods': methods_used,
                            'clickable': is_clickable
                        })
                    except Exception as e:
                        continue
                
                # Print ALL found servers
                if found_servers:
                    print(f"\n{'='*60}")
                    print(f"FOUND {len(found_servers)} SERVERS:")
                    print(f"{'='*60}")
                    for i, srv in enumerate(found_servers, 1):
                        clickable_str = "✓" if srv['clickable'] else "✗"
                        methods_str = ", ".join(srv['methods'])
                        print(f"  {i:3d}. {clickable_str} {srv['name']:50s} (via: {methods_str})")
                    print(f"{'='*60}\n")
                    
                    # Find best match using scoring system
                    best_match = None
                    best_score = -1
                    
                    print(f"Searching for server matching '{self.target_server}'...")
                    
                    for srv in found_servers:
                        name_lower = srv['name_lower']
                        score = 0
                        reason = ""
                        
                        # Exact match gets highest score
                        if name_lower == target_lower:
                            score = 100
                            reason = "exact match"
                        # Starts with target gets high score
                        elif name_lower.startswith(target_lower):
                            score = 80
                            reason = "starts with"
                        # Contains target as whole word gets medium score
                        elif f" {target_lower} " in f" {name_lower} " or name_lower.startswith(target_lower + " ") or name_lower.endswith(" " + target_lower):
                            score = 60
                            reason = "whole word"
                        # Contains target anywhere gets low score
                        elif target_lower in name_lower:
                            score = 40
                            reason = "contains"
                        else:
                            continue
                        
                        # Prefer clickable elements
                        if srv['clickable']:
                            score += 10
                        
                        if score > best_score:
                            best_score = score
                            best_match = srv
                            print(f"  → New best match: '{srv['name']}' (score: {score}, reason: {reason})")
                    
                    if best_match and best_score >= 40:
                        print(f"\n✓ Best match: '{best_match['name']}' (score: {best_score})")
                        
                        if not best_match['clickable']:
                            print(f"⚠ Warning: Selected server element may not be clickable")
                        
                        print(f"  Clicking on '{best_match['name']}' server...")
                        
                        # Scroll element into view if needed
                        try:
                            await best_match['element'].scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)  # Reduced from 0.5s
                        except:
                            pass
                        
                        # Try multiple click methods
                        clicked = False
                        try:
                            # Method 1: Direct click
                            await best_match['element'].click()
                            clicked = True
                        except:
                            try:
                                # Method 2: JavaScript click
                                await best_match['element'].evaluate('el => el.click()')
                                clicked = True
                            except:
                                try:
                                    # Method 3: Click on parent if element itself isn't clickable
                                    parent = await best_match['element'].evaluate_handle('el => el.parentElement')
                                    if parent:
                                        await parent.click()
                                        clicked = True
                                except:
                                    pass
                        
                        if clicked:
                            await asyncio.sleep(2)  # Reduced from 3s - Wait for server to load
                            
                            # Verify we're on the right server by checking the page
                            await asyncio.sleep(1)  # Reduced from 2s
                            
                            # Try to verify server name from page
                            try:
                                # Check server name in the header/title area
                                server_name_selectors = [
                                    '[class*="guildName"]',
                                    '[class*="serverName"]',
                                    'h1[class*="name"]',
                                    'div[class*="name"][class*="guild"]',
                                    'div[class*="title"]'
                                ]
                                for sel in server_name_selectors:
                                    name_elem = await self.page.query_selector(sel)
                                    if name_elem:
                                        current_name = await name_elem.inner_text()
                                        if current_name and target_lower in current_name.lower():
                                            print(f"✓ Verified: Currently on '{current_name}' server")
                                            break
                            except:
                                pass
                            
                            print(f"✓ Successfully navigated to server\n")
                            return True
                        else:
                            print(f"✗ Failed to click on server element")
                    else:
                        print(f"\n⚠ No good match found for '{self.target_server}'")
                        if found_servers:
                            print(f"   Searched through {len(found_servers)} servers but none matched.")
                            print(f"   Please check the server list above and verify '{self.target_server}' is present.")
                
                await asyncio.sleep(1)  # Reduced from 2s
                
            except Exception as e:
                print(f"Error during server search: {e}")
                await asyncio.sleep(1)
        
        print(f"\n⚠ Could not automatically find '{self.target_server}' server.")
        print(f"Please manually navigate to the '{self.target_server}' server in the browser.")
        input("Press Enter once you're on the Bittensor server...")
        await asyncio.sleep(1)  # Reduced from 2s
        return True
        
    async def wait_for_login(self, timeout: int = 300):
        """Wait for user to log in by checking for Discord UI elements."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check for various Discord UI elements that appear after login
                selectors = [
                    '[aria-label*="Servers"]',
                    '[class*="guilds"]',
                    '[class*="sidebar"]',
                    'div[class*="channels"]',
                    '[data-list-id*="guild"]'
                ]
                
                for selector in selectors:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        print("✓ Login detected! Starting to scrape...")
                        await asyncio.sleep(1)  # Reduced from 2s - Give UI time to fully load
                        return True
                
                await asyncio.sleep(1)
            except Exception as e:
                await asyncio.sleep(1)
        
        raise TimeoutError("Login timeout. Please ensure you've logged in to Discord.")
    
    async def get_channel_list_container(self, force_refresh: bool = False):
        """
        Get the channel list container (left sidebar), using cache when available.
        
        Args:
            force_refresh: If True, ignore cache and find container again
            
        Returns:
            The channel list container element, or None if not found
        """
        # Return cached container if valid
        if not force_refresh and self._channel_list_container:
            try:
                # Verify the cached container is still valid/attached to DOM
                is_connected = await self._channel_list_container.evaluate('el => el.isConnected')
                if is_connected:
                    return self._channel_list_container
            except:
                pass  # Container is stale, need to find again
        
        # Find the channel list container
        selectors = [
            'nav[aria-label*="Channels"]',
            'nav[aria-label*="channels"]',
            'div[class*="channels"]',
            'div[class*="sidebar"]',
            '[class*="scroller"][class*="channel"]'
        ]
        
        for selector in selectors:
            try:
                container = await self.page.query_selector(selector)
                if container:
                    is_scrollable = await container.evaluate('el => el.scrollHeight > el.clientHeight')
                    if is_scrollable:
                        self._channel_list_container = container
                        return container
            except:
                continue
        
        # Fallback: find scrollable div in sidebar area
        try:
            all_divs = await self.page.query_selector_all('div[class*="scroller"], div[class*="scrollable"]')
            for div in all_divs:
                try:
                    is_scrollable = await div.evaluate('el => el.scrollHeight > el.clientHeight')
                    if is_scrollable:
                        bounding_box = await div.bounding_box()
                        if bounding_box and bounding_box['x'] < 300:  # Sidebar is on the left
                            self._channel_list_container = div
                            return div
                except:
                    continue
        except:
            pass
        
        return None
    
    async def expand_all_categories(self, scroll_container=None):
        """Expand all collapsed channel categories to show all channels."""
        try:
            # Find category headers/buttons that can be clicked to expand
            category_selectors = [
                'button[class*="category"]',
                'div[class*="category"][role="button"]',
                'div[class*="categoryHeader"]',
                '[aria-label*="category"]',
                'button[aria-expanded="false"]',  # Collapsed categories
                'div[class*="containerDefault"][class*="clickable"]'  # Category containers
            ]
            
            expanded_count = 0
            last_expanded = -1
            
            # Try multiple passes to expand all categories
            for pass_num in range(5):  # Multiple passes to catch all categories
                current_expanded = 0
                
                for selector in category_selectors:
                    try:
                        category_buttons = await self.page.query_selector_all(selector)
                        for btn in category_buttons:
                            try:
                                # Check if it's collapsed
                                aria_expanded = await btn.get_attribute('aria-expanded')
                                if aria_expanded == 'false':
                                    # Scroll element into view if needed
                                    if scroll_container:
                                        try:
                                            await btn.scroll_into_view_if_needed()
                                            await asyncio.sleep(0.1)
                                        except:
                                            pass
                                    
                                    await btn.click()
                                    await asyncio.sleep(0.2)
                                    current_expanded += 1
                                    expanded_count += 1
                            except:
                                # Try clicking anyway (might be expandable)
                                try:
                                    if scroll_container:
                                        try:
                                            await btn.scroll_into_view_if_needed()
                                            await asyncio.sleep(0.1)
                                        except:
                                            pass
                                    await btn.click()
                                    await asyncio.sleep(0.2)
                                    current_expanded += 1
                                    expanded_count += 1
                                except:
                                    pass
                    except:
                        continue
                
                # If no new categories expanded, we're done
                if current_expanded == 0 and last_expanded == 0:
                    break
                
                last_expanded = current_expanded
                await asyncio.sleep(0.3)
            
            if expanded_count > 0:
                print(f"  Expanded {expanded_count} categories")
            else:
                print(f"  No collapsed categories found (or already expanded)")
                
        except Exception as e:
            print(f"  ⚠ Error expanding categories: {e}")
    
    async def scroll_channel_list(self, max_scrolls: int = 200):
        """Scroll the channel list in the left panel to load all channels."""
        try:
            print("Scrolling channel list to load all channels...")
            
            # First, expand all categories
            await self.expand_all_categories()
            await asyncio.sleep(0.5)  # Reduced from 1s
            
            # Use cached channel list container
            channel_list_container = await self.get_channel_list_container()
            
            if channel_list_container:
                print(f"  Found scrollable channel list container")
                last_height = 0
                scroll_count = 0
                no_change_count = 0
                
                # Start from top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.3)  # Reduced from 0.5s
                
                for i in range(max_scrolls):
                    # Get current measurements
                    current_height = await channel_list_container.evaluate('el => el.scrollHeight')
                    scroll_top = await channel_list_container.evaluate('el => el.scrollTop')
                    client_height = await channel_list_container.evaluate('el => el.clientHeight')
                    
                    # Scroll down incrementally (not all the way at once)
                    scroll_amount = client_height * 0.8  # Scroll 80% of viewport
                    new_scroll = scroll_top + scroll_amount
                    await channel_list_container.evaluate(f'el => el.scrollTop = {new_scroll}')
                    await asyncio.sleep(0.2)  # Reduced from 0.4s - Wait for channels to load
                    
                    # Check if we've reached the bottom
                    new_scroll_top = await channel_list_container.evaluate('el => el.scrollTop')
                    new_height = await channel_list_container.evaluate('el => el.scrollHeight')
                    
                    # Check if we're at the bottom
                    if new_scroll_top + client_height >= new_height - 10:  # 10px tolerance
                        print(f"  Reached bottom of channel list after {i+1} scrolls")
                        break
                    
                    # Check if new channels loaded
                    if new_height == last_height:
                        no_change_count += 1
                        if no_change_count > 3:
                            # No new content for a while, might be at bottom
                            print(f"  No new channels loading after {i+1} scrolls")
                            break
                    else:
                        no_change_count = 0
                    
                    last_height = new_height
                    scroll_count = i + 1
                    
                    # Progress update every 20 scrolls
                    if (i + 1) % 20 == 0:
                        print(f"  Scrolled {i+1} times, found {new_height}px of content")
                
                print(f"  Scrolled channel list {scroll_count} times, total height: {last_height}px")
                
                # Scroll back to top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.5)  # Reduced from 1s - Wait for DOM to settle
            else:
                print("  ⚠ Could not find scrollable channel list container, proceeding with visible channels only")
                
        except Exception as e:
            print(f"  ⚠ Error scrolling channel list: {e}")
            import traceback
            traceback.print_exc()
    
    async def collect_channels_while_scrolling(self) -> List[Dict]:
        """Collect all channel elements while scrolling through the channel list."""
        all_channel_elements = []
        seen_hrefs = set()
        
        try:
            # Use cached channel list container
            channel_list_container = await self.get_channel_list_container()
            
            if channel_list_container:
                # Start from top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.3)  # Reduced from 0.5s
                
                # Expand categories at the start
                await self.expand_all_categories(scroll_container=channel_list_container)
                await asyncio.sleep(0.3)  # Reduced from 0.5s
                
                last_height = 0
                scroll_count = 0
                max_scrolls = 300  # Increased for more thorough scrolling
                no_change_count = 0
                last_channel_count = 0
                
                for i in range(max_scrolls):
                    # Expand categories periodically as we scroll (new categories might appear)
                    if i > 0 and i % 30 == 0:
                        await self.expand_all_categories(scroll_container=channel_list_container)
                        await asyncio.sleep(0.3)
                    
                    # Collect channels at current scroll position
                    channel_links = await self.page.query_selector_all('a[href^="/channels/"]')
                    
                    for link in channel_links:
                        try:
                            href = await link.get_attribute('href')
                            if href and href not in seen_hrefs:
                                seen_hrefs.add(href)
                                all_channel_elements.append(link)
                        except:
                            continue
                    
                    # Scroll down
                    current_height = await channel_list_container.evaluate('el => el.scrollHeight')
                    scroll_top = await channel_list_container.evaluate('el => el.scrollTop')
                    client_height = await channel_list_container.evaluate('el => el.clientHeight')
                    
                    # Check if we're at the absolute bottom
                    if scroll_top + client_height >= current_height - 5:  # 5px tolerance
                        # Try scrolling to absolute bottom one more time
                        await channel_list_container.evaluate('el => el.scrollTop = el.scrollHeight')
                        await asyncio.sleep(0.3)  # Reduced from 0.5s
                        
                        # Expand categories one final time at bottom
                        await self.expand_all_categories(scroll_container=channel_list_container)
                        await asyncio.sleep(0.3)  # Reduced from 0.5s
                        
                        # Final collection at bottom
                        final_links = await self.page.query_selector_all('a[href^="/channels/"]')
                        for link in final_links:
                            try:
                                href = await link.get_attribute('href')
                                if href and href not in seen_hrefs:
                                    seen_hrefs.add(href)
                                    all_channel_elements.append(link)
                            except:
                                continue
                        
                        print(f"  Reached absolute bottom after {i+1} scrolls")
                        break
                    
                    scroll_amount = client_height * 0.75  # Slightly smaller increments
                    new_scroll = scroll_top + scroll_amount
                    await channel_list_container.evaluate(f'el => el.scrollTop = {new_scroll}')
                    await asyncio.sleep(0.2)  # Reduced from 0.4s
                    
                    new_height = await channel_list_container.evaluate('el => el.scrollHeight')
                    
                    # Check if new channels were found
                    if len(all_channel_elements) == last_channel_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0
                    
                    # If no new channels for several scrolls and height hasn't changed, might be at bottom
                    if new_height == last_height and no_change_count > 3 and i > 10:
                        # Try scrolling to bottom one more time
                        await channel_list_container.evaluate('el => el.scrollTop = el.scrollHeight')
                        await asyncio.sleep(0.3)  # Reduced from 0.5s
                        break
                    
                    last_height = new_height
                    last_channel_count = len(all_channel_elements)
                    scroll_count = i + 1
                    
                    if (i + 1) % 20 == 0:
                        print(f"  Collected {len(all_channel_elements)} channels so far (scroll {i+1}, height: {new_height}px)")
                
                print(f"  Total collected: {len(all_channel_elements)} channels after {scroll_count} scrolls")
                
                # Scroll back to top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.3)  # Reduced from 0.5s
            
            return all_channel_elements
            
        except Exception as e:
            print(f"  Error collecting channels while scrolling: {e}")
            return all_channel_elements
    
    async def get_subnet_channels(self) -> List[Dict]:
        """
        Extract subnet channels from the Bittensor server.
        Subnet channels are organized under categories like "subnets", "subnets 2", "subnets 3".
        Each subnet channel name is informal but always includes the subnet number (e.g., "neza 99", "hippius 75").
        Category names are not important - we just need to find channels with numbers.
        """
        channels = []
        
        try:
            # Wait for channels to load
            await self.page.wait_for_selector('[class*="channel"], [class*="channelText"], [data-list-item-id*="channel"]', timeout=10000)
            await asyncio.sleep(1)  # Reduced from 2s - Give extra time for channels to render
            
            print("\nCollecting all channels while scrolling...")
            # Collect channels incrementally while scrolling (this also expands categories)
            channel_elements = await self.collect_channels_while_scrolling()
            
            # One more pass: scroll to bottom and expand categories there
            print("\nFinal pass: Ensuring we reach 'subnets 3' category...")
            try:
                # Use cached container
                channel_list_container = await self.get_channel_list_container()
                
                if channel_list_container:
                    # Scroll all the way to bottom
                    await channel_list_container.evaluate('el => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(0.5)  # Reduced from 1s
                    
                    # Expand categories at bottom (including "subnets 3")
                    await self.expand_all_categories(scroll_container=channel_list_container)
                    await asyncio.sleep(0.5)  # Reduced from 1s
                    
                    # Collect any new channels from bottom
                    bottom_links = await self.page.query_selector_all('a[href^="/channels/"]')
                    existing_hrefs = set()
                    for elem in channel_elements:
                        try:
                            href = await elem.get_attribute('href')
                            if href:
                                existing_hrefs.add(href)
                        except:
                            continue
                    
                    new_from_bottom = 0
                    for link in bottom_links:
                        try:
                            href = await link.get_attribute('href')
                            if href and href not in existing_hrefs:
                                channel_elements.append(link)
                                existing_hrefs.add(href)
                                new_from_bottom += 1
                        except:
                            continue
                    
                    if new_from_bottom > 0:
                        print(f"  Found {new_from_bottom} additional channels from bottom categories (subnets 3)")
            except Exception as e:
                print(f"  ⚠ Error in final bottom pass: {e}")
            
            await asyncio.sleep(0.5)  # Reduced from 1s
            
            # Final collection pass - get all channel links one more time
            final_channel_links = await self.page.query_selector_all('a[href^="/channels/"]')
            
            # Build set of hrefs we already have
            existing_hrefs = set()
            for elem in channel_elements:
                try:
                    href = await elem.get_attribute('href')
                    if href:
                        existing_hrefs.add(href)
                except:
                    continue
            
            # Add any new channels found in final scan
            new_channels_added = 0
            for link in final_channel_links:
                try:
                    href = await link.get_attribute('href')
                    if href and href not in existing_hrefs:
                        existing_hrefs.add(href)
                        channel_elements.append(link)
                        new_channels_added += 1
                except:
                    continue
            
            if new_channels_added > 0:
                print(f"  Added {new_channels_added} additional channels from final scan")
            
            print(f"\nTotal unique channels found: {len(channel_elements)}")
            print(f"Scanning channels to find subnets...")
            print("Looking for channels with numbers (subnet numbers)...")
            
            for element in channel_elements:
                try:
                    # Get channel name - handle aria-hidden elements
                    name = None
                    
                    # Try multiple selectors for name element (including aria-hidden)
                    name_selectors = [
                        '[class*="name"]',  # Matches class like "*-name"
                        'span[class*="name"]',
                        'div[class*="name"]',
                        'div[class*="content"]',
                        '[aria-label]'  # Fallback to aria-label
                    ]
                    
                    for name_selector in name_selectors:
                        name_elem = await element.query_selector(name_selector)
                        if name_elem:
                            # Try inner_text first
                            name = await name_elem.inner_text()
                            if not name or not name.strip():
                                # If inner_text fails (e.g., aria-hidden), try text_content
                                name = await name_elem.evaluate('el => el.textContent || el.innerText')
                            name = name.strip() if name else None
                            if name:
                                break
                    
                    # If no name found, try getting text directly from element
                    if not name:
                        name = await element.inner_text()
                        if not name or not name.strip():
                            # Try text_content as fallback
                            name = await element.evaluate('el => el.textContent || el.innerText')
                        name = name.strip() if name else None
                    
                    # Skip if no name
                    if not name:
                        continue
                    
                    # Skip category headers (like "subnets", "subnets 2", "subnets 3")
                    # These are not actual channels, just category labels
                    name_lower = name.lower()
                    if re.match(r'^subnets?\s+\d+$', name_lower.strip()):
                        print(f"  - Skipping category header: {name}")
                        continue
                    
                    # Skip channels with "ex" right after "・" (expired/past subnets)
                    # Examples: "xxxx・ex123" - these are past subnets, not active ones
                    # Note: "𝛼・apex・1" should NOT be skipped because "ex" is part of "apex", not right after "・"
                    # Pattern matches: "・ex" followed by a number (ex must come right after the separator)
                    if re.search(r'・ex\d+', name_lower):
                        print(f"  - Skipping expired subnet: {name} (contains '・ex' pattern)")
                        continue
                    
                    # Get channel link/ID - must have href to be a clickable channel
                    href = await element.get_attribute('href')
                    if not href:
                        # Try to get data attributes
                        data_id = await element.get_attribute('data-list-item-id')
                        if data_id and 'channel' in data_id:
                            href = f"/channels/{data_id}"
                    
                    # Must have href to be a valid channel
                    if not href:
                        continue
                    
                    # Check if channel name contains a number (subnet number)
                    # Examples: "neza 99", "hippius 75", "θ・vanta・8", etc.
                    # Extract all numbers from the channel name
                    numbers = re.findall(r'\d+', name)
                    
                    if numbers:
                        # Use the LAST number in the channel name as the subnet identifier
                        # Discord subnet channels have the format: "channelname・123" where 123 is the subnet
                        # This avoids false positives from numbers embedded in names like "agents4all"
                        try:
                            subnet_number = int(numbers[-1])  # Get the last number
                            
                            # Only accept if the last number is in valid subnet range (1-128)
                            if 1 <= subnet_number <= 128:
                                channels.append({
                                    'name': name,
                                    'href': href,
                                    'element': element,
                                    'subnet_number': subnet_number
                                })
                                print(f"  ✓ Found subnet channel: {name} (subnet {subnet_number})")
                            # If last number is outside 1-128 range, skip it
                        except:
                            pass
                            
                except Exception as e:
                    continue
            
            # Remove duplicates based on href (more reliable than name)
            seen_hrefs = set()
            unique_channels = []
            for ch in channels:
                if ch['href'] not in seen_hrefs:
                    seen_hrefs.add(ch['href'])
                    unique_channels.append(ch)
            
            # Filter to only include channels with subnet numbers 1-128
            filtered_channels = []
            for ch in unique_channels:
                subnet_num = ch.get('subnet_number')
                if subnet_num and 1 <= subnet_num <= 128:
                    filtered_channels.append(ch)
            
            # Sort channels by subnet number
            filtered_channels.sort(key=lambda ch: ch.get('subnet_number', 999))
            
            print(f"\n✓ Found {len(filtered_channels)} subnet channels (subnets 1-128)")
            if filtered_channels:
                subnet_numbers = [ch.get('subnet_number') for ch in filtered_channels if ch.get('subnet_number')]
                if subnet_numbers:
                    print(f"  Subnet numbers found: {min(subnet_numbers)} - {max(subnet_numbers)}")
                    print(f"  Total unique subnets: {len(set(subnet_numbers))}")
                    
                    # Show which subnet numbers are missing (if any)
                    found_set = set(subnet_numbers)
                    expected_set = set(range(1, 129))
                    missing = sorted(expected_set - found_set)
                    if missing:
                        print(f"  ⚠ Missing subnet numbers: {missing[:20]}{'...' if len(missing) > 20 else ''}")
            
            # Scroll back to top of channel list so first channels are visible
            # This ensures scrape_channel() can properly check for unread messages
            print(f"\n  Scrolling back to top of channel list...")
            try:
                # Use cached container
                channel_list_container = await self.get_channel_list_container()
                
                if channel_list_container:
                    # Scroll to top
                    await channel_list_container.evaluate('el => el.scrollTop = 0')
                    await asyncio.sleep(0.3)  # Reduced from 0.5s
                    print(f"  ✓ Scrolled to top of channel list")
                else:
                    print(f"  ⚠ Could not find channel list container to scroll to top")
            except Exception as e:
                print(f"  ⚠ Error scrolling to top: {e}")
            
            return filtered_channels
            
        except Exception as e:
            print(f"Error getting subnet channels: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def parse_discord_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse Discord timestamp string into datetime object."""
        if not timestamp_str:
            return None
        
        try:
            # Try ISO format first
            if 'T' in timestamp_str or '-' in timestamp_str:
                # Try parsing ISO format
                try:
                    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    pass
            
            # Try parsing datetime attribute
            if timestamp_str.startswith('20'):  # Likely ISO format
                try:
                    return datetime.strptime(timestamp_str[:19], '%Y-%m-%dT%H:%M:%S')
                except:
                    pass
            
            # Try relative time formats like "Today at 3:45 PM", "Yesterday at 2:30 PM"
            now = datetime.now()
            timestamp_lower = timestamp_str.lower()
            
            if 'today' in timestamp_lower:
                # Extract time like "3:45 PM"
                time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', timestamp_str, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    am_pm = time_match.group(3).upper()
                    if am_pm == 'PM' and hour != 12:
                        hour += 12
                    elif am_pm == 'AM' and hour == 12:
                        hour = 0
                    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            elif 'yesterday' in timestamp_lower:
                time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', timestamp_str, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    am_pm = time_match.group(3).upper()
                    if am_pm == 'PM' and hour != 12:
                        hour += 12
                    elif am_pm == 'AM' and hour == 12:
                        hour = 0
                    yesterday = now - timedelta(days=1)
                    return yesterday.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Try formats like "Dec 18, 2024 3:45 PM"
            try:
                return datetime.strptime(timestamp_str, '%b %d, %Y %I:%M %p')
            except:
                pass
            
            # If all else fails, return None (will use current time as fallback)
            return None
            
        except Exception as e:
            return None
    
    async def channel_has_unread(self, channel_elem) -> bool:
        """
        Check if a channel has unread messages by checking computed styles.
        
        Discord uses CSS variables for channel name colors:
        - Unread: color: var(--interactive-text-active); font-weight: 500+
        - Read: color: var(--channels-default); font-weight: normal (400)
        
        Since class names are dynamically generated (e.g., _2ea32c412048f708-name),
        we use computed styles which remain consistent regardless of class name changes.
        """
        try:
            if not channel_elem:
                return False
            
            # The channel element should be the <a> tag with href
            # Find the name element inside it (the div with dynamically generated class ending in "-name")
            name_elem = await channel_elem.query_selector('div[class*="name"]')
            
            if not name_elem:
                # Try alternative selectors
                name_elem = await channel_elem.query_selector('[class*="name"]')
            
            if not name_elem:
                # Try finding any text element inside the channel link
                name_elem = await channel_elem.query_selector('span, div')
            
            if name_elem:
                # Method 1: Check computed color against CSS variable values
                # This is the most reliable method as it works regardless of class name changes
                try:
                    is_unread_by_color = await name_elem.evaluate('''
                        el => {
                            const style = window.getComputedStyle(el);
                            const elementColor = style.color;
                            
                            // Get the CSS variable values from the document root
                            const rootStyle = getComputedStyle(document.documentElement);
                            const activeColor = rootStyle.getPropertyValue('--interactive-text-active').trim();
                            const defaultColor = rootStyle.getPropertyValue('--channels-default').trim();
                            
                            // Helper function to parse RGB/RGBA color string to comparable format
                            const parseColor = (colorStr) => {
                                if (!colorStr) return null;
                                // Try to create a temporary element to compute the color
                                const temp = document.createElement('div');
                                temp.style.color = colorStr;
                                document.body.appendChild(temp);
                                const computed = getComputedStyle(temp).color;
                                document.body.removeChild(temp);
                                return computed;
                            };
                            
                            // Compare element color with the active color (unread indicator)
                            const activeColorComputed = parseColor(activeColor);
                            const defaultColorComputed = parseColor(defaultColor);
                            
                            // If element color matches active color, it's unread
                            if (activeColorComputed && elementColor === activeColorComputed) {
                                return true;
                            }
                            
                            // If element color matches default color, it's read
                            if (defaultColorComputed && elementColor === defaultColorComputed) {
                                return false;
                            }
                            
                            // Alternative check: Compare raw RGB values
                            // Parse RGB values from color strings like "rgb(255, 255, 255)" or "rgba(255, 255, 255, 1)"
                            const parseRGB = (color) => {
                                const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
                                if (match) {
                                    return { r: parseInt(match[1]), g: parseInt(match[2]), b: parseInt(match[3]) };
                                }
                                return null;
                            };
                            
                            const elemRGB = parseRGB(elementColor);
                            const activeRGB = activeColorComputed ? parseRGB(activeColorComputed) : null;
                            const defaultRGB = defaultColorComputed ? parseRGB(defaultColorComputed) : null;
                            
                            // Check if element color is closer to active (unread) or default (read)
                            if (elemRGB && activeRGB && defaultRGB) {
                                // Calculate color distance
                                const distToActive = Math.sqrt(
                                    Math.pow(elemRGB.r - activeRGB.r, 2) +
                                    Math.pow(elemRGB.g - activeRGB.g, 2) +
                                    Math.pow(elemRGB.b - activeRGB.b, 2)
                                );
                                const distToDefault = Math.sqrt(
                                    Math.pow(elemRGB.r - defaultRGB.r, 2) +
                                    Math.pow(elemRGB.g - defaultRGB.g, 2) +
                                    Math.pow(elemRGB.b - defaultRGB.b, 2)
                                );
                                
                                // If closer to active color (and significantly different from default), it's unread
                                if (distToActive < distToDefault && distToActive < 50) {
                                    return true;
                                }
                            }
                            
                            return null;  // Could not determine by color
                        }
                    ''')
                    
                    if is_unread_by_color is True:
                        return True
                    elif is_unread_by_color is False:
                        return False
                    # If null, continue to other checks
                except Exception as e:
                    pass
                
                # Method 2: Check font-weight (Discord uses 500+ for unread channels)
                try:
                    font_weight = await name_elem.evaluate('el => window.getComputedStyle(el).fontWeight')
                    
                    if font_weight:
                        # Check if bold - Discord uses 500+ for unread channels
                        if font_weight == 'bold':
                            return True
                        try:
                            fw_num = int(font_weight)
                            # Discord uses 500 or higher for unread (bold) channels
                            if fw_num >= 500:
                                return True
                        except:
                            # If it's a string like "500", "600", "700", check directly
                            if font_weight in ['500', '600', '700', '800', '900']:
                                return True
                except Exception as e:
                    pass
                
                # Method 3: Check font-weight via alternative approach
                try:
                    is_bold = await name_elem.evaluate('''
                        el => {
                            const style = window.getComputedStyle(el);
                            const fw = style.fontWeight;
                            if (fw === "bold") return true;
                            const fwNum = parseInt(fw);
                            return fwNum >= 500;
                        }
                    ''')
                    if is_bold:
                        return True
                except:
                    pass
            
            # Method 4: Check the <a> element itself for bold styling
            try:
                link_font_weight = await channel_elem.evaluate('el => window.getComputedStyle(el).fontWeight')
                if link_font_weight:
                    if link_font_weight == 'bold':
                        return True
                    try:
                        if int(link_font_weight) >= 500:
                            return True
                    except:
                        if link_font_weight in ['500', '600', '700', '800', '900']:
                            return True
            except:
                pass
            
            # Method 5: Check for unread class on the channel element or its parents
            channel_class = await channel_elem.get_attribute('class') or ""
            if 'unread' in channel_class.lower():
                return True
            
            # Method 6: Check parent wrapper for unread indicators
            try:
                parent = await channel_elem.evaluate_handle('el => el.parentElement')
                if parent:
                    parent_class = await parent.evaluate('el => el.className || ""')
                    if 'unread' in parent_class.lower():
                        return True
                    
                    # Check if parent has bold styling
                    parent_font_weight = await parent.evaluate('el => window.getComputedStyle(el).fontWeight')
                    if parent_font_weight:
                        if parent_font_weight == 'bold':
                            return True
                        try:
                            if int(parent_font_weight) >= 500:
                                return True
                        except:
                            if parent_font_weight in ['500', '600', '700', '800', '900']:
                                return True
            except:
                pass
            
            # Method 7: Check for unread badge/pill indicator
            unread_badge = await channel_elem.query_selector('[class*="unread"], [class*="unreadBadge"], [class*="unreadCount"]')
            if unread_badge:
                return True
            
            # Method 8: Check for the small white pill/indicator on the left side of unread channels
            try:
                # Discord shows a small white pill on the left side of unread channels
                unread_pill = await channel_elem.evaluate('''
                    el => {
                        // Check parent and siblings for unread indicators
                        const parent = el.parentElement;
                        if (!parent) return false;
                        
                        // Look for elements with opacity or visibility indicating unread
                        const siblings = parent.querySelectorAll('div, span');
                        for (const sib of siblings) {
                            const style = window.getComputedStyle(sib);
                            // The unread pill is usually a small white element with specific dimensions
                            if (sib.offsetWidth > 0 && sib.offsetWidth < 10 && sib.offsetHeight > 5) {
                                const bgColor = style.backgroundColor;
                                // White or light-colored background indicates unread pill
                                if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                                    return true;
                                }
                            }
                        }
                        return false;
                    }
                ''')
                if unread_pill:
                    return True
            except:
                pass
            
            return False
        except Exception as e:
            return False
    
    async def has_unread_messages_in_view(self) -> bool:
        """Check if the current channel view shows unread messages."""
        try:
            # Look for unread markers in the message view
            unread_selectors = [
                'div[class*="newMessagesBar"]',
                'div[class*="unreadBar"]',
                'div[class*="newMessages"]',
                '[class*="unread"]',
                '[aria-label*="New messages"]',
                '[aria-label*="new messages"]'
            ]
            
            for selector in unread_selectors:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    return True
            
            return False
        except:
            return False
    
    async def find_unread_marker_position(self):
        """Find the position of the unread marker in the message view."""
        try:
            unread_marker_selectors = [
                'div[class*="newMessagesBar"]',
                'div[class*="unreadBar"]',
                'div[class*="newMessages"]',
                'div[aria-label*="New messages"]',
                'div[aria-label*="new messages"]'
            ]
            
            for selector in unread_marker_selectors:
                marker = await self.page.query_selector(selector)
                if marker:
                    # Get marker position
                    box = await marker.bounding_box()
                    if box:
                        return box['y']
            return None
        except:
            return None
    
    async def scroll_to_load_unread_messages(self, max_scrolls: int = 10):
        """
        Handle scrolling for unread messages.
        Discord behavior:
        - If few unread: messages are visible immediately
        - If many unread: Discord auto-scrolls to first unread message
        """
        try:
            # Find the message container
            message_container_selectors = [
                '[class*="messages"]',
                '[class*="scroller"]',
                '[class*="messageContainer"]',
                'div[class*="scrollerInner"]'
            ]
            
            message_container = None
            for selector in message_container_selectors:
                try:
                    message_container = await self.page.query_selector(selector)
                    if message_container:
                        break
                except:
                    continue
            
            if not message_container:
                scrollable = await self.page.query_selector('[class*="scrollable"], [class*="scrollerInner"]')
                if scrollable:
                    message_container = scrollable
            
            if not message_container:
                return
            
            # Wait for Discord to auto-scroll to unread messages (if many unread)
            await asyncio.sleep(1)  # Reduced from 2s
            
            # Check if we're already at unread messages (Discord auto-scrolled)
            has_unread_marker = await self.has_unread_messages_in_view()
            
            if has_unread_marker:
                print(f"  📬 Found unread marker - Discord auto-scrolled to unread messages")
                
                # Find the unread marker position
                marker_y = await self.find_unread_marker_position()
                
                if marker_y:
                    # Scroll to position slightly above the marker to load messages before it
                    container_box = await message_container.bounding_box()
                    if container_box:
                        container_y = container_box['y']
                        relative_y = marker_y - container_y
                        # Scroll to show messages around the marker
                        await message_container.evaluate(f'el => el.scrollTop = {max(0, relative_y - 200)}')
                        await asyncio.sleep(0.3)  # Reduced from 0.5s
                
                # Scroll down from marker to load all unread messages
                for i in range(5):  # Scroll down a few times to load unread messages
                    current_scroll = await message_container.evaluate('el => el.scrollTop')
                    scroll_height = await message_container.evaluate('el => el.scrollHeight')
                    client_height = await message_container.evaluate('el => el.clientHeight')
                    
                    # If we're near the bottom, stop
                    if current_scroll + client_height >= scroll_height - 50:
                        break
                    
                    # Scroll down
                    await message_container.evaluate('el => el.scrollTop += 400')
                    await asyncio.sleep(0.3)
            else:
                # Few unread messages - they should be visible at bottom
                print(f"  📬 Few unread messages - checking bottom of view")
                
                # Scroll to bottom to see unread messages
                await message_container.evaluate('el => el.scrollTop = el.scrollHeight')
                await asyncio.sleep(0.5)
                
                # Scroll up a bit to load messages above
                await message_container.evaluate('el => el.scrollTop -= 300')
                await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"  Error scrolling to unread: {e}")
            import traceback
            traceback.print_exc()
    
    async def mark_channel_as_read(self):
        """
        Mark the current channel as read by scrolling to the bottom.
        Discord marks channels as read when you scroll to the bottom of the message view.
        This will update the channel's read state in your Discord account.
        """
        try:
            print(f"  📖 Marking channel as read...")
            
            # Find the message container - try multiple approaches
            message_container = None
            
            # Method 1: Look for the main message scroller
            selectors = [
                'div[class*="scrollerInner"]',
                'div[class*="scroller"][class*="message"]',
                '[class*="messages"]',
                '[class*="messageContainer"]',
                'div[class*="scroller"]'
            ]
            
            for selector in selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for elem in elements:
                        # Check if it's scrollable and in the message area
                        is_scrollable = await elem.evaluate('el => el.scrollHeight > el.clientHeight')
                        if is_scrollable:
                            # Check if it's in the right area (not sidebar)
                            box = await elem.bounding_box()
                            if box and box['x'] > 200:  # Message area is on the right
                                message_container = elem
                                print(f"  Found message container: {selector}")
                                break
                    if message_container:
                        break
                except:
                    continue
            
            if not message_container:
                # Method 2: Find by clicking in message area and finding focused element
                try:
                    # Click in the message area to focus it
                    message_area = await self.page.query_selector('[class*="chat"], [class*="message"], [class*="content"]')
                    if message_area:
                        await message_area.click()
                        await asyncio.sleep(0.2)
                    
                    # Find the scrollable container
                    scrollable = await self.page.query_selector('[class*="scroller"]')
                    if scrollable:
                        message_container = scrollable
                except:
                    pass
            
            if message_container:
                # Get container info
                scroll_height = await message_container.evaluate('el => el.scrollHeight')
                client_height = await message_container.evaluate('el => el.clientHeight')
                initial_scroll = await message_container.evaluate('el => el.scrollTop')
                
                print(f"  Scroll info: height={scroll_height}, client={client_height}, current={initial_scroll}")
                
                # Method 1: Use keyboard to scroll to bottom (more reliable)
                try:
                    # Focus the message container
                    await message_container.focus()
                    await asyncio.sleep(0.1)  # Reduced from 0.2s
                    
                    # Press End key to go to bottom
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(0.3)  # Reduced from 0.5s
                    
                    # Press End again to ensure we're at bottom
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(0.3)  # Reduced from 0.5s
                except Exception as e:
                    print(f"  ⚠ Keyboard scroll failed: {e}")
                
                # Method 2: Programmatic scroll with multiple attempts
                max_attempts = 5
                for attempt in range(max_attempts):
                    current_scroll = await message_container.evaluate('el => el.scrollTop')
                    current_height = await message_container.evaluate('el => el.scrollHeight')
                    current_client = await message_container.evaluate('el => el.clientHeight')
                    
                    # Calculate if we're at bottom (with 5px tolerance)
                    at_bottom = (current_scroll + current_client >= current_height - 5)
                    
                    if at_bottom:
                        print(f"  ✓ Reached bottom after {attempt + 1} attempt(s)")
                        break
                    
                    # Scroll to bottom
                    await message_container.evaluate('el => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(0.3)
                    
                    # Trigger scroll events
                    await message_container.evaluate('''
                        el => {
                            // Trigger multiple scroll-related events
                            const scrollEvent = new Event('scroll', { bubbles: true, cancelable: true });
                            el.dispatchEvent(scrollEvent);
                            
                            // Also trigger scrollend if supported
                            if ('scrollend' in window) {
                                const scrollEndEvent = new Event('scrollend', { bubbles: true });
                                el.dispatchEvent(scrollEndEvent);
                            }
                        }
                    ''')
                    await asyncio.sleep(0.3)
                
                # Final verification and scroll
                final_scroll = await message_container.evaluate('el => el.scrollTop')
                final_height = await message_container.evaluate('el => el.scrollHeight')
                final_client = await message_container.evaluate('el => el.clientHeight')
                
                # One more scroll to absolute bottom
                await message_container.evaluate('el => el.scrollTop = el.scrollHeight')
                await asyncio.sleep(0.3)  # Reduced from 0.5s
                
                # Trigger final scroll event and Discord-specific events
                await message_container.evaluate('''
                    el => {
                        el.scrollTop = el.scrollHeight;
                        
                        // Trigger standard scroll event
                        const scrollEvent = new Event('scroll', { bubbles: true, cancelable: true });
                        el.dispatchEvent(scrollEvent);
                        
                        // Trigger scrollend if supported
                        if ('scrollend' in window) {
                            const scrollEndEvent = new Event('scrollend', { bubbles: true });
                            el.dispatchEvent(scrollEndEvent);
                        }
                        
                        // Trigger input event (Discord sometimes listens to this)
                        const inputEvent = new Event('input', { bubbles: true });
                        el.dispatchEvent(inputEvent);
                        
                        // Trigger change event
                        const changeEvent = new Event('change', { bubbles: true });
                        el.dispatchEvent(changeEvent);
                    }
                ''')
                
                # Also try to trigger Discord's read state update by interacting with the viewport
                try:
                    # Click in the message area to ensure focus
                    message_area = await self.page.query_selector('[class*="chat"], [class*="message"]')
                    if message_area:
                        await message_area.click()
                        await asyncio.sleep(0.2)
                except:
                    pass
                
                await asyncio.sleep(0.8)  # Reduced from 1.5s - Give Discord time to update read state
                
                # Verify final position
                verify_scroll = await message_container.evaluate('el => el.scrollTop')
                verify_height = await message_container.evaluate('el => el.scrollHeight')
                verify_client = await message_container.evaluate('el => el.clientHeight')
                
                at_bottom_final = (verify_scroll + verify_client >= verify_height - 10)
                
                if at_bottom_final:
                    print(f"  ✓ Channel marked as read (scrolled to bottom: {verify_scroll}/{verify_height})")
                else:
                    print(f"  ⚠ May not be at bottom (scroll: {verify_scroll}, height: {verify_height})")
            else:
                print(f"  ⚠ Could not find message container to mark as read")
                # Fallback: Try using keyboard End key on the page
                try:
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(0.3)  # Reduced from 0.5s
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(0.3)  # Reduced from 0.5s
                    print(f"  ✓ Used keyboard fallback to scroll to bottom")
                except:
                    print(f"  ✗ Could not mark channel as read")
        except Exception as e:
            print(f"  ⚠ Error marking channel as read: {e}")
            import traceback
            traceback.print_exc()
    
    async def scroll_to_load_messages(self, max_scrolls: int = 10):
        """Scroll to load messages - minimal scrolling for unread mode."""
        try:
            message_container_selectors = [
                '[class*="messages"]',
                '[class*="scroller"]',
                '[class*="messageContainer"]'
            ]
            
            message_container = None
            for selector in message_container_selectors:
                try:
                    message_container = await self.page.query_selector(selector)
                    if message_container:
                        break
                except:
                    continue
            
            if not message_container:
                scrollable = await self.page.query_selector('[class*="scrollable"], [class*="scrollerInner"]')
                if scrollable:
                    message_container = scrollable
            
            if message_container:
                if self.scrape_unread_only:
                    # Handle unread messages (Discord auto-scrolls if many unread)
                    await self.scroll_to_load_unread_messages()
                else:
                    # Scroll to top for all messages
                    await message_container.evaluate('element => element.scrollTop = 0')
                    await asyncio.sleep(0.3)
        except Exception as e:
            print(f"Error scrolling: {e}")
    
    async def extract_messages_from_channel(self) -> List[Dict]:
        """Extract messages from the current channel (unread messages if enabled)."""
        messages = []
        
        try:
            # Wait for Discord to auto-scroll to unread messages (if many unread)
            # Discord needs time to position the view at unread messages
            await asyncio.sleep(1.5)  # Reduced from 2.5s
            
            # Scroll to load messages (handles unread messages appropriately)
            await self.scroll_to_load_messages()
            
            # Wait a bit more for messages to render after scrolling
            await asyncio.sleep(0.5)  # Reduced from 1s
            
            # Try multiple selectors for message elements
            message_selectors = [
                '[class*="message"]',
                '[class*="messageGroup"]',
                'li[class*="message"]',
                'div[class*="message"]'
            ]
            
            message_elements = []
            for selector in message_selectors:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    message_elements = elements
                    print(f"  Found {len(elements)} message elements")
                    break
            
            if not message_elements:
                print("  No messages found with standard selectors. Trying alternative approach...")
                # Alternative: look for message-like divs
                all_divs = await self.page.query_selector_all('div')
                message_elements = [d for d in all_divs if 'message' in (await d.get_attribute('class') or '').lower()]
            
            # Extract messages - focus on unread messages if in unread mode
            unread_marker_y = None
            if self.scrape_unread_only:
                unread_marker_y = await self.find_unread_marker_position()
                if unread_marker_y:
                    print(f"  📍 Unread marker found - extracting messages below marker")
                else:
                    print(f"  📍 No unread marker found - extracting visible messages (likely few unread)")
            
            # Get viewport bounds to filter messages
            viewport_height = await self.page.evaluate('window.innerHeight')
            
            for element in message_elements:
                try:
                    element_box = await element.bounding_box()
                    if not element_box:
                        continue
                    
                    element_y = element_box['y']
                    
                    # If we have an unread marker, only extract messages at or below it
                    if self.scrape_unread_only and unread_marker_y:
                        # Unread messages are below the marker
                        # Only extract messages that are at or below the unread marker
                        if element_y < unread_marker_y - 100:  # 100px tolerance above marker
                            continue  # Skip messages too far above the marker (already read)
                    elif self.scrape_unread_only:
                        # No marker found - likely few unread messages visible
                        # Extract messages in the lower portion of viewport (where unread usually are)
                        viewport_bottom = viewport_height
                        if element_y > viewport_bottom - 600:  # Lower 600px of viewport
                            # This is likely an unread message
                            pass
                        else:
                            # Skip messages in upper portion (likely already read)
                            continue
                    
                    message_data = await self.extract_message_data(element)
                    if message_data:
                        messages.append(message_data)
                except Exception as e:
                    continue
            
            # Remove duplicates based on message content and timestamp
            seen = set()
            unique_messages = []
            for msg in messages:
                key = (msg.get('content', ''), msg.get('timestamp', ''))
                if key not in seen:
                    seen.add(key)
                    unique_messages.append(msg)
            
            return unique_messages
            
        except Exception as e:
            print(f"Error extracting messages: {e}")
            return []
    
    async def extract_message_data(self, element) -> Optional[Dict]:
        """Extract data from a single message element."""
        try:
            # Get username
            username = None
            username_selectors = [
                '[class*="username"]',
                '[class*="author"]',
                'span[class*="username"]',
                'strong'
            ]
            
            for selector in username_selectors:
                username_elem = await element.query_selector(selector)
                if username_elem:
                    username = await username_elem.inner_text()
                    username = username.strip()
                    if username:
                        break
            
            # Get message content
            content = None
            content_selectors = [
                '[class*="content"]',
                '[class*="messageContent"]',
                'div[class*="markup"]',
                'span[class*="text"]'
            ]
            
            for selector in content_selectors:
                content_elem = await element.query_selector(selector)
                if content_elem:
                    content = await content_elem.inner_text()
                    content = content.strip()
                    if content and len(content) > 0:
                        break
            
            # Get timestamp
            timestamp = None
            timestamp_selectors = [
                '[class*="timestamp"]',
                'time',
                '[class*="time"]'
            ]
            
            for selector in timestamp_selectors:
                timestamp_elem = await element.query_selector(selector)
                if timestamp_elem:
                    timestamp = await timestamp_elem.inner_text()
                    if not timestamp:
                        timestamp = await timestamp_elem.get_attribute('datetime')
                    if timestamp:
                        break
            
            # Get channel name (from current page)
            channel_name = None
            try:
                channel_elem = await self.page.query_selector('[class*="channelName"], h1, [class*="title"]')
                if channel_elem:
                    channel_name = await channel_elem.inner_text()
                    channel_name = channel_name.strip()
            except:
                pass
            
            if username and content:
                return {
                    'username': username,
                    'content': content,
                    'timestamp': timestamp or datetime.now().isoformat(),
                    'channel': channel_name or 'Unknown',
                    'scraped_at': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            return None
    
    async def scrape_channel(self, channel_name: str, channel_href: str = None):
        """Scrape messages from a specific channel."""
        print(f"\n{'='*60}")
        print(f"Checking channel: {channel_name}")
        print(f"{'='*60}")
        
        try:
            # If scraping unread only, check for unread indicator (bold text) before opening channel
            if self.scrape_unread_only:
                # Look for unread indicator on the channel in the sidebar
                try:
                    # Find the channel element
                    channel_elem = None
                    if channel_href:
                        channel_elem = await self.page.query_selector(f'a[href*="{channel_href}"]')
                    
                    if channel_elem:
                        # Scroll the channel into view in the sidebar before checking
                        await channel_elem.scroll_into_view_if_needed()
                        await asyncio.sleep(0.1)  # Brief pause for render
                        
                        # Check if channel name is bold (unread indicator)
                        has_unread = await self.channel_has_unread(channel_elem)
                        if not has_unread:
                            print(f"  ⏭️  Channel name not bold (no unread), skipping")
                            return
                        else:
                            print(f"  ✓ Channel has unread messages (bold name)")
                    else:
                        # If we can't find the element, proceed anyway
                        print(f"  ⚠ Could not find channel element, proceeding...")
                except Exception as e:
                    # If we can't check, proceed anyway
                    print(f"  ⚠ Error checking unread status: {e}, proceeding...")
                    pass
            
            print(f"Scraping channel: {channel_name}")
            
            # Click on the channel if href is provided
            if channel_href:
                try:
                    # Try to click the channel link
                    channel_link = await self.page.query_selector(f'a[href*="{channel_href}"]')
                    if channel_link:
                        await channel_link.click()
                        await asyncio.sleep(1)  # Reduced from 1.5s
                    else:
                        # Alternative: try to find and click by text
                        await self.page.click(f'text={channel_name}')
                        await asyncio.sleep(1)  # Reduced from 1.5s
                except:
                    # Alternative: try to find and click by text
                    try:
                        await self.page.click(f'text={channel_name}')
                        await asyncio.sleep(1)  # Reduced from 1.5s
                    except:
                        pass
            
            # Extract messages (already filtered by time limit)
            messages = await self.extract_messages_from_channel()
            
            if self.scrape_unread_only:
                print(f"\n  Found {len(messages)} unread messages")
            else:
                print(f"\n  Found {len(messages)} messages")
            
            # Print ALL messages for debugging
            if messages:
                print(f"\n  ALL MESSAGES FOUND IN '{channel_name}':")
                print(f"  {'-'*60}")
                unique_usernames = set()
                for i, msg in enumerate(messages, 1):
                    username = msg.get('username', 'Unknown')
                    content_preview = msg.get('content', '')[:50] + ('...' if len(msg.get('content', '')) > 50 else '')
                    timestamp = msg.get('timestamp', 'N/A')
                    unique_usernames.add(username)
                    print(f"  {i:3d}. User: {username:30s} | Content: {content_preview}")
                
                print(f"\n  Unique usernames found ({len(unique_usernames)}):")
                for uname in sorted(unique_usernames):
                    print(f"    - {uname}")
                print(f"  {'-'*60}\n")
            
            # Filter messages by target username - improved matching
            # Include messages FROM target user OR messages that MENTION target user in content
            filtered_messages = []
            target_username_normalized = self.normalize_username(self.target_username)
            
            for msg in messages:
                msg_username = msg.get('username', '')
                msg_content = msg.get('content', '')
                msg_username_normalized = self.normalize_username(msg_username)
                msg_content_normalized = msg_content.lower() if msg_content else ''
                
                # Check if message is FROM target user
                matches_username = (
                    target_username_normalized in msg_username_normalized or
                    msg_username_normalized in target_username_normalized or
                    self.target_username in msg_username or
                    msg_username in self.target_username
                )
                
                # Check if message content MENTIONS target user
                matches_content = (
                    self.target_username.lower() in msg_content_normalized or
                    target_username_normalized in msg_content_normalized or
                    self.target_username in msg_content
                )
                
                if matches_username or matches_content:
                    filtered_messages.append(msg)
            
            if filtered_messages:
                # Count messages from user vs messages mentioning user
                from_user = sum(1 for msg in filtered_messages 
                              if self.normalize_username(self.target_username) in self.normalize_username(msg.get('username', '')))
                mentioning_user = len(filtered_messages) - from_user
                
                print(f"  ✓ Found {len(filtered_messages)} messages matching '{self.target_username}'")
                if from_user > 0:
                    print(f"    - {from_user} message(s) FROM '{self.target_username}'")
                if mentioning_user > 0:
                    print(f"    - {mentioning_user} message(s) MENTIONING '{self.target_username}'")
                
                for msg in filtered_messages:
                    msg['channel'] = channel_name
                    self.messages.append(msg)
            else:
                print(f"  - No messages matching '{self.target_username}' in this channel")
            
            # Mark channel as read by scrolling to the bottom
            # This ensures the channel won't show as unread in the next scraping session
            # Only mark as read if we found messages (meaning there were unread messages)
            if self.scrape_unread_only and messages:
                await self.mark_channel_as_read()
            
        except Exception as e:
            print(f"  ✗ Error scraping channel {channel_name}: {e}")
            import traceback
            traceback.print_exc()
    
    def normalize_username(self, username: str) -> str:
        """Normalize username for comparison (handles special characters)."""
        if not username:
            return ""
        # Convert to lowercase and remove extra whitespace
        normalized = username.lower().strip()
        # Remove common Discord formatting characters but keep special chars like τ
        normalized = normalized.replace('[', '').replace(']', '').replace(',', '').replace(' ', '')
        return normalized
    
    async def scrape_subnet_channels(self):
        """Scrape messages from all subnet channels in Bittensor server."""
        print("\n" + "="*60)
        print(f"Starting to scrape subnet channels from {self.target_server} server...")
        print(f"Filtering messages from user: {self.target_username}")
        print("="*60 + "\n")
        
        # Get subnet channels
        channels = await self.get_subnet_channels()
        
        if not channels:
            print("⚠ No subnet channels found automatically.")
            print("Please manually navigate to a subnet channel, and the scraper will collect messages.")
            input("Press Enter after you've navigated to a subnet channel...")
            messages = await self.extract_messages_from_channel()
            
            # Print all messages for debugging
            if messages:
                print(f"\n  Found {len(messages)} total messages")
                print(f"\n  ALL MESSAGES FOUND:")
                unique_usernames = set()
                for i, msg in enumerate(messages, 1):
                    username = msg.get('username', 'Unknown')
                    content_preview = msg.get('content', '')[:50] + ('...' if len(msg.get('content', '')) > 50 else '')
                    unique_usernames.add(username)
                    print(f"  {i:3d}. User: {username:30s} | Content: {content_preview}")
                
                print(f"\n  Unique usernames found ({len(unique_usernames)}):")
                for uname in sorted(unique_usernames):
                    print(f"    - {uname}")
            
            # Use improved matching
            # Include messages FROM target user OR messages that MENTION target user in content
            target_username_normalized = self.normalize_username(self.target_username)
            filtered = []
            for msg in messages:
                msg_username = msg.get('username', '')
                msg_content = msg.get('content', '')
                msg_username_normalized = self.normalize_username(msg_username)
                msg_content_normalized = msg_content.lower() if msg_content else ''
                
                # Check if message is FROM target user
                matches_username = (
                    target_username_normalized in msg_username_normalized or
                    msg_username_normalized in target_username_normalized or
                    self.target_username in msg_username or
                    msg_username in self.target_username
                )
                
                # Check if message content MENTIONS target user
                matches_content = (
                    self.target_username.lower() in msg_content_normalized or
                    target_username_normalized in msg_content_normalized or
                    self.target_username in msg_content
                )
                
                if matches_username or matches_content:
                    filtered.append(msg)
            
            self.messages.extend(filtered)
        else:
            print(f"Found {len(channels)} subnet channels. Starting to scrape...\n")
            
            for i, channel in enumerate(channels, 1):
                print(f"[{i}/{len(channels)}] Processing subnet: {channel['name']}")
                await self.scrape_channel(channel['name'], channel.get('href'))
                await asyncio.sleep(0.8)  # Reduced from 1.5s - Small delay between channels
        
        # Count messages from user vs messages mentioning user
        from_user = sum(1 for msg in self.messages 
                      if self.normalize_username(self.target_username) in self.normalize_username(msg.get('username', '')))
        mentioning_user = len(self.messages) - from_user
        
        print(f"\n✓ Scraping complete! Found {len(self.messages)} messages matching '{self.target_username}' across {len(channels)} subnets")
        if from_user > 0:
            print(f"  - {from_user} message(s) FROM '{self.target_username}'")
        if mentioning_user > 0:
            print(f"  - {mentioning_user} message(s) MENTIONING '{self.target_username}'")
    
    async def send_to_telegram(self) -> bool:
        """
        Send scraped messages to Telegram channel.
        
        Returns:
            True if messages were sent successfully, False otherwise
        """
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠ Telegram not configured (missing bot token or chat ID)")
            return False
        
        if not self.messages:
            print("⚠ No messages to send to Telegram")
            return False
        
        print(f"\n📱 Sending {len(self.messages)} messages to Telegram...")
        
        telegram_api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Send a summary header first
                header_text = (
                    f"🔔 *Discord Scraper Results*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 Server: `{self.target_server}`\n"
                    f"👤 User: `{self.target_username}`\n"
                    f"📊 Messages found: *{len(self.messages)}*\n"
                    f"🕐 Scraped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                
                # Send header
                async with session.post(telegram_api_url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": header_text,
                    "parse_mode": "Markdown"
                }) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"  ✗ Failed to send header: {error_text}")
                        return False
                    print(f"  ✓ Sent summary header")
                
                await asyncio.sleep(0.5)  # Rate limiting
                
                # Group messages by channel
                messages_by_channel: Dict[str, List[Dict]] = {}
                for msg in self.messages:
                    channel = msg.get('channel', 'Unknown')
                    if channel not in messages_by_channel:
                        messages_by_channel[channel] = []
                    messages_by_channel[channel].append(msg)
                
                # Send messages grouped by channel
                sent_count = 0
                for channel, channel_messages in messages_by_channel.items():
                    # Format messages for this channel
                    message_texts = []
                    for msg in channel_messages:
                        username = msg.get('username', 'Unknown')
                        content = msg.get('content', '')
                        timestamp = msg.get('timestamp', '')
                        
                        # Escape special Markdown characters in content
                        content_escaped = content.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')
                        
                        # Truncate long messages
                        if len(content_escaped) > 500:
                            content_escaped = content_escaped[:500] + "..."
                        
                        message_texts.append(
                            f"👤 *{username}*\n"
                            f"💬 {content_escaped}\n"
                            f"🕐 _{timestamp}_"
                        )
                    
                    # Combine messages for this channel
                    channel_text = f"📢 *Channel: #{channel}*\n\n" + "\n\n───────────\n\n".join(message_texts)
                    
                    # Split if too long (Telegram limit is 4096 chars)
                    if len(channel_text) > 4000:
                        # Send in chunks
                        chunks = []
                        current_chunk = f"📢 *Channel: #{channel}* (continued)\n\n"
                        
                        for msg_text in message_texts:
                            if len(current_chunk) + len(msg_text) + 20 > 4000:
                                chunks.append(current_chunk)
                                current_chunk = f"📢 *Channel: #{channel}* (continued)\n\n"
                            current_chunk += msg_text + "\n\n───────────\n\n"
                        
                        if current_chunk.strip():
                            chunks.append(current_chunk)
                        
                        # Send each chunk
                        for i, chunk in enumerate(chunks):
                            async with session.post(telegram_api_url, json={
                                "chat_id": self.telegram_chat_id,
                                "text": chunk,
                                "parse_mode": "Markdown"
                            }) as response:
                                if response.status == 200:
                                    sent_count += 1
                                else:
                                    # Try without Markdown if it fails
                                    async with session.post(telegram_api_url, json={
                                        "chat_id": self.telegram_chat_id,
                                        "text": chunk.replace('*', '').replace('_', '').replace('`', '')
                                    }) as retry_response:
                                        if retry_response.status == 200:
                                            sent_count += 1
                            await asyncio.sleep(0.3)  # Rate limiting
                    else:
                        # Send as single message
                        async with session.post(telegram_api_url, json={
                            "chat_id": self.telegram_chat_id,
                            "text": channel_text,
                            "parse_mode": "Markdown"
                        }) as response:
                            if response.status == 200:
                                sent_count += 1
                            else:
                                # Try without Markdown if it fails
                                async with session.post(telegram_api_url, json={
                                    "chat_id": self.telegram_chat_id,
                                    "text": channel_text.replace('*', '').replace('_', '').replace('`', '')
                                }) as retry_response:
                                    if retry_response.status == 200:
                                        sent_count += 1
                        await asyncio.sleep(0.3)  # Rate limiting
                
                print(f"  ✓ Sent {sent_count} message groups to Telegram")
                return True
                
        except aiohttp.ClientError as e:
            print(f"  ✗ Network error sending to Telegram: {e}")
            return False
        except Exception as e:
            print(f"  ✗ Error sending to Telegram: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_no_messages_notification(self):
        """Send a notification to Telegram when no messages are found."""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
        
        telegram_api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        
        notification_text = (
            f"📭 *No Messages Found*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Server: `{self.target_server}`\n"
            f"👤 User: `{self.target_username}`\n"
            f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"No new messages from the target user were found."
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(telegram_api_url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": notification_text,
                    "parse_mode": "Markdown"
                }) as response:
                    if response.status == 200:
                        print("📱 Sent 'no messages found' notification to Telegram")
                        return True
                    else:
                        print(f"⚠ Failed to send Telegram notification: {response.status}")
                        return False
        except Exception as e:
            print(f"⚠ Error sending Telegram notification: {e}")
            return False
    
    async def run(self, check_interval: int = 10):
        """
        Main execution method with real-time monitoring.
        
        Args:
            check_interval: Seconds to wait between scraping cycles
        """
        try:
            await self.setup_browser()
            
            print("\n" + "="*60)
            print("🔄 REAL-TIME MONITORING MODE")
            print(f"   Checking for unread messages every {check_interval} seconds")
            print("   Press Ctrl+C to stop")
            print("="*60 + "\n")
            
            cycle_count = 0
            
            while True:
                cycle_count += 1
                print(f"\n{'─'*60}")
                print(f"🔍 Scrape cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'─'*60}")
                
                # Clear messages from previous cycle to avoid duplicates
                self.messages = []
                
                # Scroll channel list back to top before scraping
                container = await self.get_channel_list_container()
                if container:
                    await container.evaluate('el => el.scrollTop = 0')
                    await asyncio.sleep(0.3)
                
                await self.scrape_subnet_channels()
                
                if self.messages:
                    # Send to Telegram if configured
                    if self.telegram_bot_token and self.telegram_chat_id:
                        await self.send_to_telegram()
                else:
                    print("\n⚠ No messages found from the target user.")
                    
                    # Send "no messages" notification to Telegram if configured
                    if self.telegram_bot_token and self.telegram_chat_id:
                        await self.send_no_messages_notification()
                
                # Wait before next cycle
                print(f"\n⏳ Next scrape in {check_interval} seconds...")
                await asyncio.sleep(check_interval)
            
        except KeyboardInterrupt:
            print("\n\n" + "="*60)
            print("⏹ Real-time monitoring stopped by user")
            print("="*60)
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.browser:
                print("\nClosing browser...")
                await self.browser.close()


async def main():
    """Main entry point."""
    import os
    
    start_time = time.time()
    
    print("="*60)
    print("Discord Message Scraper - Bittensor Subnets")
    print("="*60)
    print(f"\nTarget: Bittensor server")
    print(f"Filtering messages from user: consτ [τ, τ]")
    print(f"Scraping: All subnet channels (1-128)")
    print(f"Time limit: Last 30 minutes only\n")
    
    # Ask about check interval
    check_interval = 10  # default
    try:
        interval_input = input("Check interval in seconds [default: 10]: ").strip()
        if interval_input:
            check_interval = int(interval_input)
    except (EOFError, KeyboardInterrupt, ValueError):
        print("Using default: 10 seconds")
        check_interval = 10
    
    # Ask about headless mode (with default to False if input fails)
    try:
        headless_input = input("Run in headless mode? (y/N): ").strip().lower()
        headless = headless_input == 'y'
    except (EOFError, KeyboardInterrupt):
        print("\nUsing default: headless=False (browser will be visible)")
        headless = False
    
    # Telegram configuration - can be set via environment variables or here
    # Set these environment variables or replace with your values:
    #   TELEGRAM_BOT_TOKEN - Get from @BotFather on Telegram
    #   TELEGRAM_CHAT_ID - Your channel/chat ID (e.g., -1001234567890 for channels)
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', None)
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', None)
    
    # Uncomment and set these if you prefer hardcoding:
    # telegram_bot_token = "YOUR_BOT_TOKEN_HERE"
    # telegram_chat_id = "YOUR_CHAT_ID_HERE"
    
    print(f"\nCheck interval: {check_interval} seconds")
    print(f"Browser mode: {'headless' if headless else 'visible'}")
    if telegram_bot_token and telegram_chat_id:
        print(f"Telegram: Enabled (chat ID: {telegram_chat_id})")
    else:
        print("Telegram: Disabled (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars to enable)")
    print("Starting scraper...\n")
    
    # Create and run scraper
    scraper = DiscordScraper(
        target_username="consτ [τ, τ]", 
        target_server="bittensor", 
        headless=headless, 
        scrape_unread_only=True,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id
    )
    await scraper.run(check_interval=check_interval)
    
    # Calculate and display execution time
    end_time = time.time()
    duration = end_time - start_time
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    milliseconds = int((duration % 1) * 1000)
    
    print("\n" + "="*60)
    print("Execution Summary")
    print("="*60)
    if hours > 0:
        print(f"Total execution time: {hours}h {minutes}m {seconds}s")
    elif minutes > 0:
        print(f"Total execution time: {minutes}m {seconds}s")
    else:
        print(f"Total execution time: {seconds}.{milliseconds:03d}s")
    print(f"({duration:.2f} seconds)")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

