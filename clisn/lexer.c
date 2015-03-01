#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "lexer.h"
#include "ast-make.h"

typedef struct {
    int is_file; // whether source is file or string
    union {
        FILE *file;
        struct {
            int idx;
            int len;
            const char *buffer;
        } string;
    } as;
    int curline;
    int curcol;

    int is_recording;
    char *recording_buf;
    int recording_len;
    int recording_size;
} Stream;


static inline void Stream_init_with_file(Stream* stream, FILE *file) {
    stream->is_file = 1;
    stream->curline = 1;
    stream->curcol = 1;

    stream->recording_buf = NULL;
    stream->is_recording = 0;
    stream->recording_len = 0;

    stream->as.file = file;
}

static inline void Stream_init_with_buffer(Stream* stream, const char* buffer, int len) {
    stream->is_file = 0;
    stream->curline = 1;
    stream->curcol = 1;

    stream->recording_buf = NULL;
    stream->is_recording = 0;
    stream->recording_len = 0;

    stream->as.string.idx = 0;
    stream->as.string.len = len;
    stream->as.string.buffer = buffer;
}

static inline void Stream_remove(Stream* stream) {
    if (stream->recording_buf) {
        free(stream->recording_buf);
    }
}

#define INITIAL_RECORDING_BUFFER_SIZE 16
static inline void Stream_start_record(Stream* stream) {
    if (stream->recording_buf) {
        free(stream->recording_buf);
    }

    stream->is_recording = 1;
    stream->recording_size = INITIAL_RECORDING_BUFFER_SIZE;
    stream->recording_buf = calloc(stream->recording_size, sizeof(char));
    stream->recording_len = 0;
}

static inline char* Stream_end_record(Stream* stream) {
    char* result = stream->recording_buf;

    stream->is_recording = 0;
    stream->recording_size = 0;
    stream->recording_buf = NULL;
    stream->recording_len = 0;
    return result;
}

static inline void Stream_clear_record(Stream* stream) {
    stream->recording_len = 0;
    if (stream->recording_buf) {
        stream->recording_buf[0] = 0;
    }
}
/*
 *
 * \\   Backslash (\)
 * \'   Single quote (')
 * \"   Double quote (")
 * \a   ASCII Bell (BEL)
 * \b   ASCII Backspace (BS)
 * \f   ASCII Formfeed (FF)
 * \n   ASCII Linefeed (LF)
 * \r   ASCII Carriage Return (CR)
 * \t   ASCII Horizontal Tab (TAB)
 * \v   ASCII Vertical Tab (VT)
 * \ooo ASCII character with octal value ooo
 * \xhh...  ASCII character with hex value hh...
 */

static inline void Stream_replace_record(Stream* stream, int pop_cnt, char* push_str, int push_strlen)  {
    if (stream->recording_len < pop_cnt) {
        stream->recording_len = 0;
    } else {
        stream->recording_len -= pop_cnt;
    }

    if (stream->recording_buf) {
        if (stream->recording_len + push_strlen + 1 >= stream->recording_size) {
            while (stream->recording_len + push_strlen + 1 >= stream->recording_size) {
                stream->recording_size *= 2;
            }
            stream->recording_buf = realloc(stream->recording_buf, sizeof(char) * stream->recording_size);
        }
        char *p = stream->recording_buf;
        int i;
        for (i = 0; i < push_strlen; i++) {
            p[stream->recording_len++] = push_str[i];
        }
        p[stream->recording_len] = 0;
    }
}


#define CHAR_EOF -1
#define CHAR_ERROR -2

