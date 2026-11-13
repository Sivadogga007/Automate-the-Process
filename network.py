"""Find relevant recruiters and send invitations; use --preview to search only."""
import argparse
import json
import socket
import sqlite3
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit

from modules.networking_targets import DEFAULT_CATEGORIES, build_queries, effective_categories

ROOT = Path(__file__).resolve().parent

def load_profile():
    profile = json.loads((ROOT / 'profile.json').read_text())
    profile['contact_categories']=effective_categories(profile.get('contact_categories',DEFAULT_CATEGORIES))
    profile['queries'] = build_queries(profile)
    required = ('target_roles', 'locations', 'queries', 'provider', 'endpoint', 'model')
    if any(not profile.get(k) for k in required):
        raise ValueError('Complete all profile fields using setup.py or edit profile.json.')
    url = urlsplit(profile.get('linkedin_url', ''))
    if profile.get('linkedin_url') and (url.hostname not in ('linkedin.com', 'www.linkedin.com') or not url.path.startswith('/in/')):
        raise ValueError('Use your own LinkedIn /in/ profile URL.')
    if profile['provider'] not in ('ollama', 'openjev'):
        raise ValueError('Provider must be ollama or openjev.')
    if not isinstance(profile['queries'], list) or not all(isinstance(q, str) and q.strip() for q in profile['queries']):
        raise ValueError('queries must be a nonempty list of searches.')
    if urlsplit(profile['endpoint']).scheme not in ('http', 'https'):
        raise ValueError('Model endpoint must be an HTTP(S) URL.')
    return profile

def confirm_profile_url(profile):
    from setup import linkedin_url
    print('\nRETURN TO THIS TERMINAL after signing in.\n'
          'In Chrome: LinkedIn > Me > View Profile. Copy the address from the address bar.\n'
          'Example: https://www.linkedin.com/in/alex-kumar-123/\n'
          'Paste your own profile URL below, then press Enter. The app waits here; it has not started sending.')
    if profile.get('linkedin_url'):
        print('Expected profile: ' + profile['linkedin_url'])
    while True:
        value = input('Your signed-in LinkedIn profile URL: ').strip()
        if not linkedin_url(value):
            print('Use the full https://www.linkedin.com/in/... profile URL, not the feed or a company page.')
            continue
        parsed = urlsplit(value)
        normalized = 'https://www.linkedin.com' + parsed.path.rstrip('/') + '/'
        if profile.get('linkedin_url'):
            expected = urlsplit(profile['linkedin_url']).path.rstrip('/')
            if parsed.path.rstrip('/') != expected:
                raise RuntimeError('That URL differs from your saved account. No invitations sent. Check which LinkedIn account is signed in before restarting.')
        return normalized


def main():
    from modules.panel_input import install
    install()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', dest='execute', action='store_true', help='Send invitations (default)')
    mode.add_argument('--preview', dest='execute', action='store_false', help='Search only')
    parser.set_defaults(execute=True)
    parser.add_argument('--limit', type=int, default=5, help='Verified invitations to send')
    parser.add_argument('--pages', type=int, default=1)
    parser.add_argument('--keep-open', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or not 1 <= args.pages <= 10:
        parser.error('Use limit 1–100 and pages 1–10.')
    profile = load_profile()
    # Check model before starting the browser; never silently switch providers.
    endpoint = profile['endpoint'].rstrip('/')
    with urlopen(endpoint + ('/health' if profile['provider'] == 'openjev' else '/api/tags'), timeout=5) as response:
        health = json.load(response)
    if profile['provider'] == 'ollama':
        models = {m['name'] for m in health.get('models', [])}
        if profile['model'] not in models and profile['model'] + ':latest' not in models:
            raise ValueError('Configured Ollama model is not installed on this endpoint.')
    from selenium import webdriver
    from modules.connection_agent import run
    # Cross-platform lock. A second controller must not share the browser profile.
    lock = socket.socket()
    try:
        lock.bind(('127.0.0.1', 47853))
    except OSError:
        raise SystemExit('Another networking runner is active (or local port 47853 is occupied).')
    data = ROOT / 'private'
    data.mkdir(exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument('--user-data-dir=' + str(data / 'browser'))
    options.page_load_strategy = 'eager'
    print('\nChrome will open your saved LinkedIn browser session. Existing sign-in will be checked automatically.\n'
          'If you are already signed in, check that it is your account.\n'
          'Only if prompted: open Me > View Profile, copy your URL, and return to THIS terminal.', flush=True)
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as error:
        lock.close()
        raise RuntimeError('Could not start the app browser. Close its previous Chrome window and controller, then retry. Check Chrome is installed. Original error: ' + str(error)) from error
    from modules.connection_control import ConnectionControl
    control=ConnectionControl(data/'career.sqlite3')
    driver.set_page_load_timeout(45)
    try:
        from modules.login_session import ensure_session
        ensure_session(driver,profile,ROOT,confirm_profile_url)
        print('Account confirmation received. Starting ' + ('invitation sending' if args.execute else 'preview only') + '. Keep Chrome and this terminal open.', flush=True)
        applicant = {k: profile[k] for k in ('education', 'experience', 'target_roles', 'locations', 'availability', 'work_authorization', 'contact_categories', 'custom_contact_types') if k in profile}
        with sqlite3.connect(data / 'career.sqlite3') as db:
            while True:
                print(json.dumps({'state':'batch_started','target':args.limit}),flush=True)
                outcomes = run(driver, db, endpoint, profile['model'], args.limit, args.execute, args.pages,
                               decision_provider=profile['provider'], decision_endpoint=endpoint,
                               applicant=applicant, queries=profile['queries'], control=control)
                (data / 'last-run.json').write_text(json.dumps(outcomes, indent=2))
                print(json.dumps({'mode': 'execute' if args.execute else 'preview',
                                  'target':args.limit,'verified_sent': sum(o['state'] == 'sent' for o in outcomes), 'outcomes': outcomes}))
                print('Batch finished or stopped. Verified sent counts only confirmed Pending states.\n'
                      'An uncertain invitation is not retried automatically. Review any error above before continuing.', flush=True)
                if not args.keep_open or input('Keep this terminal and Chrome open. Type run + Enter for another batch, or close + Enter to exit: ').strip().lower() != 'run':
                    break
    finally:
        control.finish()
        driver.quit()
        lock.close()

if __name__ == '__main__':
    main()
