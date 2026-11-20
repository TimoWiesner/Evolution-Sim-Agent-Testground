"""End-to-end harness test using a fake CLI; no provider credentials needed."""
import datetime as dt
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest.mock import patch
from harness import core

FAKE = '''#!/usr/bin/env python3
import json,os,pathlib,re,sys
prompt=sys.argv[-1]
match=re.search(r'Task (TASK-\\d+), phase (PLAN|IMPLEMENT|REVIEW|MERGE), cycle (\\d+)',prompt)
if match:
 task,phase,cycle=match.groups();phase=phase.lower();cycle=int(cycle)
 path=pathlib.Path.cwd()/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
 if os.getenv('FAKE_MISSING')!='1':
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps({'task_id':task,'phase':phase,'cycle':cycle,'summary':'completed','changed_files':[],'decisions':[],'tests':[],'risks':[],'next_steps':[],'verdict':'PASS' if phase=='review' else 'N/A','gaps':[]}))
  state=pathlib.Path.cwd()/'docs'/'STATE.md'
  if phase=='merge':
   if os.getenv('FAKE_BAD_MERGE')!='1':state.write_text('merged\\n')
  elif os.getenv('FAKE_CONFLICT')=='1' and phase=='implement':state.write_text(task+'\\n')
  else:state.write_text(state.read_text() if os.getenv('FAKE_CONFLICT')=='1' else 'updated\\n')
  if phase=='implement':(pathlib.Path.cwd()/(task+'.txt')).write_text(task)
if os.getenv('FAKE_LEFTOVER')=='1':
 pathlib.Path('leftover.txt').write_text('x');(pathlib.Path.cwd()/'docs'/'STATE.md').write_text('half done\\n')
if os.getenv('FAKE_OUTAGE')=='1':print(json.dumps({'type':'error','error':{'message':'fetch failed: ECONNREFUSED'}}),flush=True);sys.exit(1)
if os.getenv('FAKE_AUTH')=='1':print(json.dumps({'type':'error','error':{'message':'401 Unauthorized'}}),flush=True);sys.exit(1)
if os.getenv('FAKE_LIMIT')=='1':print(json.dumps({'type':'error','error':{'message':'429 Too Many Requests: usage limit reached'}}),flush=True);sys.exit(1)
print(json.dumps({'type':'step_finish','part':{'tokens':{'input':10,'output':5},'cost':0.01}}),flush=True)
'''

