import subprocess
import sys
import time

proc = subprocess.Popen([sys.executable, '-c', 'print("hello"); import sys; sys.stdout.flush()'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(1)
out, err = proc.communicate()
print('stdout:', out.decode())
print('stderr:', err.decode())