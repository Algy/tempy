/*
 * This file contains c extension module for parse file/string to build LISN as dictionaray form in Python.
 * LISN(LIDL Syntax Notation) is general form to notate several 'functional' syntax.
 *
 * Author: Alchan Kim
 */

#include <Python.h>
#include <stdio.h>
#include <stdlib.h>

#include "clisn/ast.h"
#include "clisn/parser.h"

/*
 * Exceptions:
 *     LISNSyntaxException
 *         LISNLexerException
 *         LISNParserException
 *
 */

static PyObject* LISNSyntaxException, *LISNLexerException, *LISNParserException;
static PyObject* dictify_ast(ASTHD *ast);
static PyObject* dictify_arguments(ASTDS_Arguments* arguments);

static PyObject* dictify_locinfo(ASTHD *ast) {
    if(ast) {
        return Py_BuildValue("{s:i,s:i,s:i,s:i}",
            "sline", ast->loc.sline,
            "eline", ast->loc.eline,
            "scol", ast->loc.scol,
            "ecol", ast->loc.ecol);
    } else {
        // Top-level empty suite
        return Py_BuildValue("{s:i,s:i,s:i,s:i}",
            "sline", 1,
            "eline", 1,
            "scol", 1,
            "ecol", 1);
    }
}

/*
 * type: "trailer" 
 * scope: lisn | None
 * trailer_type: "attr" | "array" | "slice"
 * 
 * -- when trailer_type is "attr" --
 * attr: string
 * -- when trialer_type is "array"
 * index_param: lisn
 * -- when trailer_type is "slice" --
 *  slice_left: lisn | None 
 *  slice_right: lisn | None
 *  
 */
static PyObject* dictify_trailer(ASTHD *ast) {
    AST_Trailer *trailer = (AST_Trailer *)ast;
    PyObject *type_name, *scope, *trailer_type, *ret;

    type_name = PyString_FromString("trailer");
    if(!trailer->scope) {
        Py_INCREF(Py_None);
        scope = Py_None;
    } else {
        scope = dictify_ast(trailer->scope);
    }

    ret = PyDict_New();
    if(!ret) {
        Py_XDECREF(type_name);
        Py_XDECREF(scope);
        return NULL;
    }

    /*
     * PyDict_SetItemString doen't take over references.
     * It share them with caller. (That is, it INCREfs them inside)
     * So, Here we can dispose our values.
     */
    PyDict_SetItemString(ret, "type", type_name);
    PyDict_SetItemString(ret, "scope", scope);
    Py_XDECREF(type_name);
    Py_XDECREF(scope);

    switch(trailer->trailer_type) {
        case trailer_attr:
            {
                PyObject *attr;
                attr = PyString_FromString(trailer->as.attr.str);
                trailer_type = PyString_FromString("attr");
                PyDict_SetItemString(ret, "attr", attr);
                Py_XDECREF(attr);
            }
            break;
        case trailer_array:
            {
                PyObject *index_param;
                index_param = dictify_ast(trailer->as.index_param);
                trailer_type = PyString_FromString("array");
                PyDict_SetItemString(ret, "index_param", index_param);
                Py_XDECREF(index_param);
            }
            break;

        case trailer_lrslice:
        case trailer_lslice:
        case trailer_rslice:
        case trailer_noslice:
            {
                PyObject *left, *right;
                trailer_type = PyString_FromString("slice");
                if(trailer->as.slice_indices.left) {
                    left = dictify_ast(trailer->as.slice_indices.left);
                } else {
                    Py_INCREF(Py_None);
                    left = Py_None;
                }
                if(trailer->as.slice_indices.right) {
                    right = dictify_ast(trailer->as.slice_indices.right);
                } else {
                    Py_INCREF(Py_None);
                    right = Py_None;
                }
                PyDict_SetItemString(ret, "slice_left", left);
                PyDict_SetItemString(ret, "slice_right", right);
                Py_XDECREF(left);
                Py_XDECREF(right);
            }
            break;


    }
    PyDict_SetItemString(ret, "trailer_type", trailer_type);
    Py_XDECREF(trailer_type);
    return ret;
}

/*
 * type: "name" 
 * name: string
 */

static PyObject* dictify_name(ASTHD *ast) {
    AST_Name *name = (AST_Name *)ast;
    PyObject *ret;

    ret = Py_BuildValue("{s:s,s:s}", "type", "name", "name", name->dstr.str);

    return ret;
}

/*
 * type: "literal"
 * literal_type: "string" | "integer" | "float"
 * content:
 */ 
