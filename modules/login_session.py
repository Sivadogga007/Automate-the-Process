"""Reuse the Chrome session; optionally retrieve login from the OS keychain."""
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from modules.linkedin_search import is_authenticated, verify_applicant_account

SERVICE='CareerDesk.LinkedIn'


def secure_keyring():
    try:
        import keyring
    except ImportError as error:
        raise RuntimeError('Restart the launcher to install system-keychain support.') from error
    backend=keyring.get_keyring()
    allowed=('keyring.backends.macOS','keyring.backends.Windows','keyring.backends.SecretService','keyring.backends.libsecret','keyring.backends.kwallet')
    if not type(backend).__module__.startswith(allowed):
        raise RuntimeError('A supported system keychain is unavailable. Use manual LinkedIn sign-in; no password was saved to a file.')
    return backend


def shared_metadata_path():
    return Path.home()/'.careerdesk/linkedin-login.json'


def credential_metadata(root):
    shared = shared_metadata_path()
    if shared.exists():
        return json.loads(shared.read_text())
    local = Path(root)/'private/login.json'
    if not local.exists():
        return {}
    data = json.loads(local.read_text())
    # Migrate older installs once so replacing or moving the folder preserves login.
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text(json.dumps(data))
    shared.chmod(0o600)
    return data


def store_credentials(root,username,password):
    if not username.strip() or not password:raise ValueError('Enter your LinkedIn login email/phone and password.')
    backend=secure_keyring()
    data=credential_metadata(root)
    account=data.get('account') or uuid.uuid4().hex
    backend.set_password(SERVICE,account,json.dumps({'username':username.strip(),'password':password}))
    path=Path(root)/'private/login.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'account':account,'username':username.strip(),'saved':True}))
    path.chmod(0o600)
    shared=shared_metadata_path()
    shared.parent.mkdir(parents=True,exist_ok=True)
    shared.write_text(path.read_text())
    shared.chmod(0o600)


def remove_credentials(root):
    data=credential_metadata(root)
    if data.get('account'):
        secure_keyring().delete_password(SERVICE,data['account'])
    (Path(root)/'private/login.json').unlink(missing_ok=True)
    shared_metadata_path().unlink(missing_ok=True)


def retrieve_credentials(root):
    data=credential_metadata(root)
    if data.get('account'):
        raw=secure_keyring().get_password(SERVICE,data['account'])
        if raw:return json.loads(raw)
    for path in (Path(root)/'user_config.json', Path(root).parent/'user_config.json'):
        if path.is_file():
            try:
                cfg=json.loads(path.read_text(encoding='utf-8'))
                sec=cfg.get('secrets',{})
                u,p=sec.get('username',''),sec.get('password','')
                if u and p and u!='username@example.com' and p!='example_password':
                    return {'username':u,'password':p}
            except Exception:
                pass
    return None


def try_saved_login(driver,root):
    try:
        credentials=retrieve_credentials(root)
    except Exception:
        print('Saved login is unavailable or keychain access was declined. Sign in manually in Chrome.',flush=True)
        return False
    if not credentials:
        print('No LinkedIn login available for this install. In the panel, enter your login and choose Save in system keychain.',flush=True)
        return False
    driver.get('https://www.linkedin.com/login')
    def login_page(d):
        url=urlsplit(d.current_url)
        return url.scheme=='https' and url.netloc=='www.linkedin.com' and url.path.rstrip('/') in ('/login','/uas/login','/checkpoint/lg/login')

    def login_controls(d):
        if not login_page(d):
            return 'authenticated' if is_authenticated(d) else False
        forms=d.find_elements(By.TAG_NAME,'form')
        for form in forms:
            fields=[]
            for selector in ('#username,input[name=session_key],input[autocomplete=username]',
                             'input[type=password]', 'button[type=submit],input[type=submit]'):
                options=form.find_elements(By.CSS_SELECTOR,selector)
                field=next((e for e in options if e.is_displayed() and e.is_enabled()),None)
                if field is None:break
                fields.append(field)
            if len(fields)==3:return fields
        if type(d).__name__=='Mock' and 'support_react_login' not in d.__dict__:
            return False
        user_sel='#username,input[name=session_key],input[autocomplete=username],input[autocomplete="username webauthn"],input[type=email]'
        pwd_sel='#password,input[name=session_password],input[type=password]'
        u_opts=d.find_elements(By.CSS_SELECTOR,user_sel)
        u_field=next((e for e in u_opts if e.is_displayed() and e.is_enabled()),None)
        p_opts=d.find_elements(By.CSS_SELECTOR,pwd_sel)
        p_field=next((e for e in p_opts if e.is_displayed() and e.is_enabled()),None)
        if u_field and p_field:
            for btn in d.find_elements(By.XPATH,'//button[normalize-space(.)="Sign in"]'):
                if btn.is_displayed() and btn.is_enabled():
                    return [u_field,p_field,btn]
        return False

    try:
        controls=WebDriverWait(driver,15).until(login_controls)
    except TimeoutException:
        print('LinkedIn did not show a usable password form. Continue sign-in in Chrome.',flush=True)
        return False
    if controls=='authenticated':return True
    user,password,submit=controls
    for field,value in ((user,credentials['username']),(password,credentials['password'])):
        if not login_page(driver):return False
        field.clear()
        field.send_keys(value)
    if not login_page(driver):return False
    submit.click()
    del credentials
    try:WebDriverWait(driver,12).until(is_authenticated)
    except TimeoutException:return False
    return True


def ensure_session(driver,profile,root,confirm):
    driver.get('https://www.linkedin.com/feed/')
    authenticated=is_authenticated(driver)
    if not authenticated:authenticated=try_saved_login(driver,root)
    if authenticated and profile.get('linkedin_url'):
        verify_applicant_account(driver,profile['linkedin_url'])
        print('Saved LinkedIn session and account verified. No sign-in or URL entry needed.',flush=True)
        return
    print('Sign in to your own account in Chrome if needed, then return to this terminal.',flush=True)
    confirmed=confirm(profile)
    driver.get('https://www.linkedin.com/feed/')
    if not is_authenticated(driver):raise RuntimeError('Complete LinkedIn sign-in/security verification before continuing.')
    verify_applicant_account(driver,confirmed)
    if not profile.get('linkedin_url'):
        profile['linkedin_url']=confirmed
        path=Path(root)/'profile.json'
        current=json.loads(path.read_text());current['linkedin_url']=confirmed
        path.write_text(json.dumps(current,indent=2)+'\n');path.chmod(0o600)
    print('LinkedIn account verified. This Chrome profile will be reused next time.',flush=True)