static inline int Stream_pop(Stream* stream) {
    int result;
    if (stream->is_file) {
        result = fgetc(stream->as.file);
        if (result == EOF) {
            if (feof(stream->as.file))
                return CHAR_EOF;
            else
                return CHAR_ERROR;
        } 
    } else {
        if (stream->as.string.idx >= stream->as.string.len)
            return CHAR_EOF;
        result = stream->as.string.buffer[stream->as.string.idx++];
    }
    if (result == '\n') {
        stream->curline++;
        stream->curcol = 1;
    } else {
        stream->curcol++;
    }

    if (stream->is_recording) {
        if (stream->recording_len + 1 >= stream->recording_size) {
            stream->recording_size *= 2;
            stream->recording_buf = realloc(stream->recording_buf, sizeof(char) * stream->recording_size);
        }
        stream->recording_buf[stream->recording_len++] = (char)result;
        stream->recording_buf[stream->recording_len] = 0;
    }
    return result;
}

static inline int Stream_peek(Stream* stream) {
    int result;
    if (stream->is_file) {
        result = fgetc(stream->as.file);
        ungetc(result, stream->as.file);
        if (result == EOF) {
            if (feof(stream->as.file))
                return CHAR_EOF;
            else
                return CHAR_ERROR;
        }
    } else {
        if (stream->as.string.idx >= stream->as.string.len)
            return CHAR_EOF;
        result = stream->as.string.buffer[stream->as.string.idx];
    }
    return result;
}

static inline int Stream_eof(Stream* stream) {
    if (stream->is_file) {
        return feof(stream->as.file);
    } else {
        return stream->as.string.idx >= stream->as.string.len;
    }
}


typedef struct Lexer {
    int is_newline_phase;
    int is_end;

    int unscanned_dedents;
    Stream stream;

    int error_occurred;
    int ind_stack[YY_MAX_STACK_SIZE];
    int ind_stack_len;

    int bracket_depth;
    char last_error_msg[LEXERR_MAX_STRING_CNT];
    int last_error_code;

    char repr_indent_char;
} Lexer;

static inline Lexer* init_lexer() {
    Lexer *lexer = (Lexer *)malloc(sizeof(Lexer));
    // set up indent stack
    lexer->ind_stack[0] = 0;
    lexer->ind_stack_len = 1;

    // set up bracket depth info
    lexer->bracket_depth = 0;

    lexer->error_occurred = 0;
    lexer->unscanned_dedents = 0;
    lexer->last_error_code = LEXERR_NO_PROBLEM;
    lexer->last_error_msg[0] = 0;

    lexer->repr_indent_char = 0;
    lexer->is_newline_phase = 0;
    lexer->is_end = 0;
    return lexer;
}

Lexer* Lexer_init_with_file(FILE *file) {
    Lexer* lexer = init_lexer();
    Stream_init_with_file(&lexer->stream, file);
    return lexer;
}

Lexer* Lexer_init_with_bytes(const char* bytes, int len) {
    Lexer* lexer = init_lexer();
    Stream_init_with_buffer(&lexer->stream, bytes, len);
    return lexer;
}

static void error(Lexer *lexer, int err_code, char *err_msg) {
    lexer->error_occurred = 1;
    strncpy(lexer->last_error_msg, err_msg, LEXERR_MAX_STRING_CNT - 1);
    lexer->last_error_code = err_code;
}

static inline int ind_stack_pop(Lexer *lexer) {
    int t;
    if(lexer->ind_stack_len > 0)  {
        t = lexer->ind_stack[--lexer->ind_stack_len];
        return t;
    }
    else
        return 0;
}

static inline int ind_stack_peek(Lexer *lexer) {
    if(lexer->ind_stack_len > 0) {
        return lexer->ind_stack[lexer->ind_stack_len - 1];
    }
    return 0;
}

static inline void ind_stack_push(Lexer *lexer, int ind_level) {
    if(lexer->ind_stack_len < YY_MAX_STACK_SIZE) {
        lexer->ind_stack[lexer->ind_stack_len++] = ind_level;
    } else {
        error(lexer, LEXERR_INDENT_STACK_OVERFLOW, "Indentation stack overflow");
    }
}

static inline int ind_stack_empty(Lexer *lexer) {
    return (lexer->ind_stack_len == 0);
}

