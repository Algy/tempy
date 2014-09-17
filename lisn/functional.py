from functools import wraps
#
# LISP-style list (llist)
#

def cons(hd, tl):
    '''
    lisp-style pair cell
    '''
    return (hd, tl)


def list_to_llist(lst):
    result = None
    for idx in range(len(lst) - 1, -1, -1):
        result = cons(lst[idx], result)
    return result

def car(pair):
    if pair is None:
        raise TypeError("Cannot car None")
    else:
        return pair[0]
def cdr(pair):
    if pair is None:
        raise TypeError("Cannot cdr None")
    else:
        return pair[1]

def llist_to_list(llst):
    result = []
    pair = llst
    while pair is not None:
        result.append(car(pair))
        pair = cdr(pair)

    return result

def llist(*args):
    return list_to_llist(args)


def llmap(fun, llst):
    if llst is None:
        return None
    else:
        return cons(fun(car(llst)),
                    llmap(fun, cdr(llst)))


def llist_to_stream(llst):
    if llst is None:
        return null_stream
    else:
        return make_stream(car(llst))(lambda: llist_to_stream(cdr(llst)))
            

#
# Lazy
#

class Promise:
    '''
    Lazy Class
    Not to be confused with Premise class!
    This class is for lazy evaluation, while Premise is used for translation

    '''
    def __init__(self, fun, args=(), kwds={}):
        self.fun = fun
        self.args = args
        self.kwds = kwds

    def __call__(self):
        return self.force()

    def force(self):
        return self.fun(*self.args, **self.kwds)

class MemoizedPromise:
    '''
    Memoized Version of Lazy Class
    '''
    def __init__(self, fun, args=(), kwds={}):
        self.fun = fun
        self.args = args
        self.kwds = kwds
        self.tried = False
        self.result = None

    def __call__(self):
        return self.force()

    def force(self):
        if not self.tried:
            self.tried = True
            self.result = self.fun(*self.args, **self.kwds)
        return self.result

def delay(*app_args, **app_kwds):
    @wraps(delay)
    def decorator(fun):
        return Promise(fun, app_args, app_kwds)
    return decorator

def memoized_delay(*app_args, **app_kwds):
    @wraps(delay)
    def decorator(fun):
        return MemoizedPromise(fun, app_args, app_kwds)
    return decorator

def is_delayed(obj):
    return isinstance(obj, Promise)

#
# Stream
#

def make_stream(first_elem, memo=False):
    memo_box = []
    @wraps(make_stream)
    def inner(thunk):
        promise = (memoized_delay if memo else delay)()(thunk)
        return cons(first_elem, promise)
    return inner

null_stream = None
def is_stream_null(stream):
    return stream is null_stream


def stream_car(stream):
    return car(stream)


def stream_cdr(stream):
    return cdr(stream).force()


def stream_filter(fun, stream):
    first_filtered = None
    success = False
    while not is_stream_null(stream):
        car_elem = stream_car(stream)
        stream = stream_cdr(stream)
        if fun(car_elem):
            first_filtered = car_elem
            success = True
            break
    if not success:
        return null_stream

    return make_stream(first_filtered)(lambda: stream_filter(fun, stream))


def stream_map(fun, *args):
    if is_stream_null(args[0]):
        return null_stream
    first_arg_list = map(stream_car, args)
    first_elem = fun(*first_arg_list)
    @make_stream(first_elem)
    def next_stream():
        return stream_map(fun, *map(stream_cdr, args))
    return next_stream


def _stream_concat_iter(stream_llist, cur_stream):
    if is_stream_null(cur_stream) and stream_llist is None:
        return null_stream
    elif is_stream_null(cur_stream):
        return _stream_concat_iter(cdr(stream_llist), car(stream_llist))
    else:
        return make_stream(stream_car(cur_stream))(lambda: _stream_concat_iter(stream_llist, stream_cdr(cur_stream)))


def _stream_concat_llist(stream_llist):
    if stream_llist is None:
        return null_stream
    else:
        return _stream_concat_iter(cdr(stream_llist), car(stream_llist))


def stream_concat(streams):
    return _stream_concat_llist(list_to_llist(streams))


def _stream_map_append_iter(fun, stream, elem_stream):
    if is_stream_null(elem_stream):
        if is_stream_null(stream):
            return null_stream
        else:
            return stream_map_append(fun, stream_cdr(stream))
    else:
        first_elem = stream_car(elem_stream)
        return make_stream(first_elem)(lambda: _stream_map_append_iter(fun,
                                                                       stream,
                                                                       stream_cdr(elem_stream)))


def stream_map_append(fun, stream):
    '''
    ('a -> 'b stream) x 'a stream -> 'b stream

    fun: 'a -> 'b stream
    stream: 'a stream
    '''
    if is_stream_null(stream):
        return null_stream
    else:
        return _stream_map_append_iter(fun, stream, fun(stream_car(stream)))


def sieve(stream):
    elem = stream_car(stream)
    return make_stream(elem)(lambda: sieve(stream_filter(lambda x: x % elem != 0, stream_cdr(stream))))
