'use strict';
const $=id=>document.getElementById(id), languages=JSON.parse($('languages').textContent);
let draftFromResult=false;
let languageAvailability={};
let cloudVoices=[], audioPlayer=null, audioURL=null, speechRequest=null;
let locale='en', catalog={}, english={}, lastResult=null, history=[], busy=false, predictionBusy=false, recognition=null, voices=[], sampleResults=[], previewURL, localeGeneration=0;
const t=key=>catalog[key]||english[key]||key;
const label=key=>t('label.'+key);
const percent=value=>new Intl.NumberFormat(locale,{style:'percent',maximumFractionDigits:1}).format(value);
async function api(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let data;try{data=await response.json();}catch{throw new Error('requestError');}if(!response.ok)throw new Error(data.error||'requestError');return data;}
function showError(id,error){$(id).textContent=t(error.message in english?error.message:'requestError');}
function tab(name){stopSpeech();window.location.hash=name;for(const n of ['analysis','assistant']){$(n+'Panel').hidden=n!==name;$(n+'Tab').setAttribute('aria-selected',String(n===name));$(n+'Tab').tabIndex=n===name?0:-1;}if(name==='assistant')checkConnection();}
$('analysisTab').onclick=()=>tab('analysis');$('assistantTab').onclick=()=>tab('assistant');
for(const name of ['analysis','assistant'])$(name+'Tab').onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){const next=name==='analysis'?'assistant':'analysis';tab(next);$(next+'Tab').focus();}};
async function setLanguage(code){
  const generation=++localeGeneration; stopSpeech();
  try{
    const response=await fetch('/static/locales/'+encodeURIComponent(code)+'.json');if(!response.ok)throw new Error('translationError');const next=await response.json();
    if(generation!==localeGeneration)return;
    if(Object.keys(english).some(key=>!next[key]))throw new Error('translationError');
    locale=code;catalog=next;localStorage.setItem('farm-language',code);document.documentElement.lang=code;document.documentElement.dir=languages[code].rtl?'rtl':'ltr';
    document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));document.querySelectorAll('[data-placeholder]').forEach(e=>e.placeholder=t(e.dataset.placeholder));document.querySelectorAll('[data-title]').forEach(e=>{e.title=t(e.dataset.title);e.setAttribute('aria-label',t(e.dataset.title));});renderLanguages();
    $('image').setAttribute('aria-label',t('upload'));$('preview').alt=t('upload');$('translationNotice').textContent=code==='en'?'':t('translationNote');$('globalError').textContent='';
    for(const id of ['imageError','chatError','speechStatus'])$(id).textContent='';
    $('analyze').textContent=t(predictionBusy?'analyzing':'analyze');updateSend();
    $('supportedCrops').textContent=['Apple','Blueberry','Cherry','Corn','Grape','Orange','Peach','Pepper,_bell','Potato','Raspberry','Soybean','Squash','Strawberry','Tomato'].map(label).join(' · ');
    renderResult();if(draftFromResult&&lastResult)composeResult();renderMessages();populateVoices();renderMetrics();checkConnection();
  }catch{$('language').value=locale;$('globalError').textContent=t('translationError');}
}
$('language').onchange=e=>setLanguage(e.target.value);
$('image').onchange=()=>{lastResult=null;renderResult();$('imageError').textContent='';$('analyze').disabled=true;$('preview').hidden=true;$('uploadPrompt').hidden=false;$('filename').textContent='';if(previewURL)URL.revokeObjectURL(previewURL);const file=$('image').files[0];if(!file)return;if(file.size>10*1024*1024){$('imageError').textContent=t('imageError');return;}previewURL=URL.createObjectURL(file);$('preview').src=previewURL;$('preview').hidden=false;$('uploadPrompt').hidden=true;$('filename').textContent=file.name;$('analyze').disabled=false;};
$('imageForm').onsubmit=async e=>{e.preventDefault();if(predictionBusy)return;predictionBusy=true;$('analyze').disabled=true;$('image').disabled=true;$('analyze').textContent=t('analyzing');$('imageError').textContent='';lastResult=null;renderResult();try{const body=new FormData();body.append('image',$('image').files[0]);const response=await fetch('/predict',{method:'POST',body});const data=await response.json();if(!response.ok)throw new Error('imageError');lastResult=data;renderResult();}catch(error){showError('imageError',error);}finally{predictionBusy=false;$('image').disabled=false;$('analyze').disabled=false;$('analyze').textContent=t('analyze');}};
function renderResult(){$('result').hidden=!lastResult;$('empty').hidden=!!lastResult;if(!lastResult)return;const top=lastResult.predictions[0],parts=top.label.split('___');$('crop').textContent=t('crop')+' · '+label(parts[0]);$('disease').textContent=label(parts[1]);$('confidence').textContent=percent(top.confidence);$('confidenceBar').style.width=(top.confidence*100)+'%';$('uncertain').hidden=!lastResult.uncertain;$('alternatives').replaceChildren();for(const prediction of lastResult.predictions.slice(1)){const row=document.createElement('div');row.className='alternative';const text=document.createElement('span');text.textContent=prediction.label.split('___').map(label).join(' · ');const score=document.createElement('strong');score.textContent=percent(prediction.confidence);row.append(text,score);$('alternatives').append(row);}}
function composeResult(){if(lastResult){const p=lastResult.predictions[0];$('message').value=t('result')+': '+p.label.split('___').map(label).join(' · ')+' ('+t('modelScore')+': '+percent(p.confidence)+'). '+t('discuss')+'.';}}
$('discuss').onclick=()=>{tab('assistant');draftFromResult=true;composeResult();updateSend();resizeComposer();$('message').focus();};
$('message').addEventListener('input',()=>{draftFromResult=false;updateSend();resizeComposer();});
async function checkConnection(){try{const data=await(await fetch('/api/assistant/status')).json();$('connection').textContent=t(data.ready?'ready':'offline');$('connection').parentElement.classList.toggle('offline',!data.ready);$('modelName').textContent=data.model;document.querySelector('[data-i18n="localChat"]').textContent=t(data.provider==='Groq'?'cloudChat':'localChat');}catch{$('connection').textContent=t('offline');}}
function svgIcon(name){return '<svg class="icon" aria-hidden="true"><use href="#icon-'+name+'"></use></svg>';}
function updateSend(){
  $('send').disabled=busy||!!recognition||!$('message').value.trim();
  $('send').setAttribute('aria-label',t(busy?'sending':'send'));
  $('send').title=t(busy?'sending':'send');
}
function resizeComposer(){const field=$('message');field.style.height='auto';field.style.height=Math.min(field.scrollHeight,170)+'px';}
function renderMessages(){
  $('messages').replaceChildren();$('welcome').hidden=history.length>0;
  for(const message of history){
    const bubble=document.createElement('article');bubble.className='bubble '+message.role;
    const speaker=document.createElement('div');speaker.className='speaker';
    if(message.role==='assistant')speaker.innerHTML=svgIcon('leaf');
    speaker.append(document.createTextNode(t(message.role==='user'?'user':'bot')));
    const content=document.createElement('div');content.className='message-content';
    const text=message.translations?.[locale]||message.content;content.textContent=text;bubble.append(speaker,content);
    if(message.role==='assistant'){
      const button=document.createElement('button');button.className='secondary';button.innerHTML=svgIcon('speaker');
      button.append(document.createTextNode(t('listen')));button.onclick=()=>speak(text,message.language);bubble.append(button);
    }
    $('messages').append(bubble);
  }
  if(busy){const pending=document.createElement('div');pending.className='thinking';pending.setAttribute('role','status');pending.setAttribute('aria-label',t('sending'));pending.innerHTML='<i></i><i></i><i></i>';$('messages').append(pending);}
  $('messages').scrollTop=$('messages').scrollHeight;
}
$('chatForm').onsubmit=async e=>{e.preventDefault();const text=$('message').value.trim();if(!text||busy||recognition)return;stopSpeech();$('speechStatus').textContent='';busy=true;$('send').disabled=true;$('clearChat').disabled=true;updateSend();$('chatError').textContent='';const requestLanguage=locale;const candidate={role:'user',content:text,language:locale};history.push(candidate);renderMessages();$('message').value='';try{let context=history.slice(-12).map(({role,content})=>({role,content}));while(context.reduce((n,m)=>n+m.content.length,0)>18000)context.shift();const data=await api('/api/chat',{messages:context,language:requestLanguage});const answer={role:'assistant',content:data.answer,language:requestLanguage};history.push(answer);renderMessages();}catch(error){history=history.filter(m=>m!==candidate);$('message').value=text;renderMessages();showError('chatError',error);}finally{busy=false;$('send').disabled=false;$('clearChat').disabled=false;updateSend();renderMessages();resizeComposer();}};
$('clearChat').onclick=async()=>{if(busy)return;stopSpeech();try{const response=await fetch('/api/history',{method:'DELETE'});if(!response.ok)throw new Error('historyError');}catch(error){showError('chatError',error);return;}history=[];$('speechStatus').textContent='';draftFromResult=false;$('message').value='';renderMessages();updateSend();resizeComposer();$('chatError').textContent='';$('message').focus();};$('type').onclick=()=>{stopSpeech();$('message').focus();};
function populateVoices(){const previous=$('voices').value;const prefix=languages[locale].speech.split('-')[0];voices=[...cloudVoices,...('speechSynthesis'in window?speechSynthesis.getVoices():[])].filter(v=>v.lang.toLowerCase().split(/[-_]/)[0]===prefix).sort((a,b)=>Number(b.lang===languages[locale].speech)-Number(a.lang===languages[locale].speech));$('voices').replaceChildren();for(const voice of voices){const option=document.createElement('option');option.value=voice.voiceURI;option.textContent=voice.name.replace(/^[a-z]{2,3}-[A-Z]{2}-/,'').replace(/Neural$/,'')+' · '+voice.lang;$('voices').append(option);}if(voices.some(v=>v.voiceURI===previous))$('voices').value=previous;$('voices').disabled=!voices.length;voiceDetails();renderMessages();}
function voiceDetails(){const voice=voices.find(v=>v.voiceURI===$('voices').value);$('voiceDetails').textContent=voice?voice.name+' · '+voice.lang+' · '+t(voice.localService?'localVoice':'remoteVoice'):t('noVoice');}
$('voices').onchange=voiceDetails;if('speechSynthesis'in window)speechSynthesis.onvoiceschanged=populateVoices;
async function speak(text,code=locale){
  stopSpeech();const prefix=languages[code].speech.split('-')[0];
  const voice=code===locale?voices.find(v=>v.voiceURI===$('voices').value):[...cloudVoices,...('speechSynthesis'in window?speechSynthesis.getVoices():[])].find(v=>v.lang.split('-')[0]===prefix);
  if(!voice){$('speechStatus').textContent=t('noVoice');return;}
  $('activityLabel').textContent=t('speakingShort');$('stopVoice').hidden=false;
  if(voice.voiceURI.startsWith('edge:')){
    const controller=new AbortController();speechRequest=controller;
    try{const response=await fetch('/api/speech/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,voice:voice.name}),signal:controller.signal});if(!response.ok)throw new Error('voiceError');audioURL=URL.createObjectURL(await response.blob());audioPlayer=new Audio(audioURL);audioPlayer.onended=()=>stopSpeech();await audioPlayer.play();}
    catch(error){if(error.name!=='AbortError'){$('speechStatus').textContent=t('voiceError');$('stopVoice').hidden=true;}}
    return;
  }
  const utterance=new SpeechSynthesisUtterance(text);utterance.voice=voice;utterance.lang=voice.lang;utterance.onerror=()=>{$('speechStatus').textContent=t('voiceError');};speechSynthesis.speak(utterance);utterance.onend=()=>{$('stopVoice').hidden=true;};
}
function stopSpeech(){if(recognition)$('speechStatus').textContent=$('message').value.trim()?t('transcriptReady'):'';$('voice').setAttribute('aria-pressed','false');if(speechRequest){speechRequest.abort();speechRequest=null;}if(audioPlayer){audioPlayer.pause();audioPlayer=null;}if(audioURL){URL.revokeObjectURL(audioURL);audioURL=null;}if(recognition){const previous=recognition;recognition=null;previous.abort();$('message').readOnly=false;updateSend();}if('speechSynthesis'in window)speechSynthesis.cancel();$('stopVoice').hidden=true;$('voice').disabled=false;$('recordTest').disabled=false;}
// Final results are committed only on Stop. Interim text is a separate preview.
function record(target){
  stopSpeech();
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){$('speechStatus').textContent=t('noRecognition');return;}
  const rec=new SR(), prefix=target==='message'?$('message').value.trim():'';
  let finalized='', partial='', stopping=false, failed=false, restarts=0, active=false;
  recognition=rec;rec.lang=languages[locale].speech;
  rec.interimResults=true;rec.continuous=true;
  $('activityLabel').textContent=t('listeningShort');
  $('voice').setAttribute('aria-pressed','true');
  $('speechStatus').textContent=t('listening');
  $('voice').disabled=true;$('recordTest').disabled=true;$('stopVoice').hidden=false;
  $('message').readOnly=true;updateSend();
  const finish=()=>{
    if(recognition!==rec)return;
    // Browsers may emit a last final result after stop(), so finish in onend.
    const transcript=finalized.trim();
    if(transcript)$(target).value=[prefix,transcript].filter(Boolean).join(' ').slice(0,$(target).maxLength);
    recognition=null;$('message').readOnly=false;
    $('voice').setAttribute('aria-pressed','false');
    $('voice').disabled=false;$('recordTest').disabled=false;$('stopVoice').hidden=true;
    if(!failed)$('speechStatus').textContent=t(transcript?'transcriptReady':'noSpeech');
    draftFromResult=false;updateSend();resizeComposer();
  };
  rec.finish=()=>{stopping=true;try{rec.stop();}catch{finish();}if(!active){rec.abort();finish();}};
  rec.onstart=()=>{active=true;};
  rec.onresult=event=>{
    if(recognition!==rec)return;
    partial='';restarts=0;
    for(let i=event.resultIndex;i<event.results.length;i++){
      if(event.results[i].isFinal)finalized+=event.results[i][0].transcript+' ';
      else partial+=event.results[i][0].transcript+' ';
    }
    $('speechStatus').textContent=[t('listening'),finalized,partial].join(' ');
  };
  rec.onerror=event=>{
    if(recognition!==rec||event.error==='aborted')return;
    if(event.error==='no-speech')return;
    failed=true;stopping=true;
    $('speechStatus').textContent=t(event.error==='language-not-supported'?'recognitionLanguageError':'voiceError');
  };
  rec.onend=()=>{
    active=false;
    if(recognition!==rec)return;
    if(stopping){finish();return;}
    // Some browsers end even a continuous session after silence. Resume it.
    if(++restarts>5){failed=true;$('speechStatus').textContent=t('voiceError');finish();return;}
    setTimeout(()=>{if(recognition===rec&&!stopping){try{rec.start();}catch{failed=true;$('speechStatus').textContent=t('voiceError');finish();}}},250);
  };
  try{rec.start();}catch{failed=true;$('speechStatus').textContent=t('voiceError');finish();}
}
$('voice').onclick=()=>record('message');$('recordTest').onclick=()=>record('transcript');
$('stopVoice').onclick=()=>{if(recognition?.finish)recognition.finish();else stopSpeech();};
$('measure').onclick=async()=>{if(!$('reference').value.trim()||!$('transcript').value.trim()){$('metrics').textContent=t('noTest');return;}try{const result=await api('/api/speech/measure',{reference:$('reference').value,transcript:$('transcript').value});sampleResults.push({...result,language:locale,voice:$('voices').selectedOptions[0]?.textContent||null,recognition:'Browser SpeechRecognition; provider model is not exposed',reference:$('reference').value,transcript:$('transcript').value,time:new Date().toISOString()});renderMetrics();$('export').disabled=false;}catch(error){showError('metrics',error);}};
function renderMetrics(){const result=sampleResults.at(-1);$('metrics').textContent=result?t('wer')+': '+percent(result.wer)+' · '+t('cer')+': '+percent(result.cer):t('noSamples');}
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(sampleResults,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='farm-ai-speech-tests.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
const languageGroups=[['languagePriority',['en','hi','te','mr']],['languageSouth',['ta','kn','ml']],['languageRest',Object.keys(languages).filter(code=>!['en','hi','te','mr','ta','kn','ml'].includes(code)).sort((a,b)=>languages[a].english.localeCompare(languages[b].english))]];
function renderLanguages(){
  $('language').replaceChildren();
  for(const [group,codes] of languageGroups){
    const options=document.createElement('optgroup');options.label=t(group);
    for(const code of codes){const option=document.createElement('option');option.value=code;
      const ready=languageAvailability[code]?.interface_ready??['en','hi','te'].includes(code);
      option.disabled=!ready;option.textContent=languages[code].english+(code==='en'?'':' / '+languages[code].name)+(ready?'':' — '+t('languagePending'));options.append(option);}
    $('language').append(options);
  }
  $('language').value=locale;
}
async function refreshCapabilities(){
  try{const data=await(await fetch('/api/speech/voices')).json();cloudVoices=data.voices||[];populateVoices();}catch{}
  try{languageAvailability=await(await fetch('/api/languages')).json();renderLanguages();}catch{}
}
$('voiceSettingsButton').onclick=()=>{$('voiceDialog').showModal();};
$('closeVoiceDialog').onclick=()=>{$('voiceDialog').close();$('voiceSettingsButton').focus();};
$('voiceDialog').addEventListener('click',event=>{if(event.target===$('voiceDialog')){const box=$('voiceDialog').getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)$('voiceDialog').close();}});
new MutationObserver(()=>{$('voiceActivity').hidden=$('stopVoice').hidden;if($('stopVoice').hidden)$('voice').setAttribute('aria-pressed','false');}).observe($('stopVoice'),{attributes:true,attributeFilter:['hidden']});
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{draftFromResult=false;$('message').value=t(button.dataset.prompt);updateSend();resizeComposer();$('message').focus();});
(async()=>{
  tab(window.location.hash==='#analysis'?'analysis':'assistant');
  english=await(await fetch('/static/locales/en.json')).json();catalog=english;renderLanguages();
  const saved=localStorage.getItem('farm-language')||'en';await setLanguage(saved in languages?saved:'en');
  try{const response=await fetch('/api/history');if(!response.ok)throw new Error();const data=await response.json();history=data.messages;renderMessages();}catch{$('chatError').textContent=t('historyError');}
  updateSend();await refreshCapabilities();
})();
setInterval(refreshCapabilities,60000);

$('message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!busy)$('chatForm').requestSubmit();}});

$('voiceDialog').addEventListener('close',()=>{if(recognition)stopSpeech();});
