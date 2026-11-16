"""Benchmark v2: subprocess isolated, resumable, streaming, local-only git harness."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASES = ('plan', 'implement', 'review')
REQUIRED = ('summary','changed_files','decisions','tests','risks','next_steps','verdict','gaps')

def read(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))

def write(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, p)

def specs():
    return {p.parent.name: read(p) for p in sorted((ROOT/'tasks').glob('TASK-*/task.json'))}

def paths(agent):
    b = ROOT/'runs'/agent
    return b, b/'workspace', b/'state.json'

def initial_state():
    return {'version':2,'tasks':{k:{'status':'PENDING','phase':'plan','cycle':1,'recovery':0,'history':[]} for k in specs()},'events':[],'spent_seconds':0,'reported_cost_usd':0,'reported_tokens':0,'cost_complete':True,'tokens_complete':True}

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def protected_manifest():
    result = {}
    for folder in ('tasks','skills'):
        for p in (ROOT/folder).glob('**/*'):
            if p.is_file() and (folder == 'skills' or p.name in ('task.md','task.json')):
                result[f'{folder}/{p.relative_to(ROOT/folder)}'] = sha(p)
    for name in ('AGENTS.md','CLAUDE.md'):
        result[name] = sha(ROOT/'starter'/name)
    return result

def protected_ok(w):
    for name, digest in protected_manifest().items():
        dest = w / ('.agents/skills/'+name[7:] if name.startswith('skills/') else name)
        if not dest.is_file() or sha(dest) != digest:
            return False, str(dest)
    # Unexpected task specifications are forbidden; generated handoffs are allowed.
    for p in (w/'tasks').glob('TASK-*/*'):
        if p.is_file() and p.name in ('task.md','task.json') and f'tasks/{p.parent.name}/{p.name}' not in protected_manifest():
            return False, str(p)
    return True,''

def git(w,*args,timeout=60):
    p = subprocess.run(['git',*args],cwd=w,text=True,capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(f'git {args}: {p.stderr[-1000:]} {p.stdout[-500:]}')
    return p.stdout.strip()

def ensure_local_git(w):
    remotes = git(w,'remote')
    if remotes: raise RuntimeError(f'Remotes forbidden in workspace: {remotes}')

def init(agent):
    b,w,s = paths(agent)
    if s.exists(): return w
    if b.exists(): raise RuntimeError(f'Incomplete run directory: {b} (do not overwrite)')
    b.mkdir(parents=True)
    shutil.copytree(ROOT/'starter',w)
    shutil.copytree(ROOT/'tasks',w/'tasks')
    shutil.copytree(ROOT/'skills',w/'.agents'/'skills')
    git(w,'init','-q')
    git(w,'config','user.name','Evolution Benchmark')
    git(w,'config','user.email','benchmark@localhost')
    git(w,'add','-A')
    git(w,'commit','-qm','benchmark baseline')
    write(s,initial_state())
    return w

def ready(state):
    sp = specs()
    return [k for k,t in state['tasks'].items() if t['status'] in ('PENDING','ACTIVE') and all(state['tasks'][d]['status']=='DONE' for d in sp[k]['dependencies'])]

def adapter(agent, model=None, unsafe=False, workspace=None):
    c=read(ROOT/'benchmark.json')['agents'][agent]
    base=[c['executable']]
    if agent == 'claude':
        base+=['-p','--output-format','stream-json','--verbose','--max-turns','80']
        if unsafe: base.append('--dangerously-skip-permissions')
        if model: base+=['--model',model]
    elif agent == 'codex':
        base+=['exec','--json','--ephemeral']
        base += ['--dangerously-bypass-approvals-and-sandbox'] if unsafe else ['--sandbox','workspace-write']
        if model: base+=['--model',model]
    elif agent == 'opencode':
        base+=['run','--standalone','--format','json']
        if workspace is not None: base+=['--dir',str(pathlib.Path(workspace).resolve())]
        if unsafe: base.append('--auto')
        if model: base+=['--model',model]
    return base + c.get('extra_args',[])

def usage(agent, out):
    tok=cost=None
    for line in out.splitlines():
        try:o=json.loads(line)
        except (ValueError,TypeError):continue
        if not isinstance(o,dict):continue
        if agent=='claude' and o.get('type')=='result':
            c=o.get('total_cost_usd')
            if isinstance(c,(int,float)): cost=float(c)
            u=o.get('usage') or {}
            if isinstance(u,dict):
                v=sum(u.get(k,0) or 0 for k in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'))
                if v:tok=int(v)
        elif agent=='codex' and o.get('type')=='turn.completed':
            u=o.get('usage') or {}
            if isinstance(u,dict):
                v=(u.get('input_tokens') or 0)+(u.get('output_tokens') or 0)
                if v:tok=int(v)
        elif agent=='opencode':
            part=o.get('part') or {}
            if isinstance(part,dict):
                c=part.get('cost')
                if isinstance(c,(int,float)):cost=(cost or 0)+c
                t=part.get('tokens') or {}
                if isinstance(t,dict):
                    v=(t.get('input') or 0)+(t.get('output') or 0)+(t.get('reasoning') or 0)
                    if v:tok=(tok or 0)+v
    return {'tokens':tok,'cost_usd':cost}

def short_event(agent, line):
    try:o=json.loads(line)
    except ValueError:return None
    if not isinstance(o,dict):return None
    if agent=='claude':
        typ=o.get('type')
        if typ=='assistant':
            blocks=(o.get('message') or {}).get('content') or []
            for x in blocks:
                if x.get('type')=='tool_use':return 'tool: '+str(x.get('name'))[:70]
            return 'assistant update' if blocks else None
        if typ=='result':return 'phase response received'
        if typ=='stream_event':
            e=o.get('event') or {}
            if e.get('type')=='content_block_start':
                b=e.get('content_block') or {}
                if b.get('type')=='tool_use':return 'tool: '+str(b.get('name'))[:70]
        return None
    if agent=='codex':
        t=o.get('type','');item=o.get('item') or {};kind=item.get('type','')
        if t=='item.started' and kind=='command_execution':return 'command started: '+str(item.get('command',''))[:100]
        if t=='item.completed' and kind in ('file_change','plan_update','agent_message'):return kind.replace('_',' ')+' completed'
        if t=='turn.completed':return 'turn completed'
        if t in ('turn.failed','error'):return 'agent error'
        return None
    part=o.get('part') or {};t=o.get('type','')
    if t=='tool' or (isinstance(part,dict) and part.get('type')=='tool'):
        name=o.get('tool') or part.get('tool') or (part.get('state') or {}).get('title') or 'tool'
        return 'tool: '+str(name)[:80]
    if t in ('step_start','step_finish'):return t.replace('_',' ')
    if t=='error':return 'agent error'
    return None

def cmd(argv,cwd,timeout=30,stdin=None,logfile=None,agent=None,live=False):
    start=time.monotonic();out=[];timed_out=False
    if logfile:
        logfile=pathlib.Path(logfile);logfile.parent.mkdir(parents=True,exist_ok=True)
    proc=subprocess.Popen(argv,cwd=str(cwd),stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
    if stdin is not None:
        proc.stdin.write(stdin);proc.stdin.close()
    # Reader thread avoids blocking on incomplete output while enforcing timeout.
    import threading, queue
    q=queue.Queue()
    def reader():
        for line in proc.stdout:q.put(line)
        q.put(None)
    reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start()
    last_event=None
    with open(logfile,'w',encoding='utf-8') if logfile else open(os.devnull,'w') as log:
        while True:
            if time.monotonic()-start>timeout:
                timed_out=True
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                break
            try:line=q.get(timeout=.15)
            except queue.Empty:
                if proc.poll() is not None and not reader_thread.is_alive():
                    break
                continue
            if line is None:break
            out.append(line);log.write(line);log.flush()
            if live and agent:
                msg=short_event(agent,line)
                if msg and msg!=last_event:
                    print('  • '+msg,flush=True);last_event=msg
        proc.wait()
        proc.stdout.close()
    return {'exit_code':124 if timed_out else proc.returncode,'seconds':round(time.monotonic()-start,2),'output':''.join(out),'timeout':timed_out}

def handoff_valid(path,task,phase,cycle):
    if not pathlib.Path(path).is_file():return False,f'missing handoff: {path}'
    try:
        d=read(path)
        if (d.get('task_id'),d.get('phase'),d.get('cycle'))!=(task,phase,cycle):return False,'wrong identity/cycle'
        for k in REQUIRED:
            if k not in d:return False,'missing '+k
        if not isinstance(d['summary'],str) or not d['summary'].strip():return False,'empty summary'
        for k in ('changed_files','decisions','tests','risks','next_steps','gaps'):
            if not isinstance(d[k],list):return False,'invalid list '+k
        if d['verdict'] not in (('PASS','FAIL') if phase=='review' else ('N/A',)):return False,'invalid verdict'
        if phase=='review' and d['verdict']=='FAIL' and not d['gaps']:return False,'FAIL requires gaps'
        return True,''
    except (OSError,ValueError,TypeError) as e:return False,str(e)

def external_checks(w,task,phase,timeout):
    return cmd([sys.executable,str(ROOT/'acceptance'/'checks.py'),str(w),task,phase],ROOT,timeout)

def prompt_for(task,phase,cycle,w=None):
    if w is None: w=pathlib.Path.cwd()
    w=pathlib.Path(w).resolve()
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    return (f'WORKSPACE ROOT (absolute): {w}\n'
            f'IMPORTANT: This is the ONLY code project root; do NOT access benchmark root docs/tasks. '
            f'First verify files {w}/AGENTS.md and {w}/docs/STATE.md exist. '
            f'Use absolute paths when unsure. Fresh context; no prior conversation. '
            f'Task {task}, phase {phase.upper()}, cycle {cycle}. '
            f'Read AGENTS.md, docs/PROJECT.md, docs/STATE.md, docs/ARCHITECTURE.md, '
            f'tasks/{task}/task.md, tasks/{task}/task.json, existing task handoffs, dependent task handoffs, '
            f'and .agents/skills/{phase}/SKILL.md. Follow that skill. '
            f'Before returning, write a VALID UTF-8 JSON handoff to this ABSOLUTE file path: {hand}. '
            f'The handoff MUST include task_id, phase, cycle (integer), summary, changed_files, '
            f'decisions, tests, risks, next_steps, verdict, gaps. verdict N/A unless review (PASS or FAIL). '
            f'Write honest results, even on failure. Create parent directory if necessary. '
            f'Persist relevant knowledge in docs. Do not commit, modify task.md/task.json, benchmark state or tools. '
            f'Do not start another phase.')

def record_usage(state,u):
    if u['tokens'] is None:state['tokens_complete']=False
    else:state['reported_tokens']+=u['tokens']
    if u['cost_usd'] is None:state['cost_complete']=False
    else:state['reported_cost_usd']+=u['cost_usd']

def error_class(r,ok,reason,integrity,check):
    if not integrity:return 'INFRA_INTEGRITY'
    if r['timeout']:return 'TIMEOUT'
    if r['exit_code']!=0:return 'CLI_FAILURE'
    if not ok:return 'HANDOFF_INVALID'
    if check['exit_code']!=0:return 'ACCEPTANCE_FAILURE'
    return None

def execute_phase(agent,model,unsafe,state,w,task,cfg,dry=False,live=True):
    ts=state['tasks'][task];phase=ts['phase'];cycle=ts['cycle'];b,_,_=paths(agent)
    label=f'{task}-{phase}-{cycle}-attempt{ts["recovery"]}'
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    if dry:
        print('DRY RUN',label,' '.join(adapter(agent,model,unsafe,w)));return False
    ensure_local_git(w)
    ok,reason=protected_ok(w)
    if not ok:raise RuntimeError('Workspace already changed protected file before phase: '+reason)
    hand.parent.mkdir(parents=True,exist_ok=True)
    if hand.exists():
        archive=b/'handoff-archive'/f'{label}-{int(time.time())}.json'
        archive.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(hand,archive)
        hand.unlink()
    # checkpoint before any agent process, survives power loss
    write(b/'inflight.json',{'task':task,'phase':phase,'cycle':cycle,'recovery':ts['recovery'],'started':dt.datetime.now(dt.timezone.utc).isoformat()})
    print(f'START {label} (cwd={w})',flush=True)
    r=cmd(adapter(agent,model,unsafe,w)+[prompt_for(task,phase,cycle,w)],w,cfg['phase_timeout_seconds'],logfile=b/'logs'/f'{label}.jsonl',agent=agent,live=live)
    hand_ok,reason=handoff_valid(hand,task,phase,cycle)
    intact,integrity_error=protected_ok(w)
    if not intact:reason='Protected benchmark spec modified: '+integrity_error
    chk=external_checks(w,task,phase,cfg['benchmark_test_timeout_seconds']) if hand_ok and intact and r['exit_code']==0 else {'exit_code':1,'output':'not run'}
    failure=error_class(r,hand_ok,reason,intact,chk)
    u=usage(agent,r['output']);record_usage(state,u);state['spent_seconds']+=r['seconds']
    ev={'task':task,'phase':phase,'cycle':cycle,'recovery':ts['recovery'],'exit_code':r['exit_code'],'seconds':r['seconds'],'handoff_valid':hand_ok,'handoff_error':reason,'external_check_exit':chk['exit_code'],'external_check_tail':chk['output'][-1200:],'usage':u,'passed':failure is None,'failure_class':failure,'timestamp':dt.datetime.now(dt.timezone.utc).isoformat()}
    ts['history'].append(ev);state['events'].append(ev)
    # Always capture agent edits in local git, even for failure; crucial for recovery diagnosis.
    ensure_local_git(w)
    if not intact:
        # Restore benchmark-owned files, preserving violation in event and raw logs.
        for name in protected_manifest():
            source=(ROOT/'skills'/name[7:]) if name.startswith('skills/') else ((ROOT/name) if name.startswith('tasks/') else ROOT/'starter'/name)
            dest=w/('.agents/skills/'+name[7:] if name.startswith('skills/') else name)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
    git(w,'add','-A')
    git(w,'commit','--allow-empty','-qm',f'{task} {phase} cycle {cycle} {"PASS" if failure is None else failure}')
    ev['commit']=git(w,'rev-parse','HEAD')
    if failure:
        if ts['recovery']<cfg['recovery_attempts']:
            ts['recovery']+=1;print('RECOVERY pending',label,failure,reason,flush=True)
        else:
            ts['status']='BLOCKED';ts['blocked_reason']=f'{failure}: {reason or chk["output"][-250:] or r["exit_code"]}'
            print('BLOCKED',label,ts['blocked_reason'],flush=True)
    else:
        ts['recovery']=0;ts['status']='ACTIVE';ts.pop('blocked_reason',None)
        if phase=='plan':ts['phase']='implement'
        elif phase=='implement':ts['phase']='review'
        else:
            if read(hand)['verdict']=='PASS':ts['status']='DONE';ts['phase']='complete'
            elif cycle<cfg['max_cycles']:ts['cycle']+=1;ts['phase']='plan'
            else:ts['status']='BLOCKED';ts['blocked_reason']='REVIEW_GAPS: max cycles reached'
        print('FINISHED',label, '=>',ts['status'],ts['phase'],flush=True)
    return True

def choose_ready(agent,model,unsafe,state,w,timeout,dry=False,live=True):
    ids=ready(state)
    active=sorted(k for k in ids if state['tasks'][k]['status']=='ACTIVE')
    if active:return active[0]
    pending=sorted(k for k in ids if state['tasks'][k]['status']=='PENDING')
    if not pending:return None
    if len(pending)==1 or dry:return pending[0]
    prompt=f'WORKSPACE ROOT: {w.resolve()}. Select one available task ID among {pending} based on dependencies. Output only TASK-NNN.'
    b,_,_=paths(agent)
    r=cmd(adapter(agent,model,unsafe,w)+[prompt],w,min(timeout,120),logfile=b/'logs'/f'choose-{int(time.time())}.jsonl',agent=agent,live=live)
    valid=[m for m in re.findall(r'TASK-\d{3}',r['output']) if m in pending]
    return valid[-1] if r['exit_code']==0 and valid else pending[0]

def report(agent):
    b,w,s=paths(agent);st=read(s);tasks=st['tasks'];counts={x:sum(v['status']==x for v in tasks.values()) for x in ('PENDING','ACTIVE','DONE','BLOCKED')}
    events=st['events'];classes={k:sum(e.get('failure_class')==k for e in events) for k in sorted({e.get('failure_class') for e in events if e.get('failure_class')})}
    result={'agent':agent,'tasks_total':len(tasks),'status_counts':counts,'completed_ratio':round(counts['DONE']/len(tasks),4),'phases_attempted':len(events),'failure_classes':classes,'reported_total_tokens':st['reported_tokens'] if st['tokens_complete'] else None,'reported_total_cost_usd':round(st['reported_cost_usd'],4) if st['cost_complete'] else None,'wall_seconds_agent_calls':round(st['spent_seconds'],2),'unreported_usage_warning':not(st['tokens_complete'] and st['cost_complete']),'tasks':tasks}
    manual=b/'manual-review.json'
    if manual.exists():result['manual_review']=read(manual)
    write(b/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='tasks'},indent=2))
    return result

@contextmanager
def lock_run(agent):
    import fcntl
    b,_,_=paths(agent)
    lock_dir=ROOT/'runs'/'.locks';lock_dir.mkdir(parents=True,exist_ok=True)
    with open(lock_dir/(agent+'.lock'),'w') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError(f'Another run for {agent} is already active')
        yield

def main():
    p=argparse.ArgumentParser(description='Evolution Benchmark v2')
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('doctor','init','run','report','unblock'):
        q=sub.add_parser(name)
        if name!='doctor':q.add_argument('--agent',choices=('claude','codex','opencode'),required=True)
        if name=='run':
            q.add_argument('--model');q.add_argument('--allow-unsafe',action='store_true');q.add_argument('--dry-run',action='store_true');q.add_argument('--max-phases',type=int);q.add_argument('--quiet',action='store_true')
        if name=='unblock':q.add_argument('--task',required=True);q.add_argument('--phase',choices=PHASES);q.add_argument('--cycle',type=int)
    a=p.parse_args();cfg=read(ROOT/'benchmark.json')
    if a.action=='doctor':
        print('Python',sys.version.split()[0]);print('git:',shutil.which('git'))
        for name,v in cfg['agents'].items():
            tool=shutil.which(v['executable']);print(name,tool or 'NOT FOUND')
            if tool:
                try:print(' ',subprocess.run([tool,'--version'],text=True,capture_output=True,timeout=8).stdout.strip()[:180])
                except Exception as e:print(' version unavailable',e)
        return
    if a.action=='init':print('Workspace:',init(a.agent));return
    if a.action=='report':report(a.agent);return
    if a.action=='unblock':
        b,w,s=paths(a.agent);st=read(s);ts=st['tasks'][a.task]
        if ts['status']!='BLOCKED':raise RuntimeError('Task is not BLOCKED')
        ts['status']='ACTIVE';ts['recovery']=0;ts.pop('blocked_reason',None)
        if a.phase:ts['phase']=a.phase
        if a.cycle:ts['cycle']=a.cycle
        write(s,st);print('Unblocked',a.task,ts['phase'],ts['cycle']);return
    with lock_run(a.agent):
        b,w,s=paths(a.agent)
        if not s.exists():init(a.agent)
        if not a.dry_run and not shutil.which(cfg['agents'][a.agent]['executable']):p.error('CLI missing')
        ensure_local_git(w)
        if (b/'inflight.json').exists():
            print('WARNING: prior interrupted phase:',read(b/'inflight.json'))
            (b/'inflight.json').unlink()
        st=read(s);n=0
        while True:
            if a.max_phases is not None and n>=a.max_phases:break
            if st['spent_seconds']>=cfg['max_run_seconds']:print('time budget exceeded');break
            if cfg['max_cost_usd'] is not None and (not st['cost_complete'] or st['reported_cost_usd']>=cfg['max_cost_usd']):print('cost budget reached/unknown');break
            if cfg['max_tokens'] is not None and (not st['tokens_complete'] or st['reported_tokens']>=cfg['max_tokens']):print('token budget reached/unknown');break
            task=choose_ready(a.agent,a.model,a.allow_unsafe,st,w,cfg['phase_timeout_seconds'],a.dry_run,not a.quiet)
            if not task:break
            done=execute_phase(a.agent,a.model,a.allow_unsafe,st,w,task,cfg,a.dry_run,not a.quiet)
            if not done:break
            write(s,st);(b/'inflight.json').unlink(missing_ok=True);n+=1
        report(a.agent)

if __name__=='__main__':main()
