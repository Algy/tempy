%{
#include <stdio.h>
#include <stdlib.h> 
#include <string.h>

#define YYERROR -1
#define YYEOF -2
#define YYNOTHING -3

#define TRACK_COL() { \
    (yyextra)->ed_colno = (yyextra)->colno + yyleng; \
    (yyextra)->ed_lineno = (yyextra)->lineno; \
}
#define ADD_LINE() { \
    (yyextra)->ed_colno = 1; \
    (yyextra)->ed_lineno = (yyextra)->lineno + 1; \
}

#define TRACK_LINE_COL(line, col) { \
    (yyextra)->ed_colno = (col); \
    (yyextra)->ed_lineno = (yyextra)->lineno + (line); \
}

#include "lexer.h"
#include "ast-make.h"

static void init_lexer_context(struct LexerContext *ctx) {
    ctx->ind_stack_size = 1;
    ctx->ind_stack[0] = 0;
    ctx->bracket_depth = 0;
    ctx->end_with_newline = 0;
    ctx->dedents = 0;

    ctx->error_occured = 0;
    memset(ctx->last_error_msg, 0, LEXERR_MAX_STRING_CNT);
    ctx->lineno = 1;
    ctx->colno = 1;
    ctx->ed_lineno = 1;
    ctx->ed_colno = 1;
}

static void remove_lexer_context(struct LexerContext *ctx) {
}

static inline void format_char(const char ch, char *dest) {
    if(ch == '\n' || (ch >= ' ' && ch <= '~')) {
        dest[0] = ch;
        dest[1] = 0;
    } else {
        int h, l;
        h = (unsigned char)ch / 16;
        l = (unsigned char)ch % 16;
        dest[0] = '\\';
        dest[1] = (h >= 10)? (h - 10) + 'a': h + '0';
        dest[2] = (l >= 10)? (l - 10) + 'a': l + '0';
        dest[3] = 0;
    }
}


static int ind_stack_pop(struct LexerContext *ctx);
static int ind_stack_peek(struct LexerContext *ctx);
static void ind_stack_push(struct LexerContext *ctx, int);
static int ind_stack_empty(struct LexerContext *ctx);


static void error(struct LexerContext *ctx, int err_code, char *err_msg) {
    ctx->error_occured = 1;
    strncpy(ctx->last_error_msg, err_msg, LEXERR_MAX_STRING_CNT - 1);
    ctx->last_error_code = err_code;
}
static void flush_ind_stack(struct LexerContext *ctx) {
    int t;

    t = ind_stack_peek(ctx);
    while(t > 0) {
        ind_stack_pop(ctx);
        t = ind_stack_peek(ctx);
        ctx->dedents++;
    }
}


%}

space [ \t]

letter [$a-zA-Z_]
exletter [$a-zA-Z0-9_!?]
digit [0-9]

%x NEWLINEPHASE
%s BRACKETPHASE
%option reentrant
%option noyywrap
%option extra-type="struct LexerContext *"

%%
<NEWLINEPHASE><<EOF>> {
    flush_ind_stack(yyextra);
    return YYEOF;
}


<BRACKETPHASE><<EOF>> {
    error(yyextra, LEXERR_BRACKET_MISMATCH, "Closing bracket not found");
    return YYERROR;
}
<INITIAL><<EOF>> {
    yyextra->end_with_newline = 1; // HACK
    flush_ind_stack(yyextra);
    return YYEOF;
}

<NEWLINEPHASE>^{space}*\r?\n {
    ADD_LINE();
    return YYNOTHING;
}

<NEWLINEPHASE>^{space}+ {
    int t;

    TRACK_COL();

    t = ind_stack_peek(yyextra);
    if(ind_stack_empty(yyextra)) {
        error(yyextra, LEXERR_FATAL_ERROR, "FATAL INDENT ERROR");
        return YYERROR;
    }

    BEGIN(INITIAL);
    if(t < yyleng) {
        ind_stack_push(yyextra, yyleng);
        if(yyextra->error_occured)
            return YYERROR;
        else
            return INDENT;
    } else if(t > yyleng) {
        while(t > yyleng) {
            ind_stack_pop(yyextra);
            t = ind_stack_peek(yyextra);
            yyextra->dedents++;
        }

        if(t != yyleng) {
            error(yyextra, LEXERR_INDENT_MISMATCH, "Indentation level mismatch");
            return YYERROR;
        }
    }
    return YYNOTHING;
}

<NEWLINEPHASE>^""/. {
    // This rule should meet only if this line is at zero-indentation level
    BEGIN(INITIAL);
    flush_ind_stack(yyextra);
    return YYNOTHING;
}

<BRACKETPHASE>\r?\n { ADD_LINE(); return YYNOTHING; }
<BRACKETPHASE>{space}+ { TRACK_COL(); return YYNOTHING; }

<INITIAL>\r?\n {
    BEGIN(NEWLINEPHASE);
    ADD_LINE();
    return NEWLINE;
}

