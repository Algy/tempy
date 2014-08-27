from lisn import loads, loads_file
from lisn.utils import LISNVisitor
from functools import wraps
from copy import copy

'''
Utils
'''
def identity(x):
    return x

def NOT_REACHABLE():
    raise Exception("Not reachable")

def dotify(name_or_name_list):
    if isinstance(name_or_name_list, str):
        dotted_name = name_or_name_list
    else:
        dotted_name = ".".join(name_or_name_list)
    return dotted_name


class Promise:
    '''
    Lazy Class
    Not to be confused with Premise class!
    This class is for lazy evaluation, while Premise is used for translation

    '''
    def __init__(self, fun, args=(), kwds={}):
        self.fun = fun
        self.args = args
        self.kwds = kwds

    def __call__(self):
        return self.force()
    def force(self):
        return self.fun(*self.args, **self.kwds)


def delay(*app_args, **app_kwds):
    @wraps(delay)
    def decorator(fun):
        return Promise(fun, app_args, app_kwds)
    return decorator

def is_delayed(obj):
    return isinstance(obj, Promise)

'''
Addition Utils for LISN object
'''
def suite_to_node_list(suite):
    return [obj["param"] for obj in suite["exprs"]]


def check_multi_xexpr(node, head_name=None):
    return node["type"] == "xexpr" and \
           node["multi_flag"] and \
           (head_name is None or
            node["head_name"] == head_name)

def force_name_to_head_expr(node):
    if not check_multi_xexpr(node):
        return None
    return force_name(node["head_expr"])


def force_name(node):
    if node["type"] != "name":
        return None
    else:
        return node["name"]


def force_dotted_name(node):
    '''
    DottedName ::= Name
                 | DottedName "." Name

    otherwise, it raise ValueError

    Returns -
        string list
        None when format is not accpetable
    '''
    def concat(a, b):
        if a is not None and b is not None:
            return a + b
        else:
            return None

    def _iter(node):
        if node is None:
            return None
        elif node["type"] == "trailer" and node["trailer_type"] == "attr":
            return concat(_iter(node["scope"]), [node["attr"]])
        elif node["type"] == "name":
            return [node["name"]]
        else:
            return None
    result = _iter(node)
    return result

def force_one_sarg(xexpr):
    if xexpr["type"] != "xexpr":
        return None

    args = xexpr["args"]
    if args["kargs"] or \
       args["has_star"] or \
       args["has_dstar"] or \
       args["has_amp"]  or \
       args["has_damp"]:
        return None
    else:
        sargs = args["sargs"]
        if len(sargs) == 1:
            return sargs[0]
        else:
            return None


'''
Python AST Classes
'''

class PyStmt:
    def to_string(self, indent, acc_indent):
        raise NotImplementedError


class PyMetaComment(PyStmt):
    def __init__(self, cmt_str):
        self.cmt_str = cmt_str

    def to_string(self, indent, acc_indent):
        if '\n' in self.cmt_str:
            res = "\n".join([" "*acc_indent + "# " + line
                             for line in self.cmt_str.splitlines()])
            res += "\n"
            return res
        else:
            return " "*acc_indent + "# " + self.cmt_str + "\n"

def stmt_list_to_string(stmt_list, indent, acc_indent):
    return "".join([stmt.to_string(indent, acc_indent+indent)
                    for stmt in stmt_list])


class PyDefun(PyStmt):
    def __init__(self, fun_name, args, kwd_args, stmt_list, star=None, dstar=None, docstring=""):
        '''
        Argument -
            kwd_args: (string, PyExpr) list

        '''
        self.fun_name = fun_name
        self.args = args
        self.kwd_args = kwd_args
        self.star = star
        self.dstar = dstar
        self.docstring = docstring
        self.stmt_list = stmt_list

    def to_string(self, indent, acc_indent):
        arglst = []

        arglst += list(self.args) 
        for keyword, arg_expr in self.kwd_args:
            arglst.append(keyword + "=" + arg_expr.to_string())
        
        if self.star is not None:
            arglst.append("*" + self.star)
        if self.dstar is not None:
            arglst.append("**" + self.dstar)
        
        return "def {0}({1}):\n{2}" \
               .format(self.fun_name,
                       ", ".join(arglst),
                       stmt_list_to_string(self.stmt_list, indent, acc_indent))

class PyReturn(PyStmt):
    def __init__(self, ret_expr=None):
        self.ret_expr = ret_expr

    def to_string(self, indent, acc_indent):
        if self.ret_expr is not None:
            ret_expr_str = self.ret_expr.to_string()
        else:
            ret_expr_str = ""

        return " "*acc_indent + "return %s\n"%ret_expr_str

