from pprint import pprint
from clisn import loads
from itertools import chain
from functional import car, cdr, cons, llist_to_list, list_to_llist, \
                       llmap

def _pull_left_string(s):
    def _is_space(c):
        return c == ' ' or c == '\t'
    length = len(s)
    idx = 0
    head_space = 0
    result = ""

    while idx < length:
        if _is_space(s[idx]):
            head_space += 1
        elif s[idx] == '\n':
            head_space = 0
        else:
            break
        idx += 1

    if idx >= length: # is eof
        return ""
    
    while idx < length:
        c = s[idx]
        cur_space = 0
        if c == '\n': # look ahead
            idx += 1
            result += "\n"
            while idx < length and _is_space(s[idx]):
                cur_space += 1
                idx += 1
            new_space = max(cur_space - head_space, 0)

            result += " "*new_space
        else:
            result += c
            idx += 1
    return result


class LISNPatternException(Exception): pass


def make_string_matcher(pat_name):
    if pat_name.startswith("$"):
        return StringMatcher(StringMatcher.WILDCARD, pat_name[1:])
    elif pat_name.startswith("NAME$"):
        return StringMatcher(StringMatcher.ANY_NAME, pat_name[len("NAME$"):])
    else:
        return StringMatcher(StringMatcher.EXACT_NAME, pat_name)


class LISNMatcher:
    def match(self, lisn):
        '''
        lisn -> (bool, dict)
        '''
        raise NotImplementedError


class StringMatcher(LISNMatcher):
    EXACT_NAME = 1
    ANY_NAME = 2
    WILDCARD = 3

    def __init__(self, _type, name):
        self._type = _type
        self.name = name

    def match(self, lisn):
        if self._type == self.EXACT_NAME:
            if lisn["type"] == "name" and lisn["name"] == self.name:
                return (True, {})
            else:
                return (False, None)
        elif self._type == self.ANY_NAME:
            if lisn["type"] == "name":
                return (True, {self.name: lisn["name"]})
            else:
                return (False, None)
        elif self._type == self.WILDCARD:
            return (True, {self.name: lisn})
        else:
            raise Exception("NOT REACHABLE")

    def match_string(self, s):
        if self._type == self.EXACT_NAME:
            if s == self.name:
                return (True, {})
            else:
                return (False, None)
        elif self._type == self.ANY_NAME or self._type == self.WILDCARD:
            return (True, {self.name: s})
        else:
            raise Exception("NOT REACHABLE")