static void flush_ind_stack(Lexer *lexer) {
    int t;

    t = ind_stack_peek(lexer);
    while(t > 0) {
        ind_stack_pop(lexer);
        t = ind_stack_peek(lexer);
        lexer->unscanned_dedents++;
    }
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

#define TEST_ERROR(c) {\
    if ((c) == CHAR_ERROR) { \
        error(lexer, LEXERR_BAD_STREAM, "Bad source stream"); \
        return TOKEN_ERROR; \
    } \
}

#define TOKEN_EOF -1
#define TOKEN_ERROR -2

static inline int lex_once(Lexer *lexer) {
    if (lexer->unscanned_dedents > 0) {
        lexer->unscanned_dedents--;
        return DEDENT;
    } else if (lexer->is_end) {
        return TOKEN_EOF;
    } else if (lexer->is_newline_phase) {
        lexer->is_newline_phase = 0;

        int next_indent_level = 0;
        int lookahead = Stream_peek(&lexer->stream);
        while (lookahead == ' ' || 
               lookahead == '\n' || 
               lookahead == '\t' ||
               lookahead == '#') {
            Stream_pop(&lexer->stream);
            if (lookahead == '#') {
                int comment_c = Stream_peek(&lexer->stream);
                while (comment_c != '\n' && comment_c != CHAR_EOF) {
                    Stream_pop(&lexer->stream);
                    comment_c = Stream_peek(&lexer->stream);
                }
            } else if (lookahead == '\n') {
                next_indent_level = 0;
            } else {
                next_indent_level++;
                if (lexer->repr_indent_char == 0) {
                    lexer->repr_indent_char = lookahead;
                } else if (lexer->repr_indent_char != lookahead) {
                    error(lexer, 
                          LEXERR_MIXED_SPACES_AND_TABS, 
                          "Don't mix spaces and tabs to indicate indents");
                    return TOKEN_ERROR;
                }
            }
            lookahead = Stream_peek(&lexer->stream);
        }
        TEST_ERROR(lookahead);

        if (lookahead == CHAR_EOF) {
            flush_ind_stack(lexer);
            lexer->is_end = 1;
            Stream_clear_record(&lexer->stream);
            return lex_once(lexer);
        }

        int t = ind_stack_peek(lexer);
        if (ind_stack_empty(lexer)) {
            error(lexer, LEXERR_FATAL_ERROR, "FATAL INDENT ERROR");
            return TOKEN_ERROR;
        } else if (t < next_indent_level) {
            ind_stack_push(lexer, next_indent_level);
            return INDENT;
        } else if (t > next_indent_level) {
            while (t > next_indent_level) {
                ind_stack_pop(lexer);
                t = ind_stack_peek(lexer);
                lexer->unscanned_dedents++;
            }
            if (t != next_indent_level) {
                error(lexer, LEXERR_INDENT_MISMATCH, "Indentation level mismatch");
                return TOKEN_ERROR;
            }
        }
        Stream_clear_record(&lexer->stream);
        return lex_once(lexer);
    }

    int skip;
    int token;
    do {
        int c = Stream_pop(&lexer->stream);
        TEST_ERROR(c);

        token = 0;
        skip = 0;
        switch (c) {
            case CHAR_EOF:
                flush_ind_stack(lexer);
                if (lexer->bracket_depth > 0) {
                    error(lexer, LEXERR_BRACKET_MISMATCH, "Expected closing bracket/parenthisis");
                    return TOKEN_ERROR;
                } else {
                    token = NEWLINE;
                }
                lexer->is_end = 1;
                break;
            case ' ':
            case '\t':
                skip = 1;
                Stream_clear_record(&lexer->stream);
                break;
            case '\n':
                if (lexer->bracket_depth > 0) {
                    skip = 1;
                    Stream_clear_record(&lexer->stream);
                } else {
                    token = NEWLINE;
                    lexer->is_newline_phase = 1;
                }
                break;
            case '#':
                {
                    int comment_c = Stream_peek(&lexer->stream);
                    while (comment_c != '\n' && comment_c != CHAR_EOF) {
                        Stream_pop(&lexer->stream);
                        comment_c = Stream_peek(&lexer->stream);
                    }
                    skip = 1;
                    Stream_clear_record(&lexer->stream);
                }
                break;
#define NEWLINE_TOKEN_HACK(returned_token) {\
    int col_c = Stream_peek(&lexer->stream); \
    while (col_c == ' ' || col_c == '\t') { \
        Stream_pop(&lexer->stream); \
        col_c = Stream_peek(&lexer->stream); \
    } \
    if (col_c == '#' || col_c == '\n') { \
        token = (returned_token); \
    } \
}
    
            case '-':
                {
                    int lookahead = Stream_peek(&lexer->stream);
                    if (lookahead == '>') {
                        Stream_pop(&lexer->stream);
                        token = ARROW;
                    } else if (lookahead == '-') {
                        Stream_pop(&lexer->stream);
                        NEWLINE_TOKEN_HACK(DMINUS_NEWLINE);
                        if (token != DMINUS_NEWLINE) {
                            error(lexer, LEXERR_INVALID_CHARACTER, "Expected newline after '--'");
                            return TOKEN_ERROR;
                        }
                    } else {
                        token = MINUS;
                    }
                    break;
                }
            case ':':
                if (Stream_peek(&lexer->stream) == '=') {
                    Stream_pop(&lexer->stream);
                    token = DEFASSIGN;
                } else if (lexer->bracket_depth == 0) {
                    NEWLINE_TOKEN_HACK(COLUMN_NEWLINE);
                    if (token != COLUMN_NEWLINE) 
                        token = COLUMN;
                } else
                    token = COLUMN;
                break;
            case '>':
                if (Stream_peek(&lexer->stream) == '=') {
                    Stream_pop(&lexer->stream);
                    token = GTE;
                } else if (lexer->bracket_depth == 0) {
                    NEWLINE_TOKEN_HACK(GT_NEWLINE);
                    if (token != GT_NEWLINE)
                        token = GT;
                } else {
                    token = GT;
                }
                break;
            case '<':
                if (Stream_peek(&lexer->stream) == '=') {
                    Stream_pop(&lexer->stream);
                    token = LTE;
                } else {
                    token = LT;
                }
                break;
            case '.':
                if (Stream_peek(&lexer->stream) >= '0' &&
                    Stream_peek(&lexer->stream) <= '9') {
                    while (Stream_peek(&lexer->stream) >= '0' &&
                           Stream_peek(&lexer->stream) <= '9') {
                        Stream_pop(&lexer->stream);
                    }
                    token = FLOAT;
                } else {
                    token = DOT;
                }
                break;
            case ',':
                token = COMMA;
                break;
            case '+':
                token = PLUS;
                break;
            case '/':
                token = SLASH;
                break;
            case '%':
                token = PERCENT;
                break;
            case '!':
                if (Stream_peek(&lexer->stream) == '=') {
                    Stream_pop(&lexer->stream);
                    token = NEQ;
                } else 
                    token = BANG;
                break;
            case '*':
                if (Stream_peek(&lexer->stream) == c) {
                    Stream_pop(&lexer->stream);
                    token = DSTAR;
                } else 
                    token = STAR;
                break;
            case '&':
                if (Stream_peek(&lexer->stream) == c) {
                    Stream_pop(&lexer->stream);
                    token = DAMP;
                } else
                    token = AMP;
                break;
            case '|':
                if (Stream_peek(&lexer->stream) == c) {
                    Stream_pop(&lexer->stream);
                    token = DPIPE;
                } else
                    token = PIPE;
                break;
            case '=':
                if (Stream_peek(&lexer->stream) == c) {
                    Stream_pop(&lexer->stream);
                    token = EQ;
                } else 
                    token = ASSIGN;
                break;

            case '\\':
                if (Stream_peek(&lexer->stream) == '\n' ||
                    Stream_peek(&lexer->stream) == CHAR_EOF) {

                    Stream_pop(&lexer->stream);
                    while (Stream_peek(&lexer->stream) == ' ' ||
                           Stream_peek(&lexer->stream) == '\t') {
                        Stream_pop(&lexer->stream);
                    }
                    skip = 1;
                    Stream_clear_record(&lexer->stream);
                } else {
                    error(lexer, LEXERR_INVALID_AFTER_BACKSLASH, "Unexpected character after line continuation character");
                    return TOKEN_ERROR;
                }
                break;
            case '[':
                lexer->bracket_depth++;
                token = LBRKT;
                break;
            case '(':
                lexer->bracket_depth++;
                token = LPAR;
                break;
            case ']':
                if(lexer->bracket_depth == 0) {
                    error(lexer, LEXERR_BRACKET_MISMATCH, "Openning bracket not found");
                    return TOKEN_ERROR;
                }
                lexer->bracket_depth--;
                token = RBRKT;
                break;
            case ')':
                if(lexer->bracket_depth == 0) {
                    error(lexer, LEXERR_BRACKET_MISMATCH, "Openning parenthisis not found");
                    return TOKEN_ERROR;
                }
                lexer->bracket_depth--;
                token = RPAR;
                break;
            default:
                if (c >= '0' && c <= '9') {
                    while (Stream_peek (&lexer->stream) >= '0' &&
                           Stream_peek (&lexer->stream) <= '9') {
                        Stream_pop(&lexer->stream);
                    }
                    if (Stream_peek(&lexer->stream) != '.') {
                        token = INTEGER;
                    } else {
                        Stream_pop(&lexer->stream); // consume dot
                        while (Stream_peek (&lexer->stream) >= '0' &&
                               Stream_peek (&lexer->stream) <= '9') {
                            Stream_pop(&lexer->stream);
                        }
                        token = FLOAT;
                    }
                } else if (c == '\'' || c == '\"') {
                    while (Stream_peek(&lexer->stream) != c && 
                           Stream_peek(&lexer->stream) != CHAR_EOF) {
                        int x = Stream_pop(&lexer->stream);
                        if (x == '\\') {
                            // accept backslash-escaping chars
                            int after_backslash = Stream_peek(&lexer->stream);
                            switch (after_backslash) {
                                case '\\':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 1, NULL, 0);
                                    break;
                                case '\'':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\'", 1);
                                    break;
                                case '\"':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\"", 1);
                                    break;
                                case 'a':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\a", 1);
                                    break;
                                case 'b':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\b", 1);
                                    break;
                                case 'f':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\f", 1);
                                    break;
                                case 'n':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\n", 1);
                                    break;
                                case 'r':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\r", 1);
                                    break;
                                case 't':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\t", 1);
                                    break;
                                case 'v':
                                    Stream_pop(&lexer->stream);
                                    Stream_replace_record(&lexer->stream, 2, "\v", 1);
                                    break;
                                case 'x':
                                    Stream_pop(&lexer->stream);
                                    {
                                        int cnt;
                                        int num = 0;
                                        for (cnt = 0; cnt < 2; cnt++) {
                                            int digit = Stream_pop(&lexer->stream);
                                            if (digit >= '0' && digit <= '9') {
                                                digit -= '0';
                                            } else if (digit >= 'a' && digit <= 'f') {
                                                digit -= 'a';
                                                digit += 10;
                                            } else if (digit >= 'A' && digit <= 'F') {
                                                digit -= 'A';
                                                digit += 10;
                                            } else {
                                                error(lexer, LEXERR_INVALID_HEX_ESCAPE, "Invalid hex escape");
                                                return TOKEN_ERROR;
                                            }
                                            num *= 16;
                                            num += digit;
                                        }
                                        char hx[1];
                                        hx[0] = (char)num;
                                        Stream_replace_record(&lexer->stream, 4, hx, 1);
                                    }
                                    break;
                                default:
                                    if (after_backslash >= '0' && after_backslash <= '7') {
                                        int cnt = 0;
                                        int oct = 0;
                                        while (cnt < 3 &&
                                               Stream_peek(&lexer->stream) >= '0' &&
                                               Stream_peek(&lexer->stream) <= '7') {
                                            oct *= 8;
                                            oct += (Stream_pop(&lexer->stream) - '0');
                                            cnt++;
                                        }
                                        char hx[1];
                                        hx[0] = (char)oct;
                                        Stream_replace_record(&lexer->stream, 1 + cnt, hx, 1);
                                    }
                            }
                        } 

                    }

                    if (Stream_peek(&lexer->stream) == CHAR_EOF) {
                        error(lexer, 
                              LEXERR_EOF_IN_STRING,
                              "encountered EOF while reading string literal");
                        return TOKEN_ERROR;
                    }
                    Stream_pop(&lexer->stream); // consume the closing quotation mark
                    token = STRING;
                } else if (c == '$' ||
                           c == '@' ||
                           (c >= 'a' && c <= 'z') ||
                           (c >= 'A' && c <= 'Z') ||
                           c == '_') {
                    // letter [$@a-zA-Z_]
                    // exletter [$@a-zA-Z0-9_!?]
                    // pattern: {letter}{exletter}*
                    char next = Stream_peek(&lexer->stream);
                    while (next == '$' ||
                           next == '@' ||
                           (next >= 'a' && next <= 'z') ||
                           (next >= 'A' && next <= 'Z') ||
                           (next >= '0' && next <= '9') ||
                           next == '_' || next == '!' ||
                           next == '?') {
                        Stream_pop(&lexer->stream);
                        next = Stream_peek(&lexer->stream);
                    }
                    token = NAME;
                } else {
                    char fmt[4];
                    char msg[128];
                    format_char(c, fmt);
                    snprintf(msg, 128, "Invalid character: '%s' [line %d, col %d]", fmt, lexer->stream.curline, lexer->stream.curcol - 1);
                    error(lexer, LEXERR_INVALID_CHARACTER, msg);
                    return TOKEN_ERROR;
                }
                break;
        }
    } while (skip);
    return token;
}

