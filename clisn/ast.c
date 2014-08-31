#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ast.h"

#ifndef NULL
# define NULL ((void *)0)
#endif

/* TODO: change me */
#define AST_NODE_TAG 10 

/* 
 * ASTDS_String stuffs
 */
ASTDS_String make_dsstring(const char *str, int len) {
    ASTDS_String s;

    s.str = (char *)malloc(len + 1);
    s.len = len;
    s.str[len] = 0;
    strncpy(s.str, str, len);

    return s;
}

ASTDS_String empty_dsstring() {
    ASTDS_String ret;
    ret.len = 0;
    ret.str = NULL;
    return ret;
}

int dsstring_empty(ASTDS_String *dstr) {
    return dstr->str == NULL;
}

void free_dsstring(ASTDS_String *dstr) {
    if(!dsstring_empty(dstr)) {
        free(dstr->str);
    }
}

ASTDS_String dsstring_from_str(const char *str) {
    return make_dsstring(str, strlen(str));
}

void dsstring_append(ASTDS_String *dstr, const char *src) {
    unsigned int src_len, len;
    if(dsstring_empty(dstr)) {
        *dstr = dsstring_from_str(src);
    } else {
        src_len = strlen(src);
        len = dstr->len;
        dstr->str = (char *)realloc(dstr->str, src_len + len + 1);
        dstr->str[src_len + len] = 0;
        strcpy(dstr->str + len, src);
    }
}

/*
 * AST Stuffs
 */
static ASTHD* ast_make(short node_type, unsigned int size) {
    ASTHD *ret = (ASTHD *)malloc(size);
    ret->tag = AST_NODE_TAG;
    ret->node_type = node_type;
    return ret;
}

static AST_Suite* reverse_suite_iter(AST_Suite* prev_suite, AST_Suite* suite) {
    if(suite) {
        AST_Suite* next;
        next = suite->next;
        suite->next = prev_suite;
        return reverse_suite_iter(suite, next);
    } else {
        return prev_suite;
    }
}

AST_Suite* reverse_suite(AST_Suite *suite) {
    return reverse_suite_iter(NULL, suite);
}



ASTHD* ast_access_attr(ASTHD *scope, const char *str) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_attr;
    trailer->as.attr = dsstring_from_str(str);
    return &trailer->hd;
}

ASTHD* ast_access_array(ASTHD *scope, ASTHD *index_param) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_array;
    trailer->as.index_param = index_param;

    return &trailer->hd;
}

ASTHD* ast_slice_lr(ASTHD *scope, ASTHD *left, ASTHD *right) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_lrslice;
    trailer->as.slice_indices.left = left;
    trailer->as.slice_indices.right = right;

    return &trailer->hd;
}

ASTHD* ast_slice_l(ASTHD *scope, ASTHD *left) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_lslice;
    trailer->as.slice_indices.left = left;
    trailer->as.slice_indices.right = NULL;

    return &trailer->hd;
}
ASTHD* ast_slice_r(ASTHD *scope, ASTHD *right) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_rslice;
    trailer->as.slice_indices.left = NULL;
    trailer->as.slice_indices.right = right;

    return &trailer->hd;
}
   
ASTHD* ast_slice_nolr(ASTHD *scope) {
    AST_Trailer *trailer = (AST_Trailer *)ast_make(asttype_trailer, sizeof(AST_Trailer));
    trailer->scope = scope;
    trailer->trailer_type = trailer_noslice;
    trailer->as.slice_indices.left = NULL;
    trailer->as.slice_indices.right = NULL;

    return &trailer->hd;

}

ASTHD* ast_name(const char *str) {
    AST_Name *name = (AST_Name *)ast_make(asttype_name, sizeof(AST_Name));
    name->dstr = dsstring_from_str(str);
    return &name->hd;
}

ASTHD* ast_string_literal(const char *str) {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_string;
    literal->dstr = dsstring_from_str(str);
    return &literal->hd;
}

ASTHD* ast_sliced_string_literal(const char *str, int start, int slice_len) {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    int len = strlen(str);
    if(start + slice_len > len) {
        literal->dstr = dsstring_from_str("");
    } else {
        literal->dstr = make_dsstring(str + start, slice_len);
    }

    literal->literal_type = literal_string;
    return &literal->hd;
}