class PyBreak(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "break\n"

class PyContinue(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "continue\n"

class PyPass(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "pass\n"


class PyForStmt(PyStmt):
    def __init__(self, elem_name, _in, stmt_list):
        self.elem_name = elem_name
        self._in = _in
        self.stmt_list = stmt_list

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + \
               "for {0} in {1}:\n{2}"\
                 .format(self.elem_name, 
                         self._in.to_string(),
                         stmt_list_to_string(self.stmt_list, indent, acc_indent))


class PyWhileStmt(PyStmt):
    def __init__(self, cond_expr, stmt_list):
        self.cond_expr = cond_expr
        self.stmt_list = stmt_list


    def to_string(self, indent, acc_indent):
        return " "*acc_indent + \
               "while %s:\n%s"%(self.cond_expr.to_string(),
                                stmt_list_to_string(self.stmt_list,
                                                    indent,
                                                    acc_indent))

class PyIfStmt(PyStmt):
    def __init__(self, if_pair, elif_pairs=None, else_stmt_list=None):
        '''
        Arguments - 
            if_pair: (expr, stmt list)
            elif_pairs: None | (expr, stmt list) list
            else_stmt_list: None | stmt list
        '''

        self.if_pair = if_pair
        self.elif_pairs = elif_pairs or []
        self.else_stmt_list = else_stmt_list or []

    def to_string(self, indent, acc_indent):
        if_expr, if_stmt_list = self.if_pair

        acc_str = "if %s:\n%s"%(if_expr.to_string(),
                                stmt_list_to_string(if_stmt_list,
                                                    indent,
                                                    acc_indent))
        if self.elif_pairs:
            def elif_chunk(elif_expr, elif_expr_stmt_list):
                res = "elif %s:\n%s"%(elif_expr.to_string(),
                                      stmt_list_to_string(elif_expr_stmt_list,
                                                          indent,
                                                          acc_indent))
                return res
            acc_str += "".join([elif_chunk(l, r) for l, r in self.elif_pairs])
        
        if self.else_stmt_list:
            acc_str += "else:\n%s"%stmt_list_to_string(self.else_stmt_list,
                                                       indent,
                                                       acc_indent)
        return acc_str


class PyImportStmt(PyStmt):
    def __init__(self, name_or_name_list):
        self.name_or_name_list = name_or_name_list

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "import " + dotify(self.name_or_name_list)+ "\n"

class PyImportFromStmt(PyStmt):
    def __init__(self, name_or_name_list, import_names):
        self.name_or_name_list = name_or_name_list
        self.import_names = import_names

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + \
               "from " + dotify(self.name_or_name_list) + \
               "import " + ", ".join(self.import_names)

def PyAssignmentToName(name, expr):
    return PyAssignment(PyAssignment.ASSIGN_NAME, name, None, None, None, expr)

def PyAssignmentToAttr(scope_expr, attr_name, expr):
    return PyAssignment(PyAssignment.ASSIGN_ATTR,
                        None, scope_expr, attr_name, None, expr)

def PyAssignmentToItem(scope_expr, index_expr, expr):
    return PyAssignment(PyAssignment.ASSIGN_ITEM,
                        None, scope_expr, None, index_expr, expr)


class PyAssignment(PyStmt):
    ASSIGN_NAME = 0
    ASSIGN_ATTR = 1
    ASSIGN_ITEM = 2

    def __init__(self, _type, name, scope_expr, attr_name, item_expr, expr):
        self._type = _type
        self.name = name # it can be either string or PyMetaID
        self.scope_expr = scope_expr
        self.attr_name = attr_name
        self.item_expr = item_expr
        self.expr = expr
    

    def to_string(self, indent, acc_indent):
        if self._type == PyAssignment.ASSIGN_NAME:
            name_str = self.name.to_string() \
                        if isinstance(self.name, PyExpr) else self.name
            return "%s = %s"%(name_str, self.expr.to_string())
        elif self._type == PyAssignment.ASSIGN_ATTR:
            virtual_parent = PyAttrAccess(self.scope_expr, self.name)
            return "%s.%s = %s"%(expr_to_string(self.scope_expr, virtual_parent),
                                 self.name,
                                 self.expr.to_string())
        elif self._type == PyAssignment.ASSIGN_ITEM:
            virtual_parent = PyItemAccess(self.scope_expr, self.item_expr)
            return "%s[%s] = %s"%(expr_to_string(self.scope_expr, virtual_parent),
                                  self.item_expr.to_string(),
                                  self.expr.to_string())
        else:
            raise Exception("NOT REACHABLE")


class PyExprStmt(PyStmt):
    def __init__(self, expr):
        self.expr = expr

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + self.expr.to_string() + "\n"

class PyExpr:
    def get_expr_pred(self):
        '''
        Expression Precedence
        --
        1. tuple, list, dictionary, string quotion, name ...
        2. attr, array, slice, call
        3. operator
        4. if-else expression
        5. lambda
        '''
        raise NotImplementedError

    def should_put_par(self, under):
        self_pred = self.get_expr_pred()
        under_pred = under.get_expr_pred()

        # TODO: somehow conservative condition (in case of the same pred)
        return self_pred <= under_pred

    def to_string(self):
        raise NotImplementedError


class PyOperatorExpr(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 3

    def operator_pred(self):
        raise NotImplementedError

    def should_put_par(self, under):
        if isinstance(under, PyOperatorExpr):
            return self.operator_pred() <= under.operator_pred()
        else:
            # coerce
            return PyExpr.should_put_par(self, under)

def put_par(s): return "(" + s + ")"
def expr_to_string(expr, parent=None):
    if parent is None:
        return expr.to_string()
    elif parent.should_put_par(expr):
        return put_par(expr.to_string())
    else:
        return expr.to_string()


BINOP_PRED = {
    "**": 1,
    "*": 3, "/": 3, "%": 3, "//": 3,
    "+": 4, "-": 4,
    ">>": 5, "<<": 5,
    "&": 6,
    "^": 7,
    "|": 8,
    "<=": 9, "<": 9, ">": 9, ">=": 9, "<>": 9, "==": 9, "!=": 9,
    "is": 9, "is not": 9, "in": 9, "not in": 9,
    "and": 11,
    "or": 12
}

BINOP_RIGHT_ASSOC = set(["**"])

UNOP_PRED = {
    "+": 2, "-": 2, "~": 2,
    "not": 10
}


class PyBinop(PyOperatorExpr):
    '''
    1. **
    3. * / % //
    4. + -
    5. >> <<
    6. &
    7. ^
    8. |
    9. <= < > >= <> == != `is` `is not` `in` `not in`
    11. and
    12. or 
    '''
    def __init__(self, op, lhs, rhs):
        assert op in BINOP_PRED
        self.op = op
        self.lhs = lhs
        self.rhs = rhs

    def operator_pred(self):
        return BINOP_PRED[self.op]

    def should_put_par(self, under):
        if self.op in BINOP_PRED and \
           isinstance(self.rhs, PyBinop) and \
           self.rhs.op == self.op:
            return False
        elif isinstance(self.lhs, PyBinop) and self.lhs.op == self.op:
            return False
        else:
            # coerce
            return PyOperatorExpr.should_put_par(self, under)

    def to_string(self):
        return expr_to_string(self.lhs, self) + \
               " " + self.op + " " + \
               expr_to_string(self.rhs, self)


class PyUnop(PyOperatorExpr):
    '''
    2. ~ + -
    10. not 
    '''
    def __init__(self, op, param):
        assert op in UNOP_PRED
        self.op = op
        self.param = param
    
    def operator_pred(self):
        return UNOP_PRED[self.op]

    def should_put_par(self, under):
        if isinstance(under, PyUnop) and \
           self.operator_pred() == self.operator_pred():
            return False
        else:
            # coerce
            return PyOperatorExpr.should_put_par(self, under)

    def to_string(self):
        space = " " if self.op == "not" else ""
        return self.op + space + expr_to_string(self.param, self)


class PyItemAccess(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, item_expr):
        self.scope_expr = scope_expr
        self.item_expr = item_expr

    def to_string(self):
        return "%s[%s]"%(expr_to_string(self.scope_expr, self),
                         self.item_expr.to_string())


class PyAttrAccess(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, attr_name):
        self.scope_expr = scope_expr
        self.attr_name = attr_name

    def to_string(self):
        return "%s.%s"%(expr_to_string(self.scope_expr, self),
                        self.attr_name)

class PyArraySlice(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, left_slice=None, right_slice=None):
        self.scope_expr = scope_expr
        self.left_slice = left_slice
        self.right_slice = right_slice

    def to_string(self):
        lslice_str = self.left_slice.to_string() if self.left_slice else ""
        rslice_str = self.right_slice.to_string() if self.right_slice else ""
        return "%s[%s:%s]"%(expr_to_string(self.scope_expr, self),
                            lslice_str,
                            rslice_str)

class PyCall(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, callee_expr, arg_exprs, kw_exprs,
                 star_expr=None, dstar_expr=None):
        '''
        Arguments -
            arg_exprs: expr list
            kw_exprs: (string, expr) list
        '''
        self.callee_expr = callee_expr
        self.arg_exprs = arg_exprs or []
        self.kw_exprs = kw_exprs or []
        self.star_expr = star_expr
        self.dstar_expr = dstar_expr

    def to_string(self):
        arglst = [x.to_string() for x in self.arg_exprs] + \
                 [keyword + "=" + x.to_string() for keyword, x in self.kw_exprs]
        
        if self.star_expr is not None:
            arglst.append("*" + self.star_expr.to_string())
        if self.dstar_expr is not None:
            arglst.append("**" + self.dstar_expr.to_string())

        return "%s(%s)"%(expr_to_string(self.callee_expr, self),
                         ", ".join(arglst))

class PyLiteral(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, literal):
        self.literal = literal # itself

    def to_string(self):
        # Because we use python to compile sth and its target file is python itself, literal is just python object
        # and just to repr it is sufficient to represent all literals(list, dict, string and so on) in target python source 
        # Funny!
        return repr(self.literal)


class PyMetaID(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, _id):
        self._id = _id

    def to_string(self):
        return "__meta_id{0}__".format(self._id)

class PyName(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, name):
        self.name = name
        
    def to_string(self):
        return self.name

'''
Translation
'''

'''
Hinting Name

ID Hint
==
 * duplication in original syntax
   - closure 
     re-initialize
   - let
      <variable_name>_l#dup_depth

 * immediate variable
   1. imd_used_as_argument
     - _imd_arg_1
     - _imd_arg_2
   2. imd_used_as_lhs_or_rhs
     _ _imd_operand
   3. else
   - _imd_el_1
   - _imd_el_2
   - ...

 * [lambda lifting]
   <Lambda lifting's are not required due to python's lexical nature>
 * reserved word
   __line__, __tags__
   python runtime names
   add suffix _rwd_#seq as least seq as possible

 * conflict each other finally
   add suffix _cfl#seq

ID Hint Object
--
 * Original Name
 * source: "local" | "argument" | "function" | "let"
 * 'let' Duplication Depth
 * usage: string set
    "return"
    "local"
    "immediate"
'''

'''
Compiling Procedures

Compiling Environments
--
  * name_env: (string -> id, ref)
  * external_globals
    * extern_fun_map: string -> function
    * name_syntax_map: string -> syntax_expander | syntax_compiler (only as global environment)
    * dname_syntax_map: string -> dsyntax_expander | dsyntax_compiler (only as global environment)

Config Value
---
# config is global premise
  * emit_line_info(li)
  * source code comment verbosity(v): Always True in this revision
  * expression_lifting_style (el): 'stack' | 'ssa' | 'stack_only_name' | 'stack_call_2' Always 'stack' in this revision
  * remove name in the end of 'let' (letdel)

Premise Values (don't expect side-effect)
--
 * use_return_value
 * prebound_id

Conclusion (Return value, frozen)
--
 * preseq_stmts: Stmt list
 * result_expr: None | PyExpr
 * comment: None | string
'''

'''
Data structures for compiling
'''

class CompException(Exception):
    def __init__(self, error_objs):
        Exception.__init__(self, error_objs)
        self.args = tuple(error_objs)

class NoMoreErrorAcceptableException(Exception):
    pass


class CompErrorObject:
    def __init__(self, _type, msg, source_file, locinfo):
        self._type = _type
        self.msg = msg
        self.source_file = source_file
        self.locinfo = locinfo
    
    def __repr__(self):
        return "<Error %s> %s in \"%s\" [line %d-%d, col %d-%d]"%(
                self._type,
                self.msg,
                self.source_file,
                self.locinfo["sline"],
                self.locinfo["eline"],
                self.locinfo["scol"],
                self.locinfo["ecol"] - 1,
            )

                        
    

class IDHint:
    def __init__(self, original_name, name_source, usage, let_dup_depth=0):
        self.original_name = original_name
        self.name_source = name_source
        self.usage = usage
        self.let_dup_depth = let_dup_depth

class IDStorage:
    def __init__(self):
        self.id_dict = {}
        self.available_id = 0


    def get(self, _id):
        return self.id_dict[_id]

class IDInfo:
    def is_var(self):
        return isinstance(self, Var)

    def is_global_scope_var(self):
        return isinstance(self, GlobalScopeVar)

    def is_runtime_extern(self):
        return isinstance(self, RuntimeExtern)
    
    def is_expander(self):
        return isinstance(self, Expander)

    def is_converter(self):
        return isinstance(self, Converter)


class Var(IDInfo):
    def __init__(self, hint):
        self.hint = hint

class GlobalScopeVar(IDInfo):
    def __init__(self, name):
        self.name = name



class RuntimeExtern(IDInfo):
    def __init__(self, runtime_obj_name):
        self.runtime_obj_name = runtime_obj_name


class Expander(IDInfo):
    '''
    expander -
        lisn x CompEnv x Premise x Config x Context -> (pre bound) lisn
    '''
    def __init__(self, expander, name=""):
        self.expander = expander
        self.name = name

    def expand(self, lisn, comp_env, premise, config, context):
        return self.expander(lisn, comp_env, premise, config, context)

    def __repr__(self):
        return "<Syntax expander %s>"%self.name


class Converter(IDInfo):
    '''
    converter - 
        lisn x CompEnv x Premise x Config x Context -> Conclusion
    '''
    def __init__(self, converter, name=""):
        self.converter = converter
        self.name = name 

    def convert(self, lisn, comp_env, premise, config, context):
        return self.converter(lisn, comp_env, premise, config, context)

    def __repr__(self):
        return "<Syntax converter %s>"%self.name


class EnvFrame:
    def __init__(self, frame_type):
        assert frame_type in ["def", "toplevel", "let"]
        self.frame_type = frame_type # "def" | "toplevel" | "let"


class Config:
    def __init__(self, emit_line_info=True, expression_lifting_style="stack", letdel=False, max_error_cnt=20, indent=4):
        self.emit_line_info = emit_line_info
        self.expression_lifting_style = expression_lifting_style
        self.letdel = letdel
        self.max_error_cnt = max_error_cnt
        self.indent = indent

class CompEnv:
    def __init__(self):
        '''
        
        Fields -
            local_env: None | LinkedDict
        '''
        self.global_env = {} # name -> id
        self.local_env = LinkedDict(EnvFrame("toplevel")) # LinkedDict
        self.id_info_dict = {}
        self.available_id = 0

    def issue_id(self, id_info):
        _id = self.available_id
        self.available_id += 1
        self.id_info_dict[_id] = id_info
        return _id

    def issue_local_immediate(self):
        imd_id = self.issue_id(Var(IDHint("", "local", "immediate")))
        return imd_id

    def get_id_info(self, _id):
        return self.id_info_dict[_id]


    def add_local(self, name, id_info):
        _id = self.issue_id(id_info)
        self.local_env.set_shallow(name, _id)
        return _id

    def add_global(self, name, id_info):
        _id = self.issue_id(id_info)
        self.global_env[name] = _id
        return _id
    
    def has_name(self, name):
        return self.local_env.has(name) or name in self.global_env

    def has_local_name(self, name, recursive=False):
        if recursive:
            return self.local_env.has(name)
        else:
            return self.local_env.has_shallow(name)

    def lookup_name(self, name):
        '''
        Returns -
            (id, info)
                id: id of corressponding name
                info: IDInfo
        Exceptions -
            KeyError
        '''
        if self.local_env.has(name):
            _id = self.local_env.get(name)
        else:
            _id = self.global_env[name]
        
        return (_id, self.get_id_info(_id))

    def lookup_global_name(self, name):
        _id = self.global_env[name]
        return (_id, self.get_id_info(_id))


    def local_names(self, recursive=False):
        return self.local_env.keys(recursive=recursive)

    def setup_local_frame(self, frame_type):
        self.local_env = LinkedDict(EnvFrame(frame_type), prev=self.local_env)

    def contract_local_frame(self):
        assert self.local_env is not None
        ret = self.local_env
        self.local_env = self.local_env.prev

    def get_id_hint_dict(self):
        '''
        Dict 
            (id -> string | IDHint)
        '''
        return dict([(_id, (info.hint if info.is_var() else info.name))
                     for _id, info in self.id_info_dict.items()
                     if info.is_var() or info.is_global_scope_var()])

def ensure_local_name(comp_env, name, id_hint):
    if comp_env.has_local_name(name, recursive=False):
        local_id, info = comp_env.lookup_name(name)
        if not info.is_var():
            # make new one
            local_id = comp_env.issue_id(Var(id_hint))
            comp_env.add_local(name, local_id)
    else:
        local_id = comp_env.issue_id(Var(id_hint))
        comp_env.add_local(name, local_id)
    return local_id


def ensure_local_var_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "local", "local"))


def ensure_function_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "function", "local"))

    
class LinkedDict:
    def __init__(self, env_data, initials={}, prev=None):
        self.env_data = env_data
        self.prev = prev
        self.namemap = {}

        for k, v in initials.items():
            self.set_shallow(k, v)

    def keys(self, recursive=False):
        name_set = set(self.namemap.keys())
        if self.prev and recursive:
            return name_set.union(self.prev.keys(recursive=True))
        else:
            return name_set
    
    def get_env_data(self):
        return self.env_data
    
    def set_shallow(self, name, _id):
        self.namemap[name] = _id

    def set(self, name, _id, shallow=True):
        if shallow:
            self.set_shallow(name, _id)
        else:
            if name in self.namemap:
                self.namemap[name] = _id
            elif self.prev:
                return self.prev.set(name, _id)
            else:
                raise KeyError(_id)

    def has(self, name):
        if name not in self.namemap:
            if self.prev:
                return self.prev.has(name)
            else:
                return False
        else:
            return True

    def has_shallow(self, name):
        return name in self.namemap

    
    def who_has(self, name):
        if name not in self.namemap:
            if self.prev:
                return self.prev.who_has(name)
            else:
                return None
        else:
            return self.env_data

    def all_dict_with_name(self, name):
        '''
        Get matching names in several linked dict and return ids of those as list.
        First encounted name is located in front of the list.

        e.g)
        If a linked dict is constructed as shown below

        {a: ..} with data "A" -prev-> {b: ..} -prev-> {a: ..} with env_data "B" 
        ^ front subdict                  ^ rear subdict
        The result of this function is ["A", "B"]
        '''
        prev_result = self.prev.backtrace_name(name) if self.prev else []
        if name in self.namemap:
            return [self] + prev_result
        else:
            return prev_result

    def all_env_data_with_name(self, name):
        return [subdict.get_env_data() 
                for subdict in self.all_dict_with_name(name)]
    
    def get(self, name):
        if name in self.namemap:
            return self.namemap[name]
        elif self.prev:
            return self.prev.get(name)
        else:
            raise KeyError(name)


