import sys
import json
import struct
import subprocess

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
proc.stdin.write(header)
proc.stdin.write(msg)
proc.stdin.flush()

# Wait a bit for processing
import time
time.sleep(2)

# Read response
try:
    response_header = proc.stdout.read(4)
    if response_header:
        response_len = struct.unpack('@I', response_header)[0]
        response = proc.stdout.read(response_len)
        print("Response:", response.decode('utf-8'))
    else:
        stderr = proc.stderr.read()
        print("No response. Stderr:", stderr.decode('utf-8') if stderr else "empty")
except Exception as e:
    print("Error:", e)
    stderr = proc.stderr.read()
    print("Stderr:", stderr.decode('utf-8') if stderr else "empty")
finally:
    proc.terminate()