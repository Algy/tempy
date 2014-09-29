from tag import is_tag_name, HTML_TAGS
from lisn import loads, loads_file
from lisn.utils import LISNVisitor
from lisn.match import LISNPattern
from functools import wraps
from copy import copy
from pprint import pprint

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


def check_multi_xexpr(node, head_label=None):
    return node["type"] == "xexpr" and \
           node["has_head_label"] and \
           (head_label is None or
            node["head_label"] == head_label)

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

def force_one_parg(xexpr):
    if xexpr["type"] != "xexpr":
        return None

    arg_info = xexpr["arg_info"]
    if arg_info["kargs"] or \
       arg_info["has_star"] or \
       arg_info["has_dstar"] or \
       arg_info["has_amp"]  or \
       arg_info["has_damp"]:
        return None
    else:
        pargs = arg_info["pargs"]
        if len(pargs) == 1:
            return pargs[0]
        else:
            return None

'''
MetaID conversion rule
--
local | argument | function | lambda | immediate

use convert-env (dict)

1. preserve name of all global-scope variables
2. preserve function name: (original), (original)_f#
3. preserve local name: (original), (original)_#
4. preserve argument name: (original), (original)_arg_#
5. name immediate locals: _imd_#
'''




'''
Python AST Classes & Meta ID Conversion tools
'''

class PyStmt:
    def to_string(self, indent, acc_indent):
        raise NotImplementedError

    def convert_meta_id(self, driver, local_dict):
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

    def convert_meta_id(self, driver, local_dict):
        pass

def stmt_list_to_string(stmt_list, indent, acc_indent):
    return "".join([stmt.to_string(indent, acc_indent+indent)
                    for stmt in stmt_list])


