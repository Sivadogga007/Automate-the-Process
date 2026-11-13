"""Guided personal setup with examples, validated formats, and explicit lists."""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from modules.networking_targets import DEFAULT_CATEGORIES, build_queries, effective_categories

ROOT = Path(__file__).resolve().parent


def section(title):
    print('\n' + '=' * 60 + '\n' + title + '\n' + '=' * 60)


def required(label, example, validate=None):
    while True:
        value = input(f'{label}\n  Example: {example}\n> ').strip()
        if not value:
            print('An answer is required. Examples are not filled in automatically.')
            continue
        if validate and not validate(value):
            print('That format is not valid. Follow the example shown above.')
            continue
        return value


def linkedin_url(value):
    try:
        url = urlsplit(value)
        if url.port:
            return False
    except ValueError:
        return False
    return (url.scheme == 'https' and url.hostname in ('linkedin.com', 'www.linkedin.com')
            and not url.username and not url.password and not url.port
            and bool(re.fullmatch(r'/in/[A-Za-z0-9_%.-]+/?', url.path)))


def month(value):
    if value.lower() == 'unknown':
        return True
    try:
        return bool(re.fullmatch(r'\d{4}-\d{2}', value)) and date.fromisoformat(value + '-01') is not None
    except ValueError:
        return False


def start_date(value):
    if value.lower() in ('immediately', 'unknown'):
        return True
    try:
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)) and date.fromisoformat(value) is not None
    except ValueError:
        return False


def choice(label, options):
    return required(label + ' [' + ' / '.join(options) + ']', options[0],
                    lambda value: value.lower() in options).lower()


def items(label, example):
    print(f'\n{label}\nEnter ONE item at a time. Press Enter on an empty line when finished.\nExample item: {example}')
    values = []
    while True:
        value = input(f'  Item {len(values) + 1}: ').strip()
        if not value:
            if values:
                return values
            print('Enter at least one item first.')
            continue
        if ';' in value:
            print('Enter one item per prompt, without semicolon separators.')
            continue
        if value.casefold() not in {v.casefold() for v in values}:
            values.append(value)


def yes_no(label):
    while True:
        value = input(label + ' [y/n]: ').strip().lower()
        if value in ('y', 'yes'): return True
        if value in ('n', 'no'): return False
        print('Enter y for yes or n for no.')


def ask_limit(default=5, task='network'):
    noun = 'jobs evaluated/attempted' if task == 'jobs' else 'connection attempts'
    print('Batch limit = ' + noun + '; not LinkedIn’s allowance or guaranteed successes.')
    while True:
        value = input(f'How many {noun} this batch? [1–100; Enter = {default}]: ').strip()
        if not value: return default
        if value.isdigit() and 1 <= int(value) <= 100: return int(value)
        print('Enter a whole number from 1 to 100.')


def collect_personal():
    section('1. Your identity')
    name = required('Full name as shown on LinkedIn', 'Alex Kumar')
    print('Find your URL: LinkedIn > Me > View Profile > copy the address from your browser.\n'
          'Use your personal /in/ URL, not the LinkedIn feed, a company page, or a search URL.')
    url = required('Your LinkedIn profile URL', 'https://www.linkedin.com/in/alex-kumar-123/', linkedin_url)
    parsed = urlsplit(url)
    url = 'https://www.linkedin.com' + parsed.path.rstrip('/') + '/'

    section('Education — one qualification at a time')
    education = []
    while True:
        education.append({
            'degree': required('Degree / qualification', 'M.Tech (or B.Sc, MBA, Diploma, none)'),
            'field': required('Subject / specialization', 'Industrial Engineering (or not applicable)'),
            'institution': required('University / institute', 'Example University (or not applicable)'),
            'status': choice('Study status', ['studying', 'completed', 'not applicable']),
            'graduation_month': required('Graduation month — actual if completed, expected if studying; YYYY-MM or unknown', '2027-07', month),
        })
        if choice('Add another qualification?', ['no', 'yes']) == 'no':
            break

    section('Work experience')
    years = required('Total years of paid professional experience (exclude internships); number or unknown',
                     '2.5 (enter 0 if none)', lambda v: v.lower() == 'unknown' or bool(re.fullmatch(r'\d{1,2}(\.\d{1,2})?', v)))
    experience = {'years': years,
                  'latest_role': required('Current or most recent job title; use none if no work experience', 'Software Engineer'),
                  'latest_employer': required('Current or most recent employer; use none if no work experience', 'Example Company'),
                  'summary': required('Briefly describe your work, internships or projects; one paragraph',
                                      'Built Python APIs for two years; completed a data analysis internship.')}

    section('Availability and work authorization')
    availability = required('Earliest date you can start; YYYY-MM-DD, immediately, or unknown', '2027-07-01', start_date)
    authorized = items('Countries where you CURRENTLY have the legal right to work; enter none if no countries', 'India')
    sponsorship = choice('Do you need employer visa sponsorship for any target country?', ['yes', 'no', 'unknown'])
    details = required('Explain country-specific visa needs; use none or unknown if appropriate',
                       'Can work in India; need sponsorship for Germany and Canada.')
    return {'name': name, 'linkedin_url': url, 'education': education, 'experience': experience,
            'availability': availability,
            'work_authorization': {'authorized_countries': authorized, 'needs_sponsorship': sponsorship, 'details': details},
            'personal_info_completed': True}


def ensure_profile(offer_personal=True):
    target = ROOT / 'profile.json'
    profile = json.loads(target.read_text()) if target.exists() else {}
    original = dict(profile)
    print('Contact categories can be changed in the control panel.')
    if not profile.get('target_roles'):
        profile['target_roles'] = items('Target job roles', 'Data Scientist')
    if not profile.get('locations'):
        profile['locations'] = items('Preferred locations, highest priority first', 'Mumbai, India')
    profile['contact_categories']=effective_categories(profile.get('contact_categories',DEFAULT_CATEGORIES))
    profile.setdefault('provider', 'openjev')
    profile.setdefault('endpoint', 'http://127.0.0.1:11436')
    profile.setdefault('model', 'openjev')
    legacy_complete = all(profile.get(k) for k in ('name','linkedin_url','education','experience','availability','work_authorization'))
    profile.setdefault('personal_info_completed', legacy_complete)
    if offer_personal and not profile['personal_info_completed']:
        print('Personal details improve matching and career answers, but are optional for connections.')
        if yes_no('Would you like to add your personal information now?'):
            profile.update(collect_personal())
        else:
            print('Skipped. We will offer again next time you open the launcher.')
    profile['queries'] = build_queries(profile)
    if profile != original:
        target.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
        target.chmod(0o600)
    print('Search roles: ' + ', '.join(profile['target_roles'] if isinstance(profile['target_roles'], list) else [profile['target_roles']]))
    return profile


def main():
    ensure_profile()


if __name__ == '__main__':
    main()
