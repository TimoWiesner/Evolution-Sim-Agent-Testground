import json, pathlib, tempfile, unittest
from harness import core, publish

REPORT={'profile':'p','track':'sequential','run_id':'r1','model':'m','reported_models':['m-1'],'cli':'codex','cli_version':'codex 1',
 'created':'2026-11-16T10:00:00','finished':True,'tasks_total':28,'status_counts':{'PENDING':0,'ACTIVE':0,'DONE':26,'BLOCKED':2},'blocked_review_gaps':1,'blocked_errors':1,
 'first_cycle_pass_ratio':0.8,'phases_attempted':90,'phases_failed':4,'operator_interventions':0,'wall_seconds_agent_calls':7300,
 'reported_input_tokens':1000,'reported_cached_input_tokens':None,'reported_output_tokens':500,'reported_total_tokens':None,
 'reported_total_cost_usd':None,'isolation':'container','completed_ratio':0.926,'failure_classes':{},'harness_commit':'abc1234','host':{},
 'benchmark_version':1,'evaluations_failed':0,
 'evaluation':{'label':'TASK-028','passed':30,'due':41,'total':41,'eval_version':1,'eval_commit':'e','categories':{'contract':{'passed':9,'due':10,'total':10}},'metrics':{'ticks_per_second':120.5},'balance':{'fixed':{'score':42,'coexistence':0.5,'runs':6,'runs_failed':1,'runs_timed_out':2},'demo':{'score':0,'missing':True}}},
 'evaluations':[]}

class PublishTests(unittest.TestCase):
 def test_leaked_login_is_found(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);(d/'src').mkdir()
   (d/'src/a.py').write_text('x=1');(d/'src/notes.md').write_text('token: sk-secret-0123456789abcdefghij')
   self.assertEqual(publish.leaked_secrets(d,{'sk-secret-0123456789abcdefghij'}),['src/notes.md'])
   self.assertEqual(publish.leaked_secrets(d,{'another-secret-value-000000'}),[])
 def test_login_secrets_reads_long_strings_only(self):
  with tempfile.TemporaryDirectory() as d:
   class R:cli='codex';home=pathlib.Path(d)
   f=R.home/'.codex/auth.json';f.parent.mkdir()
   f.write_text(json.dumps({'tokens':{'access_token':'A'*40,'kind':'oauth'},'list':['B'*25]}))
   self.assertEqual(publish.login_secrets(R),{'A'*40,'B'*25})
 def test_run_readme_states_scores_and_self_containment(self):
  art={'build_ok':True,'self_contained':False,'self_contained_detail':'exit status 127','asset':'evosim-p.tar.gz','sha256':'ab','size_bytes':2500000}
  md=publish.run_readme(REPORT,art,'https://example/rel','https://example/harness')
  self.assertIn('**30 of 41 checks passed**',md);self.assertIn('**not** self-contained',md)
  self.assertIn('| Cost | — |',md);self.assertIn('120.5 ticks per second',md);self.assertIn('example configuration 42 (50%; 1 of 6 runs failed; 2 of 6 runs over the time limit)',md);self.assertIn('26 of 28 (2 (1 review, 1 error) blocked)',md);self.assertIn('demo scenario no demo',md)
  md=publish.run_readme({**REPORT,'evaluation':None},{**art,'build_ok':False},None,None)
  self.assertIn('not scored',md);self.assertIn('No executable',md)
 def test_screenshots_are_filtered_and_shown(self):
  png=b'\x89PNG\r\n\x1a\n'+b'x'*50
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);src=d/'in';src.mkdir()
   (src/'main.png').write_bytes(png);(src/'Charts View.png').write_bytes(png)
   (src/'fake.png').write_text('not an image');(src/'empty.png').write_bytes(b'');(src/'notes.txt').write_text('x')
   (src/'link.png').symlink_to('/etc/hostname')
   for i in range(8):(src/f'z{i}.png').write_bytes(png)
   names=publish.collect_screenshots(src,d/'out')
   self.assertEqual(names[:2],['main.png','charts-view.png']);self.assertEqual(len(names),publish.MAX_SCREENSHOTS)
   self.assertEqual(sorted(p.name for p in (d/'out').iterdir()),sorted(names))
   self.assertEqual(publish.collect_screenshots(d/'missing',d/'out'),[]);self.assertFalse((d/'out').exists())
  art={'build_ok':False,'screenshots':['main.png','charts-view.png']}
  md=publish.run_readme(REPORT,art,None,None)
  self.assertIn('![main](screenshots/main.png)',md);self.assertIn('![charts-view](screenshots/charts-view.png)',md)
  self.assertIn('wrote no screenshots',publish.run_readme(REPORT,{'build_ok':False},None,None))
  self.assertIn('[ANALYSIS.md](ANALYSIS.md)',publish.index_readme([REPORT],None,None,['ANALYSIS.md']))
  self.assertNotIn('Written analyses',publish.index_readme([REPORT],None,None))
  idx=publish.index_readme([{**REPORT,'screenshot':'screenshots/main.png'}],None,None)
  self.assertIn('## Interfaces',idx);self.assertIn('(results/p/sequential/r1/screenshots/main.png)',idx)
  self.assertNotIn('## Interfaces',publish.index_readme([REPORT],None,None))
 def test_index_lists_runs_without_check_details(self):
  md=publish.index_readme([{**REPORT,'has_asset':True}],'https://example/harness','https://example/results')
  self.assertIn('results/p/sequential/r1/README.md',md);self.assertIn('releases/tag/p-sequential-r1',md)
  self.assertIn('## Hidden test results',md)
 def test_public_report_has_no_free_text(self):
  cfg=core.config();cfg['runs_root']=tempfile.mkdtemp()
  run=core.Run('gpt-luna',cfg=cfg);st=core.initial_state()
  st['tasks']['TASK-001']['history'].append({'seconds':5,'failure_class':'HANDOFF_INVALID','handoff_error':'/secret/path','usage':{'tokens':1,'cost_usd':None}})
  st['events']=list(st['tasks']['TASK-001']['history'])
  st['evaluations'].append({'label':'TASK-001','passed':1,'due':1,'total':41,'categories':{},'metrics':{},'eval_version':1,'eval_commit':'x','checks':[{'id':'C01'}]})
  core.write(run.meta,core.run_metadata(run))
  out=json.dumps(publish.public_report(run,st))
  self.assertNotIn('/secret/path',out);self.assertNotIn('C01',out);self.assertNotIn('eval_commit',out)
 def test_balance_over_the_time_limit_is_not_a_collapse(self):
  from harness import core
  ev={'balance':{'demo':{'score':None,'coexistence':None,'runs':6,'runs_failed':0,'runs_timed_out':6}}}
  self.assertEqual(core.fmt_balance(ev,'demo'),'— (6 of 6 runs over the time limit)')
if __name__=='__main__':unittest.main()
