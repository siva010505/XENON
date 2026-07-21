import sys
import struct
import json
import os
import subprocess

def get_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        sys.exit(0)
    message_length = struct.unpack('@I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def send_message(message):
    encoded_content = json.dumps(message).encode('utf-8')
    encoded_length = struct.pack('@I', len(encoded_content))
    sys.stdout.buffer.write(encoded_length)
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()

def main():
    while True:
        try:
            msg = get_message()
            
            if msg.get('action') == 'start_server':
                current_dir = os.path.dirname(os.path.abspath(__file__))
                backend_dir = os.path.join(current_dir, 'backend')
                uvicorn_exe = os.path.join(backend_dir, 'venv', 'Scripts', 'uvicorn.exe')
                
                if os.path.exists(uvicorn_exe):
                    # Launch uvicorn completely silently in the background but log to file
                    log_file = open(os.path.join(current_dir, "server.log"), "w")
                    subprocess.Popen([uvicorn_exe, "server:app", "--host", "127.0.0.1", "--port", "8000"],
                                     cwd=backend_dir,
                                     stdin=subprocess.DEVNULL,
                                     stdout=log_file,
                                     stderr=subprocess.STDOUT,
                                     creationflags=0x08000000)
                    
                    send_message({"status": "success", "message": "Server started silently."})
                else:
                    send_message({"status": "error", "message": "uvicorn.exe not found."})
                    
            elif msg.get('action') == 'ping':
                send_message({"status": "success", "message": "Host is alive."})
            
        except Exception as e:
            send_message({"status": "error", "message": str(e)})

if __name__ == '__main__':
    main()
