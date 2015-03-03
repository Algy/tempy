from tag import is_tag_name, HTML_TAGS
from lisn import loads, loads_file, LISNSyntaxException
from lisn.utils import LISNVisitor
from lisn.match import LISNPattern
from functools import wraps
from copy import copy
from pprint import pprint
from errors import TempyCompileError, TempySyntaxError, CompileError

'''
Utils
'''
def identity(x):
    return x

def NOT_REACHABLE():
    raise Exception("Not reachable")

def dotify(name_or_name_list):
    if isinstance(name_or_name_list, basestring):
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

class PyRaise(PyStmt):
    def __init__(self, to_be_throwed=None):
        self.to_be_throwed = to_be_throwed 

    def to_string(self, indent, acc_indent):
        result = " "*acc_indent + "raise"
        if self.to_be_throwed is not None:
            result += " "
            result += self.to_be_throwed.to_string()
        result += "\n"
        return result


    def convert_meta_id(self, driver, local_dict):
        if self.to_be_throwed is not None:
            self.to_be_throwed = self.to_be_throwed.convert_meta_id(driver, local_dict)


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
    def __init__(self, name_or_name_list, alias):
        self.name_or_name_list = name_or_name_list
        self.alias = alias # string or PyMetaID

    def to_string(self, indent, acc_indent):
        if isinstance(self.alias, PyMetaID):
            alias_str = self.alias.to_string().name
        elif isinstance(self.alias, basestring):
            alias_str = self.alias
        else:
            alias_str = ""
        if alias_str:
            alias_str = " as " + alias_str
        return " "*acc_indent + "import " + dotify(self.name_or_name_list) + alias_str + "\n"

    def convert_meta_id(self, driver, local_dict):
        if isinstance(self.alias, PyMetaID):
            self.alias = self.alias.convert_meta_id(driver, local_dict).name

class PyImportFromStmt(PyStmt):
    def __init__(self, name_or_name_list, import_names):
        self.name_or_name_list = name_or_name_list
        self.import_names = import_names

    def to_string(self, indent, acc_indent):
        result = " "*acc_indent + \
                 "from " + dotify(self.name_or_name_list) + \
                 " import "

        addhoc = ""
        for name_or_pair in self.import_names:
            if addhoc:
                addhoc += ", "
            if isinstance(name_or_pair, tuple):
                src, dest = name_or_pair
                if isinstance(dest, PyMetaID):
                    dest = dest.to_string().name
                addhoc += "%s as %s"%(src, dest)
            else:
                addhoc += name_or_pair
        return result + addhoc + "\n"

    def convert_meta_id(self, driver, local_dict):
        new_ins = []
        for item in self.import_names:
            if isinstance(item, tuple):
                src, dest = item
                new_ins.append((src, dest.convert_meta_id(driver, local_dict).name))
            else:
                new_ins.append(item)
        self.import_names = new_ins


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
            return "(" + self.exprs[0].to_string() + ", )"
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