class PyDefun(PyStmt):
    def __init__(self, fun_name, pos_args, kwd_args, stmt_list, star=None, dstar=None, docstring=""):
        '''
        Argument -
            kwd_args: (string | PyMetaID, PyExpr) list

        '''
        self.fun_name = fun_name # string or PyMetaID
        self.pos_args = pos_args or []
        self.kwd_args = kwd_args or []
        self.star = star
        self.dstar = dstar
        self.docstring = docstring
        self.stmt_list = stmt_list

    def convert_meta_id(self, driver, local_dict):
        local_dict = {}
        if isinstance(self.fun_name, PyMetaID):
            self.fun_name = self.fun_name.convert_meta_id(driver, local_dict).name
        self.pos_args = [(pos_arg.convert_meta_id(driver, local_dict).name
                        if isinstance(pos_arg, PyMetaID)
                        else pos_arg)
                     for pos_arg in self.pos_args]
        self.kwd_args = [(keyword.convert_meta_id(driver, local_dict).name
                            if isinstance(keyword, PyMetaID)
                            else keyword,
                          kexpr.convert_meta_id(driver, local_dict))
                         for keyword, kexpr in self.kwd_args]
        if self.star:
            if isinstance(self.star, PyMetaID):
                self.star = self.star.convert_meta_id(driver, local_dict).name
        if self.dstar:
            if isinstance(self.dstar, PyMetaID):
                self.dstar = self.dstar.convert_meta_id(driver, local_dict).name
        meta_convert_stmt_list(self.stmt_list, driver, local_dict)

    def to_string(self, indent, acc_indent):
        arglst = []

        arglst += [(pos_arg.to_string() if isinstance(pos_arg, PyMetaID) else pos_arg)
                    for pos_arg in self.pos_args]
        for keyword, arg_expr in self.kwd_args:
            if isinstance(keyword, PyMetaID):
                keyword = keyword.to_string()
            arglst.append(keyword + "=" + arg_expr.to_string())
        
        if self.star is not None:
            star = self.star
            if isinstance(star, PyMetaID):
                star = star.to_string()
            arglst.append("*" + star)
        if self.dstar is not None:
            dstar = self.dstar
            if isinstance(dstar, PyMetaID):
                dstar = dstar.to_string()
            arglst.append("**" + dstar)

        if isinstance(self.fun_name, PyMetaID):
            fun_name = self.fun_name.to_string()
        else:
            fun_name = self.fun_name
        
        return " "*acc_indent + "def {0}({1}):\n{2}" \
               .format(fun_name,
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

    def convert_meta_id(self, driver, local_dict):
        if self.ret_expr is not None:
            self.ret_expr = self.ret_expr.convert_meta_id(driver, local_dict)


class PyBreak(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "break\n"

    def convert_meta_id(self, driver, local_dict):
        pass

class PyContinue(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "continue\n"

    def convert_meta_id(self, driver, local_dict):
        pass

class PyPass(PyStmt):
    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "pass\n"

    def convert_meta_id(self, driver, local_dict):
        pass


def meta_convert_stmt_list(stmt_list, driver, local_dict):
    for stmt in stmt_list:
        stmt.convert_meta_id(driver, local_dict)


class PyForStmt(PyStmt):
    def __init__(self, elem_name, _in, stmt_list):
# elem_name can be either string or PyTupleExpr
        assert isinstance(elem_name, (str, PyMetaID, PyTupleExpr))
        self.elem_name = elem_name
        self._in = _in
        self.stmt_list = stmt_list

    def to_string(self, indent, acc_indent):
        if isinstance(self.elem_name, PyExpr):
            elem_name = self.elem_name.to_string()
        return " "*acc_indent + \
               "for {0} in {1}:\n{2}"\
                 .format(elem_name, 
                         self._in.to_string(),
                         stmt_list_to_string(self.stmt_list, indent, acc_indent))

    def convert_meta_id(self, driver, local_dict):
        if isinstance(self.elem_name, PyExpr):
            self.elem_name = self.elem_name.convert_meta_id(driver, local_dict)
        self._in = self._in.convert_meta_id(driver, local_dict)
        meta_convert_stmt_list(self.stmt_list, driver, local_dict)


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

    def convert_meta_id(self, driver, local_dict):
        self.cond_expr = self.cond_expr.convert_meta_id(driver, local_dict)
        meta_convert_stmt_list(self.stmt_list, driver, local_dict)


class PyIfStmt(PyStmt):
    def __init__(self, if_pair, elif_pairs=None, else_stmt_list=None):
        '''
        Arguments - 
            if_pair: (expr, stmt list)
            elif_pairs: (expr, stmt list) list
            else_stmt_list: stmt list
        '''

        self.if_pair = if_pair
        self.elif_pairs = elif_pairs or []
        self.else_stmt_list = else_stmt_list or []

    def convert_meta_id(self, driver, local_dict):
        meta_convert_stmt_list(self.if_pair[1], driver, local_dict)
        self.if_pair = (self.if_pair[0].convert_meta_id(driver, local_dict),
                        self.if_pair[1])

        new_elif_pairs = []
        for elif_cond_expr, elif_stmt_list in self.elif_pairs:
            meta_convert_stmt_list(elif_stmt_list, driver, local_dict)
            new_elif_pairs.append((elif_cond_expr.convert_meta_id(driver,
                                                                  local_dict),
                                   elif_stmt_list))
        self.elif_pairs = new_elif_pairs
        meta_convert_stmt_list(self.else_stmt_list, driver, local_dict)

    def to_string(self, indent, acc_indent):
        if_expr, if_stmt_list = self.if_pair

        acc_str = " "*acc_indent + \
                  "if %s:\n%s"%(if_expr.to_string(),
                                stmt_list_to_string(if_stmt_list,
                                                    indent,
                                                    acc_indent))
        if self.elif_pairs:
            def elif_chunk(elif_expr, elif_expr_stmt_list):
                res = " "*acc_indent + \
                      "elif %s:\n%s"%(elif_expr.to_string(),
                                      stmt_list_to_string(elif_expr_stmt_list,
                                                          indent,
                                                          acc_indent))
                return res
            acc_str += "".join([elif_chunk(l, r) for l, r in self.elif_pairs])
        
        if self.else_stmt_list:
            acc_str += " "*acc_indent + \
                    "else:\n%s"%stmt_list_to_string(self.else_stmt_list,
                                                       indent,
                                                       acc_indent)
        return acc_str


class PyImportStmt(PyStmt):
    def __init__(self, name_or_name_list):
        self.name_or_name_list = name_or_name_list

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + "import " + dotify(self.name_or_name_list)+ "\n"

    def convert_meta_id(self, driver, local_dict):
        pass

class PyImportFromStmt(PyStmt):
    def __init__(self, name_or_name_list, import_names):
        self.name_or_name_list = name_or_name_list
        self.import_names = import_names

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + \
               "from " + dotify(self.name_or_name_list) + \
               "import " + ", ".join(self.import_names)

    def convert_meta_id(self, driver, local_dict):
        pass

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
            result = " "*acc_indent
            result += "%s = %s\n"%(name_str, self.expr.to_string())
            return result
        elif self._type == PyAssignment.ASSIGN_ATTR:
            virtual_parent = PyAttrAccess(self.scope_expr, self.name)
            result = " "*acc_indent
            result += "%s.%s = %s\n"%(expr_to_string(self.scope_expr, virtual_parent),
                                      self.attr_name,
                                      self.expr.to_string())
            return result 
        elif self._type == PyAssignment.ASSIGN_ITEM:
            virtual_parent = PyItemAccess(self.scope_expr, self.item_expr)
            result = " "*acc_indent
            result += "%s[%s] = %s\n"%(expr_to_string(self.scope_expr, virtual_parent),
                                     self.item_expr.to_string(),
                                     self.expr.to_string())
            return result
        else:
            raise Exception("NOT REACHABLE")

    def convert_meta_id(self, driver, local_dict):
        if self._type == PyAssignment.ASSIGN_NAME:
            if isinstance(self.name, PyMetaID):
                self.name = self.name.convert_meta_id(driver, local_dict).name

        elif self._type == PyAssignment.ASSIGN_ATTR:
            self.scope_expr = self.scope_expr.convert_meta_id(driver,
                                                              local_dict)
        elif self._type == PyAssignment.ASSIGN_ITEM:
            self.scope_expr = self.scope_expr.convert_meta_id(driver,
                                                              local_dict)
            self.item_expr = self.item_expr.convert_meta_id(driver,
                                                            local_dict)
        else:
            raise Exception("NOT REACHABLE")

        self.expr = self.expr.convert_meta_id(driver, local_dict)


class PyExprStmt(PyStmt):
    def __init__(self, expr):
        assert isinstance(expr, PyExpr)
        self.expr = expr

    def to_string(self, indent, acc_indent):
        return " "*acc_indent + self.expr.to_string() + "\n"

    def convert_meta_id(self, driver, local_dict):
        self.expr = self.expr.convert_meta_id(driver, local_dict)


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

    def may_have_side_effect(self):
        # conservative condition
        return True

    def to_string(self):
        raise NotImplementedError

    def convert_meta_id(self, driver, local_dict):
        raise NotImplementedError

class PyDataReprExpr(PyExpr):
    def get_expr_pred(self):
        return 1
    

class PyTupleExpr(PyDataReprExpr):
    def __init__(self, exprs):
        self.exprs = exprs

    def may_have_side_effect(self):
        return any((expr.may_have_side_effect() for expr in self.exprs))

    def to_string(self):
        if len(self.exprs) == 1:
            return "(" + self.exprs[0].to_string + ", )"
        else:
            return "(" + \
                   ", ".join([expr.to_string() for expr in self.exprs]) + \
                   ")"

    def convert_meta_id(self, driver, local_dict):
        return PyTupleExpr([elem.convert_meta_id(driver, local_dict)
                            for elem in self.exprs])

class PyListExpr(PyDataReprExpr):
    def __init__(self, exprs):
        self.exprs = exprs

    def may_have_side_effect(self):
        return any((expr.may_have_side_effect() for expr in self.exprs))

    def to_string(self):
        return "[" + \
               ", ".join([expr.to_string() for expr in self.exprs]) + \
               "]"

    def convert_meta_id(self, driver, local_dict):
        return PyListExpr([elem.convert_meta_id(driver, local_dict)
                           for elem in self.exprs])


class PyDictExpr(PyDataReprExpr):
    def __init__(self, expr_dict):
        self.expr_dict = expr_dict

    def may_have_side_effect(self):
        return any((k.may_have_side_effect() or v.may_have_side_effect()
                    for k, v in self.expr_dict.items()))

    def to_string(self):
        return "{" + \
               ", ".join(("%s: %s"%(k.to_string(), v.to_string())
                         for k, v in self.expr_dict.items())) + \
               "}"

    def convert_meta_id(self, driver, local_dict):
        return PyDictExpr(
                dict([(k.convert_meta_id(driver, local_dict),
                       v.convert_meta_id(driver, local_dict))
                      for k, v in self.expr_dict.items()]))


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

    def may_have_side_effect(self):
        return self.lhs.may_have_side_effect() or \
               self.rhs.may_have_side_effect()

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

    def convert_meta_id(self, driver, local_dict):
        return PyBinop(self.op,
                       self.lhs.convert_meta_id(driver, local_dict),
                       self.rhs.convert_meta_id(driver, local_dict))


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

    def may_have_side_effect(self):
        return self.param.may_have_side_effect()

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


    def convert_meta_id(self, driver, local_dict):
        return PyUnop(self.op, self.param.convert_meta_id(driver, local_dict))


class PyItemAccess(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, item_expr):
        self.scope_expr = scope_expr
        self.item_expr = item_expr

    def may_have_side_effect(self):
        return True

    def to_string(self):
        return "%s[%s]"%(expr_to_string(self.scope_expr, self),
                         self.item_expr.to_string())

    def convert_meta_id(self, driver, local_dict):
        return PyItemAccess(self.scope_expr.convert_meta_id(driver, local_dict),
                            self.item_expr.convert_meta_id(driver, local_dict))

class PyAttrAccess(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, attr_name):
        assert isinstance(scope_expr, PyExpr)
        self.scope_expr = scope_expr
        self.attr_name = attr_name

    def may_have_side_effect(self):
        return True

    def to_string(self):
        return "%s.%s"%(expr_to_string(self.scope_expr, self),
                        self.attr_name)

    def convert_meta_id(self, driver, local_dict):
        return PyAttrAccess(self.scope_expr.convert_meta_id(driver, local_dict),
                            self.attr_name)

class PyArraySlice(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, scope_expr, left_slice=None, right_slice=None):
        self.scope_expr = scope_expr
        self.left_slice = left_slice
        self.right_slice = right_slice

    def may_have_side_effect(self):
        return True

    def to_string(self):
        lslice_str = self.left_slice.to_string() if self.left_slice else ""
        rslice_str = self.right_slice.to_string() if self.right_slice else ""
        return "%s[%s:%s]"%(expr_to_string(self.scope_expr, self),
                            lslice_str,
                            rslice_str)

    def convert_meta_id(self, driver, local_dict):
        new_lslice = self.left_slice.convert_meta_id(driver, local_dict) \
                        if self.left_slice else None
        new_rslice = self.right_slice.convert_meta_id(driver, local_dict) \
                        if self.right_slice else None
        return PyArraySlice(self.scope_expr.convert_meta_id(driver, local_dict),
                            new_lslice,
                            new_rslice)

class PyCall(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 2

    def __init__(self, callee_expr, arg_exprs, kw_exprs,
                 star_expr=None, dstar_expr=None):
        '''
        Arguments -
            arg_exprs: expr list
            kw_exprs: (string | PyMetaID, expr) list
        '''
        self.callee_expr = callee_expr
        self.arg_exprs = arg_exprs or []
        self.kw_exprs = kw_exprs or []
        self.star_expr = star_expr
        self.dstar_expr = dstar_expr


    def may_have_side_effect(self):
        return True


    def to_string(self):
        arglst = [x.to_string() for x in self.arg_exprs] + \
                 [keyword + "=" + x.to_string() for keyword, x in self.kw_exprs]
        
        if self.star_expr is not None:
            arglst.append("*" + self.star_expr.to_string())
        if self.dstar_expr is not None:
            arglst.append("**" + self.dstar_expr.to_string())

        return "%s(%s)"%(expr_to_string(self.callee_expr, self),
                         ", ".join(arglst))

    def convert_meta_id(self, driver, local_dict):
        callee_expr = self.callee_expr.convert_meta_id(driver, local_dict)
        arg_exprs = [pos_expr.convert_meta_id(driver, local_dict)
                            for pos_expr in self.arg_exprs]
        kw_exprs = [(keyword.convert_meta_id(driver, local_dict).name
                       if isinstance(keyword, PyMetaID) else keyword,
                     kexpr.convert_meta_id(driver, local_dict))
                    for keyword, kexpr in self.kw_exprs]
        star_expr = self.star_expr.convert_meta_id(driver, local_dict) \
                      if self.star_expr else None
        dstar_expr = self.dstar_expr.convert_meta_id(driver, local_dict) \
                       if self.dstar_expr else None
        return PyCall(callee_expr,
                      arg_exprs,
                      kw_exprs,
                      star_expr,
                      dstar_expr)



class PyLiteral(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, literal):
        self.literal = literal # itself

    def may_have_side_effect(self):
        return False

    def to_string(self):
        # Because we use python to compile sth and its target file is python itself, literal is just python object
        # and just to repr it is sufficient to represent all literals(list, dict, string and so on) in target python source 
        # Funny!
        return repr(self.literal)

    def convert_meta_id(self, driver, local_dict):
        return self


class PyMetaID(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, _id):
        self._id = _id

    def may_have_side_effect(self):
        return False

    def to_string(self):
        return "__meta_id{0}__".format(self._id)

    def convert_meta_id(self, driver, local_dict):
        return PyName(driver(self._id, local_dict))


class PyName(PyExpr):
    # @implement PyExpr
    def get_expr_pred(self):
        return 1

    def __init__(self, name):
        self.name = name

    def may_have_side_effect(self):
        return False
        
    def to_string(self):
        return self.name

    def convert_meta_id(self, driver, local_dict):
        return self


class PyLambda(PyExpr):
    def get_expr_pred(self):
        return 5

    def may_have_side_effect(self):
        return False

    def __init__(self, pos_args, kwd_args, expr, star=None, dstar=None, docstring=""):
        '''
        Argument -
            kwd_args: (string, PyExpr) list

        '''
        self.pos_args = pos_args or []
        self.kwd_args = kwd_args or []
        self.star = star
        self.dstar = dstar
        self.docstring = docstring
        self.expr = expr 

    def convert_meta_id(self, driver, local_dict):
        pos_args = [(pos_arg.convert_meta_id(driver, local_dict).name
                  if isinstance(pos_arg, PyMetaID)
                  else pos_arg)
                for pos_arg in self.pos_args]
        kwd_args = [(keyword.convert_meta_id(driver, local_dict).name
                       if isinstance(keyword, PyMetaID) else keyword,
                     kexpr.convert_meta_id(driver, local_dict))
                    for keyword, kexpr in self.kwd_args]
        expr = self.expr.convert_meta_id(driver, local_dict)
        if self.star:
            if isinstance(self.dstar, PyMetaID):
                star = self.star.convert_meta_id(driver, local_dict).name \
                        if self.star else None
            else:
                star = self.star
        else:
            star = None
        if self.dstar:
            if isinstance(self.dstar, PyMetaID):
                dstar = self.dstar.convert_meta_id(driver, local_dict).name
            else:
                dstar = self.dstar
        else:
            dstar = None


        return PyLambda(pos_args,
                        kwd_args,
                        expr,
                        star,
                        dstar,
                        self.docstring)

    def to_string(self):
        arglst = [(pos_arg.to_string() if isinstance(pos_arg, PyMetaID) else pos_arg)
                  for pos_arg in self.pos_args]
        for keyword, arg_expr in self.kwd_args:
            if isinstance(keyword, PyMetaID):
                keyword = keyword.to_string()
            arglst.append(keyword + "=" + arg_expr.to_string())
        
        if self.star is not None:
            star = self.star
            if isinstance(star, PyMetaID):
                star = star.to_string()
            arglst.append("*" + star)
        if self.dstar is not None:
            dstar = self.dstar
            if isinstance(dstar, PyMetaID):
                dstar = dstar.to_string()
            arglst.append("**" + dstar)

        return "lambda {0}: {1}" \
               .format(", ".join(arglst),
                       self.expr.to_string())

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
 * source: "local" | "argument" | "function" | "lambda" | "immediate"
 * 'let' Duplication Depth
 * usage: string set
    "return"
    "local"
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
    def __init__(self, original_name, name_source, usage):
        assert name_source in ["argument", "local", "immediate", "lambda", "function"]
        self.original_name = original_name
        self.name_source = name_source
        self.usage = usage
    
    def __repr__(self):
        return "<%s (%s, %s)>"%(self.original_name,
                                    self.name_source,
                                    self.usage)

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

    def __repr__(self):
        return "<Var %s>"%repr(self.hint)


class GlobalScopeVar(IDInfo):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<GlobalScope %s>"% self.name



class RuntimeExtern(IDInfo):
    def __init__(self, name):
        self.name = name


class Expander(IDInfo):
    '''
    expander -
        translator x lisn x CompEnv x Premise x Config x Context -> (pre bound) lisn
    '''
    def __init__(self, expander, name=""):
        self.expander = expander
        self.name = name

    def expand(self, translator, lisn, comp_env, premise, config, context):
        return self.expander(translator, lisn, comp_env, premise, config, context)

    def __repr__(self):
        return "<Syntax expander %s>"%self.name


class Converter(IDInfo):
    '''
    converter - 
        translator x lisn x CompEnv x Premise x Config x Context -> Conclusion
    '''
    def __init__(self, converter, name=""):
        self.converter = converter
        self.name = name 

    def convert(self, translator, lisn, comp_env, premise, config, context):
        return self.converter(translator, lisn, comp_env, premise, config, context)

    def __repr__(self):
        return "<Syntax converter %s>"%self.name


class EnvFrame:
    def __init__(self, frame_type):
        assert frame_type in ["def", "toplevel", "let", "lambda"]
        self.frame_type = frame_type # "def" | "toplevel" | "let" | "lambda"


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
        assert isinstance(id_info, IDInfo)
        _id = self.available_id
        self.available_id += 1
        self.id_info_dict[_id] = id_info
        return _id

    def issue_local_immediate(self):
        imd_id = self.issue_id(Var(IDHint("", "immediate", "local")))
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

    def get_hint_dict(self):
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
            local_id = comp_env.add_local(name, Var(id_hint))
    else:
        local_id = comp_env.add_local(name, Var(id_hint))
    return local_id


def ensure_local_var_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "local", "local"))

def ensure_lambda_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "lambda", "local"))

