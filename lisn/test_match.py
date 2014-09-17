#!/usr/bin/env ipython
import unittest

from clisn import loads
from match import LISNPattern
from pprint import pprint

class PatternTest(unittest.TestCase):
    def test_very_basic_pattern(self):
        @LISNPattern
        def pat_vb(case, default):
            @case
            def A(res):
                '''
                FooBar
                '''
                return True

            @case
            def B(res):
                '''
                NAME$a
                '''
                return res['a']
        
            @case
            def C(res):
                '''
                $a
                '''
                return res['a']

        @LISNPattern
        def pat_node(case, default):
            @case
            def D(res):
                '''
                c(NAME$x)
                '''
                return res['x']
        
        foobar_lisn = loads("FooBar")["exprs"][0]["param"]
        b_lisn = loads("b")["exprs"][0]["param"]
        c_lisn = loads("c(a)")["exprs"][0]["param"]
        '''
        self.assertTrue(pat_vb(foobar_lisn))
        self.assertEqual(pat_vb(b_lisn), 'b')
        self.assertIs(pat_vb(c_lisn), c_lisn)
        self.assertEqual(pat_node(c_lisn), 'a')
        '''

    def test_basic_node(self):
        thunk_lisn = loads('thunk: a + 2')["exprs"][0]["param"]
        defvar_lisn = loads('defvar x: foo(1 + 2)')["exprs"][0]["param"]
        f_lisn = loads('f(parg_first, parg_second, \
                         label=karg, \
                         **dstar, &amp, &&damp)')["exprs"][0]["param"]

        @LISNPattern
        def pat_v(case, default):
            @case
            def a(res):
                '''
                thunk: $node
                '''
                return res['node']
            @case
            def b(res):
                '''
                defvar NAME$var_name:
                    $val_node
                '''
                return (res["var_name"], res["val_node"])

        @LISNPattern
        def pat_arg(case, default):
            @case
            def a(res):
                '''
                f>
                    parg_first
                    parg_second
                    keyword -> dict:
                        label -> karg
                    *__optional__:
                        star
                    **dstar
                    &amp
                    &&damp
                '''
                return True

        
        '''
        self.assertEqual(pat_v(thunk_lisn)["type"], "binop")
        var_name, val_node = pat_v(defvar_lisn)
        self.assertEqual(var_name, "x")
        self.assertEqual(val_node["head_expr"]["name"], "foo")
        self.assertTrue(pat_arg(f_lisn))
        '''

    def test_fun(self):
        fun_lisn = loads('''
def go(a, b, c, d=2, e=3, *f, **g, &h, &&i)
''')["exprs"][0]["param"]
    

        @LISNPattern
        def pat_fun(case, default):
            @case
            def case1(res):
                '''
                def NAME$funname>
                    __kleene_star__(pargs): NAME$argname
                    keyword -> dict(kargs)
                    *__optional__(star): NAME$argname
                    **__optional__(dstar): NAME$argname
                    &__optional__(amp): NAME$argname
                    &&__optional__(damp): NAME$argname
                --
                    __kleene_star__(body): $expr
                '''
                return res
            '''
        pprint(pat_fun(fun_lisn))
        '''

    def test_lets(self):
        lets_lisn = loads('''
lets>
    a -> 1
    a -> a + 1
    a -> a + 2
--
    a
''')["exprs"][0]["param"]

        @LISNPattern
        def pat_lets(case, default):
            @case
            def case1(res):
                '''
                lets>
                    keyword -> seq:
                        __kleene_star__(definition):
                            NAME$key -> $value
                --
                    __kleene_plus__(body): $expr
                '''
                return res
        '''
        pprint(pat_lets(lets_lisn))
        '''
    
    def test_or(self):
        yy_lisn = loads('''
yinyang:
    yin
    yang
    yang
    yin
''')["exprs"][0]["param"]
        @LISNPattern
        def pat_yinyang(case, default):
            @case
            def case1(res):
                '''
                yinyang:
                    __kleene_star__(list):
                        __or__:
                            __group__(yin):
                                yin
                            __group__(yang):
                                yang
                '''
                return res
        pprint(pat_yinyang(yy_lisn))

if __name__ == "__main__":
    unittest.main()


