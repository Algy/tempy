import py_compile
import time
import marshal
import errno
import traceback

from os.path import join as path_join, isfile, isdir, getmtime
from translate import translate_file, translate_string, pystmts_to_string
from struct import unpack

from errors import TempyError, TempyImportError, TempyCompileError, TempyNativeCompileError

TEMPY_EXT = "tpy"
TEMPYC_EXT = "tpyc"


class TempyModule:
    def __init__(self, name, env, _dir, _global=None):
        self.__name__ = name
        self.__env__ = env
        self.__dir__ = _dir
        self.__global__ = _global or {}
        self.__submodule__ = {}

    def __repr__(self):
        return "<TempyModule %s at %s>"%(repr(self.__name__), self.__dir__)

    def __getattr__(self, key):
        try:
            return self.__global__[key]
        except KeyError:
            raise AttributeError("%s has no attribute '%s'"%(repr(self), key))



class _Importer:
    def __init__(self, env, current_module_name, visited):
        self.env = env
        self.current_module_name = current_module_name
        self.visited = visited

    def __call__(self, *names):
        return self.env._module(names, self.visited, self.current_module_name)



def _write_code(filename, codeobject):
    with open(filename, "wb") as fc:
        fc.write('\0\0\0\0')
        py_compile.wr_long(fc, long(time.time()))
        marshal.dump(codeobject, fc)
        fc.flush()
        fc.seek(0, 0)
        fc.write(py_compile.MAGIC)

def _naive_logger(x): print("[TempyEnvironmentLog]", x)

class CompileOption:
    def __init__(self, use_tpyc=True, write_py=False, verbose=False, logger=_naive_logger):
        self.use_tpyc = use_tpyc
        self.write_py = write_py
        self.verbose = verbose
        self.logger = logger


    def log(self, x):
        if self.verbose:
            self.logger(x)

class ModuleFetcher:
    def __init__(self, systemdir=None, extradirs=None):
        self.systemdir = systemdir
        self.extradirs = extradirs or []

    def _find(self, where, module_name):
        file_path = path_join(where, module_name + "." + TEMPY_EXT)
        if isfile(file_path):
            return file_path
        dir_path = path_join(where, module_name)
        dir_init_path = path_join(where, module_name, "__init__" + "." + TEMPY_EXT)
        if isdir(dir_path) and isfile(dir_init_path):
            return dir_init_path
        return None

    def fetch_dir_by_name(self, pwd, module_name):
        '''
        Return (tpy filepath, if it is shared), according to given module_name.
        If not found, None should be returned.
        '''

        first = self._find(pwd, module_name)
        if first is not None:
            return (first, False)

        for where in [self.systemdir] + self.extradirs:
            res = self._find(where, module_name)
            if res is not None:
                return (res, True)
        return None


def _exchange_ext(s, new_ext):
    rdot_idx = s.rfind(".")
    if rdot_idx == -1:
        return s + "." + new_ext 
    else:
        return s[:rdot_idx] + "." + new_ext

