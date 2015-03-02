%include  { 
    #include <stdio.h>
    #include <assert.h>
    #include <string.h>
    #include "ast.h"
    #include "lexer.h"
    #include "astmisc.h"

    #ifndef NULL
    # define NULL ((void *) 0)
    #endif

    #define RM_TOKEN(x) Lexer_remove_token(x)

}

%name LEMONParse
%token_type { LexToken * }
%token_destructor { RM_TOKEN($$); }
%default_type { ASTHD * }
%type argument { ASTMISC_OneArg }
%type arguments { ASTDS_Arguments }
%type arg_stub { ASTDS_Arguments }
%type vert_arg_exprs { ASTDS_Arguments }
%type vert_arg_expr { ASTMISC_OneArg }
%stack_size 1024


%default_destructor { ast_free($$); }
%destructor arguments { astds_free_arguments(&$$); }
%destructor argument { astmisc_remove_onearg(&$$); }
%destructor arg_stub { astds_free_arguments(&$$); }
%destructor vert_arg_exprs { astds_free_arguments(&$$); }
%destructor vert_arg_expr { astmisc_remove_onearg(&$$); }

%extra_argument { ParseResult* parser_result }

%start_symbol program
%syntax_error {
    pres_set_error(parser_result, PARSE_ERR_SYNTAX_ERROR, "syntax error");
#ifndef NDEBUG
    int n = sizeof(yyTokenName) / sizeof(yyTokenName[0]);
    for (int i = 0; i < n; ++i) {
        int a = yy_find_shift_action(yypParser, (YYCODETYPE)i);
        if (a < YYNSTATE + YYNRULE) {
            printf("possible token: %s\n", yyTokenName[i]);
        }
    }
 #endif

}
%stack_overflow {
    pres_set_error(parser_result, PARSE_ERR_STACK_OVERFLOW, "parser stack overflow.");
}

program(A) ::= exprs(B). {
    A = B;
    parser_result->result_ast = A;
}

// expr may be an arrow expression. It should not appear in expr suite
/*
 * In parsing process, Suite appears in reversed order.
 * Reversing suite list should be done as final processing of ast
*/
exprs(A) ::= expr(B). {
    ASTLoc loc;
    loc = B->loc;
    if(B->node_type == asttype_imd_arrow) {
        AST_Arrow *arrow = (AST_Arrow *)(B);
        A = ast_suite_cons_arrow_del(arrow, NULL);
    } else {
        A = ast_suite_cons_normal(B, NULL);
    }
    A->loc = loc;
}

exprs(A) ::= NEWLINE(tokB). {
    A = NULL;
    RM_TOKEN(tokB);
}

exprs(A) ::= exprs(DST) expr(ELEM).  {
    if(!ELEM) {
        A = DST;
        if(DST) {
            TRACK_N(A, DST);
        } 
    } else {
        ASTLoc loc;

        if(DST) {
            MERGE_ASTLOC(loc, DST->loc, ELEM->loc);
        } else {
            loc = ELEM->loc;
        }
        if(ELEM->node_type == asttype_imd_arrow) {
            AST_Arrow *arrow = (AST_Arrow *)(ELEM);
            A = ast_suite_cons_arrow_del(arrow, DST);
        } else {
            A = ast_suite_cons_normal(ELEM, DST);
        }
        A->loc = loc;
    }
}

exprs(A) ::= exprs(DST) NEWLINE(tokC). {
    A = DST;
    if (DST) {
        TRACK_NT(A, DST, tokC);
    }
    RM_TOKEN(tokC);
}

expr(A) ::= normal_expr(B). { 
    A = B;
    TRACK_N(A, B);
}

/*
 * definition of lvalue
 * ---
 * lvalue := id ( id )
 * lvalue := expr . id ( attribute access )
 * lvalue := expr [ expr ] ( array access )
 *
 */
expr(A) ::= small_expr(B) ASSIGN normal_expr(C). {
    ASTLoc lloc, rloc;
    lloc = B->loc;
    rloc = C->loc;
    A = astmisc_make_assign(assign_normal, B,  C, parser_result);
    MERGE_ASTLOC(A->loc, lloc, rloc);
}
/* a := 1 */
expr(A) ::= small_expr(B) DEFASSIGN normal_expr(C). {
    ASTLoc lloc, rloc;
    lloc = B->loc;
    rloc = C->loc;
    A = astmisc_make_assign(assign_def, B,  C, parser_result);
    MERGE_ASTLOC(A->loc, lloc, rloc);
}

