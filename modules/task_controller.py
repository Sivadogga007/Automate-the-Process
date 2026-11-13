"""Run tasks behind the local panel and deliver their questions to its buttons."""
import collections
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path


class TaskController:
    def __init__(self,root):
        self.root=Path(root)
        self.process=None
        self.prompt=None
        self.counts=collections.Counter()
        self.progress={}
        self.logs=collections.deque(maxlen=600)
        self.lock=threading.RLock()
        self.stopping=False
        self.auth_answers={}
        self.callback_url=None
        self.token=None

    def start(self,task,limit,preview):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError('A task is already running. Stop it before starting another.')
            self.logs.clear()
            self.counts.clear()
            self.progress={}
            self.prompt=None
            self.stopping=False
            env={**os.environ,'CAREERDESK_PANEL':'1','PYTHONUNBUFFERED':'1'}
            if self.callback_url:
                env.update(CAREERDESK_PANEL_URL=self.callback_url,CAREERDESK_PANEL_TOKEN=self.token)
            command=[sys.executable,str(self.root/'launch.py'),'--'+task,'--configured','--limit',str(limit)]
            if preview:command.append('--preview')
            options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
            process=subprocess.Popen(command,cwd=self.root,env=env,stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,**options)
            self.process=process
            threading.Thread(target=self._read,args=(process,),daemon=True).start()

    def _read(self,process):
        try:
            for line in process.stdout:
                with self.lock:
                    if process is not self.process:return
                    try:
                        event=json.loads(line)
                    except ValueError:
                        event={}
                    if isinstance(event,dict) and 'panel_prompt' in event:
                        self.prompt=event['panel_prompt']
                    else:
                        self.logs.append(line.rstrip())
                        if isinstance(event,dict):self.record_event(event)
            process.wait()
        finally:
            with self.lock:
                if process is self.process:self.prompt=None

    def record_event(self,event):
        # Only count individual events, never the outcomes repeated in a summary.
        state=event.get('state')
        if state=='batch_started':
            self.counts.clear()
            self.progress={}
        key={'header_decision':'headlines_checked','reading_profile':'profile_reads_started',
             'assessing_profile':'profile_reads_completed','sent':'sent','skip':'skipped',
             'skipped_by_user':'skipped','review':'review','already_pending':'pending',
             'unavailable':'unavailable','email_required':'unavailable','uncertain':'uncertain',
             'needs_review':'review'}.get(state)
        if key:self.counts[key]+=1
        if state and state not in ('batch_started','search_results'):
            self.progress={k:event[k] for k in ('name','state','step','read_level','sections_read','read_status') if k in event}

    def status(self):
        with self.lock:
            code=self.process.poll() if self.process else None
            return {'running':bool(self.process and code is None),'exit_code':code,
                    'stopping':self.stopping,'prompt':self.prompt,'logs':list(self.logs),
                    'counts':dict(self.counts),'progress':dict(self.progress)}

    def answer(self,identifier,value):
        with self.lock:
            if not self.prompt or self.prompt['id']!=identifier or not self.process or self.process.poll() is not None:
                raise RuntimeError('This question has changed. Wait for the current task status.')
            if not isinstance(value,str) or '\n' in value or '\r' in value:
                raise ValueError('Enter a single-line answer.')
            if self.prompt.get('auth'):
                self.auth_answers[identifier]=value
                self.prompt=None
                return
            self.process.stdin.write(value+'\n')
            self.process.stdin.flush()
            self.prompt=None

    def auth_prompt(self,text):
        import uuid
        with self.lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError('Task has stopped.')
            identifier=uuid.uuid4().hex
            self.prompt={'id':identifier,'text':text,'auth':True,
                         'secret':'yes/no' not in text.lower() and 'fingerprint' not in text.lower()}
            return identifier

    def auth_answer(self,identifier):
        with self.lock:
            if identifier in self.auth_answers:
                return {'ready':True,'value':self.auth_answers.pop(identifier)}
            if not self.process or self.process.poll() is not None:
                raise RuntimeError('Task has stopped.')
            return {'ready':False}

    def stop(self):
        with self.lock:
            process=self.process
            if not process or process.poll() is not None:return
            self.stopping=True
            self.auth_answers.clear()
            self.prompt=None
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
            else:
                try:os.killpg(process.pid,signal.SIGINT)
                except ProcessLookupError:pass
                threading.Thread(target=self._finish_stop,args=(process,),daemon=True).start()

    def _finish_stop(self,process):
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
