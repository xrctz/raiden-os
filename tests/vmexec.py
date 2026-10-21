#!/usr/bin/env python3
"""Run a shell command inside the test VM through tests/vm-agent.py.

    vmexec.py 'journalctl -b | tail'
"""
import socket
import sys

cmd = " ".join(sys.argv[1:])
s = socket.create_connection(("127.0.0.1", 2222), timeout=900)
s.sendall(cmd.encode())
s.shutdown(socket.SHUT_WR)
out = b""
while True:
    chunk = s.recv(65536)
    if not chunk:
        break
    out += chunk
sys.stdout.write(out.decode(errors="replace"))
