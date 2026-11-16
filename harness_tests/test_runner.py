import unittest, tempfile, json, pathlib
from harness.core import specs, initial_state, ready, handoff_valid, adapter, usage
class RunnerTests(unittest.TestCase):
 def test_task_graph(self):
  sp=specs();self.assertEqual(len(sp),27)
  self.assertEqual(len(set(sp)),27)
  for t,x in sp.items():
   for d in x['dependencies']:
    self.assertIn(d,sp);self.assertLess(int(d[-3:]),int(t[-3:]))
 def test_ready_deps(self):
  st=initial_state();self.assertEqual(ready(st),['TASK-001'])
  st['tasks']['TASK-001']['status']='DONE'
  self.assertIn('TASK-002',ready(st))
 def test_handoff(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'x.json';p.write_text(json.dumps({'task_id':'TASK-001','phase':'review','cycle':1,'summary':'ok','changed_files':[],'decisions':[],'tests':[],'risks':[],'next_steps':[],'verdict':'FAIL','gaps':['missing']}))
   self.assertTrue(handoff_valid(p,'TASK-001','review',1)[0]);self.assertFalse(handoff_valid(p,'TASK-001','review',2)[0])
 def test_adapters(self):
  for name in ('claude','codex','opencode'):
   self.assertTrue(adapter(name,None))
 def test_usage_unavailable(self):
  self.assertEqual(usage('opencode','blah')['cost_usd'],None)
if __name__=='__main__':unittest.main()