class Premise:
    def __init__(self, use_return_value=False):
        self.use_return_value = use_return_value

    def copy(self):
        return copy(self)


class Conclusion:
    def __init__(self, preseq_stmts, result_expr, error=False, comment=None):
        self.preseq_stmts = preseq_stmts # this is set to None if and only if error occured
        self.result_expr = result_expr
        self.error = error
        self.comment = comment

    def error_occured(self):
        return self.error 
    
    def has_result(self):
        return self.result_expr is not None

    def is_pure_expr(self):
        return len(self.preseq_stmts) == 0



def expr_conclusion(expr, comment=None):
    return Conclusion([],
                      expr,
                      error=False,
                      comment=comment)

def stmt_conclusion(stmts, comment=None):
    if isinstance(stmts, PyStmt):
        stmts = [stmts]
    return Conclusion(stmts,
                      None,
                      error=False,
                      comment=comment)

def stmt_result_conclusion(stmts, result_expr, comment=None):
    if isinstance(stmts, PyStmt):
        stmts = [stmts]
    return Conclusion(stmts,
                      result_expr,
                      error=False,
                      comment=comment)

def error_conclusion(comment=None):
    conclusion = Conclusion(None,
                            None,
                            error=True,
                            comment=comment)
    return conclusion


def noreturn_conclusion(conclusions):
    if any([lambda x: x.error_occured() for x in conclusions]):
        return error_conclusion()

    # assume that result is not emmited with these conclusions
    stmts = []
    for concl in conclusions:
        stmts += concl.preseq_stmts
        if concl.has_result():
            stmts.append(PyExprStmt(concl.result_expr)) # Result might have side-effect so that we should put result expr as well

    return stmt_conclusion(stmts)