{space}+ { TRACK_COL(); return YYNOTHING; }
"#".*$  { TRACK_COL(); return YYNOTHING; } // inline-comment

<INITIAL>":"{space}*\r?\n {
    ADD_LINE();
    BEGIN(NEWLINEPHASE); 
    return COLUMN_NEWLINE;
}

<INITIAL>">"{space}*\r?\n {
    ADD_LINE();
    BEGIN(NEWLINEPHASE); 
    return GT_NEWLINE;
}

<INITIAL>"--"{space}*\r?\n {
    ADD_LINE(); 
    BEGIN(NEWLINEPHASE);
    return DMINUS_NEWLINE;
}

":" {TRACK_COL(); return COLUMN; }
"\." {TRACK_COL(); return DOT;}
"," {TRACK_COL(); return COMMA;}
"\+" {TRACK_COL(); return PLUS;}
"-" {TRACK_COL(); return MINUS;}
"\*" {TRACK_COL(); return STAR;}
"\*\*"  {TRACK_COL(); return DSTAR;}
"/" {TRACK_COL(); return SLASH;}
"%" {TRACK_COL(); return PERCENT;}
"!" {TRACK_COL(); return BANG;}

"&" {TRACK_COL(); return AMP;}
"\|" {TRACK_COL(); return PIPE;}
"&&" {TRACK_COL(); return DAMP;}
"\|\|" {TRACK_COL(); return DPIPE;}

":=" {TRACK_COL(); return DEFASSIGN;}
"=" {TRACK_COL(); return ASSIGN;}

"->" {TRACK_COL(); return ARROW;}

">" {TRACK_COL(); return GT;}
"<" {TRACK_COL(); return LT;}
"<=" {TRACK_COL(); return LTE;}
">=" {TRACK_COL(); return GTE;}
"==" {TRACK_COL(); return EQ;}
"!=" {TRACK_COL(); return NEQ;}

<INITIAL>"\\"\r?\n{space}* {
    int col;
    char *p;
    p = strstr(yytext, "\n");
    if(p) {
        p++;
        col = strlen(p) + 1;
    } else {
        col = 1;
    }
    TRACK_LINE_COL(1, col);
    return YYNOTHING;
}

<INITIAL>"\\"\<<EOF>> {
    TRACK_COL();
    return YYEOF;
}

<INITIAL>"\\". {
    TRACK_COL();
    error(yyextra, LEXERR_INVALID_AFTER_BACKSLASH, "Unexpected character after line continuation character");
    return YYERROR;
}


"[" {
    TRACK_COL();
    yyextra->bracket_depth++;
    BEGIN(BRACKETPHASE);
    return LBRKT;
}

"]" {
    TRACK_COL();
    if(yyextra->bracket_depth == 0) {
        error(yyextra, LEXERR_BRACKET_MISMATCH, "Openning bracket not found");
        return YYERROR;
    }
    else {
        if(--yyextra->bracket_depth == 0) {
            BEGIN(INITIAL);
        }
        return RBRKT;
    }
}

"(" {
    TRACK_COL();
    yyextra->bracket_depth++;
    BEGIN(BRACKETPHASE);
    return LPAR;
}
")" {
    TRACK_COL();
    if(yyextra->bracket_depth == 0) {
        error(yyextra, LEXERR_BRACKET_MISMATCH, "Openning bracket not found");
        return YYERROR;
    }
    else {
        if(--yyextra->bracket_depth == 0) {
            BEGIN(INITIAL);
        }
        return RPAR;
    }
}

{digit}*"\."{digit}+ {
    TRACK_COL();
   return FLOAT;
} 

{digit}+"\." {
    TRACK_COL();
   return FLOAT;
}

{digit}+ {
    TRACK_COL();
   return INTEGER;
}

{letter}{exletter}* {
    TRACK_COL();
    return NAME;
}

