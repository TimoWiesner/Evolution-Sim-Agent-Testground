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
import threading
import time
from contextlib import contextmanager

BENCHMARK_VERSION = 1
ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASES = ('plan', 'implement', 'review')
TRACKS = ('sequential','parallel')
# Paths inside the agent container.
CONTAINER_WS = '/workspace'
CONTAINER_HOME = '/root'
CONTAINER_CLI = '/opt/evo-cli'
CONTAINER_WORKERS = '/workers'   # parallel track: one private checkout per task in progress
# Login/config files (relative to $HOME) copied into a run's private container home.
LOGIN_FILES = {
    'claude': ('.claude/.credentials.json',),
    'codex': ('.codex/auth.json',),
    'opencode': ('.config/opencode/opencode.jsonc','.config/opencode/opencode.json','.local/share/opencode/auth.json'),
}
LOGIN_REQUIRED = ('claude','codex')
PROTECTED_STARTER = ('AGENTS.md','CLAUDE.md','docs/CONTRACT.md')
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
    def __init__(self, name, track='sequential', run_id='r1', cfg=None, container=False, workers=None):
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
        self.workers_dir = self.base/'workers'
        # Number of agents working at the same time; fixed for the whole run.
        self.workers = 1
        if track == 'parallel':
            stored = read(self.meta).get('workers') if self.meta.exists() else None
            self.workers = int(workers or stored or self.profile.get('workers') or 1)
            if self.workers < 1: raise RuntimeError('--workers must be at least 1')

    def place(self, task, phase):
        """Where a phase works: (host path, path inside the container).

        Parallel tasks are developed in a private checkout and only merged into the workspace."""
        if self.track == 'parallel' and phase != 'merge':
            return self.workers_dir/task, f'{CONTAINER_WORKERS}/{task}'
        return self.workspace, CONTAINER_WS

