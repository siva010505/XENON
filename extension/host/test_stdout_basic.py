import sys
import subprocess

proc = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"TEST")'], stdout=subprocess.PIPE)
out = proc.stdout.read(4)
print('Got:', repr(out))
proc.terminate()