Tempy
===
Python HTML template engine and yet another meta-language for python

Tempy is still under construction. Contribute to me!

Installation
==
In the root of project directory, type
```bash
python setup.py install
```
GNU flex is required to compile internal parser used in tempy.

Basic example
==

Let’s assume that working directory is composed like the following structure.
```
run.py
tempy-templates/
  index.tpy
```
As shown above, name of tempy files ends with “.tpy”. Write below code into index.tpy.
```
MainTemplate = html:
  head:
    title: "First example" # comment starts with sharp(#), as in Python.
  body:
    h2: 'Hello World!' # You can wrap content with either single quotation mark or double one.
    h3:
      "This is content in h3 element" # You can also specify content at the next line with one-indent deeper
    p(id="main-content", class="foo bar"): 
	    '''
	    It is the first example of Tempy library, HTML template-engine.
	    With a sequence of three single or double quotation marks, you can write multi-line content.
	    '''
    a(href="#"): "external link"
```

And, in run.py, write the following stub
```python
from tempy import Environment
env = Environment("tempy-templates") # specify the directory where tpy files are present

index_module = env.module("index")
with open("result.html", "w") as f:
    f.write(str(index_module.MainTemplate))
```
Note that “Environment.module(..)” method doesn’t accept file name with extension. In other words, you should specify filename without its extention (“index” in this case) instead of full filename(“index.tpy” in this case)


Then if you execute run.py, you will see the below HTML code genereted in result.html.
```html
<html>
  <head>
    <title>
      First example
    </title>
  </head>
  <body>
    <h2>
      Hello World!
    </h2>
    <h3>
      This is content in h3 element
    </h3>
    <p class="foo bar" id="main-content">
          
      It is the first example of Tempy library, HTML template-engine.
      With a sequence of three single or double quotation marks, you can write multi-line content.
          
    </p>
    <a href="#">
      external link
    </a>
  </body>
</html>
```

Many template engines provide methods to fill up template file with data so that user generates different page on various data. In Tempy, user can use "def" statement to define templates to which data is passed as arguments. 

```
def MainTemplate(user_name):
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
		p:
			"Hello!"
			user_name
			"How have you been?"
		
```

You may notice that it's very simillar to define a function in Python. In fact, there's no difference between function and template. Thus, user just calls MainTemplate in python with argument "user_name".
```python
from tempy import Environment
env = Environment("tempy-templates")

user_name = raw_input("Your name")

index_module = env.module("index")
result = index_module.MainTemplate(user_name)
with open("result.html", "w") as f:
    f.write(str(result))
```

You can also access elements of a dict, access attributes of a list, or iterate a list in Tempy.
```
def MainTemplate(author_list, footer_dict):
  table:
		thead:
			tr:
				td: "Name"
				td: "Country"
				td: "Note"
		tbody:
			$each(author_obj, in = author_list):
				tr:
					td: author_obj.name
					td: author_obj.country
					td: author_obj.note
	footer:
	    p: "Maintainer: " + footer_dict["maintainer"]
	    p: "Tel. " + footer_dict["tel"]
	    p: 
	        "Contact us at "
	        a(href=footer_dict["github_url"])
```

run.py:
```python
from tempy import Environment
env = Environment("tempy-templates")

class Author:
    def __init__(self, name, country, note):
        self.name = name
        self.country = country
        self.note = note


authors = [
    Author('Alchan "Algy" Kim', 'Korea', 'Maintainer'),
    Author('You', 'Somewhere', '')
]

footer_dict = {
    "maintainer": "Kim",
    "tel": "82-10-xxxx-xxxx",
    "github_url": "https://github.com/Algy/tempy"
}

index_module = env.module("index")
result = index_module.MainTemplate(authors, footer_dict)
with open("result.html", "w") as f:
    f.write(str(result))
```
Execute run.py and you will see result.html.


Many template engines have extension system. For example, there could be a base template with common header and footer so that concrete templates could fill up detail contents into the base. In Tempy, all you need to do that is defining "base function" and call it with appropriate html fragments.
```
def Base(_title, Fragment):
  html:
    header:   
      title: _title # A preceeding underline is used to avoid name conflict with the HTML tag, "title"
      Fragment

Fragment1 = div:
  h3: "Heading3"
  p: "Paragraph content"

Fragment2 = table:
  tr:
    td: "1"
    td: "2"
  tr: 
    td: "3"
    td: "4"
    
def Template1():
  Base("H3 And Paragraph", Fragment1) 
  # Base(_title="H3 And Paragraph", Fragment=Fragment1) is possible as well.
    
def Template2():
  Base("A table", Fragment2)

```
Or, use ">" next to the callee and you can directly specify non-inline elements as arguments vertically.
```
# ...

def Template1():
  Base>
    # First argument
    "H3 And Paragraph"
    # Second argument
    div:
      h3: "Heading3"
      p: "Paragraph content" 
            
# ...
```
Or, you can use "<argument name> -> <content>" notation for the sake of readability. It is like calling with keyword argument in python. Ordering of arguments doesn't matter in this case.

```
def Template1():
  Base>
    Fragment -> div:
      h3: "Heading 3"
      p: "Paragraph content"
    _title -> "H3 And Paragraph"
```

You can freely use various standard libaries of python in Tempy. So you can do funny thing like this!
```
pyimport urllib2

def MainTemplate():
  # it allows content to be written as it is, without being escaped.
	rawstring: 
		urllib2.urlopen("http://canrailsscale.com").read()\
		       .replace("Rails", "Flask").replace("NO", "YES") 
```





The following document about LISN parser is outdated.
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
