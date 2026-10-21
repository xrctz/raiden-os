"""Copy a file into the test VM through tests/vm-agent.py (no size limit, unlike
a command line).

    vmput.py LOCAL_FILE REMOTE_PATH [MODE]
"""
import base64
import socket
import sys

local, remote = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "644"
data = base64.b64encode(open(local, "rb").read()).decode()
cmd = (f"base64 -d > '{remote}.vmput' <<'VMPUT_EOF'\n{data}\nVMPUT_EOF\n"
       f"chmod {mode} '{remote}.vmput' && mv -f '{remote}.vmput' '{remote}' && "
       f"echo \"put {remote} $(stat -c %s '{remote}') bytes\"")
s = socket.create_connection(("127.0.0.1", 2222), timeout=300)
s.sendall(cmd.encode())
s.shutdown(socket.SHUT_WR)
out = b""
while chunk := s.recv(65536):
    out += chunk
sys.stdout.write(out.decode(errors="replace"))
