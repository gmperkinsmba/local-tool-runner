#!/usr/bin/env python3
"""Local-only controller for a small allowlist of safe fixture processes."""
import atexit, fcntl, http.server, json, os, pty, select, secrets, shutil, signal, struct, subprocess, sys, termios, threading, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RESOURCE_ROOT=Path(getattr(sys,"_MEIPASS",ROOT))
DATA=Path(os.environ.get("LOCAL_CONSOLE_DATA",Path.home()/".local/share/local-console"))
PORT=int(os.environ.get("LOCAL_CONSOLE_PORT","8314"))
MAX_BODY=4096; MAX_OUTPUT=64*1024; MAX_ACTIVE=4; MAX_HISTORY=12; TIMEOUTS=(30,60,120)
PROFILES={"progress":"Progress fixture","runtime":"Python runtime report","checksum":"Synthetic file checksums","tree":"Process tree fixture","output":"Output limit fixture"}
DATA.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(DATA,0o700)
LOCK=threading.RLock(); SESSIONS={}; TOKEN=secrets.token_urlsafe(32)

def cleanup_all():
    with LOCK:
        for session in SESSIONS.values():
            try: stop_process(session,"server stopped")
            except Exception: pass

atexit.register(cleanup_all)

def valid_id(value):
    if not isinstance(value,str) or len(value)!=32 or any(c not in "0123456789abcdef" for c in value): raise ValueError("Invalid session ID")
    return value

def session_record(sid):
    sid=valid_id(sid)
    if sid not in SESSIONS: raise KeyError("Session not found")
    return SESSIONS[sid]

def stop_process(session, reason="stopped"):
    proc=session["proc"]
    def child_signal(sig):
        for child in session.get("children",()):
            try:
                if os.getpgid(child)==proc.pid: os.kill(child,sig)
            except ProcessLookupError: pass
    if proc.poll() is None:
        try: os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError: pass
    else: child_signal(signal.SIGTERM)
    try: proc.wait(timeout=1)
    except subprocess.TimeoutExpired: pass
    if proc.poll() is None:
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    else: child_signal(signal.SIGKILL)
    if proc.poll() is None: proc.wait(timeout=2)
    session["state"]=reason; session["ended"]=time.time()

def watch(session):
    master=session["master"]
    try:
        while True:
            if time.time()-session["started"]>session["timeout"] and session["proc"].poll() is None:
                with LOCK: stop_process(session,"timed out")
            try: ready,_,_=select.select([master],[],[],0.2)
            except (OSError,ValueError): break
            if not ready:
                if session["proc"].poll() is not None: break
                continue
            try: chunk=os.read(master,4096)
            except OSError: break
            if not chunk: break
            with LOCK:
                session["output"].extend(chunk)
                if len(session["output"])>MAX_OUTPUT: del session["output"][:-MAX_OUTPUT]
                lines=(session.get("parse_tail",b"")+chunk).split(b"\n"); session["parse_tail"]=lines.pop()
                for line in lines:
                    if line.startswith(b"CHILD_PID:"):
                        try: session["children"].add(int(line.split(b":",1)[1]))
                        except ValueError: pass
                if session["proc"].poll() is not None and session["state"]=="running": session["state"]="finished"
    finally:
        with LOCK:
            if not session.get("master_closed"):
                try: os.close(master)
                except OSError: pass
                session["master_closed"]=True
            if session["proc"].poll() is not None and session["state"]=="running": session["state"]="finished"

def safe_view(s):
    return {"id":s["id"],"label":s["label"],"profile":s["profile"],"profile_name":PROFILES[s["profile"]],"state":s["state"],"pid":str(s["proc"].pid),"started":s["started"],"timeout":s["timeout"],"rows":s["rows"],"cols":s["cols"],"output":bytes(s["output"]).decode("utf-8","replace"),"cwd":"isolated runtime"}