void ast_string_literal_append(ASTHD *ast, char *str) {
    AST_Literal *literal = (AST_Literal *)ast;
    dsstring_append(&literal->dstr, str);
}

ASTHD* ast_integer_literal(const char *str) {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_integer;
    literal->dstr = dsstring_from_str(str);
    return &literal->hd;
}
ASTHD* ast_float_literal(const char *str) {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_float;
    literal->dstr = dsstring_from_str(str);
    return &literal->hd;
}
ASTHD* ast_null_literal() {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_null;
    literal->dstr = empty_dsstring();

    return &literal->hd;
}

ASTHD* ast_true_literal() {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_true;
    literal->dstr = empty_dsstring();

    return &literal->hd;
}

ASTHD* ast_false_literal() {
    AST_Literal *literal = (AST_Literal *)ast_make(asttype_literal, sizeof(AST_Literal));

    literal->literal_type = literal_false;
    literal->dstr = empty_dsstring();

    return &literal->hd;
}

ASTHD* ast_binop(const char *binop_str, ASTHD *lhs, ASTHD *rhs) {
    AST_BinOp *binop = (AST_BinOp *)ast_make(asttype_binop, sizeof(AST_BinOp));

    binop->binop_str = dsstring_from_str(binop_str);
    binop->lhs = lhs;
    binop->rhs = rhs;

    return &binop->hd;
}
ASTHD* ast_unop(const char *unop_str, ASTHD *param) {
    AST_UnOp *unop = (AST_UnOp *)ast_make(asttype_unop, sizeof(AST_UnOp));
    unop->unop_str = dsstring_from_str(unop_str);
    unop->param = param;

    return &unop->hd;
}

ASTHD* ast_assign_name(short assign_type, ASTDS_String dstr, ASTHD *param) {
    AST_Assign *assign = (AST_Assign *)ast_make(asttype_assign, sizeof(AST_Assign));
    assign->assign_type = assign_type;
    assign->lvalue_type = lvalue_name;
    assign->lvalue_as.name = dstr;
    assign->param = param;
    return &assign->hd;
}
ASTHD* ast_assign_attr(short assign_type, ASTHD *scope, ASTDS_String attr_dstr, ASTHD *param) {
    AST_Assign *assign = (AST_Assign *)ast_make(asttype_assign, sizeof(AST_Assign));
    assign->assign_type = assign_type;
    assign->lvalue_type = lvalue_attr;
    assign->lvalue_as.attr.scope = scope;
    assign->lvalue_as.attr.name = attr_dstr;
    assign->param = param;
    return &assign->hd;
}
ASTHD* ast_assign_array(short assign_type, ASTHD *scope, ASTHD *index, ASTHD *param) {
    AST_Assign *assign = (AST_Assign *)ast_make(asttype_assign, sizeof(AST_Assign));
    assign->assign_type = assign_type;
    assign->lvalue_type = lvalue_array;
    assign->lvalue_as.array.scope = scope;
    assign->lvalue_as.array.index = index;
    assign->param = param;
    return &assign->hd;
}

ASTHD* ast_suite_cons_normal(ASTHD *elem, ASTHD *dst) {
    AST_Suite *suite = (AST_Suite *)ast_make(asttype_suite, sizeof(AST_Suite));

    suite->is_arrow = 0;
    suite->arrow_lstring = empty_dsstring();
    suite->param = elem;
    suite->next = (AST_Suite *)dst;

    return &suite->hd;
}

ASTHD* ast_suite_cons_arrow_del(AST_Arrow *arrow, ASTHD *dst) {
    AST_Suite *suite = (AST_Suite *)ast_make(asttype_suite, sizeof(AST_Suite));

    suite->is_arrow = 1;
    suite->arrow_lstring = arrow->name;
    suite->param = arrow->param;
    suite->next = (AST_Suite *)dst;

    ast_shallow_remove(&arrow->hd);

    return &suite->hd;
}


