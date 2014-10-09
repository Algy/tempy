from clisn import loads, loads_file, \
                  LISNSyntaxException, LISNLexerException, LISNParserException

def load_one(s):
    suite = loads(s)
    assert suite["type"] == "suite"
    expr_list = suite["exprs"]
    if len(expr_list) == 0:
        raise LISNSyntaxException("No expression in source", {"sline": 0, "eline": 0, "scol": 0, "ecol": 0})
    elif len(expr_list) > 1:
        raise LISNSyntaxException("Too many expressions found", expr_list[2]["param"]["locinfo"])

    obj = expr_list[0]

    if obj["is_arrow"]:
        raise LISNSyntaxException("Arrow expression cannot be accepted", obj["param"]["locinfo"])
    return obj["param"]
