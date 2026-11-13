"""Read the target profile's visible About, Experience and Education sections."""
import re
from threading import Event
from urllib.parse import urlsplit
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException

SECTIONS=('about', 'experience', 'education')


class ProfileAlreadyPending(Exception):
    pass


class ProfileRestricted(RuntimeError):
    pass


def wait_for_condition(driver, condition, restriction_check=None):
    """Observe readiness without an elapsed-time cutoff; Ctrl+C remains available."""
    poll = Event()
    while True:
        if restriction_check and restriction_check(driver):
            raise ProfileRestricted('LinkedIn restriction or security check while waiting')
        try:
            result = condition(driver)
            if result:
                return result
        except (StaleElementReferenceException, NoSuchElementException):
            pass
        poll.wait(0.25)


def normalize(value):
    return ' '.join(re.sub(r'\([^)]*\)','',value).casefold().split())


def profile_root(driver):
    main=driver.find_element(By.TAG_NAME,'main')
    primary=main.find_elements(By.CSS_SELECTOR,'section[aria-label="Primary content"]')
    return primary[0] if primary else main


def matching_sections(driver):
    found=[]
    for heading in profile_root(driver).find_elements(By.CSS_SELECTOR,'h2,[role="heading"]'):
        if not heading.is_displayed() or not heading.text.strip():continue
        if heading.find_elements(By.XPATH,'./ancestor::aside'):continue
        title=heading.text.strip().split('\n')[0].casefold()
        if title not in SECTIONS:continue
        sections=heading.find_elements(By.XPATH,'./ancestor::section[1]')
        if not sections:continue
        section=sections[0]
        # Never accept an outer page wrapper containing multiple profile cards.
        if section.get_attribute('aria-label')=='Primary content':continue
        if section.find_elements(By.CSS_SELECTOR,'aside'):continue
        found.append((title,section))
    return found


def expand_text(driver, section, restriction_check=None):
    """Click exposed text controls and verify the rendered expansion."""
    for button in section.find_elements(By.CSS_SELECTOR, 'button'):
        label = (button.text or '').strip().casefold()
        if not button.is_displayed() or label not in (
            'see more', '…see more', '...see more', '… more', '... more', 'show more'
        ):
            continue
        driver.execute_script(
            "arguments[0].parentElement.scrollIntoView({block:'center',behavior:'instant'})", button
        )
        def exposed(d):
            return d.execute_script("""
                const e=arguments[0],r=e.getBoundingClientRect();
                const top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
                return e.isConnected && r.width>0 && r.height>0 && (e===top || e.contains(top));
            """, button)
        wait_for_condition(driver, exposed, restriction_check)
        before = driver.execute_script("return arguments[0].parentElement.getBoundingClientRect().height", button)
        button.click()
        def expanded(d):
            try:
                return not button.is_displayed() or button.get_attribute('aria-expanded')=='true' or d.execute_script(
                    "return arguments[0].parentElement.getBoundingClientRect().height", button
                ) > before
            except StaleElementReferenceException:
                return True
        wait_for_condition(driver, expanded, restriction_check)


