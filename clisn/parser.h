#include <stdio.h>
#include "ast.h"
#include "lexer.h"

#define MAX_LEX_PARSE_ERROR_MSG 1024
typedef struct {
    int error_occurred;
    int is_lexerr;
    int err_code;
    char err_msg[MAX_LEX_PARSE_ERROR_MSG];
    int sline, eline, scol, ecol;
} LexParseError;

ASTHD* parse_file(FILE *f, LexParseError *err_out);
ASTHD* parse_bytes(const char *bytes, int len, LexParseError *err_out);
