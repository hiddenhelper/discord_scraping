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
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser


class DiscordScraper:
    def __init__(self, target_username: str = "Mams [τ, ꨄ]", target_server: str = "bittensor", headless: bool = False, scrape_unread_only: bool = True):
        """
        Initialize the Discord scraper.
        
        Args:
            target_username: The username to filter messages for (default: "D&C")
            target_server: The server name to scrape (default: "bittensor")
            headless: Whether to run browser in headless mode
            scrape_unread_only: Only scrape unread messages (default: True) - faster and avoids duplicates
        """
        self.target_username = target_username
        self.target_server = target_server.lower()
        self.headless = headless
        self.scrape_unread_only = scrape_unread_only
        self.messages: List[Dict] = []
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        if scrape_unread_only:
            print(f"📬 Mode: Only scraping UNREAD messages (faster, avoids duplicates)")
        else:
            print(f"📬 Mode: Scraping all messages")
        
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
        await asyncio.sleep(3)
        
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
                    await asyncio.sleep(2)
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
                            await asyncio.sleep(0.5)
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
                            await asyncio.sleep(3)  # Wait for server to load
                            
                            # Verify we're on the right server by checking the page
                            await asyncio.sleep(2)
                            
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
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error during server search: {e}")
                await asyncio.sleep(1)
        
        print(f"\n⚠ Could not automatically find '{self.target_server}' server.")
        print(f"Please manually navigate to the '{self.target_server}' server in the browser.")
        input("Press Enter once you're on the Bittensor server...")
        await asyncio.sleep(2)
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
                        await asyncio.sleep(2)  # Give UI time to fully load
                        return True
                
                await asyncio.sleep(1)
            except Exception as e:
                await asyncio.sleep(1)
        
        raise TimeoutError("Login timeout. Please ensure you've logged in to Discord.")
    
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
            await asyncio.sleep(1)
            
            # Find the channel list container (left sidebar)
            channel_list_selectors = [
                'nav[aria-label*="Channels"]',
                'nav[aria-label*="channels"]',
                'div[class*="channels"]',
                'div[class*="sidebar"]',
                '[class*="scroller"][class*="channel"]',
                'div[class*="list"]'
            ]
            
            channel_list_container = None
            for selector in channel_list_selectors:
                try:
                    container = await self.page.query_selector(selector)
                    if container:
                        # Check if it's scrollable
                        is_scrollable = await container.evaluate('el => el.scrollHeight > el.clientHeight')
                        if is_scrollable:
                            channel_list_container = container
                            print(f"  Found scrollable channel list container")
                            break
                except:
                    continue
            
            # If no specific container found, try to find any scrollable element in the sidebar
            if not channel_list_container:
                # Look for scrollable divs in the sidebar area
                all_divs = await self.page.query_selector_all('div[class*="scroller"], div[class*="scrollable"]')
                for div in all_divs:
                    try:
                        is_scrollable = await div.evaluate('el => el.scrollHeight > el.clientHeight')
                        if is_scrollable:
                            # Check if it's in the sidebar (left side of page)
                            bounding_box = await div.bounding_box()
                            if bounding_box and bounding_box['x'] < 300:  # Sidebar is on the left
                                channel_list_container = div
                                print(f"  Found scrollable sidebar container")
                                break
                    except:
                        continue
            
            if channel_list_container:
                last_height = 0
                scroll_count = 0
                no_change_count = 0
                
                # Start from top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.5)
                
                for i in range(max_scrolls):
                    # Get current measurements
                    current_height = await channel_list_container.evaluate('el => el.scrollHeight')
                    scroll_top = await channel_list_container.evaluate('el => el.scrollTop')
                    client_height = await channel_list_container.evaluate('el => el.clientHeight')
                    
                    # Scroll down incrementally (not all the way at once)
                    scroll_amount = client_height * 0.8  # Scroll 80% of viewport
                    new_scroll = scroll_top + scroll_amount
                    await channel_list_container.evaluate(f'el => el.scrollTop = {new_scroll}')
                    await asyncio.sleep(0.4)  # Wait for channels to load
                    
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
                await asyncio.sleep(1)  # Wait for DOM to settle
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
            # Find the channel list container
            channel_list_container = None
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
                            channel_list_container = container
                            break
                except:
                    continue
            
            if not channel_list_container:
                all_divs = await self.page.query_selector_all('div[class*="scroller"], div[class*="scrollable"]')
                for div in all_divs:
                    try:
                        is_scrollable = await div.evaluate('el => el.scrollHeight > el.clientHeight')
                        if is_scrollable:
                            bounding_box = await div.bounding_box()
                            if bounding_box and bounding_box['x'] < 300:
                                channel_list_container = div
                                break
                    except:
                        continue
            
            if channel_list_container:
                # Start from top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.5)
                
                # Expand categories at the start
                await self.expand_all_categories(scroll_container=channel_list_container)
                await asyncio.sleep(0.5)
                
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
                        await asyncio.sleep(0.5)
                        
                        # Expand categories one final time at bottom
                        await self.expand_all_categories(scroll_container=channel_list_container)
                        await asyncio.sleep(0.5)
                        
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
                    await asyncio.sleep(0.4)
                    
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
                        await asyncio.sleep(0.5)
                        break
                    
                    last_height = new_height
                    last_channel_count = len(all_channel_elements)
                    scroll_count = i + 1
                    
                    if (i + 1) % 20 == 0:
                        print(f"  Collected {len(all_channel_elements)} channels so far (scroll {i+1}, height: {new_height}px)")
                
                print(f"  Total collected: {len(all_channel_elements)} channels after {scroll_count} scrolls")
                
                # Scroll back to top
                await channel_list_container.evaluate('el => el.scrollTop = 0')
                await asyncio.sleep(0.5)
            
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
            await asyncio.sleep(2)  # Give extra time for channels to render
            
            print("\nCollecting all channels while scrolling...")
            # Collect channels incrementally while scrolling (this also expands categories)
            channel_elements = await self.collect_channels_while_scrolling()
            
            # One more pass: scroll to bottom and expand categories there
            print("\nFinal pass: Ensuring we reach 'subnets 3' category...")
            try:
                # Find scroll container again
                channel_list_container = None
                selectors = ['nav[aria-label*="Channels"]', 'div[class*="channels"]', 'div[class*="scroller"]']
                for selector in selectors:
                    try:
                        container = await self.page.query_selector(selector)
                        if container:
                            is_scrollable = await container.evaluate('el => el.scrollHeight > el.clientHeight')
                            if is_scrollable:
                                channel_list_container = container
                                break
                    except:
                        continue
                
                if not channel_list_container:
                    all_divs = await self.page.query_selector_all('div[class*="scroller"], div[class*="scrollable"]')
                    for div in all_divs:
                        try:
                            is_scrollable = await div.evaluate('el => el.scrollHeight > el.clientHeight')
                            if is_scrollable:
                                bounding_box = await div.bounding_box()
                                if bounding_box and bounding_box['x'] < 300:
                                    channel_list_container = div
                                    break
                        except:
                            continue
                
                if channel_list_container:
                    # Scroll all the way to bottom
                    await channel_list_container.evaluate('el => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(1)
                    
                    # Expand categories at bottom (including "subnets 3")
                    await self.expand_all_categories(scroll_container=channel_list_container)
                    await asyncio.sleep(1)
                    
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
            
            await asyncio.sleep(1)
            
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
                        # STRICTLY check if any number is in the valid subnet range (1-128)
                        # Only accept subnets 1-128, nothing outside this range
                        is_subnet_channel = False
                        subnet_number = None
                        
                        for num_str in numbers:
                            try:
                                num = int(num_str)
                                # Only accept if number is between 1 and 128 (inclusive)
                                if 1 <= num <= 128:
                                    is_subnet_channel = True
                                    subnet_number = num
                                    break  # Use first valid subnet number found
                            except:
                                continue
                        
                        # Only add if we found a valid subnet number (1-128)
                        if is_subnet_channel and subnet_number:
                            channels.append({
                                'name': name,
                                'href': href,
                                'element': element,
                                'subnet_number': subnet_number
                            })
                            print(f"  ✓ Found subnet channel: {name} (subnet {subnet_number})")
                        # If channel has numbers but none in 1-128 range, skip it
                            
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
        """Check if a channel has unread messages by checking if the name is bold."""
        try:
            if not channel_elem:
                return False
            
            # The channel element should be the <a> tag with href
            # Find the name div inside it: <div class="_2ea32c412048f708-name ...">
            name_elem = await channel_elem.query_selector('div[class*="name"]')
            
            if not name_elem:
                # Try alternative selectors
                name_elem = await channel_elem.query_selector('[class*="name"]')
            
            if name_elem:
                # Check computed style for font-weight (works even with aria-hidden)
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
                
                # Also check if the element itself has bold styling via CSS
                try:
                    # Check computed font-weight including inherited styles
                    is_bold = await name_elem.evaluate('el => { const style = window.getComputedStyle(el); const fw = style.fontWeight; if (fw === "bold") return true; const fwNum = parseInt(fw); return fwNum >= 500; }')
                    if is_bold:
                        return True
                except:
                    pass
            
            # Check the <a> element itself for bold styling
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
            
            # Check for unread class on the channel element or its parents
            channel_class = await channel_elem.get_attribute('class') or ""
            if 'unread' in channel_class.lower():
                return True
            
            # Check parent wrapper for unread indicators
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
            
            # Check for unread badge
            unread_badge = await channel_elem.query_selector('[class*="unread"], [class*="unreadBadge"], [class*="unreadCount"]')
            if unread_badge:
                return True
            
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
            
            if not message_container:
                return
            
            # Wait a moment for Discord to auto-scroll to unread messages (if many unread)
            await asyncio.sleep(1)
            
            # Check if we're already at unread messages (Discord auto-scrolled)
            has_unread_marker = await self.has_unread_messages_in_view()
            
            if has_unread_marker:
                print(f"  📬 Discord auto-scrolled to unread messages (many unread)")
                # We're already at unread messages, just scroll down a bit to load more
                await message_container.evaluate('element => element.scrollTop += 500')
                await asyncio.sleep(0.3)
            else:
                # Few unread messages - they should be visible, just scroll down to load more if needed
                print(f"  📬 Few unread messages visible")
                # Scroll down slightly to ensure all visible unread messages are loaded
                await message_container.evaluate('element => element.scrollTop += 300')
                await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"  Error scrolling to unread: {e}")
    
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
            # Wait a bit for messages to load and for Discord to auto-scroll (if many unread)
            await asyncio.sleep(1.5)
            
            # Scroll to load messages (handles unread messages appropriately)
            await self.scroll_to_load_messages()
            
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
            
            # Extract all visible messages
            # If unread mode: Discord already positioned us at unread messages
            # - Few unread: visible immediately
            # - Many unread: Discord auto-scrolled to first unread
            for element in message_elements:
                try:
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
                        await asyncio.sleep(1.5)  # Reduced wait time
                    else:
                        # Alternative: try to find and click by text
                        await self.page.click(f'text={channel_name}')
                        await asyncio.sleep(1.5)
                except:
                    # Alternative: try to find and click by text
                    try:
                        await self.page.click(f'text={channel_name}')
                        await asyncio.sleep(1.5)
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
            filtered_messages = []
            target_username_normalized = self.normalize_username(self.target_username)
            
            for msg in messages:
                msg_username = msg.get('username', '')
                msg_username_normalized = self.normalize_username(msg_username)
                
                # Try multiple matching strategies
                matches = (
                    target_username_normalized in msg_username_normalized or
                    msg_username_normalized in target_username_normalized or
                    self.target_username in msg_username or
                    msg_username in self.target_username
                )
                
                if matches:
                    filtered_messages.append(msg)
            
            if filtered_messages:
                print(f"  ✓ Found {len(filtered_messages)} messages matching '{self.target_username}'")
                for msg in filtered_messages:
                    msg['channel'] = channel_name
                    self.messages.append(msg)
            else:
                print(f"  - No messages matching '{self.target_username}' in this channel")
            
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
            target_username_normalized = self.normalize_username(self.target_username)
            filtered = []
            for msg in messages:
                msg_username = msg.get('username', '')
                msg_username_normalized = self.normalize_username(msg_username)
                
                matches = (
                    target_username_normalized in msg_username_normalized or
                    msg_username_normalized in target_username_normalized or
                    self.target_username in msg_username or
                    msg_username in self.target_username
                )
                
                if matches:
                    filtered.append(msg)
            
            self.messages.extend(filtered)
        else:
            print(f"Found {len(channels)} subnet channels. Starting to scrape...\n")
            
            # for i, channel in enumerate(channels, 1):
            #     print(f"[{i}/{len(channels)}] Processing subnet: {channel['name']}")
            #     await self.scrape_channel(channel['name'], channel.get('href'))
            #     await asyncio.sleep(1.5)  # Small delay between channels to avoid rate limiting
        
        print(f"\n✓ Scraping complete! Found {len(self.messages)} messages from {self.target_username} across {len(channels)} subnets")
    
    async def save_results(self, filename: str = None):
        """Save scraped messages to a JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"discord_messages_{self.target_username}_{timestamp}.json"
        
        output = {
            'target_username': self.target_username,
            'total_messages': len(self.messages),
            'scraped_at': datetime.now().isoformat(),
            'messages': self.messages
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results saved to: {filename}")
        return filename
    
    async def run(self):
        """Main execution method."""
        try:
            await self.setup_browser()
            await self.scrape_subnet_channels()
            
            if self.messages:
                await self.save_results()
            else:
                print("\n⚠ No messages found from the target user.")
            
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
    print("="*60)
    print("Discord Message Scraper - Bittensor Subnets")
    print("="*60)
    print(f"\nTarget: Bittensor server")
    print(f"Filtering messages from user: D&C")
    print(f"Scraping: All subnet channels (1-128)")
    print(f"Time limit: Last 30 minutes only\n")
    
    # Ask about headless mode (with default to False if input fails)
    try:
        headless_input = input("Run in headless mode? (y/N): ").strip().lower()
        headless = headless_input == 'y'
    except (EOFError, KeyboardInterrupt):
        print("\nUsing default: headless=False (browser will be visible)")
        headless = False
    
    print(f"\nBrowser mode: {'headless' if headless else 'visible'}")
    print("Starting scraper...\n")
    
    # Create and run scraper with hardcoded values
    scraper = DiscordScraper(target_username="D&C", target_server="bittensor", headless=headless, scrape_unread_only=True)
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())

