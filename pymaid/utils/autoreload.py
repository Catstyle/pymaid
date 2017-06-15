# -----------------------------------------------------------------------------
#   Copyright (C) 2000 Thomas Heller
#   Copyright (C) 2008 Pauli Virtanen <pav@iki.fi>
#   Copyright (C) 2012  The IPython Development Team
#
#   Distributed under the terms of the BSD License.  The full license is in
#   the file COPYING, distributed as part of this software.
# -----------------------------------------------------------------------------
#
#  This IPython module is written by Pauli Virtanen, based on the autoreload
#  code by Thomas Heller.

# -----------------------------------------------------------------------------
#  Imports
# -----------------------------------------------------------------------------

from __future__ import print_function

import os
import sys
from traceback import format_exc
import types
import weakref
from importlib import import_module

try:
    # Reload is not defined by default in Python3.
    reload
except NameError:
    from imp import reload

try:
    try:
        # Python 3.2, see PEP 3147
        from importlib.util import source_from_cache
    except ImportError:
        # deprecated since 3.4
        from imp import source_from_cache
except ImportError:
    # Python <= 3.1: .pyc files go next to .py
    def source_from_cache(path):
        basename, ext = os.path.splitext(path)
        if ext not in ('.pyc', '.pyo'):
            raise ValueError('Not a cached Python file extension', ext)
        # Should we look for .pyw files?
        return basename + '.py'

if sys.version_info[0] >= 3:
    PY3 = True
else:
    PY3 = False

# ------------------------------------------------------------------------------
# Autoreload functionality
# ------------------------------------------------------------------------------


class ModuleReloader(object):

    enabled = False
    """Whether this reloader is enabled"""

    check_all = True
    """Autoreload all modules, not just those listed in 'modules'"""

    def __init__(self):
        # Modules that failed to reload: {module: mtime-on-failed-reload, ...}
        self.failed = {}
        # Modules specially marked as autoreloadable.
        self.modules = {}
        # Modules specially marked as not autoreloadable.
        self.skip_modules = {}
        # (module-name, name) -> weakref, for replacing old code objects
        self.old_objects = {}
        # Module modification timestamps
        self.modules_mtimes = {}

        # Cache module modification times
        self.check(check_all=True, do_reload=False)

    def mark_module_skipped(self, module_name):
        """Skip reloading the named module in the future"""
        try:
            del self.modules[module_name]
        except KeyError:
            pass
        self.skip_modules[module_name] = True

    def mark_module_reloadable(self, module_name):
        """Reload the named module in the future (if it is imported)"""
        try:
            del self.skip_modules[module_name]
        except KeyError:
            pass
        self.modules[module_name] = True

    def aimport_module(self, module_name):
        """Import a module, and mark it reloadable

        Returns
        -------
        top_module : module
            The imported module if it is top-level, or the top-level
        top_name : module
            Name of top_module

        """
        self.mark_module_reloadable(module_name)

        import_module(module_name)
        top_name = module_name.split('.')[0]
        top_module = sys.modules[top_name]
        return top_module, top_name

    def filename_and_mtime(self, module):
        if not hasattr(module, '__file__') or module.__file__ is None:
            return None, None

        if getattr(module, '__name__', None) == '__main__':
            # we cannot reload(__main__)
            return None, None

        filename = module.__file__
        path, ext = os.path.splitext(filename)

        if ext.lower() == '.py':
            py_filename = filename
        else:
            try:
                py_filename = source_from_cache(filename)
            except ValueError:
                return None, None

        try:
            pymtime = os.stat(py_filename).st_mtime
        except OSError:
            return None, None

        return py_filename, pymtime

    def check(self, check_all=False, do_reload=True):
        """Check whether some modules need to be reloaded."""

        if not self.enabled and not check_all:
            return

        if check_all or self.check_all:
            modules = list(sys.modules.keys())
        else:
            modules = list(self.modules.keys())

        for modname in modules:
            m = sys.modules.get(modname, None)

            if modname in self.skip_modules:
                continue

            py_filename, pymtime = self.filename_and_mtime(m)
            if py_filename is None:
                continue

            try:
                if pymtime <= self.modules_mtimes[modname]:
                    continue
            except KeyError:
                self.modules_mtimes[modname] = pymtime
                continue
            else:
                if self.failed.get(py_filename, None) == pymtime:
                    continue

            self.modules_mtimes[modname] = pymtime

            # If we've reached this point, we should try to reload the module
            if do_reload:
                try:
                    superreload(m, reload, self.old_objects)
                    if py_filename in self.failed:
                        del self.failed[py_filename]
                except:
                    print(
                        "[autoreload of %s failed: %s]" % (modname, format_exc()),  # noqa
                        file=sys.stderr
                    )
                    self.failed[py_filename] = pymtime

