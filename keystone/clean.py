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

from keystone import exception


def check_length(property_name, value, min_length=1, max_length=64):
    if len(value) < min_length:
        if min_length == 1:
            msg = _("%s cannot be empty.") % property_name
        else:
            msg = (_("%(property_name)s cannot be less than "
                   "%(min_length)s characters.")) % locals()
        raise exception.ValidationError(msg)
    if len(value) > max_length:
        msg = (_("%(property_name)s should not be greater than "
               "%(max_length)s characters.")) % locals()
        raise exception.ValidationError(msg)


def check_type(property_name, value, expected_type, display_expected_type):
    if not isinstance(value, expected_type):
        msg = _("%(property_name)s is not a "
                "%(display_expected_type)s") % locals()
        raise exception.ValidationError(msg)


def check_enabled(property_name, enabled):
    # Allow int and it's subclass bool
    check_type('%s enabled' % property_name, enabled, int, 'boolean')
    return bool(enabled)


def check_name(property_name, name):
    check_type('%s name' % property_name, name, basestring, 'str or unicode')
    name = name.strip()
    check_length('%s name' % property_name, name)
    return name


def domain_name(name):
    return check_name('Domain', name)


def project_name(name):
    return check_name('Project', name)


def project_enabled(enabled):
    return check_enabled('Project', enabled)


def user_name(name):
    return check_name('User', name)


def user_enabled(enabled):
    return check_enabled('User', enabled)


def group_name(name):
    return check_name('Group', name)
