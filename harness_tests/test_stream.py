import tempfile, pathlib, sys, unittest
from harness.core import cmd, short_event

class StreamTests(unittest.TestCase):
 def test_live_jsonl_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'raw.jsonl'
   r=cmd([sys.executable,'-c','import json;print(json.dumps({"type":"turn.completed","usage":{"input_tokens":2}}), flush=True)'],tmp,3,logfile=p,agent='codex',live=False)
   self.assertEqual(r['exit_code'],0)
   self.assertIn('turn.completed',p.read_text())
   self.assertEqual(short_event('codex',p.read_text().strip()),'turn completed')
 def test_timeout(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=cmd([sys.executable,'-c','import time;time.sleep(3)'],tmp,.25)
   self.assertEqual(r['exit_code'],124)
 def test_watch_ends_the_process(self):
  from unittest.mock import patch
  import harness.core as core
  with tempfile.TemporaryDirectory() as tmp:
   clock=iter(range(0,100000,20))
   with patch.object(core.time,'monotonic',lambda:next(clock)):
    r=cmd([sys.executable,'-c','import time;time.sleep(30)'],tmp,10**6,watch=lambda:'server gone')
   self.assertEqual((r['aborted'],r['timeout'],r['exit_code']),('server gone',False,1))

if __name__=='__main__':unittest.main()
