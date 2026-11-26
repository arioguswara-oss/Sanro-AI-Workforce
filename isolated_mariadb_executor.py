"""Narrow, synthetic-only MariaDB acceptance using an owned temporary datadir."""
from __future__ import annotations

import json
import os
import pathlib
import pwd
import shutil
import subprocess
import tempfile
import time


class IsolatedMariaDBError(RuntimeError):
    pass


def run_synthetic_acceptance(timeout_seconds: int = 90) -> dict:
    if type(timeout_seconds) is not int or not 15 <= timeout_seconds <= 180:
        raise ValueError("timeout must be between 15 and 180 seconds")
    server = shutil.which("mariadbd")
    installer = shutil.which("mariadb-install-db")
    client = shutil.which("mariadb")
    admin = shutil.which("mariadb-admin")
    if not all((server, installer, client, admin)):
        raise IsolatedMariaDBError("MariaDB server, installer, client and admin binaries are required")
    username = pwd.getpwuid(os.getuid()).pw_name
    if not username or username.startswith("-"):
        raise IsolatedMariaDBError("current runtime user cannot be safely resolved")

    owned = tempfile.TemporaryDirectory(prefix=f"sanro-workforce-mariadb-{os.getuid()}-")
    root = pathlib.Path(owned.name)
    datadir, socket_path, pid_path, log_path = (root / "data", root / "db.sock", root / "db.pid", root / "mariadb.log")
    datadir.mkdir(mode=0o700)
    init_log = root / "initialize.log"
    server_log = root / "server.stdout.log"
    process = None
    started = time.monotonic()
    deadline = started + timeout_seconds
    try:
        with init_log.open("wb") as out:
            initialized = subprocess.run(
                [installer, "--no-defaults", f"--datadir={datadir}", "--auth-root-authentication-method=normal", "--skip-test-db", f"--user={username}"],
                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, timeout=min(35, max(1, deadline - time.monotonic())), check=False,
                env={"PATH": "/usr/bin:/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": str(root), "TMPDIR": str(root)})
        if initialized.returncode:
            raise IsolatedMariaDBError("isolated MariaDB initialization failed; bounded diagnostics stored in temporary job directory")

        args = [server, "--no-defaults", f"--datadir={datadir}", f"--socket={socket_path}", f"--pid-file={pid_path}", f"--log-error={log_path}", f"--tmpdir={root}", f"--user={username}", "--skip-networking", "--skip-name-resolve", "--performance-schema=OFF", "--innodb-buffer-pool-size=32M", "--aria-pagecache-buffer-size=16M"]
        with server_log.open("wb") as out:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True,
                                       env={"PATH": "/usr/bin:/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": str(root), "TMPDIR": str(root)})

        def query(sql: str) -> str:
            if process.poll() is not None:
                raise IsolatedMariaDBError("isolated MariaDB process exited before query")
            result = subprocess.run([client, "--no-defaults", "--protocol=SOCKET", f"--socket={socket_path}", "--user=root", "--batch", "--skip-column-names", "--connect-timeout=2", f"--execute={sql}"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=min(5, max(1, deadline - time.monotonic())), check=False,
                                    env={"PATH": "/usr/bin:/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": str(root)})
            if result.returncode:
                raise IsolatedMariaDBError("synthetic SQL operation failed")
            return result.stdout.decode("utf-8", "replace").strip()

        startup_deadline = min(deadline, time.monotonic() + min(25, timeout_seconds / 2))
        ready = False
        while time.monotonic() < startup_deadline and process.poll() is None:
            if socket_path.exists():
                try:
                    if query("SELECT 1") == "1":
                        ready = True
                        break
                except (OSError, subprocess.SubprocessError, IsolatedMariaDBError):
                    pass
            time.sleep(0.2)
        if not ready:
            snippets = []
            for path in (init_log, log_path, server_log):
                try:
                    lines = path.read_text(errors="replace").splitlines()[-10:]
                    if lines:
                        snippets.append(path.name + ": " + " | ".join(lines))
                except OSError:
                    pass
            detail = " ".join(snippets).replace(str(root), "<job-temp>")
            raise IsolatedMariaDBError("isolated MariaDB did not become ready within the bound" + ("; " + detail if detail else ""))

        if query("SELECT @@skip_networking") != "1":
            raise IsolatedMariaDBError("MariaDB network listener is not disabled")
        query("CREATE DATABASE sanro_synthetic")
        query("CREATE TABLE sanro_synthetic.records (id INT PRIMARY KEY, value_text VARCHAR(40) NOT NULL)")
        query("INSERT INTO sanro_synthetic.records VALUES (1, 'GDI02R_SYNTHETIC'), (2, 'LOCAL_ONLY')")
        actual = query("SELECT CONCAT(id, ':', value_text) FROM sanro_synthetic.records ORDER BY id")
        if actual != "1:GDI02R_SYNTHETIC\n2:LOCAL_ONLY":
            raise IsolatedMariaDBError("synthetic SQL result did not match expected rows")
        return {"status": "PASS", "server_version": query("SELECT VERSION()"), "network_disabled": True,
                "synthetic_rows_verified": 2, "duration_seconds": round(time.monotonic() - started, 3), "resource_scope": "unique temporary datadir/socket/pid/log"}
    finally:
        if process is not None and process.poll() is None:
            try:
                subprocess.run([admin, "--no-defaults", "--protocol=SOCKET", f"--socket={socket_path}", "--user=root", "--connect-timeout=2", "shutdown"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4, check=False,
                               env={"PATH": "/usr/bin:/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": str(root)})
                process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        owned.cleanup()


if __name__ == "__main__":
    try:
        print(json.dumps(run_synthetic_acceptance(), sort_keys=True))
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "reason": type(error).__name__ + ": " + str(error)}))
        raise SystemExit(1)
