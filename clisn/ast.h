#ifndef _AST_H
# define _AST_H 
/*
 * Abstract Syntax Tree(AST)
 */

/*
 * The definitions of several types of syntax node
 */

enum {
    asttype_trailer = 0,
    asttype_name,
    asttype_literal,
    asttype_binop,
    asttype_unop,
    asttype_assign,
    asttype_suite,
    asttype_xexpr,
    asttype_imd_inline_app, /* imd -> intermediate */
    asttype_imd_arrow, /* imd -> intermediate */
    asttype_count
};

typedef struct {
    int sline;
    int scol;
    int eline;
    int ecol;
} ASTLoc;

typedef struct {
    short tag;
    short node_type;
    ASTLoc loc;
} ASTHD;

typedef struct {
    unsigned int len;
    char *str; /* can be null. in this case, len is 0 */
} ASTDS_String;

typedef struct ASTDS_PosArg {
    ASTHD *param;
    struct ASTDS_PosArg *next;
} ASTDS_PosArg;

typedef struct ASTDS_KwdArg {
    ASTDS_String name;
    ASTHD *param;
    struct ASTDS_KwdArg *next;
} ASTDS_KwdArg;

typedef struct { 
    ASTLoc loc;
    ASTDS_PosArg *pargs;
    ASTDS_KwdArg *kargs;
    int has_star, has_dstar, has_amp, has_damp;
    ASTHD *star, *dstar, *amp, *damp;
} ASTDS_Arguments;

enum {
    trailer_attr,
    trailer_array,
    trailer_lrslice,
    trailer_lslice,
    trailer_rslice,
    trailer_noslice
};

typedef struct AST_Trailer {
    ASTHD hd;
    ASTHD *scope;
    int trailer_type;
    union {
        ASTDS_String attr;
        ASTHD *index_param;
        struct {
            ASTHD *left;
            ASTHD *right;
        } slice_indices;
    } as;
} AST_Trailer;

/* each of structures below is an intermediate. It cannot appear outside of module and only exists during parsing phase */
typedef struct { 
    ASTHD hd;
    ASTHD *scope;
    ASTDS_Arguments arg_info;
} AST_InlineApp;

typedef struct {
    ASTHD hd;
    ASTDS_String name;
    ASTHD *param;
} AST_Arrow;

typedef struct {
    ASTHD hd;
    ASTDS_String dstr;
} AST_Name;

enum {
    literal_string,
    literal_integer,
    literal_float,
    literal_null,
    literal_true,
    literal_false,
};

typedef struct {
    ASTHD hd;
    short literal_type;
    ASTDS_String dstr;
} AST_Literal;

typedef struct {
    ASTHD hd;
    ASTDS_String binop_str;
    ASTHD *lhs;
    ASTHD *rhs;
} AST_BinOp;

typedef struct {
    ASTHD hd;
    ASTDS_String unop_str;
    ASTHD *param;
} AST_UnOp;

enum {
    assign_normal,
    assign_def
};
enum {
    lvalue_name,
    lvalue_attr,
    lvalue_array
};

typedef struct {
    ASTHD hd;
    short assign_type;
    short lvalue_type;
    union {
        ASTDS_String name;
        struct {
            ASTHD *scope;
            ASTDS_String name;
        } attr;
        struct {
            ASTHD *scope;
            ASTHD *index;
        } array;
    } lvalue_as;
    ASTHD *param;
} AST_Assign;

typedef struct AST_Suite {
    ASTHD hd;
    int is_arrow;
    ASTDS_String arrow_lstring;
    ASTHD *param;
    struct AST_Suite *next;
} AST_Suite;


/*
 * # has_head_label == 0
 * # has_vert_suite == 0
 * fun(a, b, c=1, ...)
 * 
 * fun>
 *   a
 *   b
 *   c -> 1
 * 
 * # " == 0
 * # " == 1
 * fun(a, b, c, d = 1, e = "aa", *f, **g, &h, &&i):
 *   expr1
 *   expr2
 *   expr3
 *   A -> Aexpr1
 *   B -> Bexpr2
 *   ..
 *
 * OR
 *
 * fun>
 *   a
 *   b
 *   c
 *   d -> 1
 *   e -> "aa"
 *   *f
 *   **g
 *   &h
 *   &&i
 * --
 *   expr1
 *   expr2
 *   expr3
 *   A -> Aexpr1
 *   B -> Bexpr2
 *   ...
 *
 * OR
 * # syntactic sugar in which there are only a expression as vertical expression
 * fun(..): expr1
 *
 * OR
 * # (special case. syntactic sugar)
 * 
 * fun:
 *   expr1
 *   expr2
 *   ...
 *
 * # it is equal to 
 * # fun():
 * #   expr1
 * #   expr2
 * #   ...
 *
 * # " == 1
 * # " == 0
 * import math
 *
 * # " == 1
 * # " == 1
 *
 * def aa(x, y, z):
 *   ...
 * 
 * OR
 *
 * def sum(a, b, c): a + b + c
 *
 */