class Base(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=pathlib.Path(self.tmp.name)/'bench'
  shutil.copytree(core.ROOT,self.root,ignore=shutil.ignore_patterns('runs','__pycache__','.git'))
  fake=self.root/'fakeagent';fake.write_text(FAKE);fake.chmod(0o755)
  cfg=core.read(self.root/'benchmark.json')
  cfg['runs_root']=str(pathlib.Path(self.tmp.name)/'runs')
  cfg['clis']['opencode']['executable']=str(fake)
  cfg['eval']={'path':None,'timeout_seconds':60}
  cfg['profiles']={'fake':{'cli':'opencode','model':'fake/model-a'}}
  core.write(self.root/'benchmark.json',cfg)
  self.patcher=patch.object(core,'ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
  self.run_=core.Run('fake');self.w=core.init(self.run_);self.s=core.initial_state()

class Integration(Base):
 def phase(self):
  return core.execute_phase(self.run_,self.s,'TASK-001',live=False)
 def test_three_phases_and_local_git(self):
  for _ in core.PHASES:
   self.assertTrue(self.phase())
  self.assertEqual(self.s['tasks']['TASK-001']['status'],'DONE')
  self.assertEqual(len(core.git(self.w,'log','--format=%H').splitlines()),4)
  self.assertEqual(core.git(self.w,'remote'),'')
  self.assertTrue(core.protected_ok(self.w)[0])
  self.assertEqual(self.s['reported_tokens'],45)
 def test_changed_contract_is_restored(self):
  c=self.w/'docs/CONTRACT.md';original=c.read_text();c.write_text('weakened')
  self.assertFalse(core.protected_ok(self.w)[0])
  (self.w/'.git/index.lock').write_text('');core.git(self.w,'remote','add','origin','https://example.invalid/x.git')
  self.assertTrue(self.phase())
  self.assertEqual(c.read_text(),original);self.assertEqual(core.git(self.w,'remote'),'')
  ev=self.s['events'][0];self.assertEqual(len(ev['repairs']),3);self.assertTrue(ev['passed'] and ev['commit'])
 def test_failed_commit_does_not_end_the_run(self):
  real=core.git
  def broken(w,*args,**k):
   if args[0]=='commit':raise RuntimeError('disk full')
   return real(w,*args,**k)
  with patch.object(core,'git',broken):self.assertTrue(self.phase())
  ev=self.s['events'][0];self.assertIsNone(ev['commit']);self.assertIn('disk full',ev['commit_error'])
  self.assertTrue(self.phase());self.assertTrue(self.s['events'][1]['commit'])
 def test_missing_handoff_recovery_and_block(self):
  with patch.dict(os.environ,{'FAKE_MISSING':'1'}):
   self.phase()
   self.assertEqual(self.s['tasks']['TASK-001']['recovery'],1)
   self.phase()
  self.assertEqual(self.s['tasks']['TASK-001']['status'],'BLOCKED')
  self.assertIn('HANDOFF_INVALID',self.s['tasks']['TASK-001']['blocked_reason'])
 def test_rate_limit_is_not_a_model_failure(self):
  with patch.dict(os.environ,{'FAKE_LIMIT':'1','FAKE_MISSING':'1'}):
   self.phase();self.phase();self.phase()
  t=self.s['tasks']['TASK-001']
  self.assertEqual((t['status'],t['phase'],t['recovery'],self.s['events']),('PENDING','plan',0,[]))
  self.assertEqual(len(self.s['rate_limits']),3);self.assertTrue(self.s['paused_until'])
  self.assertFalse(core.wait_for_limit(self.s,self.run_.cfg,stop_on_limit=True))
  self.s['paused_until']=1
  with patch.object(core.time,'sleep') as sleep:self.assertTrue(core.wait_for_limit(self.s,self.run_.cfg))
  sleep.assert_called_once();self.assertIsNone(self.s['paused_until'])
  self.phase();self.assertEqual(t['phase'],'implement')
  out=json.dumps({'type':'rate_limit_event','rate_limit_info':{'status':'rejected','resetsAt':123}})
  self.assertEqual(core.rate_limited('claude',out),{'resets_at':123})
  self.assertIsNone(core.rate_limited('claude',out.replace('rejected','allowed_warning')))
 def test_codex_reset_time_is_read_from_the_message(self):
  utc=lambda *a:dt.datetime(*a,tzinfo=dt.timezone.utc).timestamp()
  now=utc(2026,11,20,10,57)
  msg='You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/settings/usage to purchase more credits or try again at 11:43 AM.'
  self.assertEqual(core.codex_reset(msg,now),utc(2026,11,20,11,43))
  self.assertEqual(core.codex_reset(msg.replace('11:43 AM','1:05 PM'),now),utc(2026,11,20,13,5))
  self.assertEqual(core.codex_reset(msg.replace('11:43 AM','9:00 AM'),now),utc(2026,11,21,9,0))
  self.assertEqual(core.codex_reset(msg.replace('11:43 AM','10:55 AM'),now),utc(2026,11,20,10,55))
  self.assertEqual(core.codex_reset(msg.replace('11:43 AM','Nov 23rd, 2026 3:00 PM'),now),utc(2026,11,23,15,0))
  self.assertEqual(core.codex_reset('Rate limit reached, try again in 2 hours 5 minutes',now),now+7500)
  self.assertIsNone(core.codex_reset('usage limit reached',now))
  out='\n'.join(json.dumps({'type':t,'message':msg},ensure_ascii=False) for t in ('error','turn.failed'))
  with patch.object(core.time,'time',return_value=now):
   self.assertEqual(core.rate_limited('codex',out),{'resets_at':utc(2026,11,20,11,43)})
  self.assertEqual(core.rate_limited('codex',json.dumps({'type':'error','message':'usage limit'})),{'resets_at':None})
 def test_outage_is_repeated_then_stops_the_run(self):
  with patch.dict(os.environ,{'FAKE_OUTAGE':'1','FAKE_MISSING':'1'}):
   for i in range(4):
    self.assertFalse(self.phase());self.assertEqual(self.s['pause_reason'],'infra');self.assertNotIn('halt',self.s)
    with patch.object(core.time,'sleep'):self.assertTrue(core.wait_for_limit(self.s,self.run_.cfg,stop_on_limit=True))
   self.assertFalse(self.phase())
  t=self.s['tasks']['TASK-001']
  self.assertEqual((t['status'],t['recovery'],self.s['events']),('PENDING',0,[]))
  self.assertEqual(len(self.s['infra_failures']),5);self.assertIn('halt',self.s)
  self.assertEqual(self.s['uncounted']['calls'],5)
  core.begin_invocation(self.s);self.assertNotIn('halt',self.s)
  self.assertTrue(self.phase());self.assertEqual(t['phase'],'implement');self.assertNotIn('infra_streak',self.s)
  self.assertEqual(core.summarize(core.read(self.run_.meta),self.s)['infra_failures'],5)
 def test_rejected_login_stops_the_run(self):
  with patch.dict(os.environ,{'FAKE_AUTH':'1','FAKE_MISSING':'1'}):self.assertFalse(self.phase())
  self.assertIn('login',self.s['halt']);self.assertEqual(self.s['events'],[])
 def test_dead_local_server_is_noticed_before_the_call(self):
  import socket
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.listen()
   self.assertEqual(core.ports_down({'host_ports':[port]}),[])
  self.run_.profile['host_ports']=[port]
  self.assertFalse(self.phase())
  self.assertEqual(self.s['infra_failures'][0]['kind'],'server');self.assertFalse((self.run_.base/'logs').exists())
 def test_outage_detection(self):
  r=lambda *events,**k:{'output':'\n'.join(json.dumps(e) for e in events),'aborted':None,**k}
  worked={'output_tokens':9};silent={'output_tokens':None}
  dead={'type':'result','terminal_reason':'api_error','api_error_status':None,'result':'Connection error'}
  self.assertEqual(core.infra_failure('claude',r(dead),silent)['kind'],'outage')
  self.assertEqual(core.infra_failure('claude',r({**dead,'api_error_status':529}),worked)['kind'],'outage')
  self.assertEqual(core.infra_failure('claude',r({**dead,'api_error_status':401}),worked)['kind'],'auth')
  self.assertIsNone(core.infra_failure('claude',r({**dead,'api_error_status':400}),worked))
  self.assertIsNone(core.infra_failure('claude',r({'type':'result','terminal_reason':'completed'}),worked))
  self.assertEqual(core.infra_failure('claude',r({'type':'result'}),silent)['kind'],'outage')
  early={'type':'error','message':'stream disconnected, retrying'};step={'type':'item.completed','item':{'type':'agent_message'}}
  self.assertIsNone(core.infra_failure('codex',r(early,step,step,step),worked))
  self.assertEqual(core.infra_failure('codex',r(step,early),worked)['kind'],'outage')
  self.assertEqual(core.infra_failure('opencode',{'output':'','aborted':'server gone'},worked)['kind'],'server')
 def test_repeated_call_keeps_every_log(self):
  with patch.dict(os.environ,{'FAKE_OUTAGE':'1','FAKE_MISSING':'1'}):self.phase()
  self.s['paused_until']=None;self.phase()
  self.assertEqual(sorted(p.name for p in (self.run_.base/'logs').iterdir()),['TASK-001-plan-1-attempt0.jsonl','TASK-001-plan-1-attempt0.try2.jsonl'])
 def test_interruption_is_recorded(self):
  core.write(self.run_.base/'inflight.json',{'task':'TASK-001','phase':'plan'})
  core.note_interruptions(self.run_,self.s)
  self.assertEqual(self.s['interruptions'][0]['task'],'TASK-001');self.assertFalse((self.run_.base/'inflight.json').exists())
  self.assertEqual(core.summarize(core.read(self.run_.meta),self.s)['interruptions'],1)
 def test_refused_call_leaves_nothing_behind(self):
  state=self.w/'docs/STATE.md';original=state.read_text()
  for kind in ('FAKE_LIMIT','FAKE_OUTAGE'):
   with patch.dict(os.environ,{kind:'1','FAKE_MISSING':'1','FAKE_LEFTOVER':'1'}):self.assertFalse(self.phase())
   self.assertFalse((self.w/'leftover.txt').exists());self.assertEqual(state.read_text(),original)
   self.assertEqual(core.git(self.w,'status','--porcelain'),'')
 def test_interrupted_phase_leaves_nothing_behind(self):
  head=core.git(self.w,'rev-parse','HEAD');(self.w/'leftover.txt').write_text('x')
  core.write(self.run_.base/'inflight.json',{'task':'TASK-001','phase':'plan','head':head})
  core.note_interruptions(self.run_,self.s)
  self.assertFalse((self.w/'leftover.txt').exists())
 def test_files_of_a_failed_commit_survive_a_refused_call(self):
  real=core.git
  def broken(w,*args,**k):
   if args[0]=='commit':raise RuntimeError('disk full')
   return real(w,*args,**k)
  with patch.object(core,'git',broken):self.assertTrue(self.phase())
  with patch.dict(os.environ,{'FAKE_LIMIT':'1','FAKE_MISSING':'1'}):self.assertFalse(self.phase())
  self.assertTrue((self.w/'tasks/TASK-001/handoffs/plan-cycle1.json').exists())
 def test_damaged_state_falls_back_to_the_previous_one(self):
  core.write(self.run_.state,{'n':1});core.write(self.run_.state,{'n':2})
  self.run_.state.write_text('{"n":')
  self.assertEqual(core.read_state(self.run_),{'n':1})
 def test_full_disk_stops_before_the_call(self):
  self.run_.cfg['min_free_disk_gb']=10**9
  self.assertFalse(self.phase());self.assertIn('GB free',self.s['halt']);self.assertEqual(self.s['events'],[])
 def test_done_tasks_without_a_score_are_found(self):
  for _ in core.PHASES:self.phase()
  todo=core.missing_evaluations(self.s)
  self.assertEqual([(t,d) for t,c,d in todo],[('TASK-001',['TASK-001'])]);self.assertEqual(todo[0][1],self.s['events'][-1]['commit'])
  self.s['evaluations']=[{'label':'TASK-001','error':'interrupted'}];self.assertEqual(len(core.missing_evaluations(self.s)),1)
  self.s['evaluations']=[{'label':'TASK-001','passed':1}];self.assertEqual(core.missing_evaluations(self.s),[])
 def test_generated_handoff_is_not_protected(self):
  hand=self.w/'tasks/TASK-001/handoffs/plan-cycle1.md'
  hand.parent.mkdir(exist_ok=True);hand.write_text('notes')
  self.assertTrue(core.protected_ok(self.w)[0])
 def test_repeated_run_archives_handoff(self):
  self.phase()
  self.s['tasks']['TASK-001']['phase']='plan'
  self.phase()
  self.assertEqual(len(list((self.run_.base/'handoff-archive').glob('*.json'))),1)
 def test_run_layout_and_metadata(self):
  self.assertEqual(self.run_.base,pathlib.Path(self.tmp.name)/'runs'/'fake'/'sequential'/'r1')
  meta=core.read(self.run_.meta)
  self.assertEqual((meta['profile'],meta['model'],meta['track'],meta['benchmark_version']),('fake','fake/model-a','sequential',1))
  self.assertIn('cpu_count',meta['host'])
 def test_separate_runs_do_not_collide(self):
  other=core.Run('fake',run_id='r2');core.init(other)
  self.assertNotEqual(other.workspace,self.w);self.assertTrue(other.state.exists())
 def test_changed_profile_is_rejected(self):
  core.check_unchanged(self.run_)
  cfg=core.read(self.root/'benchmark.json');cfg['profiles']['fake']['model']='fake/model-b'
  core.write(self.root/'benchmark.json',cfg)
  with self.assertRaises(RuntimeError):
   core.check_unchanged(core.Run('fake'))
 def test_runs_root_inside_repo_is_rejected(self):
  cfg=core.read(self.root/'benchmark.json');cfg['runs_root']=str(self.root/'runs')
  with self.assertRaises(RuntimeError):
   core.Run('fake',cfg=cfg)
 def test_report_names_profile_and_model(self):
  self.phase();core.write(self.run_.state,self.s)
  with patch('builtins.print'):
   r=core.report(self.run_)
  self.assertEqual((r['profile'],r['model'],r['phases_attempted']),('fake','fake/model-a',1))
 def test_compare_lists_runs_and_keeps_unknown_distinct(self):
  self.phase();core.write(self.run_.state,self.s)
  other=core.Run('fake',run_id='r2');core.init(other)
  with patch('builtins.print'):
   rows=core.compare(self.run_.cfg)
  self.assertEqual([r['run_id'] for r in rows],['r1','r2'])
  self.assertEqual((rows[0]['reported_total_tokens'],rows[0]['phases_attempted'],rows[0]['finished']),(15,1,False))
  md=(self.run_.root/'comparison.md').read_text()
  self.assertIn('| sequential | fake | fake/model-a | 2 |',md)
  self.assertTrue((self.run_.root/'comparison.json').exists())
  self.assertIsNone(core.total([{'usage':{'tokens':None}},{'usage':{'tokens':5}}],'tokens'))
  self.assertEqual(core.known_total([{'usage':{'tokens':None}},{'usage':{'tokens':5}}],'tokens'),(5,1))
  self.assertEqual((core.at_least('$2.00',1),core.at_least('$2.00',0),core.at_least('—',3)),('≥ $2.00','$2.00','—'))
 def test_final_evaluation_scores_blocked_work(self):
  for t in self.s['tasks'].values():t['status']='DONE'
  self.s['tasks']['TASK-027'].update(status='BLOCKED',blocked_reason='REVIEW_GAPS: max cycles reached')
  self.s['tasks']['TASK-026'].update(status='BLOCKED',blocked_reason='TIMEOUT: 124')
  calls=[]
  def fake(run,state,label,commit='HEAD',done=None):
   calls.append((label,sorted(done)));state['evaluations'].append({'label':label,'commit':core.git(self.w,'rev-parse','HEAD'),'passed':1,'due':1,'total':1,'categories':{},'metrics':{}});return state['evaluations'][-1]
  with patch.object(core,'eval_dir',lambda cfg:self.root),patch.object(core,'evaluate_run',fake):
   self.assertTrue(core.final_evaluation(self.run_,self.s))
   self.assertIsNone(core.final_evaluation(self.run_,self.s))   # same commit: not scored twice
   self.assertTrue(core.final_evaluation(self.run_,self.s,again=True))
   self.s['tasks']['TASK-001']['status']='ACTIVE'
   self.assertIsNone(core.final_evaluation(self.run_,self.s))   # work can still go on
  self.assertEqual(calls[0][0],'final');self.assertEqual(len(calls[0][1]),28);self.assertEqual(len(calls),2)
  row=core.summarize(core.read(self.run_.meta),self.s)
  self.assertEqual((row['blocked_review_gaps'],row['blocked_errors']),(1,1))
  self.assertIn('2 (1 review, 1 error)',core.comparison_markdown([row]))
 def test_evaluation_is_recorded_and_compared(self):
  self.assertIsNone(core.evaluate_run(self.run_,self.s,'TASK-001'))
  self.s['evaluations'].append({'label':'TASK-002','commit':'abc','eval_commit':'def','eval_version':1,'passed':3,'due':4,'total':41,
   'categories':{'contract':{'passed':3,'due':4,'total':10}},'metrics':{'ticks_per_second':250.0},'seconds':5,'timestamp':'t'})
  self.s['evaluations'].append({'label':'TASK-003','error':'boom'})
  core.write(self.run_.state,self.s)
  row=core.summarize(core.read(self.run_.meta),self.s)
  self.assertEqual((row['evaluation']['label'],row['evaluations_failed']),('TASK-002',1))
  md=core.comparison_markdown([row])
  self.assertIn('| sequential | fake | r1 | TASK-002 | 3/41 | 3/10 | 250.0 | — | — |',md)
  self.s['evaluations'][0]['balance']={'fixed':{'score':37,'coexistence':1/6},'demo':{'score':0,'missing':True}}
  md=core.comparison_markdown([core.summarize(core.read(self.run_.meta),self.s)])
  self.assertIn('| 250.0 | 37 (17%) | no demo |',md)

if __name__=='__main__':unittest.main()

class Parallel(Base):
 """TASK-003 and TASK-004 both depend only on TASK-002, so they are the first pair to run side by side."""
 def setUp(self):
  super().setUp()
  self.run_=core.Run('fake','parallel',workers=2);self.w=core.init(self.run_);self.s=core.read(self.run_.state)
 def go(self,n):
  core.run_parallel(self.run_,self.s,max_phases=n,no_eval=True,live=False)
  return self.s['tasks']
 def test_layout_and_worker_lock(self):
  self.assertEqual(core.read(self.run_.meta)['workers'],2)
  self.assertEqual(core.Run('fake','parallel').workers,2)
  with self.assertRaises(RuntimeError):core.check_unchanged(core.Run('fake','parallel',workers=3))
  self.assertEqual(core.Run('fake').workers,1)
 def test_task_is_built_in_a_checkout_and_merged(self):
  t=self.go(3)
  self.assertEqual((t['TASK-001']['status'],t['TASK-001']['phase']),('ACTIVE','merge'))
  self.assertFalse((self.w/'TASK-001.txt').exists())
  self.assertTrue((self.run_.workers_dir/'TASK-001'/'TASK-001.txt').exists())
  self.assertEqual(core.git(self.run_.workers_dir/'TASK-001','remote'),'')
  self.assertEqual(core.ready(self.s),['TASK-001'])
  t=self.go(1)
  self.assertEqual(t['TASK-001']['status'],'DONE')
  self.assertTrue((self.w/'TASK-001.txt').exists())
  self.assertFalse((self.run_.workers_dir/'TASK-001').exists())
  self.assertEqual(self.s['merges'][0]['conflict'],False)
 def test_independent_tasks_run_side_by_side_and_merge_cleanly(self):
  t=self.go(16)
  self.assertEqual([t[f'TASK-00{i}']['status'] for i in (1,2,3,4)],['DONE']*4)
  for i in (1,2,3,4):self.assertTrue((self.w/f'TASK-00{i}.txt').exists())
  self.assertEqual(t['TASK-003']['base_commit'],t['TASK-004']['base_commit'])
  r=core.summarize(core.read(self.run_.meta),self.s)
  self.assertEqual((r['workers'],r['merges'],r['merge_conflicts'],r['merges_failed']),(2,4,0,0))
  self.assertIn('## Parallel track',core.comparison_markdown([r]))
  self.assertTrue(core.protected_ok(self.w)[0])
 def test_conflict_is_resolved_by_one_agent_call(self):
  with patch.dict(os.environ,{'FAKE_CONFLICT':'1'}):t=self.go(17)
  self.assertEqual([t[f'TASK-00{i}']['status'] for i in (1,2,3,4)],['DONE']*4)
  self.assertEqual([m['conflict'] for m in self.s['merges']],[False,False,False,True])
  self.assertEqual(self.s['merges'][3]['conflict_files'],['docs/STATE.md'])
  self.assertEqual((self.w/'docs/STATE.md').read_text(),'merged\n')
  self.assertEqual([e['phase'] for e in self.s['events']].count('merge'),1)
  self.assertEqual(core.git(self.w,'status','--porcelain'),'')
 def test_unresolved_conflict_blocks_the_task_and_leaves_main_untouched(self):
  with patch.dict(os.environ,{'FAKE_CONFLICT':'1','FAKE_BAD_MERGE':'1'}):t=self.go(18)
  blocked=[k for k in ('TASK-003','TASK-004') if t[k]['status']=='BLOCKED']
  self.assertEqual(len(blocked),1)
  self.assertIn('MERGE_UNRESOLVED',t[blocked[0]]['blocked_reason'])
  self.assertFalse((self.w/(blocked[0]+'.txt')).exists())
  self.assertEqual(core.git(self.w,'status','--porcelain'),'')
  self.assertTrue((self.run_.workers_dir/blocked[0]).exists())
  self.assertEqual(core.summarize(core.read(self.run_.meta),self.s)['merges_failed'],1)
 def test_job_order(self):
  s=core.initial_state()
  for k in ('TASK-001','TASK-002'):s['tasks'][k]['status']='DONE'
  self.assertEqual(core.parallel_jobs(s,(),3),['TASK-003','TASK-004'])
  self.assertEqual(core.parallel_jobs(s,('TASK-003',),3),['TASK-004'])
  self.assertEqual(core.parallel_jobs(s,(),1),['TASK-003'])
  for k in ('TASK-003','TASK-004'):s['tasks'][k].update(status='ACTIVE',phase='merge')
  self.assertEqual(core.parallel_jobs(s,(),3),['TASK-003'])
  self.assertEqual(core.parallel_jobs(s,('TASK-003',),3),[])

