parser_test: ast.c astmisc.c lexer.c ast-make.c parser.c parser_test.c
	gcc -g -O2 -std=c99 ast.c astmisc.c lexer.c ast-make.c parser.c parser_test.c -o parser_test 

lexer_test: lexer.c lexer_test.c
	gcc -g -std=c99 lexer.c lexer_test.c -o lexer_test

ast-make.c: ast-make.y lemon
	./lemon ast-make.y

lemon: lemon.c lempar.c
	gcc -g -std=c99 lemon.c -o lemon

clean:
	rm -rf lexer_test
	rm -rf parser_test ast-make.c ast-make.h ast-make.out
	rm -rf lemon