class XExprMatcher(LISNMatcher):
    def __init__(self, head_expr_matcher, head_label_matcher=None, 
                 pos_matcher=None, kw_matcher=None, star_matcher=None, dstar_matcher=None,
                 amp_matcher=None, damp_matcher=None, vert_suite_matcher=None):
        assert head_expr_matcher is not None
        assert head_label_matcher is None or isinstance(head_label_matcher, StringMatcher)
        assert pos_matcher is None or isinstance(pos_matcher, PosMatcher)
        assert kw_matcher is None or isinstance(kw_matcher, KeywordMatcher)
        assert star_matcher is None or isinstance(star_matcher, PosMatcher)
        assert dstar_matcher is None or isinstance(dstar_matcher, PosMatcher)
        assert amp_matcher is None or isinstance(amp_matcher, PosMatcher)
        assert damp_matcher is None or isinstance(damp_matcher, PosMatcher)
        assert vert_suite_matcher is None or isinstance(vert_suite_matcher, PosMatcher)

        self.head_label_matcher = head_label_matcher 
        self.head_expr_matcher = head_expr_matcher 
        self.pos_matcher = pos_matcher
        self.kw_matcher = kw_matcher
        self.star_matcher = star_matcher
        self.dstar_matcher = dstar_matcher
        self.amp_matcher = amp_matcher
        self.damp_matcher = damp_matcher
        self.vert_suite_matcher = vert_suite_matcher

    def match(self, lisn):
        result = {}
        if lisn["type"] != "xexpr":
            return (False, None)
        
        if lisn["has_head_label"] and self.head_label_matcher:
            hd_lbl_suc, hd_lbl_res = self.head_label_matcher.match_string(lisn["head_label"])
            if hd_lbl_suc:
                result.update(hd_lbl_res)
            else:
                return (False, None)
        elif not lisn["has_head_label"] and not self.head_label_matcher:
            pass
        else:
            return (False, None)

        hd_expr_suc, hd_expr_res = self.head_expr_matcher.match(lisn["head_expr"])
        if hd_expr_suc:
            result.update(hd_expr_res)
        else:
            return (False, None)

        arg_info = lisn["arg_info"]
        # positional arguments
        if self.pos_matcher:
            pos_suc, pos_res = self.pos_matcher.match_pos(arg_info["pargs"])
            if pos_suc:
                result.update(pos_res)
            else:
                return (False, None)
        elif not self.pos_matcher and len(arg_info["pargs"]) > 0:
            return (False, None)


        # keyword arguments
        if self.kw_matcher:
            kw_suc, kw_res = self.kw_matcher.match_kw(arg_info["kargs"])
            if kw_suc:
                result.update(kw_res)
            else:
                return (False, None)
        elif not self.kw_matcher and len(arg_info["kargs"]) > 0:
            return (False, None)


        # special arguments
        for matcher, special_lisn in [(self.star_matcher, arg_info.get("star")),
                                      (self.dstar_matcher, arg_info.get("dstar")),
                                      (self.amp_matcher, arg_info.get("amp")),
                                      (self.damp_matcher, arg_info.get("damp"))]:
            if matcher:
                virtual_lisn_list = [] if special_lisn is None else [special_lisn]
                spc_suc, spc_res = matcher.match_pos(virtual_lisn_list)
                if spc_suc:
                    result.update(spc_res)
                else:
                    return (False, None)
            elif not matcher and special_lisn:
                return (False, None)
        
        vert_list = _suite_to_list(lisn["vert_suite"]) if lisn["has_vert_suite"] else []
        if self.vert_suite_matcher:
            vrt_suc, vrt_res = self.vert_suite_matcher.match_pos(vert_list)
            if vrt_suc:
                result.update(vrt_res)
            else:
                return (False, None)
        elif vert_list:
            return (False, None)
        return (True, result)


def _convert_info_dict(info_dict):
    if info_dict is None:
        return ()
    elif isinstance(info_dict, dict):
        result = {}
        for key, value in info_dict.items():
            result[key] = _convert_info_dict(value)
        return result
    elif isinstance(info_dict, tuple):
        p = info_dict
        result = []
        while p is not None:
            result.append(_convert_info_dict(car(p)))
            p = cdr(p)
        return tuple(result)
    else:
        return info_dict


class PosMatcher:
    def match_pos(self, lisn_list):
        # Wrapper function for _match_pos which use llist instead of list and additional formal arguments
        lisn_llist = list_to_llist(lisn_list) 
        info_dict = {}

        success = self._match_pos(lisn_llist, None, info_dict)
        if success:
            return (True, _convert_info_dict(info_dict))
        else:
            return (False, None)
        

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        '''
        lisn_llist: (lisn | (string, lisn)) list
        seq_cont: (matcher x dict) llist 
            first element of pairs are containing matchers to be matched next
            second element of pairs is a scope dict

        Returns -
            bool
        '''
        raise NotImplementedError


class KeywordMatcher:
    def match_kw(self, name_lisn_pairs):
        '''
        name_lisn_pairs: (string, lisn) list 

        Returns -
            (bool, dict)
        '''
        raise NotImplementedError



#
# Regex-style matching implementation
#

def _follow_cont(lisn_llist, seq_cont):
    if lisn_llist is None and seq_cont is None:
        return True
    elif seq_cont is None:
        return False
    else:
        mat, scope_dict = car(seq_cont)
        return mat._match_pos(lisn_llist, cdr(seq_cont), scope_dict)


