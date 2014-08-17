#include <stdio.h>

#define YY_MAX_STACK_SIZE 1024
#define LEXERR_MAX_STRING_CNT 128


typedef struct LexerContext {
    int ind_stack[YY_MAX_STACK_SIZE];
    int ind_stack_size;
    int bracket_depth;

    int end_with_newline;
    int dedents;

    int error_occured;
    char last_error_msg[LEXERR_MAX_STRING_CNT];
    int last_error_code;

    int lineno, colno;
    int ed_lineno, ed_colno; // ed_lineno is inclusive while ed_colno is exclusive.

} LexerContext;

typedef struct Lexer {
    short tag;
    int remaining_dedents;
    void *scanner;
    int is_end;
    LexerContext lexer_ctx;
} Lexer;

#define LEXERR_FATAL_ERROR 1
#define LEXERR_BRACKET_MISMATCH 2
#define LEXERR_INVALID_CHARACTER 3
#define LEXERR_INDENT_MISMATCH 4
#define LEXERR_INDENT_STACK_OVERFLOW 5
#define LEXERR_INVALID_AFTER_BACKSLASH 6

typedef struct LexError {
    int code;
    char msg[LEXERR_MAX_STRING_CNT];
} LexError;

typedef struct LexToken {
    int error_occured;
    int token;
    char *text;
    unsigned int text_len;

    int sline, eline;
    int scol, ecol;
} LexToken;

void init_lexer_with_file(Lexer *lexer, short tag, FILE *file);
void init_lexer_with_bytes(Lexer *lexer, short tag, const char* bytes, int len);
LexToken* lexer_lex(Lexer *lexer, LexError *lexerr);
void lexer_remove_token(LexToken *);
int lexer_current_line(Lexer *lexer);
int lexer_current_col(Lexer *lexer);
void remove_lexer(Lexer *lexer);
