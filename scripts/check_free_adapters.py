"""Contract checks only: MongoDB double and mocked Groq HTTP, no cloud claims."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, Mock
import mongomock
import requests

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from chat_store import MongoChatStore
import assistant_service as assistant

with patch('pymongo.MongoClient',mongomock.MongoClient):
    store=MongoChatStore('mongodb://localhost')
    store.append_turn('a','नमस्ते','नमस्ते किसान','hi')
    assert len(store.history('a'))==2 and store.history('b')==[]
    for i in range(60): store.append_turn('a',str(i),'reply','en')
    assert len(store.history('a'))==100
    assert store.history('a')[0]['content']=='10'
    assert store.collection.index_information()['expires_at_1']['expireAfterSeconds']==0
    store.clear('a');assert store.history('a')==[]

response=Mock()
response.json.return_value={'choices':[{'message':{'content':'नमस्ते किसान'}}]}
with patch.object(assistant,'PROVIDER','groq'),patch.object(assistant,'MODEL','qwen/qwen3.8-27b'),patch.dict('os.environ',{'GROQ_API_KEY':'test-placeholder'}),patch.object(assistant.requests,'post',return_value=response) as post:
    assert assistant.complete([{'role':'user','content':'नमस्ते'}],'hi')=='नमस्ते किसान'
    args=post.call_args
    assert args.args[0]=='https://api.groq.com/openai/v1/chat/completions'
    assert args.kwargs['json']['reasoning_effort']=='none'
    assert 'Hindi' in args.kwargs['json']['messages'][0]['content']
    response.raise_for_status.side_effect=requests.HTTPError('rate limit')
    try: assistant.complete([{'role':'user','content':'hello'}],'en')
    except requests.HTTPError: pass
    else: raise AssertionError('Provider failure was hidden')
report={'mongodb_contract':'passed: isolation, atomic turn payload, 100-message cap, TTL index, deletion (mongomock)',
        'groq_contract':'passed: endpoint, native-language prompt, non-thinking mode, provider errors (mock HTTP)',
        'live_atlas':'not tested; credentials required','live_groq':'not tested; credentials required'}
(root/'artifacts/free-adapter-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