class NoMoreErrorAcceptable(Exception):
    '''
    Exception for internal use
    '''
    pass


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
        translator x lisn x Premise x Context -> (pre bound) lisn
    '''
    def __init__(self, expander, name=""):
        self.expander = expander
        self.name = name

    def expand(self, translator, lisn, premise, context):
        return self.expander(translator, lisn, premise, context)

    def __repr__(self):
        return "<Syntax expander %s>"%self.name


class Converter(IDInfo):
    '''
    converter - 
        translator x lisn x Premise x Context -> Conclusion
    '''
    def __init__(self, converter, name=""):
        self.converter = converter
        self.name = name 

    def convert(self, translator, lisn, premise, context):
        return self.converter(translator, lisn, premise, context)

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

    def error_occurred(self):
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

_cached_error_conclusion = Conclusion(None,
                                      None,
                                      error=True,
                                      comment=None)
def error_conclusion(comment=None):
    if comment is None:
        return _cached_error_conclusion
    else:
        conclusion = Conclusion(None,
                                None,
                                error=True,
                                comment=comment)
        return conclusion


def noreturn_conclusion(conclusions):
    if any([x.error_occurred() for x in conclusions]):
        return error_conclusion()

    # assume that result is not emmited with these conclusions
    stmts = []
    for concl in conclusions:
        stmts += concl.preseq_stmts
        if concl.has_result() and concl.result_expr.may_have_side_effect():
            stmts.append(PyExprStmt(concl.result_expr)) # Result might have side-effect so that we should put result expr as well

    return stmt_conclusion(stmts)


def seq_conclusion(conclusions):
    if any([x.error_occurred() for x in conclusions]):
        return error_conclusion()
    stmts = []

    rest_concl = noreturn_conclusion(conclusions[:-1])
    last_concl = conclusions[-1]

    return stmt_result_conclusion(rest_concl.preseq_stmts + last_concl.preseq_stmts,
                                  last_concl.result_expr)
    

def make_integrator(allow_None):
    def integrate_conclusion(comp_env, result_proc, *conclusions):
        '''
        result_proc: A x A x A x .. -> PyExpr | ((PyStmt | PyStmt list), (None | PyExpr))
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
                if a.error_occurred():
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
            expr list, # results
            expr list # used_imd_ids
        }
    '''
    preseq_stmts = []
    result = []
    used_imd_ids = []
    success = True
    for concl in conclusions:
        if concl.error_occurred():
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

class RuntimeStore:
    def __init__(self, runtime_obj_id, importer_id, line_info_id):
        self.runtime_obj_id = runtime_obj_id
        self.importer_id = importer_id
        self.line_info_id = line_info_id


class Context:
    def __init__(self, comp_env, config, rt_store, filename):
        self.comp_env = comp_env
        self.config = config
        self.rt_store = rt_store
        self.errors = []
        self.filename = filename

    def add_error(self, error_obj):
        self.errors.append(error_obj)
        if self.config.max_error_cnt <= len(self.errors):
            raise NoMoreErrorAcceptable

    def any_error(self):
        return len(self.errors) > 0

def set_comp_error(context, error_obj):
    if not error_obj.filename:
        error_obj.filename = context.filename
    context.add_error(error_obj)


#
# Translators
#

node_translator = LISNVisitor()
def stmtify_expr(expr, use_return_value, imd_id=None):
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
    def wrapper(translator, lisn, premise, context):
        conclusion = fun(translator, lisn, premise, context)
        assert isinstance(conclusion, Conclusion)

        if context.config.emit_line_info:
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
def nt_trailer(translator, lisn, premise, context):
    trailer_type = lisn["trailer_type"] 
    scope = lisn["scope"]
    
    if scope is None:
        set_comp_error(context,
                       CompileError("Scope",
                                       "scope should be specified",
                                       lisn["locinfo"]))
        return error_conclusion()

    scope_concl = translator(scope,
                             Premise(True),
                             context)

    if trailer_type == "attr":
        def f(scope_expr):
            return PyAttrAccess(scope_expr, attr)

        attr = lisn["attr"]
        return integrate_conclusion(context.comp_env, f, scope_concl)
    elif trailer_type == "array":
        index_param = lisn["index_param"]
        item_concl = translator(index_param,
                                Premise(True),
                                context)

        return integrate_conclusion(context.comp_env,
                                    PyItemAccess,
                                    scope_concl,
                                    item_concl)

    elif trailer_type == "slice":
        left_slice = lisn["left_slice"]
        right_slice = lisn["right_slice"]

        left_slice_concl = translator(left_slice,
                                      Premise(True),
                                      context) \
                            if left_slice else None
        right_slice_concl = translator(right_slice,
                                       Premise(True),
                                       context) \
                             if right_slice else None


        if left_slice is None and right_slice is None:
            return integrate_conclusion(context.comp_env,
                lambda scope_expr: PyArraySlice(scope_expr, None, None),
                scope_concl
            )

        elif left_slice is None:
            return integrate_conclusion(context.comp_env,
                lambda scope_expr, right_expr: PyArraySlice(scope_expr, None, right_expr),
                scope_concl,
                right_slice_concl
            )
        elif right_slice is None:
            return integrate_conclusion(context.comp_env,
                lambda scope_expr, left_expr: PyArraySlice(scope_expr, left_expr, None),
                scope_concl,
                left_slice_concl
            )
        else:
            return integrate_conclusion(context.comp_env,
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
def nt_name(translator, lisn, premise, context):
    name = lisn["name"]
    use_return_value = premise.use_return_value

    def set_noreturn_error(name):
        set_comp_error(context, CompileError("NoReturnValue",
                                                "'%s' cannot have return value" % name,
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
        if context.comp_env.has_name(name):
            name_id, info = context.comp_env.lookup_name(name)
        else:
            set_comp_error(context,
                           CompileError("UnboundVariable",
                                           "Name '%s' is not found"%name,
                                           lisn["locinfo"]))
            return error_conclusion()

    else:
        name_id = lisn["meta_id"]
        info = context.comp_env.get_id_info(name_id)

    if info.is_var() or info.is_global_scope_var():
        return expr_conclusion(PyMetaID(name_id))
    elif info.is_runtime_extern():
        return expr_conclusion(PyAttrAccess(PyMetaID(context.runtime_obj_id), name))
    elif info.is_expander() or info.is_converter():
        err_obj = CompileError("IllegalName",
                                  repr(info) + " cannot be used as a variable",
                                  lisn["locinfo"])
        set_comp_error(context, err_obj)
        return error_conclusion()
    else:
        NOT_REACHABLE()


@node_translator.add.literal
def nt_literal(translator, lisn, premise, context):
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
def nt_binop(translator, lisn, premise, context):
# && || -> and or
    if lisn["op"] == "&&":
        pyop = "and"
    elif lisn["op"] == "||":
        pyop = "or"
    else:
        pyop = lisn["op"]

    def integrate_result(lhs_result, rhs_result):
        return PyBinop(pyop, lhs_result, rhs_result)

    lhs_conclusion = translator(lisn["lhs"], Premise(True), context)
    rhs_conclusion = translator(lisn["rhs"], Premise(True), context)


    return integrate_conclusion(context.comp_env, integrate_result, lhs_conclusion, rhs_conclusion)




@node_translator.add.unop
def nt_unop(translator, lisn, premise, context):
# ! -> not
    if lisn["op"] == "!":
        pyop = "not"
    else:
        pyop = lisn["op"]

    param_conclusion = translator(lisn["param"], Premise(True), context)
    return integrate_conclusion(context.comp_env,
                                lambda param_expr: PyUnop(pyop, param_expr),
                                param_conclusion)


@node_translator.add.assign
def nt_assign(translator, lisn, premise, context):
    op = lisn["op"]
    lvalue_type = lisn["lvalue_type"]
    param = lisn["param"]
    param_concl = translator(param, Premise(True), context)

    if lvalue_type == "name":
        lvalue_name = lisn["lvalue_name"]
        if python_native_literal(lvalue_name) or \
           python_control_name(lvalue_name):
            set_comp_error(context,
                           CompileError("IllegalAssignName",
                                           "cannot assign to %s"%lvalue_name,
                                           lisn["locinfo"]))
            return error_conclusion()

        local_id = ensure_local_var_name(context.comp_env, lvalue_name)

        return integrate_conclusion(context.comp_env,
                                    lambda param_expr: \
                                      (PyAssignmentToName(PyMetaID(local_id),
                                                          param_expr),
                                       PyLiteral(None)),
                                    param_concl)

    elif lvalue_type == "attr":
        lvalue_name = lisn["lvalue_name"]
        lvalue_scope = lisn["lvalue_scope"]
        scope_concl = translator(lvalue_scope,
                                 Premise(True),
                                 context)
        return integrate_conclusion(context.comp_env,
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
                                 Premise(True),
                                 context)
        index_concl = translator(lvalue_index,
                                 Premise(True),
                                 context)
        return integrate_conclusion(context.comp_env,
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
def nt_suite(translator, lisn, premise, context):
    return translate_suite(translator, lisn, premise, context)


@node_translator.add.xexpr
def nt_xexpr(translator, lisn, premise, context):
    # 1. check if multi name is def, import, import_from
    # 2. lookahead name part to check if name is expander/converter
    # 3. lastly treat label as just function

    if lisn["has_head_label"]:
        head_label = lisn["head_label"]
        if head_label == "def":
            return translate_def(translator, lisn, Premise(False), context)
        elif head_label == "import":
            return translate_import(translator, lisn, Premise(False), context)
        elif head_label == "import_from":
            return translate_import_from(translator, lisn, Premise(False), context)
        elif head_label == "pyimport":
            return translate_pyimport(translator, lisn, Premise(False), context)
        elif head_label == "pyimport_from":
            return translate_pyimport_from(translator, lisn, Premise(False), context)
        else:
            set_comp_error(context,
                           CompileError(
                               "UnknownHeadLabel",
                               "Unknown head label: %s"%head_label,
                               lisn["locinfo"]))
            return error_conclusion()
    else:
        head_expr = lisn["head_expr"]
        head_expr_name = force_name(head_expr)
        arg_info = lisn["arg_info"]
        success = True

        # lookahead
        if head_expr_name is not None and \
            context.comp_env.has_name(head_expr_name):
            _, info = context.comp_env.lookup_name(head_expr_name)
            if info.is_expander():
                return translator(info.expand(translator,
                                              lisn,
                                              premise,
                                              context),
                                  premise,
                                  context)
            elif info.is_converter():
                return info.convert(translator, lisn, premise, context)


        applicant_concl = translator(head_expr, Premise(True), context)
        parg_concls = [translator(parg, Premise(True), context) for parg in arg_info["pargs"]]
        karg_keywords = [k for k, _ in arg_info["kargs"]]
        karg_concls = [translator(karg, Premise(True), context) for _, karg in arg_info["kargs"]]
        star_concl = translator(arg_info["star"],
                                Premise(True),
                                context) if arg_info["has_star"] else None
        dstar_concl = translator(arg_info["dstar"],
                                 Premise(True),
                                 context) if arg_info["has_dstar"] else None

        amp_concl = translator(arg_info["amp"],
                               Premise(True),
                               context) if arg_info["has_amp"] else None
        damp_concl = translator(arg_info["damp"],
                                 Premise(True),
                                 context) if arg_info["has_damp"] else None


        # function-style xexpr

        varg_concls = []
        vattr_concls = []
        vattr_keywords = []
        if lisn["has_vert_suite"]:
            for obj in lisn["vert_suite"]["exprs"]:
                param = obj["param"]
                concl = translator(param,
                                   Premise(True),
                                   context)
                if obj["is_arrow"]:
                    label = obj["arrow_lstring"]
                    vattr_keywords.append(label)
                    vattr_concls.append(concl)
                else:
                    varg_concls.append(concl)

        if not success:
            return error_conclusion()

        def integrator(callee_expr, parg_exprs, karg_exprs, star_expr, dstar_expr, 
                       amp_expr, damp_expr, varg_exprs, vattr_exprs):
            tuple_maker_id, _ = context.comp_env.lookup_global_name("tuple")
            dict_maker_id, _ = context.comp_env.lookup_global_name("dict")

            real_kargs = zip(karg_keywords, karg_exprs)
            preseq_stmts = []

            if amp_expr:
                amp_tup = PyCall(PyMetaID(tuple_maker_id), [amp_expr], None)
            if varg_exprs:
                varg_tup = PyTupleExpr(varg_exprs)

            if vattr_exprs:
                vattr_dict = PyCall(PyMetaID(dict_maker_id), [], zip(vattr_keywords, vattr_exprs))

            if amp_expr is None and varg_exprs:
                real_kargs.append(("__varg__", varg_tup))
            elif amp_expr is not None and not varg_exprs:
                real_kargs.append(("__varg__", amp_tup))
            elif amp_expr is not None and varg_exprs:
                real_kargs.append(("__varg__",
                                   PyBinop("+",
                                           amp_tup,
                                           varg_tup)))

            if damp_expr is None and vattr_exprs:
                real_kargs.append(("__vattr__", vattr_dict))
            elif damp_expr is not None and not vattr_exprs:
                real_kargs.append(("__vattr__", damp_expr))
            elif damp_expr is not None and vattr_exprs:
                imd_id = context.comp_env.issue_local_immediate()
                preseq_stmts.append(PyAssignmentToName(PyMetaID(imd_id), damp_expr))
                preseq_stmts.append(PyExprStmt(PyCall(PyAttrAccess(PyMetaID(imd_id),
                                                                   "update"),
                                                      [vattr_dict],
                                                      None)))
                real_kargs.append(("__vattr__", PyMetaID(imd_id)))

            result_expr = PyCall(callee_expr,
                                 parg_exprs, 
                                 real_kargs,
                                 star_expr,
                                 dstar_expr)
            return (preseq_stmts, result_expr)
        return xintegrate_conclusion(context.comp_env,
                                     integrator,
                                     applicant_concl,
                                     parg_concls,
                                     karg_concls,
                                     star_concl,
                                     dstar_concl,
                                     amp_concl,
                                     damp_concl,
                                     varg_concls,
                                     vattr_concls)

@LISNPattern
def branch_pat(case, default):
    '''
    Returns -
        (success, failure_reason, cond_pairs, else_pair_or_None)
    '''

    @case
    def f(predicates, consequents, **kwds):
        '''
        NAME$head>
            __kleene_plus__(predicates): $expr
        --
            __kleene_plus__(consequents): $expr
        '''
        predicates = [d["expr"] for d in predicates]
        consequents = [d["expr"] for d in consequents]
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


def translate_branch(translator, lisn, premise, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = context.comp_env.issue_local_immediate()
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
                       CompileError("Branch",
                                       msg,
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
        pred_concl = translator(pred, Premise(True), context)
        conseq_concl = translator(conseq, premise.copy(), context)

        if pred_concl.error_occurred():
            success = False
            cur_success = False
        elif conseq_concl.error_occurred():
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
        else_concl = translator(else_lisn, premise.copy(), context)
        if else_concl.error_occurred():
            success = False
    else:
        else_concl = expr_conclusion(PyLiteral(None))

    if not success:
        return error_conclusion()
    iter_if_stmt.else_stmt_list = conclusion_to_stmts(else_concl)


    preseq_stmts.append(if_stmt)
    if use_return_value:
        return stmt_result_conclusion(preseq_stmts,
                                      PyMetaID(result_id))
    else:
        return stmt_conclusion(preseq_stmts)
    
@LISNPattern
def cond_case_pat(case, default):
    '''
    Returns -
        (success, failure_reason, cond_pairs, else_pair_or_None)
    '''

    @case
    def f(cases, else_opt):
        '''
        cond:
            __kleene_star__(cases):
                case($case_expr):
                    __kleene_plus__(case_body): $expr
            __optional__(else_opt):
                else:
                    __kleene_plus__(else_body): $expr
        '''
        cases = [(case_obj["case_expr"],
                  [d["expr"] for d in case_obj["case_body"]])
                 for case_obj in cases]

        if else_opt:
            else_body = [d["expr"] for d in else_opt["else_body"]]
        else:
            else_body = None

        return (True, "", cases, else_body)


    @default
    def el():
        return (False, "Bad Form", None, None)


def is_def_node(node):
    return check_multi_xexpr(node, "def")


def xtranslate_seq(translator, node_list, premise, context):
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
                                   CompileError("DefName",
                                                   "Name of def node is not appropriate",
                                                   node["locinfo"]))
                    success = False
                else:
                    function_id = ensure_function_name(context.comp_env, def_name)
                    child_premise.prebound_id = function_id # HACK?

                    @delay(node, child_premise, context)
                    def translation_promise(node, child_premise, context):
                        return translator(node, child_premise, context)
                    concls.append(translation_promise)
            else:
                concls.append(translator(node, child_premise, context))
        
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

def ltranslate_in_app_order(translator, node_list, context):
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
        concl = translator(node, Premise(True), context)
        if concl.error_occurred():
            success = False
            continue
        preseq_stmts.extend(concl.preseq_stmts)
        if concl.has_result() and concl.result_expr.may_have_side_effect():
            imd_id = context.comp_env.issue_local_immediate()
            preseq_stmts.append(PyAssignmentToName(PyMetaID(imd_id), concl.result_expr))
            result_exprs.append(PyMetaID(imd_id))
        else:
            result_exprs.append(concl.result_expr)
    return (success, preseq_stmts, result_exprs)

def translate_suite(translator, suite, premise, context):
    node_list = suite_to_node_list(suite)
    return xtranslate_seq(translator, node_list, premise, context)

def translate_def(translator, lisn, premise, context):
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
                               CompileError("FormalArgument",
                                               "Invalid star formal argument",
                                               lisn["head_expr"]["locinfo"]))
                argument_test_success = False
        
        if arg_info["has_dstar"]:
            dstar_str = force_name(arg_info["dstar"])
            if dstar_str is None:
                set_comp_error(context,
                               CompileError("FormalArgument",
                                               "Invalid double-star formal argument",
                                               lisn["head_expr"]["locinfo"]))
                argument_test_success = False


        if arg_info["has_damp"] or arg_info["has_amp"]:
            set_comp_error(context,
                           CompileError("NotSupported",
                                           "& or && argument is not supported",
                                           lisn["head_expr"]["locinfo"]))
            argument_test_success = False


        def_name = force_name(lisn["head_expr"])
        if def_name is None:
            set_comp_error(context,
                           CompileError("DefName",
                                           "Name of def node is not appropriate",
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
            concl = translator(suite, Premise(True), context)
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
    kw_concls = [translator(knode, Premise(True), context) 
                 for _, knode in kwd_pairs]
    kw_success, preseq_stmts, karg_default_exprs, _ = integrate_list(context.comp_env, kw_concls)
    if not kw_success:
        return error_conclusion()

    prebound_id = premise.prebound_id if hasattr(premise, "prebound_id") else None
    if prebound_id is None:
        function_id = ensure_function_name(context.comp_env, def_name) # function name
    else:
        assert context.comp_env.has_local_name(def_name, recursive=False)
        _id, info = context.comp_env.lookup_name(def_name)
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
                           CompileError("FormalArgument",
                               "Duplicated name of formal argument: %s"%name,
                               lisn["locinfo"]))
    if not no_duplication_found:
        return error_conclusion()

    ## NEW ENV
    context.comp_env.setup_local_frame("def") 

    # set names of arguments into new local environment
    parg_ids = []
    karg_id_pairs = []
    for name in parg_strs:
        parg_ids.append(PyMetaID(ensure_local_arg_name(context.comp_env, name)))

    for name, kexpr in zip(keywords, karg_default_exprs):
        k_id = ensure_local_arg_name(context.comp_env, name)
        karg_id_pairs.append((PyMetaID(k_id), kexpr))

    star_id = None
    dstar_id = None
    if star_str:
        star_id = PyMetaID(ensure_local_arg_name(context.comp_env, star_str))
    if dstar_str:
        dstar_id = PyMetaID(ensure_local_arg_name(context.comp_env, dstar_str))
    defun = make_defun(lisn,
                       PyMetaID(function_id),
                       parg_ids,
                       karg_id_pairs,
                       star_id,
                       dstar_id)

    ## DEL ENV
    context.comp_env.contract_local_frame() 

    if premise.use_return_value:
        return stmt_result_conclusion(preseq_stmts + [defun], PyLiteral(None))
    else:
        return stmt_conclusion(preseq_stmts + [defun])

def translate_let(translator, lisn, premise, context):
    if lisn["has_vert_suite"]:
        arg_info = lisn["arg_info"]
        # TODO: syntax checking ( keyword duplication, prohbiting star&dstar argument)
        kargs = arg_info["kargs"]
        keywords = [k for k, _ in kargs]
        concls = [translator(node, Premise(True), context)
                    for _, node in kargs]
        success, preseq_stmts, let_exprs, _ = integrate_list(context.comp_env, concls)

        context.comp_env.setup_local_frame("let")
        for name, expr in zip(keywords, let_exprs):
            let_id = ensure_local_var_name(context.comp_env, name)
            preseq_stmts += stmtify_expr(expr, True, let_id)

        suite_result = translator(lisn["vert_suite"], premise.copy(), context)
        if suite_result.error_occurred():
            success = False
            result_expr = None
        else:
            preseq_stmts += suite_result.preseq_stmts
            if suite_result.has_result():
                result_expr = suite_result.result_expr
            else:
                result_expr = PyLiteral(None)

        context.comp_env.contract_local_frame()
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


def translate_seq(translator, lisn, premise, context):
    if lisn["has_vert_suite"]:
        return translator(lisn["vert_suite"], premise.copy(), context)
    else:
        return expr_conclusion(PyLiteral(None))

@LISNPattern
def lambda_pat(case, default):
    '''
    (success, failure_reason, parg, karg, star, dstar, body)
    '''

    @case
    def lam(pargs, karg, star, dstar, body):
        '''
        lambda>
            kleene_star(parg): NAME$name
            keyword -> dict(karg)
            *__optional__(star): NAME$name
            **__optional__(dstar): NAME$name
        --
            __kleene_plus__(body): $expr
        '''
        parg = [x["name"] for x in parg]
        karg = karg["__rest__"]
        star = star["name"] if star else None
        dstar = dstar["name"] if dstar else None
        body = [x["expr"] for x in body]

        return (True, "", parg, karg, star, dstar, body)

    @default
    def el():
        return (False, "Bad form", None, None, None, None, [])


def translate_lambda(translator, lisn, premise, context):
    # pure expr -> use function
    # expr with pre-sequential stmts -> def
    # TODO
    pass


@LISNPattern
def for_pat(case, default):
    @case
    def fr(elem, iterable, opt, body, **kwds):
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
        index = opt["index_name"] if opt else None
        body = [x["expr"] for x in body]

        return (True, "", elem, index, iterable, body)

    @case
    def fr2(elems, opt, body, iterable, **kwds):
        '''
        NAME$for>
            _>
                __kleene_plus__(elems): $elem
            keyword -> seq:
                __optional__(opt):
                    index -> NAME$index_name
                in -> $iterable
        --
            __kleene_plus__(body): $expr
        '''
        raise Exception
        elem = [s["elem"] for s in elems]
        index = opt["index_name"] if opt else None
        body = [x["expr"] for x in body]

        return (True, "", elem, index, iterable, body)

    @default
    def el():
        return (False, "Bad form", None, None, None, None)




def _translate_iter_head(translator, lisn, premise, context,
                         body_kont, error_handler):
    success, failure_reason, elem, index, iterable, body = for_pat(lisn)

    if not success:
        error_handler(failure_reason)
        return error_conclusion()

    enumerate_id, _ = context.comp_env.lookup_global_name("enumerate")

    iterable_concl = translator(iterable, Premise(True), context)
    preseq_stmts = iterable_concl.preseq_stmts
    iterable_expr = iterable_concl.result_expr 

    elem_obj = None
    index_id = None
    if isinstance(elem, tuple):
        elem_ids = [PyMetaID(ensure_local_var_name(context.comp_env, x))
                    for x in elem]
        if index is not None:
            index_id = ensure_local_var_name(context.comp_env, index)
            elem_ids.insert(0, PyMetaID(index_id))
            iterable_expr = PyCall(PyMetaID(enumerate_id), [iterable_expr], None)
        elem_obj = PyTupleExpr(elem_ids)
    else:
        elem_id = ensure_local_var_name(context.comp_env, elem)
        if index is not None:
            index_id = ensure_local_var_name(context.comp_env, index)
            elem_obj = PyTupleExpr([PyMetaID(index_id), PyMetaID(elem_id)])
            iterable_expr = PyCall(PyMetaID(enumerate_id), [iterable_expr], None)
        else:
            elem_obj = PyMetaID(elem_id)

    return body_kont(preseq_stmts, elem_obj, iterable_expr, body)



def translate_for(translator, lisn, premise, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = context.comp_env.issue_local_immediate()
    else:
        result_id = None

    def kont(head_preseq_stmts, elem_obj, iterable_expr, body):
        body_concl = xtranslate_seq(translator,
                                    body,
                                    premise.copy(),
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
                       CompileError("for",
                                       reason,
                                       lisn["locinfo"]))

    return _translate_iter_head(translator, lisn, premise.copy(), context,
                                kont, error_handler)


def translate_each(translator, lisn, premise, context):
    use_return_value = premise.use_return_value
    if use_return_value:
        result_id = context.comp_env.issue_local_immediate()
    else:
        result_id = None

    def kont(head_preseq_stmts, elem_obj, iterable_expr, body):
        success, body_stmts, result_exprs = ltranslate_in_app_order(translator,
                                                                    body,
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
                       CompileError("each",
                                       reason,
                                       lisn["locinfo"]))

    return _translate_iter_head(translator, lisn, premise.copy(), context,
                                kont, error_handler)

@LISNPattern
def html_node_pat(case, default):
    @case
    def cond(html_node, attr, updater, body):
        '''
        NAME$html_node>
            keyword -> dict(attr)
            **__optional__(updater): $expr
        --
            __kleene_star__(body): $expr
        '''
        tag_name = html_node
        attr = attr["__rest__"]
        body = [x["expr"] for x in body]
        if updater:
            updater = updater["expr"]
        return (True, "", tag_name, attr, body, updater)

    @default
    def el():
        return (False, "Bad Form", None, None, None, None)


HTML_TAGPOOL_NAME = "__html__"
def translate_html_node(translator, lisn, premise, context):
    tagpool_id, _ = context.comp_env.lookup_global_name(HTML_TAGPOOL_NAME)
    success, failure_reason, tag_name, attr, body, updater = html_node_pat(lisn)

    if not success:
        set_comp_error(context,
                       CompileError("HtmlNode",
                                       failure_reason,
                                       lisn["locinfo"]))
        return error_conclusion()

    attr_pairs = attr.items()
    attr_keys = [k for k, _ in attr_pairs]
    success, stmts, param_exprs = \
        ltranslate_in_app_order(translator,
                                [v for _, v in attr_pairs] + 
                                body + 
                                ([updater] if updater else []),
                                context)
    attr_exprs = param_exprs[:len(attr_pairs)]
    body_exprs = param_exprs[len(attr_pairs):-1] if updater else param_exprs[len(attr_pairs):]
    updater_expr = param_exprs[-1] if updater else None

    dict_expr = PyDictExpr(dict(zip(map(PyLiteral, attr_keys), attr_exprs)))
    attr_expr = None
    if updater is None:
        attr_expr = dict_expr
    else:
        local_imd = context.comp_env.issue_local_immediate()
        stmts.extend(stmtify_expr(dict_expr, True, local_imd))
        stmts.extend(stmtify_expr(PyCall(PyAttrAccess(PyMetaID(local_imd), "update"),
                                         [updater_expr], []),
                                  False))
        attr_expr = PyMetaID(local_imd)
    caller_pargs = [attr_expr]
    caller_pargs.extend(body_exprs)

    mk = PyCall(PyAttrAccess(PyMetaID(tagpool_id),
                             tag_name),
                caller_pargs,
                None)
    return stmt_result_conclusion(stmts, mk)

def _make_import_accessor(context, names):
    return PyCall(PyMetaID(context.rt_store.importer_id), map(PyLiteral, names), None)
        

def translate_import(translator, lisn, premise, context):
    assert check_multi_xexpr(lisn, "import")

    head_node = lisn["head_expr"]
    names = force_dotted_name(head_node)
    if names is None:
        set_comp_error(context,
                       CompileError("IllegalImportName",
                                       "Not appropriate import name",
                                       head_node["locinfo"]))
        return error_conclusion()
    else:
        last_name = names[-1]
        accessor = _make_import_accessor(context, names)
        module_id = ensure_local_var_name(context.comp_env, last_name)
        assign = PyAssignmentToName(PyMetaID(module_id), accessor)
        return stmt_conclusion([assign])

def set_error(context, lisn, _type, name):
    set_comp_error(context, CompileError(_type, name, lisn["locinfo"]))

def translate_pyimport(translator, lisn, premise, context):
    head_node = lisn["head_expr"]
    names = force_dotted_name(head_node)
    last_name = names[-1]
    if names is None:
        set_error(context, head_node, "IllegalPyImportName", "Not appropriate pyimport name")
        return error_conclusion()

    if lisn["has_vert_suite"]:
        set_error(context, head_node, "IllegalPyImportForm", "No vertical body expected for pyimport")
        return error_conclusion()

    preseq_stmts = []
    importee_id = ensure_local_var_name(context.comp_env, last_name)

    return stmt_result_conclusion([PyImportStmt(names, PyMetaID(importee_id))], PyLiteral(None))

@LISNPattern
def pyimport_from_pat(case, default):
    @case
    def c1(_from, imported_names):
        '''
        pyimport_from $_from:
            __kleene_plus__(imported_names):
                __or__(opt):
                    NAME$src_name
                    NAME$src_name -> NAME$dest_name
        '''
        names = force_dotted_name(_from)

        if names is None:
            return (False, "Bad pyimport name", None, None)


        result = []
        for x in imported_names:
            import_obj = x["opt"]
            if "dest_name" in import_obj:
                result.append((import_obj["src_name"], import_obj["dest_name"]))
            else:
                result.append(import_obj["src_name"])
        return (True, "", names, imported_names)
    @default
    def d():
        return (False, "Bad form", None, None)


def translate_pyimport_from(translator, lisn, premise, context):
    success, failure_reason, module_names, dest_name_or_pairs = pyimport_from_pat(lisn)

    if not success:
        set_error(context, lisn, "PyImportFrom", failure_reason)
        return error_conclusion()
    new_dnp = []
    for dp in dest_name_or_pairs:
        if isinstance(dp, tuple):
            src, dest = dp
            dest_id = ensure_local_var_name(context.comp_env, dest)
            new_dnp.append((src, PyMetaID(dest_id)))
        else:
            dest_id = ensure_local_var_name(context.comp_env, dp)
            new_dnp.append((dp, PyMetaID(dest_id)))


    return stmt_result_conclusion([PyImportFromStmt(module_names, new_dnp)],
                                  PyLiteral(None))


def translate_import_from(translator, lisn, premise, context):
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
                               CompileError("IllegalImportName",
                                               "Invalid import name",
                                               suite["param"]["locinfo"]))
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
                       CompileError("IllegalImportName",
                                    "Not appropriate import name",
                                    head_node["locinfo"]))
        return error_conclusion()
    else:
        last_name = module_names[-1]

        accessor = _make_import_accessor(context, module_names)
        module_id = context.comp_env.issue_local_immediate()

        stmts = [PyAssignmentToName(PyMetaID(module_id), accessor)]
        for name_or_name_pair in import_names:
            if isinstance(name_or_name_pair, tuple):
                source_name, dest_name = name_or_name_pair

                dest_id = ensure_local_var_name(context.comp_env, dest_name)

                stmts.append(PyAssignmentToName(PyMetaID(dest_id), PyAttrAccess(PyMetaID(module_id), source_name)))
            else:
                dest_name = name_or_name_pair
                dest_id = ensure_local_var_name(context.comp_env, dest_name)

                stmts.append(PyAssignmentToName(PyMetaID(dest_id), PyAttrAccess(PyMetaID(module_id), dest_name)))

        return stmt_conclusion(stmts)

@LISNPattern
def raise_pat(case, default):
    @case
    def c1(expr):
        '''
        raise ($expr)
        '''
        return expr

    @case
    def c2(obj):
        '''
        raise()
        '''
        return None

    @default
    def d():
        return False


def translate_raise(translator, lisn, premise, context):
    throwee = raise_pat(lisn)

    if throwee == False:
        set_error(context, lisn, "Raise", "Bad Form")
        return error_conclusion()
    else:
        if throwee:
            concl = translator(throwee,
                               Premise(True),
                               context)
        else:
            concl = None
        return xintegrate_conclusion(context.comp_env,
                                     lambda expr: (PyRaise(expr), None),
                                     concl)


@LISNPattern
def try_pat(case, default):
    @case
    def with_fallthrough(_with, body, exc_part):
        '''
        try>
            keyword -> dict(_with)
        --
            __kleene_star__(body): $expr
            __kleene_star__(exc_part):
                NAME$name -> $action
        '''
        pass
# TODO


@LISNPattern
def class_pat(case, default):
    @case
    def c1(parent, decls):
        '''
        class x>
            __optional__(parent): NAME$name
        --
            __kleene_star__(decls): $defun
        '''
        pass
# TODO


    
@LISNPattern
def list_like_pat(case, default):
    @case
    def c1(decl_s, decl_star, decl_amp, decl_v, **kwds):
        '''
        NAME$__head__>
            __kleene_star__(decl_s): $expr
            *__optional__(decl_star): $expr
            &__optional__(decl_amp): $expr
        --
            __kleene_star__(decl_v): $expr
        '''
        decls = [x["expr"] for x in decl_s]
        if decl_star:
            decls.append(decl_star["expr"])
        if decl_amp:
            decls.append(decl_amp["expr"])
        decls.extend([x["expr"] for x in decl_v])
        return decls

    @default
    def df():
        return None


def make_list_like_translator(factory, debug_tag):
    def translate_list(translator, lisn, premise, context):
        decls = list_like_pat(lisn)
        if decls is None:
            set_error(context, lisn, debug_tag, "Bad form")
            return error_conclusion()
        concls = [translator(decl, Premise(True), context) for decl in decls]
        success, preseq_stmts, results, _ = integrate_list(context.comp_env, concls)

        if not success:
            return error_conclusion()
        return stmt_result_conclusion(preseq_stmts, factory(results))
    return translate_list



@LISNPattern
def dict_pat(case, default):
    @case
    def c1(vkw1, vkw2, **kwds):
        '''
        NAME$__double_dollar__>
            keyword -> seq:
                __kleene_star__(vkw1): 
                    NAME$key -> $value
        --
            __kleene_star__(vkw2): 
                NAME$key -> $value
        '''


        k = []
        for x in vkw1 + vkw2:
            k.append(expr_conclusion(PyLiteral(x["key"])))
            k.append(x["value"])
        return k

    @case
    def c2(kvpairs_s, kvpairs_v, **kwds):
        '''
        NAME$__double_dollar__>
            __kleene_star__(kvpairs_s):
                $key
                $value
        --
            __kleene_star__(kvpairs_v):
                $key
                $value
        '''
        kvpairs = []
        for x in kvpairs_s:
            kvpairs.append(x["key"])
            kvpairs.append(x["value"])

        for x in kvpairs_v:
            kvpairs.append(x["key"])
            kvpairs.append(x["value"])
        return kvpairs

    @default
    def df():
        return None


def translate_dict_expr(translator, lisn, premise, context):
    kvpairs = dict_pat(lisn)
    if kvpairs is None:
        set_error(context, lisn, "Dict", "Bad Form")
        return error_conclusion()

    kvconcls = []

    for decl in kvpairs:
        if isinstance(decl, Conclusion):
            kvconcls.append(decl)
        else:
            kvconcls.append(translator(decl, Premise(True), context))
    success, preseq_stmts, results, _ = integrate_list(context.comp_env, kvconcls)
    if not success:
        return error_conclusion()
    idx = 0
    _dict = {}
    while idx < len(results):
        _dict[results[idx]] = results[idx + 1]
        idx += 2
    return stmt_result_conclusion(preseq_stmts, PyDictExpr(_dict))



def add_python_native(comp_env):
    glob = {}
    exec("", glob)
    for name in glob["__builtins__"].keys():
        comp_env.add_global(name, GlobalScopeVar(name))
    comp_env.add_global(name, GlobalScopeVar("print"))
    

def setup_base_syntax(comp_env):
    add_python_native(comp_env)
    comp_env.add_global("raise",
                        Converter(translate_raise,
                                  "raise"))
    comp_env.add_global("if",
                        Converter(translate_branch,
                                  "if"))
    comp_env.add_global("$if",
                        Converter(translate_branch,
                                  "if"))
    comp_env.add_global("let",
                        Converter(translate_let,
                                  "let"))
    comp_env.add_global("$let",
                        Converter(translate_let,
                                  "let"))
    comp_env.add_global("seq",
                        Converter(translate_seq,
                                  "seq"))
    comp_env.add_global("$seq",
                        Converter(translate_seq,
                                  "seq"))
    comp_env.add_global("for",
                        Converter(translate_for,
                                  "for"))
    comp_env.add_global("$for",
                        Converter(translate_for,
                                  "for"))
    comp_env.add_global("each",
                        Converter(translate_each,
                                  "each"))
    comp_env.add_global("$each",
                        Converter(translate_each,
                                  "each"))
    comp_env.add_global("_",
                        Converter(make_list_like_translator(PyTupleExpr, "Tuple"),
                                  "_"))
    comp_env.add_global("$",
                        Converter(make_list_like_translator(PyListExpr, "List"),
                                  "$"))
    comp_env.add_global("$$",
                        Converter(translate_dict_expr,
                                  "$$"))

def setup_html_runtime(comp_env):
    for tag_name in HTML_TAGS:
        comp_env.add_global(tag_name,
                            Converter(translate_html_node,
                                      tag_name))
    comp_env.add_global("rawstring",
                        Converter(translate_html_node,
                                  "rawstring"))


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

def main_translate(suite, filename, config=None, extimport=None):
    config = config or Config()
    extimport = extimport or {}
    comp_env = CompEnv()

    # html tag pool -> "tempy.tag.TagPool"
    extimport[HTML_TAGPOOL_NAME] = ("name", ("tempy.tag", "TagPool"))

    setup_base_syntax(comp_env)
    setup_html_runtime(comp_env)

    result_stmts = []

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
    context = Context(comp_env,
                      config,
                      RuntimeStore(runtime_obj_id, importer_id, line_info_id),
                      filename)

    def_stmts = []
    success = True
    error_flooded = False

    for name_in_src, mod_obj in extimport.items():
        _type, name_obj = mod_obj
        _id = comp_env.add_global(name_in_src, Var(IDHint(name_in_src, "local", "local")))
        if _type == "module":
            def_stmts.append(PyImportStmt(name_obj, PyMetaID(_id)))
        elif _type == "name":
            mod_name, name_str = name_obj
            def_stmts.append(PyImportFromStmt(mod_name, [(name_str, PyMetaID(_id))]))
        else:
            raise ValueError("%s is not appropriate type tag for dynscope value"%_type)

    try:
        main_concl = node_translator(suite, Premise(False), context)
        if main_concl.error_occurred():
            success = False 
        else:
            def_stmts += main_concl.preseq_stmts
    except NoMoreErrorAcceptable:
        error_flooded = True

    if context.errors:
        success = False

    if not success:
        raise TempyCompileError(context.errors, error_flooded)

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
    def_mk_tmp = PyDefun("__tempy_main__",
                         [PyMetaID(runtime_obj_id),
                          PyMetaID(importer_id),
                          PyMetaID(line_info_id)],
                         None,
                         def_stmts)
    result_stmts.append(def_mk_tmp)
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
    local_dict = {}
    for stmt in result_stmts:
        stmt.convert_meta_id(naive_renaming_driver, local_dict)

    return result_stmts

def _raise_formated_syntax_error(err, filename):
    if isinstance(err.args, basestring) or len(err.args) <= 1:
        raise TempySyntaxError(err.args)
    else:
        locinfo = err.args[1]
        errmsg = "%s in \"%s\" [line %d-%d, col %d-%d]"%(
                err.args[0],
                filename or "",
                locinfo["sline"],
                locinfo["eline"],
                locinfo["scol"],
                locinfo["ecol"] - 1,
            )
        raise TempySyntaxError((errmsg,))




def translate_string(s, config=None, extimport=None, filename="<string>"):
    '''
    Translate tempy file to python code string

    Returns -
        compiled source(PyStmt list)
    extimport: 
        dict of 
            string(name in compiled source) to
                ("module", string)
                ("name", (string, string))
    '''
    try:
        suite = loads(s)
    except LISNSyntaxException as e:
        _raise_formated_syntax_error(e, filename)
    return main_translate(suite, filename, config, extimport)


def translate_file(filepath, config=None, extimport=None, filename=None):
    '''
    Translate tempy file to python code string

    Returns -
        compiled source(PyStmt list)
    extimport: 
        dict of 
            string(name in compiled source) to
                ("module", string)
                ("name", (string, string))
    '''
    filename = filename or filepath
    try:
        node = loads_file(filepath)
    except LISNSyntaxException as e:
        _raise_formated_syntax_error(e, filename)

    return main_translate(node, 
                          filename,
                          config, 
                          extimport)

def pystmts_to_string(stmts, indent=4):
    return "".join(stmt.to_string(indent, 0) for stmt in stmts)