class Handler(http.server.BaseHTTPRequestHandler):
    server_version="LocalConsole/1"
    def setup(self):
        super().setup(); self.connection.settimeout(3)
    def log_message(self,*_): pass
    def send_json(self,status,obj):
        data=json.dumps(obj).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(data)
    def host_ok(self): return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}")
    def state_boundary(self):
        origin=self.headers.get("Origin")
        return self.host_ok() and origin in (f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}") and secrets.compare_digest(self.headers.get("X-Console-Request",""),TOKEN)
    def get_boundary(self):
        origin=self.headers.get("Origin")
        return self.host_ok() and (origin is None or origin in (f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}")) and self.headers.get("Sec-Fetch-Site") in ("same-origin","none") and secrets.compare_digest(self.headers.get("X-Console-Request",""),TOKEN)
    def body(self):
        n=int(self.headers.get("Content-Length","-1"))
        if n<0 or n>MAX_BODY: raise ValueError("Request is too large")
        return json.loads(self.rfile.read(n))
    def do_GET(self):
        if not self.host_ok(): return self.send_json(403,{"error":"Host check failed"})
        path=self.path.split("?",1)[0]
        if path=="/": return self.static("index.html","text/html; charset=utf-8",True, "desktop=1" in self.path)
        if path=="/app.css": return self.static("app.css","text/css; charset=utf-8")
        if path=="/app.js": return self.static("app.js","text/javascript; charset=utf-8")
        if self.path=="/api/session": return self.send_json(200,{"token":TOKEN})
        if self.path=="/api/sessions":
            if not self.get_boundary(): return self.send_json(403,{"error":"Request boundary check failed"})
            with LOCK: return self.send_json(200,{"sessions":[safe_view(s) for s in SESSIONS.values()],"limits":{"active":MAX_ACTIVE,"output_bytes":MAX_OUTPUT,"timeouts":TIMEOUTS}})
        self.send_json(404,{"error":"Not found"})
    def static(self,name,mime,html=False,desktop=False):
        data=(RESOURCE_ROOT/name).read_bytes()
        if desktop: data=data.replace(b"<body>",b'<body class="native-shell">',1)
        if name=="app.css": data+=b"\nbody.native-shell main{padding-top:28px}body.native-shell .hero{margin-bottom:20px;animation:none}body.native-shell .hero h1{font-size:32px;letter-spacing:-1px}body.native-shell .panel{animation:none}\n"
        self.send_response(200); self.send_header("Content-Type",mime); self.send_header("Content-Length",str(len(data))); self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Cache-Control","no-cache")
        if html: self.send_header("Content-Security-Policy","default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"); self.send_header("Referrer-Policy","no-referrer")
        self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        if not self.state_boundary(): return self.send_json(403,{"error":"Request boundary check failed"})
        try:
            data=self.body()
            if not isinstance(data,dict): raise ValueError("Invalid request")
            parts=self.path.strip("/").split("/")
            if self.path=="/api/sessions": return self.create(data)
            sid=valid_id(parts[2]); session=session_record(sid)
            if len(parts)==4 and parts[3]=="resize":
                rows,cols=data.get("rows"),data.get("cols")
                if type(rows) is not int or type(cols) is not int or not 10<=rows<=80 or not 30<=cols<=160: raise ValueError("Resize is outside the allowed range")
                with LOCK:
                    if session.get("master_closed"): return self.send_json(409,{"error":"Session has ended"})
                    session["rows"]=rows; session["cols"]=cols
                    fcntl.ioctl(session["master"],termios.TIOCSWINSZ,struct.pack("HHHH",rows,cols,0,0))
                return self.send_json(200,{"rows":rows,"cols":cols})
            if len(parts)==4 and parts[3]=="stop":
                with LOCK: stop_process(session); return self.send_json(200,{"session":safe_view(session)})
            self.send_json(404,{"error":"Not found"})
        except KeyError: self.send_json(404,{"error":"Session not found"})
        except (ValueError,IndexError,json.JSONDecodeError,TypeError): self.send_json(400,{"error":"Invalid request"})
    def create(self,data):
        profile=data.get("profile"); label=data.get("label",""); timeout=data.get("timeout",60)
        if profile not in PROFILES or not isinstance(label,str) or not 1<=len(label.strip())<=80: return self.send_json(400,{"error":"Choose a listed tool and enter a short label"})
        if type(timeout) is not int or timeout not in TIMEOUTS: return self.send_json(400,{"error":"Choose a supported time limit"})
        with LOCK:
            active=sum(s["proc"].poll() is None for s in SESSIONS.values())
            if active>=MAX_ACTIVE: return self.send_json(429,{"error":"All four session slots are in use"})
            while len(SESSIONS)>=MAX_HISTORY:
                old=next((sid for sid,s in SESSIONS.items() if s["proc"].poll() is not None),None)
                if old is None: return self.send_json(429,{"error":"Session history is full; stop a running session first"})
                del SESSIONS[old]
            sid=secrets.token_hex(16); root=DATA/"sessions"/sid; root.mkdir(parents=True,mode=0o700)
            master,slave=pty.openpty(); rows,cols=24,100; fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack("HHHH",rows,cols,0,0))
            env={"PATH":os.defpath,"PYTHONIOENCODING":"utf-8","HOME":str(root)}
            command=([sys.executable,"--local-console-worker",profile] if getattr(sys,"frozen",False) else [sys.executable,"-I",str(ROOT/"worker.py"),profile])
            proc=subprocess.Popen(command,cwd=root,env=env,stdin=slave,stdout=slave,stderr=slave,close_fds=True,start_new_session=True)
            os.close(slave); session={"id":sid,"label":label.strip(),"profile":profile,"state":"running","proc":proc,"master":master,"output":bytearray(),"started":time.time(),"timeout":timeout,"rows":rows,"cols":cols}
            session["children"]=set(); session["master_closed"]=False; session["parse_tail"]=b""
            SESSIONS[sid]=session; reader=threading.Thread(target=watch,args=(session,),daemon=True); session["reader"]=reader; reader.start()
            return self.send_json(201,{"session":safe_view(session)})

def make_server(host="127.0.0.1", port=PORT):
    """Return an unstarted, loopback-only server with the app's request policy."""
    class LocalThreadingHTTPServer(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def server_bind(self):
            import socketserver
            socketserver.TCPServer.server_bind(self)
            self.server_name = "127.0.0.1"
            self.server_port = self.socket.getsockname()[1]

    if host != "127.0.0.1":
        raise ValueError("Local Tool Runner only binds to loopback")
    return LocalThreadingHTTPServer((host, port), Handler)


if __name__=="__main__":
    print(f"Local Tool Runner listening at http://127.0.0.1:{PORT}",flush=True)
    server=make_server(port=PORT)
    def shutdown(signum,frame): cleanup_all(); raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: cleanup_all(); server.server_close()
