#include <string.h>
#include <assert.h>
#include "astmisc.h"
void init_parse_result(ParseResult *pres) { 
    pres->error_occurred = 0;
    pres->err_msg[0] = 0;
    pres->result_ast = NULL;
}

void pres_set_error(ParseResult *pres, int err_code, const char *err_msg) {
    pres->error_occurred = 1;
    pres->err_code = err_code;
    strncpy(pres->err_msg, err_msg, PARSE_MAX_ERR_MSG_CNT - 1);
}

void remove_parse_result(ParseResult *pres, int remove_ast) {
    if(remove_ast && pres->result_ast)
        ast_free(pres->result_ast);
}

ASTMISC_OneArg astmisc_onearg_pos(ASTHD *ast) {
    ASTMISC_OneArg ret;
    ret.type = onearg_pos;
    ret.name = empty_dsstring();
    ret.value = ast;

    return ret;
}
ASTMISC_OneArg astmisc_onearg_pair(const char *str, ASTHD *value) {
    ASTMISC_OneArg ret;
    ret.type = onearg_pair;
    ret.name = dsstring_from_str(str);
    ret.value = value;

    return ret;
}
ASTMISC_OneArg astmisc_onearg_pair_with_literal_del(ASTHD *literal, ASTHD *value) {
    ASTMISC_OneArg ret;
    ret.type = onearg_pair;
    ret.name = ((AST_Literal *)literal)->dstr;
    ret.value = value;

    ast_shallow_remove(literal);
    return ret;
}
ASTMISC_OneArg astmisc_onearg_pair_with_arrow_del(ASTHD *arrow) {
    ASTMISC_OneArg ret;
    ret.type = onearg_pair;
    ret.name = ((AST_Arrow *)arrow)->name;
    ret.value = ((AST_Arrow *)arrow)->param;

    ast_shallow_remove(arrow);
    return ret;

}
ASTMISC_OneArg astmisc_onearg_star(ASTHD *ast) {
    ASTMISC_OneArg ret;
    ret.type = onearg_star;
    ret.name = empty_dsstring();
    ret.value = ast;
    return ret;
}
ASTMISC_OneArg astmisc_onearg_dstar(ASTHD *ast) {
    ASTMISC_OneArg ret;
    ret.type = onearg_dstar;
    ret.name = empty_dsstring();
    ret.value = ast;
    return ret;
}
ASTMISC_OneArg astmisc_onearg_amp(ASTHD *ast) {
    ASTMISC_OneArg ret;
    ret.type = onearg_amp;
    ret.name = empty_dsstring();
    ret.value = ast;
    return ret;
}
ASTMISC_OneArg astmisc_onearg_damp(ASTHD *ast) {
    ASTMISC_OneArg ret;
    ret.type = onearg_damp;
    ret.name = empty_dsstring();
    ret.value = ast;
    return ret;
}

void astmisc_remove_onearg(ASTMISC_OneArg *oarg) {
    free_dsstring(&oarg->name);
}

void astmisc_check_arg_order(ASTMISC_OneArg new_onearg, ASTDS_Arguments arg_info, ParseResult *pres) {
    switch(new_onearg.type) {
        case onearg_pos:
            break;
        case onearg_pair:
            if(arg_info.pargs) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "keyword argument cannot precede any positional argument");
            }
            break;
        case onearg_star:
            if(arg_info.pargs || arg_info.kargs) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "star-argument cannot precede any positional or keword argument");
            }
            if(arg_info.has_star) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "duplicated star-argument");
            }
            break;
        case onearg_dstar:
            if(arg_info.pargs || arg_info.kargs) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-star-argument cannot precede any positional or keword argument");
            }
            if(arg_info.has_star) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-star-argument cannot precede star-argument");
            }
            if(arg_info.has_dstar) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "duplicated double-star-argument");
            }
            break;
        case onearg_amp:
            if(arg_info.pargs || arg_info.kargs) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "ampersand-argument cannot precede any positional or keword argument");
            }
            if(arg_info.has_star) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "ampersand-argument cannot precede star-argument");
            }
            if(arg_info.has_dstar) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "ampersand-argument cannot precede double-star-argument");
            }
            if(arg_info.has_amp) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "duplicated ampersand-argument");
            }
            break;
        case onearg_damp:
            if(arg_info.pargs || arg_info.kargs) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-ampersand-argument cannot precede any positional or keword argument");
            }
            if(arg_info.has_star) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-ampersand-argument cannot precede star-argument");
            }
            if(arg_info.has_dstar) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-ampersand-argument cannot precede double-star-argument");
            }
            if(arg_info.has_amp) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "double-ampersand-argument cannot precede double-star-argument");
            }
            if(arg_info.has_damp) {
                pres_set_error(pres, PARSE_ERR_ILLEGAL_ARG, "duplicated double-ampersand-argument");
            }
            break;
    }
}

