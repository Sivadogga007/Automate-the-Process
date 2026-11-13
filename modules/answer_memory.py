"""User-confirmed form answers with explicit reuse scope and atomic profile writes."""
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def normalized(question):
    return ' '.join(question.casefold().split())


def fingerprint(profile):
    facts={k:v for k,v in profile.items() if k not in ('confirmed_answers','queries','contact_categories','provider','endpoint','model','personal_info_completed')}
    return hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()


def valid(value,kind,options):
    if not isinstance(value,str) or not value.strip(): return False
    if options: return value in options
    if kind=='number': return bool(re.fullmatch(r'[-+]?\d+(\.\d+)?',value))
    if kind=='email': return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value))
    return True


class AnswerMemory:
    def __init__(self,path):
        self.path=Path(path)

    def load(self):
        return json.loads(self.path.read_text())

    def relevant(self,url):
        profile=self.load();today=datetime.now(timezone.utc).date().isoformat()
        return [e for e in profile.get('confirmed_answers',[]) if e.get('profile_fingerprint')==fingerprint(profile)
                and (e['scope']=='reusable' or (e['scope']=='application' and e.get('job_url')==url)
                     or (e['scope']=='today' and e['created'][:10]==today))]

    def lookup(self,question,options,kind,url):
        for entry in reversed(self.relevant(url)):
            if normalized(entry['question'])==normalized(question) and entry.get('kind')==kind and entry.get('options',[])==(options or []):
                if valid(entry['answer'],kind,options): return self.result(entry)
        return None

    @staticmethod
    def result(entry):
        result={'unknown':False,'answer':entry['answer'],'profile_quote':entry['answer'],
                'source':'user_confirmed','scope':entry['scope']}
        if entry.get('options'): result['selected_option']=entry['answer']
        return result

    def save(self,question,value,options,kind,url,scope):
        if scope not in ('reusable','application','today') or not valid(value,kind,options):
            raise ValueError('Invalid answer or reuse scope')
        profile=self.load()
        entry={'question':question,'answer':value,'options':options or [],'kind':kind,'job_url':url,
               'scope':scope,'created':datetime.now(timezone.utc).isoformat(),'source':'user_confirmed',
               'profile_fingerprint':fingerprint(profile)}
        profile.setdefault('confirmed_answers',[]).append(entry)
        fd,temp=tempfile.mkstemp(prefix='.profile-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as out:
                json.dump(profile,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return self.result(entry)

    def ask(self,question,options,kind,url):
        print('\n'+'='*60+'\nYOUR ANSWER IS NEEDED — return to this terminal.\n'
              'Chrome will wait. Nothing is submitted while this question is unanswered.\n'
              'Job: '+url+'\nQuestion: '+question,flush=True)
        if options:
            for i,value in enumerate(options,1): print(f'  {i}. {value}')
            print('Enter the option number, or type skip to leave this application blocked.')
        else:
            print('Enter the exact answer to fill'+(' (number only)' if kind=='number' else '')+'. Type skip to stop this application.')
        while True:
            value=input('Your answer: ').strip()
            if value.casefold()=='skip': return None
            if options and value.isdigit() and 1<=int(value)<=len(options):value=options[int(value)-1]
            if valid(value,kind,options):break
            print('Enter a valid value'+(' or a listed option number.' if options else '.'))
        print('Save scope: 1 = reusable personal fact; 2 = only this job; 3 = today only (UTC).\n'
              'Use only-this-job for employer/country-specific answers, and today for temporary facts such as offer deadlines.')
        while True:
            scope=input('Scope [Enter = 2]: ').strip() or '2'
            if scope in ('1','2','3'):break
            print('Choose 1, 2 or 3.')
        result=self.save(question,value,options,kind,url,{'1':'reusable','2':'application','3':'today'}[scope])
        print('Saved your answer locally. Continuing this application.',flush=True)
        return result
