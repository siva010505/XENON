@echo off
python -c "
import sys, json, struct
msg = json.dumps({'type': 'PING'}).encode('utf-8')
sys.stdout.buffer.write(struct.pack('@I', len(msg)))
sys.stdout.buffer.write(msg)
sys.stdout.buffer.flush()
" | python "C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py" 2>&1