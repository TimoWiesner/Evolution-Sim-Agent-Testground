"""End-to-end harness test using a fake CLI; no provider credentials needed."""
import json
import pathlib
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
  import shutil
  shutil.copytree(core.ROOT,self.root,ignore=shutil.ignore_patterns('runs','__pycache__'))
  fake=self.root/'fakeagent';fake.write_text(FAKE);fake.chmod(0o755)
  cfg=core.read(self.root/'benchmark.json');cfg['agents']['opencode']['executable']=str(fake)
  core.write(self.root/'benchmark.json',cfg)
  self.patcher=patch.object(core,'ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
  self.w=core.init('opencode');self.s=core.initial_state();self.cfg=core.read(self.root/'benchmark.json')
 def test_three_phases_and_local_git(self):
  for phase in ('plan','implement','review'):
   self.assertTrue(core.execute_phase('opencode',None,False,self.s,self.w,'TASK-001',self.cfg,live=False))
  self.assertEqual(self.s['tasks']['TASK-001']['status'],'DONE')
  self.assertEqual(len(core.git(self.w,'log','--format=%H').splitlines()),4)
  self.assertEqual(core.git(self.w,'remote'),'')
  self.assertTrue(core.protected_ok(self.w)[0])
 def test_missing_handoff_recovery_and_block(self):
  import os
  with patch.dict(os.environ,{'FAKE_MISSING':'1'}):
   core.execute_phase('opencode',None,False,self.s,self.w,'TASK-001',self.cfg,live=False)
   self.assertEqual(self.s['tasks']['TASK-001']['recovery'],1)
   core.execute_phase('opencode',None,False,self.s,self.w,'TASK-001',self.cfg,live=False)
  self.assertEqual(self.s['tasks']['TASK-001']['status'],'BLOCKED')
  self.assertIn('HANDOFF_INVALID',self.s['tasks']['TASK-001']['blocked_reason'])
 def test_generated_handoff_is_not_protected(self):
  hand=self.w/'tasks/TASK-001/handoffs/plan-cycle1.md'
  hand.parent.mkdir(exist_ok=True);hand.write_text('notes')
  self.assertTrue(core.protected_ok(self.w)[0])
 def test_repeated_run_archives_handoff(self):
  core.execute_phase('opencode',None,False,self.s,self.w,'TASK-001',self.cfg,live=False)
  self.s['tasks']['TASK-001']['phase']='plan'
  core.execute_phase('opencode',None,False,self.s,self.w,'TASK-001',self.cfg,live=False)
  self.assertEqual(len(list((self.root/'runs/opencode/handoff-archive').glob('*.json'))),1)

if __name__=='__main__':unittest.main()