def initial_state():
    return {'version':1,'tasks':{k:{'status':'PENDING','phase':'plan','cycle':1,'recovery':0,'history':[]} for k in specs()},'events':[],'interventions':[],'evaluations':[],'spent_seconds':0,'reported_cost_usd':0,'reported_tokens':0,'cost_complete':True,'tokens_complete':True}

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
            'isolation':'container' if run.container else 'host','workers':run.workers,
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
    if stored.get('workers',1) != run.workers:
        raise RuntimeError(f'This run was started with {stored.get("workers",1)} worker(s), not {run.workers}. '
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
    if run.track == 'parallel': argv += ['-v',f'{run.workers_dir}:{CONTAINER_WORKERS}']
    for k in ('cpus','memory'):
        v = p.get(k) or c.get(k)
        if v: argv += [f'--{k}',str(v)]
    return argv + [c['image'],'sleep','infinity']

def container_exec_argv(run, argv, timeout, cwd=CONTAINER_WS):
    """Wrap an adapter command; `timeout` inside the container kills the whole agent process tree."""
    exe = cli_mount(run.profile)[2]
    env = [x for k,v in (run.profile.get('env') or {}).items() for x in ('-e',f'{k}={v}')]
    return [runtime(run.cfg),'exec',*env,'-w',cwd,container_name(run),
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

CONTAINER_LOCK = threading.Lock()

def ensure_container(run, refresh_login=False):
    with CONTAINER_LOCK: _ensure_container(run, refresh_login)

def _ensure_container(run, refresh_login):
    rt = runtime(run.cfg); name = container_name(run)
    run.home.mkdir(parents=True,exist_ok=True)
    if run.track == 'parallel': run.workers_dir.mkdir(parents=True,exist_ok=True)
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
    for name in PROTECTED_STARTER:
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

TOKEN_KINDS = ('input_tokens','cached_input_tokens','output_tokens')

def usage(cli, out):
    """Sum the usage a CLI reports over one process. None means 'not reported', never zero.

    Tokens are normalised so CLIs can be compared: input_tokens is fresh (uncached) input including
    cache writes, cached_input_tokens is input read from the provider cache, output_tokens includes
    reasoning. `tokens` is their sum."""
    cost=model=None;seen=False;t=dict.fromkeys(TOKEN_KINDS,0)
    def num(d,*keys):
        return sum(d.get(k) or 0 for k in keys if isinstance(d.get(k),(int,float)))
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
                u=o.get('usage')
                if isinstance(u,dict):
                    seen=True
                    t['input_tokens']+=num(u,'input_tokens','cache_creation_input_tokens')
                    t['cached_input_tokens']+=num(u,'cache_read_input_tokens')
                    t['output_tokens']+=num(u,'output_tokens')
        elif cli=='codex' and o.get('type')=='turn.completed':
            u=o.get('usage')
            if isinstance(u,dict):
                seen=True;cached=num(u,'cached_input_tokens')
                t['input_tokens']+=max(num(u,'input_tokens')-cached,0)
                t['cached_input_tokens']+=cached
                t['output_tokens']+=num(u,'output_tokens')
        elif cli=='opencode':
            part=o.get('part') or {}
            if isinstance(part,dict):
                c=part.get('cost')
                if isinstance(c,(int,float)):cost=(cost or 0)+c
                u=part.get('tokens')
                if isinstance(u,dict):
                    seen=True;cache=u.get('cache') if isinstance(u.get('cache'),dict) else {}
                    t['input_tokens']+=num(u,'input')+num(cache,'write')
                    t['cached_input_tokens']+=num(cache,'read')
                    t['output_tokens']+=num(u,'output','reasoning')
    total=int(sum(t.values()))
    if not seen or not total:return {'tokens':None,**dict.fromkeys(TOKEN_KINDS),'cost_usd':cost,'reported_model':model}
    return {'tokens':total,**{k:int(v) for k,v in t.items()},'cost_usd':cost,'reported_model':model}

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

STOP = threading.Event()   # set to end every running agent process (parallel track)

class Interrupted(Exception):
    pass

def cmd(argv,cwd,timeout=30,stdin=None,logfile=None,agent=None,live=False,env=None,prefix=''):
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
            if time.monotonic()-start>timeout or STOP.is_set():
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
                    print(f'  • {prefix}{msg}',flush=True);last_event=msg
        proc.wait()
        proc.stdout.close()
    if STOP.is_set():raise Interrupted()
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

PARALLEL_NOTE=('PARALLEL WORK: this workspace is your private checkout for this one task. Other agents are working on other '
               'tasks at the same time in their own checkouts; you cannot see their unfinished work. When your task passes review, '
               'your commits are merged into the main line. Keep changes focused on your task and avoid needless rewrites of shared '
               'files, so the merge stays simple. Build output and installed project dependencies are not shared between checkouts; '
               'run ./setup.sh here when something is missing. ')

def merge_prompt(task,cycle,files,w,sandbox=False):
    w=pathlib.PurePosixPath(w) if sandbox else pathlib.Path(w).resolve()
    hand=w/'tasks'/task/'handoffs'/f'merge-cycle{cycle}.json'
    return (f'WORKSPACE ROOT (absolute): {w}\n'
            + (SANDBOX_NOTE if sandbox else '') +
            f'IMPORTANT: This is the ONLY code project root; do NOT access files outside it. Fresh context; no prior conversation. '
            f'Task {task}, phase MERGE, cycle {cycle}. '
            f'{task} was developed in parallel with other tasks and has passed its review. Git is now merging it into the main line '
            f'in this workspace and stopped with conflicts in: {", ".join(files)}. '
            f'Read AGENTS.md, docs/CONTRACT.md, docs/STATE.md, tasks/{task}/task.md and the handoffs of {task} and of the tasks '
            f'whose changes collide with it (see `git status`, `git diff`, `git log --merge`). '
            f'Resolve every conflict so that the work of BOTH sides is kept and works together; never drop one side to make the '
            f'conflict disappear. Remove all conflict markers. Run ./setup.sh if needed and the test suite, and fix what the '
            f'combination broke. Do not start new feature work. '
            f'Do NOT run git commit, git merge --abort, git reset or git checkout of whole branches; the orchestrator concludes the merge. '
            f'Before returning, write a VALID UTF-8 JSON handoff to this ABSOLUTE file path: {hand}. '
            f'The handoff MUST include task_id, phase ("merge"), cycle (integer), summary, changed_files, '
            f'decisions, tests, risks, next_steps, verdict ("N/A"), gaps. Write honest results, even on failure.')

def prompt_for(task,phase,cycle,w=None,sandbox=False,parallel=False):
    if w is None: w=pathlib.Path.cwd()
    w=pathlib.PurePosixPath(w) if sandbox else pathlib.Path(w).resolve()
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    return (f'WORKSPACE ROOT (absolute): {w}\n'
            + (SANDBOX_NOTE if sandbox else '') + (PARALLEL_NOTE if parallel else '') +
            f'IMPORTANT: This is the ONLY code project root; do NOT access files outside it. '
            f'First verify files {w}/AGENTS.md and {w}/docs/STATE.md exist. '
            f'Use absolute paths when unsure. Fresh context; no prior conversation. '
            f'Task {task}, phase {phase.upper()}, cycle {cycle}. '
            f'Read AGENTS.md, docs/PROJECT.md, docs/CONTRACT.md, docs/STATE.md, docs/ARCHITECTURE.md, '
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

def phase_argv(run,task,phase,cycle,unsafe=False,files=()):
    """Full command for one phase: the CLI adapter plus prompt, wrapped for the container if used."""
    timeout=run.profile['phase_timeout_seconds'];host,inside=run.place(task,phase)
    w=inside if run.container else host
    if phase=='merge':prompt=merge_prompt(task,cycle,files,w,sandbox=run.container)
    else:prompt=prompt_for(task,phase,cycle,w,sandbox=run.container,parallel=run.track=='parallel')
    if run.container:
        return container_exec_argv(run,adapter(run.profile,True)+[prompt],timeout,inside)
    return adapter(run.profile,unsafe)+[prompt]

def agent_call(run,task,phase,cycle,label,unsafe=False,live=True,files=()):
    """Run one fresh agent process for a phase and return the result of `cmd`."""
    b=run.base;w=run.place(task,phase)[0];limit=run.profile['phase_timeout_seconds']
    argv=phase_argv(run,task,phase,cycle,unsafe,files)
    prefix=f'[{task}] ' if run.track=='parallel' else ''
    if run.container:
        # The in-container `timeout` enforces the limit (exit 124); the outer limit is only a backstop.
        r=cmd(argv,b,limit+60,logfile=b/'logs'/f'{label}.jsonl',agent=run.cli,live=live,prefix=prefix)
        if r['exit_code']==124:r['timeout']=True
    else:
        r=cmd(argv,w,limit,logfile=b/'logs'/f'{label}.jsonl',agent=run.cli,live=live,env=run.profile.get('env'),prefix=prefix)
    return r

def inflight_path(run,task):
    return run.base/(f'inflight-{task}.json' if run.track=='parallel' else 'inflight.json')

def archive_handoff(run,hand,label):
    hand.parent.mkdir(parents=True,exist_ok=True)
    if hand.exists():
        archive=run.base/'handoff-archive'/f'{label}-{int(time.time())}.json'
        archive.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(hand,archive)
        hand.unlink()

def restore_protected(w):
    """Put benchmark-owned files back; the violation stays visible in the event and raw logs."""
    for name in protected_manifest():
        source=(ROOT/'skills'/name[7:]) if name.startswith('skills/') else ((ROOT/name) if name.startswith('tasks/') else ROOT/'starter'/name)
        dest=w/('.agents/skills/'+name[7:] if name.startswith('skills/') else name)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)

class NoLock:
    def __enter__(self):return self
    def __exit__(self,*exc):return False

def execute_phase(run,state,task,unsafe=False,live=True,lock=None):
    """One PLAN, IMPLEMENT or REVIEW phase. `lock` guards the shared state when phases run in parallel."""
    cfg=run.cfg;b=run.base;lock=lock or NoLock()
    with lock:
        ts=state['tasks'][task];phase=ts['phase'];cycle=ts['cycle'];recovery=ts['recovery']
    w=run.place(task,phase)[0]
    label=f'{task}-{phase}-{cycle}-attempt{recovery}'
    hand=w/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
    if run.container:ensure_container(run)
    ensure_local_git(w)
    ok,reason=protected_ok(w)
    if not ok:raise RuntimeError('Workspace already changed protected file before phase: '+reason)
    archive_handoff(run,hand,label)
    # checkpoint before any agent process, survives power loss
    write(inflight_path(run,task),{'task':task,'phase':phase,'cycle':cycle,'recovery':recovery,'started':now()})
    print(f'START {label} (cwd={w})',flush=True)
    r=agent_call(run,task,phase,cycle,label,unsafe,live)
    with lock:
        hand_ok,reason=handoff_valid(hand,task,phase,cycle)
        intact,integrity_error=protected_ok(w)
        if not intact:reason='Protected benchmark spec modified: '+integrity_error
        chk=external_checks(w,task,phase,cfg['benchmark_test_timeout_seconds']) if hand_ok and intact and r['exit_code']==0 else {'exit_code':1,'output':'not run'}
        failure=error_class(r,hand_ok,reason,intact,chk)
        u=usage(run.cli,r['output']);record_usage(state,u);state['spent_seconds']+=r['seconds']
        ev={'task':task,'phase':phase,'cycle':cycle,'recovery':recovery,'exit_code':r['exit_code'],'seconds':r['seconds'],'handoff_valid':hand_ok,'handoff_error':reason,'external_check_exit':chk['exit_code'],'external_check_tail':chk['output'][-1200:],'usage':u,'passed':failure is None,'failure_class':failure,'timestamp':now()}
        ts['history'].append(ev);state['events'].append(ev)
        # Always capture agent edits in local git, even for failure; crucial for recovery diagnosis.
        ensure_local_git(w)
        if not intact:restore_protected(w)
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
                if read(hand)['verdict']=='PASS':
                    # A parallel task only counts as done once it is merged into the main line.
                    if run.track=='parallel':ts['phase']='merge'
                    else:ts['status']='DONE';ts['phase']='complete'
                elif cycle<cfg['max_cycles']:ts['cycle']+=1;ts['phase']='plan'
                else:ts['status']='BLOCKED';ts['blocked_reason']='REVIEW_GAPS: max cycles reached'
            print('FINISHED',label, '=>',ts['status'],ts['phase'],flush=True)
    return True

# --- parallel track ----------------------------------------------------------

def start_worker(run,task,ts):
    """Give a task its private checkout: a local clone of the main line as it is right now."""
    d=run.workers_dir/task
    if d.exists():return d
    run.workers_dir.mkdir(parents=True,exist_ok=True)
    tmp=d.with_name(d.name+'.tmp');shutil.rmtree(tmp,ignore_errors=True)
    git(run.base,'clone','-q',str(run.workspace),str(tmp))
    git(tmp,'remote','remove','origin')
    git(tmp,'config','user.name',run.cfg['git_author_name'])
    git(tmp,'config','user.email',run.cfg['git_author_email'])
    os.replace(tmp,d)
    ts['base_commit']=git(d,'rev-parse','HEAD')
    return d

def conflict_markers(w,files):
    bad=[]
    for f in files:
        p=pathlib.Path(w)/f
        if p.is_file() and re.search(r'^(<{7}|>{7}) ',p.read_text(encoding='utf-8',errors='replace'),re.M):bad.append(f)
    return bad

def reset_main(w,commit='HEAD'):
    """Drop an unfinished merge and everything it left behind (ignored files such as build output stay)."""
    subprocess.run(['git','merge','--abort'],cwd=w,capture_output=True)
    git(w,'reset','-q','--hard',commit);git(w,'clean','-fdq')

def execute_merge(run,state,task,unsafe=False,live=True,lock=None):
    """Merge a reviewed task into the main line. Git does it alone when it can; on a conflict one
    agent call has to resolve it, which is counted and timed like any other phase."""
    cfg=run.cfg;w=run.workspace;src=run.workers_dir/task;lock=lock or NoLock()
    with lock:
        ts=state['tasks'][task];cycle=ts['cycle'];recovery=ts['recovery']
    label=f'{task}-merge-{cycle}-attempt{recovery}'
    hand=w/'tasks'/task/'handoffs'/f'merge-cycle{cycle}.json'
    reset_main(w);before=git(w,'rev-parse','HEAD')
    git(w,'fetch','-q',str(src),'HEAD');theirs=git(w,'rev-parse','FETCH_HEAD')
    m=subprocess.run(['git','merge','--no-ff','--no-commit','FETCH_HEAD'],cwd=w,text=True,capture_output=True)
    files=git(w,'diff','--name-only','--diff-filter=U').splitlines()
    rec={'task':task,'base_commit':ts.get('base_commit'),'task_commit':theirs,'main_moved':ts.get('base_commit')!=before,
         'conflict':bool(files),'conflict_files':files,'attempts':recovery+1}
    failure=reason=None
    if files:
        print(f'MERGE {task}: conflict in {", ".join(files)}; asking the agent to resolve it',flush=True)
        if run.container:ensure_container(run)
        archive_handoff(run,hand,label)
        write(inflight_path(run,task),{'task':task,'phase':'merge','cycle':cycle,'recovery':recovery,'started':now()})
        r=agent_call(run,task,'merge',cycle,label,unsafe,live,files)
    elif m.returncode:
        failure='MERGE_ERROR';reason=(m.stderr or m.stdout)[-400:]
    with lock:
        if files:
            hand_ok,reason=handoff_valid(hand,task,'merge',cycle)
            intact,integrity_error=protected_ok(w)
            if not intact:reason='Protected benchmark spec modified: '+integrity_error
            left=conflict_markers(w,files) if hand_ok and intact else []
            failure=error_class(r,hand_ok,reason,intact,{'exit_code':0})
            if not failure and left:failure='MERGE_UNRESOLVED';reason='conflict markers left in '+', '.join(left)
            u=usage(run.cli,r['output']);record_usage(state,u);state['spent_seconds']+=r['seconds']
            ev={'task':task,'phase':'merge','cycle':cycle,'recovery':recovery,'exit_code':r['exit_code'],'seconds':r['seconds'],'handoff_valid':hand_ok,'handoff_error':reason,'external_check_exit':None,'external_check_tail':'','usage':u,'passed':failure is None,'failure_class':failure,'timestamp':now()}
            ts['history'].append(ev);state['events'].append(ev)
        if not failure:
            git(w,'add','-A')
            git(w,'commit','--allow-empty','-qm',f'{task} merge'+(' (conflicts resolved by agent)' if files else ''))
            # The agent must not have backed out of the merge instead of resolving it.
            if subprocess.run(['git','merge-base','--is-ancestor',theirs,'HEAD'],cwd=w).returncode:
                failure='MERGE_UNRESOLVED';reason='the merge was abandoned instead of resolved'
                if files:ev['passed']=False;ev['failure_class']=failure;ev['handoff_error']=reason
        if failure:
            reset_main(w,before)
            if ts['recovery']<cfg['recovery_attempts']:
                ts['recovery']+=1;print('RECOVERY pending',label,failure,reason,flush=True);return True
            ts['status']='BLOCKED';ts['blocked_reason']=f'{failure}: {reason}'
            state.setdefault('merges',[]).append({**rec,'merged':False,'timestamp':now()})
            print('BLOCKED',label,ts['blocked_reason'],flush=True);return True
        commit=git(w,'rev-parse','HEAD')
        if files:ev['commit']=commit
        ts.update(status='DONE',phase='complete',recovery=0,merge_commit=commit);ts.pop('blocked_reason',None)
        state.setdefault('merges',[]).append({**rec,'merged':True,'commit':commit,'timestamp':now()})
        shutil.rmtree(src,ignore_errors=True)
        print(f'MERGED {task}'+(' after conflict resolution' if files else ' without conflicts'),flush=True)
    return True

def parallel_jobs(state,running,slots):
    """Which tasks get a free worker now. Fixed order, decided by the harness: merges first (one at a
    time, they all write to the main line), then started tasks, then the lowest ready task IDs."""
    tasks=state['tasks'];merging=any(tasks[k]['phase']=='merge' for k in running);out=[]
    for k in sorted((k for k in ready(state) if k not in running),key=lambda k:(tasks[k]['phase']!='merge',tasks[k]['status']!='ACTIVE',k)):
        if len(out)>=slots:break
        if tasks[k]['phase']=='merge':
            if merging:continue
            merging=True
        out.append(k)
    return out

def budget_reached(state,cfg):
    if state['spent_seconds']>=cfg['max_run_seconds']:return 'time budget exceeded'
    if cfg['max_cost_usd'] is not None and (not state['cost_complete'] or state['reported_cost_usd']>=cfg['max_cost_usd']):return 'cost budget reached/unknown'
    if cfg['max_tokens'] is not None and (not state['tokens_complete'] or state['reported_tokens']>=cfg['max_tokens']):return 'token budget reached/unknown'
    return None

def run_parallel(run,state,max_phases=None,no_eval=False,unsafe=False,live=True):
    """Keep up to `run.workers` agents busy. Every job is one phase or one merge of one task.

    Hidden evaluations run beside the workers, one at a time, and never take a worker slot."""
    from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
    cfg=run.cfg;lock=threading.Lock();running={};n=0
    began=time.monotonic();earlier=state.get('elapsed_seconds',0);state.setdefault('merges',[])
    STOP.clear();reset_main(run.workspace)
    for f in run.base.glob('inflight-*.json'):
        print('WARNING: prior interrupted phase:',read(f));f.unlink()
    def job(task):
        with lock:
            merge=state['tasks'][task]['phase']=='merge'
            if not merge:start_worker(run,task,state['tasks'][task])
        (execute_merge if merge else execute_phase)(run,state,task,unsafe,live,lock)
        with lock:write(run.state,state)
        inflight_path(run,task).unlink(missing_ok=True)
    def score(task,commit,done):
        if evaluate_run(run,state,task,commit,done) is None:print('NOTE: hidden evaluation skipped, evaluation repository not found',flush=True)
        with lock:write(run.state,state)
    pool=ThreadPoolExecutor(run.workers);scorer=ThreadPoolExecutor(1)
    try:
        while True:
            with lock:
                stop=budget_reached(state,cfg)
                free=run.workers-len(running)
                if max_phases is not None:free=min(free,max_phases-n)
                new=[] if stop else parallel_jobs(state,running.values(),free)
            for task in new:running[pool.submit(job,task)]=task
            n+=len(new)
            if not running:
                if stop:print(stop)
                break
            for f in wait(running,return_when=FIRST_COMPLETED)[0]:
                task=running.pop(f);f.result()
                with lock:
                    state['elapsed_seconds']=round(earlier+time.monotonic()-began,2)
                    ts=state['tasks'][task]
                    if ts['status']=='DONE' and not no_eval and eval_dir(cfg):
                        done=[k for k,v in state['tasks'].items() if v['status']=='DONE']
                        scorer.submit(score,task,ts['merge_commit'],done)
                    write(run.state,state)
    except BaseException:
        STOP.set()
        if run.container:stop_container(run)
        pool.shutdown(wait=True,cancel_futures=True);scorer.shutdown(wait=False,cancel_futures=True)
        raise
    pool.shutdown();scorer.shutdown(wait=True)
    with lock:write(run.state,state)

def choose_ready(state):
    """Deterministic order: finish started tasks first, then the lowest ready task ID.

    The harness decides, not the model, so every profile works through the same sequence."""
    ids=ready(state)
    active=sorted(k for k in ids if state['tasks'][k]['status']=='ACTIVE')
    if active:return active[0]
    pending=sorted(k for k in ids if state['tasks'][k]['status']=='PENDING')
    return pending[0] if pending else None

def total(events,key):
    """Sum a usage field over all phases; None as soon as one phase did not report it."""
    values=[e['usage'].get(key) for e in events]
    return None if any(v is None for v in values) else sum(values)

def summarize(meta,state):
    """Comparable figures for one run, derived only from run.json and state.json."""
    tasks=state['tasks'];events=state['events']
    counts={x:sum(v['status']==x for v in tasks.values()) for x in ('PENDING','ACTIVE','DONE','BLOCKED')}
    classes={k:sum(e.get('failure_class')==k for e in events) for k in sorted({e.get('failure_class') for e in events if e.get('failure_class')})}
    done=[t for t in tasks.values() if t['status']=='DONE']
    cost=total(events,'cost_usd')
    merges=state.get('merges',[]);spent=state['spent_seconds'];elapsed=state.get('elapsed_seconds',spent)
    parallel={'workers':meta.get('workers',1),'elapsed_seconds':round(elapsed,2),
              # Agent seconds per elapsed second: how many agents were busy on average.
              'parallelism':round(spent/elapsed,2) if elapsed else None,
              'merges':sum(m['merged'] for m in merges),'merge_conflicts':sum(m['conflict'] for m in merges),
              'merge_conflict_files':sum(len(m['conflict_files']) for m in merges),
              'merges_failed':sum(not m['merged'] for m in merges),
              'merge_agent_seconds':round(sum(e.get('seconds',0) for e in events if e.get('phase')=='merge'),2)}
    return {**parallel,'benchmark_version':meta['benchmark_version'],'profile':meta['profile'],'track':meta['track'],'run_id':meta['run_id'],
            'cli':meta['cli'],'cli_version':meta['cli_version'],'model':meta['model'],
            'reported_models':sorted({e['usage'].get('reported_model') for e in events if e['usage'].get('reported_model')}),
            'isolation':meta.get('isolation','host'),'harness_commit':meta['harness_commit'],'host':meta['host'],'created':meta['created'],
            'finished':counts['PENDING']+counts['ACTIVE']==0 or not ready(state),
            'tasks_total':len(tasks),'status_counts':counts,'completed_ratio':round(counts['DONE']/len(tasks),4),
            'first_cycle_pass_ratio':round(sum(t['cycle']==1 for t in done)/len(done),4) if done else None,
            'phases_attempted':len(events),'phases_failed':sum(1 for e in events if e.get('failure_class')),'failure_classes':classes,
            'operator_interventions':len(state.get('interventions',[])),
            'evaluation':next((e for e in reversed(state.get('evaluations',[])) if 'error' not in e),None),
            'evaluations_failed':sum('error' in e for e in state.get('evaluations',[])),
            'reported_total_tokens':total(events,'tokens'),**{'reported_'+k:total(events,k) for k in TOKEN_KINDS},
            'reported_total_cost_usd':None if cost is None else round(cost,4),
            'wall_seconds_agent_calls':round(state['spent_seconds'],2),
            'unreported_usage_warning':total(events,'tokens') is None or cost is None}

def report(run):
    st=read(run.state);result=summarize(read(run.meta),st);result['tasks']=st['tasks']
    manual=run.base/'manual-review.json'
    if manual.exists():result['manual_review']=read(manual)
    write(run.base/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('tasks','host')},indent=2))
    return result

