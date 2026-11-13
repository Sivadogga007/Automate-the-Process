"""Loopback-only task control panel. No public hosting, no stored passwords."""
import json
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

ROOT=Path(__file__).resolve().parent


def create_app(root=ROOT):
    from modules.task_controller import TaskController
    controller=TaskController(root)
    app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=16*1024*1024
    token=secrets.token_urlsafe(32)
    root=Path(root)
    def read(name):
        path=root/name
        return json.loads(path.read_text()) if path.exists() else {}
    def write(name,value):
        path=root/name;path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)
    @app.before_request
    def guard():
        if request.host.split(':')[0] not in ('127.0.0.1','localhost'): return ('Local access only',403)
        if request.path.startswith('/api/') and request.headers.get('X-App-Token')!=token: return ('Invalid local session',403)
    @app.get('/')
    def index():
        return (root/'panel.html').read_text().replace('__APP_TOKEN__',token)
    @app.get('/api/config')
    def config():
        return jsonify(profile=read('profile.json'),ssh=read('passpoli.json'))
    @app.post('/api/config')
    def save():
        data=request.get_json();profile=read('profile.json')
        if 'connection_limit' in data:
            if type(data['connection_limit']) is not int or not 1<=data['connection_limit']<=100:
                return jsonify(error='Choose a connection target from 1 to 100.'),400
            profile['connection_limit']=data['connection_limit']
        for key in ('target_roles','locations'):
            value=data.get(key)
            if not isinstance(value,list) or not value or any(not isinstance(v,str) or not v.strip() for v in value):
                return jsonify(error='Enter at least one '+key.replace('_',' ')),400
            profile[key]=[v.strip() for v in value]
        for key in ('name','linkedin_url','education','experience','availability','work_authorization','email','phone','current_city','resume_path'):
            if key in data and isinstance(data[key],str) and data[key].strip(): profile[key]=data[key].strip()
        from datetime import date
        for key in ('education','experience','work_authorization'):
            if key not in data or isinstance(data[key],str): continue
            value=data[key]
            if key=='education':
                if not isinstance(value,list) or any(not isinstance(row,dict) for row in value):
                    return jsonify(error='Education must contain separate qualification entries.'),400
                for row in value:
                    month=row.get('graduation_month','')
                    if month:
                        try:
                            date.fromisoformat(month+'-01')
                        except (ValueError,TypeError):return jsonify(error='Graduation month must use YYYY-MM.'),400
                    if row.get('status','') not in ('','unknown','studying','completed','not applicable'):
                        return jsonify(error='Choose a valid study status.'),400
            elif not isinstance(value,dict):return jsonify(error='Use the separate '+key.replace('_',' ')+' fields.'),400
            if key=='experience' and value.get('years') not in (None,'','unknown'):
                try:
                    years=float(value['years'])
                    if not 0<=years<=80:raise ValueError()
                except (TypeError,ValueError):return jsonify(error='Experience years must be a number from 0 to 80.'),400
            if key=='work_authorization':
                if value.get('needs_sponsorship','') not in ('','yes','no','unknown'):
                    return jsonify(error='Choose yes, no, or unknown for sponsorship.'),400
                if not isinstance(value.get('authorized_countries',[]),list):return jsonify(error='Enter authorized countries one per line.'),400
            if key in profile and profile[key]!=value:
                profile.setdefault('profile_edit_history',[]).append({'field':key,'previous_value':profile[key]})
            profile[key]=value
        if profile.get('linkedin_url'):
            from setup import linkedin_url
            if not linkedin_url(profile['linkedin_url']): return jsonify(error='Use your own https://www.linkedin.com/in/... profile URL.'),400
        from modules.networking_targets import CATEGORIES, DEFAULT_CATEGORIES, effective_categories
        categories=data.get('contact_categories',profile.get('contact_categories',DEFAULT_CATEGORIES))
        if isinstance(categories,list): categories=effective_categories(categories)
        custom=data.get('custom_contact_types',profile.get('custom_contact_types',[]))
        if not isinstance(custom,list) or any(not isinstance(v,str) or not v.strip() for v in custom):
            return jsonify(error='Enter one custom contact type per line.'),400
        unique={}
        for label in custom:
            label=' '.join(label.split())
            unique.setdefault(label.casefold(),label)
        profile['custom_contact_types']=list(unique.values())
        if not isinstance(categories,list) or not (categories or custom) or any(not isinstance(k,str) or k not in CATEGORIES for k in categories):
            return jsonify(error='Select a contact category or enter a custom contact type.'),400
        profile['contact_categories']=list(dict.fromkeys(categories))
        profile.setdefault('provider','openjev');profile.setdefault('endpoint','http://127.0.0.1:11436');profile.setdefault('model','openjev')
        profile['personal_info_completed']=all(profile.get(k) for k in ('name','linkedin_url','education','experience','availability','work_authorization'))
        from modules.networking_targets import build_queries
        profile['queries']=build_queries(profile)
        username=data.get('passpoli_username','').strip()
        if username:
            from launch import ssh_command
            try: ssh_command(username,'10.119.2.11',11436)
            except ValueError as error: return jsonify(error=str(error)),400
            write('passpoli.json',{'username':username,'host':'10.119.2.11'})
        write('profile.json',profile)
        return jsonify(saved=True)
    @app.get('/api/login')
    def login_status():
        from modules.login_session import credential_metadata, retrieve_credentials
        data=credential_metadata(root)
        saved=bool(data.get('saved'))
        username=data.get('username','')
        if not saved:
            creds=retrieve_credentials(root)
            if creds:
                saved=True
                username=creds.get('username',username)
        return jsonify(saved=saved,username=username)
    @app.post('/api/login')
    def login_save():
        from modules.login_session import store_credentials,remove_credentials
        data=request.get_json()
        try:
            if data.get('remove') is True:remove_credentials(root)
            else:store_credentials(root,data.get('username',''),data.get('password',''))
        except Exception:
            return jsonify(error='Could not access the system keychain. Restart the launcher, approve keychain access if prompted, or use manual sign-in. No plaintext password file is created.'),400
        return jsonify(saved=data.get('remove') is not True)
    @app.post('/api/resume')
    def resume():
        file=request.files.get('resume')
        if not file or not file.filename.lower().endswith('.pdf'): return jsonify(error='Select a PDF résumé.'),400
        raw=file.read()
        if not raw.startswith(b'%PDF-'):return jsonify(error='This file is not a PDF.'),400
        folder=root/'private/resumes';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(secrets.token_hex(4)+'-'+secure_filename(file.filename))
        path.write_bytes(raw);path.chmod(0o600)
        return jsonify(path=str(path))
    @app.post('/api/start')
    def start():
        data=request.get_json();task=data.get('task');limit=data.get('limit')
        if task not in ('network','jobs','career') or type(limit)is not int or not 1<=limit<=100:
            return jsonify(error='Choose a task and a whole-number limit from 1 to 100.'),400
        profile=read('profile.json')
        if not profile.get('target_roles') or not profile.get('locations'):return jsonify(error='Save roles and locations first.'),400
        if task=='jobs':
            keys=('name','linkedin_url','education','experience','availability','work_authorization','email','phone','current_city','resume_path')
            missing=[k for k in keys if not profile.get(k)]
            if missing:return jsonify(error='Easy Apply needs: '+', '.join(missing)),400
            resume=Path(profile['resume_path']).expanduser()
            if not resume.is_file() or resume.suffix.lower()!='.pdf':return jsonify(error='Choose an existing PDF résumé.'),400
        try:
            from launch import check_existing_runner
            check_existing_runner()
            controller.callback_url=request.host_url.rstrip('/')
            controller.token=token
            controller.start(task,limit,data.get('preview') is True)
        except (OSError,RuntimeError,subprocess.SubprocessError) as error:return jsonify(error=str(error)),409
        return jsonify(started=True,message='Task started. Follow progress and answer any questions below. Complete LinkedIn sign-in in Chrome if prompted.')
    @app.post('/api/task/auth')
    def task_auth():
        prompt=(request.get_json() or {}).get('prompt')
        if not isinstance(prompt,str):return jsonify(error='Missing authentication prompt'),400
        try:return jsonify(id=controller.auth_prompt(prompt))
        except RuntimeError as error:return jsonify(error=str(error)),409

    @app.get('/api/task/auth/<identifier>')
    def task_auth_answer(identifier):
        try:return jsonify(controller.auth_answer(identifier))
        except RuntimeError as error:return jsonify(error=str(error)),409

    @app.get('/api/task')
    def task_status():
        return jsonify(controller.status())

    @app.post('/api/task/answer')
    def task_answer():
        data=request.get_json() or {}
        try:controller.answer(data.get('id'),data.get('value'))
        except (ValueError,RuntimeError,OSError) as error:return jsonify(error=str(error)),409
        return jsonify(answered=True)

    @app.post('/api/task/stop')
    def task_stop():
        controller.stop()
        return jsonify(stopping=True)

    @app.get('/api/current-profile')
    def current_profile():
        from modules.connection_control import current
        path=root/'private/career.sqlite3'
        return jsonify(profile=current(path) if path.exists() else None)

    @app.post('/api/skip-profile')
    def skip_profile():
        from modules.connection_control import request_skip
        path=root/'private/career.sqlite3'
        attempt=(request.get_json() or {}).get('attempt')
        if not isinstance(attempt,str) or not path.exists() or not request_skip(path,attempt):
            return jsonify(error='This profile has changed or sending has begun. Refresh the current profile.'),409
        return jsonify(message='Skip requested. The reader will move on at its next check. A model request already in progress may finish first.')

    @app.get('/api/status')
    def status():
        output={'applications':[],'connections':[]}
        path=root/'private/career.sqlite3'
        if path.exists():
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
                for name,table in [('applications','easy_apply_jobs'),('connections','outreach')]:
                    if db.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone():
                        output[name]=[{'state':state,'count':count} for state,count in db.execute('SELECT state,COUNT(*) FROM '+table+' GROUP BY state')]
        return jsonify(output)
    app.extensions['task_controller']=controller
    return app


def main():
    app=create_app()
    server=make_server('127.0.0.1',0,app)
    url='http://127.0.0.1:'+str(server.server_port)
    print('Local control panel: '+url+'\nKeep this launcher open. Control tasks and authentication from the browser panel.',flush=True)
    threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        app.extensions['task_controller'].stop()
        server.server_close()

if __name__=='__main__':main()
