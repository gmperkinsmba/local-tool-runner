"""Fixed, harmless worker profiles launched by server.py."""
import hashlib, platform, signal, subprocess, sys, time

def progress():
    for step in range(1, 11):
        print(f"fixture step {step:02d}/10 · {step * 10}%", flush=True)
        time.sleep(0.7)
    print("fixture complete", flush=True)

def runtime():
    print(f"Python {platform.python_version()}", flush=True)
    print(f"Platform {platform.system()} {platform.machine()}", flush=True)
    print(f"Terminal {__import__('shutil').get_terminal_size((80, 24)).columns} × {__import__('shutil').get_terminal_size((80, 24)).lines}", flush=True)

def checksum():
    fixtures=(b"synthetic console fixture one\n",b"synthetic console fixture two\n")
    for i,data in enumerate(fixtures,1): print(f"fixture-{i}.txt  {len(data)} bytes  sha256 {hashlib.sha256(data).hexdigest()}",flush=True)

def process_tree():
    child=None
    def reap(signum,frame):
        if child is not None:
            if child.poll() is None: child.terminate()
            try: child.wait(timeout=2)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,reap)
    command=([sys.executable,"--local-console-worker","child"] if getattr(sys,"frozen",False) else [sys.executable,"-I",__file__,"child"])
    child=subprocess.Popen(command,close_fds=True,start_new_session=False)
    print(f"CHILD_PID:{child.pid}",flush=True)
    while child.poll() is None: time.sleep(0.2)
    print("child process ended",flush=True)

def output_limit():
    for i in range(6000): print(f"bounded output fixture row {i:05d} · synthetic text",flush=True)

def child():
    while True: time.sleep(1)

PROFILES={"progress":progress,"runtime":runtime,"checksum":checksum,"tree":process_tree,"output":output_limit,"child":child}
if __name__=="__main__":
    name=sys.argv[1]
    if name not in PROFILES: raise SystemExit(2)
    PROFILES[name]()