class PosSingle(PosMatcher):
    def __init__(self, lisn_matcher, label_matcher=None):
        self.lisn_matcher = lisn_matcher
        self.label_matcher = label_matcher

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        if lisn_llist is None:
            return False
        else:
            item_to_be_matched = car(lisn_llist)
            if isinstance(item_to_be_matched, tuple):
                if not self.label_matcher:
                    return False
                label_str, single_lisn = item_to_be_matched
                label_suc, label_res = self.label_matcher.match_string(label_str)
                if label_suc:
                    info_dict.update(label_res)
                else:
                    return False
            else:
                if self.label_matcher:
                    return False
                single_lisn = item_to_be_matched

            single_suc, single_res = self.lisn_matcher.match(single_lisn)
            if single_suc:
                info_dict.update(single_res)
                return _follow_cont(cdr(lisn_llist), seq_cont)
            else:
                return False


class PosOr(PosMatcher):
    def __init__(self, mats, group_name=None, inherit_group=False):
        self.mats = mats
        self.group_name = group_name
        self.inherit_group = inherit_group

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        for mat in self.mats:
            sub_dict = {}
            if mat._match_pos(lisn_llist, seq_cont, sub_dict):
                if self.group_name:
                    info_dict[self.group_name] = sub_dict
                elif self.inherit_group:
                    info_dict.update(sub_dict)
                return True
        return False

class PosNone(PosMatcher):
    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        if lisn_llist is None:
            return _follow_cont(lisn_llist, seq_cont)
        else:
            return False


class PosGroup(PosMatcher):
    def __init__(self, mats, group_name=None, inherit_group=False):
        assert len(mats) >= 1
        self.mats = mats 
        self.group_name = group_name
        self.inherit_group = inherit_group
        
    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        sub_dict = {}

        res_seq_cont = seq_cont
        for matcher in self.mats[1:][::-1]:
            res_seq_cont = cons((matcher, sub_dict),
                                res_seq_cont)
        if self.mats[0]._match_pos(lisn_llist, res_seq_cont, sub_dict):
            if self.group_name:
                info_dict[self.group_name] = sub_dict
            elif self.inherit_group:
                info_dict.update(sub_dict)
            return True
        else:
            return False


class PosOptional(PosMatcher):
    def __init__(self, submat, group_name=None, inherit_group=False):
        self.submat = submat
        self.group_name = group_name
        self.inherit_group = inherit_group

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        def set_group(sub_dict=None):
            if self.group_name:
                info_dict[self.group_name] = sub_dict
            elif self.inherit_group and sub_dict:
                info_dict.update(sub_dict)

        if lisn_llist is None:
            set_group(None)
            return _follow_cont(lisn_llist, seq_cont)
        else:
            sub_dict = {}
            submat = self.submat
            if submat._match_pos(lisn_llist, seq_cont, sub_dict):
                set_group(sub_dict)
                return True
            else:
                set_group(None)
                return _follow_cont(lisn_llist, seq_cont)
            

class PosKleeneStar(PosMatcher):
    def __init__(self, submat, group_name=None, inherit_group=False):
        self.submat = submat 
        self.group_name = group_name
        self.inherit_group = inherit_group

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        if self.group_name and self.group_name not in info_dict:
            info_dict[self.group_name] = None 
            
        submat = self.submat
        sub_dict = {}
        if self.submat._match_pos(lisn_llist, cons((self, info_dict), seq_cont), sub_dict):
            consed_info = cons(sub_dict, info_dict[self.group_name])
            if self.group_name:
                info_dict[self.group_name] = consed_info
            return True
        else:
            return _follow_cont(lisn_llist, seq_cont)


class PosKleenePlus(PosMatcher):
    def __init__(self, submat, group_name=None, inherit_group=False):
        self.submat = submat 
        self.group_name = group_name
        self.inherit_group = inherit_group

    def _match_pos(self, lisn_llist, seq_cont, info_dict):
        if self.group_name and self.group_name not in info_dict:
            info_dict[self.group_name] = None 
            
        submat = self.submat
        sub_dict = {}
        
        if self.submat._match_pos(lisn_llist,
                                 cons((PosKleeneStar(self.submat,
                                                     self.group_name),
                                       info_dict),
                                      seq_cont),
                                 sub_dict):
            if self.group_name:
                info_dict[self.group_name] = cons(sub_dict, info_dict[self.group_name])
            return True
        else:
            return False


