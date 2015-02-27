" Vim syntax file
" Language: Tempy
" Maintainer: Alchan Kim
" Latest Revision: 

if exists("b:current_syntax")
  finish
endif

syn keyword syntaxHTMLElement html head title base link meta style script noscript template body
syn keyword syntaxHTMLElement section nav article aside h1 h2 h3 h4 h5 h6 header footer address
syn keyword syntaxHTMLElement main p hr pre blockquote ol ul li dl dt dd figure figcaption div
syn keyword syntaxHTMLElement a em strong small s cite q dfn abbr data time code var samp kbd
syn keyword syntaxHTMLElement sub i b u mark ruby rt rp bdi bdo span br wbr ins del img iframe
syn keyword syntaxHTMLElement embed object param video audio source track canvas map area svg
syn keyword syntaxHTMLElement math table caption colgroup col tbody thead tfoot tr td th form
syn keyword syntaxHTMLElement fieldset legend label input button select datalist optgroup option
syn keyword syntaxHTMLElement textarea keygen output progress meter details summary menuitem menu
syn keyword syntaxHTMLElement rawstring

syn keyword syntaxStatementLabel pass raise if let seq for each _ 
syn keyword syntaxDef def import import_from pyimport pyimport_from skipwhite

syn keyword syntaxTODO containedin=inlineComment contained TODO FIXME XXX NOTE


syn region syntaxInsidePar start=+(+ end=+)+ contains=constStringLiteralInPar,syntaxHTMLAttribute,syntaxKeywordInPar 

syn match listOrDict '\$\$\?'
syn match constNumber '\d*\.\d\+'
syn match constNumber '\d\+\.'
syn match constNumber '\d\+'

" Imported from python syntax script
syn region constStringLiteral start=+'+ skip=+\\\\\|\\'\|\\$+ excludenl end=+'+ end=+$+ 
syn region constStringLiteral start=+"+ skip=+\\\\\|\\"\|\\$+ excludenl end=+"+ end=+$+
syn region constStringLiteral start=+"""+ end=+"""+ 
syn region constStringLiteral start=+'''+ end=+'''+

syn region constStringLiteralInPar start=+'+ skip=+\\\\\|\\'\|\\$+ excludenl end=+'+ end=+$+ contained
syn region constStringLiteralInPar start=+"+ skip=+\\\\\|\\"\|\\$+ excludenl end=+"+ end=+$+ contained
syn region constStringLiteralInPar start=+"""+ end=+"""+  contained
syn region constStringLiteralInPar start=+'''+ end=+'''+ contained

syn keyword syntaxHTMLAttribute code text onreset cols datetime disabled accept-charset shape codetype alt contained
syn keyword syntaxHTMLAttribute compact onload style title valuetype version onmousemove valign onsubmit contained
syn keyword syntaxHTMLAttribute onkeypress rules nohref abbr background scrolling name summary noshade contained
syn keyword syntaxHTMLAttribute coords onkeyup dir frame usemap ismap onchange hspace vlink for selected contained
syn keyword syntaxHTMLAttribute rev label content onselect rel onfocus charoff method alink onkeydown contained
syn keyword syntaxHTMLAttribute codebase noresize span src language standby declare maxlength action tabindex contained
syn keyword syntaxHTMLAttribute color colspan accesskey height href nowrap size rows checked start bgcolor  contained 
syn keyword syntaxHTMLAttribute onmouseup scope scheme type cite onblur onmouseout link hreflang onunload contained 
syn keyword syntaxHTMLAttribute target align value headers vspace longdesc classid defer prompt accept contained 
syn keyword syntaxHTMLAttribute onmousedown char border archive axis rowspan media charset id readonly contained 
syn keyword syntaxHTMLAttribute onclick cellspacing profile multiple object cellpadding http-equiv contained 
syn keyword syntaxHTMLAttribute marginheight data class frameborder enctype lang clear face contained  
syn keyword syntaxHTMLAttribute marginwidth ondblclick width onmouseover contained  

syn keyword syntaxKeywordInPar in contained

syn match inlineComment '#.*$' contains=syntaxTODO

let b:current_syntax = "tempy"

hi def link inlineComment Comment
hi def link syntaxStatementLabel Statement
hi def link listOrDict Statement
hi def link syntaxDef Statement
hi def link syntaxHTMLElement Type
hi def link constNumber Number
hi def link constStringLiteral PreProc
hi def link constStringLiteralInPar String
hi def link syntaxTODO Todo
hi def link syntaxHTMLAttribute Delimiter
hi def link syntaxKeywordInPar Statement
