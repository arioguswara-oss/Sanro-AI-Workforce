"""Linux Landlock filesystem boundary for JD-04 child commands (fail closed)."""
import ctypes
import errno
import os
import platform

NR_CREATE_RULESET = 444
NR_ADD_RULE = 445
NR_RESTRICT_SELF = 446
RULE_PATH_BENEATH = 1
CREATE_VERSION = 1
EXECUTE = 1 << 0
WRITE_FILE = 1 << 1
READ_FILE = 1 << 2
READ_DIR = 1 << 3
REMOVE_DIR = 1 << 4
REMOVE_FILE = 1 << 5
MAKE_CHAR = 1 << 6
MAKE_DIR = 1 << 7
MAKE_REG = 1 << 8
MAKE_SOCK = 1 << 9
MAKE_FIFO = 1 << 10
MAKE_BLOCK = 1 << 11
MAKE_SYM = 1 << 12
REFER = 1 << 13
TRUNCATE = 1 << 14
READ_ACCESS = EXECUTE | READ_FILE | READ_DIR
WRITE_ACCESS = WRITE_FILE | REMOVE_DIR | REMOVE_FILE | MAKE_CHAR | MAKE_DIR | MAKE_REG | MAKE_SOCK | MAKE_FIFO | MAKE_BLOCK | MAKE_SYM | REFER | TRUNCATE


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32), ("reserved", ctypes.c_uint32)]


def _syscall(number, *args):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(number, *args)
    if result < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return result


def landlock_abi():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "aarch64"}:
        return 0
    try:
        return _syscall(NR_CREATE_RULESET, ctypes.c_void_p(), 0, CREATE_VERSION)
    except OSError:
        return 0


def apply_landlock(workspace: str, job_tmp: str) -> None:
    """Restrict the calling child to read-only system paths and writable project paths."""
    abi = landlock_abi()
    if abi < 1:
        raise OSError(errno.ENOTSUP, "Landlock unavailable; refusing unsandboxed execution")
    handled = READ_ACCESS | WRITE_ACCESS
    if abi < 2:
        handled &= ~REFER
    if abi < 3:
        handled &= ~TRUNCATE
    attr = RulesetAttr(handled)
    ruleset_fd = _syscall(NR_CREATE_RULESET, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    fds = [ruleset_fd]
    try:
        workspace = os.path.realpath(workspace)
        job_tmp = os.path.realpath(job_tmp)
        grants = [(workspace, handled), (job_tmp, handled)]
        grants += [(path, READ_ACCESS) for path in ("/usr", "/bin", "/lib", "/lib64") if os.path.exists(path)]
        grants += [(path, READ_FILE) for path in ("/etc/ld.so.cache", "/dev/null", "/dev/urandom") if os.path.exists(path)]
        for path, rights in grants:
            fd = os.open(path, getattr(os, "O_PATH", os.O_RDONLY) | os.O_CLOEXEC)
            fds.append(fd)
            rule = PathBeneathAttr(rights & handled, fd, 0)
            _syscall(NR_ADD_RULE, ruleset_fd, RULE_PATH_BENEATH, ctypes.byref(rule), 0)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))
        _syscall(NR_RESTRICT_SELF, ruleset_fd, 0)
    finally:
        for fd in fds:
            try: os.close(fd)
            except OSError: pass
