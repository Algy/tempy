#!/usr/bin/env python

from distutils.core import setup
from distutils.extension import Extension

setup(name="LISN",
      version="0.1",
      description="General-purpose python-like syntax parser",
      author="Alchan Kim",
      author_email="a9413miky@gmail.com",
      packages=["lisn"],
      ext_modules=[Extension("clisn",
                             sources=["clisn/ast.c", "clisn/lex.yy.c",
                                      "clisn/ast-make.c", "clisn/parser.c", 
                                      "clisn/astmisc.c",
                                      "clisnmod.c"])])