# --- hidden evaluation -------------------------------------------------------

EVAL_PREP=('cd /workspace; for s in setup build; do '
           'if [ -x ./$s.sh ]; then timeout -k 10 1800 ./$s.sh >/out/$s.log 2>&1; echo $? >/out/$s.exit; '
           'else echo 127 >/out/$s.exit; fi; done')

def eval_dir(cfg):
    """The private evaluation repository, or None when it is not available on this machine."""
    path=(cfg.get('eval') or {}).get('path')
    if not path:return None
    p=pathlib.Path(path).expanduser()
    p=(p if p.is_absolute() else ROOT/p).resolve()
    return p if (p/'evaluate.py').is_file() else None

def repo_commit(path):
    try:return git(path,'rev-parse','HEAD')+('-dirty' if git(path,'status','--porcelain') else '')
    except Exception:return None

def evaluation_commands(cfg,name,image,product,out,ed,done):
    """Two containers: (1) setup and build with network but without the tests;
    (2) the tests, mounted read-only, with no network, so product code can never leak them."""
    rt=runtime(cfg);t=cfg['eval']['timeout_seconds'];mounts=['-v',f'{product}:{CONTAINER_WS}','-v',f'{out}:/out']
    prep=[rt,'run','--name',name,'--network','pasta:--map-guest-addr,none',*mounts,cfg['container']['image'],'bash','-c',EVAL_PREP]
    test=[rt,'run','--rm','--name',name,'--network','none',*mounts,'-v',f'{ed}:/eval:ro',image,
          'timeout','-k','10',str(t),'python3','/eval/evaluate.py','--product',CONTAINER_WS,'--out','/out/result.json',
          '--done',','.join(sorted(done)),'--prep','/out']
    return prep,test

