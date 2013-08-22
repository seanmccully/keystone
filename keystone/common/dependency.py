# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

REGISTRY = {}

_future_dependencies = {}


class UnresolvableDependencyException(Exception):
    def __init__(self, name):
        msg = 'Unregistered dependency: %s' % name
        super(UnresolvableDependencyException, self).__init__(msg)


def provider(name):
    """Register the wrapped dependency provider under the specified name."""
    def wrapper(cls):
        def wrapped(init):
            def __wrapped_init__(self, *args, **kwargs):
                """Initialize the wrapped object and add it to the registry."""
                init(self, *args, **kwargs)
                REGISTRY[name] = self

                resolve_future_dependencies(name)

            return __wrapped_init__

        cls.__init__ = wrapped(cls.__init__)
        return cls

    return wrapper


def requires(*dependencies):
    """Inject specified dependencies from the registry into the instance."""
    def wrapper(self, *args, **kwargs):
        """Inject each dependency from the registry."""
        self.__wrapped_init__(*args, **kwargs)

        for dependency in self._dependencies:
            if dependency not in REGISTRY:
                if dependency in _future_dependencies:
                    _future_dependencies[dependency] += [self]
                else:
                    _future_dependencies[dependency] = [self]

                continue

            setattr(self, dependency, REGISTRY[dependency])

    def wrapped(cls):
        """Note the required dependencies on the object for later injection.

        The dependencies of the parent class are combined with that of the
        child class to create a new set of dependencies.
        """
        existing_dependencies = getattr(cls, '_dependencies', set())
        cls._dependencies = existing_dependencies.union(dependencies)
        if not hasattr(cls, '__wrapped_init__'):
            cls.__wrapped_init__ = cls.__init__
            cls.__init__ = wrapper
        return cls

    return wrapped


def resolve_future_dependencies(provider_name=None):
    if provider_name:
        targets = _future_dependencies.pop(provider_name, [])

        for target in targets:
            setattr(target, provider_name, REGISTRY[provider_name])

        return

    try:
        for dependency, targets in _future_dependencies.iteritems():
            if dependency not in REGISTRY:
                raise UnresolvableDependencyException(dependency)

            for target in targets:
                setattr(target, dependency, REGISTRY[dependency])
    finally:
        _future_dependencies.clear()


def reset():
    """Reset the registry of providers.

    This is useful for unit testing to ensure that tests don't use providers
    from previous tests.
    """

    REGISTRY.clear()
    _future_dependencies.clear()
