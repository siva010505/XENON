import os
import sys
import json
import struct
import socket
import subprocess

PORT = 7788
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(PROJECT_DIR, "server.py")


def is_server_running(port=PORT):
    """Check if FastAPI server is listening on port 7788."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        res = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return res == 0
    except Exception:
        return False


def start_server_silently():
    """Start server.py in 100% silent background mode without command prompt."""
    if is_server_running():
        return True

    python_executable = sys.executable
    # On Windows, pythonw.exe runs without creating any command window
    pythonw_path = os.path.join(os.path.dirname(python_executable), "pythonw.exe")
    exec_path = pythonw_path if os.path.exists(pythonw_path) else python_executable

    # Windows flags for completely detached, hidden process
    creationflags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS

    try:
        subprocess.Popen(
            [exec_path, SERVER_SCRIPT],
            cwd=PROJECT_DIR,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except Exception as e:
        # Fallback to standard Popen
        try:
            subprocess.Popen(
                [exec_path, SERVER_SCRIPT],
                cwd=PROJECT_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False


def read_message():
    """Read a Chrome Native Message from sys.stdin.buffer."""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length or len(raw_length) < 4:
            return None
        length = struct.unpack("@I", raw_length)[0]
        raw_msg = sys.stdin.buffer.read(length)
        if not raw_msg or len(raw_msg) < length:
            return None
        return json.loads(raw_msg.decode("utf-8"))
    except Exception:
        return None


def send_message(response):
    """Send a Chrome Native Message to sys.stdout.buffer."""
    try:
        msg_bytes = json.dumps(response).encode("utf-8")
        sys.stdout.buffer.write(struct.pack("@I", len(msg_bytes)))
        sys.stdout.buffer.write(msg_bytes)
        sys.stdout.buffer.flush()
    except Exception:
        pass


def main():
    msg = read_message()
    if not msg:
        # If run directly from command line for testing:
        if not is_server_running():
            start_server_silently()
        sys.exit(0)

    action = msg.get("action") or msg.get("command") or "start"

    if action in ["start", "launch", "ping"]:
        running_before = is_server_running()
        if not running_before:
            start_server_silently()
        send_message({
            "status": "ok",
            "server_running": is_server_running(),
            "started_now": not running_before
        })
    elif action == "status":
        send_message({
            "status": "ok",
            "server_running": is_server_running()
        })
    else:
        send_message({"status": "unknown_command"})


if __name__ == "__main__":
    main()