ASTHD* ast_xexpr_single(ASTHD *head_expr, ASTDS_Arguments argument,
                        ASTHD *vert_suite) {
    AST_XExpr *xexpr = (AST_XExpr *)ast_make(asttype_xexpr, sizeof(AST_XExpr));

    xexpr->has_head_label = 0;
    xexpr->has_vert_suite = !!vert_suite;
    xexpr->head_expr = head_expr;
    xexpr->head_label = empty_dsstring();
    xexpr->args = argument;
    xexpr->vert_suite = vert_suite;

    return &xexpr->hd;
}

ASTHD* ast_xexpr_double(const char *head_label_str, ASTHD *head_expr, ASTDS_Arguments argument,
                        ASTHD *vert_suite) {
    AST_XExpr *xexpr = (AST_XExpr *)ast_make(asttype_xexpr, sizeof(AST_XExpr));

    xexpr->has_head_label = 1;
    xexpr->has_vert_suite = !!vert_suite;
    xexpr->head_label = dsstring_from_str(head_label_str);
    xexpr->head_expr = head_expr;
    xexpr->args = argument;
    xexpr->vert_suite = vert_suite;

    return &xexpr->hd;
}

void ast_xexpr_set_vert_suite(AST_XExpr *xexpr, AST_Suite *vert_suite) {
    xexpr->has_vert_suite = !!vert_suite;
    xexpr->vert_suite = &vert_suite->hd;
}


ASTDS_SingleArg* astds_singlearg_cons(ASTHD *elem, ASTDS_SingleArg* sarg) {
    ASTDS_SingleArg *ret = (ASTDS_SingleArg *)malloc(sizeof(ASTDS_SingleArg));

    ret->param = elem;
    ret->next = sarg;

    return ret;
}

ASTDS_KwdArg* astds_kwdarg_cons(ASTDS_String dstr, ASTHD *elem, ASTDS_KwdArg *karg) {
    ASTDS_KwdArg *ret = (ASTDS_KwdArg *)malloc(sizeof(ASTDS_KwdArg));

    ret->name = dstr;
    ret->param = elem;
    ret->next = karg;

    return ret;
}

ASTDS_Arguments astds_arguments(ASTDS_SingleArg *sargs,
                                ASTDS_KwdArg *kargs,
                                ASTHD *star,
                                ASTHD *dstar,
                                ASTHD *amp,
                                ASTHD *damp) {

    ASTDS_Arguments ret;
    ret.sargs = sargs;
    ret.kargs = kargs;
    ret.star = star;
    ret.dstar = dstar;
    ret.amp = amp;
    ret.damp = damp;

    ret.has_star = !!star;
    ret.has_dstar = !!dstar;
    ret.has_amp = !!amp;
    ret.has_damp = !!damp;

    return ret;
}

ASTDS_Arguments astds_empty_arguments() {
    return astds_arguments(NULL, NULL, NULL, NULL, NULL, NULL);
}

ASTHD* ast_inline_app(ASTHD *scope, ASTDS_Arguments args) {
    AST_InlineApp *iapp = (AST_InlineApp *)ast_make(asttype_imd_inline_app, sizeof(AST_InlineApp));
    iapp->scope = scope;
    iapp->args = args;

    return &iapp->hd;
}

ASTHD* ast_arrow(const char *str, ASTHD *param) {
    AST_Arrow *arrow = (AST_Arrow *)ast_make(asttype_imd_arrow, sizeof(AST_Arrow));
    arrow->name = dsstring_from_str(str);
    arrow->param = param;
    return &arrow->hd;
}

ASTHD* ast_arrow_with_literal_del(AST_Literal *literal, ASTHD *param) {
    AST_Arrow *arrow = (AST_Arrow *)ast_make(asttype_imd_arrow, sizeof(AST_Arrow));
    arrow->name = literal->dstr;
    arrow->param = param;

    ast_shallow_remove(&literal->hd);
    return &arrow->hd;
}

void ast_shallow_remove(ASTHD *ast) {
    free(ast);
}