static PyObject* dictify_literal(ASTHD *ast) {
    AST_Literal *literal = (AST_Literal *)ast;
    char *literal_type_name;
    PyObject *ret;

    switch(literal->literal_type) {
        case literal_string:
            literal_type_name = "string";
            break;
        case literal_integer:
            literal_type_name = "integer";
            break;
        case  literal_float:
            literal_type_name = "float";
            break;
        default:
            literal_type_name = "unknown";
            break;
    }
    ret = Py_BuildValue("{s:s,s:s,s:s}",
            "type", "literal", 
            "literal_type", literal_type_name,
            "content", literal->dstr.str);


    return ret;
}

/*
 * type: "binop"
 * op: string # Operator string
 * lhs: lisn
 * rhs: lisn
 */ 
static PyObject* dictify_binop(ASTHD *ast) {
    AST_BinOp *binop = (AST_BinOp *)ast;

    return Py_BuildValue("{s:s,s:s,s:N,s:N}", 
            "type", "binop",
            "op", binop->binop_str.str,
            "lhs", dictify_ast(binop->lhs),
            "rhs", dictify_ast(binop->rhs));
} 
/*
 * type: "unop"
 * op: string # Operator string
 * param: lisn
 */ 
static PyObject* dictify_unop(ASTHD *ast) {
    AST_UnOp *unop = (AST_UnOp *)ast;
    return Py_BuildValue("{s:s,s:s,s:N}",
            "type", "unop",
            "op", unop->unop_str.str,
            "param", dictify_ast(unop->param));
}

/*
 * type: "assign"
 * op: "=" | ":="
 * lvalue_type: "name" | "attr" | "array"
 * param: lisn
 * -- when lvalue_type is "name" --
 * lvalue_name: string
 * -- when lvalue_type is "attr" --
 * lvalue_name: string
 * lvalue_scope: lisn
 * -- when lvalue_type is "array" --
 * lvalue_index: lisn
 * lvalue_scope: lisn
 *
 */ 
static PyObject* dictify_assign(ASTHD *ast) {
    AST_Assign *assign = (AST_Assign *)ast;
    PyObject *ret, *lvalue_type;
    char *op;
    
    switch(assign->assign_type) {
        case assign_normal:
            op = "=";
            break;
        case assign_def:
            op = ":=";
            break;
        default:
            op = "";
            break;
    }
    ret = Py_BuildValue("{s:s,s:s,s:N}",
            "type", "assign",
            "op", op,
            "param", dictify_ast(assign->param));
    switch(assign->lvalue_type) {
        case lvalue_name:
            {
            PyObject *lvalue_name;
            lvalue_name = PyString_FromString(assign->lvalue_as.name.str);
            
            PyDict_SetItemString(ret, "lvalue_name", lvalue_name);
            Py_XDECREF(lvalue_name);

            lvalue_type = PyString_FromString("name");
            }
            break;
        case lvalue_attr:
            {
            PyObject *lvalue_name, *lvalue_scope;
            lvalue_name = PyString_FromString(assign->lvalue_as.attr.name.str);
            lvalue_scope = dictify_ast(assign->lvalue_as.attr.scope);
            PyDict_SetItemString(ret, "lvalue_name", lvalue_name);
            PyDict_SetItemString(ret, "lvalue_scope", lvalue_scope);
            Py_XDECREF(lvalue_name);
            Py_XDECREF(lvalue_scope);

            lvalue_type = PyString_FromString("attr");
            }
            break;
        case lvalue_array:
            {
            PyObject *lvalue_index, *lvalue_scope;
            lvalue_index = dictify_ast(assign->lvalue_as.array.index);
            lvalue_scope = dictify_ast(assign->lvalue_as.array.scope);

            PyDict_SetItemString(ret, "lvalue_index", lvalue_index);
            PyDict_SetItemString(ret, "lvalue_scope", lvalue_scope);

            Py_XDECREF(lvalue_index);
            Py_XDECREF(lvalue_scope);
            lvalue_type = PyString_FromString("array");
            }
            break;
        default:

            lvalue_type = PyString_FromString("unknown");
            break;
    }
    PyDict_SetItemString(ret, "lvalue_type", lvalue_type);
    Py_XDECREF(lvalue_type);

    return ret;
}

/*
 * type: "suite"
 * exprs: array of
 *   {
 *     is_arrow: bool
 *     param: lisn
 *     -- if is_arrow is true --
 *     arrow_lstring: 
 *   }
 */
