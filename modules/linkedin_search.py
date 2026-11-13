"""LinkedIn search URLs and selectors for both classic and semantic-search layouts."""
from urllib.parse import urlencode, urlsplit
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

CLASSIC_CARDS = "//li[@data-occludable-job-id]"
MODERN_CARDS = "//*[@role='button' and starts-with(@componentkey,'job-card-component-ref-')]"
CARDS_XPATH = CLASSIC_CARDS + ' | ' + MODERN_CARDS


class LinkedInLoginRequired(RuntimeError):
    pass


class SearchPageTimeout(TimeoutException):
    pass


def build_search_url(keyword, settings):
    params = {'keywords':keyword}
    location = settings.get('search_location', '').strip()
    if location: params['location'] = location
    if settings.get('search_geo_id'): params['geoId'] = settings['search_geo_id']
    if settings.get('easy_apply_only'): params['f_AL'] = 'true'
    if settings.get('sort_by'): params['sortBy'] = {'Most recent':'DD','Most relevant':'R'}[settings['sort_by']]
    dates = {'Past 24 hours':'r86400','Past week':'r604800','Past month':'r2592000'}
    if settings.get('date_posted') in dates: params['f_TPR'] = dates[settings['date_posted']]
    for name, param, options in [
        ('experience_level','f_E',['Internship','Entry level','Associate','Mid-Senior level','Director','Executive']),
        ('on_site','f_WT',['On-site','Remote','Hybrid']),
        ('job_type','f_JT',['Full-time','Part-time','Contract','Temporary','Volunteer','Internship','Other']),
    ]:
        chosen = settings.get(name, [])
        if chosen:
            codes = ['F','P','C','T','V','I','O'] if name == 'job_type' else [str(i+1) for i in range(len(options))]
            params[param] = ','.join(codes[options.index(value)] for value in chosen)
    if settings.get('under_10_applicants'): params['f_EA'] = 'true'
    if settings.get('in_your_network'): params['f_N'] = 'true'
    return 'https://www.linkedin.com/jobs/search/?'+urlencode(params)


def card_id(card):
    for attr in ('data-occludable-job-id','data-job-id','componentkey'):
        value = card.get_attribute(attr) or ''
        match = re.search(r'(\d+)$',value)
        if match: return match[1]
    return ''


def visible_cards(driver):
    cards, seen = [], set()
    for card in driver.find_elements(By.XPATH, CARDS_XPATH):
        try:
            identity = card_id(card)
            # Preserve off-screen but already rendered cards for scroll-to-view.
            if identity and identity not in seen:
                cards.append(card); seen.add(identity)
        except StaleElementReferenceException:
            continue
    return cards


def authentication_blocked(driver):
    path = urlsplit(driver.current_url).path.lower()
    return any(part in path for part in ('/login','/checkpoint','/authwall','/challenge','/uas/login'))


def is_authenticated(driver):
    if authentication_blocked(driver): return False
    # Positive evidence only; missing Sign in buttons do not prove authentication.
    path = urlsplit(driver.current_url).path
    if path.startswith('/feed'): return True
    return any(e.is_displayed() for e in driver.find_elements(By.XPATH,
        "//a[contains(@href,'/mynetwork') or contains(@href,'/messaging')]"))


def wait_for_results(driver, timeout=30):
    def loaded(d):
        if authentication_blocked(d): return False  # allow transient checkpoint redirects to settle
        cards = visible_cards(d)
        if cards: return ('results',cards)
        empty = d.find_elements(By.XPATH,
            "//*[self::h1 or self::h2 or self::h3 or @role='status'][contains(.,'No matching jobs') or contains(.,'No results found') or contains(.,'No jobs found') or contains(.,'No results for')]"
            " | //div[contains(@class,'jobs-search-no-results-banner')]")
        if any(e.is_displayed() for e in empty): return ('empty',[])
        return False
    try:
        return WebDriverWait(driver,timeout).until(loaded)
    except TimeoutException as error:
        if authentication_blocked(driver):
            raise LinkedInLoginRequired('LinkedIn requires sign-in or a security check. Complete it in the browser, then start the bot again.') from error
        raise SearchPageTimeout(f'Job results did not load within {timeout}s on {urlsplit(driver.current_url).path}. The browser may still be open.') from error


class LinkedInAccountMismatch(RuntimeError):
    pass


def profile_slug(url):
    """Recognize a resolved LinkedIn member profile URL."""
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    match = re.fullmatch(r'/in/([a-z0-9_%\-]+)/?', parts.path, re.IGNORECASE)
    if parts.scheme == 'https' and parts.netloc.lower() in ('www.linkedin.com', 'linkedin.com') and match:
        slug = match[1].lower()
        return slug if slug != 'me' else None
    return None


def require_applicant_profile(expected_slug, actual_url):
    actual_slug = profile_slug(actual_url)
    if not actual_slug:
        raise LinkedInAccountMismatch('Could not verify the signed-in LinkedIn account.')
    if actual_slug != expected_slug:
        raise LinkedInAccountMismatch(f'Wrong LinkedIn account: {actual_slug}. Expected {expected_slug}. Sign in as the configured applicant.')
    return actual_slug


def verify_applicant_account(driver, expected_profile, timeout=30):
    """Resolve LinkedIn's own-profile shortcut before any job or application is opened."""
    expected_slug = profile_slug(expected_profile)
    if not expected_slug:
        raise LinkedInAccountMismatch('Configure your own LinkedIn profile URL before running applications.')
    driver.get('https://www.linkedin.com/in/me/')
    try:
        WebDriverWait(driver, timeout).until(lambda d: profile_slug(d.current_url))
    except TimeoutException as error:
        raise LinkedInAccountMismatch('Could not verify the signed-in LinkedIn account. No applications will be processed.') from error
    return require_applicant_profile(expected_slug, driver.current_url)
