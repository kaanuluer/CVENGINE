#!/usr/bin/env python3
"""Double-fork a command so it survives parent shell / process-group teardown."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chdir", default="")
    parser.add_argument("--log", default="")
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("detach.py: missing command", file=sys.stderr)
        return 2

    # First fork
    if os.fork() > 0:
        return 0
    os.setsid()
    # Second fork
    if os.fork() > 0:
        os._exit(0)

    if args.chdir:
        os.chdir(args.chdir)

    # Redirect stdio
    log_fd = None
    if args.log:
        log_fd = os.open(args.log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        os.close(log_fd)
    else:
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
    try:
        null_in = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null_in, 0)
        os.close(null_in)
    except OSError:
        pass

    os.environ.setdefault("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    os.execvpe(cmd[0], cmd, os.environ)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
