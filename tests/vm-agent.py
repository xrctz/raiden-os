#!/usr/bin/env python3
"""Test-VM command agent (TEST VMs ONLY - never put this on a real system).

Listens on TCP 2222 inside the VM; each connection sends one shell command
and half-closes, the agent replies with the command output. The host reaches
it through QEMU's user-mode port forward (hostfwd tcp::2222-:2222); see
tests/vmexec.py. Equivalent one-liner for typing into a VM console:

  sudo setsid python3 -c 'exec("import socket as S,subprocess as P\\ns=S.socket();s.setsockopt(1,2,1);s.bind((\\"\\",2222));s.listen()\\nwhile 1:\\n c=s.accept()[0];d=b\\"\\"\\n while x:=c.recv(65536):d+=x\\n r=P.run(d.decode(),shell=1,capture_output=1,text=1);c.sendall((r.stdout+r.stderr).encode());c.close()")' &
"""
import socket
import subprocess

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("", 2222))
srv.listen()
while True:
    conn = srv.accept()[0]
    data = b""
    while chunk := conn.recv(65536):
        data += chunk
    res = subprocess.run(data.decode(), shell=True, capture_output=True, text=True)
    conn.sendall((res.stdout + res.stderr).encode())
    conn.close()
