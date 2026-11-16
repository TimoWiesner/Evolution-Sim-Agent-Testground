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
 def test_termination_signal_ends_the_agent_process(self):
  import subprocess,os,time
  root=str(pathlib.Path(__file__).resolve().parents[1])
  with tempfile.TemporaryDirectory() as tmp:
   pid=pathlib.Path(tmp)/'pid'
   child=f'import os,time,pathlib;pathlib.Path({str(pid)!r}).write_text(str(os.getpid()));time.sleep(60)'
   code=('import sys,signal,os,threading;sys.path.insert(0,%r);from harness import core\n'
         'signal.signal(signal.SIGTERM,core.terminate);threading.Timer(1.5,os.kill,(os.getpid(),signal.SIGTERM)).start()\n'
         'try:core.cmd([sys.executable,"-c",%r],".",100)\nexcept KeyboardInterrupt:print("stopped")')%(root,child)
   p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
   self.assertIn('stopped',p.stdout,p.stderr)
   time.sleep(.3)
   with self.assertRaises(ProcessLookupError):os.kill(int(pid.read_text()),0)

if __name__=='__main__':unittest.main()
