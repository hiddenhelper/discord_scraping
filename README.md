# Discord Web Scraper - Bittensor Subnets

A browser-based scraper for Discord web application that collects messages from the **Bittensor server's subnet channels** and filters them by a specific user.

## Features

- ✅ Scrapes messages from Discord web application (no API access required)
- ✅ Automatically navigates to the Bittensor server
- ✅ Scrapes all subnet channels (1-128 subnets)
- ✅ Filters messages from user: **consttt**
- ✅ Saves results to JSON file
- ✅ Handles scrolling to load older messages
- ✅ Works without server owner permissions

## Requirements

- Python 3.8 or higher
- Playwright browser automation library

## Installation

1. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

**Note**: If you're using Python 3.13, make sure to use the latest version of Playwright (already specified in requirements.txt) which includes Python 3.13 compatible dependencies.

## Usage

1. Activate the virtual environment (if you created one):
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the scraper:
```bash
python discord_scraper.py
```

3. The browser will open. **Log in to Discord manually** in the browser window.

4. Wait for the scraper to detect your login (it will automatically detect when you're logged in).

5. The scraper will then:
   - Automatically navigate to the **Bittensor** server
   - Find and scrape all **subnet channels** (1-128 subnets)
   - Scroll through messages to load older ones
   - Extract and filter messages from user: **consttt**
   - Save results to a JSON file

## Configuration

The scraper is configured to:
- **Target Server**: Bittensor
- **Target User**: consttt
- **Channels**: All subnet channels (automatically detected)

To change these settings, edit the `main()` function in `discord_scraper.py`.

## Output

The scraper saves results to a JSON file named: `discord_messages_consttt_{timestamp}.json`

The JSON structure:
```json
{
  "target_username": "consttt",
  "total_messages": 42,
  "scraped_at": "2024-01-01T12:00:00",
  "messages": [
    {
      "username": "consttt",
      "content": "Message content here",
      "timestamp": "2024-01-01T10:00:00",
      "channel": "subnet-1",
      "scraped_at": "2024-01-01T12:00:00"
    }
  ]
}
```

## Important Notes

⚠️ **Rate Limiting**: Discord may rate limit if you scrape too aggressively. The scraper includes delays between actions to avoid this.

⚠️ **Manual Navigation**: If automatic channel detection fails, you can manually navigate to channels. The scraper will collect messages from whatever channel is currently visible.

⚠️ **Login**: You must manually log in to Discord when the browser opens. The scraper will wait for you to complete the login.

⚠️ **Permissions**: You can only scrape channels you have access to. Private channels you don't have access to won't be scraped.

## Troubleshooting

### No subnet channels found
- Make sure you're logged in and on the Bittensor server
- The scraper will prompt you to manually navigate if it can't find subnets automatically
- Check that you have access to the Bittensor server and subnet channels
- Subnet channels are typically named like "subnet-1", "subnet-2", "sn1", "sn2", or just numbers 1-128

### Bittensor server not found
- Make sure you're a member of the Bittensor Discord server
- The scraper will prompt you to manually navigate to the server if it can't find it automatically
- Once you're on the Bittensor server, press Enter to continue

### Messages not loading
- The scraper automatically scrolls to load older messages
- If messages aren't loading, try manually scrolling in the browser window
- Some channels may have message history limits

### Browser closes immediately
- Run with `headless=False` (default) to see what's happening
- Check the console output for error messages

### Build errors (greenlet compilation issues)
- If you encounter `greenlet` build errors, make sure you're using Python 3.13 with the latest Playwright version (already in requirements.txt)
- Use a virtual environment to avoid system package conflicts
- If issues persist, try using Python 3.11 or 3.12 instead

### Browser not opening
- Make sure you answered "N" (or just press Enter) when asked about headless mode - the browser won't be visible in headless mode
- Check that Playwright browsers are installed: `playwright install chromium`
- Try running the test script: `python test_browser.py` - this will verify if the browser can open
- On macOS, you may need to grant Terminal/iTerm permission to control your computer (System Preferences > Security & Privacy > Accessibility)
- Check the console output for error messages - the scraper now includes detailed debug output
- If the browser opens but immediately closes, check for errors in the console output

## Legal Disclaimer

This tool is for educational purposes. Make sure you have permission to scrape messages from the Discord servers you're accessing. Respect Discord's Terms of Service and rate limits.

