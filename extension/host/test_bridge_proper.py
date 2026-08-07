import sys
import json
import struct
import subprocess
import os

# Create the PING message
msg = json.dumps({'type': 'PING'}).encode('utf-8')
header = struct.pack('@I', len(msg))

# Launch the bridge
proc = subprocess.Popen(
    [sys.executable, r"C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Send the message
print("Sending PING...", file=sys.stderr)
proc.stdin.write(header)
proc.stdin.write(msg)
proc.stdin.flush()

# Read response header (4 bytes)
print("Reading response header...", file=sys.stderr)
response_header = b''
while len(response_header) < 4:
    chunk = proc.stdout.read(4 - len(response_header))
    if not chunk:
        break
    response_header += chunk

print(f"Response header bytes: {response_header!r}", file=sys.stderr)

if len(response_header) == 4:
    response_len = struct.unpack('@I', response_header)[0]
    print(f"Response length: {response_len}", file=sys.stderr)
    
    # Read response body
    response_body = b''
    while len(response_body) < response_len:
        chunk = proc.stdout.read(response_len - len(response_body))
        if not chunk:
            break
        response_body += chunk
    
    print(f"Response body bytes: {response_body!r}", file=sys.stderr)
    print("Response:", response_body.decode('utf-8'))
else:
    stderr = proc.stderr.read()
    print("No response header. Stderr:", stderr.decode('utf-8') if stderr else "empty", file=sys.stderr)

proc.terminate()