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

"""Token provider interface."""


from keystone.common import dependency
from keystone.common import manager
from keystone import config
from keystone import exception
from keystone.openstack.common import log as logging


CONF = config.CONF
LOG = logging.getLogger(__name__)


# supported token versions
V2 = 'v2.0'
V3 = 'v3.0'
VERSIONS = frozenset([V2, V3])

# default token providers
PKI_PROVIDER = 'keystone.token.providers.pki.Provider'
UUID_PROVIDER = 'keystone.token.providers.uuid.Provider'


class UnsupportedTokenVersionException(Exception):
    """Token version is unrecognizable or unsupported."""
    pass


@dependency.provider('token_provider_api')
class Manager(manager.Manager):
    """Default pivot point for the token provider backend.

    See :mod:`keystone.common.manager.Manager` for more details on how this
    dynamically calls the backend.

    """

    @classmethod
    def get_token_provider(cls):
        """Return package path to the configured token provider.

        The value should come from ``keystone.conf`` ``[token] provider``,
        however this method ensures backwards compatibility for
        ``keystone.conf`` ``[signing] token_format`` until Havana + 2.

        Return the provider based on ``token_format`` if ``provider`` is not
        set. Otherwise, ignore ``token_format`` and return the configured
        ``provider`` instead.

        """
        if CONF.token.provider is not None:
            # NOTE(gyee): we are deprecating CONF.signing.token_format. This
            # code is to ensure the token provider configuration agrees with
            # CONF.signing.token_format.
            if ((CONF.signing.token_format == 'PKI' and
                    CONF.token.provider != PKI_PROVIDER or
                    (CONF.signing.token_format == 'UUID' and
                        CONF.token.provider != UUID_PROVIDER))):
                raise exception.UnexpectedError(
                    _('keystone.conf [signing] token_format (deprecated) '
                      'conflicts with keystone.conf [token] provider'))
            return CONF.token.provider
        else:
            if not CONF.signing.token_format:
                # No token provider and no format, so use default (PKI)
                return PKI_PROVIDER

            msg = _('keystone.conf [signing] token_format is deprecated in '
                    'favor of keystone.conf [token] provider')
            if CONF.signing.token_format == 'PKI':
                LOG.warning(msg)
                return PKI_PROVIDER
            elif CONF.signing.token_format == 'UUID':
                LOG.warning(msg)
                return UUID_PROVIDER
            else:
                raise exception.UnexpectedError(
                    _('Unrecognized keystone.conf [signing] token_format: '
                      'expected either \'UUID\' or \'PKI\''))

    def __init__(self):
        super(Manager, self).__init__(self.get_token_provider())


class Provider(object):
    """Interface description for a Token provider."""

    def get_token_version(self, token_data):
        """Return the version of the given token data.

        If the given token data is unrecognizable,
        UnsupportedTokenVersionException is raised.

        """
        raise exception.NotImplemented()

    def issue_v2_token(self, token_ref, roles_ref=None, catalog_ref=None):
        """Issue a V2 token.

        :param token_ref: token data to generate token from
        :type token_ref: dict
        :param roles_ref: optional roles list
        :type roles_ref: dict
        :param catalog_ref: optional catalog information
        :type catalog_ref: dict
        :return: (token_id, token_data)
        """
        raise exception.NotImplemented()

    def issue_v3_token(self, user_id, method_names, expires_at=None,
                       project_id=None, domain_id=None, auth_context=None,
                       metadata_ref=None, include_catalog=True):
        """Issue a V3 Token.

        :param user_id: identity of the user
        :type user_id: string
        :param method_names: names of authentication methods
        :type method_names: list
        :param expires_at: optional time the token will expire
        :type expires_at: string
        :param project_id: optional project identity
        :type project_id: string
        :param domain_id: optional domain identity
        :type domain_id: string
        :param auth_context: optional context from the authorization plugins
        :type auth_context: dict
        :param metadata_ref: optional metadata reference
        :type metadata_ref: dict
        :param include_catalog: optional, include the catalog in token data
        :type include_catalog: boolean
        :returns: (token_id, token_data)
        """
        raise exception.NotImplemented()

    def revoke_token(self, token_id):
        """Revoke a given token.

        :param token_id: identity of the token
        :type token_id: string
        :returns: None.
        """
        raise exception.NotImplemented()

    def validate_v2_token(self, token_id, belongs_to=None):
        """Validate the given V2 token and return the token data.

        Must raise Unauthorized exception if unable to validate token.

        :param token_id: identity of the token
        :type token_id: string
        :param belongs_to: optional identity of the scoped project to validate
        :type belongs_to: string
        :returns: token data
        :raises: keystone.exception.Unauthorized

        """
        raise exception.NotImplemented()

    def validate_v3_token(self, token_id):
        """Validate the given V3 token and return the token_data.

        :param token_id: identity of the token
        :type token_id: string
        :param belongs_to: project_id token belongs to
        :type belongs_to: string
        :returns: token data
        :raises: keystone.exception.Unauthorized
        """
        raise exception.NotImplemented()

    def check_v2_token(self, token_id, belongs_to=None):
        """Check the validity of the given V2 token.

        Must raise Unauthorized exception if unable to check token.

        :param token_id: identity of the token
        :type token_id: string
        :param belongs_to: identity of the scoped project to validate
        :type belongs_to: string
        :returns: None
        :raises: keystone.exception.Unauthorized

        """
        raise exception.NotImplemented()

    def check_v3_token(self, token_id):
        """Check the validity of the given V3 token.

        Must raise Unauthorized exception if unable to check token.

        :param token_id: identity of the token
        :type token_id: string
        :param belongs_to: identity of the scoped project to validate
        :type belongs_to: string
        :returns: None
        :raises: keystone.exception.Unauthorized

        """
        raise exception.NotImplemented()
