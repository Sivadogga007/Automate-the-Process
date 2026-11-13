"""Local terminal career workspace. Never submits applications or sends messages."""
import argparse
import json
import sqlite3
from pathlib import Path
from modules import career_workspace as work

ROOT = Path(__file__).resolve().parent


def settings():
    path = ROOT / 'career-settings.json'
    if not path.exists():
        path.write_text(json.dumps({'text_endpoint': 'http://127.0.0.1:11434', 'text_model': 'qwen3.8:27b',
                                    'choice_endpoint': 'http://127.0.0.1:11436'}, indent=2))
        path.chmod(0o600)
    return json.loads(path.read_text())


def profile_facts():
    profile = json.loads((ROOT / 'profile.json').read_text())
    # Include only applicant data, not API/SSH settings.
    facts = {key: profile[key] for key in ('name', 'education', 'experience', 'target_roles', 'locations', 'availability', 'work_authorization') if key in profile}
    for key in ('skills', 'languages', 'projects', 'achievements', 'behavioral_preferences'):
        if key in profile:
            facts[key] = profile[key]
    from modules.answer_memory import AnswerMemory
    facts['confirmed_answers'] = AnswerMemory(ROOT / 'profile.json').relevant('')
    evidence = ROOT / 'private/evidence.txt'
    if evidence.exists():
        facts['additional_verified_facts'] = evidence.read_text(encoding='utf-8')
    return facts


def job(db):
    key = input('Job ID (copy from List): ').strip()
    row = db.execute('SELECT * FROM workspace_jobs WHERE id=?', (key,)).fetchone()
    if not row:
        raise ValueError('Unknown job ID. Choose List to see saved jobs.')
    return row


def menu():
    config = settings()
    print('LOCAL CAREER WORKSPACE — drafts only; no automatic applications or outreach.\n'
          'Text: ' + config['text_model'] + ' | Decisions: OpenJev\n'
          'Add verified résumé/project details to private/evidence.txt for richer answers.\n'
          'Do not include passwords. Profile and evidence are sent to your configured model servers.')
    with work.connect(ROOT / 'private/career.sqlite3') as db:
        while True:
            print('\n1 Import job description   2 List/rank jobs   3 Evaluate fit\n'
                  '4 Draft application + interview packet   5 Answer a form question\n'
                  '6 Record outcome   7 Import existing opportunity queue   0 Exit')
            command = input('Choose a number: ').strip()
            try:
                if command == '0':
                    return
                if command == '1':
                    company = input('Company (example: Example Labs): ').strip()
                    title = input('Role (example: Research Engineer): ').strip()
                    url = input('Original posting URL (https://...): ').strip()
                    path = Path(input('Path to saved job description (.txt or .html; drag file here): ').strip().strip('"\'' )).expanduser()
                    key, added = work.import_posting(db, company, title, url, path.read_text(encoding='utf-8'), 'html' if path.suffix.lower() in ('.html','.htm') else 'text')
                    print(('Saved: ' if added else 'Already tracked: ') + key)
                    print(json.loads(db.execute('SELECT findings FROM workspace_jobs WHERE id=?',(key,)).fetchone()[0])['verdict'])
                elif command == '2':
                    rows = list(db.execute('SELECT * FROM workspace_jobs'))
                    rows.sort(key=lambda r: (json.loads(r['assessment']).get('weighted_score') or -1) if r['assessment'] else -1, reverse=True)
                    for row in rows:
                        assessment = json.loads(row['assessment']) if row['assessment'] else {}
                        print(json.dumps({'id': row['id'], 'company':row['company'],'title':row['title'],'status':row['status'],
                                          'score':assessment.get('weighted_score'),'coverage':assessment.get('coverage'),'decision':assessment.get('decision','unevaluated')},ensure_ascii=False))
                elif command == '3':
                    row = job(db)
                    findings = json.loads(row['findings'])
                    if '⚠' in findings.get('verdict',''):
                        raise ValueError('Posting contains suspicious instructions/encoding. Review the source and import a corrected posting before model processing.')
                    print('Evaluating with the text model and OpenJev. Stay in this terminal; this can take a few minutes.', flush=True)
                    result = work.assess(row['posting'], profile_facts(), config)
                    db.execute('UPDATE workspace_jobs SET assessment=?,packet=NULL,updated=? WHERE id=?',(json.dumps(result),work.now(),row['id']))
                    db.commit()
                    print(json.dumps(result,indent=2))
                elif command == '4':
                    row = job(db)
                    if not row['assessment']:
                        raise ValueError('Evaluate fit first (option 3).')
                    print('Drafting, then reviewing source evidence. Wait here; no application will be submitted.', flush=True)
                    result = work.packet(row['posting'], profile_facts(), json.loads(row['assessment']), config)
                    db.execute('UPDATE workspace_jobs SET packet=?,updated=? WHERE id=?',(json.dumps(result),work.now(),row['id']))
                    db.commit()
                    row = db.execute('SELECT * FROM workspace_jobs WHERE id=?',(row['id'],)).fetchone()
                    print('Saved draft: ' + str(work.export_packet(row,ROOT/'private/packets')))
                    print('Review state: ' + result['state'])
                    print('Open the saved .md file in a text editor and review it. Return here to choose your next action.')
                elif command == '5':
                    question = input('Paste the exact form question: ').strip()
                    print('For dropdown/multiple-choice: enter ONE option per line; blank line finishes.\nFor a free-text answer, press Enter immediately.')
                    options = []
                    while True:
                        option = input('Option: ').strip()
                        if not option: break
                        options.append(option)
                    print('Preparing a grounded answer; OpenJev will choose an option if supplied. Wait here.', flush=True)
                    print(json.dumps(work.answer(question,profile_facts(),config,options or None),indent=2))
                elif command == '6':
                    row = job(db)
                    print('States: ' + ', '.join(work.STATES))
                    state = input('Observed outcome: ').strip()
                    proof = input('Factual note / confirmation reference (example: confirmation email received on YYYY-MM-DD): ').strip()
                    work.record_outcome(db,row['id'],state,proof)
                    print('Recorded as user-reported; the app did not submit anything.')
                elif command == '7':
                    path = Path(input('Path to existing career.sqlite3: ').strip().strip('"\'')).expanduser()
                    # Read-only access; never modify the original queue or status.
                    if not path.is_file(): raise ValueError('Database not found.')
                    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as source:
                        count=0
                        for url,raw in source.execute('SELECT url,details FROM opportunities'):
                            details=json.loads(raw)
                            sections=details.get('sections',{})
                            posting=sections.get('job_posting') if isinstance(sections,dict) else None
                            text=posting or json.dumps(details,ensure_ascii=False)
                            _, added=work.import_posting(db, str(details.get('company') or 'Unknown company'),str(details.get('title') or 'Imported opportunity'),url,text)
                            count+=added
                    print(f'Imported {count} new postings. Existing submission status was not inferred.')
                else:
                    print('Choose a listed number.')
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
                print('Stopped this operation: ' + str(error))
                print('No application was submitted. Check facts/model connectivity before retrying.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    menu()