def seq_conclusion(conclusions):
    if any([lambda x: x.error_occured() for x in conclusions]):
        return error_conclusion()
    stmts = []

    last_concl = conclusions[-1]
    rest_concl = noreturn_conclusion(conclusions[:-1])

    return stmt_result_conclusion(rest_concl + last_concl.preseq_stmts,
                                  last_concl.result_expr)
    

def make_integrator(allow_None):
    def integrate_conclusion(comp_env, result_proc, *conclusions):
        '''
        result_proc: A x A x A x .. -> PyExpr
        '''
        preseq_stmts = []
        success_box = [True]
        def convert(a):
            '''
            A ::= A list
            A ::= A tuple
            A ::= Conclusion
            A ::= None?

            '''
            if isinstance(a, list):
                return list(map(convert, a))
            elif isinstance(a, tuple):
                return tuple(map(convert, a))
            elif isinstance(a, Conclusion):
                if a.error_occured():
                    success_box[0] = False
                    return None

                result_expr = a.result_expr
                if a.is_pure_expr():
                    return result_expr
                elif isinstance(result_expr, (PyMetaID, )):
                    preseq_stmts.extend(a.preseq_stmts)
                    return result_expr
                else:
                    preseq_stmts.extend(a.prseq_stmts)
                    result_id = comp_env.issue_local_immidiate()
                    preseq_stmts.extend(stmtify_expr(result_expr, True, result_id))
                    return PyMetaID(result_id)
            elif a is None:
                if allow_None:
                    return None
                else:
                    raise TypeError("NoneType is not allowed")
            else:
                raise TypeError("%s is not allowed"%a.__class__.__name__)

        argument_exprs = convert(conclusions)
        if not success_box[0]:
            return error_conclusion()

        result_expr = result_proc(*argument_exprs)
        return stmt_result_conclusion(preseq_stmts, result_expr)
    return integrate_conclusion

integrate_conclusion = make_integrator(False)
xintegrate_conclusion = make_integrator(True)


class Context:
    def __init__(self, runtime_obj_id, importer_id, line_info_id, max_error_cnt):
        self.runtime_obj_id = runtime_obj_id
        self.importer_id = importer_id
        self.line_info_id = line_info_id
        self.max_error_cnt = max_error_cnt
        self.errors = []

    def add_error(self, error_obj):
        self.errors.append(error_obj)
        if self.max_error_cnt <= len(self.errors):
            raise NoMoreErrorAcceptableException

    def any_error(self):
        return len(self.errors) > 0

def set_comp_error(context, error_obj):
    context.add_error(error_obj)


