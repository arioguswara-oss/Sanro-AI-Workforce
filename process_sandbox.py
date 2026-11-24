"""Unprivileged seccomp deny policy for worker children (Linux x86_64/aarch64)."""
import ctypes
import errno
import os
import platform


_DENIED = {
    "x86_64": {41, 42, 43, 44, 45, 46, 47, 49, 50, 53, 56, 57, 58, 62, 101, 109, 112, 165, 166, 200, 234, 272, 288, 299, 307, 308, 310, 311, 424, 425, 434},
    "aarch64": {39, 40, 97, 117, 129, 130, 131, 154, 157, 198, 199, 200, 201, 202, 203, 206, 207, 211, 212, 243, 268, 269, 270, 271, 424, 425, 434, 435},
}


class SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(SockFilter))]


def apply_process_policy() -> None:
    """Deny sockets, network syscalls and process escape/inspection primitives.

    The policy is inherited by fork/exec descendants. Unsupported kernels or
    architectures fail closed; this remains defense-in-depth, not a VM boundary.
    """
    machine = platform.machine().lower()
    denied = _DENIED.get(machine)
    if platform.system() != "Linux" or denied is None:
        raise OSError(errno.ENOTSUP, "worker seccomp profile unsupported on this platform")
    instructions = [SockFilter(0x20, 0, 0, 0)]  # BPF_LD | BPF_W | BPF_ABS (seccomp_data.nr)
    for syscall in sorted(denied):
        instructions.append(SockFilter(0x15, 0, 1, syscall))  # BPF_JMP | JEQ; mismatch skips next deny
        instructions.append(SockFilter(0x06, 0, 0, 0x00050000 | errno.EPERM))  # SECCOMP_RET_ERRNO
    instructions.append(SockFilter(0x06, 0, 0, 0x7FFF0000))  # SECCOMP_RET_ALLOW
    array = (SockFilter * len(instructions))(*instructions)
    program = SockFprog(len(instructions), array)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        code = ctypes.get_errno(); raise OSError(code, os.strerror(code))
    if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:  # PR_SET_SECCOMP, FILTER
        code = ctypes.get_errno(); raise OSError(code, os.strerror(code))
