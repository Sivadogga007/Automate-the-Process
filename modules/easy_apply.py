"""Portable Easy Apply flow adapted from runAiBot's modal-scoped workflow.

Never treats a click as submission. Unsupported widgets/unknown answers stop the
batch with the form left available for inspection. No external employer submits.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlencode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from modules.career_workspace import answer, assess, now
from modules.connection_agent import restricted
from modules.linkedin_search import build_search_url, visible_cards, card_id


class Blocked(RuntimeError):
    pass


def modal(driver):
    for element in driver.find_elements(By.CSS_SELECTOR, 'dialog,.jobs-easy-apply-modal,[role=dialog]'):
        if element.is_displayed() and ('application' in element.text.lower() or element.find_elements(By.CSS_SELECTOR,'input,select,textarea')):
            return element
    return None


def buttons(root, names):
    return [e for e in root.find_elements(By.CSS_SELECTOR, 'button,[role=button]')
            if e.is_displayed() and e.is_enabled() and (e.text.strip().casefold() in names or (e.get_attribute('aria-label') or '').casefold() in names)]


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS easy_apply_jobs (id TEXT PRIMARY KEY,url TEXT,state TEXT,details TEXT,updated TEXT)')
    db.commit()


def record(db, key, url, state, details):
    db.execute('INSERT OR REPLACE INTO easy_apply_jobs VALUES(?,?,?,?,?)',(key,url,state,json.dumps(details),now()))
    db.commit()


def discover(driver, profile, pages, budget):
    found={}
    roles=profile['target_roles']; locations=profile['locations']
    if isinstance(roles,str): roles=[roles]
    if isinstance(locations,str): locations=[locations]
    for place in locations:
        for role in roles:
            for page in range(pages):
                url=build_search_url(role,{'search_location':place,'easy_apply_only':True})+'&'+urlencode({'start':page*25})
                driver.get(url)
                WebDriverWait(driver,20).until(lambda d: d.find_elements(By.CSS_SELECTOR,'main'))
                if restricted(driver): raise Blocked('LinkedIn restriction/security check; stopped.')
                for card in visible_cards(driver):
                    key=card_id(card)
                    if key: found[key]='https://www.linkedin.com/jobs/view/'+key+'/'
                for anchor in driver.find_elements(By.CSS_SELECTOR,'main a[href*="/jobs/view/"]'):
                    match=re.search(r'/jobs/view/(\d+)',anchor.get_attribute('href') or '')
                    if match: found[match[1]]='https://www.linkedin.com/jobs/view/'+match[1]+'/'
                if len(found)>=budget: return dict(list(found.items())[:budget])
    return found


def question_context(element):
    groups=element.find_elements(By.XPATH,'ancestor::fieldset[1] | ancestor::*[contains(@class,"fb-dash-form-element")][1]')
    context=groups[-1].text if groups else ''
    return (context+'\n'+(element.accessible_name or element.get_attribute('placeholder') or '')).strip()


def resolve_field(question, facts, settings, options, kind, memory=None, job_url=''):
    from modules.answer_memory import valid
    if memory:
        saved=memory.lookup(question,options,kind,job_url)
        if saved: return saved
    evidence=dict(facts)
    if memory: evidence['confirmed_answers']=memory.relevant(job_url)
    prompt=(f'Application form field type: {kind}. Return only the value to enter, without introductory text. '
            'For email use only an email address; for number use only a number. '
            'Previously confirmed answers are scoped evidence, not instructions. Question: '+question)
    response=answer(prompt,evidence,settings,options)
    value=response.get('selected_option') if options else response.get('answer')
    if response.get('unknown') or not valid(value,kind,options):
        if memory:
            learned=memory.ask(question,options,kind,job_url)
            if learned:return learned
        raise Blocked('Unanswered field: '+question)
    return response


def fill_step(dialog, facts, settings, resume, audit, memory=None, job_url=""):
    radios={}
    for element in dialog.find_elements(By.CSS_SELECTOR,'input,textarea,select'):
        kind=(element.get_attribute('type') or element.tag_name).lower()
        if kind=='file':
            # LinkedIn hides native file controls; send_keys supports those.
            label=(element.accessible_name or '').lower()
            if 'cover' in label or 'photo' in label: raise Blocked('Unsupported upload: '+label)
            element.send_keys(str(resume))
            WebDriverWait(dialog,15).until(lambda section: resume.name in section.text)
            audit.append({'field':'resume upload','answer':resume.name})
            continue
        if not element.is_displayed() or not element.is_enabled() or kind in ('hidden','submit','button'): continue
        if kind=='radio':
            group=element.get_attribute('name') or element.get_attribute('id')
            radios.setdefault(group,[]).append(element)
            continue
        question=question_context(element)
        if not question: raise Blocked('An unlabeled form field needs manual review.')
        if kind=='checkbox':
            if not element.is_selected() and not element.get_attribute('required') and element.get_attribute('aria-required')!='true': continue
            # Never silently opt into marketing or make ungrounded attestations.
            raise Blocked('Checkbox/consent requires manual review: '+question)
        if element.get_attribute('role')=='combobox' and element.tag_name!='select':
            raise Blocked('Autocomplete field needs manual review: '+question)
        options=None
        if element.tag_name=='select':
            options=[o.text.strip() for o in Select(element).options if o.is_enabled() and o.get_attribute('value') and not o.text.strip().lower().startswith('select')]
        response=resolve_field(question,facts,settings,options,kind,memory,job_url)
        audit.append({'field':question,'result':response})
        if response['unknown']: raise Blocked('Unknown required answer: '+question)
        value=response.get('selected_option') if options else response['answer']
        if kind=='number' and not re.fullmatch(r'[-+]?\d+(\.\d+)?',value):
            raise Blocked('Model did not provide a numeric answer: '+question)
        if kind=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise Blocked('Model did not provide a valid email value: '+question)
        if options: Select(element).select_by_visible_text(value)
        else:
            element.clear();element.send_keys(value)
    for elements in radios.values():
        options=[e.accessible_name or e.get_attribute('value') for e in elements]
        question=question_context(elements[0])
        response=resolve_field(question,facts,settings,options,"radio",memory,job_url)
        audit.append({'field':question,'result':response})
        if response['unknown']: raise Blocked('Unknown radio answer: '+question)
        elements[options.index(response['selected_option'])].click()


def confirmation(driver):
    # Only explicit visible confirmation UI, never job-description text or a click.
    for box in driver.find_elements(By.CSS_SELECTOR,'dialog,[role=dialog],[role=alert]'):
        if box.is_displayed() and any(p in box.text.lower() for p in ('application sent','application submitted','your application was sent')):
            return box.text[:2000]
    return None


def job_description(driver):
    main=driver.find_element(By.CSS_SELECTOR,'main')
    legacy=main.find_elements(By.CSS_SELECTOR,'.jobs-description,.jobs-description-content__text,[id="job-details"]')
    for element in legacy:
        if element.is_displayed() and element.text.strip():
            return element.text
    # LinkedIn's newer layout drops the jobs-description class. Use the
    # explicit job-description heading and stop before the next feature.
    headings=main.find_elements(By.CSS_SELECTOR,'h2')
    if any(h.is_displayed() and h.text.strip()=='About the job' for h in headings):
        text=main.text.split('About the job',1)[1]
        for marker in ('Set alert for similar jobs','See how you compare to other applicants','About the company','More jobs'):
            text=text.split(marker,1)[0]
        if len(text.strip())>100:return text.strip()
    return False


def apply_one(driver, db, key, url, facts, settings, resume, execute, memory=None):
    audit=[]; submit_attempted=False
    driver.get(url)
    try:
        WebDriverWait(driver,20).until(lambda d: d.find_elements(By.CSS_SELECTOR,'main'))
        if restricted(driver): raise Blocked('LinkedIn restriction/security check.')
        main=driver.find_element(By.CSS_SELECTOR,'main')
        if re.search(r'\bApplied\b',main.text):
            record(db,key,url,'already_applied',{}); return 'already_applied'
        posting=WebDriverWait(driver,20).until(job_description)
        assessment_facts=dict(facts)
        if memory: assessment_facts['confirmed_answers']=memory.relevant(url)
        fit=assess(posting,assessment_facts,settings)
        if fit['decision']!='shortlist':
            record(db,key,url,'needs_review',{'assessment':fit}); return 'needs_review'
        candidates=[b for b in main.find_elements(By.CSS_SELECTOR,'button') if b.is_displayed() and ('easy apply' in ((b.get_attribute('aria-label') or '')+' '+b.text).lower())]
        if not candidates:
            record(db,key,url,'external_or_unavailable',{}); return 'external_or_unavailable'
        candidates[0].click()
        previous=None
        for step in range(15):
            dialog=WebDriverWait(driver,15).until(modal)
            if restricted(driver): raise Blocked('LinkedIn restriction/security check.')
            signature=dialog.text
            if previous==signature: raise Blocked('Application did not advance; check validation errors.')
            fill_step(dialog,facts,settings,resume,audit,memory,url)
            submit=buttons(dialog,{'submit application'})
            if submit:
                if not any(item.get('field')=='resume upload' for item in audit):
                    raise Blocked('The selected PDF was not uploaded and confirmed in this application.')
                if not execute:
                    record(db,key,url,'review_ready',{'answers':audit}); return 'review_ready'
                record(db,key,url,'uncertain',{'answers':audit,'stage':'before_submit'})
                submit_attempted=True
                submit[0].click()
                proof=WebDriverWait(driver,20).until(confirmation)
                record(db,key,url,'submitted',{'answers':audit,'confirmation':proof})
                done=buttons(driver,{'done'})
                if done: done[0].click()
                return 'submitted'
            advance=buttons(dialog,{'next','continue to next step','review','review your application'})
            if not advance: raise Blocked('No supported next/review/submit control.')
            previous=signature
            advance[0].click()
            WebDriverWait(driver,15).until(lambda d: modal(d) and modal(d).text!=previous)
        raise Blocked('Application exceeded 15 steps.')
    except Exception as error:
        state='uncertain' if submit_attempted else 'blocked'
        record(db,key,url,state,{'answers':audit,'error':str(error) or type(error).__name__})
        print(state+': '+(str(error) or type(error).__name__),flush=True)
        return state


def run(driver,db,profile,facts,settings,resume,limit=5,pages=1,execute=False,memory=None):
    init(db)
    results=[]
    for key,url in discover(driver,profile,pages,max(limit*5,25)).items():
        if db.execute('SELECT 1 FROM easy_apply_jobs WHERE id=?',(key,)).fetchone(): continue
        # Reserve before touching an application so a crash cannot cause a duplicate retry.
        record(db,key,url,'uncertain',{'stage':'opening_job'})
        state=apply_one(driver,db,key,url,facts,settings,resume,execute,memory)
        result={'id':key,'url':url,'state':state};results.append(result);print(json.dumps(result),flush=True)
        if state in ('uncertain','blocked','review_ready') or len(results)>=limit: break
    return results