node_translator = LISNVisitor()
def stmtify_expr(expr, use_return_value, imd_id):
    '''
    CompEnv x bool x id -> stmt list
    '''
    if use_return_value:
        return [PyAssignmentToName(PyMetaID(imd_id), expr)]
    else:
        return [PyExprStmt(expr)]


def basic_emitter(fun):
    @wraps(fun)
    def wrapper(translator, lisn, comp_env, premise, config, context):
        conclusion = fun(translator, lisn, comp_env, premise, config, context)
        assert isinstance(conclusion, Conclusion)

        if config.emit_line_info:
            locinfo = lisn["locinfo"]
            line_directive = \
                PyCall(PyMetaID(context.line_info_id),
                       [PyLiteral(locinfo["sline"]),
                        PyLiteral(locinfo["eline"]),
                        PyLiteral(locinfo["scol"]),
                        PyLiteral(locinfo["ecol"] - 1)],
                       [])
            conclusion.preseq_stmts.insert(0, line_directive)

            return conclusion
        else:
            return conclusion
    return wrapper 


@node_translator.add.trailer
def nt_trailer(translator, lisn, comp_env, premise, config, context):
    trailer_type = lisn["tralier_type"] 
    scope = lisn["trailer_type"]
    
    if scope is None:
        set_comp_error(context,
                       CompErrorObject("Scope",
                                       "scope should be specified",
                                       "<source>",
                                       lisn["locinfo"]))
        return error_conclusion()

    scope_concl = translator(scope,
                             comp_env,
                             Premise(True),
                             config,
                             context)

    if trailer_type == "attr":
        attr = lisn["attr"]

        return integrate_conclusion(
            comp_env,
            lambda scope_expr: PyAttrAccess(scope_expr, attr),
            scope_concl
        )
    elif trailer_type == "array":
        index_param = lisn["index_param"]
        item_concl = translator(index_param,
                                comp_env,
                                Premise(True),
                                config,
                                context)

        return integrate_conclusion(comp_env,
                                    PyItemAccess,
                                    scope_concl,
                                    item_concl)

    elif trailer_type == "slice":
        left_slice = lisn["left_slice"]
        right_slice = lisn["right_slice"]
        
        left_slice_concl = translator(left_slice,
                                      comp_env,
                                      Premise(True),
                                      config,
                                      context) \
                            if left_slice else None
        right_slice_concl = translator(right_slice,
                                       comp_env,
                                       Premise(True),
                                       config,
                                       context) \
                             if right_slice else None


        if left_slice is None and right_slice is None:
            return integrate_conclusion(comp_env,
                lambda scope_expr: PyArraySlice(scope_expr, None, None),
                scope_concl
            )

        elif left_slice is None:
            return integrate_conclusion(comp_env,
                lambda scope_expr, right_expr: PyArraySlice(scope_expr, None, right_expr),
                scope_concl,
                right_slice_concl
            )
        elif right_slice is None:
            return integrate_conclusion(comp_env,
                lambda scope_expr, left_expr: PyArraySlice(scope_expr, left_expr, None),
                scope_concl,
                left_slice_concl
            )
        else:
            return integrate_conclusion(comp_env,
                lambda scope_expr, left_expr, right_expr: \
                  PyArraySlice(scope_expr, left_expr, right_expr),
                scope_concl,
                left_slice_concl,
                right_slice_concl
            )
    else:
        NOT_REACHABLE()


def python_native_literal(name):
    if name == "True":
        return PyLiteral(True)
    elif name == "False":
        return PyLiteral(False)
    elif name == "None":
        return PyLiteral(None)
    else:
        return None


def python_control_name(name):
    if name == "break":
        return PyBreak()
    elif name == "continue":
        return PyContinue()
    else:
        return None


@node_translator.add.name
def nt_name(translator, lisn, comp_env, premise, config, context):
    name = lisn["name"]
    use_return_value = premise.use_return_value

    def set_noreturn_error(name):
        set_comp_error(context, CompErrorObject("NoReturnValue",
                                                "'%s' cannot have return value" % name,
                                                "<source>",
                                                lisn["locinfo"]))

    
    native_literal = python_native_literal(name)
    if native_literal is not None:
        return expr_conclusion(native_literal)

    if name == "pass":
        if use_return_value:
            return stmt_result_conclusion([PyPass()], PyLiteral(None))
        else:
            return stmt_conclusion([PyPass()])

    control_stmt = python_control_name(name)
    if control_stmt is not None:
        if use_return_value:
            set_noreturn_error(name)
            return error_conclusion()
        else:
            return stmt_conclusion([control_stmt])

    if not hasattr(lisn, "meta_id"):
        name_id, info = comp_env.lookup_name(name)
    else:
        name_id = lisn["meta_id"]
        info = comp_env.get_id_info(name_id)

    if info.is_var() or info.is_global_scope_var():
        return expr_conclusion(PyMetaID(name_id))
    elif info.is_runtime_extern():
        return expr_conclusion(PyAttrAccess(PyMetaID(context.runtime_obj_id), name))
    elif info.is_expander() or info.is_converter():
        err_obj = CompErrorObject("IllegalName",
                                  repr(info) + " cannot be used as a variable",
                                  "<source>",
                                  lisn.locinfo)
        set_comp_error(context, err_obj)
        return error_conclusion()
    else:
        NOT_REACHABLE()


@node_translator.add.literal
def nt_literal(translator, lisn, comp_env, premise, config, context):
    literal_type = lisn["literal_type"]
    if literal_type == "string":
        return expr_conclusion(PyLiteral(lisn["content"]))
    elif literal_type == "integer":
        return expr_conclusion(PyLiteral(int(lisn["content"])))
    elif literal_type == "float":
        return expr_conclusion(PyLiteral(float(lisn["content"])))
    else:
        NOT_REACHABLE()


@node_translator.add.binop
def nt_binop(translator, lisn, comp_env, premise, config, context):
# && || -> and or
    if lisn["op"] == "&&":
        pyop = "and"
    elif lisn["op"] == "||":
        pyop = "or"
    else:
        pyop = lisn["op"]

    def integrate_result(lhs_result, rhs_result):
        return PyBinop(pyop, lhs_result, rhs_result)

    lhs_conclusion = translator(lisn["lhs"], comp_env, Premise(use_return_value=True), config, context)
    rhs_conclusion = translator(lisn["rhs"], comp_env, Premise(use_return_value=True), config, context)


    return integrate_conclusion(comp_env, integrate_result, lhs_conclusion, rhs_conclusion)




@node_translator.add.unop
def nt_unop(translator, lisn, comp_env, premise, config, context):
# ! -> not
    if lisn["op"] == "!":
        pyop = "not"
    else:
        pyop = lisn["op"]

    param_conclusion = translator(lisn["param"], comp_env, Premise(True), config, context)
    return integrate_conclusion(comp_env,
                                lambda param_expr: PyUnop(pyop, param_expr),
                                param_conclusion)


