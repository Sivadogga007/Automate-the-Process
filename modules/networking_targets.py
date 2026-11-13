"""Contact audiences, interactive selection and interleaved search generation."""
from itertools import zip_longest

DEFAULT_CATEGORIES = ['recruiters', 'iitb_ieor_alumni']
CATEGORIES = {
    'recruiters': 'Recruiters',
    'iitb_ieor_alumni': 'IIT Bombay IEOR alumni',
    'managers': 'Hiring managers / team leads',
    'iitb_alumni': 'IIT Bombay alumni (any department)',
    'professionals': 'Professionals in my target roles',
}


def effective_categories(categories):
    """Broader alumni targeting includes IEOR; ignore the retired faculty option."""
    return list(dict.fromkeys(
        category for category in categories
        if category != 'iitb_faculty'
        and not (category == 'iitb_ieor_alumni' and 'iitb_alumni' in categories)
    ))


def select_categories(current=None):
    selected = effective_categories(DEFAULT_CATEGORIES if current is None else current)
    keys = list(CATEGORIES)
    print('\nWho would you like to connect with?')
    for index, key in enumerate(keys, 1):
        print(f"  {index}. [{'x' if key in selected else ' '}] {CATEGORIES[key]}")
    print('Press Enter to keep the selected options, or enter option numbers separated by commas.')
    print('Example: 1,2,3 selects recruiters, IEOR alumni and managers. Example: 2 selects only IIT Bombay IEOR alumni.')
    while True:
        answer = input('Contact categories: ').strip()
        if not answer:
            return selected
        values = [value.strip() for value in answer.split(',')]
        if all(value in [str(i) for i in range(1,len(keys)+1)] for value in values):
            return list(dict.fromkeys(keys[int(value)-1] for value in values))
        print('Use the displayed option numbers separated by commas; for example 1,2.')


def values(value):
    return [value] if isinstance(value, str) else value


def build_queries(profile):
    categories = effective_categories(profile.get('contact_categories', DEFAULT_CATEGORIES))
    custom = profile.get('custom_contact_types', [])
    if not (categories or custom) or any(key not in CATEGORIES for key in categories):
        raise ValueError('Select at least one supported contact category.')
    roles, locations = values(profile['target_roles']), values(profile['locations'])
    groups = []
    for category in categories:
        if category == 'recruiters':
            groups.append([f'{role} recruiter {place}' for place in locations for role in roles])
        elif category == 'managers':
            groups.append([f'{role} {title} {place}' for place in locations for role in roles
                           for title in ('hiring manager', 'team lead')])
        elif category == 'professionals':
            groups.append([f'{role} {place}' for place in locations for role in roles])
        elif category == 'iitb_alumni':
            groups.append(['IIT Bombay alumni', 'IIT Bombay graduate'])
        else:
            groups.append(['IIT Bombay IEOR alumni', 'IIT Bombay Industrial Engineering Operations Research alumni',
                           'IIT Bombay IEOR graduate'])
    for label in custom:
        groups.append([f'{label} {place}' for place in locations])
    # Avoid consuming a whole batch on recruiters before reaching alumni.
    return list(dict.fromkeys(query for row in zip_longest(*groups) for query in row if query))
