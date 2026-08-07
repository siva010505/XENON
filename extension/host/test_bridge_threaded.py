import sys
import json
import struct
import subprocess
import threading
import time

def read_stream(stream, name, output_list):
    for line in iter(stream.readline, b''):
        output_list.append((name, line.decode('utf-8', errors='replace').rstrip()))

# Launch the bridge
proc = subprocess.Popen(
    [sys.executable, r"C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

stderr_output = []
stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, "stderr", stderr_output))
stderr_thread.daemon = True
stderr_thread.start()

# Give it a moment to start
time.sleep(1)

# Create the PING message
msg = json.dumps({'type': 'PING'}).encode('utf-8')
header = struct.pack('@I', len(msg))

# Send the message
print("Sending PING...")
proc.stdin.write(header)
proc.stdin.write(msg)
proc.stdin.flush()

# Wait for response
time.sleep(3)

# Read response
try:
    response_header = proc.stdout.read(4)
    if response_header:
        response_len = struct.unpack('@I', response_header)[0]
        response = proc.stdout.read(response_len)
        print("Response:", response.decode('utf-8'))
    else:
        print("No response header received")
except Exception as e:
    print("Error reading response:", e)

# Print any stderr output
for name, line in stderr_output:
    print(f"[{name}] {line}")

proc.terminate()