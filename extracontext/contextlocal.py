"""
Super context wrapper -

meant to be simpler to use and work in more scenarios than
Python's contextvars.

Usage:
Create one or more project-wide instances of "ContextLocal"
Decorate your functions, co-routines, worker-methods and generators
that should hold their own states with that instance's `context` method -

and use the instance as namespace for private variables that will be local
and non-local until entering another callable decorated
with `intance.context` - that will create a new, separated scope
visible inside  the decorated callable.


"""

import sys

from functools import wraps


__author__ = "João S. O. Bueno"
__license__ = "LGPL v. 3.0+"

class ContextError(AttributeError):
    pass


_sentinel = object()


class ContextLocal:

    def __init__(self):
        super().__setattr__("_registry", {})

    def _introspect_registry(self, name=None):

        f = sys._getframe(2)
        while f:
            hf = hash(f)
            if hf in self._registry:
                if not "$contexts" in f.f_locals:
                    del self._registry[hf]
                else:
                    namespace = f.f_locals["$contexts"][self._registry[hf]]
                    if name is None or name in namespace:
                        return namespace
            f = f.f_back
        if name:
            raise ContextError(f"{name !r} not defined in any previous context")
        raise ContextError("No previous context set")

    def _register_context(self, f):
        hf = hash(f)
        contexts_list = f.f_locals.setdefault("$contexts", [])
        contexts_list.append({})
        self._registry[hf] = len(contexts_list) - 1

    def __getattr__(self, name):
        try:
            namespace = self._introspect_registry(name)
            return namespace[name]
        except (ContextError, KeyError):
            raise AttributeError(f"Attribute not set: {name}")


    def __setattr__(self, name, value):
        try:
            namespace = self._introspect_registry()
        except ContextError:
            # Automatically creates a new namespace if not inside
            # any explicit denominated context:
            self._register_context(sys._getframe(1))
            namespace = self._introspect_registry()

            # namespace = self._registry[hash(sys._getframe(1))] = {}
        namespace[name] = value


    def __delattr__(self, name):
        namespace = self._introspect_registry(name)
        del namespace[name]

    def context(self, callable_):
        @wraps(callable_)
        def wrapper(*args, **kw):
            f = sys._getframe()
            self._register_context(f)
            # f = sys._getframe()
            # self._registry[hash(f)] = {}
            result = _sentinel
            try:
                result = callable_(*args, **kw)
            finally:
                del self._registry[hash(f)]
                # Setup context for generator or coroutine if one was returned:
                if result is not _sentinel:
                    frame = getattr(result, "gi_frame", getattr(result, "cr_frame", None))
                    if frame:
                        self._register_context(frame)

            return result
        return wrapper