class Environment:
    def __init__(self, pwd, cache_module=True, main_name="__main__", module_fetcher=None, compile_option=None):
        self.cache_module = cache_module
        self.module_fetcher = module_fetcher or ModuleFetcher(pwd)
        self.main_module = TempyModule(main_name, self, pwd)
        self.shared_dict = {}
        self.compile_option = compile_option if compile_option else CompileOption()


    def _code_generation(self, tpy_path, tpyc_path, write_to_pyc=True):
        if self.compile_option.write_py:
            py_path = _exchange_ext(tpyc_path, "py")
            try:
                with open(py_path, "w") as f:
                    f.write(pystmts_to_string(translate_file(tpy_path)))
            except IOError as err:
                self.compile_option.log("IOError occured while writing .py file(%s): %s"%(tpyc_path, str(err)))
        code = compile_file(tpy_path)
        if write_to_pyc:
            try:
                _write_code(tpyc_path, code)
            except IOError as err:
                self.compile_option.log("IOError occured while writing codeobject to .tpyc file(%s): %s"%(tpyc_path, str(err)))
        return code


    def _retrieve_code(self, tpy_path, tpyc_path):
        if self.compile_option.use_tpyc:
            if isfile(tpyc_path):
                try:
                    f = open(tpyc_path, "rb")
                    magic_str = f.read(4)
                    if len(magic_str) < 4 or py_compile.MAGIC != magic_str:
                        return self._code_generation(tpy_path, tpyc_path)
                    timestamp_str = f.read(4)

                    if len(timestamp_str) < 4:
                        return self._code_generation(tpy_path, tpyc_path)
                    tpyc_timestamp = unpack("<I", timestamp_str)[0]

                    try:
                        tpy_timestamp = long(getmtime(tpy_path))
                    except IOError:
                        tpy_timestamp = 0
                    if tpyc_timestamp <= tpy_timestamp: # outdated
                        return self._code_generation(tpy_path, tpyc_path)
                    code = marshal.load(f)
                    return code
                except IOError as err:
                    if err.errno == errno.ENOENT: # No such file
                        self.compile_option.log("Failed to locate .pyc file(%s) even though It was assured that it should be present"%tpyc_path)
                        return self._code_generation(tpy_path, tpyc_path)
                    else:
                        raise
                finally:
                    f.close()
            else:
                return self._code_generation(tpy_path, tpyc_path)
        else:
            return self._code_generation(tpy_path, tpyc_path, write_to_pyc=False)


    def _import(self, parent_module, module_name, visited=None, invoker_module_name=None):
        if module_name in parent_module.__submodule__:
            return parent_module.__submodule__[module_name]
        elif module_name in self.shared_dict:
            return self.shared_dict[module_name]
        else:
            if visited is None:
                visited = set()
            pair = self.module_fetcher.fetch_dir_by_name(parent_module.__dir__, module_name)
            if pair is None:
                raise TempyImportError("No such module named '%s'"%module_name)
            tpy_path, is_shared = pair
            tpyc_path = _exchange_ext(tpy_path, TEMPYC_EXT)

            try:
                code = self._retrieve_code(tpy_path, tpyc_path)
            except TempyError:
                raise
            except Exception as error:
                err_info = str(error)
                err_msg = "Cannot import the module named '%s': %s\n%s"%(module_name, err_info, traceback.format_exc())
                raise TempyImportError(err_msg)
            else:
                lcl = {} # local
                gbl = {} # global
                exec(code, gbl, lcl)
                if is_shared:
                    current_module_name = module_name
                else:
                    current_module_name = parent_module.__name__ + "." + module_name
                if current_module_name in visited:
                    raise TempyImportError("circular dependency: in module '%s', tried to import '%s'"%(invoker_module_name, module_name))
                exec_result = lcl['__tempy_main__'](None, 
                                                    _Importer(self, 
                                                              current_module_name,
                                                              visited.union([current_module_name])
                                                              ),
                                                    None)
                mod = TempyModule(current_module_name, self, path_join(parent_module.__dir__, module_name), exec_result)
                if self.cache_module:
                    if is_shared:
                        self.shared_dict[module_name] = mod
                    else:
                        parent_module.__submodule__[module_name] = mod
                return mod


    def _module(self, names, visited=None, invoker_module_name=None):
        iter_module = self.main_module
        invoker_module_name = invoker_module_name or self.main_module.__name__
        for module_name in names:
            iter_module = self._import(iter_module, module_name, visited, invoker_module_name)
        return iter_module

    def module(self, dotted_str):
        return self._module(dotted_str.split("."))




def _compile_kont(stmts, filename):
    src = pystmts_to_string(stmts)
    try:
        code = compile(src, filename, "exec")
        return code
    except SyntaxError as error:
        raise TempyNativeCompileError(error.args)

def compile_string(path, filename="<string>"):
    '''
    compile tempy string into compiled python bytecode(.pyc file)
    '''
    stmts = translate_string(path, filename=filename)
    return _compile_kont(stmts, filename)

def compile_file(path, filename=None):
    '''
    compile tempy file into compiled python bytecode(.pyc file)
    '''
    if filename is None:
        filename = path
    stmts = translate_file(path, filename=filename)
    return _compile_kont(stmts, filename)
