# type: ignore
import ctypes, ctypes.util, struct, platform, pathlib, re, time, os, signal
from tinygrad.helpers import from_mv, to_mv, getenv, init_c_struct_t, colored, ansicolor, time_to_str
from hexdump import hexdump
from tinygrad.runtime.autogen import libc
from tinygrad.device import CPUProgram
import contextlib
from typing import Any

from .helpers import IOCTL, diff

IOCTL_TIMING = getenv("IOCTL_TIMING", 0)

def func_addr(f): return ctypes.cast(f, ctypes.c_void_p).value

start = time.perf_counter()
processor = platform.processor()

IOCTL_SYSCALL = {"aarch64": 0x1d, "x86_64":16}[processor]

def install_trampoline(c_func, py_func):
  c_func_addr = ctypes.cast(c_func, ctypes.c_void_p).value
  py_func_addr = ctypes.cast(py_func, ctypes.c_void_p).value

  # We are going to replace first few bytes of the C function with a trampoline to the python function.
  if processor == "aarch64":
    # 0x0000000000000000:  70 00 00 10    adr x16, #0xc
    # 0x0000000000000004:  10 02 40 F9    ldr x16, [x16]
    # 0x0000000000000008:  00 02 1F D6    br  x16
    tramp = b"\x70\x00\x00\x10\x10\x02\x40\xf9\x00\x02\x1f\xd6"
    tramp += struct.pack("Q", py_func_addr)
  elif processor == "x86_64":
    # 0x0000000000000000:  49 BB aa aa aa aa aa aa aa aa    movabs r11, <address>
    # 0x000000000000000a:  41 FF E3                         jmp    r11
    tramp = b"\x49\xBB" + struct.pack("Q", py_func_addr) + b"\x41\xFF\xE3"
  else:
    raise Exception(f"processor {processor} not supported")

  # Allow write to the page where the C function is located. Keep the page boundaries in mind.
  assert not libc.mprotect((c_func_addr//0x1000)*0x1000, 0x2000,
                            libc.PROT_READ | libc.PROT_WRITE | libc.PROT_EXEC)

  ctypes.memmove(c_func_addr, ctypes.create_string_buffer(tramp), len(tramp))

  # Clear the instruciton cache just in case
  CPUProgram.rt_lib["__clear_cache"](c_func_addr, c_func_addr+len(tramp))

fd_cache = {}
def fd_filename(fd):
  if fd < 0 or fd not in fd_cache:
    with contextlib.suppress(FileNotFoundError): fd_cache[fd] = os.readlink(f"/proc/self/fd/{fd}")
  return fd_cache.get(fd)


_ioctl_handlers = {
  # (filename[None, str, re], request[None, int, tuple(min, max)]) : handler(fs, filename, request, argp) -> (ret, dict)

}
_mmap_handlers = {}

def match_ioctl(fd, filename, request, argp):
  """
  Look for a registered handler for this type of ioctl.

  Returns the pre- and post- handlers as a tuple.

  A handler takes the iocyl arguments, and returns a tuple that contains:
    - ret code. None - do nothin, if not-None:
      - pre:  don't execute the ioctl and return ret.
      - post: the ioctl has been execured, return the alternative ret.
    - An `Diffable` `IOCTL` object, that can be used to pretty-print the difference the call did on the argp.
    - Color (str) with which to print the message. Useful for telling apart calls to different device files.
  """
  for (fn, req), h in _ioctl_handlers.items():
    if fn is None or fn == filename or (isinstance(fn, re.Pattern) and fn.search(filename)):
      if req is None or req == request or (isinstance(req, tuple) and req[0] <= request <= req[1]):
        return h if isinstance(h, tuple) else (h, h)

  return (l:=lambda fd, fname, request, argp: (None, IOCTL(fd, fname, request, argp), "black"), l) # Default fallback

_ioctl_nr = 0

def print_ioctl(nr, time, before, after, ret, errno, err_msg=None, color=None):
  timing = (" " + colored(time_to_str(time), color)) if time is not None and IOCTL_TIMING else ''
  body = ansicolor(color) + (diff(before, after, color) if after else repr(before))

  if not err_msg: err_msg = f"(Errno {errno}: {os.strerror(errno)})" if ret < 0 else "Success"
  err = colored(f"{ret} {err_msg}", 'red' if ret < 0 else 'green')
  print(f"#{nr}:{timing} {body} = {err}")

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p)
def ioctl(fd, request, argp):
  global _ioctl_nr; _ioctl_nr += 1

  fname = fd_filename(fd)
  errno = 0
  pre_handler, post_handler = match_ioctl(fd, fname, request, argp)
  bret, before, c = pre_handler(fd, fname, request, argp)
  if bret: print_ioctl(_ioctl_nr, None, before, before, bret, None, "PRE-ABORTED", c); return bret
  st = time.perf_counter()
  ret = libc.syscall(IOCTL_SYSCALL, ctypes.c_int(fd), ctypes.c_ulong(request), ctypes.c_void_p(argp))
  et = time.perf_counter()-st
  if ret < 0: errno=ctypes.get_errno()
  aret, after, c = post_handler(fd, fname, request, argp)
  if aret: print_ioctl(_ioctl_nr, None, before, after, aret, None, "POST-ABORTED", c); return aret

  print_ioctl(_ioctl_nr, et, before, after, ret, errno, None, c)

  # if ret < 0: ctypes.set_errno(errno) # XXX Correctly set the errno in libc to relay the error reason
  return ret


@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long)
def mmap(fd, request, argp):
  fn = os.readlink(f"/proc/self/fd/{fd}")
  print(f"IOCTL: {fd=} ({fn}), {request=}, {argp=}")
  return 0

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)
def close(fd): fd_cache.pop(fd, None)

_installed = False
def install_hooks(ioctl_handlers=None, mmap_handlers=None):
  global _ioctl_handlers, _mmap_handlers, _installed
  if ioctl_handlers: _ioctl_handlers = { **ioctl_handlers, **_ioctl_handlers }
  if mmap_handlers: _mmap_handlers = { **mmap_handlers, **_mmap_handlers }

  if not _installed:
    _installed = True
    install_trampoline(libc.ioctl, ioctl)
  # install_hook(libc.mmap, mmap)
  # install_hook(libc.close, close) # Note: There might be other ways to close an fd, like dup2, dup3, etc.

install_hooks()

if getenv("IOCTL_NV", 0) >= 1:
  from .nv_ioctl_nvidiactl import ioctl_handlers as ctrl_ioctl_handler, mmap_handlers as ctrl_mmap_handlers
  from .nv_ioctl_nvidia_uvm import ioctl_handlers as uvm_ioctl_handlers, mmap_handlers as uvm_mmap_handlers

  install_hooks(ctrl_ioctl_handler, ctrl_mmap_handlers)

  install_hooks(uvm_ioctl_handlers, uvm_mmap_handlers)
