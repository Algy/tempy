parser_test: ast.c astmisc.c lex.yy.c ast-make.c parser.c parser_test.c
	gcc -g -O2 -std=c99 ast.c astmisc.c lex.yy.c ast-make.c parser.c parser_test.c -o parser_test 
lexer_test: lex.yy.c lexer_test.c
	gcc -g -std=c99 lex.yy.c lexer_test.c -o lexer_test
lex.yy.c: lexer.l
	flex lexer.l
ast-make.c: ast-make.y lemon
	./lemon ast-make.y
lemon: lemon.c lempar.c
	gcc -g -std=c99 lemon.c -o lemon

clean:
	rm -rf lex.yy.c lexer_test
	rm -rf parser_test ast-make.c ast-make.h ast-make.out
	rm -rf lemon
