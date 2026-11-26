#!/usr/bin/env python3
"""Private, fixed-destination Gitea bridge for rootless runner jobs.

The only upstream is the existing host Gitea listener at 127.0.0.1:3000.
Jobs receive this Unix socket, never host loopback or the Docker API socket.
"""

import argparse
import os
import socket
import threading


UPSTREAM = ("127.0.0.1", 3000)


def relay(source: socket.socket, target: socket.socket) -> None:
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            target.sendall(data)
    except OSError:
        pass
    finally:
        try:
            target.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle(client: socket.socket) -> None:
    try:
        upstream = socket.create_connection(UPSTREAM, timeout=10)
    except OSError:
        client.close()
        return
    a = threading.Thread(target=relay, args=(client, upstream), daemon=True)
    b = threading.Thread(target=relay, args=(upstream, client), daemon=True)
    a.start()
    b.start()
    a.join()
    b.join()
    client.close()
    upstream.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    path = os.path.abspath(args.socket)
    if os.path.lexists(path):
        info = os.lstat(path)
        if not os.path.islink(path) and __import__("stat").S_ISSOCK(info.st_mode):
            os.unlink(path)
        else:
            raise SystemExit("refusing to replace non-socket bridge path")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    os.chmod(path, 0o660)
    server.listen(16)
    try:
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle, args=(client,), daemon=True).start()
    finally:
        server.close()
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
