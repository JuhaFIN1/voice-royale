import sys
if sys.platform == "darwin":
    try:
        import ctypes, ctypes.util
        _lib = ctypes.util.find_library("objc")
        if _lib:
            _objc = ctypes.CDLL(_lib)
            _objc.objc_getClass.restype = ctypes.c_void_p
            _objc.objc_getClass.argtypes = [ctypes.c_char_p]
            _objc.sel_registerName.restype = ctypes.c_void_p
            _objc.sel_registerName.argtypes = [ctypes.c_char_p]
            _objc.objc_msgSend.restype = ctypes.c_void_p
            _objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            _cls = _objc.objc_getClass(b"NSApplication")
            _sel = _objc.sel_registerName(b"sharedApplication")
            if _cls:
                _objc.objc_msgSend(_cls, _sel)
    except Exception:
        pass
