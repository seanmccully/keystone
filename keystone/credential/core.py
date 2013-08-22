# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack LLC
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

"""Main entry point into the Credentials service."""

from keystone.common import dependency
from keystone.common import logging
from keystone.common import manager
from keystone import config
from keystone import exception


CONF = config.CONF

LOG = logging.getLogger(__name__)


@dependency.provider('credential_api')
class Manager(manager.Manager):
    """Default pivot point for the Credential backend.

    See :mod:`keystone.common.manager.Manager` for more details on how this
    dynamically calls the backend.

    """

    def __init__(self):
        super(Manager, self).__init__(CONF.credential.driver)


class Driver(object):
    # credential crud

    def create_credential(self, credential_id, credential):
        """Creates a new credential.

        :raises: keystone.exception.Conflict

        """
        raise exception.NotImplemented()

    def list_credentials(self):
        """List all credentials in the system.

        :returns: a list of credential_refs or an empty list.

        """
        raise exception.NotImplemented()

    def get_credential(self, credential_id):
        """Get a credential by ID.

        :returns: credential_ref
        :raises: keystone.exception.CredentialNotFound

        """
        raise exception.NotImplemented()

    def update_credential(self, credential_id, credential):
        """Updates an existing credential.

        :raises: keystone.exception.CredentialNotFound,
                 keystone.exception.Conflict

        """
        raise exception.NotImplemented()

    def delete_credential(self, credential_id):
        """Deletes an existing credential.

        :raises: keystone.exception.CredentialNotFound

        """
        raise exception.NotImplemented()
