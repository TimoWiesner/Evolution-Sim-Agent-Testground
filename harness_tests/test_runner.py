import unittest, tempfile, json, pathlib
from harness.core import specs, initial_state, ready, handoff_valid, adapter, usage, config, resolve_profile, choose_ready
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
 def test_choice_is_deterministic(self):
  st=initial_state()
  for t in ('TASK-001','TASK-002'):st['tasks'][t]['status']='DONE'
  self.assertEqual(choose_ready(st),'TASK-003')
  st['tasks']['TASK-004']['status']='ACTIVE'
  self.assertEqual(choose_ready(st),'TASK-004')
 def test_handoff(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'x.json';p.write_text(json.dumps({'task_id':'TASK-001','phase':'review','cycle':1,'summary':'ok','changed_files':[],'decisions':[],'tests':[],'risks':[],'next_steps':[],'verdict':'FAIL','gaps':['missing']}))
   self.assertTrue(handoff_valid(p,'TASK-001','review',1)[0]);self.assertFalse(handoff_valid(p,'TASK-001','review',2)[0])
 def test_every_profile_has_an_adapter(self):
  cfg=config()
  for name in cfg['profiles']:
   p=resolve_profile(cfg,name);argv=adapter(p)
   self.assertEqual(argv[0],p['executable'])
   if p['model']:self.assertEqual(argv[argv.index('--model')+1],p['model'])
 def test_unknown_profile(self):
  with self.assertRaises(RuntimeError):resolve_profile(config(),'nope')
 def test_usage_unavailable(self):
  self.assertEqual(usage('opencode','blah')['cost_usd'],None)
 def test_usage_sums_and_reports_model(self):
  turn=json.dumps({'type':'turn.completed','usage':{'input_tokens':2,'output_tokens':3}})
  self.assertEqual(usage('codex',turn+'\n'+turn)['tokens'],10)
  out='\n'.join(json.dumps(x) for x in ({'type':'system','subtype':'init','model':'m-1'},{'type':'result','total_cost_usd':0.5,'usage':{'input_tokens':4,'output_tokens':6}}))
  self.assertEqual(usage('claude',out),{'tokens':10,'cost_usd':0.5,'reported_model':'m-1'})
if __name__=='__main__':unittest.main()
