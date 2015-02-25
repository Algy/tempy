#include <stdio.h>
#include "lexer.h"
#include "ast-make.h"

int main() {
    FILE *f;
    Lexer lexer;
    LexToken *lexres;
    LexError lexerr;

    char* lst[3];
    int lst_cnt;

    lst_cnt = 0;

    f = fopen("lextest.lidl", "r");
    init_lexer_with_file(&lexer, 0, f);
    while(1) {
        int token;
        char* text;
        lexres = lexer_lex(&lexer, &lexerr);
        token = lexres->token;
        text = lexres->text;
        if(lexres->error_occured) {
            printf("ERROR! error code=>%d\nerror msg=>%s\n", lexerr.code, lexerr.msg);
            printf("(%d, %d)-(%d, %d)\n", lexres->sline, lexres->scol, lexres->sline, lexres->ecol - 1);
            break;
        } else if(lexres->token == 0) {
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
            printf("%d\t%s\n", token, text);
        }
        lexer_remove_token(lexres);
    }
    fclose(f);
    remove_lexer(&lexer);
    return 0;
}