"\""[^"]*"\"" {
    TRACK_COL();
    return STRING;
}
"\'"[^']*"\'" {
    TRACK_COL();
    return STRING;
}

"\'\'\'"(.|\r?\n)*"\'\'\'" {
    // XXX: something wrong with tracking long string...
    // e.g '''aabb''' '''ccdd''' => String("aabb\'\'\' \'\'\'ccdd")
    char *p, *next;
    int n;
    p = strstr(yytext, "\n");

    if(p) {
        n = 0;
        p++;
        while(1) {
            n++;
            next = strstr(p, "\n");
            if(next)
                p = next + 1;
            else
                break;
        }
        TRACK_LINE_COL(n, strlen(p) + 1);
    } else {
        TRACK_COL();
    }

    return LONGSTRING;
}
"\"\"\""(.|\r?\n)*"\"\"\"" {
    char *p, *next;
    int n;
    p = strstr(yytext, "\n");

    if(p) {
        n = 0;
        p++;
        while(1) {
            n++;
            next = strstr(p, "\n");
            if(next)
                p = next + 1;
            else
                break;
        }
        TRACK_LINE_COL(n, strlen(p) + 1);
    } else {
        TRACK_COL();
    }
    return LONGSTRING;
}


. {
    TRACK_COL();
    char fmt[4];
    char msg[128];
    format_char(yytext[0], fmt);
    snprintf(msg, 128, "Invalid character: %s", fmt);
    error(yyextra, LEXERR_INVALID_CHARACTER, msg);
    return YYERROR;
}

%%

int ind_stack_peek(struct LexerContext *ctx) {
    if(ctx->ind_stack_size > 0) {
        return ctx->ind_stack[ctx->ind_stack_size-1];
    }
    return 0;
}
static int ind_stack_pop(struct LexerContext *ctx) {
    int t;
    if(ctx->ind_stack_size > 0)  {
        t = ctx->ind_stack[--ctx->ind_stack_size];
        return t;
    }
    else
        return 0;
}

static void ind_stack_push(struct LexerContext *ctx, int ind) {
    if(ctx->ind_stack_size < YY_MAX_STACK_SIZE)
        ctx->ind_stack[ctx->ind_stack_size++] = ind;
    else 
        error(ctx, LEXERR_INDENT_STACK_OVERFLOW, "Indentation stack overflow");
}

static int ind_stack_empty(struct LexerContext *ctx) {
    return (ctx->ind_stack_size == 0);
}

static void lexer_set_default(Lexer *lexer, short tag) {
    init_lexer_context(&lexer->lexer_ctx);
    lexer->tag = tag;
    lexer->remaining_dedents = 0;
    lexer->is_end = 0;

    yylex_init_extra(&lexer->lexer_ctx, (yyscan_t *)&lexer->scanner);
}

void init_lexer_with_file(Lexer *lexer, short tag, FILE *f) {
    lexer_set_default(lexer, tag);
    yyset_in(f, (yyscan_t)lexer->scanner);
}

void init_lexer_with_bytes(Lexer *lexer, short tag, const char* bytes, int len) {
    lexer_set_default(lexer, tag);
    yy_scan_bytes(bytes, len, (yyscan_t)lexer->scanner);
}

static void pop_dedents(Lexer *lexer) {
    lexer->remaining_dedents += lexer->lexer_ctx.dedents;
    lexer->lexer_ctx.dedents = 0;
}

static int lex_once(Lexer *lexer, int *call_it_again) {
    int result;

    *call_it_again = 0;
    if(lexer->remaining_dedents > 0) {
        lexer->remaining_dedents--;
        return DEDENT;
    } else if(lexer->is_end) {
        return 0;
    }
    result = yylex(lexer->scanner);
    switch(result) {
        case YYNOTHING:
            *call_it_again = 1;
            break;
        case YYEOF:
            lexer->is_end = 1;

            if(lexer->lexer_ctx.end_with_newline) {
                result = NEWLINE;
            } else {
                result = YYNOTHING;
                *call_it_again = 1;
            } 
            break;
    }
    pop_dedents(lexer);
    return result;
}

LexToken* lexer_lex(Lexer *lexer, LexError *lexerr) {
    LexToken *ret;
    int token;
    int lex_again;
    int sline, eline, scol, ecol;
    
    do {
        sline = lexer->lexer_ctx.lineno;
        scol = lexer->lexer_ctx.colno;

        token = lex_once(lexer, &lex_again);

        eline = lexer->lexer_ctx.ed_lineno;
        ecol = lexer->lexer_ctx.ed_colno;

        lexer->lexer_ctx.lineno = lexer->lexer_ctx.ed_lineno;
        lexer->lexer_ctx.colno = lexer->lexer_ctx.ed_colno;
    } while(lex_again);

    if(token == 0) {
        return NULL;
    }

    char *src_text, *copied_text;
    unsigned int text_len;

    src_text = yyget_text((yyscan_t)lexer->scanner);
    text_len = (unsigned int)yyget_leng((yyscan_t)lexer->scanner);
    copied_text = (char *)malloc(text_len + 1);
    strcpy(copied_text, src_text);

    ret = (LexToken *)malloc(sizeof(LexToken));
    ret->token = token;
    ret->text = copied_text;
    ret->text_len = text_len;
    ret->sline = sline;
    ret->eline = eline;
    ret->scol = scol;
    ret->ecol = ecol;

    if(token != YYERROR) {
        ret->error_occured = 0;
    } else {
        ret->error_occured = 1;
        lexerr->code = lexer->lexer_ctx.last_error_code;
        strncpy(lexerr->msg, lexer->lexer_ctx.last_error_msg, LEXERR_MAX_STRING_CNT - 1);
    }

    return ret;
}

int lexer_current_line(Lexer *lexer) {
    return lexer->lexer_ctx.lineno;
}

int lexer_current_col(Lexer *lexer) {
    return lexer->lexer_ctx.colno;
}

void lexer_remove_token(LexToken *tok) {
    free(tok->text);
    free(tok);
}

void remove_lexer(Lexer *lexer) {
    remove_lexer_context(&lexer->lexer_ctx);
    // Internel buffer is automatically removed in this function.
    yylex_destroy(lexer->scanner);
}
