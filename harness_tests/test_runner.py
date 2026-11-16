import unittest, tempfile, json, pathlib, sys
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
  u=usage('codex',json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':7}}))
  self.assertEqual((u['input_tokens'],u['cached_input_tokens'],u['output_tokens'],u['tokens']),(20,80,7,107))
  out='\n'.join(json.dumps(x) for x in ({'type':'system','subtype':'init','model':'m-1'},{'type':'result','total_cost_usd':0.5,'usage':{'input_tokens':4,'output_tokens':6}}))
  self.assertEqual(usage('claude',out),{'tokens':10,'input_tokens':4,'cached_input_tokens':0,'output_tokens':6,'cost_usd':0.5,'reported_model':'m-1','subagents':0,'delegated':False})
 def test_container_commands(self):
  from harness import core
  cfg=config();cfg['runs_root']='/tmp/evo-test-runs'
  run=core.Run('local-qwen',cfg=cfg,container=True)
  run.profile['executable']=sys.executable
  create=core.container_create_argv(run)
  self.assertEqual(create[create.index('--network')+1],'pasta:--map-guest-addr,none,-T,8080')
  self.assertIn(f'{run.workspace}:/workspace',create)
  self.assertIn(f'{run.home}:/root',create)
  self.assertTrue(any(x.endswith(':ro') for x in create))
  self.assertFalse(any(str(core.ROOT) in x for x in create))
  argv=core.phase_argv(run,'TASK-001','plan',1)
  self.assertEqual(argv[:2],['podman','exec'])
  self.assertEqual(argv[argv.index('timeout')+3],'7200')
  self.assertIn('--auto',argv)
  self.assertIn('WORKSPACE ROOT (absolute): /workspace',argv[-1])
  self.assertIn('/workspace/tasks/TASK-001/handoffs/plan-cycle1.json',argv[-1])
  self.assertNotIn(str(run.workspace),argv[-1])
 def test_host_mode_has_no_container_wrapper(self):
  from harness import core
  cfg=config();cfg['runs_root']='/tmp/evo-test-runs'
  run=core.Run('gpt-luna',cfg=cfg)
  argv=core.phase_argv(run,'TASK-001','plan',1)
  self.assertEqual(argv[0],'codex');self.assertIn('workspace-write',argv)
 def test_contract_is_protected_and_referenced(self):
  from harness import core
  self.assertIn('docs/CONTRACT.md',core.protected_manifest())
  self.assertIn('docs/CONTRACT.md',core.prompt_for('TASK-001','plan',1,'/tmp'))
  sp=specs()
  for t in ('TASK-002','TASK-003','TASK-019','TASK-021','TASK-022','TASK-023','TASK-027'):
   self.assertTrue(any('docs/CONTRACT.md' in c for c in sp[t]['acceptance_criteria']),t)
   md=(core.ROOT/'tasks'/t/'task.md').read_text()
   for c in sp[t]['acceptance_criteria']:self.assertIn(c,md)
 def test_evaluation_keeps_tests_away_from_the_network(self):
  from harness import core
  cfg=config()
  prep,test=core.evaluation_commands(cfg,'n','img','/p','/o','/secret-eval',['TASK-002','TASK-001'])
  self.assertFalse(any('secret-eval' in x for x in prep))
  self.assertEqual(prep[prep.index('--network')+1],'pasta:--map-guest-addr,none')
  self.assertEqual(test[test.index('--network')+1],'none')
  self.assertIn('/secret-eval:/eval:ro',test)
  self.assertEqual(test[test.index('--done')+1],'TASK-001,TASK-002')
 def test_subagent_use_is_read_from_each_cli(self):
  out=json.dumps({'type':'result','total_cost_usd':0.1,'usage':{'input_tokens':4,'output_tokens':248},
   'modelUsage':{'m':{'inputTokens':6,'cacheCreationInputTokens':10,'cacheReadInputTokens':30,'outputTokens':297}},'subagent_stats':{'spawned':2}})
  u=usage('claude',out)
  self.assertEqual((u['input_tokens'],u['cached_input_tokens'],u['output_tokens'],u['subagents'],u['delegated']),(16,30,297,2,True))
  turn=json.dumps({'type':'turn.completed','usage':{'input_tokens':2,'output_tokens':3}})
  u=usage('codex',turn);self.assertEqual((u['subagents'],u['delegated']),(None,False))
  u=usage('codex',json.dumps({'type':'item.completed','item':{'type':'collab_tool_call','tool':'wait'}})+'\n'+turn)
  self.assertEqual((u['subagents'],u['delegated']),(None,True))
  part=lambda i:json.dumps({'type':'tool','part':{'type':'tool','tool':'task','callID':i}})
  u=usage('opencode',part('a')+'\n'+part('a')+'\n'+part('b'));self.assertEqual((u['subagents'],u['delegated']),(2,True))
 def test_subagent_track_changes_only_prompt_and_codex_session(self):
  from harness import core
  cfg=config();cfg['runs_root']='/tmp/evo-test-runs'
  for name in ('gpt-luna','claude-haiku'):
   a=core.Run(name,cfg=cfg);b=core.Run(name,'subagents',cfg=cfg)
   for r in (a,b):r.profile['executable']=sys.executable
   x=core.phase_argv(a,'TASK-001','plan',1);y=core.phase_argv(b,'TASK-001','plan',1)
   self.assertNotIn('DELEGATION:',x[-1]);self.assertIn('DELEGATION:',y[-1])
   self.assertEqual(x[-1],y[-1].replace(core.DELEGATION_NOTE,'').replace('/subagents/','/sequential/'))
   self.assertEqual([v for v in x[:-1] if v!='--ephemeral'],y[:-1])
   self.assertEqual('--ephemeral' in x,name=='gpt-luna');self.assertNotIn('--ephemeral',y)
if __name__=='__main__':unittest.main()