/* INTERMEDIATE */
/* doc -> "Hello world!" */
expr(A) ::= NAME(tokB) ARROW normal_expr(C). {
    A = ast_arrow(tokB->text, C);
    TRACK_TN(A, tokB, C);
    RM_TOKEN(tokB);
}
/* INTERMEDIATE */
/* "doc" -> "Hello world!" */
expr(A) ::= strings(B) ARROW normal_expr(C). {
     A = ast_arrow_with_literal_del((AST_Literal *)B, C);
     TRACK_NN(A, B, C);
}

normal_expr(A) ::= simple_expr(B). {
    A = B;
    TRACK_N(A, B);
}
normal_expr(A) ::= compound_expr(B). {
    A = B;
    TRACK_N(A, B);
}

compound_expr(A) ::= vert_xexpr(B). {
    A = B;
    TRACK_N(A, B);
}

simple_expr(A) ::= small_expr(B) NEWLINE. {
    A = B;
    TRACK_N(A, B);
}

small_expr(A) ::= inline_xexpr(B). {
    A = B;
    TRACK_N(A, B);
}


inline_xexpr(A) ::= or_expr(B). { 
    A = B;
    TRACK_N(A, B);
}

inline_xexpr(A) ::= small_expr(B) COLUMN or_expr(C). {
    ASTLoc loc;
    ASTHD *suite;
    
    suite = ast_suite_cons_normal(C, NULL);
    suite->loc = C->loc;
    MERGE_ASTLOC(loc, B->loc, C->loc);
    A = astmisc_vert_lookahead(B, suite, NULL);
    A->loc = loc;
}


or_expr(A) ::= and_expr(B). { 
    A = B;
    TRACK_N(A, B);
}

