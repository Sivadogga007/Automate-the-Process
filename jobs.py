"""LinkedIn Easy Apply task using the shared profile and local model services."""
import json
import socket
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent


def prepare_profile(profile, interactive=True):
    from setup import collect_personal, required
    needed=('name','linkedin_url','education','experience','availability','work_authorization')
    if any(not profile.get(k) for k in needed):
        if not interactive: raise ValueError('Easy Apply needs the personal profile fields shown in the control panel.')
        print('Job applications require your personal details; these cannot be skipped for this task.')
        profile.update(collect_personal())
    fields=[('email','Application email','alex@example.com'),('phone','Phone including country code','+91 9876543210'),
            ('current_city','Current city','Mumbai, India'),('resume_path','Absolute path to your PDF resume','/Users/alex/Documents/resume.pdf')]
    for key,label,example in fields:
        if not profile.get(key):
            if not interactive: raise ValueError('Fill '+label+' in the control panel.')
            profile[key]=required(label,example)
    resume=Path(profile['resume_path']).expanduser().resolve()
    if not resume.is_file() or resume.suffix.lower()!='.pdf': raise ValueError('Select an existing PDF resume file.')
    if '@' not in profile['email']: raise ValueError('Enter a valid application email.')
    profile['resume_path']=str(resume)
    target=ROOT/'profile.json';target.write_text(json.dumps(profile,indent=2)+'\n');target.chmod(0o600)
    return profile


def main(limit=5,pages=1,execute=True):
    from selenium import webdriver
    from modules.linkedin_search import verify_applicant_account
    from modules.easy_apply import run
    from modules.answer_memory import AnswerMemory
    from network import load_profile,confirm_profile_url
    from career import settings,profile_facts
    profile=prepare_profile(load_profile(),interactive=False)
    facts=profile_facts()
    facts.update({k:profile[k] for k in ('name','email','phone','current_city','linkedin_url')})
    lock=socket.socket()
    try: lock.bind(('127.0.0.1',47853))
    except OSError: raise RuntimeError('Another app task is active. Finish it before applying.')
    private=ROOT/'private';private.mkdir(exist_ok=True)
    options=webdriver.ChromeOptions(); options.add_argument('--user-data-dir='+str(private/'browser'))
    print('Chrome will open LinkedIn. Sign in there, then return here to confirm your profile URL.',flush=True)
    driver=None
    try:
        driver=webdriver.Chrome(options=options);driver.set_page_load_timeout(45)
        from modules.login_session import ensure_session
        ensure_session(driver,profile,ROOT,confirm_profile_url)
        print('Account verified. '+('Submitting eligible Easy Apply applications.' if execute else 'Preview: will stop before submission.'),flush=True)
        with sqlite3.connect(private/'career.sqlite3') as db:
            outcomes=run(driver,db,profile,facts,settings(),Path(profile['resume_path']),limit,pages,execute,memory=AnswerMemory(ROOT/'profile.json'))
        (private/'applications-last-run.json').write_text(json.dumps(outcomes,indent=2))
        print(json.dumps({'verified_submissions':sum(x['state']=='submitted' for x in outcomes),'outcomes':outcomes}),flush=True)
        input('Batch stopped/finished. Inspect Chrome if a form is blocked. Press Enter here to close the app browser: ')
    finally:
        if driver: driver.quit()
        lock.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=5);p.add_argument('--pages',type=int,default=1);p.add_argument('--preview',action='store_true')
    args=p.parse_args()
    if not 1<=args.limit<=100 or not 1<=args.pages<=10: p.error('Invalid limit/pages')
    main(args.limit,args.pages,not args.preview)