class KwDictStyleMatcher(KeywordMatcher):
    def __init__(self, matcher_dict, group_name, exact=True):
        self.matcher_dict = matcher_dict
        self.group_name = group_name
        self.exact = exact

    def match_kw(self, name_lisn_pairs):
        actual_name_map = {}
        for s, lisn in name_lisn_pairs:
            # duplicated
            if s in actual_name_map:
                return (False, None) 
            actual_name_map[s] = lisn

        matcher_name_set = set(self.matcher_dict.keys())
        actual_name_set = set(actual_name_map.keys())
        # inclusion check
        if self.exact:
            if not (matcher_name_set.issubset(actual_name_set) and
                    matcher_name_set.issuperset(actual_name_set)):
                return (False, None)
        else:
            if not matcher_name_set.issubset(actual_name_set):
                return (False, None)

        sub_dict = {}
        for _str, matcher in self.matcher_dict.items():
            suc, _dict = matcher.match(actual_name_map[_str])
            if not suc:
                return (False, None)
            sub_dict.update(_dict)

        if not self.exact:
            rest_dict = {}
            for rest_key in actual_name_set.difference(matcher_name_set):
                rest_dict[rest_key] = actual_name_map[rest_key]
            sub_dict["__rest__"] = rest_dict

        if self.group_name:
            result = {self.group_name: sub_dict}
        else:
            result = sub_dict
        return (True, result)


class KwSeqStyleMatcher(KeywordMatcher):
    def __init__(self, pos_matcher, group_name):
        self.pos_matcher = pos_matcher
        self.group_name = group_name

    def match_kw(self, name_lisn_pairs):
        suc, sub_dict = self.pos_matcher.match_pos(name_lisn_pairs)
        if not suc:
            return (False, None)
        if self.group_name:
            return (True, {self.group_name: sub_dict})
        else:
            return (True, sub_dict)

#
# Pattern compile functions
#

def _suite_to_list(suite):
    assert suite["type"] == "suite"

    def filter_fun(obj):
        if obj["is_arrow"]:
            return (obj["arrow_lstring"], obj["param"])
        else:
            return obj["param"]

    return map(filter_fun, suite["exprs"])


def _force_only_pargs_there(xexpr, number=1):
    if xexpr["type"] != "xexpr":
        return None

    arg_info = xexpr["arg_info"]
    if arg_info["kargs"] or \
       arg_info["has_star"] or \
       arg_info["has_dstar"] or \
       arg_info["has_amp"]  or \
       arg_info["has_damp"]:
        return None
    else:
        pargs = arg_info["pargs"]
        if isinstance(number, (int, long)):
            if len(pargs) == number:
                return tuple(pargs)
            else:
                return None
        else:
            if len(pargs) in number:
                return tuple(pargs)
            else:
                return None


def _get_group_name(pat):
    arg_info = pat["arg_info"]
    maybe_pargs = _force_only_pargs_there(pat, xrange(2))
    if maybe_pargs is None:
        raise Exception("Bad form: too many args for special node")

    if len(maybe_pargs) == 0:
        group_name = None
    else:
        if not maybe_pargs[0]["type"] == "name":
            raise Exception("Bad form: group name should be specified by a name node")
        group_name = maybe_pargs[0]["name"]

    if len(arg_info["kargs"]) > 0 or \
       arg_info["has_star"] or \
       arg_info["has_dstar"] or \
       arg_info["has_amp"] or \
       arg_info["has_damp"]:
        raise Exception("Bad form")
    return group_name