static void ast_free_trailer(ASTHD *ast) {
    AST_Trailer *trailer = (AST_Trailer *)ast;
    switch(trailer->trailer_type) {
        case trailer_attr:
            free_dsstring(&trailer->as.attr);
            break;
        case trailer_array:
            ast_free(trailer->as.index_param);
            break;
        case trailer_lrslice:
        case trailer_lslice:
        case trailer_rslice:
        case trailer_noslice:
            ast_free(trailer->as.slice_indices.left);
            ast_free(trailer->as.slice_indices.right);
            break;
    }
    ast_free(trailer->scope);
}

static void ast_free_name(ASTHD *ast) {
    AST_Name *name = (AST_Name *)ast;
    free_dsstring(&name->dstr);
}

static void ast_free_literal(ASTHD *ast) {
    AST_Literal *literal = (AST_Literal *)ast;
    free_dsstring(&literal->dstr);
}

static void ast_free_binop(ASTHD *ast) {
    AST_BinOp *binop = (AST_BinOp *)ast;
    free_dsstring(&binop->binop_str);
    ast_free(binop->lhs);
    ast_free(binop->rhs);
}

static void ast_free_unop(ASTHD *ast) {
    AST_UnOp *unop = (AST_UnOp *)ast;

    free_dsstring(&unop->unop_str);
    ast_free(unop->param);
}

static void ast_free_imd_inline_app(ASTHD *ast) {
    AST_InlineApp *iapp = (AST_InlineApp *)ast;
    astds_free_arguments(&iapp->args);
    ast_free(iapp->scope);
}

static void ast_free_imd_arrow(ASTHD *ast) {
    AST_Arrow *arrow = (AST_Arrow *)ast;
    free_dsstring(&arrow->name);
    ast_free(arrow->param);
}

static void ast_free_assign(ASTHD *ast) {
    AST_Assign *assign = (AST_Assign *)ast;
    switch(assign->lvalue_type) {
        case lvalue_name:
            free_dsstring(&assign->lvalue_as.name);
            break;
        case lvalue_attr:
            free_dsstring(&assign->lvalue_as.attr.name);
            ast_free(assign->lvalue_as.attr.scope);
            break;
        case lvalue_array:
            ast_free(assign->lvalue_as.array.scope);
            ast_free(assign->lvalue_as.array.index);
            break;
    }
    ast_free(assign->param);
}

void astds_free_arguments(ASTDS_Arguments *arguments) {
    free_singlearg(arguments->sargs);
    free_kwdarg(arguments->kargs);
    if(arguments->has_star)
        ast_free(arguments->star);
    if(arguments->has_dstar)
        ast_free(arguments->dstar);
    if(arguments->has_amp)
        ast_free(arguments->amp);
    if(arguments->has_damp)
        ast_free(arguments->damp);
}

static void ast_free_xexpr(ASTHD *ast) {
    AST_XExpr *xexpr = (AST_XExpr *)ast;
    
    free_dsstring(&xexpr->head_label);
    ast_free(xexpr->head_expr);
    astds_free_arguments(&xexpr->args);

    ast_free(xexpr->vert_suite);
}

static void ast_free_suite(ASTHD *ast) {
    AST_Suite *suite, *next;
    for(suite = (AST_Suite *)ast; suite; suite = next) {
        next = suite->next;
        free_dsstring(&suite->arrow_lstring);
        ast_free(suite->param);
        if(&suite->hd != ast)
            ast_shallow_remove(&suite->hd);
    }
}

void ast_free(ASTHD *ast) {
    if(!ast)
        return;
    switch(ast->node_type) {
        case asttype_trailer:
            ast_free_trailer(ast);
            break;
        case asttype_name:
            ast_free_name(ast);
            break;
        case asttype_literal:
            ast_free_literal(ast);
            break;
        case asttype_binop:
            ast_free_binop(ast);
            break;
        case asttype_unop:
            ast_free_unop(ast);
            break;
        case asttype_assign:
            ast_free_assign(ast);
            break;
        case asttype_suite:
            ast_free_suite(ast);
            break;
        case asttype_xexpr:
            ast_free_xexpr(ast);
            break;
        case asttype_imd_inline_app:
            ast_free_imd_inline_app(ast);
            break;
        case asttype_imd_arrow:
            ast_free_imd_arrow(ast);
            break;
    }
    free(ast);
}

