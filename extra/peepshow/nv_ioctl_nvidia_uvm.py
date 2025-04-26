from .helpers import IOCTL, Diffable, HexInt, NamedHexInt, raw_repr, get_struct, colored
from dataclasses import dataclass, Field, field
from tinygrad.runtime.autogen import nv_gpu
from types import NoneType
import ctypes
import sys

def get_nv_uvm(name):
    if name.startswith("UVM"):
        t =  getattr(nv_gpu, tn:=(name + "_PARAMS"), NoneType)
        if t is not NoneType:
            return (name, getattr(nv_gpu, name), tn, t)
    return None

NV_UVM = { type(name, (NamedHexInt,), {})(nvtT[1], 8): (nvtT[2], nvtT[3]) for name in dir(nv_gpu) if (nvtT := get_nv_uvm(name)) }

# Sanity check
for name, (tname, ttype) in dict(sorted(NV_UVM.items())).items():
    if ttype is NoneType: print("Warning: Missing parameters for {name}")
    # print(name, tname, ttype)


def nvidia_uvm(fd, file, cmd, arg):
    if cmd in NV_UVM:
        cmd = next(u for u in NV_UVM if u == cmd)
        pname, ptype = NV_UVM[cmd]
        arg = Diffable.from_ctypes_struct(get_struct(arg, ptype), pname)

    return 0, IOCTL(fd, file, cmd, arg), "magenta"

ioctl_handlers = { ("/dev/nvidia-uvm", None): nvidia_uvm }
mmap_handlers = { }
