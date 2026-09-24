"""Free local model connection and reproducible speech error metrics."""
import os
import re
import unicodedata
import requests
from languages import LANGUAGE_MAP

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
PROVIDER = os.environ.get('ASSISTANT_PROVIDER','ollama')
if PROVIDER not in {'ollama','groq'}:
    raise RuntimeError('ASSISTANT_PROVIDER must be ollama or groq')
MODEL = os.environ.get('ASSISTANT_MODEL', 'qwen/qwen3.8-27b' if PROVIDER=='groq' else 'qwen3.5:4b')

def status():
    if PROVIDER == 'groq':
        ready=False
        if os.environ.get('GROQ_API_KEY'):
            try:
                response=requests.get('https://api.groq.com/openai/v1/models',
                    headers={'Authorization':'Bearer '+os.environ['GROQ_API_KEY']},timeout=(3,5))
                response.raise_for_status()
                ready=MODEL in {item['id'] for item in response.json().get('data',[])}
            except (requests.RequestException,ValueError,KeyError):
                pass
        return {'ready':ready, 'model':MODEL,'provider':'Groq',
                'verification':'Model availability checked; chat requests also require remaining quota.'}
    try:
        response = requests.get(OLLAMA_URL + '/api/tags', timeout=3)
        response.raise_for_status()
        available = [m['name'] for m in response.json().get('models', [])]
        return {'ready': MODEL in available, 'model': MODEL, 'provider': 'Ollama',
                'available_models': available, 'api_fee': 0}
    except (requests.RequestException, ValueError, KeyError):
        return {'ready': False, 'model': MODEL, 'provider': 'Ollama', 'api_fee': 0}

def complete(messages, language, translate=False):
    name = LANGUAGE_MAP[language]['english']
    instruction = (
        f'Translate the supplied text into {name}. Preserve meaning. Output only the translation.'
        if translate else
        f'You are a farming assistant. Answer in {name} using its native script. '
        f'The required reply language is {name}, even when earlier messages are in another language. '
        'Do not translate the question into English or provide an English version. '
        'Use simple words a farmer understands. Keep replies below 120 words. '
        'Be concise and practical. Ask for crop, location and symptoms when needed. '
        'Treat leaf-model predictions as unconfirmed; never claim an image proves a disease. '
        'Do not invent weather, prices, pesticide doses, test results or sources. '
        'If unsure, say so and suggest consulting a local agricultural extension worker. '
        'Do not reveal reasoning; provide only your useful final answer.'
    )
    if PROVIDER == 'groq':
        payload={'model':MODEL,'messages':[{'role':'system','content':instruction},*messages],
                 'temperature':0.2,'max_completion_tokens':700,'stream':False}
        if MODEL.startswith('qwen/'):
            payload.update(reasoning_effort='none',reasoning_format='hidden')
        response = requests.post('https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization':'Bearer '+os.environ.get('GROQ_API_KEY','')},
            json=payload,timeout=(5,60))
        response.raise_for_status()
        answer=response.json()['choices'][0]['message']['content'].strip()
        if not answer: raise ValueError('No final answer returned')
        return answer
    response = requests.post(OLLAMA_URL + '/api/chat', json={
        'model': MODEL, 'messages': [{'role': 'system', 'content': instruction}, *messages],
        'stream': False, 'think': False,
        'options': {'temperature': 0.2, 'num_ctx': 4096, 'num_predict': 500},
    }, timeout=(5, 240))
    response.raise_for_status()
    answer = response.json().get('message', {}).get('content', '')
    answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.S).strip()
    if not answer or '<think>' in answer: raise ValueError('No final answer returned')
    return answer

def normalize(text):
    text = unicodedata.normalize('NFC', text).casefold()
    return ' '.join(''.join(' ' if unicodedata.category(c).startswith('P') else c for c in text).split())

def distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, item in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (item != other)))
        previous = current
    return previous[-1]

def speech_metrics(reference, transcript):
    ref, hyp = normalize(reference), normalize(transcript)
    if not ref: raise ValueError('Empty reference')
    words = ref.split()
    chars = ref.replace(' ', '')
    return {'wer': distance(words, hyp.split()) / len(words),
            'cer': distance(chars, hyp.replace(' ', '')) / len(chars),
            'reference_words': len(words), 'reference_characters': len(chars),
            'normalization': 'NFC, casefold, punctuation removed, whitespace collapsed',
            'scope': 'One user-recorded sample; not an overall accuracy estimate'}
