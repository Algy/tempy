Tempy
===
Python HTML template engine and yet another meta-language for python

Installation
==
In the root of project directory, type
```bash
python setup.py install
```
GNU flex, the lexer gernator, is required to install this.

Basic example
==

Let’s assume that working directory is composed like the following structure.
```
run.py
tempy-templates/
  index.tpy
  outline.tpy
  factorial.tpy
```
As shown above, name of tempy file ends with “.tpy”. 


```
MainTemplate = html:
  head:
		title: "First example" # comment starts with sharp(#), as in Python.
	body:
		h2: 'Hello World!' # You can wrap content with either single quotation mark or double one.
		h3:
			"This is content in h3 element" # You can also specify content at the next line with one-indent deeper
		p: 
			'''
			It is the first example of Tempy library, HTML template-engine.
			With a sequence of three single or double quotation marks, you can write multi-line content.
			'''
```

And code into run.py like the following stub
```python
from tempy import Environment
env = Environment("tempy-templates")

index_module = env.module("index")
with open("result.html", "w") as f:
    f.write(str(index_module.MainTemplate))
```
Note that “Environment.module(..)” method doesn’t accept file name with extension. In other words, you should specify filename without its extention (“index” in this case) instead of full filename(“index.tpy” in this case)


....Under construction

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
