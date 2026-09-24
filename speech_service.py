"""Optional online speech output; no API key. Browser voices remain available."""
import asyncio
import json
from pathlib import Path
import edge_tts

CACHE = Path(__file__).resolve().parent / 'artifacts/edge-voices.json'

async def available_voices():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding='utf-8'))
    return await asyncio.wait_for(edge_tts.list_voices(),timeout=20)

async def synthesize(text, voice):
    known = await available_voices()
    if voice not in {v['ShortName'] for v in known}: raise ValueError('Unknown voice')
    audio = bytearray()
    async def collect():
        async for chunk in edge_tts.Communicate(text,voice=voice).stream():
            if chunk['type']=='audio': audio.extend(chunk['data'])
    await asyncio.wait_for(collect(),timeout=45)
    if not audio: raise ValueError('No speech audio received')
    return bytes(audio)
