"""Read-only actual runtime gate after the SINGLE cached blocker sanity."""
import json
import re
import subprocess
import httpx
from evaluation.common import EvaluationDataError
from evaluation.token_admission_diagnostics import runtime_token_count


def validate_admission(flags,counts,profile):
    if flags.get('-c')!=profile['num_ctx'] or flags.get('-b',0)<profile['num_batch'] or flags.get('-ub',0)<profile['num_batch']:
        raise EvaluationDataError('PHYSICAL_BATCH_PROFILE_NOT_APPLIED')
    maximum=max((r['count'] for r in counts),default=0)
    if maximum>profile['num_batch'] or maximum>profile['num_ctx']:
        raise EvaluationDataError('FROZEN_INPUT_EXCEEDS_AUTHORIZED_TOKEN_CAP')
    return {'maximum_total_tokens':maximum,'count_gt2048':sum(r['count']>2048 for r in counts),
            'count_gt4096':sum(r['count']>4096 for r in counts),'count_gt8192':sum(r['count']>8192 for r in counts)}


def actual_admission_gate(base_url,model,entities,profile):
    command="""$r=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'llama-server.exe'} | ForEach-Object {$f=@{};foreach($m in [regex]::Matches($_.CommandLine,'(?:^|\\s)(--?[A-Za-z][A-Za-z0-9_-]*)[ =]+(\\d+)(?=\\s|$)')){$f[$m.Groups[1].Value]=[int]$m.Groups[2].Value};$f});ConvertTo-Json -InputObject $r -Compress"""
    runners=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True))
    with httpx.Client(base_url=base_url,timeout=20) as client:
        response=client.post('/api/show',json={'model':model});response.raise_for_status();show=response.json()
    if show.get('model_info',{}).get('bert.context_length')!=8192:raise EvaluationDataError('EXPECTED_BGE_CAPACITY_CHANGED')
    match=re.search(r'^FROM\s+(.+)$',show['modelfile'],re.M)
    if not match:raise EvaluationDataError('MODEL_PATH_MISSING')
    selected=[]
    for flags in runners:
        port=flags.get('--port')
        if not port:continue
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20) as client:
            response=client.get('/props');response.raise_for_status()
            if response.json().get('model_path')==match[1].strip():selected.append((port,flags))
    if len(selected)!=1:raise EvaluationDataError('BGE_RUNNER_NOT_UNIQUELY_VERIFIED')
    port,flags=selected[0];counts=[]
    # Verify physical settings BEFORE tokenizing all inputs or any batch resume.
    validate_admission(flags,[],profile)
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=30) as client:
        for kind,key,canonical,_ in entities:
            value=runtime_token_count(client,canonical.semantic_text,add_special=True)
            counts.append({'kind':kind,'entity_id':key,**value})
    summary=validate_admission(flags,counts,profile)
    return {'verified_runner_flags':flags,'count_method':'same loaded BGE /tokenize add_special=true',
            'inputs_counted':len(counts),'per_input':counts,**summary}
