import argparse
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import pty
import os
import subprocess
import select
import signal
import termios
import struct
import fcntl
import shlex
import logging
import sys
import webbrowser

logging.getLogger("werkzeug").setLevel(logging.ERROR)

__version__ = "0.5.0.2"

app = Flask(__name__, template_folder=".", static_folder=".", static_url_path="")
app.config["SECRET_KEY"] = "secret!"
# Per-client PTY state: map session id -> {fd, pid}
app.config["clients"] = {}
# Use eventlet async mode when available and allow cross-origin requests from the same origin.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


def set_winsize(fd, row, col, xpix=0, ypix=0):
    logging.debug("setting window size with termios")
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def read_and_forward_pty_output(sid: str):
    """Background task that reads from a single client's PTY and forwards output."""
    max_read_bytes = 1024 * 20
    while True:
        socketio.sleep(0.01)
        client = app.config["clients"].get(sid)
        if not client:
            return
        fd = client.get("fd")
        if not fd:
            return
        timeout_sec = 0
        try:
            (data_ready, _, _) = select.select([fd], [], [], timeout_sec)
        except Exception:
            data_ready = []
        if data_ready:
            try:
                raw = os.read(fd, max_read_bytes)
                if not raw:
                    raise OSError("pty closed")
                output = raw.decode(errors="ignore")
                # Emit only to this client (use room = sid)
                socketio.emit("pty-output", {"output": output}, namespace="/pty", to=sid)
            except OSError:
                logging.exception("pty read error for sid %s, cleaning up", sid)
                # Attempt to reap child
                try:
                    pid = client.get("pid")
                    if pid:
                        os.waitpid(pid, os.WNOHANG)
                except Exception:
                    pass
                # cleanup
                try:
                    os.close(fd)
                except Exception:
                    pass
                app.config["clients"].pop(sid, None)
                socketio.emit("pty-closed", {"reason": "pty closed"}, namespace="/pty", to=sid)
                return


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("pty-input", namespace="/pty")
def pty_input(data):
    """write to the child pty. The pty sees this as if you are typing in a real
    terminal.
    """
    sid = request.sid
    client = app.config["clients"].get(sid)
    if client and client.get("fd"):
        logging.debug("received input from browser (sid=%s): %s", sid, data["input"])
        try:
            os.write(client.get("fd"), data["input"].encode())
        except OSError:
            logging.exception("pty write error for sid %s; cleaning up", sid)
            try:
                pid = client.get("pid")
                if pid:
                    os.waitpid(pid, os.WNOHANG)
            except Exception:
                pass
            try:
                os.close(client.get("fd"))
            except Exception:
                pass
            app.config["clients"].pop(sid, None)
            socketio.emit("pty-closed", {"reason": "pty write error"}, namespace="/pty", to=sid)


@socketio.on("resize", namespace="/pty")
def resize(data):
    sid = request.sid
    client = app.config["clients"].get(sid)
    if client and client.get("fd"):
        logging.debug(f"Resizing window for sid {sid} to {data['rows']}x{data['cols']}")
        set_winsize(client.get("fd"), data["rows"], data["cols"])


@socketio.on("connect", namespace="/pty")
def connect():
    """new client connected: spawn a dedicated PTY for this sid."""
    sid = request.sid
    logging.info("new client connected: %s", sid)

    # If this sid already has a client (reconnect), clean it up first
    existing = app.config["clients"].get(sid)
    if existing:
        try:
            pid = existing.get("pid")
            if pid:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            fd = existing.get("fd")
            if fd:
                os.close(fd)
        except Exception:
            pass
        app.config["clients"].pop(sid, None)

    (child_pid, fd) = pty.fork()
    if child_pid == 0:
        # Ensure the child runs with the script's directory as CWD so
        # relative paths like "game.py" resolve correctly even when
        # the parent process was started from a different directory.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(app.config["cmd"], cwd=script_dir)
    else:
        app.config["clients"][sid] = {"fd": fd, "pid": child_pid}
        set_winsize(fd, 50, 50)
        cmd = " ".join(shlex.quote(c) for c in app.config["cmd"])
        socketio.start_background_task(read_and_forward_pty_output, sid)
        logging.info("spawned child pid %s for sid %s", child_pid, sid)
        logging.info(
            "starting background task with command `%s` to continously read and forward pty output to client %s",
            cmd,
            sid,
        )


@socketio.on("disconnect", namespace="/pty")
def disconnect():
    """Clean up PTY and child process when a client disconnects."""
    sid = request.sid
    logging.info("client disconnected: %s", sid)
    client = app.config["clients"].pop(sid, None)
    if not client:
        return
    try:
        pid = client.get("pid")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                os.waitpid(pid, 0)
            except Exception:
                pass
    except Exception:
        pass
    try:
        fd = client.get("fd")
        if fd:
            try:
                os.close(fd)
            except Exception:
                pass
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description=(
            "A fully functional terminal in your browser. "
            "https://github.com/cs01/pyxterm.js"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-p", "--port", default=5050, help="port to run server on", type=int
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="host to run server on (use 0.0.0.0 to allow access from other hosts)",
    )
    parser.add_argument("--debug", action="store_true", help="debug the server")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument(
        "--command", default="python3", help="Command to run in the terminal"
    )
    parser.add_argument(
        "--cmd-args",
        default="game.py",
        help="arguments to pass to command (i.e. --cmd-args='arg1 arg2 --flag')",
    )
    args = parser.parse_args()
    if args.version:
        print(__version__)
        exit(0)
    # If the user requested the generic 'python' or 'python3', prefer using
    # the current interpreter (`sys.executable`) so child processes use the
    # same Python environment (important when running inside a venv).
    if args.command in ("python", "python3"):
        python_cmd = sys.executable
    else:
        python_cmd = args.command
    app.config["cmd"] = [python_cmd] + shlex.split(args.cmd_args)
    green = "\033[92m"
    end = "\033[0m"
    log_format = (
        green
        + "pyxtermjs > "
        + end
        + "%(levelname)s (%(funcName)s:%(lineno)s) %(message)s"
    )
    logging.basicConfig(
        format=log_format,
        stream=sys.stdout,
        level=logging.DEBUG if args.debug else logging.INFO,
    )
    display_host = args.host
    # webbrowser cannot open 0.0.0.0 — prefer localhost for the browser URL
    if args.host in ("0.0.0.0", "::", "::0"):
        display_host = "localhost"
    url = f"http://{display_host}:{args.port}/index.html"
    logging.info(f"serving on http://{args.host}:{args.port}")
    webbrowser.open_new_tab(url)
    socketio.run(app, debug=args.debug, port=args.port, host=args.host, allow_unsafe_werkzeug=True)
    


if __name__ == "__main__":
    main()
