#include <stdio.h>
#include <stdlib.h>
#include "parser.h"

#define USE_BYTES

int main() {
    FILE *fp;
    LexParseError err;
    ASTHD *ast;

    fp = fopen("lextest.lidl", "r");

#ifdef USE_FILE
    ast = parse_file(fp, &err);
    if(err.error_occurred) {
        printf("ERROR!\n");
        printf("%s\n", err.err_msg);
    } else {
        printf("==>result<==\n");
        ast_dbg_print(ast);
        ast_free(ast);
    }
#elif defined(USE_BYTES)
    char *source;
    int len;
    
    fseek(fp, 0, SEEK_END);
    len = ftell(fp);
    rewind(fp);

    source = (char *)calloc(len + 1, 1);
    fread(source, 1, len, fp);

    ast = parse_bytes(source, len, &err);
    if(err.error_occurred) {
        printf("ERROR!\n");
        printf("line:%d-%d\n", err.sline, err.eline);
        printf("col:%d-%d\n", err.scol, err.ecol-1);
        printf("%s\n", err.err_msg);
    } else {
        printf("==>result<==\n");
        ast_dbg_print(ast);
        ast_free(ast);
    }

    free(source);
#else
# error "specify kind of error test"
#endif
    fclose(fp);
    return 0;
}
