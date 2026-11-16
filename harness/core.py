"""Evolution Agent Benchmark v1: subprocess isolated, resumable, streaming, local-only git harness."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager

BENCHMARK_VERSION = 1
ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASES = ('plan', 'implement', 'review')
TRACKS = ('sequential',)
# Paths inside the agent container.
CONTAINER_WS = '/workspace'
CONTAINER_HOME = '/root'
CONTAINER_CLI = '/opt/evo-cli'
# Login/config files (relative to $HOME) copied into a run's private container home.
LOGIN_FILES = {
    'claude': ('.claude/.credentials.json',),
    'codex': ('.codex/auth.json',),
    'opencode': ('.config/opencode/opencode.jsonc','.config/opencode/opencode.json','.local/share/opencode/auth.json'),
}
LOGIN_REQUIRED = ('claude','codex')
REQUIRED = ('summary','changed_files','decisions','tests','risks','next_steps','verdict','gaps')

def read(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))

def write(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, p)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def config():
    return read(ROOT/'benchmark.json')

def specs():
    return {p.parent.name: read(p) for p in sorted((ROOT/'tasks').glob('TASK-*/task.json'))}

# --- profiles and runs -------------------------------------------------------

def runs_root(cfg):
    """Run data lives outside the harness tree so agents cannot read operator files."""
    r = pathlib.Path(cfg['runs_root']).expanduser().resolve()
    root = ROOT.resolve()
    if r == root or root in r.parents:
        raise RuntimeError(f'runs_root must be outside the benchmark repository: {r}')
    return r

def resolve_profile(cfg, name):
    """A profile is one CLI + model + settings; defaults are filled in from the config."""
    if name not in cfg['profiles']:
        raise RuntimeError(f'Unknown profile {name!r}; available: {", ".join(sorted(cfg["profiles"]))}')
    p = {**cfg['defaults'], **cfg['profiles'][name]}
    if p.get('cli') not in cfg['clis']:
        raise RuntimeError(f'Profile {name!r} names unknown cli {p.get("cli")!r}')
    p['executable'] = cfg['clis'][p['cli']]['executable']
    p.setdefault('model', None)
    return p

def fingerprint(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()[:16]

class Run:
    """One benchmark run: <runs_root>/<profile>/<track>/<run_id>/."""
    def __init__(self, name, track='sequential', run_id='r1', cfg=None, container=False):
        if track not in TRACKS: raise RuntimeError(f'Unknown track {track!r}')
        if not re.fullmatch(r'[A-Za-z0-9._-]+', run_id): raise RuntimeError(f'Invalid run id {run_id!r}')
        self.cfg = cfg or config()
        self.name, self.track, self.run_id = name, track, run_id
        self.profile = resolve_profile(self.cfg, name)
        self.cli = self.profile['cli']
        self.root = runs_root(self.cfg)
        self.base = self.root/name/track/run_id
        self.workspace = self.base/'workspace'
        self.state = self.base/'state.json'
        self.meta = self.base/'run.json'
        self.container = container
        self.home = self.base/'home'   # container $HOME; holds copied logins, never publish it

def initial_state():
    return {'version':1,'tasks':{k:{'status':'PENDING','phase':'plan','cycle':1,'recovery':0,'history':[]} for k in specs()},'events':[],'spent_seconds':0,'reported_cost_usd':0,'reported_tokens':0,'cost_complete':True,'tokens_complete':True}

def cli_version(executable):
    tool = shutil.which(executable)
    if not tool: return None
    try: return subprocess.run([tool,'--version'],text=True,capture_output=True,timeout=8).stdout.strip()[:180] or None
    except Exception: return None

def host_info():
    info = {'platform':platform.platform(),'python':platform.python_version(),'cpu_count':os.cpu_count(),'cpu_model':None,'ram_gb':None}
    try:
        for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'): info['cpu_model']=line.split(':',1)[1].strip();break
        for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal'): info['ram_gb']=round(int(line.split()[1])/1048576,1);break
    except (OSError,ValueError,IndexError): pass
    return info

def harness_commit():
    try:
        head = git(ROOT,'rev-parse','HEAD')
        return head + ('-dirty' if git(ROOT,'status','--porcelain') else '')
    except Exception: return None

def run_metadata(run):
    return {'benchmark_version':BENCHMARK_VERSION,'profile':run.name,'track':run.track,'run_id':run.run_id,
            'cli':run.cli,'model':run.profile['model'],'settings':run.profile,'fingerprint':fingerprint(run.profile),
            'cli_version':cli_version(run.profile['executable']),'harness_commit':harness_commit(),
            'isolation':'container' if run.container else 'host',
            'container_image':image_id(run.cfg) if run.container else None,
            'host':host_info(),'created':now()}

def check_unchanged(run):
    """A run is only comparable if every phase used the same model and settings."""
    stored = read(run.meta)
    if stored['fingerprint'] != fingerprint(run.profile):
        raise RuntimeError(f'Profile {run.name!r} changed since this run started '
                           f'(was {stored["settings"]}). Start a new run with --run-id.')
    mode = 'container' if run.container else 'host'
    if stored.get('isolation','host') != mode:
        raise RuntimeError(f'This run was started in {stored.get("isolation","host")} mode, not {mode} mode. '
                           f'Start a new run with --run-id.')

# --- container isolation -----------------------------------------------------

def runtime(cfg):
    return cfg['container']['runtime']

def image_id(cfg):
    p = subprocess.run([runtime(cfg),'image','inspect','-f','{{.Id}}',cfg['container']['image']],text=True,capture_output=True)
    return p.stdout.strip() or None if p.returncode==0 else None

def container_name(run):
    return 'evo-' + re.sub(r'[^a-z0-9_.-]','-',f'{run.name}-{run.track}-{run.run_id}'.lower())

def cli_mount(profile):
    """Mount the host's CLI read-only so the container runs the recorded CLI version.

    Returns (host source, container target, executable path inside the container)."""
    tool = shutil.which(profile['executable'])
    if not tool: raise RuntimeError(f'CLI not found on host: {profile["executable"]}')
    real = pathlib.Path(tool).resolve()
    target = f'{CONTAINER_CLI}/{profile["cli"]}'
    package = real.parent.parent
    home = pathlib.Path.home()
    # A self-contained package folder (<pkg>/bin/<exe> plus resources) is mounted whole.
    if real.parent.name == 'bin' and home in package.parents and package != home/'.local':
        return package, target, f'{target}/bin/{real.name}'
    inner = f'{target}/bin/{profile["cli"]}'
    return real, inner, inner

def network_arg(profile):
    """Outbound internet only; host services are unreachable except explicitly listed loopback ports."""
    return 'pasta:--map-guest-addr,none' + ''.join(f',-T,{int(p)}' for p in profile.get('host_ports') or [])

def container_create_argv(run):
    c = run.cfg['container']; p = run.profile; src, target, _ = cli_mount(p)
    argv = [c['runtime'],'run','-d','--name',container_name(run),'--hostname','evo-sandbox','--stop-signal','SIGKILL',
            '--network',network_arg(p),
            '-v',f'{run.workspace}:{CONTAINER_WS}','-v',f'{run.home}:{CONTAINER_HOME}','-v',f'{src}:{target}:ro',
            '-e','IS_SANDBOX=1','-e',f'HOME={CONTAINER_HOME}','-w',CONTAINER_WS]
    for k in ('cpus','memory'):
        v = p.get(k) or c.get(k)
        if v: argv += [f'--{k}',str(v)]
    return argv + [c['image'],'sleep','infinity']

def container_exec_argv(run, argv, timeout):
    """Wrap an adapter command; `timeout` inside the container kills the whole agent process tree."""
    exe = cli_mount(run.profile)[2]
    env = [x for k,v in (run.profile.get('env') or {}).items() for x in ('-e',f'{k}={v}')]
    return [runtime(run.cfg),'exec',*env,'-w',CONTAINER_WS,container_name(run),
            'timeout','-k','10',str(int(timeout)),exe,*argv[1:]]

def copy_logins(run, refresh=False):
    """Give the run its own copy of the CLI login; the rest of the host home stays invisible."""
    found = False
    for rel in LOGIN_FILES[run.cli]:
        src = pathlib.Path.home()/rel; dest = run.home/rel
        if src.is_file() and (refresh or not dest.exists()):
            dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest); dest.chmod(0o600)
        found = found or dest.exists()
    if run.cli in LOGIN_REQUIRED and not found:
        raise RuntimeError(f'No {run.cli} login found on the host ({LOGIN_FILES[run.cli][0]}); log in with the CLI first.')

def ensure_container(run, refresh_login=False):
    rt = runtime(run.cfg); name = container_name(run)
    run.home.mkdir(parents=True,exist_ok=True)
    copy_logins(run,refresh_login)
    if subprocess.run([rt,'container','exists',name]).returncode == 0:
        state = subprocess.run([rt,'inspect','-f','{{.State.Running}}',name],text=True,capture_output=True).stdout.strip()
        if state != 'true': subprocess.run([rt,'start',name],check=True,capture_output=True)
        return
    if not image_id(run.cfg):
        raise RuntimeError(f'Container image {run.cfg["container"]["image"]} is missing; run: python3 run.py build-image')
    p = subprocess.run(container_create_argv(run),text=True,capture_output=True)
    if p.returncode: raise RuntimeError(f'Could not start container: {p.stderr[-800:]}')

def stop_container(run):
    subprocess.run([runtime(run.cfg),'stop','-t','2',container_name(run)],capture_output=True)

def build_image(cfg):
    return subprocess.run([runtime(cfg),'build','-t',cfg['container']['image'],'-f',str(ROOT/'container'/'Containerfile'),str(ROOT/'container')]).returncode

# --- workspace integrity -----------------------------------------------------

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

def init(run):
    w = run.workspace
    if run.state.exists(): return w
    if run.base.exists(): raise RuntimeError(f'Incomplete run directory: {run.base} (do not overwrite)')
    run.base.mkdir(parents=True)
    shutil.copytree(ROOT/'starter',w)
    shutil.copytree(ROOT/'tasks',w/'tasks')
    shutil.copytree(ROOT/'skills',w/'.agents'/'skills')
    git(w,'init','-q')
    git(w,'config','user.name',run.cfg['git_author_name'])
    git(w,'config','user.email',run.cfg['git_author_email'])
    git(w,'add','-A')
    git(w,'commit','-qm','benchmark baseline')
    write(run.meta,run_metadata(run))
    write(run.state,initial_state())
    return w

def ready(state):
    sp = specs()
    return [k for k,t in state['tasks'].items() if t['status'] in ('PENDING','ACTIVE') and all(state['tasks'][d]['status']=='DONE' for d in sp[k]['dependencies'])]

# --- CLI adapters ------------------------------------------------------------

def adapter(profile, unsafe=False):
    cli=profile['cli'];model=profile.get('model');base=[profile['executable']]
    if cli == 'claude':
        base+=['-p','--output-format','stream-json','--verbose']
        if profile.get('max_turns'): base+=['--max-turns',str(profile['max_turns'])]
        if unsafe: base.append('--dangerously-skip-permissions')
        if model: base+=['--model',model]
    elif cli == 'codex':
        base+=['exec','--json','--ephemeral']
        base += ['--dangerously-bypass-approvals-and-sandbox'] if unsafe else ['--sandbox','workspace-write']
        if model: base+=['--model',model]
    elif cli == 'opencode':
        # The workspace is selected through the subprocess working directory.
        base+=['run','--standalone','--format','json']
        if unsafe: base.append('--auto')
        if model: base+=['--model',model]
    else:
        raise RuntimeError(f'No adapter for cli {cli!r}')
    return base + list(profile.get('extra_args') or [])

def usage(cli, out):
    """Sum the usage a CLI reports over one process. None means 'not reported', never zero."""
    tok=cost=model=None
    for line in out.splitlines():
        try:o=json.loads(line)
        except (ValueError,TypeError):continue
        if not isinstance(o,dict):continue
        if cli=='claude':
            if o.get('type')=='system' and o.get('subtype')=='init' and isinstance(o.get('model'),str):
                model=o['model']
            if o.get('type')=='result':
                c=o.get('total_cost_usd')
                if isinstance(c,(int,float)): cost=(cost or 0)+float(c)
                u=o.get('usage') or {}
                if isinstance(u,dict):
                    v=sum(u.get(k,0) or 0 for k in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'))
                    if v:tok=(tok or 0)+int(v)
        elif cli=='codex' and o.get('type')=='turn.completed':
            u=o.get('usage') or {}
            if isinstance(u,dict):
                v=(u.get('input_tokens') or 0)+(u.get('output_tokens') or 0)
                if v:tok=(tok or 0)+int(v)
        elif cli=='opencode':
            part=o.get('part') or {}
            if isinstance(part,dict):
                c=part.get('cost')
                if isinstance(c,(int,float)):cost=(cost or 0)+c
                t=part.get('tokens') or {}
                if isinstance(t,dict):
                    v=(t.get('input') or 0)+(t.get('output') or 0)+(t.get('reasoning') or 0)
                    if v:tok=(tok or 0)+v
    return {'tokens':tok,'cost_usd':cost,'reported_model':model}

def short_event(cli, line):
    try:o=json.loads(line)
    except ValueError:return None
    if not isinstance(o,dict):return None
    if cli=='claude':
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
    if cli=='codex':
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

def cmd(argv,cwd,timeout=30,stdin=None,logfile=None,agent=None,live=False,env=None):
    start=time.monotonic();out=[];timed_out=False
    if logfile:
        logfile=pathlib.Path(logfile);logfile.parent.mkdir(parents=True,exist_ok=True)
    proc=subprocess.Popen(argv,cwd=str(cwd),stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env={**os.environ,**env} if env else None)
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

# --- phases ------------------------------------------------------------------

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

SANDBOX_NOTE=('ENVIRONMENT: you are root inside a disposable Linux container (Ubuntu 24.04; Python 3, Rust, Node, build tools, xvfb). '
              'You may install what you need. System packages installed with apt may NOT persist into later phases: '
              'record every system dependency and its exact install command in docs/STATE.md and reinstall when missing. ')

def prompt_for(task,phase,cycle,w=None,sandbox=False):
    if w is None: w=pathlib.Path.cwd()
    w=pathlib.PurePosixPath(w) if sandbox else pathlib.Path(w).resolve()
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    return (f'WORKSPACE ROOT (absolute): {w}\n'
            + (SANDBOX_NOTE if sandbox else '') +
            f'IMPORTANT: This is the ONLY code project root; do NOT access files outside it. '
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

def phase_argv(run,task,phase,cycle,unsafe=False):
    """Full command for one phase: the CLI adapter plus prompt, wrapped for the container if used."""
    timeout=run.profile['phase_timeout_seconds']
    if run.container:
        argv=adapter(run.profile,True)+[prompt_for(task,phase,cycle,CONTAINER_WS,sandbox=True)]
        return container_exec_argv(run,argv,timeout)
    return adapter(run.profile,unsafe)+[prompt_for(task,phase,cycle,run.workspace)]

def execute_phase(run,state,task,unsafe=False,live=True):
    cfg=run.cfg;w=run.workspace;b=run.base;profile=run.profile
    ts=state['tasks'][task];phase=ts['phase'];cycle=ts['cycle']
    label=f'{task}-{phase}-{cycle}-attempt{ts["recovery"]}'
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    argv=phase_argv(run,task,phase,cycle,unsafe)
    if run.container:ensure_container(run)
    ensure_local_git(w)
    ok,reason=protected_ok(w)
    if not ok:raise RuntimeError('Workspace already changed protected file before phase: '+reason)
    hand.parent.mkdir(parents=True,exist_ok=True)
    if hand.exists():
        archive=b/'handoff-archive'/f'{label}-{int(time.time())}.json'
        archive.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(hand,archive)
        hand.unlink()
    # checkpoint before any agent process, survives power loss
    write(b/'inflight.json',{'task':task,'phase':phase,'cycle':cycle,'recovery':ts['recovery'],'started':now()})
    print(f'START {label} (cwd={w})',flush=True)
    limit=profile['phase_timeout_seconds']
    if run.container:
        # The in-container `timeout` enforces the limit (exit 124); the outer limit is only a backstop.
        r=cmd(argv,b,limit+60,logfile=b/'logs'/f'{label}.jsonl',agent=run.cli,live=live)
        if r['exit_code']==124:r['timeout']=True
    else:
        r=cmd(argv,w,limit,logfile=b/'logs'/f'{label}.jsonl',agent=run.cli,live=live,env=profile.get('env'))
    hand_ok,reason=handoff_valid(hand,task,phase,cycle)
    intact,integrity_error=protected_ok(w)
    if not intact:reason='Protected benchmark spec modified: '+integrity_error
    chk=external_checks(w,task,phase,cfg['benchmark_test_timeout_seconds']) if hand_ok and intact and r['exit_code']==0 else {'exit_code':1,'output':'not run'}
    failure=error_class(r,hand_ok,reason,intact,chk)
    u=usage(run.cli,r['output']);record_usage(state,u);state['spent_seconds']+=r['seconds']
    ev={'task':task,'phase':phase,'cycle':cycle,'recovery':ts['recovery'],'exit_code':r['exit_code'],'seconds':r['seconds'],'handoff_valid':hand_ok,'handoff_error':reason,'external_check_exit':chk['exit_code'],'external_check_tail':chk['output'][-1200:],'usage':u,'passed':failure is None,'failure_class':failure,'timestamp':now()}
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

def choose_ready(state):
    """Deterministic order: finish started tasks first, then the lowest ready task ID.

    The harness decides, not the model, so every profile works through the same sequence."""
    ids=ready(state)
    active=sorted(k for k in ids if state['tasks'][k]['status']=='ACTIVE')
    if active:return active[0]
    pending=sorted(k for k in ids if state['tasks'][k]['status']=='PENDING')
    return pending[0] if pending else None

def report(run):
    st=read(run.state);meta=read(run.meta);tasks=st['tasks']
    counts={x:sum(v['status']==x for v in tasks.values()) for x in ('PENDING','ACTIVE','DONE','BLOCKED')}
    events=st['events'];classes={k:sum(e.get('failure_class')==k for e in events) for k in sorted({e.get('failure_class') for e in events if e.get('failure_class')})}
    reported=sorted({e['usage'].get('reported_model') for e in events if e['usage'].get('reported_model')})
    result={'benchmark_version':meta['benchmark_version'],'isolation':meta.get('isolation','host'),'profile':run.name,'track':run.track,'run_id':run.run_id,'cli':meta['cli'],'cli_version':meta['cli_version'],'model':meta['model'],'reported_models':reported,'harness_commit':meta['harness_commit'],'host':meta['host'],
            'tasks_total':len(tasks),'status_counts':counts,'completed_ratio':round(counts['DONE']/len(tasks),4),'phases_attempted':len(events),'failure_classes':classes,'reported_total_tokens':st['reported_tokens'] if st['tokens_complete'] else None,'reported_total_cost_usd':round(st['reported_cost_usd'],4) if st['cost_complete'] else None,'wall_seconds_agent_calls':round(st['spent_seconds'],2),'unreported_usage_warning':not(st['tokens_complete'] and st['cost_complete']),'tasks':tasks}
    manual=run.base/'manual-review.json'
    if manual.exists():result['manual_review']=read(manual)
    write(run.base/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('tasks','host')},indent=2))
    return result

@contextmanager
def lock_run(run):
    import fcntl
    lock_dir=run.root/'.locks';lock_dir.mkdir(parents=True,exist_ok=True)
    with open(lock_dir/f'{run.name}--{run.track}--{run.run_id}.lock','w') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError(f'Another process is already working on {run.base}')
        yield

def doctor(cfg):
    print('Benchmark version',BENCHMARK_VERSION);print('Python',sys.version.split()[0]);print('git:',shutil.which('git'))
    print('runs root:',runs_root(cfg))
    for name,v in cfg['clis'].items():
        print(f'cli {name}:',shutil.which(v['executable']) or 'NOT FOUND',' ',cli_version(v['executable']) or '')
    c=cfg['container'];rt=shutil.which(c['runtime'])
    print(f'container runtime {c["runtime"]}:',rt or 'NOT FOUND')
    if rt:print(f'container image {c["image"]}:',image_id(cfg) or 'NOT BUILT (run: python3 run.py build-image)')
    print('profiles:')
    for name in sorted(cfg['profiles']):
        p=resolve_profile(cfg,name)
        print(f'  {name}: cli={p["cli"]} model={p["model"] or "(CLI default)"} phase_timeout={p["phase_timeout_seconds"]}s')

def main():
    cfg=config()
    p=argparse.ArgumentParser(description=f'Evolution Agent Benchmark v{BENCHMARK_VERSION}')
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('doctor','build-image','init','run','report','unblock'):
        q=sub.add_parser(name)
        if name not in ('doctor','build-image'):
            q.add_argument('--profile',choices=sorted(cfg['profiles']),required=True,help='named CLI + model combination from benchmark.json')
            q.add_argument('--track',choices=TRACKS,default='sequential')
            q.add_argument('--run-id',default='r1',help='distinguishes repeated runs of the same profile and track')
        if name in ('init','run'):
            q.add_argument('--no-container',action='store_true',help='run the agent directly on the host instead of in the sandbox container')
        if name=='run':
            q.add_argument('--refresh-login',action='store_true',help='copy the host CLI login into the run again')
            q.add_argument('--allow-unsafe',action='store_true',help='host mode only: let the CLI skip its permission prompts');q.add_argument('--dry-run',action='store_true');q.add_argument('--max-phases',type=int);q.add_argument('--quiet',action='store_true')
        if name=='unblock':q.add_argument('--task',required=True);q.add_argument('--phase',choices=PHASES);q.add_argument('--cycle',type=int)
    a=p.parse_args()
    if a.action=='doctor':doctor(cfg);return
    if a.action=='build-image':sys.exit(build_image(cfg))
    run=Run(a.profile,a.track,a.run_id,cfg,container=not getattr(a,'no_container',False))
    if a.action=='run' and a.dry_run:
        st=read(run.state) if run.state.exists() else initial_state()
        task=choose_ready(st)
        if task:
            ts=st['tasks'][task];print('DRY RUN',task,ts['phase'],'cycle',ts['cycle']);print(' '.join(phase_argv(run,task,ts['phase'],ts['cycle'],a.allow_unsafe)))
            if run.container:print('container:',' '.join(container_create_argv(run)))
        return
    if a.action=='init':print('Workspace:',init(run));return
    if a.action=='report':report(run);return
    if a.action=='unblock':
        st=read(run.state);ts=st['tasks'][a.task]
        if ts['status']!='BLOCKED':raise RuntimeError('Task is not BLOCKED')
        ts['status']='ACTIVE';ts['recovery']=0;ts.pop('blocked_reason',None)
        if a.phase:ts['phase']=a.phase
        if a.cycle:ts['cycle']=a.cycle
        write(run.state,st);print('Unblocked',a.task,ts['phase'],ts['cycle']);return
    with lock_run(run):
        b=run.base;w=run.workspace
        if not run.state.exists():init(run)
        check_unchanged(run)
        if not shutil.which(run.profile['executable']):p.error('CLI missing')
        if run.container and a.refresh_login:copy_logins(run,True)
        ensure_local_git(w)
        if (b/'inflight.json').exists():
            print('WARNING: prior interrupted phase:',read(b/'inflight.json'))
            (b/'inflight.json').unlink()
        st=read(run.state);n=0
        while True:
            if a.max_phases is not None and n>=a.max_phases:break
            if st['spent_seconds']>=cfg['max_run_seconds']:print('time budget exceeded');break
            if cfg['max_cost_usd'] is not None and (not st['cost_complete'] or st['reported_cost_usd']>=cfg['max_cost_usd']):print('cost budget reached/unknown');break
            if cfg['max_tokens'] is not None and (not st['tokens_complete'] or st['reported_tokens']>=cfg['max_tokens']):print('token budget reached/unknown');break
            task=choose_ready(st)
            if not task:break
            try:execute_phase(run,st,task,a.allow_unsafe,not a.quiet)
            except BaseException:
                if run.container:stop_container(run)
                raise
            write(run.state,st);(b/'inflight.json').unlink(missing_ok=True);n+=1
        if run.container:stop_container(run)
        report(run)

if __name__=='__main__':main()
