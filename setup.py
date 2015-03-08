#!/usr/bin/env python

from os.path import join as path_join
from subprocess import check_call
from distutils.core import setup
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from distutils.ccompiler import new_compiler, CCompiler


class LemonGen(build_ext):
    def run(self):
        cc = new_compiler()
        cc.link(CCompiler.EXECUTABLE, ["clisn/lemon.c"], "clisn/lemon")
        check_call([path_join("clisn", "lemon"),
                    path_join("clisn", "ast-make.y")])
        build_ext.run(self)




setup(name="LISN",
      version="0.1",
      description="General-purpose python-like syntax parser",
      author="Alchan Kim",
      author_email="a9413miky@gmail.com",
      packages=["lisn", "tempy"],
      ext_modules=[Extension("clisn",
                             sources=["clisn/ast.c", "clisn/lexer.c",
                                      "clisn/ast-make.c", "clisn/parser.c", 
                                      "clisn/astmisc.c",
                                      "clisnmod.c"])],
      cmdclass = {"build_ext": LemonGen})

