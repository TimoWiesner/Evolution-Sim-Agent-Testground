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
match=re.search(r'Task (TASK-\\d+), phase (PLAN|IMPLEMENT|REVIEW), cycle (\\d+)',prompt)
if match:
 task,phase,cycle=match.groups();phase=phase.lower();cycle=int(cycle)
 path=pathlib.Path.cwd()/'tasks'/task/'handoffs'/f'{phase}-cycle{cycle}.json'
 if os.getenv('FAKE_MISSING')!='1':
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps({'task_id':task,'phase':phase,'cycle':cycle,'summary':'completed','changed_files':[],'decisions':[],'tests':[],'risks':[],'next_steps':[],'verdict':'PASS' if phase=='review' else 'N/A','gaps':[]}))
  (pathlib.Path.cwd()/'docs'/'STATE.md').write_text('updated\\n')
print(json.dumps({'type':'step_finish','part':{'tokens':{'input':10,'output':5},'cost':0.01}}),flush=True)
'''

class Integration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=pathlib.Path(self.tmp.name)/'bench'
  shutil.copytree(core.ROOT,self.root,ignore=shutil.ignore_patterns('runs','__pycache__','.git'))
  fake=self.root/'fakeagent';fake.write_text(FAKE);fake.chmod(0o755)
  cfg=core.read(self.root/'benchmark.json')
  cfg['runs_root']=str(pathlib.Path(self.tmp.name)/'runs')
  cfg['clis']['opencode']['executable']=str(fake)
  cfg['profiles']={'fake':{'cli':'opencode','model':'fake/model-a'}}
  core.write(self.root/'benchmark.json',cfg)
  self.patcher=patch.object(core,'ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
  self.run_=core.Run('fake');self.w=core.init(self.run_);self.s=core.initial_state()
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

if __name__=='__main__':unittest.main()