def ensure_local_arg_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "argument", "local"))

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
        assert preseq_stmts is None or all(map(lambda x: isinstance(x, PyStmt), preseq_stmts))
        assert result_expr is None or isinstance(result_expr, PyExpr)
        self.preseq_stmts = preseq_stmts or []
        self.result_expr = result_expr
        self.error = error
        self.comment = comment

    def error_occured(self):
        return self.error 
    
    def has_result(self):
        return self.result_expr is not None

    def is_pure_expr(self):
        return len(self.preseq_stmts) == 0
    
    def make_stmt_list(self):
        if self.has_result() and self.result_expr.may_have_side_effect():
            return self.preseq_stmts + [PyExprStmt(self.result_expr)]



def expr_conclusion(expr, comment=None):
    assert isinstance(expr, PyExpr)
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
    assert isinstance(result_expr, PyExpr)
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
    if any([x.error_occured() for x in conclusions]):
        return error_conclusion()

    # assume that result is not emmited with these conclusions
    stmts = []
    for concl in conclusions:
        stmts += concl.preseq_stmts
        if concl.has_result() and concl.result_expr.may_have_side_effect():
            stmts.append(PyExprStmt(concl.result_expr)) # Result might have side-effect so that we should put result expr as well

    return stmt_conclusion(stmts)


