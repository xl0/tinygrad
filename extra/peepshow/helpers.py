from dataclasses import dataclass, make_dataclass
from typing import Any, ClassVar
from tinygrad.helpers import colored, ansicolor, getenv
import ctypes
class HexInt(int):
  def __new__(cls, value, bits=32):
    i = super().__new__(cls, int(value) if value is not None else 0)
    i.bits = bits
    return i

  def __repr__(self):
     if self >= 0: return f"0x{int(self):0{max(self.bits, (int(self).bit_length() + 3)) // 4}x}"
     else: return repr(int(self))

ctypes_hex_types = (
    ctypes.c_int8, ctypes.c_int16, ctypes.c_int32, ctypes.c_int64,
    ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64,
    ctypes.c_void_p
)

def ctypes_struct_init(self, d):
    for k, t in d._fields_:
        if t in ctypes_hex_types: setattr(self, k, HexInt(getattr(d, k), ctypes.sizeof(t)*8))
        else:                     setattr(self, k, getattr(d, k))

class Diffable:
    ct_to_dc_cache: ClassVar[dict[tuple[str, ctypes.Structure], Any]] = {}

    @classmethod
    def from_ctypes_struct(cls, s, name):
        if (type(s), name) not in cls.ct_to_dc_cache: cls.ct_to_dc_cache.update({
           (type(s), name): make_dataclass(name, [f[0] for f in s._fields_], bases=(cls,), namespace={"__init__": ctypes_struct_init})
           })
        return cls.ct_to_dc_cache[type(s), name](s)

SNIFFER_SUPRESS_RAW = getenv("SNIFFER_SUPRESS_RAW", 0)
def raw_repr(cls):
    if SNIFFER_SUPRESS_RAW: return cls
    _repr = cls.__repr__
    cls.__repr__ = lambda self: f"{repr(HexInt(self, self.bits) )if isinstance(self, HexInt) else repr (self._raw)} = {_repr(self)}"
    return cls

@raw_repr
class NamedHexInt(HexInt, Diffable):
    _raw: int
    def __new__(cls, val, bits=32):
       c = super().__new__(cls, val, bits)
       c._raw = val
       return c
    def __repr__(self): return f"{self.__class__.__name__}"


def get_struct(argp, stype):
  return ctypes.cast(ctypes.c_void_p(argp), ctypes.POINTER(stype)).contents


@dataclass
class IOCTL(Diffable):
  fd: int
  filename: str
  op: HexInt|Any
  argp: HexInt|Any

  def __init__(self, fd, filename, op, argp):
    self.fd, self.filename = fd, filename
    self.op = HexInt(op) if isinstance(op, int) and not isinstance(op, HexInt) else op
    self.argp = HexInt(argp) if isinstance(argp, int) else argp

def diff(x, y, color):
  if type(x) == type(y):
    if x == y: return repr(x)
    elif isinstance(x, Diffable):
        return f"{x.__class__.__name__}({", ".join([f"{k}=" + diff(getattr(x, k), getattr(y, k), color) for k in x.__dict__.keys()])})"
  return colored(f"{x} 🡆 {y}", "CYAN") + ansicolor(color)