static PyObject* dictify_suite(ASTHD *ast) {
    AST_Suite *p;
    AST_Suite *suite = (AST_Suite *)ast;
    Py_ssize_t suite_len, i;
    PyObject* exprs;

    suite_len = 0;
    for(p = suite; p; p = p->next) {
        suite_len++;
    }

    exprs = PyList_New(suite_len);

    i = 0;
    for(p = suite; p; p = p->next) {
        PyObject* item;
        if(p->is_arrow) {
            item = Py_BuildValue("{s:O,s:N,s:s}",
                    "is_arrow", Py_True,
                    "param", dictify_ast(p->param),
                    "arrow_lstring", p->arrow_lstring.str);
        } else {
            item = Py_BuildValue("{s:O,s:N}",
                    "is_arrow", Py_False,
                    "param", dictify_ast(p->param));
        }
        PyList_SET_ITEM(exprs, i, item);
        i++;
    }
    return Py_BuildValue("{s:s,s:N}", "type", "suite", "exprs", exprs);
}

/*
 * 
 * sargs: lisn list
 * kargs: (string, lisn) list
 * has_star: bool
 * has_dstar: bool
 * has_amp: bool
 * has_damp: bool
 *
 * -- 
 * star: lisn 
 * dstar: lisn 
 * amp: lisn
 * damp: lisn 
 *
 *
 * 
 *
 */