# ------------------------------------------------------------------------------
# superreload
# ------------------------------------------------------------------------------


if PY3:
    func_attrs = ['__code__', '__defaults__', '__doc__',
                  '__closure__', '__globals__', '__dict__']
else:
    func_attrs = ['func_code', 'func_defaults', 'func_doc',
                  'func_closure', 'func_globals', 'func_dict']


def update_function(old, new):
    """Upgrade the code object of a function"""
    for name in func_attrs:
        try:
            setattr(old, name, getattr(new, name))
        except (AttributeError, TypeError):
            pass


def update_class(old, new):
    """Replace stuff in the __dict__ of a class, and upgrade
    method code objects"""
    for key in list(old.__dict__.keys()):
        old_obj = getattr(old, key)

        try:
            new_obj = getattr(new, key)
        except AttributeError:
            # obsolete attribute: remove it
            try:
                delattr(old, key)
            except (AttributeError, TypeError):
                pass
            continue

        if update_generic(old_obj, new_obj):
            continue

        try:
            setattr(old, key, getattr(new, key))
        except (AttributeError, TypeError):
            pass  # skip non-writable attributes


def update_property(old, new):
    """Replace get/set/del functions of a property"""
    update_generic(old.fdel, new.fdel)
    update_generic(old.fget, new.fget)
    update_generic(old.fset, new.fset)


def isinstance2(a, b, typ):
    return isinstance(a, typ) and isinstance(b, typ)


UPDATE_RULES = [
    (lambda a, b: isinstance2(a, b, type),
     update_class),
    (lambda a, b: isinstance2(a, b, types.FunctionType),
     update_function),
    (lambda a, b: isinstance2(a, b, property),
     update_property),
]


if PY3:
    UPDATE_RULES.extend([
        (lambda a, b: isinstance2(a, b, types.MethodType),
         lambda a, b: update_function(a.__func__, b.__func__)),
    ])
else:
    UPDATE_RULES.extend([
        (lambda a, b: isinstance2(a, b, types.ClassType),
         update_class),
        (lambda a, b: isinstance2(a, b, types.MethodType),
         lambda a, b: update_function(a.__func__, b.__func__)),
    ])


def update_generic(a, b):
    for type_check, update in UPDATE_RULES:
        if type_check(a, b):
            update(a, b)
            return True
    return False


class StrongRef(object):

    def __init__(self, obj):
        self.obj = obj

    def __call__(self):
        return self.obj


def superreload(module, reload=reload, old_objects={}):
    """Enhanced version of the builtin reload function.

    superreload remembers objects previously in the module, and

    - upgrades the class dictionary of every old class in the module
    - upgrades the code object of every old function and method
    - clears the module's namespace before reloading

    """

    # collect old objects in the module
    for name, obj in list(module.__dict__.items()):
        if not hasattr(obj, '__module__') or obj.__module__ != module.__name__:
            continue
        key = (module.__name__, name)
        try:
            old_objects.setdefault(key, []).append(weakref.ref(obj))
        except TypeError:
            # weakref doesn't work for all types;
            # create strong references for 'important' cases
            if not PY3 and isinstance(obj, types.ClassType):
                old_objects.setdefault(key, []).append(StrongRef(obj))

    # reload module
    try:
        # clear namespace first from old cruft
        old_dict = module.__dict__.copy()
        old_name = module.__name__
        module.__dict__.clear()
        module.__dict__['__name__'] = old_name
        module.__dict__['__loader__'] = old_dict['__loader__']
    except (TypeError, AttributeError, KeyError):
        pass

    try:
        module = reload(module)
    except:
        # restore module dictionary on failed reload
        module.__dict__.update(old_dict)
        raise

    # iterate over all objects and update functions & classes
    for name, new_obj in list(module.__dict__.items()):
        key = (module.__name__, name)
        if key not in old_objects:
            continue

        new_refs = []
        for old_ref in old_objects[key]:
            old_obj = old_ref()
            if old_obj is None:
                continue
            new_refs.append(old_ref)
            update_generic(old_obj, new_obj)

        if new_refs:
            old_objects[key] = new_refs
        else:
            del old_objects[key]

    return module