def _compile_pos_matcher(pats, group_name, inherit_group):
    '''
    pats: (lisn | (string, lisn)) list -> PosMatcher
    '''
    def special_pat(pat, pat_label):
        if pat["type"] != "xexpr" or pat["head_expr"]["type"] != "name":
            return None

        head_name = pat["head_expr"]["name"]
        arg_info = pat["arg_info"]
        has_head_label = pat["has_head_label"]
        has_vert_suite = pat["has_vert_suite"]
        pargs = arg_info["pargs"]

        if has_head_label:
            return None

        def get_submat(sub_group_name, sub_inherit_group):
            return _compile_pos_matcher(_suite_to_list(pat["vert_suite"]),
                                        sub_group_name,
                                        sub_inherit_group)
        def get_selective_submats():
            result = []
            for obj in _suite_to_list(pat["vert_suite"]):
                if isinstance(obj, tuple):
                    result.append(PosSingle(compile_pattern(obj[1]),
                                            make_string_matcher(obj[0])))
                else:
                    result.append(_compile_pos_matcher([obj], None, True))
            return result
            

        if head_name == "__optional__":
            pass
        elif head_name == "__or__":
            pass
        elif head_name == "__group__":
            pass
        elif head_name == "__kleene_star__":
            pass
        elif head_name == "__kleene_plus__":
            pass
        else:
            return None

        ##
        ## fail-safe line
        ##

        if pat_label:
            raise Exception("Special pattern cannot be labeled")

        group_name = _get_group_name(pat)
        if head_name == "__optional__":
            return PosOptional(get_submat(None, True), 
                               group_name,
                               inherit_group)
        elif head_name == "__kleene_star__":
            return PosKleeneStar(get_submat(None, True),
                                 group_name,
                                 inherit_group)
        elif head_name == "__kleene_plus__":
            return PosKleenePlus(get_submat(None, True),
                                 group_name,
                                 inherit_group)
        elif head_name == "__or__":
            return PosOr(get_selective_submats(), group_name, inherit_group)
        elif head_name == "__group__":
            return PosGroup(get_selective_submats(), group_name, inherit_group)
        else:
            return None

    result = []
    for pat in pats:
        if isinstance(pat, tuple):
            pat_label, pat  = pat
        else:
            pat_label = None

        special_node_maybe = special_pat(pat, pat_label)
        if special_node_maybe:
            result.append(special_node_maybe)
        else:
            if pat_label is None:
                label_matcher = None
            else:
                label_matcher = make_string_matcher(pat_label)
            result.append(PosSingle(compile_pattern(pat), label_matcher))

    if len(result) == 0:
        return PosNone()
    elif len(result) == 1 and inherit_group:
        return result[0]
    else:
        return PosGroup(result, group_name, inherit_group)


def _compile_kw_matcher(kargs):
    if len(kargs) >= 2:
        raise Exception("Bad form: Keyword Matcher")
    if len(kargs) == 1 and kargs[0][0] != "keyword":
        raise Exception("Bad form: name of keyword matcher should be 'keyword'")

    if len(kargs) == 1:
        _, spec = kargs[0]
        if spec["type"] != "xexpr" or \
           spec["has_head_label"] or \
           spec["head_expr"]["type"] != "name":
            raise Exception("Bad form: Keyword Matcher")

        head_name = spec["head_expr"]["name"]
        group_name = _get_group_name(spec)
        if head_name == "dict":
            if spec["has_vert_suite"]:
                sub_pat_list = _suite_to_list(spec["vert_suite"])
                # duplication test
                name_set = set()
                str_matcher_pairs = []
                for obj in sub_pat_list:
                    if isinstance(obj, tuple):
                        _str, pat = obj
                        if _str in name_set:
                            raise Exception("Bad form: duplicated key in dict matcher")
                        name_set.add(_str)
                        matcher = compile_pattern(pat)
                        str_matcher_pairs.append((_str, matcher))
                    else:
                        raise Exception("Bad form: an item of suite of keyword definition should be 'name -> lisn'")
                return KwDictStyleMatcher(dict(str_matcher_pairs), group_name, group_name is None)
            else:
                return KwDictStyleMatcher({}, group_name, group_name is None)
        elif head_name == "seq":
            if spec["has_vert_suite"]:
                node_list = _suite_to_list(spec["vert_suite"])
                pos_matcher = _compile_pos_matcher(node_list, None, True)
                return KwSeqStyleMatcher(pos_matcher, group_name)
            else:
                return None
        else:
            raise Exception("Bad form: should be dict-style or seq-style")
        
    else:
        return None