static void trailer_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_Trailer *trailer = (AST_Trailer *)ast;

    ast_visit(&trailer->scope, visitor, arg);
    switch(trailer->trailer_type) {
        case trailer_array:
            ast_visit(&trailer->as.index_param, visitor, arg);
            break;
        case trailer_lrslice:
        case trailer_lslice:
        case trailer_rslice:
        case trailer_noslice:
            ast_visit(&trailer->as.slice_indices.left, visitor, arg);
            ast_visit(&trailer->as.slice_indices.right, visitor, arg);
            break;
    }
}

static void binop_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_BinOp *binop = (AST_BinOp *)ast;

    ast_visit(&binop->lhs, visitor, arg);
    ast_visit(&binop->rhs, visitor, arg);
}

static void unop_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_UnOp *unop = (AST_UnOp *)ast;
    ast_visit(&unop->param, visitor, arg);
}

static void assign_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_Assign *assign = (AST_Assign *)ast;
    ast_visit(&assign->param, visitor, arg);
    if(assign->lvalue_type == lvalue_attr) {
        ast_visit(&assign->lvalue_as.attr.scope, visitor, arg);
    } else if(assign->lvalue_type == lvalue_array) {
        ast_visit(&assign->lvalue_as.array.scope, visitor, arg);
        ast_visit(&assign->lvalue_as.array.index, visitor, arg);
    }
}

static void suite_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_Suite *p;

    for(p = (AST_Suite *)ast; p; p = p->next) {
        ast_visit(&p->param, visitor, arg);
    }
}

static void arguments_visit(ASTDS_Arguments *args, ast_visitor_fun visitor, void *arg) {
    ASTDS_SingleArg *sp;
    ASTDS_KwdArg *kp;
    for(sp = args->sargs; sp; sp = sp->next) {
        ast_visit(&sp->param, visitor, arg);
    }
    for(kp = args->kargs; kp; kp = kp->next) {
        ast_visit(&kp->param, visitor, arg);
    }
    if(args->has_star)
        ast_visit(&args->star, visitor, arg);
    if(args->has_dstar)
        ast_visit(&args->dstar, visitor, arg);
    if(args->has_amp)
        ast_visit(&args->amp, visitor, arg);
    if(args->has_damp)
        ast_visit(&args->damp, visitor, arg);
}


static void xexpr_visit(ASTHD *ast, ast_visitor_fun visitor, void *arg) {
    AST_XExpr *xexpr = (AST_XExpr *)ast;
    ast_visit(&xexpr->head_expr, visitor, arg);
    if(xexpr->has_vert_suite)
        ast_visit(&xexpr->vert_suite, visitor, arg);
    arguments_visit(&xexpr->args, visitor, arg);
}

void ast_visit(ASTHD **root, ast_visitor_fun visitor, void *arg) {
    if(!root)
        return;
    ASTHD *ast = *root;
    if(!ast)
        return;
    switch(ast->node_type) {
        case asttype_trailer:
            trailer_visit(*root, visitor, arg);
            break;
        case asttype_binop:
            binop_visit(*root, visitor, arg);
            break;
        case asttype_unop:
            unop_visit(*root, visitor, arg);
            break;
        case asttype_assign:
            assign_visit(*root, visitor, arg);
            break;
        case asttype_suite:
            suite_visit(*root, visitor, arg);
            break;
        case asttype_xexpr:
            xexpr_visit(*root, visitor, arg);
            break;
        case asttype_imd_inline_app:
            {
            AST_InlineApp *iapp = (AST_InlineApp *)ast;
            ast_visit(&iapp->scope, visitor, arg);
            arguments_visit(&iapp->args, visitor, arg);
            }
            break;
        case asttype_imd_arrow:
            {
            AST_Arrow *arrow = (AST_Arrow *)ast;
            ast_visit(&arrow->param, visitor, arg);
            }
            break;
    }
    visitor(root, arg);
}

void free_singlearg(ASTDS_SingleArg* sarg) {
    ASTDS_SingleArg *p, *next;
    for(p = sarg; p; p = next) {
        next = p->next;
        ast_free(p->param);
        free(p);
    }
}

