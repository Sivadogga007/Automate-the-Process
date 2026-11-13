"""Expose existing task questions through the local control panel."""
import builtins
import json
import os
import sys
import uuid


def install():
    if not os.environ.get('CAREERDESK_PANEL') or getattr(builtins.input,'panel_input',False):
        return
    def ask(prompt=''):
        identifier=uuid.uuid4().hex
        print(json.dumps({'panel_prompt':{'id':identifier,'text':prompt}}),flush=True)
        value=sys.stdin.readline()
        if not value:
            raise EOFError('Task stopped from control panel')
        return value.rstrip('\r\n')
    ask.panel_input=True
    builtins.input=ask
