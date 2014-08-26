from lisn import loads, loads_file
from lisn.utils import LISNVisitor
from functools import wraps


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
            elif_pair: None | (expr, stmt list) list
            else_stmt_list: None | stmt list
        '''

        self.if_pair = if_pair
        self.elif_pairs = elif_pairs
        self.else_stmt_list = else_stmt_list

    def to_string(self, indent, acc_indent):
        if_expr, if_stmt_list = self.if_pair

        acc_str = "if %s:\n%s"%(if_expr.to_string(),
                                stmt_list_to_string(if_stmt_list,
                                                    indent,
                                                    acc_indent))
        if self.elif_pairs is not None:
            def elif_chunk(elif_expr, elif_expr_stmt_list):
                res = "elif %s:\n%s"%(elif_expr.to_string(),
                                      stmt_list_to_string(elif_expr_stmt_list,
                                                          indent,
                                                          acc_indent))
                return res
            acc_str += "".join([elif_chunk(l, r) for l, r in self.elif_pairs])
        
        if self.else_stmt_list is not None:
            acc_str += "else:\n%s"%stmt_list_to_string(self.else_stmt_list,
                                                       indent,
                                                       acc_indent)
        return acc_str

def dotify(name_or_name_list):
    if isinstance(name_or_name_list, str):
        dotted_name = name_or_name_list
    else:
        dotted_name = ".".join(name_or_name_list)
    return dotted_name


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
            return "%s = %s"%(self.name, self.expr.to_string())
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
           self.operator_pred() == self.opertor_pred():
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
        self.arg_exprs = arg_exprs if arg_exprs else []
        self.kw_exprs = kw_exprs if kw_exprs else []
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
**Top-level tags**
import relative_env_path
import "<path>"
import_from ..:
    name
    original_name -> new_name

def ...
    HTML:
        BODY:
**

'''

