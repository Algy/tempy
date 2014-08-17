#include "ast.h"
#define PARSE_MAX_ERR_MSG_CNT 1024 
#define PARSE_ERR_OK 0
#define PARSE_ERR_SYNTAX_ERROR 1
#define PARSE_ERR_STACK_OVERFLOW 2
#define PARSE_ERR_ILLEGAL_ARG 3
#define PARSE_ERR_ILLEGAL_LVALUE 4

#ifndef NULL
# define NULL ((void *) 0)
#endif

#define MERGE_ASTLOC(A, B, C) { \
    (A).sline = (B).sline; \
    (A).scol = (B).scol; \
    (A).eline = (C).eline; \
    (A).ecol = (C).ecol; \
}

#define TRACK_N(DST, SRC) { \
    DST->loc = SRC->loc; \
}

#define TRACK_T(DST, TOK) { \
    DST->loc.sline = TOK->sline; \
    DST->loc.scol = TOK->scol; \
    DST->loc.eline = TOK->eline; \
    DST->loc.ecol = TOK->ecol; \
}

#define TRACK_TT(DST, TOKL, TOKR) { \
    MERGE_ASTLOC(DST->loc, *TOKL, *TOKR); \
}

#define TRACK_TN(DST, TOKL, NODER) { \
    ASTLoc rloc; \
    rloc = NODER->loc; \
    MERGE_ASTLOC(DST->loc, *TOKL, rloc); \
}

#define TRACK_NT(DST, NODEL, TOKR) { \
    ASTLoc lloc; \
    lloc = NODEL->loc; \
    MERGE_ASTLOC(DST->loc, lloc, *TOKR); \
}

#define TRACK_NA(DST, NODEL, ARGR) { \
    ASTLoc lloc; \
    lloc = NODEL->loc; \
    MERGE_ASTLOC(DST->loc, lloc, ARGR.loc); \
}
#define ARG_TRACK_TT(DST, TOKL, TOKR) { \
    MERGE_ASTLOC(DST.loc, *TOKL, *TOKR); \
}

#define ARG_TRACK_N(DST, NODE) { \
    DST.loc = NODE->loc; \
}

#define ARG_TRACK_TN(DST, TOKL, NODER) { \
    ASTLoc rloc; \
    rloc = NODER->loc; \
    MERGE_ASTLOC(DST.loc, *TOKL, rloc); \
}

#define TRACK_NN(DST, NODEL, NODER) { \
    ASTLoc lloc, rloc; \
    lloc = NODEL->loc; \
    rloc = NODER->loc; \
    MERGE_ASTLOC(DST->loc, lloc, rloc); \
}

#define ARG_TRACK_NN(DST, NODEL, NODER) { \
    ASTLoc lloc, rloc; \
    lloc = NODEL->loc; \
    rloc = NODER->loc; \
    MERGE_ASTLOC(DST.loc, lloc, rloc); \
}

#define ARG_TRACK_AA(DST, ARGL, ARGR) { \
    ASTLoc lloc, rloc; \
    lloc = ARGL.loc; \
    rloc = ARGR.loc; \
    MERGE_ASTLOC(DST.loc, lloc, rloc); \
}

typedef struct {
    int error_occured;
    char err_msg[PARSE_MAX_ERR_MSG_CNT];
    int err_code;

    /* this field may not be NULL even if error occured. In that case, user should release it manually. */
    ASTHD *result_ast;
} ParseResult;

void init_parse_result(ParseResult *pres);
void pres_set_error(ParseResult *pres, int err_code, const char *err_msg);
void remove_parse_result(ParseResult *pres, int remove_ast);


ASTHD *astmisc_vert_lookahead(ASTHD* scope, ASTHD *vert_suite, ASTDS_Arguments *p_args);
ASTHD* astmisc_dexpr_lookahead(ASTHD *scope, char *head_name, ASTHD *vert_suite);
ASTHD *astmisc_trailer_set_leaf_scope(ASTHD* trailers, ASTHD *leaf_scope);

enum {
    onearg_pos,
    onearg_pair,
    onearg_star,
    onearg_dstar,
    onearg_amp,
    onearg_damp
};
typedef struct {
    int type;
    // an  empty string unless the type is onearg_pair
    ASTDS_String name; 
    ASTHD *value;
    ASTLoc loc;
} ASTMISC_OneArg;

ASTMISC_OneArg astmisc_onearg_pos(ASTHD *);
ASTMISC_OneArg astmisc_onearg_pair(const char *str, ASTHD *value);
ASTMISC_OneArg astmisc_onearg_pair_with_literal_del(ASTHD *literal, ASTHD *value);
ASTMISC_OneArg astmisc_onearg_pair_with_arrow_del(ASTHD *arrow);
ASTMISC_OneArg astmisc_onearg_star(ASTHD *);
ASTMISC_OneArg astmisc_onearg_dstar(ASTHD *);
ASTMISC_OneArg astmisc_onearg_amp(ASTHD *);
ASTMISC_OneArg astmisc_onearg_damp(ASTHD *);
void astmisc_remove_onearg(ASTMISC_OneArg *oarg);

void astmisc_check_arg_order(ASTMISC_OneArg, ASTDS_Arguments, ParseResult *);
ASTHD* astmisc_make_assign(short assign_type, ASTHD *lvalue, ASTHD *param, ParseResult *);

void astmisc_args_prepend(ASTMISC_OneArg, ASTDS_Arguments *);

ASTHD *convert_inline_app_to_xexpr(ASTHD *ast);
void astmisc_convert_all_inline_app(ASTHD **ast);
