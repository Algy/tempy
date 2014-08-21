from clisn import loads, loads_file

ALL_TYPES = set([
    "trailer", "name", "literal",
    "binop", "unop", "assign",
    "suite", "xexpr"
])

def _check_lisn_validity(lisn):
    if not isinstance(lisn, dict):
        raise ValueError("LISN object should be a dict object")

    _type = lisn['type']
    if 'type' not in lisn:
        raise ValueError("LISN object doesn't have `type` key")

    if _type not in ALL_TYPES:
        raise ValueError("%s is not valid LISN type"%_type)


class LISNVisitException(Exception): pass


class _VisitorCollection:
    def __init__(self):
        self.visitors = {}
        self.default_visitors = {}

    def _register_visitor(self, _type, fun):
        if _type not in self.visitors:
            self.visitors[_type] = []
        self.visitors[_type].append(fun)

    def _register_default_visitor(self, _type, fun):
        if _type in self.visitors:
            raise ValueError("Default visitor should be only one")
        self.default_visitors[_type] = fun

    def __getattr__(self, _type):
        if _type.startswith("default_"):
            _core_type = _type[len("default_"):]
            default_case = True
        else:
            _core_type = _type
            default_case = False
        
        if _core_type not in ALL_TYPES:
            return object.__getattr__(self, _type)

        if default_case:
            def default_visitor_registerer(fun):
                self._register_default_visitor(_type, fun)
                return fun

            return default_visitor_registerer
        else:
            def visitor_registerer(fun):
                self._register_visitor(_type, fun)
                return fun

            return visitor_registerer

class LISNVisitor:
    def __init__(self):
        self.add = _VisitorCollection()

    def __call__(self, *args, **kwds):
        return self.visit(*args, **kwds)

    def visit(self, lisn_obj, *ctx_args, **ctx_kwds):
        _check_lisn_validity(lisn_obj)

        _type = lisn_obj['type']

        done = False
        for visitor in self.add.visitors.get(_type, []):
            ret = visitor(self.visit, lisn_obj, *ctx_args, **ctx_kwds)
            if ret != False: 
                done = True
                break

        if not done:
            # last chance to catch 
            def_visitor = self.add.default_visitors.get(_type)
            if def_visitor is None:
                raise LISNVisitException('No match case for type \'%s\'. '
                                         'Try to make default visitor.'%_type)
            ret = def_visitor(self.visit, lisn_obj, *ctx_args, **ctx_kwds)
            done = True
        return ret


_calculator = LISNVisitor()

@_calculator.add.literal
def _cal_literal(visitor, obj):
    literal_type = obj['literal_type']
    content = obj['content']
    if literal_type == 'float':
        num = float(content)
    elif literal_type == 'integer':
        num = int(content)
    else:
        num = content
    return num

_CAL_BINOP_MAP = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "/": lambda a, b: a / b,
    "*": lambda a, b: a * b,
    "%": lambda a, b: a % b,
    "**": lambda a, b: a ** b
}

_CAL_UNOP_MAP = {
    "+": lambda a: +a,
    "-": lambda a: -a
}

@_calculator.add.binop
def _cal_binop(visitor, obj):
    op = obj['op']
    return _CAL_BINOP_MAP[op](visitor(obj['lhs']), visitor(obj['rhs']))

@_calculator.add.unop
def _cal_unop(visitor, obj):
    op = obj['op']
    return _CAL_UNOP_MAP[op](visitor(obj['param']))

@_calculator.add.suite
def _cal_unop(visitor, obj):
    exprs = obj['exprs']
    for line in exprs:
        yield visitor(line['param'])

def calculator(s):
    res = list(_calculator(loads(s)))

    if res:
        return res[-1]
    else:
        return None