void free_kwdarg(ASTDS_KwdArg* karg) {
    ASTDS_KwdArg *p, *next;
    for(p = karg; p; p = next) {
        next = p->next;
        free_dsstring(&p->name);
        ast_free(p->param);
        free(p);
    }
}

ASTDS_String astds_strip_del_name(ASTHD *name) {
    ASTDS_String ret;
    ret = ((AST_Name *)name)->dstr;
    ast_shallow_remove(name);

    return ret;
}

ASTDS_String astds_strip_del_literal(ASTHD *literal) {
    ASTDS_String ret;
    ret = ((AST_Literal *)literal)->dstr;

    ast_shallow_remove(literal);
    return ret;
}
/*
 * Debug String Output
 */
static void print_locinfo(ASTHD *ast) {
    if (ast)
        printf("[line:%d-%d, col:%d-%d]",
                ast->loc.sline, ast->loc.eline,
                ast->loc.scol, ast->loc.ecol - 1);
}

static void print_ast(ASTHD *ast, int indent);
static void print_indent(int indent) {
    int i;
    for(i = 0; i < indent; i++)
        printf(" ");
}
static void println() { printf("\n"); }
static void print_dsstring(ASTDS_String *dstr) { printf("%s", dstr->str); }
static void print_arguments(ASTDS_Arguments *args, int indent) {
    ASTDS_SingleArg *sa;
    ASTDS_KwdArg *ka;

    for(sa = args->sargs; sa; sa = sa->next) {
        print_indent(indent);
        printf("$ ->\n");
        print_ast(sa->param, indent + 2);
    }
    for(ka = args->kargs; ka; ka = ka->next) {
        print_indent(indent);
        print_dsstring(&ka->name);
        printf(" -> \n");
        print_ast(ka->param, indent + 2);
    }
    if(args->has_star) {
        print_indent(indent);
        printf("* -> \n");
        print_ast(args->star, indent + 2);
    }
    if(args->has_dstar) {
        print_indent(indent);
        printf("** -> \n");
        print_ast(args->dstar, indent + 2);
    }
    if(args->has_amp) {
        print_indent(indent);
        printf("& -> \n");
        print_ast(args->amp, indent + 2);
    }
    if(args->has_damp) {
        print_indent(indent);
        printf("&& -> \n");
        print_ast(args->damp, indent + 2);
    }

}

static void print_trailer(ASTHD *ast, int indent) {
    AST_Trailer *trailer = (AST_Trailer *)ast;
    print_indent(indent);
    print_locinfo(ast);
    switch(trailer->trailer_type) {
        case trailer_attr:
            printf("Attr(%s):\n", trailer->as.attr.str);
            print_ast(trailer->scope, indent+2);
            break;
        case trailer_array:
            printf("Array:\n");
            print_indent(indent+2);
            printf("index->\n");
            print_ast(trailer->as.index_param, indent+2);
            print_indent(indent+2);
            printf("content->\n");
            print_ast(trailer->scope, indent+2);
            break;
        case trailer_lrslice:
        case trailer_lslice:
        case trailer_rslice:
        case trailer_noslice:
            printf("Slice:\n");
            if(trailer->as.slice_indices.left) {
                print_indent(indent+2);
                printf("left ->\n");
                print_ast(trailer->as.slice_indices.left, indent+2);
            }
            if(trailer->as.slice_indices.right) {
                print_indent(indent+2);
                printf("right ->\n");
                print_ast(trailer->as.slice_indices.right, indent+2);
            }
            print_indent(indent+2);
            printf("content->\n");
            print_ast(trailer->scope, indent+2);
            break;
    }
    println();
}

static void print_name(ASTHD *ast, int indent) {
    print_indent(indent);
    print_locinfo(ast);
    printf("Name(%s)", ((AST_Name *)ast)->dstr.str);
    println();
}

static void print_literal(ASTHD *ast, int indent) {
    AST_Literal *literal = (AST_Literal *)ast;
    print_indent(indent);
    print_locinfo(ast);
    switch(literal->literal_type) {
        case literal_string:
            printf("'");
            print_dsstring(&literal->dstr);
            printf("'");
            break;
        case literal_integer:
        case literal_float:
            print_dsstring(&literal->dstr);
            break;
        case literal_null:
            printf("null");
            break;
        case literal_true:
            printf("true");
            break;
        case literal_false:
            printf("false");
            break;
    }
    println();
}

