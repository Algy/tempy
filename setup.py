#!/usr/bin/env python

from distutils.core import setup
from distutils.extension import Extension

setup(name="clisn",
      ext_modules=[Extension("clisn",
                             sources=["clisn/ast.c", "clisn/lex.yy.c",
                                      "clisn/ast-make.c", "clisn/parser.c", 
                                      "clisn/astmisc.c",
                                      "clisnmod.c"])])