@node_translator.add.assign
def nt_assign(translator, lisn, comp_env, premise, config, context):
    op = lisn["op"]
    lvalue_type = lisn["lvalue_type"]
    param = lisn["param"]
    param_concl = translator(param, comp_env, Premise(True), config, context)
    
    if lvalue_type == "name":
        lvalue_name = lisn["lvalue_name"]
        if python_native_literal(lvalue_name) or \
           python_control_name(lvalue_name):
            set_comp_error(context,
                           CompErrorObject("IllegalAssignName",
                                           "cannot assign to %s"%lvalue_name,
                                           "<source>",
                                           lisn["locinfo"]))
            return error_conclusion()

        local_id = ensure_local_var_name(comp_env, lvalue_name)
        return integrate_conclusion(comp_env,
                                    lambda param_expr: \
                                      PyAssignmentToName(PyMetaID(local_id),
                                                         param_expr),
                                    param_concl)

    elif lvalue_type == "attr":
        lvalue_name = lisn["lvalue_name"]
        lvalue_scope = lisn["lvalue_scope"]
        scope_concl = translator(lvalue_scope,
                                 comp_env,
                                 Premise(True),
                                 config,
                                 context)
        return integrate_conclusion(comp_env,
                                    lambda param_expr, scope_expr: \
                                      PyAssignmentToAttr(scope_expr,
                                                         lvalue_name,
                                                         param_expr),
                                    param_concl,
                                    scope_concl)
    elif lvalue_type == "array":
        lvalue_scope = lisn["lvalue_scope"]
        lvalue_index = lisn["lvalue_index"]

        scope_concl = translator(lvalue_scope,
                                 comp_env,
                                 Premise(True),
                                 config,
                                 context)
        index_concl = translator(lvalue_index,
                                 comp_env,
                                 Premise(True),
                                 config,
                                 context)
        return integrate_conclusion(comp_env,
                                    lambda param_expr, scope_expr, index_expr: \
                                      PyAssignmentToItem(scope_expr,
                                                         index_expr,
                                                         param_expr),
                                    param_concl,
                                    scope_concl,
                                    index_concl)
    else:
        NOT_REACHABLE()


@node_translator.add.suite
def nt_suite(translator, lisn, comp_env, premise, config, context):
    return translate_suite(translator, lisn, comp_env, premise, config, context)


@node_translator.add.xexpr
def nt_xexpr(translator, lisn, comp_env, premise, config, context):
    # 1. check if multi name is def, import, import_from
    # 2. lookahead name part to check if name is expander/converter
    # 3. lastly treat label as just function

    if lisn["multi_flag"]:
        head_name = lisn["head_name"]
        if head_name == "def":
            return translate_def(translator, lisn, comp_env, Premise(False), config, context)
        elif head_name == "import":
            return translate_import(translator, lisn, comp_env, Premise(False), config, context)
        elif head_name == "import_from":
            return translate_import_from(translator, lisn, comp_env, Premise(False), config, context)
        else:
            set_comp_error(context,
                           CompErrorObject(
                               "UnknownHeadLabel",
                               "Unknown head label: %s"%head_name,
                               "<source>",
                               lisn["locinfo"]))
            return error_conclusion()
    else:
        head_expr = lisn["head_expr"]
        head_expr_name = force_name(head_expr)
        args = lisn["args"]
        success = True

        if lisn["vert_suite"]["exprs"]:
            set_comp_error(context,
                           CompErrorObject(
                               "IllegalCall",
                               "Vertical Arguments should not be applied to function",
                               "<source>",
                               lisn["vert_suite"]["locinfo"]))
            success = False

        # lookahead
        if head_expr_name is not None and \
            comp_env.has_name(head_expr_name):
            _, info = comp_env.lookup_name(head_expr_name)
            if info.is_expander():
                return translator(info.expand(lisn,
                                              comp_env,
                                              premise,
                                              config,
                                              context),
                                  comp_env,
                                  premise,
                                  config,
                                  context)
            elif info.is_converter():
                return info.convert(lisn, comp_env, premise, config, context)

        applicant_concl = translator(head_expr, Premise(True), config, context)
        sarg_concls = [translator(sarg, comp_env, Premise(True), config, context) for sarg in args["sargs"]]
        karg_keywords = [k for k, _ in args["kargs"]]
        karg_concls = [translator(karg, comp_env, Premise(True), config, context) for _, karg in args["kargs"]]
        star_concl = translator(args["star"],
                                comp_env,
                                Premise(True),
                                config,
                                context) if args["star"] else None
        dstar_concl = translator(args["dstar"],
                                 comp_env,
                                 Premise(True),
                                 config,
                                 context) if args["dstar"] else None


        if not success:
            return error_conclusion()

        return xintegrate_conclusion(comp_env,
                                    lambda callee_expr, sarg_exprs, karg_exprs, star_expr, dstar_expr: \
                                      PyCall(callee_expr,
                                             sarg_exprs, 
                                             zip(karg_keywords, karg_exprs),
                                             star_expr,
                                             dstar_expr),
                                    applicant_concl,
                                    sarg_concls,
                                    karg_concls,
                                    star_concl,
                                    dstar_concl)