def evaluate_run(run,state,label,commit='HEAD',done=None):
    """Score a committed workspace state with the hidden suite. The result is stored with the run
    and never shown to the agent. Returns the record, or None when no evaluation repository exists."""
    cfg=run.cfg;ed=eval_dir(cfg)
    if not ed:return None
    rt=runtime(cfg);t=cfg['eval']['timeout_seconds'];start=time.monotonic()
    if done is None:done=[k for k,v in state['tasks'].items() if v['status']=='DONE']
    work=run.base/'eval'/label;shutil.rmtree(work,ignore_errors=True)
    product=work/'product';out=work/'out';product.mkdir(parents=True);out.mkdir()
    name='evo-eval-'+container_name(run)[4:]+'-'+label.lower();image=name+'-img'
    record={'label':label,'commit':git(run.workspace,'rev-parse',commit),'eval_commit':repo_commit(ed),'done_tasks':len(done),'timestamp':now()}
    print(f'EVALUATE {label} (hidden suite, result not shown to the agent)',flush=True)
    try:
        tar=subprocess.run(['git','archive','--format=tar',commit],cwd=run.workspace,capture_output=True,check=True).stdout
        subprocess.run(['tar','-x','-C',str(product)],input=tar,check=True)
        prep,test=evaluation_commands(cfg,name,image,product,out,ed,done)
        subprocess.run([rt,'rm','-f',name],capture_output=True)
        cmd(prep,work,t,logfile=work/'prep.log')
        subprocess.run([rt,'stop','-t','0',name],capture_output=True)
        subprocess.run([rt,'commit','-q',name,image],check=True,capture_output=True)
        subprocess.run([rt,'rm','-f',name],capture_output=True)
        cmd(test,work,t+60,logfile=work/'eval.log')
        result=read(out/'result.json')
        write(run.base/'eval'/f'{label}.json',{**record,**result})
        record.update({k:result[k] for k in ('eval_version','passed','due','total','categories','metrics')})
    except Exception as e:
        record['error']=f'{type(e).__name__}: {e}'[:400]
    finally:
        subprocess.run([rt,'rm','-f',name],capture_output=True)
        subprocess.run([rt,'rmi','-f',image],capture_output=True)
        shutil.rmtree(product,ignore_errors=True)
    record['seconds']=round(time.monotonic()-start,1)
    state['evaluations']=[e for e in state.get('evaluations',[]) if e['label']!=label]+[record]
    print(f'EVALUATED {label}: '+(record.get('error') or f'{record["passed"]}/{record["due"]} due checks passed'),flush=True)
    return record

