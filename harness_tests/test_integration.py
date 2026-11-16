"""End-to-end harness test using a fake CLI; no provider credentials needed."""
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
  self.s['tasks']['TASK-001']['phase']='plan'
  with self.assertRaises(RuntimeError):self.phase()
 def test_missing_handoff_recovery_and_block(self):
  with patch.dict(os.environ,{'FAKE_MISSING':'1'}):
   self.phase()
   self.assertEqual(self.s['tasks']['TASK-001']['recovery'],1)
   self.phase()
  self.assertEqual(self.s['tasks']['TASK-001']['status'],'BLOCKED')
  self.assertIn('HANDOFF_INVALID',self.s['tasks']['TASK-001']['blocked_reason'])
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
 def test_evaluation_is_recorded_and_compared(self):
  self.assertIsNone(core.evaluate_run(self.run_,self.s,'TASK-001'))
  self.s['evaluations'].append({'label':'TASK-002','commit':'abc','eval_commit':'def','eval_version':1,'passed':3,'due':4,'total':41,
   'categories':{'contract':{'passed':3,'due':4,'total':10}},'metrics':{'ticks_per_second':250.0},'seconds':5,'timestamp':'t'})
  self.s['evaluations'].append({'label':'TASK-003','error':'boom'})
  core.write(self.run_.state,self.s)
  row=core.summarize(core.read(self.run_.meta),self.s)
  self.assertEqual((row['evaluation']['label'],row['evaluations_failed']),('TASK-002',1))
  md=core.comparison_markdown([row])
  self.assertIn('| sequential | fake | r1 | TASK-002 | 3/41 | 3/10 | 250.0 |',md)

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

