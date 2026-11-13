"""Strict choice selection through the local OpenJev endpoint."""
import json
from urllib.request import Request, urlopen

def decide(endpoint,state,question,options):
    if not 2 <= len(options) <= 26:
        raise ValueError('Use between 2 and 26 options')
    labels=list(options)
    choices='\n'.join(f'[{chr(65+i)}] {label}: {options[label]}' for i,label in enumerate(labels))
    prompt=f'State:\n{state}\n\nQuestion: {question}\nOptions:\n{choices}\n\nAnswer with the letter of the best option only.'
    data={'model':'openjev','messages':[{'role':'user','content':prompt}],'max_tokens':4,'temperature':0,
          'chat_template_kwargs':{'enable_thinking':False}}
    with urlopen(Request(endpoint.rstrip('/')+'/v1/chat/completions',data=json.dumps(data).encode(),
                         headers={'Content-Type':'application/json'}),timeout=120) as r:
        reply=json.load(r)
    letter=reply['choices'][0]['message']['content'].strip()
    if len(letter)!=1 or not 'A' <= letter <= chr(64+len(labels)):
        raise ValueError('Unexpected decision output: '+repr(letter))
    return labels[ord(letter)-65]

