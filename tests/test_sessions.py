import fcntl, http.client, importlib.util, json, os, pty, struct, subprocess, tempfile, threading, time, unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
TEMP=tempfile.TemporaryDirectory(); os.environ["LOCAL_CONSOLE_DATA"]=TEMP.name
spec=importlib.util.spec_from_file_location("local_console_server",BASE/"server.py"); app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)

class Sessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=app.http.server.ThreadingHTTPServer(("127.0.0.1",0),app.Handler); cls.port=cls.http.server_port; app.PORT=cls.port
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.clean(); cls.http.shutdown(); cls.http.server_close(); TEMP.cleanup()
    @classmethod
    def clean(cls):
        with app.LOCK:
            sessions=list(app.SESSIONS.values())
        for s in sessions:
            with app.LOCK: app.stop_process(s,"test teardown")
            reader=s.get("reader")
            if reader: reader.join(timeout=2)
            with app.LOCK:
                if not s.get("master_closed"):
                    try: os.close(s["master"])
                    except OSError: pass
                    s["master_closed"]=True
        with app.LOCK: app.SESSIONS.clear()
    def setUp(self): self.clean()
    def call(self,path,method="GET",body=None,headers=None):
        h={"Host":f"127.0.0.1:{self.port}","Origin":f"http://127.0.0.1:{self.port}","Sec-Fetch-Site":"same-origin","X-Console-Request":app.TOKEN}; h.update(headers or {})
        c=http.client.HTTPConnection("127.0.0.1",self.port,timeout=4); data=json.dumps(body) if isinstance(body,(dict,list)) else body
        if isinstance(body,(dict,list)): h["Content-Type"]="application/json"
        c.request(method,path,body=data,headers=h); r=c.getresponse(); raw=r.read(); c.close()
        try: return r.status,json.loads(raw)
        except Exception:return r.status,raw
    def start(self,profile,label=None,timeout=30):
        status,data=self.call("/api/sessions","POST",{"profile":profile,"label":label or profile,"timeout":timeout})
        self.assertEqual(status,201,data); return data["session"]
    def wait_output(self,sid,needle,limit=4):
        stop=time.time()+limit
        while time.time()<stop:
            _,d=self.call("/api/sessions"); s=next(x for x in d["sessions"] if x["id"]==sid)
            if needle in s["output"]: return s
            time.sleep(.05)
        self.fail(f"output did not contain {needle!r}")
    def test_session_isolation_and_reconnect_retains_output(self):
        a=self.start("runtime","Runtime facts"); b=self.start("checksum","Sample hashes")
        av=self.wait_output(a["id"],"Python "); bv=self.wait_output(b["id"],"sha256 ")
        self.assertIn("Python ",av["output"]); self.assertNotIn("sha256 ",av["output"])
        self.assertIn("sha256 ",bv["output"]); self.assertNotIn("Python ",bv["output"])
        _,again=self.call("/api/sessions"); self.assertEqual({s["id"] for s in again["sessions"]},{a["id"],b["id"]})
    def test_resize_changes_the_real_pty_and_rejects_unbounded_dimensions(self):
        s=self.start("progress"); status,data=self.call(f"/api/sessions/{s['id']}/resize","POST",{"rows":38,"cols":122})
        self.assertEqual(status,200); self.assertEqual((data["rows"],data["cols"]),(38,122))
        rows,cols,_,_=struct.unpack("HHHH",fcntl.ioctl(app.SESSIONS[s["id"]]["master"],app.termios.TIOCGWINSZ,b"\0"*8))
        self.assertEqual((rows,cols),(38,122))
        self.assertEqual(self.call(f"/api/sessions/{s['id']}/resize","POST",{"rows":999,"cols":10})[0],400)
    def test_timeout_kills_a_silent_child(self):
        s=self.start("tree",timeout=30); line=self.wait_output(s["id"],"CHILD_PID:")["output"]; child=int(line.split("CHILD_PID:",1)[1].splitlines()[0])
        with app.LOCK: app.SESSIONS[s["id"]]["timeout"]=0.05; app.SESSIONS[s["id"]]["started"]=time.time()-1
        deadline=time.time()+3
        while time.time()<deadline:
            if app.SESSIONS[s["id"]]["state"]=="timed out": break
            time.sleep(.05)
        self.assertEqual(app.SESSIONS[s["id"]]["state"],"timed out")
        self.assertIsNotNone(app.SESSIONS[s["id"]]["proc"].poll())
        self.assertFalse(subprocess.run(["ps","-o","stat=","-p",str(child)],capture_output=True,text=True).stdout.strip())
    def test_stop_kills_and_reaps_the_process_group(self):
        s=self.start("tree"); line=self.wait_output(s["id"],"CHILD_PID:")["output"]
        child=int(line.split("CHILD_PID:",1)[1].splitlines()[0])
        status,result=self.call(f"/api/sessions/{s['id']}/stop","POST",{})
        self.assertEqual(status,200); self.assertIsNotNone(app.SESSIONS[s["id"]]["proc"].poll())
        deadline=time.time()+2; state=""
        while time.time()<deadline:
            p=subprocess.run(["ps","-o","stat=","-p",str(child)],capture_output=True,text=True,check=False)
            state=p.stdout.strip()
            if not state: break
            time.sleep(.05)
        self.assertFalse(state,f"child remains unreaped: {state}")
    def test_output_retention_is_capped(self):
        s=self.start("output"); deadline=time.time()+8
        while time.time()<deadline and app.SESSIONS[s["id"]]["proc"].poll() is None: time.sleep(.05)
        session=app.SESSIONS[s["id"]]; self.assertIsNotNone(session["proc"].poll()); self.assertLessEqual(len(session["output"]),app.MAX_OUTPUT)
        self.assertIn(b"synthetic text",session["output"])
    def test_fixed_allowlist_limits_and_web_origin_boundary(self):
        self.assertEqual(self.call("/api/sessions","POST",{"profile":"/bin/sh","label":"bad","timeout":60})[0],400)
        self.assertEqual(self.call("/api/sessions","POST",{"profile":"progress","label":"bad","timeout":999})[0],400)
        self.assertEqual(self.call("/api/sessions","POST",{"profile":"progress","label":"bad","timeout":60},{"Origin":"https://attacker.invalid"})[0],403)
        self.assertEqual(self.call("/api/sessions","POST",{"profile":"progress","label":"bad","timeout":60},{"X-Console-Request":"wrong"})[0],403)
        self.assertEqual(self.call("/api/sessions","POST",{"profile":"progress;touch /tmp/no","label":"bad","timeout":60})[0],400)
        self.assertEqual(self.call("/api/sessions/not-a-session/stop","POST",{})[0],400)
        self.assertEqual(self.call("/api/sessions","GET",headers={"Origin":"https://attacker.invalid"})[0],403)
        self.assertEqual(self.call("/api/sessions","GET",headers={"X-Console-Request":"wrong"})[0],403)
        self.assertEqual(self.call("/api/session","GET",headers={"Host":"attacker.invalid"})[0],403)
    def test_maximum_four_running_sessions(self):
        for n in range(app.MAX_ACTIVE): self.start("progress",f"slot {n}")
        status,_=self.call("/api/sessions","POST",{"profile":"progress","label":"overflow","timeout":60})
        self.assertEqual(status,429)

if __name__=="__main__":unittest.main()
