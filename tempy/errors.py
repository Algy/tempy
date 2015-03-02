class TempyError(Exception):
    pass
class TempyImportError(TempyError):
    pass
class TempyCompileError(TempyError):
    def __init__(self, errors, error_flooded):
        self.args = errors
        self.error_flooded = error_flooded

class TempySyntaxError(TempyCompileError):
    def __init__(self, args):
        self.args = args

class TempyNativeCompileError(TempyError):
    def __init__(self, args):
        self.args = args

class CompileError:
    def __init__(self, _type, msg, locinfo, filename=None):
        self._type = _type
        self.msg = msg
        self.locinfo = locinfo
        self.filename = filename
    
    def __repr__(self):
        return "<Error %s> %s in \"%s\" [line %d-%d, col %d-%d]"%(
                self._type,
                self.msg,
                self.filename or "",
                self.locinfo["sline"],
                self.locinfo["eline"],
                self.locinfo["scol"],
                self.locinfo["ecol"] - 1,
            )


