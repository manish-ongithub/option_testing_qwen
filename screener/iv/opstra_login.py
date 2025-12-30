"""
Opstra Auto-Login with Persistent Chrome Profile.

Uses Selenium with a persistent Chrome profile to automatically extract
Opstra session cookies without manual daily login.

First run: Opens browser for manual Google login (profile saved)
Subsequent runs: Uses saved profile, no manual login needed
"""

import os
import time
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from screener.utils.logging_setup import logger

# Default Chrome profile path
DEFAULT_CHROME_PROFILE = os.path.expanduser("~/.opstra_chrome_profile")


def get_opstra_cookies_via_browser(force_login=False, headless=False, timeout=120, use_undetected=True):
    """
    Opens browser with persistent profile to extract Opstra session cookies.
    
    First run: You'll need to login manually via Google.
    Subsequent runs: Profile is already logged in, cookies extracted automatically.
    
    Args:
        force_login: If True, waits for manual login even if profile exists
        headless: If True, runs browser in headless mode (only works if already logged in)
        timeout: Seconds to wait for login/page load
        use_undetected: If True, uses undetected-chromedriver to bypass Google detection
    
    Returns:
        dict: {'JSESSIONID': '...', 'DSESSIONID': '...'} or None on failure
    """
    from screener.config import CHROME_PROFILE_PATH
    
    profile_path = CHROME_PROFILE_PATH or DEFAULT_CHROME_PROFILE
    profile_exists = os.path.exists(profile_path)
    
    # Try undetected-chromedriver first (bypasses Google detection)
    if use_undetected:
        try:
            return _get_cookies_undetected(profile_path, profile_exists, force_login, headless, timeout)
        except ImportError:
            logger.info("undetected-chromedriver not installed. Trying standard Selenium...")
        except Exception as e:
            logger.warning("Undetected Chrome failed: %s. Trying standard Selenium...", e)
    
    # Fallback to standard Selenium with anti-detection
    return _get_cookies_standard(profile_path, profile_exists, force_login, headless, timeout)