or_expr(A) ::= or_expr(B) DPIPE(tokOP) and_expr(C). {
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

and_expr(A) ::= comp_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
and_expr(A) ::= and_expr(B) DAMP(tokOP) comp_expr(C). {
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

comp_expr(A) ::= pipe_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
comp_expr(A) ::= comp_expr(B) LT(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

comp_expr(A) ::= comp_expr(B) GT(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
comp_expr(A) ::= comp_expr(B) LTE(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

comp_expr(A) ::= comp_expr(B) GTE(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
comp_expr(A) ::= comp_expr(B) EQ(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
comp_expr(A) ::= comp_expr(B) NEQ(tokOP) pipe_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

pipe_expr(A) ::= amp_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
pipe_expr(A) ::= pipe_expr(B) PIPE(tokOP) amp_expr(C). {
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

amp_expr(A) ::= arith_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
amp_expr(A) ::= amp_expr(B) AMP(tokOP) arith_expr(C). {
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

arith_expr(A) ::= term_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
arith_expr(A) ::= arith_expr(B) PLUS(tokOP) term_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
arith_expr(A) ::= arith_expr(B) MINUS(tokOP) term_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

term_expr(A) ::= factor_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
term_expr(A) ::= term_expr(B) STAR(tokOP) factor_expr(C).{
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
term_expr(A) ::= term_expr(B) SLASH(tokOP) factor_expr(C).{ 
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}
term_expr(A) ::= term_expr(B) PERCENT(tokOP) factor_expr(C).{ 
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

factor_expr(A) ::= power_expr(B). {
    A = B;
    TRACK_N(A, B);
}
factor_expr(A) ::= PLUS(tokOP) factor_expr(B).{ 
    A = ast_unop(tokOP->text, B); 
    TRACK_TN(A, tokOP, B);
    RM_TOKEN(tokOP);
}
factor_expr(A) ::= MINUS(tokOP) factor_expr(B).{ 
    A = ast_unop(tokOP->text, B); 
    TRACK_TN(A, tokOP, B);
    RM_TOKEN(tokOP);
}
factor_expr(A) ::= BANG(tokOP) factor_expr(B).{ 
    A = ast_unop(tokOP->text, B); 
    TRACK_TN(A, tokOP, B);
    RM_TOKEN(tokOP);
}

power_expr(A) ::= par_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
power_expr(A) ::= par_expr(B) DSTAR(tokOP) factor_expr(C). { 
    A = ast_binop(tokOP->text, B, C);
    TRACK_NN(A, B, C);
    RM_TOKEN(tokOP);
}

par_expr(A) ::= LPAR(tokL) small_expr(B) RPAR(tokR). {
    A = B; 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
par_expr(A) ::= dexpr_head(B). { 
    A = B;
    TRACK_N(A, B);
}


dexpr_head(A) ::= access_expr(B). { 
    A = B;
    TRACK_N(A, B);
}
dexpr_head(A) ::= NAME(tok_LABELL) access_expr(HEAD). {
    ASTLoc loc;
    MERGE_ASTLOC(loc, *tok_LABELL, HEAD->loc);
    A = astmisc_dexpr_lookahead(HEAD, tok_LABELL->text, NULL); 
    A->loc = loc;
    RM_TOKEN(tok_LABELL);
}

access_expr(A) ::= atom(B). { 
    A = B; 
    TRACK_N(A, B);
}
access_expr(A) ::= atom(B) trailers(TRAILERS). { 
    A = astmisc_trailer_set_leaf_scope(TRAILERS, B); 
    TRACK_NN(A, B, TRAILERS);
}

id(A) ::= NAME(tokB). { 
    A = ast_name(tokB->text);
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}

atom(A) ::= strings(B). { 
    A = B; 
    TRACK_N(A, B);
}
atom(A) ::= BOOL(tokB). {
    if(!strcmp(tokB->text, "true")) 
        A = ast_true_literal();
    else
        A = ast_false_literal();

    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
atom(A) ::= INTEGER(tokB). { 
    A = ast_integer_literal(tokB->text);
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
atom(A) ::= FLOAT(tokB).{ 
    A = ast_float_literal(tokB->text); 
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
atom(A) ::= NULLOBJ(tokB). {
    A = ast_null_literal(); 
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
atom(A) ::= id(B). {
    A = B;
    TRACK_N(A, B);
}

/* strings yield AST_Name */
strings(A) ::= STRING(tokB). {
    A = ast_sliced_string_literal(tokB->text, 1, tokB->text_len - 2);
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
strings(A) ::= LONGSTRING(tokB). {
    // LONG STRING has format of '''...''' or """..."""
    A = ast_sliced_string_literal(tokB->text, 3, tokB->text_len - 6);
    TRACK_T(A, tokB);
    RM_TOKEN(tokB);
}
strings(A) ::= strings(B) STRING(tokC). { 
    ASTDS_String dstr;
    if(tokC->text_len >= 2) {
        dstr = make_dsstring(tokC->text + 1, tokC->text_len - 2);
    } else {
        dstr = dsstring_from_str("");
    }
    ast_string_literal_append(B, dstr.str);
    free_dsstring(&dstr);
    A = B;
    TRACK_NT(A, B, tokC);
    RM_TOKEN(tokC);
}

strings(A) ::= strings(B) LONGSTRING(tokC). {
    // HACK
    ASTDS_String dstr;
    if(tokC->text_len >= 6) {
        dstr = make_dsstring(tokC->text + 3, tokC->text_len - 6);
    } else {
        dstr = dsstring_from_str("");
    }
    ast_string_literal_append(B, dstr.str);
    free_dsstring(&dstr);
    A = B;
    TRACK_NT(A, B, tokC);
    RM_TOKEN(tokC);
}

trailers(A) ::= trailer(B). {
    A = B;
    TRACK_N(A, B);
}
trailers(A) ::= trailers(SCOPE) trailer(B). {
    if(B->node_type == asttype_imd_inline_app) {
        ((AST_InlineApp *)B)->scope = SCOPE;
    } else {
        ((AST_Trailer *)B)->scope = SCOPE;
    }
    A = B;
    TRACK_NN(A, SCOPE, B);
}

/* foo.x */
trailer(A) ::= DOT(tokB) NAME(tokC). { 
    A = ast_access_attr(NULL, tokC->text);
    TRACK_TT(A, tokB, tokC);
    RM_TOKEN(tokB);
    RM_TOKEN(tokC);
}
/* foo[x]*/
trailer(A) ::= LBRKT(tokL) or_expr(B) RBRKT(tokR). { 
    A = ast_access_array(NULL, B);
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
/* foo[:]*/
trailer(A) ::= LBRKT(tokL) COLUMN RBRKT(tokR). { 
    A = ast_slice_nolr(NULL); 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
/* foo[x:]*/
trailer(A) ::= LBRKT(tokL) or_expr(LEFT) COLUMN RBRKT(tokR). { 
    A = ast_slice_l(NULL, LEFT); 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
/* foo[:y]*/
trailer(A) ::= LBRKT(tokL) COLUMN or_expr(RIGHT) RBRKT(tokR). { 
    A = ast_slice_r(NULL, RIGHT); 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
/* foo[x:y]*/
trailer(A) ::= LBRKT(tokL) or_expr(LEFT) COLUMN or_expr(RIGHT) RBRKT(tokR). { 
    A = ast_slice_lr(NULL, LEFT, RIGHT); 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}

/* foo(x, y) : simple application, treated as special case */
trailer(A) ::= LPAR(tokL) arguments(ARGS) RPAR(tokR). { 
    A = ast_inline_app(NULL, ARGS);
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
/* foo() */
trailer(A) ::= LPAR(tokL) RPAR(tokR). { 
    ASTDS_Arguments arg_info;

    arg_info = astds_empty_arguments();
    ARG_TRACK_TT(arg_info, tokL, tokR);
    A = ast_inline_app(NULL, arg_info);
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}

argument(A) ::= small_expr(B). { 
    A = astmisc_onearg_pos(B); 
    ARG_TRACK_N(A, B);
}

argument(A) ::= NAME(tokB) ASSIGN small_expr(C). { 
    A = astmisc_onearg_pair(tokB->text, C); 
    ARG_TRACK_TN(A, tokB, C);
    RM_TOKEN(tokB);
}
argument(A) ::= strings(B) ASSIGN small_expr(C). {
    A = astmisc_onearg_pair_with_literal_del(B, C);
    ARG_TRACK_NN(A, B, C);
}
argument(A) ::= STAR(tokL) small_expr(B). { 
    A = astmisc_onearg_star(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
argument(A) ::= DSTAR(tokL) small_expr(B). { 
    A = astmisc_onearg_dstar(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
argument(A) ::= AMP(tokL) small_expr(B). { 
    A = astmisc_onearg_amp(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
argument(A) ::= DAMP(tokL) small_expr(B). { 
    A = astmisc_onearg_damp(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}

arguments(A) ::= argument(B). {
    A = astds_empty_arguments();
    astmisc_args_prepend(B, &A);
    A.loc = B.loc;
}

/* right recursion is intended. I believe that no one will use a huge number of arguments. */
arguments(A) ::= argument(B) COMMA arguments(C). {
    astmisc_check_arg_order(B, C, parser_result);
    astmisc_args_prepend(B, &C);
    A = C;
    ARG_TRACK_AA(A, B, C);
}


/* context sensitive filter */
vert_xexpr(A) ::= small_expr(B) COLUMN_NEWLINE NEWLINE stub(C). {
    ASTLoc loc;
    MERGE_ASTLOC(loc, B->loc, C->loc);
    A = astmisc_vert_lookahead(B, C, NULL);
    A->loc = loc;
}

vert_xexpr(A) ::= small_expr(B) GT_NEWLINE NEWLINE arg_stub(C). {
    ASTLoc loc;
    MERGE_ASTLOC(loc, B->loc, C.loc);
    A = astmisc_vert_lookahead(B, NULL, &C);
    A->loc = loc;
}
vert_xexpr(A) ::= small_expr(B) GT_NEWLINE NEWLINE arg_stub(C) DMINUS_NEWLINE NEWLINE stub(D). {
    ASTLoc loc;
    MERGE_ASTLOC(loc, B->loc, D->loc);
    A = astmisc_vert_lookahead(B, D, &C);
    A->loc = loc;
}

stub(A) ::= INDENT(tokL) exprs(B) DEDENT(tokR). { 
    A = B; 
    TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}
arg_stub(A) ::= INDENT(tokL) vert_arg_exprs(B) DEDENT(tokR). { 
    A = B; 
    ARG_TRACK_TT(A, tokL, tokR);
    RM_TOKEN(tokL);
    RM_TOKEN(tokR);
}

vert_arg_exprs(A) ::= vert_arg_expr(B). {
    A = astds_empty_arguments();
    astmisc_args_prepend(B, &A);
    A.loc = B.loc;
}
vert_arg_exprs(A) ::= vert_arg_expr(B) vert_arg_exprs(C). {
    astmisc_check_arg_order(B, C, parser_result);
    astmisc_args_prepend(B, &C);
    A = C;
    ARG_TRACK_AA(A, B, C);
}

vert_arg_expr(A) ::= expr(B). {
    if(B->node_type == asttype_imd_arrow) {
        A = astmisc_onearg_pair_with_arrow_del(B);
    } else {
        A = astmisc_onearg_pos(B);
    }
    A.loc = B->loc;
}
vert_arg_expr(A) ::= STAR(tokL) normal_expr(B). { 
    A = astmisc_onearg_star(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
vert_arg_expr(A) ::= DSTAR(tokL) normal_expr(B). { 
    A = astmisc_onearg_dstar(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
vert_arg_expr(A) ::= AMP(tokL) normal_expr(B). { 
    A = astmisc_onearg_amp(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}
vert_arg_expr(A) ::= DAMP(tokL) normal_expr(B). { 
    A = astmisc_onearg_damp(B); 
    ARG_TRACK_TN(A, tokL, B);
    RM_TOKEN(tokL);
}

