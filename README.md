Tempy
===
python HTML template engine and yet another meta-language for python

<Under construction>

LISN
====
General-purpose expression-oriented syntax parser

What is LISN?
--
Originally, its name is originated from "LIdl Syntax Notation", in which LIDL is a functional programming language with python-like grammar(though it's being designed and not implemented yet :). LISN is designed to have a flexible grammar enough to represent any kind of expression-oriented syntax where syntax block is represented by indentation.

Currently, source codes consist of two part, parser written in C and its wrapper written in python.

Dependency
--
In compilation of C sources, it depends on GNU flex and Lemon parser. Source codes of the latter are provided inside this repo. So GNU flex is only an external dependency.


Python wrapper
--
TODO

C native API
--
clisn/ directory has sources for LISN parser written in C.
TODO

Compilation & Installation
--
cd clisn/
make
cd ..
./setup.py install

TODO