def translate_branch(translator, lisn, comp_env, premise, config, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = comp_env.issue_local_immediate()
    else:
        result_id = None

    def conclusion_to_stmts(concl):
        if use_return_value:
            return concl.preseq_stmts + \
                stmtify_expr(concl.result_expr,
                    True,
                    result_id)
        else:
            return concl.preseq_stmts + \
                   stmtify_expr(concl.result_expr, False, None)
    def set_branch_error(lisn, msg):
        set_comp_error(context,
                       CompErrorObject("Branch",
                                       msg,
                                       "<source>",
                                       lisn["locinfo"]))

    def convert_branch(if_cond_concl, if_suite_concl,
                       elif_cond_concls, elif_suite_concls,
                       else_suite_concl=None):
        assert len(elif_cond_concls) == len(elif_suite_concls)

        result_stmts = if_cond_concl.preseq_stmts[:]
        if_stmt = PyIfStmt((if_cond_concl.result_expr,
                            conclusion_to_stmts(if_suite_concl)))
        iter_if_stmt = if_stmt

        for elif_cond_concl, elif_suite_concl in \
                zip(elif_cond_concls, elif_suite_concls):

            if elif_cond_concl.is_pure_expr():
                iter_if_stmt.elif_pairs.append(
                    (elif_cond_concl.result_expr, 
                     conclusion_to_stmts(elif_suite_concl)))
            else:
                cond_id = comp_env.issue_local_immediate()
                iter_if_stmt.else_stmt_list += elif_cond_concl.preseq_stmts
                nested_if_stmt = PyIfStmt((
                    elif_cond_concl.result_expr,
                    conclusion_to_stmts(elif_suite_concl)))
                iter_if_stmt = nested_if_stmt

        if else_suite_concl is not None:
            iter_if_stmt.else_stmt_list = conclusion_to_stmts(else_suite_concl)
        result_stmts.append(if_stmt)

        if use_return_value:
            return stmt_result_conclusion(result_stmts,
                                          PyMetaID(result_id))
        else:
            return stmt_conclusion(result_stmts)
    def set_invalid_predicate(dest_lisn):
        set_branch_error(dest_lisn, "Invalid predicate")

    def set_arity_mismatch(dest_lisn, msg):
        set_branch_error(dest_lisn, msg)

    success = True
    args = lisn["args"]
    vert_suite = lisn["vert_suite"]

    res_list = [obj["param"]
                  for obj in vert_suite["exprs"]
                  if not obj["is_arrow"]]
    tagged_res_list = [(obj["arrow_lstring"], obj["param"])
                       for obj in vert_suite["exprs"]
                       if obj["is_arrow"]]

    pred_list = args["sargs"]
    tagged_pred_list = args["kargs"]
    if tagged_pred_list:
        set_invalid_predicate(tagged_pred_list[0][1])
        success = False

    if tagged_res_list:
        set_invalid_predicate(tagged_res_list[0][1])
        success = False

    if args["has_star"]:
        set_invalid_predicate(args["star"])
        success = False
    if args["has_dstar"]:
        set_invalid_predicate(args["dstar"])
        success = False

    if args["has_amp"]:
        set_invalid_predicate(args["amp"])
        success = False

    if args["has_damp"]:
        set_invalid_predicate(args["damp"])
        success = False

    if not success:
        return error_conclusion()
    
    pred_cnt = len(pred_list)
    res_cnt = len(res_list)

    pred_concls = [translator(pred, comp_env, premise.copy(), config, context)
                   for pred in pred_list]
    res_concls = [translator(res, comp_env, premise.copy(), config, context)
                  for res in res_list]
    if pred_cnt == 0:
        set_arity_mismatch(lisn, "Predicate Expected");
        success = False
    else:
        if pred_cnt == res_cnt:
            if_pred_concl = pred_concls[0]
            if_res_concl = res_concls[0]
            elif_pred_concls = pred_concls[1:]
            elif_res_concls = res_concls[1:]
            else_res_concl = None
        if pred_cnt == res_cnt + 1:
            if_pred_concl = pred_concls[0]
            if_res_concl = res_concls[0]
            elif_pred_concls = pred_concls[1:]
            elif_res_concls = res_concls[1:-1]
            else_res_concl = res_concls[-1]
        else:
            set_arity_mismatch(pred_list[0], "Number of predicates is expected to be %d or %d" % (res_cnt, res_cnt + 1));
            success = False

    if not success:
        return error_conclusion()
    return convert_branch(if_pred_concl, if_res_concl,
                          elif_pred_concls, elif_res_concls,
                          else_res_concl)
    

def is_def_node(node):
    return check_multi_xexpr(node, "def")


def translate_suite(translator, suite, comp_env, premise, config, context):
    use_return_value = premise.use_return_value
    success = True
    concls = []
    node_list = suite_to_node_list(suite)
    if node_list:
        last_node = node_list[-1]
        for node in suite_to_node_list(suite):
            child_premise = Premise(use_return_value and node is last_node)
            if is_def_node(node):
                def_name = force_name_to_head_expr(node)
                if def_name is None:
                    set_comp_error(context,
                                   CompErrorObject("DefName",
                                                   "Name of def node is not appropriate",
                                                   "<source>",
                                                   suite["head_expr"]["locinfo"]))
                    success = False
                else:
                    function_id = ensure_function_name(comp_env, def_name)
                    child_premise.prebound_id = function_id # HACK?

                    @delay()
                    def translation_promise():
                        return translator(node, comp_env, child_premise, config, context)
                    concls.append(translation_promise)
            else:
                concls.append(translator(node, comp_env, child_premise, config, context))
        
        # force evaluation of translation of defs
        for idx in range(len(concls)):
            concl = concls[idx]
            if is_delayed(concl):
                concls[idx] = concl.force()
        
        if not success:
            return error_conclusion()

        if use_return_value:
            return seq_conclusion(concls)
        else:
            return noreturn_conclusion(concls)
    else:
        # empty suite
        if use_return_value:
            return expr_conclusion(PyLiteral(None))
        else:
            return stmt_conclusion(PyPass())



def translate_def(translator, lisn, comp_env, premise, config, context):
    assert is_def_node(lisn)

    def gather_formal_info():
        arg_info = lisn["args"]
        sarg_strs = []
        kwd_pairs = []
        star_str = None
        dstar_str = None

        argument_test_success = True
        for sarg_node in arg_info["sargs"]:
            sarg_str = force_name(sarg_node)
            if sarg_str is None:
                sarg_strs.append(sarg_str)
                argument_test_success = False
        for karg_str, karg_val_node in arg_info["kargs"]:
            kwd_pairs.append((karg_str, karg_val_node))

        if arg_info["has_star"]:
            star_str = force_name(arg_info["star"])
            if star_str is None:
                set_comp_error(context,
                               CompErrorObject("FormalArgument",
                                               "Invalid star formal argument",
                                               "<source>",
                                               lisn["head_expr"]["locinfo"]))
                argument_test_success = False
        
        if arg_info["has_dstar"]:
            dstar_str = force_name(arg_info["dstar"])
            if dstar_str is None:
                set_comp_error(context,
                               CompErrorObject("FormalArgument",
                                               "Invalid double-star formal argument",
                                               "<source>",
                                               lisn["head_expr"]["locinfo"]))
                argument_test_success = False


        if arg_info["has_damp"] or arg_info["has_amp"]:
            set_comp_error(context,
                           CompErrorObject("NotSupported",
                                           "& or && argument is not supported",
                                           "<source>",
                                           lisn["head_expr"]["locinfo"]))
            argument_test_success = False


        def_name = force_name(lisn["head_expr"])
        if def_name is None:
            set_comp_error(context,
                           CompErrorObject("DefName",
                                           "Name of def node is not appropriate",
                                           "<source>",
                                           lisn["head_expr"]["locinfo"]))
            argument_test_success = False
        if argument_test_success:
            return (def_name, sarg_strs, kwd_pairs, star_str, dstar_str)
        else:
            return None

    def process_kwd_pairs(kwd_pairs):
        '''
        Results -
            (
                bool, # success?
                stmt list, # preseq_stmts
                (string, expr) list # default_pairs
            }
        '''
        preseq_stmts = []
        default_pairs = []
        concl_pairs = [(keyword,
                        translator(default_node,
                                   comp_env,
                                   Premise(True),
                                   config,
                                   context))
                        for keyword, default_node in kwd_pairs]
        success = True
        for keyword, concl in concl_pairs:
            if concl.error_occured():
                success = False
            elif concl.is_pure_expr():
                expr = concl.result_expr
                default_pairs.append((keyword, expr))
            else:
                imd_id = comp_env.issue_local_immediate()
                preseq_stmts += concl.preseq_stmts
                preseq_stmts.append(PyAssignmentToName(PyMetaID(imd_id),
                                                       concl.result_expr))
                default_pairs.append((keyword, PyMetaID(imd_id)))

        return (success, preseq_stmts, default_pairs)

    def make_defun(def_xexpr, def_name, sarg_strs, default_pairs, star_str, dstar_str):
        '''
        Return - 
            PyDefun
        '''
        if def_xexpr["vert_flag"]:
            def_stmts = []
            suite = def_xexpr["vert_suite"]
            concl = translator(suite, comp_env, Premise(True), config, context)
            def_stmts = concl.preseq_stmts
            def_stmts.append(PyReturn(concl.result_expr))
        else:
            def_stmts = [PyPass()]
        return PyDefun(def_name,
                       sarg_strs,
                       default_pairs,
                       def_stmts,
                       star_str,
                       dstar_str)

    formal_info = gather_formal_info()
    if formal_info is None:
        return error_conclusion()
    def_name, sarg_strs, kwd_pairs, star_str, dstar_str = formal_info
    default_value_test_success, preseq_stmts, default_pairs = process_kwd_pairs(kwd_pairs)

    prebound_id = premise.prebound_id if hasattr(premise, "prebound_id") else None
    if prebound_id is None:
        function_id = ensure_function_name(comp_env, def_name) # function name
    else:
        assert comp_env.has_local_name(def_name, recursive=False)
        _id, info = comp_env.lookup_name(def_name)
        assert _id == prebound_id
        assert info.is_var()
        function_id = prebound_id # name is already bound to 

    # formal arguments duplication check
    name_set = set([])
    no_duplication_found = True
    for name in sarg_strs + \
                [k for k, _ in kwd_pairs] + \
                (star_str or []) + \
                (dstar_str or []):
        if name not in name_set:
            name_set.add(name)
        else:
            no_duplication_found = False
            set_comp_error(context,
                           CompErrorObject("FormalArgument",
                               "Duplicated name of formal argument: %s"%name,
                               "<source>",
                               lisn["locinfo"]))
    if not no_duplication_found:
        return error_conclusion()

    ## NEW ENV
    comp_env.setup_local_frame("def") 

    # set names of arguments into new local environment
    for name in sarg_strs:
        ensure_local_var_name(comp_env, name)
    for name, _ in kwd_pairs:
        ensure_local_var_name(comp_env, name)
    if star_str:
        ensure_local_var_name(comp_env, star_str)
    if dstar_str:
        ensure_local_var_name(comp_env, dstar_str)
    defun = make_defun(lisn, def_name, sarg_strs, default_pairs, star_str, dstar_str)

    ## DEL ENV
    comp_env.contract_local_frame() 

    if premise.use_return_value:
        return stmt_result_conclusion(preseq_stmts + [defun], PyLiteral(None))
    else:
        return stmt_conclusion(preseq_stmts + [defun])


def translate_import(translator, lisn, comp_env, premise, config, context):
    assert check_multi_xexpr(lisn, "import")

    head_node = lisn["head_expr"]
    names = force_dotted_name(head_node)
    if names is None:
        set_comp_error(context,
                       CompErrorObject("IllegalImportName",
                                       "Not appropriate import name",
                                       "<source>", head_node["locinfo"]))
        return error_conclusion()
    else:
        last_name = names[-1]
        accessor = PyMetaID(context.import_id)
        for name in names[::-1]:
            accessor = PyAttrAccess(accessor, name)
        module_id = ensure_local_var_name(comp_env, last_name)

        assign = PyAssignmentToName(PyMetaID(module_id), accessor)
        return stmt_conclusion([assign])


def translate_import_from(translator, lisn, comp_env, premise, config, context):
    assert check_multi_xexpr(lisn, "import_from")

    def extract_import_names(suite):
        '''
        Returns -
            (success?, NAME_OR_NAME_PAIR list)
            where NAME_OR_NAME_PAIR is (string | (string, string)) list

        '''
        success = True
        result = []
        for obj in suite["exprs"]:
            if suite["param"]["type"] != "name":
                set_comp_error(context,
                               CompErrorObject("IllegalImportName",
                                               "Invalid import name",
                                               "<source>", suite["param"]["locinfo"]))
                success = False
                continue
            dest_name = suite["param"]["name"]
            if obj["is_arrow"]:
                source_name =  obj["arrow_lstring"]
                result.append((source_name, dest_name))
            else:
                result.append(dest_name)
            return (success, result)

    head_node = lisn["head_expr"]
    import_name_valid, import_names = extract_import_names(lisn["vert_suite"])

    if not import_name_valid:
        return error_conclusion()

    module_names = force_dotted_name(head_node)
    if module_names is None:
        set_comp_error(context,
                       CompErrorObject("IllegalImportName",
                                       "Not appropriate import module",
                                       "<source>", head_node["locinfo"]))
        return error_conclusion()
    else:
        last_name = module_names[-1]
        accessor = PyMetaID(context.import_id)
        for name in module_names[::-1]:
            accessor = PyAttrAccess(accessor, name)
        module_id = comp_env.issue_local_immediate()

        stmts = [PyAssignmentToName(PyMetaID(module_id), accessor)]
        for name_or_name_pair in import_names:
            if isinstance(name_or_name_pair, tuple):
                source_name, dest_name = name_or_name_pair

                dest_id = ensure_local_var_name(comp_env, dest_name)

                stmts.append(PyAssignmentToName(PyMetaID(dest_id), PyAttrAccess(PyMetaID(module_id), source_name)))
            else:
                dest_name = name_or_name_pair
                dest_id = ensure_local_var_name(comp_env, dest_name)

                stmts.append(PyAssignmentToName(PyMetaID(dest_id), PyAttrAccess(PyMetaID(module_id), dest_name)))

        return stmt_conclusion(stmts)


def add_python_native(comp_env):
    for name in dir(__builtins__):
        comp_env.add_global(name, GlobalScopeVar(name))


def setup_base_syntax(comp_env):
    add_python_native(comp_env)
    comp_env.add_global("if",
                        Converter(translate_branch,
                                  "if"))
    #TODO
    '''

    comp_env.add_global("let",
                        Converter(translate_let,
                                  "let"))
    '''
                        


def main_translate(suite, config=None):
    config = config or Config()
    comp_env = CompEnv()
    add_python_native(comp_env)

    comp_env.setup_local_frame("def")

    runtime_obj_id = comp_env.add_local("__runtime__",
                                        Var(IDHint("__runtime__",
                                                   "argument",
                                                   "local",
                                                   "local")))

    importer_id = comp_env.add_local("__importer__",
                                     Var(IDHint("__importer__",
                                                "argument",
                                                "local",
                                                "local")))
    line_info_id = comp_env.add_local("__line__",
                                      Var(IDHint("__line__",
                                                 "argument",
                                                 "local",
                                                 "local")))
    context = Context(runtime_obj_id, importer_id, line_info_id, config.max_error_cnt)

    def_stmts = []
    success = True
    error_flooded = False

    try:
        main_concl = node_translator(suite,
                                     comp_env,
                                     Premise(False),
                                     config,
                                     context)
        def_stmts += main_concl.preseq_stmts
    except NoMoreErrorAcceptableException:
        error_flooded = True

    if context.errors:
        success = False

    if not success:
        print context.errors
        if error_flooded:
            print "Error Flooded"
        return None

    dict_sym_id, dict_sym_info = comp_env.lookup_global_name("dict")
    assert dict_sym_info.is_global_scope_var()

    kw_arguments = []
    for local_name in comp_env.local_names():
        local_id, local_info = comp_env.lookup_name(local_name)
        if not local_info.is_var():
            continue
        kw_arguments.append((local_name, PyMetaID(local_id)))
        
    def_stmts.append(PyReturn(PyCall(PyMetaID(dict_sym_id),
                                     None,
                                     kw_arguments)))
    comp_env.contract_local_frame()
    def_mk_tmp = PyDefun("__make_template__",
                         [context.runtime_obj_id,
                          context.importer_id,
                          context.line_info_id],
                         None,
                         def_stmts)
    return def_mk_tmp

def translate_string(s):
    suite = loads(s)
    return main_translate(suite)


def translate_file(filepath):
    node = loads_file(filepath)
    return main_translate(node)