'''
def make_template(__genv__, __tags__, __line__):
    __line__("f.swn", 1, 2)
    mod = __genv__.import_from_path("")

    __line__("f.swn", 1, 2)
    def f1:
        pass
    def f2:
        pass

    return {
        : g_v
    }
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
 * source: "local" | "argument" | "function" | "closure" | "let"
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
 * use_expr_return_value
 * force_expr_lift
 * top_level
 * used_as_fun_label

Conclusion (Return value, frozen)
--
 * expressed_as: "expr" | "stmt" 
 * code_result_var: None | id (present if expressed as stmt and use_expr_return_value is True)
 * code_instance: Expr | Stmt list
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

def NOT_REACHABLE():
    raise Exception("Not reachable")

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
    def lookup_local_name(self, name, recursive=False):
        return self.local_env.

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
        assert self.name_env is not None
        ret = self.local_env
        self.local_env = self.local_env.prev

    
class LinkedDict:
    def __init__(self, env_data, initials={}, prev=None):
        self.env_data = env_data
        self.prev = prev
        self.namemap = {}

        for k, v in initials.items():
            self.add(k, v)

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
        if upsert:
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
            raise KeyError(_id)


class Premise:
    def __init__(self, use_return_value=False):
        self.use_return_value = use_return_value


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
                            error=True
                            comment=comment)
    return conclusion

def identity(x): return x


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

    return stmt_result_conclusion(rest.concl + last_concl.preseq_stmts,
                                  last_concl.result_expr)
    
def xtranslate_node_list(translator, node_list, comp_env, premise, config, context):
    if premise.use_result_value:
        if not node_list:
            return expr_conclusion(PyLiteral(None))
        else:
            rest_nodes = nodes[:-1]
            last_node = nodes[-1]

            rest_concls = [translator(node,
                           comp_env,
                           Premise(False),
                           config,
                           context)
                            for node in rest_nodes]
            last_concl = translator(last_node,
                                    comp_env,
                                    Premise(True),
                                    config,
                                    context)
            return seq_conclusion(rest_concls + [last_concl])
    else:
        concls = [translator(node,
                             comp_env,
                             Premise(False),
                             config,
                             context)
                     for node in node_list]
        return noreturn_conclusion(concls)


def integrate_conclusion(result_proc, *conclusions):
    '''
    result_proc: PyExpr x PyExpr x .. -> PyExpr
    '''
    if any([lambda x: x.error_occured() for x in conclusions]):
        return error_conclusion()
    pre_stmts = []
    for concl in conclusions:
        assert concl.has_result()
        pre_stmts += concl.preseq_stmts

    result_expr = result_proc(*[concl.result_expr for concl in  conclusions])

    return stmt_result_conclusion(pre_stmts, result_expr)



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


node_translator = LISNVisitor()

def set_comp_error(context, error_obj):
    context.add_error(error_obj)


def stmtify_expr(comp_env, expr, use_return_value=True):
    '''
    CompEnv x PyExpr x bool -> stmt list
    '''
    if use_return_value:
        imd_id = comp_env.issue_local_immediate()
        return ([PyAssignmentToName(PyMetaID(imd_id), expr)], imd_id)
    else:
        return ([PyExprStmt(expr)], None)

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
        set_comp_error(context, CompErrorObject("ScopeError", "scope should be specified"))
        return error_conclusion()

    scope_concl = translator(scope,
                             comp_env,
                             Premise(use_return_value=True),
                             config,
                             context)

    if trailer_type == "attr":
        attr = lisn["attr"]

        return integrate_conclusion(
            lambda scope_expr: PyAccessAttr(scope_expr, attr),
            scope_concl
        )
    elif trailer_type == "array":
        index_param = lisn["index_param"]

        item_concl = translator(index_param,
                                comp_env,
                                Premise(use_return_value=True),
                                config,
                                context)

        return integrate_conclusion(PyItemAccess,
                                    scope_concl,
                                    item_concl)

    elif trailer_type == "slice":
        left_slice = lisn["left_slice"]
        right_slice = lisn["right_slice"]
        
        left_slice_concl = translator(left_slice,
                                      comp_env,
                                      Premise(use_return_value=True),
                                      config,
                                      context) \
                            if left_slice else None
        right_slice_concl = translator(right_slice,
                                       comp_env,
                                       Premise(use_return_value=True),
                                       config,
                                       context) \
                             if right_slice else None


        if left_slice is None and right_slice is None:
            return integrate_conclusion(
                lambda scope_expr: PyArraySlice(scope_expr, None, None),
                scope_concl
            )

        elif left_slice is None:
            return integrate_conclusion(
                lambda scope_expr, right_expr: PyArraySlice(scope_expr, None, right_expr),
                scope_concl,
                right_slice_concl
            )
        elif right_slice is None:
            return integrate_conclusion(
                lambda scope_expr, left_expr: PyArraySlice(scope_expr, left_expr, None),
                scope_concl,
                left_slice_concl
            )
        else:
            return integrate_conclusion(
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
    else name == "False":
        return PyLiteral(False)
    else name == "None":
        return PyLiteral(None)
    else:
        return None

def python_control_literal(name):
    if name == "break":
        return PyBreak()
    elif name == "continue":
        return PyContinue()
    elif name == "pass":
        return PyPass()
    else:
        return None



@node_translator.add.name
def nt_name(translator, lisn, comp_env, premise, config, context):
    name = lisn["name"]
    
    naitve_literal = python_native_literal(name)
    if native_literal is not None:
        return expr_conclusion(native_literal)

    control_stmt = python_control_name(name)
    if control_stmt is not None:
        if premise.use_return_value:
            set_comp_error(context, CompErrorObject("NoReturnValue",
                                                    "Control statement don't have return value",
                                                    "<source>",
                                                    lisn["locinfo"]))
            return error_conclusion()
        else:
            return stmt_conclusion([control_stmt])


    name_id, info = comp_env.lookup_name(name)

    if info.is_var() or info.is_global_scope_var():
        return expr_conclusion(PyMetaID(name_id))
    elif info.is_runtime_extern():
        return expr_conclusion(PyAttrAccess(PyMetaID(context.runtime_obj_id), name))
    elif info.is_expander() or info.is_converter():
        raise CompException(CompErrorObject("IllegalName",
                                            "%s"%repr(info)
                                            "cannot be used as a variable",
                                            "<source>",
                                            lisn.locinfo))
    else:
        NOT_REACHABLE()


@node_translator.add.literal
def nt_name(translator, lisn, comp_env, premise, config, context):
    literal_type = lisn["literal_type"]
    if literal_type == "string":
        return expr_conclusion(PyLiteral(lisn["content"]))
    elif literal_type == "integer":
        return expr_conclusion(PyLiteral(int(lisn["content"])))
    elif literla_type == "float":
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


    return integrate_conclusion(integrate_result, lhs_conclusion, rhs_conclusion)




@node_translator.add.unop
def nt_unop(translator, lisn, comp_env, premise, config, context):
# ! -> not
    if lisn["op"] == "!":
        pyop = "not"
    else:
        pyop = lisn["op"]

    param_conclusion = translator(lisn["param"], comp_env, Premise(use_return_value=True), config, context)
    return integrate_conclusion(identity, lhs_conclusion, rhs_conclusion)

def ensure_local_name(comp_env, name, id_hint):
    if comp_env.has_local_name(name, recursive=False):
        local_id, info = lookup_name(name)
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


def ensure_closure_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "closure", "local"))


def ensure_function_name(comp_env, name):
    return ensure_local_name(comp_env, name, IDHint(name, "function", "local"))


@node_translator.add.assign
def nt_assign(translator, lisn, comp_env, premise, config, context):
    op = lisn["op"]
    lvalue_type = lisn["lvalue_type"]
    param = lisn["param"]
    param_concl = translator(param, comp_env, Premise(True), config, context)
    
    if lvalue_type == "name":
        lvalue_name = lisn["lvalue_name"]
        local_id = ensure_local_var_name(comp_env, lvalue_name)
        return integrate_conclusion(lambda param_expr: \
                                      PyAssignemntToName(PyMetaID(local_id),
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
        return integrate_conclusion(lambda param_expr, scope_expr: \
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
        return integrate_conclusion(lambda param_expr, scope_expr, index_expr: \
                                      PyAssignmentToItem(scope_expr,
                                                         index_expr,
                                                         param_expr),
                                    param_concl,
                                    scope_concl,
                                    index_concl)
    else:
        NOT_REACHABLE()


def suite_to_node_list(suite):
    return [obj["param"] for node in suite["exprs"]]


@node_translator.add.xexpr
def nt_xexpr(translator, lisn, comp_env, premise, config, context):
    # 1. check if multi name is def, import, import_from
    # 2. check whther name is not or special condition directives(if, elif, else)
    #    these names are already processed in the lookahead fashon  by suite translator
    # 3. lookahead name part to check if name is expander/converter
    # 4. lastly treat label as just function
    if lisn["multi_flag"]:
        head_name = lisn["head_name"]
        if head_name == "def":
            return translate_import(translator, lisn, Premise(False), config, context)
        elif head_name == "import":
            return translate_import(translator, lisn, Premise(False), config, context)
        elif head_name == "import_from":
            return translate_import_from(translator, lisn, Premise(False), config, context)
        else:
            return translate

    else:




def translate_suite(translate, suite, comp_env, premise, config, context, top_level=True):
    # if:
    # {elif:}*
    # {else:}?

    state = "fun"



def translate_def_node(translator, lisn, comp_env, premise, config, context, prebound_id=None):
    assert lisn.get("head_name") == "def"

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

    def process_suite(def_xexpr, def_name, sarg_strs, default_pairs, star_str, dstar_str):
        '''
        Return - 
            PyDefun
        '''
        if def_xexpr["vert_flag"]:
            def_stmts = []
            nodes = suite_to_node_list(def_xexpr["vert_suite"])
            concl = xtranslate_node_list(translator,
                                         nodes,
                                         comp_env,
                                         Premise(True),
                                         config,
                                         context)
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
    default_value_test_success, preseq_stmts, default_pairs = process_kwd_pairs()

    if prebound_id is None:
        function_id = ensure_closure_name(comp_env, def_name) # function name
    else:
        assert comp_env.has_local_name(def_name, recursive=False)
        _id, info = comp_env.lookup_name(def_name)
        assert _id == prebound_id
        assert info.is_var()
        function_id = prebound_id # name is already bound to 

    ## NEW ENV
    comp_env.setup_local_frame("def") 

    # set names of arguments into new local environment
    for name in sarg_strs:
        ensure_local_var_name(name)
    for name, _ in kwd_pairs:
        ensure_local_var_name(name)
    if star_str:
        ensure_local_var_name(star_str)
    if dstar_str:
        ensure_local_var_name(dstar_str)
    # make defun
    defun = process_suite(lisn, def_name, sarg_strs, default_pairs, star_str, dstar_str)

    ## DEL ENV
    comp_env.contract_local_frame() 

    if premise.use_return_value:
        return stmt_result_conclusion(preseq_stmts + [defun], PyLiteral(None))
    else:
        return stmt_conclusion(preseq_stmts + [defun])


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


def translate_import(translator, lisn, comp_env, premise, config, context):
    assert lisn.get("head_name") == "import"

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
    assert lisn.get("head_name") == "import_from"

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


def main_translate(suite, config=None):
    config = config or Config()
    initial_premise = Premise(use_return_value=False)
    comp_env = CompEnv()
    add_python_native(comp_env)

    comp_env.setup_local_frame("def")

    runtime_obj_id = comp_env.add_local("__runtime__",
                                        Var(IDHint("__runtime__",
                                                   "argument",
                                                   "local",
                                                   "local"))

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
        for obj in node['exprs']:
            node = obj["param"]
            node_conclusion = node_translator(node,
                                              comp_env,
                                              Premise(use_return_value=False),
                                              config)
            if not node_conclusion.error_occured():
                if node_conclusion.expressed_as_expr():
                    expr = node_conclusion.code_instance
                    def_stmts.append(PyExprStmt(expr))

                else: # expressed as stmt list
                    stmt_list = node_conclusion.code_instance
                    def_stmts += stmt_list

    except NoMoreErrorAcceptableException:
        error_flooded = True

    if context.errors:
        success = False

    if not success:
        print context.errors
        if error_flooded:
            print "Error Flooded"
        return None
    else:
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
        def_mk_tmp = PyDefun("make_template",
                           args=[context.runtime_obj_id, context.line_dbg_id],
                           kwd_args=None,
                           def_stmts)
        return def_mk_tmp.to_string(config.indent, 0)


def translate_string(s):
    suite = loads(s)
    return main_translate(suite)


def translate_file(filepath):
    node = loads_flie(filepath)
    return main_translate(node)


TEST_SRC1 = '''
coef = 1
def factorial(n):
    if (n < 0):
        -1
    elif (n == 0):
        1
    elif (n == 0):
        1
    else:
        coef * n * factorial(n - 1)
'''

TEST_SRC2 = '''
'''