ASTHD* astmisc_make_assign(short assign_type, ASTHD *lvalue, ASTHD *param, ParseResult *pres) {
    switch(lvalue->node_type) {
        case asttype_name:
            return ast_assign_name(assign_type, astds_strip_del_name(lvalue), param);
        case asttype_trailer:
            {
                int trailer_type;
                AST_Trailer *trailer;
                ASTHD *scope;
                trailer = (AST_Trailer *)lvalue;
                trailer_type = trailer->trailer_type;
                scope = trailer->scope;

                if(trailer_type == trailer_attr) {
                    ASTHD *ret;

                    ret = ast_assign_attr(assign_type, scope, trailer->as.attr, param);
                    ast_shallow_remove(&trailer->hd);
                    return ret;
                } else if(trailer_type == trailer_array) {
                    ASTHD *ret;

                    ret = ast_assign_array(assign_type, scope, trailer->as.index_param, param);
                    ast_shallow_remove(&trailer->hd);
                    return ret;
                } 
            }
            break;
    }

    pres_set_error(pres, PARSE_ERR_ILLEGAL_LVALUE, "invalid l-value for definition/assignment");
    // HACK
    ast_free(lvalue);
    ast_free(param);
    return ast_string_literal("ERROR");
}

void astmisc_args_prepend(ASTMISC_OneArg B, ASTDS_Arguments *C) {
    switch(B.type) {
        case onearg_pos:
            C->pargs = astds_singlearg_cons(B.value, C->pargs);
            break;
        case onearg_pair:
            C->kargs = astds_kwdarg_cons(B.name, B.value, C->kargs);
            break;
        case onearg_star:
            C->has_star = 1;
            C->star = B.value;
            break;
        case onearg_dstar:
            C->has_dstar = 1;
            C->dstar = B.value;
            break;
        case onearg_amp:
            C->has_amp = 1;
            C->amp = B.value;
            break;
        case onearg_damp:
            C->has_damp = 1;
            C->damp = B.value;
            break;
    }
}

#define IS_DOUBLE_XEXPR(scope) \
    ((scope) && \
     (scope)->node_type == asttype_xexpr && \
     ((AST_XExpr *)(scope))->has_head_label)

#define IS_DOUBLE_INLINE_XEXPR(scope) \
    ((scope) && \
     (scope)->node_type == asttype_xexpr && \
     ((AST_XExpr *)(scope))->has_head_label && \
     !((AST_XExpr *)(scope))->has_vert_suite)


static ASTHD *imd_inline_to_single_xexpr(AST_InlineApp *iapp, ASTHD *vert_suite) {
    ASTHD *inside_scope = iapp->scope;
    ASTHD *ret = ast_xexpr_single(inside_scope, iapp->arg_info, vert_suite);
    ast_shallow_remove(&iapp->hd);

    return ret;
}

static ASTHD *imd_inline_to_double_xexpr(AST_InlineApp *iapp, char *head_name, ASTHD *vert_suite) {
    ASTHD *inside_scope = iapp->scope;
    ASTHD *ret = ast_xexpr_double(head_name, inside_scope, iapp->arg_info, vert_suite);
    ast_shallow_remove(&iapp->hd);

    return ret;
}
     