def _compile_xexpr_pattern(pat_xexpr):
    # let
    head_label_matcher = None 
    if pat_xexpr["has_head_label"]:
        head_label_matcher = make_string_matcher(pat_xexpr["head_label"])
    # let
    head_expr_matcher = compile_pattern(pat_xexpr["head_expr"])
    arg_info = pat_xexpr["arg_info"]

    # let
    pos_matcher = _compile_pos_matcher(arg_info['pargs'], None, True)
    # let
    kw_matcher = _compile_kw_matcher(arg_info['kargs'])
    if arg_info['has_star']:
        star_matcher = _compile_pos_matcher([arg_info['star']], None, True)
    else:
        star_matcher = None
    if arg_info['has_dstar']:
        dstar_matcher = _compile_pos_matcher([arg_info['dstar']], None, True)
    else:
        dstar_matcher = None
    if arg_info['has_amp']:
        amp_matcher = _compile_pos_matcher([arg_info['amp']], None, True)
    else:
        amp_matcher = None
    if arg_info['has_damp']:
        damp_matcher = _compile_pos_matcher([arg_info['damp']], None, True)
    else:
        damp_matcher = None

    ## vert_suite
    if pat_xexpr["has_vert_suite"]:
        vert_suite_matcher = _compile_pos_matcher(
                _suite_to_list(pat_xexpr["vert_suite"]),
                None,
                True)
    else:
        vert_suite_matcher = None
    
    return XExprMatcher(head_expr_matcher,
                        head_label_matcher,
                        pos_matcher,
                        kw_matcher,
                        star_matcher,
                        dstar_matcher,
                        amp_matcher,
                        damp_matcher,
                        vert_suite_matcher)


def _compile_name_pattern(pat_name):
    return make_string_matcher(pat_name["name"])


def _compile_string_pattern(pat_s):
    return make_string_matcher(pat_s)


def compile_pattern(pat_lisn):
    '''
    lisn -> LISNMatcher
    '''
    type_name = pat_lisn["type"]
    if type_name == "name":
        return _compile_name_pattern(pat_lisn)
    elif type_name == "xexpr":
        return _compile_xexpr_pattern(pat_lisn)
    else:
        raise Exception("NOT REACHABLE")



class LISNPattern:
    def __init__(self, pattern_decl_fun):
        self.test_fun_pairs = []
        self._default_placeholder = lambda: None
        self.default_case_fun = self._default_placeholder 

        def add_case(fun):
            if fun.__doc__ is None:
                raise ValueError("case's docstring should be filled with pattern string")
            pat_string = _pull_left_string(fun.__doc__)
            pat_suite = loads(pat_string)

            if len(pat_suite["exprs"]) >= 2:
                raise ValueError("Too many pattern nodes in pattern docstring")
            if len(pat_suite["exprs"]) == 0:
                raise ValueError("No pattern node in pattern docstring")

            obj = pat_suite["exprs"][0]
            pat_lisn = obj["param"]

            matcher = compile_pattern(pat_lisn)
            self.test_fun_pairs.append((matcher, fun))

        def default_case(fun):
            self.default_case_fun = fun

        pattern_decl_fun(add_case, default_case)

    def __call__(self, lisn):
        for test_pat, fun in self.test_fun_pairs:
            success, result = test_pat.match(lisn)
            if success:
                return fun(**result)

        if self.default_case_fun is self._default_placeholder:
            raise LISNPatternException("No pattern is matched"
                                       " with given lisn object")
        else:
            return self.default_case_fun()