def read_profile(driver,url,name,restriction_check):
    driver.get(url)
    expected=urlsplit(url)
    def check_page(d):
        if restriction_check(d):raise ProfileRestricted('LinkedIn restriction or security check while reading profile')
        actual=urlsplit(d.current_url)
        if actual.hostname!=expected.hostname or actual.path.rstrip('/')!=expected.path.rstrip('/'):
            return False
        headings=profile_root(d).find_elements(By.CSS_SELECTOR,'h1,h2')
        # The first visible heading belongs to the owner, not a recommendation.
        visible=[h.text.strip() for h in headings if h.is_displayed() and h.text.strip()]
        return bool(visible and normalize(visible[0])==normalize(name))
    wait_for_condition(driver, check_page)
    # Check only the verified owner's top card, before expanding any sections.
    root=profile_root(driver)
    headings=[h for h in root.find_elements(By.CSS_SELECTOR,'h1,h2')
              if h.is_displayed() and normalize(h.text)==normalize(name)]
    if headings:
        cards=headings[0].find_elements(By.XPATH,'./ancestor::section[1]')
        if cards and cards[0].get_attribute('aria-label')!='Primary content':
            pending=[e for e in cards[0].find_elements(By.CSS_SELECTOR,'button,a,[role="button"]')
                     if e.is_displayed() and (e.text.strip()=='Pending' or
                         e.get_attribute('aria-label') in ('Pending',f'Pending invitation to {name}',f'Invitation pending for {name}'))]
            if pending:
                raise ProfileAlreadyPending('Invitation already pending on verified profile')
    collected={};truncated=set();expanded={};detail_links={}
    def ready(d):
        if restriction_check(d):raise ProfileRestricted('LinkedIn restriction while reading profile')
        actual=urlsplit(d.current_url)
        if actual.hostname!=expected.hostname or actual.path.rstrip('/')!=expected.path.rstrip('/'):
            raise ValueError('Profile URL changed while reading sections')
        root=profile_root(d)
        loading=any(e.is_displayed() for e in root.find_elements(
            By.CSS_SELECTOR,'[aria-busy="true"],[role="progressbar"]'))
        for title,section in matching_sections(d):
            if section.id not in expanded:
                expand_text(d,section,restriction_check)
                expanded[section.id]=True
            for link in section.find_elements(By.CSS_SELECTOR,'a[href]'):
                address=urlsplit(link.get_attribute('href'))
                detail_path=expected.path.rstrip('/')+'/details/'+title+'/'
                if address.hostname==expected.hostname and address.path==detail_path:
                    detail_links[title]=link.get_attribute('href')
            text=section.text.strip()
            lines=[line.strip() for line in text.splitlines() if line.strip()]
            if len(lines)>1:
                collected[title]=text
        # These owner cards follow education. Once rendered they also mark
        # the end of the relevant section range on shorter profiles.
        later_titles={'skills','recommendations','interests','honors & awards','languages'}
        end_seen = root.get_attribute('aria-label') == 'Primary content' and any(
            h.is_displayed() and h.text.strip().casefold() in later_titles
            for h in root.find_elements(By.CSS_SELECTOR,'section h2')
        )
        if collected and (len(collected)==len(SECTIONS) or end_seen) and not loading:
            return True
        if not loading:
            d.execute_script("""
                let el = arguments[0];
                while (el && !(el.scrollHeight > el.clientHeight &&
                    /auto|scroll/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
                el = el || document.scrollingElement;
                if (el && el.scrollTop + el.clientHeight < el.scrollHeight - 2)
                    el.scrollBy(0, Math.max(450, el.clientHeight * 0.75));
            """,root)
        return False

    status='ready'
    wait_for_condition(driver, ready)
    if not check_page(driver):
        raise ValueError('Profile identity changed while reading sections')
    detail_errors={}
    for title,link in detail_links.items():
        driver.get(link)
        last_text=None
        def detail_ready(d):
            nonlocal last_text
            if restriction_check(d):raise ProfileRestricted('LinkedIn restriction on profile detail page')
            if urlsplit(d.current_url).path!=urlsplit(link).path:
                raise ValueError('Profile detail URL changed')
            root=profile_root(d)
            if root.text.strip().split('\n',1)[0].casefold()!=title:return False
            expand_text(d,root,restriction_check)
            text=root.text.strip()
            if len(text.splitlines())<2:return False
            busy=any(e.is_displayed() for e in root.find_elements(By.CSS_SELECTOR,'[aria-busy="true"],[role="progressbar"]'))
            bottom=d.execute_script("""
                let el=arguments[0];
                while(el && !(el.scrollHeight>el.clientHeight && /auto|scroll/.test(getComputedStyle(el).overflowY)))el=el.parentElement;
                el=el||document.scrollingElement;
                const atEnd=el.scrollTop+el.clientHeight>=el.scrollHeight-2;
                if(!atEnd)el.scrollBy(0,Math.max(450,el.clientHeight*.75));
                return atEnd;
            """,root)
            settled=bottom and not busy and text==last_text
            last_text=text
            return text if settled else False
        try:
            collected[title] = wait_for_condition(driver, detail_ready)
        except ElementClickInterceptedException as error:
            detail_errors[title]=type(error).__name__
            status='incomplete'
    return {'url':url,'header':name,'sections':collected,
            'missing_sections':[key for key in SECTIONS if key not in collected],
            'truncated_sections':sorted(truncated),'source':'visible_profile_sections',
            'detail_pages':detail_links,'detail_errors':detail_errors,
            'read_status':status}
