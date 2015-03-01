#include <stdlib.h>
#include <string.h>

#include "ast.h"
#include "astmisc.h"
#include "ast-make.h"
#include "parser.h"

#ifdef _BENCHMARK
# include <sys/time.h>
#endif

#ifdef _DBG_VERBOSE
# define DBG_LOG printf
#endif



void *LEMONParseAlloc(void *(*mallocProc)(size_t));
void LEMONParseFree(
  void *p,                    /* The parser to be deleted */
  void (*freeProc)(void*)     /* Function used to reclaim memory */
);
void LEMONParse(
  void *yyp,                   /* The parser */
  int yymajor,                 /* The major token code number */
  LexToken *yyminor,
  ParseResult* parser_result
);


static void suite_reverser(ASTHD **ast, void *arg) {
    ASTHD *reversed;
    ASTLoc saved_loc;
    AST_Suite *p;
    switch((*ast)->node_type) {
        case asttype_suite:
            saved_loc = (*ast)->loc; // preserve location information
            reversed = &reverse_suite((AST_Suite *)(*ast))->hd;
            reversed->loc = saved_loc; // restore loc info
            // make suites' loc info meaningless except for head suite chain
            for (p = ((AST_Suite *)reversed)->next; p; p = p->next) {
                p->hd.loc.sline = -1;
                p->hd.loc.eline = -1;
                p->hd.loc.scol = -1;
                p->hd.loc.ecol = -1;
            }
            *ast = reversed;
            break;
    }
}

static ASTHD* do_parse(Lexer* lexer, LexParseError *err_out) {
    LexToken *lextok;
    LexError lexerr;
    ParseResult parseres;
    void *parser;
    int success;

    int token;
    char *text;
    int tok_sline, tok_eline, tok_scol, tok_ecol;
    
#ifdef _BENCHMARK
    struct timeval st, ed;
    gettimeofday(&st, NULL);
#endif 

    err_out->error_occurred = 0;

    parser = LEMONParseAlloc(malloc);
    init_parse_result(&parseres);

    success = 1;
    do {
        lextok = Lexer_lex(lexer, &lexerr);
        if(!lextok) { // EOF
            token = 0;
            text = NULL;
            tok_sline = tok_eline = Lexer_current_line(lexer);
            tok_scol = tok_ecol = Lexer_current_col(lexer);
#ifdef _DBG_VERBOSE
            DBG_LOG("feeding(EOF):<<EOF>>\n");
#endif
        } else {
            int line, col;
            token = lextok->token;
            text = lextok->text;
            tok_sline = lextok->sline;
            tok_eline = lextok->eline;
            tok_scol = lextok->scol;
            tok_ecol = lextok->ecol;
#ifdef _DBG_VERBOSE
            DBG_LOG("feeding(%d)[line:%d~%d, col:%d~%d]:%s\n",
                     token,
                     lextok->sline, lextok->eline,
                     lextok->scol, lextok->ecol - 1,
                     text);
#endif
        }
        if(lextok && lextok->error_occurred) {
            err_out->error_occurred = 1;
            err_out->is_lexerr = 1;
            err_out->err_code = lexerr.code;
            err_out->sline = tok_sline;
            err_out->eline = tok_eline;
            err_out->scol = tok_scol;
            err_out->ecol = tok_ecol;
            strncpy(err_out->err_msg, lexerr.msg, MAX_LEX_PARSE_ERROR_MSG);
            success = 0;

            // Parser is supposed to free tokens which are fed to itself. 
            // But, here is not the case, freeing lextok is our duty here
            // because the token is not fed to parser yet.
            Lexer_remove_token(lextok); 
            break;
        }
        LEMONParse(parser, token, lextok, &parseres);
        if(parseres.error_occurred) {
            err_out->error_occurred = 1;
            err_out->is_lexerr = 0;
            err_out->err_code = parseres.err_code;
            err_out->sline = tok_sline;
            err_out->eline = tok_eline;
            err_out->scol = tok_scol;
            err_out->ecol = tok_ecol;
            strncpy(err_out->err_msg, parseres.err_msg, MAX_LEX_PARSE_ERROR_MSG);
            success = 0;
            break;
        }
    } while (token);
    /*
     * Post processings
     */
    if(success) {
        ast_visit(&parseres.result_ast, suite_reverser, NULL);
        // Change all intermediates to complete syntax form
        astmisc_convert_all_inline_app(&parseres.result_ast);
    } else {
        remove_parse_result(&parseres, 1);
    }
    LEMONParseFree(parser, free);

#ifdef _BENCHMARK
    gettimeofday(&ed, NULL);
    printf("Time Elapsed: %lfus\n", (ed.tv_sec - st.tv_sec) / 1000000.0 + (ed.tv_usec - st.tv_usec));
#endif
    return parseres.result_ast;
}

ASTHD* parse_file(FILE *f, LexParseError *err_out) {
    Lexer *lexer;
    ASTHD *ret;

    lexer = Lexer_init_with_file(f);
    ret = do_parse(lexer, err_out);
    Lexer_remove(lexer);

    return ret;
}


ASTHD* parse_bytes(const char *bytes, int len, LexParseError *err_out) {
    Lexer *lexer;
    ASTHD *ret;

    lexer = Lexer_init_with_bytes(bytes, len);
    ret = do_parse(lexer, err_out);
    Lexer_remove(lexer);

    return ret;
}