ASTHD *astmisc_vert_lookahead(ASTHD* scope, ASTHD *vert_suite, ASTDS_Arguments *p_args) {
    if(!p_args && IS_DOUBLE_INLINE_XEXPR(scope)) {
        /*
         * def aa(a=1, b= 2):
         *  c
         *  d
         */
        AST_XExpr *dxexpr = (AST_XExpr *)scope;
        ast_xexpr_set_vert_suite(dxexpr, (AST_Suite *)vert_suite);

        return &dxexpr->hd;
    } else if(!p_args && scope->node_type == asttype_imd_inline_app) {
        /*
         *   aa(1,2,3):
         *      a
         *      b
         *      c
         */
        return imd_inline_to_single_xexpr((AST_InlineApp *)scope, vert_suite);
    } else if(p_args && IS_DOUBLE_INLINE_XEXPR(scope)) {
        /*
         * def f>
         *   a -> 1
         *   b -> 2
         * --
         *   a   
         *   b
         *
         */
        AST_XExpr *dxexpr = (AST_XExpr *)scope;
        ast_xexpr_set_vert_suite(dxexpr, (AST_Suite *)vert_suite);
        dxexpr->arg_info = *p_args;
        return &dxexpr->hd;
    } else if(p_args) {
        /*
         * fun>
         *   a -> 1
         *   b -> 2
         * --
         *   1
         *   2
         *   3
         *
         */
        ASTHD *ret;
        ret = ast_xexpr_single(
            scope, 
            *p_args,
            vert_suite);
        return ret;
    } else {
        /*
         * list:
         *   1
         *   2
         *   3
         *
         */
        ASTHD *ret;
        ret = ast_xexpr_single(
            scope, 
            astds_empty_arguments(),
            vert_suite);
        return ret;
    }
}

ASTHD* astmisc_dexpr_lookahead(ASTHD *scope, char *head_name, ASTHD *vert_suite) {
    if(scope->node_type == asttype_imd_inline_app) {
        return imd_inline_to_double_xexpr((AST_InlineApp *)scope, head_name, vert_suite);
    } else {
        ASTHD *ret;
        ret = ast_xexpr_double(
            head_name,
            scope, 
            astds_empty_arguments(),
            vert_suite);
        return ret;
    }
}

ASTHD *convert_inline_app_to_xexpr(ASTHD *ast) {
    if(ast->node_type == asttype_imd_inline_app) {
        ASTHD *ret;
        AST_InlineApp *iapp = (AST_InlineApp *)ast;

        ret = ast_xexpr_single(iapp->scope, iapp->arg_info, NULL);
        ast_shallow_remove(ast);
        return ret;
    } else {
        return ast;
    }
}

static void trace_trailer(ASTHD *start, ASTHD *leaf_scope) {
    ASTHD* p, *prev;

    if(!start)
        return;

    for(p = start; p; ) {
        if(p->node_type == asttype_trailer) {
            prev = p;
            p = ((AST_Trailer *)p)->scope;
        } else if(p->node_type == asttype_imd_inline_app) {
            prev = p;
            p = ((AST_InlineApp *)p)->scope;
        } else 
            assert(0); // NOT REACHABLE
    }
    if(prev->node_type == asttype_trailer) {
        ((AST_Trailer *)prev)->scope = leaf_scope;
    } else if(prev->node_type == asttype_imd_inline_app) {
        ((AST_InlineApp *)prev)->scope = leaf_scope;
    } else
        assert(0); // NOT REACHABLE
}

ASTHD *astmisc_trailer_set_leaf_scope(ASTHD* trailers, ASTHD *leaf_scope) {
    trace_trailer(trailers, leaf_scope);
    return trailers;
}

static void app_line_changer(ASTHD **p_ast, void *arg) {
    ASTHD *root = *p_ast;
    if(root->node_type == asttype_imd_inline_app) {
        ASTHD *ret;
        AST_InlineApp *iapp;

        iapp = (AST_InlineApp *)root;
        ret = ast_xexpr_single(iapp->scope, iapp->arg_info, NULL);
        ret->loc = root->loc;
        ast_shallow_remove(root);
        *p_ast = ret;
    }
}

void astmisc_convert_all_inline_app(ASTHD** root) {
    /* suite node is processed seperately to prevent stack overflow */
    if(root)
        ast_visit(root, app_line_changer, NULL);
}