def _get_cookies_undetected(profile_path, profile_exists, force_login, headless, timeout):
    """
    Use undetected-chromedriver to bypass Google's bot detection.
    This library patches Chrome to avoid detection.
    """
    import undetected_chromedriver as uc
    
    options = uc.ChromeOptions()
    
    # Use persistent profile
    options.add_argument(f'--user-data-dir={profile_path}')
    
    # Only run headless if profile exists and not forcing login
    if headless and profile_exists and not force_login:
        options.add_argument('--headless=new')
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1200,800')
    
    driver = None
    
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        
        # Navigate to Opstra
        driver.get('https://opstra.definedge.com/')
        
        # Check if we're already logged in
        time.sleep(3)
        cookies = _get_session_cookies(driver)
        
        if cookies and not force_login:
            logger.info("Opstra session found in saved profile. Cookies extracted.")
            return cookies
        
        # Need manual login
        if not profile_exists or force_login:
            _show_login_instructions()
        
        # Wait for successful login
        start_time = time.time()
        while time.time() - start_time < timeout:
            cookies = _get_session_cookies(driver)
            
            if cookies:
                logger.info("Login successful! Opstra cookies extracted.")
                return cookies
            
            time.sleep(2)
        
        logger.error("Timeout waiting for Opstra login (%d seconds)", timeout)
        return None
        
    except Exception as e:
        logger.error("Undetected Chrome error: %s", e)
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def _get_cookies_standard(profile_path, profile_exists, force_login, headless, timeout):
    """
    Use standard Selenium with maximum anti-detection measures.
    Note: Google may still block this. Use undetected-chromedriver if issues persist.
    """
    options = Options()
    
    # Use persistent profile directory
    options.add_argument(f'--user-data-dir={profile_path}')
    
    # Only run headless if profile exists and not forcing login
    if headless and profile_exists and not force_login:
        options.add_argument('--headless=new')
    
    # Anti-detection measures
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--window-size=1200,800')
    options.add_argument('--start-maximized')
    
    # Realistic user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Disable automation flags
    options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Additional preferences to appear more human
    prefs = {
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False,
        'profile.default_content_setting_values.notifications': 2,
    }
    options.add_experimental_option('prefs', prefs)
    
    driver = None
    
    try:
        # Use webdriver-manager to handle ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Execute CDP commands to mask webdriver
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                window.chrome = {
                    runtime: {}
                };
            '''
        })
        
        # Navigate to Opstra
        driver.get('https://opstra.definedge.com/')
        
        # Check if we're already logged in by looking for cookies
        time.sleep(3)
        cookies = _get_session_cookies(driver)
        
        if cookies and not force_login:
            logger.info("Opstra session found in saved profile. Cookies extracted.")
            return cookies
        
        # Need manual login
        if not profile_exists or force_login:
            _show_login_instructions_with_alternative()
        
        # Wait for successful login (cookies appear after login)
        start_time = time.time()
        while time.time() - start_time < timeout:
            cookies = _get_session_cookies(driver)
            
            if cookies:
                logger.info("Login successful! Opstra cookies extracted.")
                return cookies
            
            time.sleep(2)
        
        logger.error("Timeout waiting for Opstra login (%d seconds)", timeout)
        return None
        
    except Exception as e:
        logger.error("Opstra browser login error: %s", e)
        return None
    finally:
        if driver:
            driver.quit()


def _get_session_cookies(driver):
    """
    Extract JSESSIONID and DSESSIONID from browser cookies.
    
    Returns:
        dict with cookies if both found, None otherwise
    """
    try:
        cookies = driver.get_cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        
        jsessionid = cookie_dict.get('JSESSIONID')
        dsessionid = cookie_dict.get('DSESSIONID')
        
        if jsessionid and dsessionid:
            return {
                'JSESSIONID': jsessionid,
                'DSESSIONID': dsessionid,
                '_ga': cookie_dict.get('_ga', ''),
                '_ga_6D0ZQ437SD': cookie_dict.get('_ga_6D0ZQ437SD', '')
            }
    except Exception:
        pass
    
    return None


def _show_login_instructions():
    """Print login instructions to console."""
    print("\n" + "=" * 60)
    print("OPSTRA LOGIN REQUIRED")
    print("=" * 60)
    print("A browser window has opened. Please:")
    print("  1. Click 'Login with Google'")
    print("  2. Complete your Google sign-in")
    print("  3. Wait for Opstra dashboard to load")
    print("")
    print("Your login will be saved for future runs.")
    print("=" * 60 + "\n")


def _show_login_instructions_with_alternative():
    """Print login instructions with workaround for Google blocking."""
    print("\n" + "=" * 70)
    print("OPSTRA LOGIN REQUIRED")
    print("=" * 70)
    print("")
    print("A browser window has opened. Please:")
    print("  1. Click 'Login with Google'")
    print("  2. Complete your Google sign-in")
    print("  3. Wait for Opstra dashboard to load")
    print("")
    print("If Google shows 'This browser or app may not be secure':")
    print("  Option A: Install undetected-chromedriver:")
    print("            pip install undetected-chromedriver")
    print("            Then run again.")
    print("")
    print("  Option B: Login manually in your regular Chrome browser:")
    print("            1. Open https://opstra.definedge.com in Chrome")
    print("            2. Login with Google")
    print("            3. Press F12 > Application > Cookies")
    print("            4. Copy JSESSIONID and DSESSIONID")
    print("            5. Run: python -m screener.main --no-opstra")
    print("               And set cookies manually in config.py")
    print("")
    print("Your login will be saved for future runs.")
    print("=" * 70 + "\n")


def refresh_opstra_session(force_login=False, headless=False):
    """
    Refresh Opstra cookies and update the screener config.
    
    This is the main function to call at screener startup.
    
    Args:
        force_login: If True, forces re-login even if profile exists
        headless: If True, tries headless mode (only works if already logged in)
    
    Returns:
        bool: True if cookies were successfully refreshed
    """
    from screener.iv.opstra import set_opstra_cookies, validate_opstra_session
    
    # First, check if current cookies are still valid
    if not force_login and validate_opstra_session():
        logger.info("Opstra session is already valid. Skipping browser refresh.")
        return True
    
    logger.info("Refreshing Opstra session via browser...")
    
    # Try headless first if profile likely exists
    from screener.config import CHROME_PROFILE_PATH
    profile_path = CHROME_PROFILE_PATH or DEFAULT_CHROME_PROFILE
    
    if os.path.exists(profile_path) and not force_login:
        logger.info("Using saved Chrome profile: %s", profile_path)
        cookies = get_opstra_cookies_via_browser(force_login=False, headless=True, timeout=30)
        
        if cookies:
            set_opstra_cookies(cookies['JSESSIONID'], cookies['DSESSIONID'])
            return True
        
        # Headless failed, try with visible browser
        logger.info("Headless mode failed. Opening browser for manual login...")
    
    # Open visible browser for login
    cookies = get_opstra_cookies_via_browser(force_login=force_login, headless=False, timeout=120)
    
    if cookies:
        set_opstra_cookies(cookies['JSESSIONID'], cookies['DSESSIONID'])
        return True
    
    logger.warning("Failed to refresh Opstra session. Will use fallback IV data.")
    return False


def clear_opstra_profile():
    """
    Delete the saved Chrome profile (for troubleshooting).
    
    After clearing, you'll need to login again on next run.
    """
    import shutil
    from screener.config import CHROME_PROFILE_PATH
    
    profile_path = CHROME_PROFILE_PATH or DEFAULT_CHROME_PROFILE
    
    if os.path.exists(profile_path):
        shutil.rmtree(profile_path)
        logger.info("Opstra Chrome profile deleted: %s", profile_path)
    else:
        logger.info("No Chrome profile found at: %s", profile_path)
