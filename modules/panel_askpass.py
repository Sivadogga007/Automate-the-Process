"""OpenSSH askpass bridge to the authenticated loopback panel."""
import json
import os
import sys
import time
from urllib.request import Request, urlopen

base=os.environ['CAREERDESK_PANEL_URL']
headers={'Content-Type':'application/json','X-App-Token':os.environ['CAREERDESK_PANEL_TOKEN']}
prompt=sys.argv[1] if len(sys.argv)>1 else 'SSH password or key passphrase'
req=Request(base+'/api/task/auth',data=json.dumps({'prompt':prompt}).encode(),headers=headers)
with urlopen(req,timeout=10) as response:
    identifier=json.load(response)['id']
while True:
    req=Request(base+'/api/task/auth/'+identifier,headers=headers)
    with urlopen(req,timeout=10) as response:
        result=json.load(response)
    if result.get('ready'):
        print(result['value'])
        break
    time.sleep(.25)
