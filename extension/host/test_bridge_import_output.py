import sys
import subprocess

# Test what happens when we run the bridge with no stdin
proc = subprocess.Popen(
    [sys.executable, r"C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Close stdin immediately
proc.stdin.close()

# Read stdout
out = proc.stdout.read(100)
print('stdout:', repr(out))

err = proc.stderr.read(100)
print('stderr:', repr(err))

proc.terminate()