"""DXGI adapter selection for the bundled DirectML provider."""

import ctypes as c
from ctypes import wintypes as w
import uuid, os


class GUID(c.Structure):
    _fields_ = [("bytes", c.c_ubyte * 16)]


class DESC(c.Structure):
    _fields_ = [
        ("Description", w.WCHAR * 128),
        ("VendorId", w.UINT),
        ("DeviceId", w.UINT),
        ("SubSysId", w.UINT),
        ("Revision", w.UINT),
        ("DedicatedVideoMemory", c.c_size_t),
        ("DedicatedSystemMemory", c.c_size_t),
        ("SharedSystemMemory", c.c_size_t),
        ("LuidLow", w.DWORD),
        ("LuidHigh", w.LONG),
        ("Flags", w.UINT),
    ]


def guid(value):
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def method(ptr, index, result, *args):
    table = c.cast(ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result, c.c_void_p, *args)(table[index])


def adapters():
    if os.name != "nt":
        return []
    factory = c.c_void_p()
    result = []
    try:
        dxgi = c.WinDLL("dxgi.dll")
        create = dxgi.CreateDXGIFactory1
        create.argtypes = [c.POINTER(GUID), c.POINTER(c.c_void_p)]
        create.restype = w.LONG
        if (
            create(
                c.byref(guid("770aae78-f26f-4dba-a829-253c83d1b387")), c.byref(factory)
            )
            < 0
        ):
            return []
        for index in range(16):
            adapter = c.c_void_p()
            if (
                method(factory, 12, w.LONG, w.UINT, c.POINTER(c.c_void_p))(
                    factory, index, c.byref(adapter)
                )
                < 0
            ):
                break
            try:
                desc = DESC()
                if (
                    method(adapter, 10, w.LONG, c.POINTER(DESC))(adapter, c.byref(desc))
                    < 0
                    or desc.Flags & 2
                ):
                    continue
                capable = False
                try:
                    probe = c.WinDLL("d3d12.dll").D3D12CreateDevice
                    probe.argtypes = [c.c_void_p, w.UINT, c.POINTER(GUID), c.c_void_p]
                    probe.restype = w.LONG
                    capable = (
                        probe(
                            adapter,
                            0xB000,
                            c.byref(guid("189819f1-1db6-4b57-be54-1821339b85f7")),
                            None,
                        )
                        >= 0
                    )
                except OSError:
                    pass
                if capable:
                    result.append(
                        {
                            "id": index,
                            "name": desc.Description,
                            "memory": desc.DedicatedVideoMemory,
                            "vendor": desc.VendorId,
                        }
                    )
            finally:
                method(adapter, 2, w.ULONG)(adapter)
    except (OSError, ValueError):
        return []
    finally:
        if factory.value:
            method(factory, 2, w.ULONG)(factory)
    return sorted(result, key=lambda a: a["memory"], reverse=True)
