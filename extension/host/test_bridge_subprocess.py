import subprocess
import sys
import time

# Launch the bridge with no stdin (should exit immediately)
proc = subprocess.Popen([sys.executable, r"C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Close stdin immediately to simulate EOF
proc.stdin.close()

# Wait for process to exit
time.sleep(2)

out, err = proc.communicate(timeout=5)
print('returncode:', proc.returncode)
print('stdout:', out.decode('utf-8', errors='replace') if out else 'empty')
print('stderr:', err.decode('utf-8', errors='replace') if err else 'empty')