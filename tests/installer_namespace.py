#!/usr/bin/env python3
"""Run a command in an authorized subordinate-UID namespace (no mount changes).

Host mapped uid/gid -> namespace root; configured subordinate range -> other IDs.
Caller must still provide bwrap filesystem/pid isolation for system commands.
"""
import ctypes, os, pwd, subprocess, sys

def subordinate(path):
    username = pwd.getpwuid(os.getuid()).pw_name
    for line in open(path):
        name, start, count = line.strip().split(":")
        if name in (username, str(os.getuid())) and int(count) >= 65536:
            return start
    raise SystemExit("Need an existing subordinate UID/GID range of at least 65536; never change host mappings in this test.")

uid_start = subordinate("/etc/subuid")
gid_start = subordinate("/etc/subgid")

read_ready,write_ready=os.pipe()
read_go,write_go=os.pipe()
pid=os.fork()
if pid==0:
    os.close(read_ready);os.close(write_go)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.unshare(0x10000000)!=0:
        raise OSError(ctypes.get_errno(),'unshare(CLONE_NEWUSER)')
    os.write(write_ready,b'1');os.close(write_ready)
    if os.read(read_go,1)!=b'1':os._exit(126)
    os.close(read_go)
    os.setgid(0);os.setuid(0)
    os.execvp(sys.argv[1],sys.argv[1:])
os.close(write_ready);os.close(read_go)
if os.read(read_ready,1)!=b'1':sys.exit(125)
os.close(read_ready)
try:
    subprocess.run(['newuidmap',str(pid),'0',str(os.getuid()),'1','1',uid_start,'65536'],check=True)
    subprocess.run(['newgidmap',str(pid),'0',str(os.getgid()),'1','1',gid_start,'65536'],check=True)
    os.write(write_go,b'1')
finally:os.close(write_go)
_,status=os.waitpid(pid,0)
sys.exit(os.waitstatus_to_exitcode(status))