# --- comparison --------------------------------------------------------------

def all_runs(cfg):
    rows=[]
    for meta in sorted(runs_root(cfg).glob('*/*/*/run.json')):
        state=meta.with_name('state.json')
        if state.exists():rows.append(summarize(read(meta),read(state)))
    return rows

def fmt_count(v):
    if v is None:return '—'
    for limit,suffix in ((1e9,'B'),(1e6,'M'),(1e3,'k')):
        if v>=limit:return f'{v/limit:.1f}{suffix}'
    return str(int(v)) if float(v).is_integer() else f'{v:.1f}'

def fmt_time(v):
    if v is None:return '—'
    m,s=divmod(int(round(v)),60);h,m=divmod(m,60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'

def label(category):return 'UI' if category=='ui' else category.capitalize()
def fmt_cost(v):return '—' if v is None else f'${v:.2f}'
def fmt_pct(v):return '—' if v is None else f'{v*100:.0f}%'

def median(values):
    import statistics
    return None if not values or any(v is None for v in values) else statistics.median(values)

def table(header,rows):
    lines=['| '+' | '.join(header)+' |','|'+'|'.join('---' for _ in header)+'|']
    return '\n'.join(lines+['| '+' | '.join(str(c) for c in r)+' |' for r in rows])

def comparison_markdown(rows):
    """Speed and cost are separate columns and never folded into a quality figure."""
    if not rows:return '# Benchmark comparison\n\nNo runs found.\n'
    groups={}
    for r in rows:groups.setdefault((r['track'],r['profile']),[]).append(r)
    out=['# Benchmark comparison','',f'{len(rows)} run(s), {len(groups)} profile/track combination(s). '
         '"—" means the CLI did not report the value; it is never counted as zero. '
         'With more than one run, the summary shows the median.','','## Summary by profile and track','']
    out.append(table(['Track','Profile','Model','Runs','Tasks done','First-cycle pass','Failed phases','Agent time','Fresh input','Cached input','Output','Cost'],
        [[track,profile,g[0]['model'] or 'CLI default',len(g),fmt_pct(median([r['completed_ratio'] for r in g])),fmt_pct(median([r['first_cycle_pass_ratio'] for r in g])),
          fmt_count(median([r['phases_failed'] for r in g])),fmt_time(median([r['wall_seconds_agent_calls'] for r in g])),
          fmt_count(median([r['reported_input_tokens'] for r in g])),fmt_count(median([r['reported_cached_input_tokens'] for r in g])),
          fmt_count(median([r['reported_output_tokens'] for r in g])),fmt_cost(median([r['reported_total_cost_usd'] for r in g]))]
         for (track,profile),g in sorted(groups.items())]))
    scored=[r for r in rows if r['evaluation']]
    if scored:
        cats=list(scored[0]['evaluation']['categories'])
        out+=['','## Hidden test results','','Checks passed out of all checks in the suite, from the latest evaluation of each run. '
              'Checks belonging to tasks that are not done yet count as not passed. Speed is measured by the suite at about 2,000 individuals.','']
        out.append(table(['Track','Profile','Run','Evaluated after','All checks']+[label(c) for c in cats]+['Ticks/s'],
            [[r['track'],r['profile'],r['run_id'],r['evaluation']['label'],f"{r['evaluation']['passed']}/{r['evaluation']['total']}"]
             +[f"{r['evaluation']['categories'][c]['passed']}/{r['evaluation']['categories'][c]['total']}" if c in r['evaluation']['categories'] else '—' for c in cats]
             +[r['evaluation']['metrics'].get('ticks_per_second','—')] for r in scored]))
    par=[r for r in rows if r['track']=='parallel']
    if par:
        seq={}
        for r in rows:
            if r['track']=='sequential' and r['finished']:seq.setdefault(r['profile'],[]).append(r['wall_seconds_agent_calls'])
        def speedup(r):
            base=median(seq.get(r['profile'],[]))
            return f"{base/r['elapsed_seconds']:.2f}×" if base and r['finished'] and r['elapsed_seconds'] else '—'
        out+=['','## Parallel track','','Several agents work on independent tasks at the same time, each in a private checkout that is merged when its review passes. '
              '"Elapsed" is wall-clock time of the run without the hidden evaluations; "Agent time" is the sum over all agent calls. '
              '"Busy agents" is agent time divided by elapsed time. "Speed-up" compares elapsed time with the agent time of the finished sequential run(s) of the same profile. '
              'A conflict is a merge Git could not do alone; the model then has to resolve it in one extra call, and a merge it cannot resolve blocks the task.','']
        out.append(table(['Profile','Run','Workers','Elapsed','Agent time','Busy agents','Speed-up','Merges','Conflicts','Conflicting files','Failed merges','Conflict resolution time'],
            [[r['profile'],r['run_id'],r['workers'],fmt_time(r['elapsed_seconds']),fmt_time(r['wall_seconds_agent_calls']),r['parallelism'] if r['parallelism'] is not None else '—',speedup(r),
              r['merges'],r['merge_conflicts'],r['merge_conflict_files'],r['merges_failed'],fmt_time(r['merge_agent_seconds'])] for r in par]))
    out+=['','## Every run','']
    out.append(table(['Track','Profile','Run','State','Done','Blocked','Phases','Failed','Interventions','Agent time','Tokens','Cost','Reported model','CLI','Isolation','Harness'],
        [[r['track'],r['profile'],r['run_id'],'finished' if r['finished'] else 'in progress',f"{r['status_counts']['DONE']}/{r['tasks_total']}",r['status_counts']['BLOCKED'],
          r['phases_attempted'],r['phases_failed'],r['operator_interventions'],fmt_time(r['wall_seconds_agent_calls']),fmt_count(r['reported_total_tokens']),fmt_cost(r['reported_total_cost_usd']),
          ', '.join(r['reported_models']) or '—',r['cli_version'] or r['cli'],r['isolation'],(r['harness_commit'] or '—')[:7]+('*' if (r['harness_commit'] or '').endswith('-dirty') else '')]
         for r in rows]))
    notes=[]
    if any((r['harness_commit'] or '').endswith('-dirty') for r in rows):notes.append('`*` harness had uncommitted changes when the run started.')
    if len({(r['harness_commit'] or '').replace('-dirty','') for r in rows})>1:notes.append('Runs used different harness commits; compare with care.')
    if len({r['benchmark_version'] for r in rows})>1:notes.append('Runs used different benchmark versions and are not directly comparable.')
    if len({json.dumps(r['host'],sort_keys=True) for r in rows})>1:notes.append('Runs were made on different hosts; times are not directly comparable.')
    if len({r['isolation'] for r in rows})>1:notes.append('Runs mix container and host isolation; the environments differ.')
    if len({(r['evaluation'].get('eval_version'),r['evaluation'].get('eval_commit')) for r in rows if r['evaluation']})>1:notes.append('Runs were scored with different versions of the hidden suite; re-run `evaluate` before comparing test results.')
    if any(r['evaluations_failed'] for r in rows):notes.append('Some evaluations could not be completed; see the run folders.')
    if any(not r['finished'] for r in rows):notes.append('Unfinished runs are included; their figures are partial.')
    if any(r['operator_interventions'] for r in rows):notes.append('Some runs had operator interventions (`unblock`).')
    if notes:out+=['','## Notes','']+['- '+n for n in notes]
    return '\n'.join(out)+'\n'

def compare(cfg,out_dir=None):
    rows=all_runs(cfg);out=pathlib.Path(out_dir).expanduser() if out_dir else runs_root(cfg)
    md=comparison_markdown(rows);out.mkdir(parents=True,exist_ok=True)
    (out/'comparison.md').write_text(md,encoding='utf-8')
    write(out/'comparison.json',{'generated':now(),'runs':rows})
    print(md);print(f'Written: {out/"comparison.md"} and {out/"comparison.json"}')
    return rows

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
    print('evaluation repository:',eval_dir(cfg) or 'NOT FOUND (runs will not be scored)')
    print('profiles:')
    for name in sorted(cfg['profiles']):
        p=resolve_profile(cfg,name)
        print(f'  {name}: cli={p["cli"]} model={p["model"] or "(CLI default)"} phase_timeout={p["phase_timeout_seconds"]}s parallel_workers={p.get("workers") or 1}')

def main():
    cfg=config()
    p=argparse.ArgumentParser(description=f'Evolution Agent Benchmark v{BENCHMARK_VERSION}')
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('doctor','build-image','compare','publish','init','run','evaluate','package','report','unblock'):
        q=sub.add_parser(name)
        if name=='compare':q.add_argument('--out',help='folder for comparison.md and comparison.json (default: runs root)')
        if name=='publish':q.add_argument('--dry-run',action='store_true',help='show the git and gh commands without running them')
        if name not in ('doctor','build-image','compare','publish'):
            q.add_argument('--profile',choices=sorted(cfg['profiles']),required=True,help='named CLI + model combination from benchmark.json')
            q.add_argument('--track',choices=TRACKS,default='sequential')
            q.add_argument('--run-id',default='r1',help='distinguishes repeated runs of the same profile and track')
        if name in ('init','run'):
            q.add_argument('--no-container',action='store_true',help='run the agent directly on the host instead of in the sandbox container')
            q.add_argument('--workers',type=int,help='parallel track: agents working at the same time (default: "workers" of the profile); fixed for the whole run')
        if name=='run':
            q.add_argument('--no-eval',action='store_true',help='skip the hidden evaluation after each completed task')
            q.add_argument('--refresh-login',action='store_true',help='copy the host CLI login into the run again')
            q.add_argument('--allow-unsafe',action='store_true',help='host mode only: let the CLI skip its permission prompts');q.add_argument('--dry-run',action='store_true');q.add_argument('--max-phases',type=int);q.add_argument('--quiet',action='store_true')
        if name=='unblock':q.add_argument('--task',required=True);q.add_argument('--phase',choices=PHASES+('merge',));q.add_argument('--cycle',type=int)
    a=p.parse_args()
    if a.action=='doctor':doctor(cfg);return
    if a.action=='build-image':sys.exit(build_image(cfg))
    if a.action=='compare':compare(cfg,a.out);return
    if a.action=='publish':
        from . import publish as pub
        pub.publish(cfg,a.dry_run);return
    run=Run(a.profile,a.track,a.run_id,cfg,container=not getattr(a,'no_container',False),workers=getattr(a,'workers',None))
    if a.action=='run' and a.dry_run:
        st=read(run.state) if run.state.exists() else initial_state()
        tasks=parallel_jobs(st,(),run.workers) if run.track=='parallel' else [t for t in [choose_ready(st)] if t]
        if run.track=='parallel':print('DRY RUN parallel track,',run.workers,'worker(s)')
        for task in tasks:
            ts=st['tasks'][task];print('DRY RUN',task,ts['phase'],'cycle',ts['cycle'])
            if ts['phase']=='merge':print('git merge of the task checkout; an agent is called only on a conflict')
            else:print(' '.join(phase_argv(run,task,ts['phase'],ts['cycle'],a.allow_unsafe)))
        if tasks and run.container:print('container:',' '.join(container_create_argv(run)))
        return
    if a.action=='init':print('Workspace:',init(run));return
    if a.action=='report':report(run);return
    if a.action=='package':
        from . import publish as pub
        with lock_run(run):pub.package(run)
        return
    if a.action=='evaluate':
        if not eval_dir(cfg):p.error('evaluation repository not found (see "eval" in benchmark.json)')
        with lock_run(run):
            st=read(run.state);evaluate_run(run,st,'final');write(run.state,st)
        report(run);return
    if a.action=='unblock':
        st=read(run.state);ts=st['tasks'][a.task]
        if ts['status']!='BLOCKED':raise RuntimeError('Task is not BLOCKED')
        ts['status']='ACTIVE';ts['recovery']=0;ts.pop('blocked_reason',None)
        if a.phase:ts['phase']=a.phase
        if a.cycle:ts['cycle']=a.cycle
        st.setdefault('interventions',[]).append({'action':'unblock','task':a.task,'phase':ts['phase'],'cycle':ts['cycle'],'timestamp':now()})
        write(run.state,st);print('Unblocked',a.task,ts['phase'],ts['cycle']);return
    with lock_run(run):
        b=run.base;w=run.workspace
        if not run.state.exists():init(run)
        check_unchanged(run)
        if not shutil.which(run.profile['executable']):p.error('CLI missing')
        if run.container and a.refresh_login:copy_logins(run,True)
        ensure_local_git(w)
        if run.track=='parallel':
            st=read(run.state)
            try:run_parallel(run,st,a.max_phases,a.no_eval,a.allow_unsafe,not a.quiet)
            finally:
                if run.container:stop_container(run)
            report(run);return
        if (b/'inflight.json').exists():
            print('WARNING: prior interrupted phase:',read(b/'inflight.json'))
            (b/'inflight.json').unlink()
        st=read(run.state);n=0;n_warned=[]
        while True:
            if a.max_phases is not None and n>=a.max_phases:break
            stop=budget_reached(st,cfg)
            if stop:print(stop);break
            task=choose_ready(st)
            if not task:break
            try:execute_phase(run,st,task,a.allow_unsafe,not a.quiet)
            except BaseException:
                if run.container:stop_container(run)
                raise
            write(run.state,st);(b/'inflight.json').unlink(missing_ok=True);n+=1
            if st['tasks'][task]['status']=='DONE' and not a.no_eval:
                if evaluate_run(run,st,task) is None and not n_warned:
                    print('NOTE: hidden evaluation skipped, evaluation repository not found');n_warned.append(1)
                write(run.state,st)
        if run.container:stop_container(run)
        report(run)

if __name__=='__main__':main()
