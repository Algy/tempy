from collections import Iterable

HTML_TAGS = ['html',
         'head',
         'title',
         'base',
         'link',
         'meta',
         'style',
         'script',
         'noscript',
         'template',
         'body',
         'section',
         'nav',
         'article',
         'aside',
         'h1',
         'header',
         'footer',
         'address',
         'main',
         'p',
         'hr',
         'pre',
         'blockquote',
         'ol',
         'ul',
         'li',
         'dl',
         'dt',
         'dd',
         'figure',
         'figcaption',
         'div',
         'a',
         'em',
         'strong',
         'small',
         's',
         'cite',
         'q',
         'dfn',
         'abbr',
         'data',
         'time',
         'code',
         'var',
         'samp',
         'kbd',
         'sub',
         'i',
         'b',
         'u',
         'mark',
         'ruby',
         'rt',
         'rp',
         'bdi',
         'bdo',
         'span',
         'br',
         'wbr',
         'ins',
         'del',
         'img',
         'iframe',
         'embed',
         'object',
         'param',
         'video',
         'audio',
         'source',
         'track',
         'canvas',
         'map',
         'area',
         'svg',
         'math',
         'table',
         'caption',
         'colgroup',
         'col',
         'tbody',
         'thead',
         'tfoot',
         'tr',
         'td',
         'th',
         'form',
         'fieldset',
         'legend',
         'label',
         'input',
         'button',
         'select',
         'datalist',
         'optgroup',
         'option',
         'textarea',
         'keygen',
         'output',
         'progress',
         'meter',
         'details',
         'summary',
         'menuitem',
         'menu']
HTML_VOID_TAGS = ['area', 'base', 'br', 'col', 'command', 
                  'embed', 'hr', 'img', 'input', 'keygen',
                  'link', 'meta', 'param', 'source', 'track', 'wbr']
_TAG_SET = set(HTML_TAGS)
_VOID_TAG_SET = set(HTML_VOID_TAGS)


def _escape_attr_value(val):
    # TODO
    return val

def _is_whitespace(s): 
    return s == " " or s == "\t" or s == "\n"

def _escape_string(val):
    imd_str = val.replace("<", "&lt;")\
                 .replace(">", "&gt;")\
                 .replace("&", "&amp;")
    result = imd_str
    '''
    imd_str_len = len(imd_str)
    result = ""
    idx = 0
        
    # consume succeeding whitespaces
    while idx < imd_str_len and _is_whitespace(imd_str[idx]):
        idx += 1

    while idx < imd_str_len:
        c = imd_str[idx]
        if _is_whitespace(c):
            if c == " ":
                result += c
                idx += 1

                interspace = 0
                while idx < imd_str_len and imd_str[idx] == " ":
                    idx += 1
                    interspace += 1

                lookahead_idx = idx
                # look stub ahead to check if all of trailing characters are whitespaces
                while lookahead_idx < imd_str_len and \
                      _is_whitespace(imd_str[lookahead_idx]):
                    lookahead_idx += 1
                
                if lookahead_idx < imd_str_len:
                    result += "&nbsp;" * interspace

                if idx < imd_str_len:
                    result += imd_str[idx:min(lookahead_idx, imd_str_len)]
                idx = lookahead_idx
            else:
                result += c
                idx += 1
        else:
            result += c
            idx += 1
            while idx < imd_str_len and not _is_whitespace(imd_str[idx]):
                result += imd_str[idx]
                idx += 1
    '''
    return result

def flatten_tags(val):
    result = []
    def iterate(obj):
        if obj is None:
            pass
        elif isinstance(obj, Iterable) and not isinstance(obj, basestring):
            for elem in obj:
                iterate(elem)
        else:
            result.append(obj)
    iterate(val)
    return result


class Tag:
    def __init__(self, tag_name, attr_dict, *sub_tags):
        tag_name = tag_name.lower()
        if tag_name not in _TAG_SET:
            raise ValueError("{0} is not appropriate HTML tag".format(tag_name))
        self.tag_name = tag_name
        self.attr_dict = attr_dict or {}
        self.sub_tags = flatten_tags(sub_tags)
        self.void_tag = tag_name in _VOID_TAG_SET
        if self.void_tag and len(sub_tags) > 0:
            raise ValueError("{0} is void tag, having sub tags though".format(tag_name))

    def __repr__(self):
        if len(self.sub_tags) == 0:
            return "TAG <%s>"%self.tag_name
        else:
            return "TAG <%s ...(%d subtags)>"%(self.tag_name, len(self.sub_tags))

    def __str__(self):
        return self.emit_html(self)

    def emit_html(self, indent=2, acc_indent=0):
        sub_tags_len = len(self.sub_tags)
        tag_name = self.tag_name
        indent_space = " " * acc_indent
        
        res = indent_space + "<%s"%tag_name
        if self.attr_dict:
            for (k, v) in self.attr_dict.items():
                if isinstance(v, bool):
                    value_str = "true" if v else "false"
                else:
                    value_str = str(v)
                value_str = _escape_attr_value(value_str)
                res += " %s=\"%s\""%(str(k), value_str)

        if sub_tags_len == 0 and not self.void_tag:
            res += " /"
        res += ">\n"

        if sub_tags_len > 0:
            for tag_node in self.sub_tags:
                if isinstance(tag_node, basestring):
                    res += indent_space + " "*indent +  _escape_string(tag_node) + "\n"
                else:
                    res += tag_node.emit_html(indent, acc_indent + indent)
            res += indent_space + "</%s>\n"%tag_name
        return res

class TagPool:
    def __getattr__(self, tag_name):
        if tag_name.lower() in _TAG_SET:
            return lambda *args, **kwds: Tag(tag_name, *args, **kwds)
        else:
            raise ValueError("{0} is not appropriate tag".format(tag_name))

def is_tag_name(name, case_sensetive=False):
    if case_sensetive:
        return name in _TAG_SET
    else:
        return name.lower() in _TAG_SET 

