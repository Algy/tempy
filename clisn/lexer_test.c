#include <stdio.h>
#include "lexer.h"
#include "ast-make.h"

int main() {
    FILE *f;
    Lexer *lexer;
    LexToken *lexres;
    LexError lexerr;

    char* lst[3];
    int lst_cnt;

    lst_cnt = 0;

    f = fopen("lextest.lidl", "r");
    lexer = Lexer_init_with_file(f);
    while(1) {
        int token;
        char* text;
        lexres = Lexer_lex(lexer, &lexerr);
        if (!lexres) {
            printf("EOF\n");
            break;
        }
        token = lexres->token;
        text = lexres->text;
        if(lexres->error_occurred) {
            printf("ERROR! error code=>%d\nerror msg=>%s\n", lexerr.code, lexerr.msg);
            printf("(%d, %d)-(%d, %d)\n", lexres->sline, lexres->scol, lexres->sline, lexres->ecol - 1);
            Lexer_remove_token(lexres);
            break;
        } else { 
            switch(token) {
                case 0:
                    text = "<<EOF>>";
                    break;
                case INDENT:
                    text = ">>";
                    break;
                case DEDENT:
                    text = "<<";
                    break;
                case NEWLINE:
                    text = "(NEWLINE)";
                    break;
            }
        }
        printf("%d\t%s\n", token, text);
        Lexer_remove_token(lexres);
    }
    fclose(f);
    Lexer_remove(lexer);
    return 0;
}