typedef struct {
    ASTHD hd;
    int has_head_label;
    int has_vert_suite;

    ASTDS_String head_label;
    ASTHD *head_expr;
    ASTDS_Arguments arg_info;
    ASTHD *vert_suite;
} AST_XExpr;

typedef struct {
    int is_lexer_error;
    char err_msg[1024];
    unsigned int err_msg_len;

    int lex_errcode;
    int parse_errcode;
} ASTParseError;

AST_Suite* reverse_suite(AST_Suite* suite);

ASTHD* ast_access_attr(ASTHD *scope, const char *str);
ASTHD* ast_access_array(ASTHD *scope, ASTHD *index_param);

ASTHD* ast_slice_lr(ASTHD *scope, ASTHD *left, ASTHD *right);
ASTHD* ast_slice_l(ASTHD *scope, ASTHD *left);
ASTHD* ast_slice_r(ASTHD *scope, ASTHD *right);
ASTHD* ast_slice_nolr(ASTHD *scope); // foo[:]

ASTHD* ast_name(const char *str);
ASTHD* ast_string_literal(const char *str);
ASTHD* ast_sliced_string_literal(const char *str, int start, int len);
void ast_string_literal_append(ASTHD *ast, char *str);
ASTHD* ast_integer_literal(const char *str);
ASTHD* ast_float_literal(const char *raw_str);
ASTHD* ast_null_literal();
ASTHD* ast_true_literal();
ASTHD* ast_false_literal();


ASTHD* ast_binop(const char *binop_str, ASTHD *lhs, ASTHD *rhs);
ASTHD* ast_unop(const char *unop_str, ASTHD *param);

ASTHD* ast_assign_name(short assign_type, ASTDS_String dstr, ASTHD *param);
ASTHD* ast_assign_attr(short assign_type, ASTHD *scope, ASTDS_String attr_dstr, ASTHD *param);
ASTHD* ast_assign_array(short assign_type, ASTHD *scope, ASTHD *index, ASTHD *param);

ASTHD* ast_suite_cons_normal(ASTHD *elem, ASTHD *dst);
ASTHD* ast_suite_cons_arrow_del(AST_Arrow *arrow, ASTHD *dst);

ASTHD* ast_xexpr_single(ASTHD *head_expr, ASTDS_Arguments argument,
                        ASTHD *vert_suite); 
ASTHD* ast_xexpr_double(const char *head_label_str, ASTHD *head_expr, ASTDS_Arguments argument,
                        ASTHD *vert_suite);

void ast_xexpr_set_vert_suite(AST_XExpr *xexpr, AST_Suite *vert_suite);

void ast_free(ASTHD *ast);

ASTDS_PosArg* astds_singlearg_cons(ASTHD *elem, ASTDS_PosArg* sarg);
ASTDS_KwdArg* astds_kwdarg_cons(ASTDS_String dstr, ASTHD *elem, ASTDS_KwdArg *karg);

void free_singlearg(ASTDS_PosArg* parg);
void free_kwdarg(ASTDS_KwdArg* karg);
void astds_free_arguments(ASTDS_Arguments *arguments);

ASTDS_Arguments astds_arguments(ASTDS_PosArg *pargs,
                                ASTDS_KwdArg *kargs,
                                ASTHD *star,
                                ASTHD *dstar,
                                ASTHD *amp,
                                ASTHD *damp);
ASTDS_Arguments astds_empty_arguments();
ASTHD* ast_inline_app(ASTHD *scope, ASTDS_Arguments arg_info);
ASTHD* ast_arrow(const char *str, ASTHD *param);
ASTHD* ast_arrow_with_literal_del(AST_Literal *literal, ASTHD *param);

void ast_shallow_remove(ASTHD *ast);

ASTDS_String make_dsstring(const char *str, int len);
ASTDS_String empty_dsstring();
int dsstring_empty(ASTDS_String *dstr);
void free_dsstring(ASTDS_String *dstr);
ASTDS_String dsstring_from_str(const char *str);
void dsstring_append(ASTDS_String *dstr, const char *src);

ASTDS_String astds_strip_del_name(ASTHD *name) ;
ASTDS_String astds_strip_del_literal(ASTHD *literal);

typedef void (* ast_visitor_fun)(ASTHD ** ast, void *arg);
void ast_visit(ASTHD **root, ast_visitor_fun visitor, void *arg);

void ast_dbg_print(ASTHD *root);
#endif //!defined(_AST_H)