LexToken* Lexer_lex(Lexer *lexer, LexError *lexerr) {
    LexToken* result;
    char *text;
    int sline, eline, scol, ecol;

    sline = lexer->stream.curline;
    scol = lexer->stream.curcol;

    Stream_start_record(&lexer->stream);
    int token = lex_once(lexer);
    text = Stream_end_record(&lexer->stream);

    if (token == TOKEN_EOF) {
        free(text);
        return NULL;
    }

    eline = lexer->stream.curline;
    ecol = lexer->stream.curcol;

    result = (LexToken *)malloc(sizeof(LexToken));
    result->token = token;
    result->text = text;
    result->text_len = strlen(text);
    result->sline = sline;
    result->eline = eline;
    result->scol = scol;
    result->ecol = ecol;

    if (token == TOKEN_ERROR) {
        result->error_occurred = 1;
        lexerr->code = lexer->last_error_code;
        strncpy(lexerr->msg, lexer->last_error_msg, LEXERR_MAX_STRING_CNT - 1);
    } else {
        result->error_occurred = 0;
    }
    return result;
}

void Lexer_remove_token(LexToken *tok) {
    free(tok->text);
    free(tok);
}
int Lexer_current_line(Lexer *lexer) {
    return lexer->stream.curline;
}

int Lexer_current_col(Lexer *lexer) {
    return lexer->stream.curcol;
}

void Lexer_remove(Lexer *lexer) {
    Stream_remove(&lexer->stream);
    free(lexer);
}