static void print_binop(ASTHD *ast, int indent) {
    AST_BinOp *binop = (AST_BinOp *)ast;
    print_indent(indent);
    print_locinfo(ast);
    printf("Bin(%s):\n", binop->binop_str.str);
    print_ast(binop->lhs, indent+2);
    print_ast(binop->rhs, indent+2);
    println();
}

static void print_unop(ASTHD *ast, int indent) {
    AST_UnOp *unop = (AST_UnOp *)ast;
    print_indent(indent);
    print_locinfo(ast);
    printf("Un(%s):\n", unop->unop_str.str);
    print_ast(unop->param, indent+2);
    println();
}

static void print_assign(ASTHD *ast, int indent) {
    AST_Assign *assign = (AST_Assign *)ast;
    print_indent(indent);
    print_locinfo(ast);
    printf("ASSIGN(%s):\n", (assign->assign_type == assign_normal)? "=" : ":=");
    switch(assign->lvalue_type) {
        case lvalue_name:
            print_indent(indent+2);
            printf("to name -> %s\n", assign->lvalue_as.name.str);
            break;
        case lvalue_attr:
            print_indent(indent+2);
            printf("Attr(%s) Of\n ->", assign->lvalue_as.attr.name.str);
            print_ast(assign->lvalue_as.attr.scope, indent+2);
            break;
        case lvalue_array:
            print_indent(indent+2);
            printf("index ->\n");
            print_ast(assign->lvalue_as.array.index, indent+2);
            printf("icope ->\n");
            print_ast(assign->lvalue_as.array.scope, indent+2);
            break;
    }
    print_indent(indent+2);
    printf("assignee ->\n");
    print_ast(assign->param, indent+2);
}

static void print_suite(ASTHD *ast, int indent) {
    AST_Suite *suite;

    print_indent(indent);
    print_locinfo(ast);
    printf("Suite:\n");
    for(suite = (AST_Suite *)ast; suite; suite = suite->next) {
        if(suite->is_arrow) {
            print_indent(indent+2);
            printf("%s ARROW(=>)\n", suite->arrow_lstring.str);
        }
        print_ast(suite->param, indent + 2);
    }
}

static void print_xexpr(ASTHD *ast, int indent) {
    AST_XExpr *xexpr = (AST_XExpr *)ast;
    print_indent(indent);
    print_locinfo(ast);
    printf("%sXEXPR\n", xexpr->has_head_label?"LABELED ":"");
    if(xexpr->has_head_label) {
        print_indent(indent + 2);
        printf("Head label: ");
        print_dsstring(&xexpr->head_label);
        println();
    }

    print_indent(indent + 2);
    printf("head_expr -> \n");
    print_ast(xexpr->head_expr, indent+4);

    print_indent(indent + 2);
    printf("arguments -> \n");
    print_arguments(&xexpr->args, indent+4);

    print_indent(indent + 2);
    printf("suite -> \n");
    print_suite(xexpr->vert_suite, indent+4);
}

static void print_ast(ASTHD *root, int indent) {
    if(!root) return;
    switch(root->node_type) {
        case asttype_trailer:
            print_trailer(root, indent);
            break;
        case asttype_name:
            print_name(root, indent);
            break;
        case asttype_literal:
            print_literal(root, indent);
            break;
        case asttype_binop:
            print_binop(root, indent);
            break;
        case asttype_unop:
            print_unop(root, indent);
            break;
        case asttype_assign:
            print_assign(root, indent);
            break;
        case asttype_suite:
            print_suite(root, indent);
            break;
        case asttype_xexpr:
            print_xexpr(root, indent);
            break;
        case asttype_imd_inline_app:
            printf("<<ERROR! INLINE APP detected!>>\n");
            break;
        case asttype_imd_arrow:
            printf("<<ERROR! ARROW detected!>>\n");
            break;
    }
}

void ast_dbg_print(ASTHD *root) {
    print_ast(root, 0);
}
