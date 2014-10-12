import py_compile
import time
import marshal

from os.path import join, isfile, getmtime
from translate import translate_file, translate_string
from struct import unpack

TEMPY_EXT = "tpy"
TEMPYC_EXT = "tpyc"

class TempyError(Exception):
    pass

class TempyImportError(TempyError):
    pass

class TempyCompileError(TempyError):
    pass

class TempyModule:
    def __init__(self, name, _dict=None):
        self.name = name
        self._dict = _dict or {}

    def __getattr__(self, key):
        return self._dict[key]

def _get_ts_and_code(path, get_code=True):
    if isfile(path):
        with open(path, "wb") as f:
            magic_str = f.read(4)
            if len(magic_str) < 4 or py_compile.MAGIC != magic_str:
                return None
            timestamp_str = f.read(4)

            if len(timestamp_str) < 4:
                return None
            timestamp = unpack("<I", timestamp_str)[0]

            if get_code:
                code = marshal.load(f)
            else:
                code = None
            return (timestamp, code)
    else:
        return None

class Environment:
    def __init__(self, path):
        self.path = path
        self.modules = {}

    def module(self, module_name):
        return self._module(module_name)

    def _module(self, module_name, visited=None):
        if visited is None:
            visited = set()

        if module_name in visited:
            raise TempyImportError("circular dependency: %s"%module_name)

        if module_name in self.modules:
            return self.modules[module_name]
        else:
            tpy_path = join(self.path, module_name + "." + TEMPY_EXT)
            tpyc_path = join(self.path, module_name + "." + TEMPYC_EXT)

            code = None
            success = True
            io_errno = None
            try:
                test_res = _get_ts_and_code(tpyc_path)
                if test_res:
                    tpyc_timestamp, tpyc_code = test_res
                    if isfile(tpy_path):
                        try:
                            tpy_timestamp = long(getmtime(tpy_path))
                        except IOError:
                            code = tpyc_code
                        else:
                            if tpy_timestamp > tpyc_timestamp:
                                code = compile_file(tpy_path)
                                if _get_ts_and_code(tpyc_path, get_code=False):
                                    try:
                                        _write_code(tpyc_path, code)
                                    except IOError:
                                        pass
                    else:
                        code = tpyc_code
                elif isfile(tpy_path):
                    code = compile_file(tpy_path)
                    if not isfile(tpy_path) or _get_ts_and_code(tpyc_path, get_code=False): # XXX: telling 0x00 or MAGIC
                        try:
                            _write_code(tpyc_path, code)
                        except IOError:
                            pass
                else:
                    success = False
            except IOError as error:
                io_errno = error.errno
                success = False

            if not success:
                err_msg = "Cannot Import the module %s"%module_name
                if io_errno is not None:
                    err_msg += " <IOErrno %d>"%io_errno
                raise TempyImportError(err_msg)
            else:
                lcl = {}
                gbl = {}
                exec(code, gbl, lcl)

                myself = self
                exec_result = lcl['tempy_main'](None,
                                                type("Importer",
                                                     (object, ),
                                                     {"__getattr__":
                                                         lambda self, n: myself._module(n, visited.union([module_name]))})(),
                                                None) # TODO 
                mod = TempyModule(module_name, exec_result)
                self.modules[module_name] = mod
                return mod


def _write_code(filename, codeobject):
    with open(filename, "wb") as fc:
        fc.write('\0\0\0\0')
        py_compile.wr_long(fc, long(time.time()))
        marshal.dump(codeobject, fc)
        fc.flush()
        fc.seek(0, 0)
        fc.write(py_compile.MAGIC)


def _compile_kont(tr_res):
    if tr_res.success:
        src = tr_res.to_string()
        try:
            code = compile(src, "<code>", "exec")
            return code
        except SyntaxError as e:
            raise
    else:
        raise TempyCompileError(tr_res.error_report())


def compile_string(path):
    tr_res = translate_string(path)
    return _compile_kont(tr_res)

def compile_file(path):
    tr_res = translate_file(path)
    return _compile_kont(tr_res)