def seq_conclusion(conclusions):
    if any([x.error_occured() for x in conclusions]):
        return error_conclusion()
    stmts = []

    rest_concl = noreturn_conclusion(conclusions[:-1])
    last_concl = conclusions[-1]

    return stmt_result_conclusion(rest_concl.preseq_stmts + last_concl.preseq_stmts,
                                  last_concl.result_expr)
    

def make_integrator(allow_None):
    def integrate_conclusion(comp_env, result_proc, *conclusions):
        '''
        result_proc: A x A x A x .. -> PyExpr | (PyStmt | PyStmt list, None | PyExpr)
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
                elif not result_expr.may_have_side_effect():
                    preseq_stmts.extend(a.preseq_stmts)
                    return result_expr
                else:
                    preseq_stmts.extend(a.preseq_stmts)
                    result_id = comp_env.issue_local_immediate()
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

        result = result_proc(*argument_exprs)
        if isinstance(result, PyExpr):
            return stmt_result_conclusion(preseq_stmts, result)
        elif isinstance(result, tuple):
            if len(result) != 2:
                raise ValueError("length of result tuple should be 2")
            if not isinstance(result[0], PyStmt) and not all(map(lambda x: isinstance(x, PyStmt),  result[0])):
                raise TypeError("The first elem of result should be a PyStmt or a list of PyStmt")

            additional_stmts, result_expr = result
            if isinstance(additional_stmts, PyStmt):
                additional_stmts = [additional_stmts]
            if result_expr is not None and not isinstance(result_expr, PyExpr):
                raise TypeError("The second elem of result should be None or PyExpr")
            
            if result_expr is None:
                return stmt_conclusion(preseq_stmts + additional_stmts)
            else:
                return stmt_result_conclusion(preseq_stmts + additional_stmts, result_expr)
        else:
            raise TypeError("Invalid return type of 'result_proc'")

    return integrate_conclusion

integrate_conclusion = make_integrator(False)
xintegrate_conclusion = make_integrator(True)


def integrate_list(comp_env, conclusions):
    '''
    CompEnv, Conclusion list -> 
    Results -
        (
            bool, # success?
            stmt list, # preseq_stmts
            (string, expr) list # result_pairs
        }
    '''
    preseq_stmts = []
    result = []
    used_imd_ids = []
    success = True
    for concl in conclusions:
        if concl.error_occured():
            success = False
        elif not concl.has_result():
            preseq_stmts += concl.preseq_stmts
            result.append(PyLiteral(None))
        else:
            expr = concl.result_expr
            preseq_stmts += concl.preseq_stmts
            if expr.may_have_side_effect():
                imd_id = comp_env.issue_local_immediate()
                used_imd_ids.append(imd_id)
                preseq_stmts.append(PyAssignmentToName(PyMetaID(imd_id),
                                                       expr))
                result.append(PyMetaID(imd_id))
            else:
                result.append(expr)

    return (success, preseq_stmts, result, used_imd_ids)

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


#
# Translators
#

node_translator = LISNVisitor()
def stmtify_expr(expr, use_return_value, imd_id):
    '''
    CompEnv x bool x id -> stmt list
    '''
    assert isinstance(expr, PyExpr)
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
    trailer_type = lisn["trailer_type"] 
    scope = lisn["scope"]
    
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
        def f(scope_expr):
            return PyAttrAccess(scope_expr, attr)

        attr = lisn["attr"]
        return integrate_conclusion(comp_env, f, scope_concl)
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
        if comp_env.has_name(name):
            name_id, info = comp_env.lookup_name(name)
        else:
            set_comp_error(context,
                           CompErrorObject("UnboundVariable",
                                           "Name '%s' is not found"%name,
                                           "<source>",
                                           lisn["locinfo"]))
            return error_conclusion()

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
                                  lisn["locinfo"])
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
                                      (PyAssignmentToName(PyMetaID(local_id),
                                                          param_expr),
                                       PyLiteral(None)),
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
                                      (PyAssignmentToAttr(scope_expr,
                                                          lvalue_name,
                                                          param_expr),
                                       PyLiteral(None)),
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
                                      (PyAssignmentToItem(scope_expr,
                                                          index_expr,
                                                          param_expr),
                                       PyLiteral(None)),
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

    if lisn["has_head_label"]:
        head_label = lisn["head_label"]
        if head_label == "def":
            return translate_def(translator, lisn, comp_env, Premise(False), config, context)
        elif head_label == "import":
            return translate_import(translator, lisn, comp_env, Premise(False), config, context)
        elif head_label == "import_from":
            return translate_import_from(translator, lisn, comp_env, Premise(False), config, context)
        else:
            set_comp_error(context,
                           CompErrorObject(
                               "UnknownHeadLabel",
                               "Unknown head label: %s"%head_label,
                               "<source>",
                               lisn["locinfo"]))
            return error_conclusion()
    else:
        head_expr = lisn["head_expr"]
        head_expr_name = force_name(head_expr)
        arg_info = lisn["arg_info"]
        success = True

        # lookahead
        if head_expr_name is not None and \
            comp_env.has_name(head_expr_name):
            _, info = comp_env.lookup_name(head_expr_name)
            if info.is_expander():
                return translator(info.expand(translator,
                                              lisn,
                                              comp_env,
                                              premise,
                                              config,
                                              context),
                                  comp_env,
                                  premise,
                                  config,
                                  context)
            elif info.is_converter():
                return info.convert(translator, lisn, comp_env, premise, config, context)

        # function-style xexpr
        if lisn["has_vert_suite"]:
            set_comp_error(context,
                           CompErrorObject(
                               "IllegalCall",
                               "Vertical Arguments should not be applied to function",
                               "<source>",
                               lisn["locinfo"]))
            success = False
        applicant_concl = translator(head_expr, comp_env, Premise(True), config, context)
        parg_concls = [translator(parg, comp_env, Premise(True), config, context) for parg in arg_info["pargs"]]
        karg_keywords = [k for k, _ in arg_info["kargs"]]
        karg_concls = [translator(karg, comp_env, Premise(True), config, context) for _, karg in arg_info["kargs"]]
        star_concl = translator(arg_info["star"],
                                comp_env,
                                Premise(True),
                                config,
                                context) if arg_info["has_star"] else None
        dstar_concl = translator(arg_info["dstar"],
                                 comp_env,
                                 Premise(True),
                                 config,
                                 context) if arg_info["has_dstar"] else None


        if not success:
            return error_conclusion()

        return xintegrate_conclusion(comp_env,
                                    lambda callee_expr, parg_exprs, karg_exprs, star_expr, dstar_expr: \
                                      PyCall(callee_expr,
                                             parg_exprs, 
                                             zip(karg_keywords, karg_exprs),
                                             star_expr,
                                             dstar_expr),
                                    applicant_concl,
                                    parg_concls,
                                    karg_concls,
                                    star_concl,
                                    dstar_concl)

@LISNPattern
def branch_pat(case, default):
    '''
    Returns -
        (success, failure_reason, cond_pairs, else_pair_or_None)
    '''

    @case
    def f(obj):
        '''
        if>
            __kleene_plus__(predicates): $expr
        --
            __kleene_plus__(consequents): $expr
        '''
        predicates = [d["expr"] for d in obj["predicates"]]
        consequents = [d["expr"] for d in obj["consequents"]]
        if len(predicates) == len(consequents):
            return (True, "", zip(predicates, consequents), None)
        elif len(predicates) + 1 == len(consequents):
            return (True, "", zip(predicates, consequents[:-1]), consequents[-1])
        else:
            conseq_cnt = len(consequents)
            return (False, "Number of predicates is expected to be %d or %d" % (conseq_cnt - 1, conseq_cnt),
                    [], None)

    @default
    def el():
        return (False, "Bad Form", [], None)


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
        elif concl.has_result():
            if concl.is_pure_expr() or \
               concl.result_expr.may_have_side_effect():
                return stmtify_expr(concl.result_expr, False, None)
            else:
                return concl.preseq_stmts + \
                       stmtify_expr(concl.result_expr, False, None)
        else:
            return concl.preseq_stmts

    def set_branch_error(lisn, msg):
        set_comp_error(context,
                       CompErrorObject("Branch",
                                       msg,
                                       "<source>",
                                       lisn["locinfo"]))

    success, error_reason, cond_pairs, else_lisn = branch_pat(lisn)
    if not success:
        set_branch_error(lisn, error_reason)
        return error_conclusion()
    
    preseq_stmts = []
    first = True
    success = True

    if_stmt = PyIfStmt(None)
    iter_if_stmt = if_stmt
    for pred, conseq in cond_pairs:
        cur_success = True
        pred_concl = translator(pred, 
                          comp_env, 
                          Premise(True), 
                          config, 
                          context)
        conseq_concl = translator(conseq, 
                                  comp_env, 
                                  premise.copy(), 
                                  config, 
                                  context)

        if pred_concl.error_occured():
            success = False
            cur_success = False
        elif conseq_concl.error_occured():
            success = False
            cur_success = False

        if cur_success:
            if iter_if_stmt.if_pair is None:
                preseq_stmts.extend(pred_concl.preseq_stmts)
                iter_if_stmt.if_pair = (pred_concl.result_expr,
                                        conclusion_to_stmts(conseq_concl))
            else:
                if pred_concl.is_pure_expr():
                    iter_if_stmt.elif_pairs.append(
                        (pred_concl.result_expr,
                         conclusion_to_stmts(conseq_concl)))
                else:
                    iter_if_stmt.else_stmt_list.extend(pred_concl.preseq_stmts)
                    nested_if_stmt = PyIfStmt((
                        pred_concl.result_expr,
                        conclusion_to_stmts(conseq_concl)))
                    iter_if_stmt.else_stmt_list.append(nested_if_stmt)
                    iter_if_stmt = nested_if_stmt


    if else_lisn:
        else_concl = translator(else_lisn,
                                comp_env,
                                premise.copy(), 
                                config,
                                context)
        if else_concl.error_occured():
            success = False
    else:
        else_concl = expr_conclusion(PyLiteral(None))

    iter_if_stmt.else_stmt_list = conclusion_to_stmts(else_concl)

    if not success:
        return error_conclusion()

    preseq_stmts.append(if_stmt)
    if use_return_value:
        return stmt_result_conclusion(preseq_stmts,
                                      PyMetaID(result_id))
    else:
        return stmt_conclusion(preseq_stmts)
    

def is_def_node(node):
    return check_multi_xexpr(node, "def")


def xtranslate_seq(translator, node_list, comp_env, premise, config, context):
    use_return_value = premise.use_return_value
    success = True
    concls = []
    if node_list:
        last_node = node_list[-1]
        for node in node_list:
            child_premise = Premise(use_return_value and node is last_node)
            if is_def_node(node):
                def_name = force_name_to_head_expr(node)
                if def_name is None:
                    set_comp_error(context,
                                   CompErrorObject("DefName",
                                                   "Name of def node is not appropriate",
                                                   "<source>",
                                                   node["locinfo"]))
                    success = False
                else:
                    function_id = ensure_function_name(comp_env, def_name)
                    child_premise.prebound_id = function_id # HACK?

                    @delay(node, comp_env, child_premise, config, context)
                    def translation_promise(node, comp_env, child_premise, config, context):
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

def ltranslate_in_app_order(translator, node_list, comp_env, premise, config, context):
    '''
    Returns -
        (success,
         Pre-sequential stmts, 
         list of expr )

    '''
    preseq_stmts = []
    result_exprs = []
    success = True
    for node in node_list:
        concl = translator(node, comp_env, Premise(True), config, context)
        if concl.error_occured():
            success = False
            continue
        preseq_stmts.extend(concl.preseq_stmts)
        if concl.has_result() and concl.result_expr.may_have_side_effect():
            imd_id = comp_env.issue_local_immediate()
            preseq_stmts.append(PyAssignmentToName(PyMetaID(imd_id), concl.result_expr))
            result_exprs.append(PyMetaID(imd_id))
        else:
            result_exprs.append(concl.result_expr)
    return (success, preseq_stmts, result_exprs)

def translate_suite(translator, suite, comp_env, premise, config, context):
    node_list = suite_to_node_list(suite)
    return xtranslate_seq(translator, node_list, comp_env, premise, config, context )

def translate_def(translator, lisn, comp_env, premise, config, context):
    assert is_def_node(lisn)

    def gather_formal_info():
        arg_info = lisn["arg_info"]
        parg_strs = []
        kwd_pairs = []
        star_str = None
        dstar_str = None

        argument_test_success = True
        for parg_node in arg_info["pargs"]:
            parg_str = force_name(parg_node)
            if parg_str is None:
                argument_test_success = False
            else:
                parg_strs.append(parg_str)

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
            return (def_name, parg_strs, kwd_pairs, star_str, dstar_str)
        else:
            return None

    def make_defun(def_xexpr, def_id, parg_ids, karg_id_pairs, star_id, dstar_id):
        '''
        Return - 
            PyDefun
        '''
        if def_xexpr["has_vert_suite"]:
            def_stmts = []
            suite = def_xexpr["vert_suite"]
            concl = translator(suite, comp_env, Premise(True), config, context)
            def_stmts = concl.preseq_stmts
            def_stmts.append(PyReturn(concl.result_expr))
        else:
            def_stmts = [PyPass()]
        return PyDefun(def_id,
                       parg_ids,
                       karg_id_pairs,
                       def_stmts,
                       star_id,
                       dstar_id)

    formal_info = gather_formal_info()
    if formal_info is None:
        return error_conclusion()
    # def_name: string
    # parg_strs: string list
    # kwd_pairs: (string, node) list
    def_name, parg_strs, kwd_pairs, star_str, dstar_str = formal_info
    keywords = [k for k, _ in kwd_pairs]
    kw_concls = [translator(knode,
                            comp_env,
                            Premise(True),
                            config,
                            context)
                   for _, knode in kwd_pairs]
    kw_success, preseq_stmts, karg_default_exprs, _ = integrate_list(comp_env, kw_concls)
    if not kw_success:
        return error_conclusion()

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
    for name in parg_strs + \
                keywords + \
                ([star_str] if star_str else []) + \
                ([dstar_str] if dstar_str else []):
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
    parg_ids = []
    karg_id_pairs = []
    for name in parg_strs:
        parg_ids.append(PyMetaID(ensure_local_arg_name(comp_env, name)))

    for name, kexpr in zip(keywords, karg_default_exprs):
        k_id = ensure_local_arg_name(comp_env, name)
        karg_id_pairs.append((PyMetaID(k_id), kexpr))

    star_id = None
    dstar_id = None
    if star_str:
        star_id = PyMetaID(ensure_local_arg_name(comp_env, star_str))
    if dstar_str:
        dstar_id = PyMetaID(ensure_local_arg_name(comp_env, dstar_str))
    defun = make_defun(lisn,
                       PyMetaID(function_id),
                       parg_ids,
                       karg_id_pairs,
                       star_id,
                       dstar_id)

    ## DEL ENV
    comp_env.contract_local_frame() 

    if premise.use_return_value:
        return stmt_result_conclusion(preseq_stmts + [defun], PyLiteral(None))
    else:
        return stmt_conclusion(preseq_stmts + [defun])

def translate_let(translator, lisn, comp_env, premise, config, context):
    if lisn["has_vert_suite"]:
        arg_info = lisn["arg_info"]
        # TODO: syntax checking ( keyword duplication, prohbiting star&dstar argument)
        kargs = arg_info["kargs"]
        keywords = [k for k, _ in kargs]
        concls = [translator(node, comp_env, Premise(True), config, context)
                    for _, node in kargs]
        success, preseq_stmts, let_exprs, _ = integrate_list(comp_env, concls)

        comp_env.setup_local_frame("let")
        for name, expr in zip(keywords, let_exprs):
            let_id = ensure_local_var_name(comp_env, name)
            preseq_stmts += stmtify_expr(expr, True, let_id)

        suite_result = translator(lisn["vert_suite"], comp_env, premise.copy(), config, context)
        if suite_result.error_occured():
            success = False
            result_expr = None
        else:
            preseq_stmts += suite_result.preseq_stmts
            if suite_result.has_result():
                result_expr = suite_result.result_expr
            else:
                result_expr = PyLiteral(None)

        comp_env.contract_local_frame()
        if not success:
            return error_conclusion()
        elif premise.use_return_value:
            return stmt_result_conclusion(preseq_stmts, result_expr)
        else:
            if result_expr.may_have_side_effect():
                preseq_stmts += stmtify_expr(result_expr, False, None)
            return stmt_conclusion(preseq_stmts)
    else:
        return expr_conclusion(PyLiteral(None))


def translate_seq(translator, lisn, comp_env, premise, config, context):
    if lisn["has_vert_suite"]:
        return translator(lisn["vert_suite"], comp_env, premise, config, context)
    else:
        return expr_conclusion(PyLiteral(None))

@LISNPattern
def lambda_pat(case, default):
    '''
    (success, failure_reason, parg, karg, star, dstar, body)
    '''

    @case
    def lam(obj):
        '''
        lambda>
            kleene_star(parg): NAME$name
            keyword -> dict(karg)
            *__optional__(star): NAME$name
            **__optional__(dstar): NAME$name
        --
            __kleene_plus__(body): $expr
        '''
        parg = [x["name"] for x in obj["parg"]]
        karg = obj["karg"]["__rest__"]
        star = obj["star"]["name"] if obj["star"] else None
        dstar = obj["dstar"]["name"] if obj["dstar"] else None
        body = [x["expr"] for x in obj["body"]]

        return (True, "", parg, karg, star, dstar, body)

    @default
    def el():
        return (False, "Bad form", None, None, None, None, [])


def translate_lambda(translator, lisn, comp_env, premise, config, context):
    # pure expr -> use function
    # expr with pre-sequential stmts -> def
    # TODO
    pass


@LISNPattern
def for_pat(case, default):
    @case
    def fr(obj):
        '''
        NAME$for>
            NAME$elem
            keyword -> seq:
                __optional__(opt):
                    index -> NAME$index_name
                in -> $iterable
        --
            __kleene_plus__(body): $expr
        '''
        elem = obj["elem"]
        iterable = obj["iterable"]
        index = obj["opt"]["index_name"] if obj["opt"] else None
        body = [x["expr"] for x in obj["body"]]

        return (True, "", elem, index, iterable, body)

    @case
    def fr2(obj):
        '''
        NAME$for>
            pair>
                __kleene_plus__(elems): $elem
            keyword -> seq:
                __optional__(opt):
                    index -> NAME$index_name
                in -> $iterable
        --
            __kleene_plus__(body): $expr
        '''
        raise Exception
        elem = [s["elem"] for s in obj["elems"]]
        iterable = obj["iterable"]
        index = obj["opt"]["index_name"] if obj["opt"] else None
        body = [x["expr"] for x in obj["body"]]

        return (True, "", elem, index, iterable, body)


    @default
    def el():
        return (False, "Bad form", None, None, None, None)




def _translate_iter_head(translator, lisn, comp_env, premise, config, context,
                         body_kont, error_handler):
    success, failure_reason, elem, index, iterable, body = for_pat(lisn)

    if not success:
        error_handler(failure_reason)
        return error_conclusion()

    enumerate_id, _ = comp_env.lookup_global_name("enumerate")

    iterable_concl = translator(iterable, comp_env, Premise(True), config, context)
    preseq_stmts = iterable_concl.preseq_stmts
    iterable_expr = iterable_concl.result_expr 

    elem_obj = None
    index_id = None
    if isinstance(elem, tuple):
        elem_ids = [PyMetaID(ensure_local_var_name(comp_env, x))
                    for x in elem]
        if index is not None:
            index_id = ensure_local_var_name(comp_env, index)
            elem_ids.insert(0, PyMetaID(index_id))
            iterable_expr = PyCall(PyMetaID(enumerate_id), [iterable_expr], None)
        elem_obj = PyTupleExpr(elem_ids)
    else:
        elem_id = ensure_local_var_name(comp_env, elem)
        if index is not None:
            index_id = ensure_local_var_name(comp_env, index)
            elem_obj = PyTupleExpr([PyMetaID(index_id), PyMetaID(elem_id)])
            iterable_expr = PyCall(PyMetaID(enumerate_id), [iterable_expr], None)
        else:
            elem_obj = PyMetaID(elem_id)

    return body_kont(preseq_stmts, elem_obj, iterable_expr, body)



def translate_for(translator, lisn, comp_env, premise, config, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = comp_env.issue_local_immediate()
    else:
        result_id = None

    def kont(head_preseq_stmts, elem_obj, iterable_expr, body):
        body_concl = xtranslate_seq(translator,
                                    body,
                                    comp_env,
                                    premise.copy(),
                                    config,
                                    context)
        stmts = head_preseq_stmts
        body_stmts = body_concl.preseq_stmts
        body_result_expr = body_concl.result_expr
        if use_return_value:
            body_stmts.append(PyExprStmt(PyCall(PyAttrAccess(PyMetaID(result_id), "append"),
                                                [body_result_expr],
                                                None)))
        stmts.append(PyForStmt(elem_obj, iterable_expr, body_stmts))
                                
        if use_return_value:
            stmts.insert(0, PyAssignmentToName(PyMetaID(result_id), PyLiteral([])))
            return stmt_result_conclusion(stmts, PyMetaID(result_id))
        else:
            return stmt_conclusion(stmts)

    def error_handler(reason):
        set_comp_error(context,
                       CompErrorObject("for",
                                       reason,
                                       "<source>",
                                       lisn["locinfo"]))

    return _translate_iter_head(translator, lisn, comp_env, premise.copy(), config, context,
                                kont, error_handler)


def translate_each(translator, lisn, comp_env, premise, config, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = comp_env.issue_local_immediate()
    else:
        result_id = None

    def kont(head_preseq_stmts, elem_obj, iterable_expr, body):
        success, body_stmts, result_exprs = ltranslate_in_app_order(translator,
                                                                    body,
                                                                    comp_env,
                                                                    Premise(True),
                                                                    config,
                                                                    context)
        if not success:
            return error_conclusion()

        stmts = head_preseq_stmts
        if use_return_value:
            body_stmts.append(PyExprStmt(PyCall(PyAttrAccess(PyMetaID(result_id), "extend"),
                                                [PyListExpr(result_exprs)],
                                                None)))

        stmts.append(PyForStmt(elem_obj,
                               iterable_expr, 
                               body_stmts))
                                
        if use_return_value:
            stmts.insert(0, PyAssignmentToName(PyMetaID(result_id), PyLiteral([])))
            return stmt_result_conclusion(stmts, PyMetaID(result_id))
        else:
            return stmt_conclusion(stmts)

    def error_handler(reason):
        set_comp_error(context,
                       CompErrorObject("each",
                                       reason,
                                       "<source>",
                                       lisn["locinfo"]))

    return _translate_iter_head(translator, lisn, comp_env, premise.copy(), config, context,
                                kont, error_handler)


@LISNPattern
def html_node_pat(case, default):
    @case
    def cond(obj):
        '''
        NAME$html_node>
            keyword -> dict(attr)
        --
            __kleene_star__(body): $expr
        '''
        tag_name = obj["html_node"]
        attr = obj["attr"]["__rest__"]
        body = [x["expr"] for x in obj["body"]]
        return (True, "", tag_name, attr, body)

    @default
    def el():
        return (False, "Bad Form", None, None, None)


def translate_html_node(translator, lisn, comp_env, premise, config, context):
    runtime_id = context.runtime_obj_id
    success, failure_reason, tag_name, attr, body = html_node_pat(lisn)

    if not success:
        set_comp_error(context,
                       CompErrorObject("HtmlNode",
                                       failure_reason,
                                       "<source>",
                                       lisn["locinfo"]))
        return error_conclusion()

    attr_pairs = attr.items()
    attr_keys = [k for k, _ in attr_pairs]
    success, stmts, param_exprs = \
        ltranslate_in_app_order(translator,
                                [v for _, v in attr_pairs] + body,
                                comp_env,
                                Premise(True),
                                config,
                                context)
    attr_exprs = param_exprs[:len(attr_pairs)]
    body_exprs = param_exprs[len(attr_pairs):]


    caller_pargs = [PyDictExpr(dict(zip(map(PyLiteral, attr_keys), attr_exprs)))]
    caller_pargs.extend(body_exprs)

    mk = PyCall(PyAttrAccess(PyAttrAccess(PyMetaID(runtime_id),
                                          "html"),
                             tag_name),
                caller_pargs,
                None)
    return stmt_result_conclusion(stmts, mk)

        
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
        accessor = PyMetaID(context.importer_id)
        for name in names:
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
            if obj["param"]["type"] != "name":
                set_comp_error(context,
                               CompErrorObject("IllegalImportName",
                                               "Invalid import name",
                                               "<source>", suite["param"]["locinfo"]))
                success = False
                continue
            dest_name = obj["param"]["name"]
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
        accessor = PyMetaID(context.importer_id)
        for name in module_names:
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
    glob = {}
    exec("", glob)
    for name in glob["__builtins__"].keys():
        comp_env.add_global(name, GlobalScopeVar(name))


def setup_base_syntax(comp_env):
    add_python_native(comp_env)
    comp_env.add_global("if",
                        Converter(translate_branch,
                                  "if"))
    comp_env.add_global("let",
                        Converter(translate_let,
                                  "let"))
    comp_env.add_global("seq",
                        Converter(translate_seq,
                                  "seq"))
    comp_env.add_global("for",
                        Converter(translate_for,
                                  "for"))
    comp_env.add_global("each",
                        Converter(translate_each,
                                  "each"))

def setup_html_runtime(comp_env):
    for tag_name in HTML_TAGS:
        comp_env.add_global(tag_name,
                            Converter(translate_html_node,
                                      tag_name))

_PYTHON_RESERVED_WORDS = set([
    'and',
    'del',
    'from',
    'not',
    'while',
    'as',
    'elif',
    'global',
    'or',
    'with',
    'assert',
    'else',
    'if',
    'pass',
    'yield',
    'break',
    'except',
    'import',
    'print',
    'class',
    'exec',
    'in',
    'raise',
    'continue',
    'finally',
    'is',
    'return',
    'def',
    'for',
    'lambda',
    'try'])

def is_python_reserved_word(name):
    return name in _PYTHON_RESERVED_WORDS 


def main_translate(suite, config=None):
    config = config or Config()
    comp_env = CompEnv()
    setup_base_syntax(comp_env)
    setup_html_runtime(comp_env)

    comp_env.setup_local_frame("def")

    runtime_obj_id = comp_env.add_local("__runtime__",
                                        Var(IDHint("__runtime__",
                                                   "argument",
                                                   "local")))

    importer_id = comp_env.add_local("__importer__",
                                     Var(IDHint("__importer__",
                                                "argument",
                                                "local")))
    line_info_id = comp_env.add_local("__line__",
                                      Var(IDHint("__line__",
                                                 "argument",
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
        if main_concl.error_occured():
            success = False 
        else:
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
        elif local_name.startswith("_"):
            continue
        kw_arguments.append((local_name, PyMetaID(local_id)))

    def_stmts.append(PyReturn(PyCall(PyMetaID(dict_sym_id),
                                     None,
                                     kw_arguments)))
    comp_env.contract_local_frame()
    def_mk_tmp = PyDefun("tempy_main",
                         [PyMetaID(context.runtime_obj_id),
                          PyMetaID(context.importer_id),
                          PyMetaID(context.line_info_id)],
                         None,
                         def_stmts)

    hint_dict = comp_env.get_hint_dict()
    def naive_renaming_driver(_id, local_dict):
        id_hint = hint_dict[_id]
        if isinstance(id_hint, IDHint):
            name_source = id_hint.name_source
            if name_source == "argument":
                suffix = "_arg"
            elif name_source == "local":
                suffix = "_"
            elif name_source == "immediate":
                suffix = "_imd"
            elif name_source == "lambda":
                suffix = "_lam"
            elif name_source == "function":
                suffix = "_f"
            else:
                print "INVALID NAME SOURCE:", name_source
                NOT_REACHABLE()

            first_name = id_hint.original_name \
                         if not is_python_reserved_word(id_hint.original_name) \
                         else "_" + id_hint.original_name
            if first_name == "":
                first_name = "_"
            trial_count = 0
            while True:
                trial_name = first_name if trial_count == 0 else (first_name + suffix + str(trial_count))
                if trial_name not in local_dict or local_dict[trial_name] == _id:
                    local_dict[trial_name] = _id
                    return trial_name
                trial_count += 1
            NOT_REACHABLE()
        else:
            return id_hint
    def_mk_tmp.convert_meta_id(naive_renaming_driver, {})
    return def_mk_tmp

def translate_string(s):
    suite = loads(s)
    return main_translate(suite)


def translate_file(filepath):
    node = loads_file(filepath)
    return main_translate(node)
