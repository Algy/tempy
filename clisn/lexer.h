#include <stdio.h>

#define YY_MAX_STACK_SIZE 1024
#define LEXERR_MAX_STRING_CNT 128

#define LEXERR_NO_PROBLEM 0
#define LEXERR_FATAL_ERROR 1
#define LEXERR_BRACKET_MISMATCH 2
#define LEXERR_INVALID_CHARACTER 3
#define LEXERR_INDENT_MISMATCH 4
#define LEXERR_INDENT_STACK_OVERFLOW 5
#define LEXERR_INVALID_AFTER_BACKSLASH 6
#define LEXERR_BAD_STREAM 7
#define LEXERR_MIXED_SPACES_AND_TABS 8
#define LEXERR_EOF_IN_STRING 9
#define LEXERR_INVALID_HEX_ESCAPE 10

typedef struct Lexer Lexer;

typedef struct LexError {
    int code;
    char msg[LEXERR_MAX_STRING_CNT];
} LexError;

typedef struct LexToken {
    int error_occurred;
    int token;
    char *text;
    unsigned int text_len;

    int sline, eline;
    int scol, ecol;
} LexToken;

Lexer* Lexer_init_with_file(FILE *file);
Lexer* Lexer_init_with_bytes(const char* bytes, int len);
LexToken* Lexer_lex(Lexer *lexer, LexError *lexerr);
void Lexer_last_error(LexError *err);

void Lexer_remove_token(LexToken *);
int Lexer_current_line(Lexer *lexer);
int Lexer_current_col(Lexer *lexer);
void Lexer_remove(Lexer *lexer);