static PyObject* dictify_arguments(ASTDS_Arguments* arguments) {
    PyObject *sarg_lst, *karg_lst, *ret;
    ASTDS_SingleArg *sp;
    ASTDS_KwdArg *kp;
    Py_ssize_t sarg_len, karg_len, i;

    sarg_len = 0;
    for(sp = arguments->sargs; sp; sp = sp->next)
        sarg_len++;
    sarg_lst = PyList_New(sarg_len);

    karg_len = 0;
    for(kp = arguments->kargs; kp; kp = kp->next)
        karg_len++;
    karg_lst = PyList_New(karg_len);


    i = 0;
    for(sp = arguments->sargs; sp; sp = sp->next) {
        PyList_SET_ITEM(sarg_lst, i, dictify_ast(sp->param));
        i++;
    }

    i = 0;
    for(kp = arguments->kargs; kp; kp = kp->next) {
        PyList_SET_ITEM(
                karg_lst, i,
                Py_BuildValue("sN", kp->name.str, dictify_ast(kp->param)));
        i++;
    }

    ret = Py_BuildValue("{s:N,s:N}", "sargs", sarg_lst, "kargs", karg_lst);

#define STR_star "star"
#define STR_dstar "dstar"
#define STR_amp "amp"
#define STR_damp "damp"
#define OPTIONAL_ARG(NAME) { \
    if(arguments->has_##NAME) { \
        PyObject *_param; \
        _param = dictify_ast(arguments->NAME); \
        PyDict_SetItemString(ret, STR_##NAME, _param); \
        Py_XDECREF(_param); \
        PyDict_SetItemString(ret, "has_"STR_##NAME, Py_True); \
    } else { \
        PyDict_SetItemString(ret, "has_"STR_##NAME, Py_False); \
    }  \
} 
    OPTIONAL_ARG(star);
    OPTIONAL_ARG(dstar);
    OPTIONAL_ARG(amp);
    OPTIONAL_ARG(damp);
#undef STR_star
#undef STR_dstr
#undef STR_amp
#undef STR_damp
#undef OPTIONAL_ARG
    return ret;
}

/* 
 * type: "xexpr"
 * multi_flag: bool
 * vert_flag: bool
 * args: arguments
 * head_expr: lisn
 *
 * -- if multi_flag is true --
 * head_name: string
 * -- if vert_flag is true --
 * vert_suite: lisn(suite, specificaly)
 *
 *
 *
 *
 */
static PyObject* dictify_xexpr(ASTHD *ast) {
    AST_XExpr *xexpr = (AST_XExpr *)ast;
    PyObject *ret;


    ret = Py_BuildValue("{s:s,s:N,s:N,s:N,s:N}",
            "type", "xexpr",
            "multi_flag", PyBool_FromLong(xexpr->multi_flag),
            "vert_flag", PyBool_FromLong(xexpr->vert_flag),
            "args", dictify_arguments(&xexpr->args),
            "head_expr", dictify_ast(xexpr->head_expr));

    if(xexpr->multi_flag) {
        PyObject *hn;
        hn = PyString_FromString(xexpr->head_dstr.str);
        PyDict_SetItemString(ret, "head_name", hn);
        Py_XDECREF(hn);
    }
    if(xexpr->vert_flag) {
        PyObject *vs;
        vs = dictify_suite(xexpr->vert_suite);
        PyDict_SetItemString(ret, "vert_suite", vs);
        Py_XDECREF(vs);
    }
    return ret;
}



static PyObject* dictify_ast(ASTHD *ast) {
    char err_msg[128];
    PyObject *ret;
    if(!ast) {
        PyErr_SetString(LISNSyntaxException, "Internal Error. dictify_ast(NULL).");
        return NULL;
    }
    switch(ast->node_type) {
        case asttype_trailer:
            ret = dictify_trailer(ast);
            break;
        case asttype_name:
            ret = dictify_name(ast);
            break;
        case asttype_literal:
            ret = dictify_literal(ast);
            break;
        case asttype_binop:
            ret = dictify_binop(ast);
            break;
        case asttype_unop:
            ret = dictify_unop(ast);
            break;
        case asttype_assign:
            ret = dictify_assign(ast);
            break;
        case asttype_suite:
            ret = dictify_suite(ast);
            break;
        case asttype_xexpr:
            ret = dictify_xexpr(ast);
            break;
        default:
            snprintf(err_msg, 128, "Internal Error. Unknown type %d.", ast->node_type);
            PyErr_SetString(LISNSyntaxException, err_msg);
            return NULL;
    }
    if(ret) {
        PyObject *locinfo = dictify_locinfo(ast);
        PyDict_SetItemString(ret, "locinfo", locinfo);
        Py_XDECREF(locinfo);
    }
    return ret;
}

static PyObject* safe_dictify_ast(ASTHD *ast) {
    /*
     * There are the case in which parse_* function returns NULL even though parsing is successfully done.
     * That case implies "empty suite" because suite node is acutually bare linked list which use zero pointer(NULL) as end of linked list. This function cover that situation.
     */
    PyObject *ret;
    if(!ast) {
        PyObject *locinfo;
        ret = dictify_suite(NULL);
        locinfo = dictify_locinfo(NULL);
        PyDict_SetItemString(ret, "locinfo", locinfo);
        Py_XDECREF(locinfo);
        return ret;
    } else {
        return dictify_ast(ast);
    }
}

static PyObject* str2lisn(PyObject *self, PyObject* args) {
    const char* source; // barrowed
    int source_size;
    LexParseError err;
    ASTHD *ast;
    PyObject *ret;

    if(!PyArg_ParseTuple(args, "s#", &source, &source_size)) {
        return NULL;
    }
    ast = parse_bytes(source, source_size, &err);

    if(err.error_occured) {
        PyObject *err_tuple;

        err_tuple = Py_BuildValue("sN",
            err.err_msg,
            Py_BuildValue("{s:i,s:i,s:i,s:i}",
                "sline", err.sline,
                "eline", err.eline,
                "scol", err.scol,
                "ecol", err.ecol));
        if(err.is_lexerr) {
            PyErr_SetObject(LISNLexerException, err_tuple);
        } else {
            PyErr_SetObject(LISNParserException, err_tuple);
        }
        Py_DECREF(err_tuple);
        return NULL;
    } 
    ret = safe_dictify_ast(ast);
    ast_free(ast);
    return ret;
}

static PyObject* file2lisn(PyObject *self, PyObject* args) {
    const char* file_name; // borrowed
    LexParseError err;
    ASTHD *ast;
    PyObject *ret;

    if(!PyArg_ParseTuple(args, "s", &file_name)) {
        return NULL;
    }
    FILE *fp;

    fp = fopen(file_name, "r");
    if(!fp) {
        return PyErr_SetFromErrno(PyExc_IOError);
    }
    ast = parse_file(fp, &err);
    fclose(fp);

    if(err.error_occured) {
        if(err.is_lexerr) {
            PyErr_SetString(LISNLexerException, err.err_msg);
        } else {
            PyErr_SetString(LISNParserException, err.err_msg);
        }
        return NULL;
    } 

    ret = safe_dictify_ast(ast);
    ast_free(ast);
    return ret;
}

static PyMethodDef lisn_methods [] = {
    {"loads", str2lisn, METH_VARARGS, "loads string to build LISN AST"},
    {"loads_file", file2lisn, METH_VARARGS, "loads file to build LISN AST"},
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initclisn(void) {
    PyObject* mod;
    if(!(mod = Py_InitModule("clisn", lisn_methods)))
        return;

    LISNSyntaxException = PyErr_NewException("clisn.LISNSyntaxException", NULL, NULL);

    Py_INCREF(LISNSyntaxException);
    PyModule_AddObject(mod, "LISNSyntaxException", LISNSyntaxException);

    LISNLexerException = PyErr_NewException("clisn.LISNLexerException", LISNSyntaxException, NULL);
    Py_INCREF(LISNLexerException);
    PyModule_AddObject(mod, "LISNLexerException", LISNLexerException);


    LISNParserException = PyErr_NewException("clisn.LISNParserException", LISNParserException, NULL);
    Py_INCREF(LISNParserException);
    PyModule_AddObject(mod, "LISNParserException", LISNParserException);
}
