# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation
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

"""Extensions supporting OAuth1."""

from keystone.common import controller
from keystone.common import dependency
from keystone.common import wsgi
from keystone import config
from keystone.contrib.oauth1 import core as oauth1
from keystone import exception
from keystone.openstack.common import jsonutils
from keystone.openstack.common import timeutils


CONF = config.CONF


@dependency.requires('oauth_api', 'token_api')
class ConsumerCrudV3(controller.V3Controller):
    collection_name = 'consumers'
    member_name = 'consumer'

    def create_consumer(self, context, consumer):
        ref = self._assign_unique_id(self._normalize_dict(consumer))
        consumer_ref = self.oauth_api.create_consumer(ref)
        return ConsumerCrudV3.wrap_member(context, consumer_ref)

    def update_consumer(self, context, consumer_id, consumer):
        self._require_matching_id(consumer_id, consumer)
        ref = self._normalize_dict(consumer)
        self._validate_consumer_ref(consumer)
        ref = self.oauth_api.update_consumer(consumer_id, consumer)
        return ConsumerCrudV3.wrap_member(context, ref)

    def list_consumers(self, context):
        ref = self.oauth_api.list_consumers()
        return ConsumerCrudV3.wrap_collection(context, ref)

    def get_consumer(self, context, consumer_id):
        ref = self.oauth_api.get_consumer(consumer_id)
        return ConsumerCrudV3.wrap_member(context, ref)

    def delete_consumer(self, context, consumer_id):
        user_token_ref = self.token_api.get_token(context['token_id'])
        user_id = user_token_ref['user'].get('id')
        self.token_api.delete_tokens(user_id, consumer_id=consumer_id)
        self.oauth_api.delete_consumer(consumer_id)

    def _validate_consumer_ref(self, consumer):
        if 'secret' in consumer:
            msg = _('Cannot change consumer secret')
            raise exception.ValidationError(message=msg)


@dependency.requires('oauth_api')
class AccessTokenCrudV3(controller.V3Controller):
    collection_name = 'access_tokens'
    member_name = 'access_token'

    def get_access_token(self, context, user_id, access_token_id):
        access_token = self.oauth_api.get_access_token(access_token_id)
        if access_token['authorizing_user_id'] != user_id:
            raise exception.NotFound()
        access_token = self._format_token_entity(access_token)
        return AccessTokenCrudV3.wrap_member(context, access_token)

    def list_access_tokens(self, context, user_id):
        refs = self.oauth_api.list_access_tokens(user_id)
        formatted_refs = ([self._format_token_entity(x) for x in refs])
        return AccessTokenCrudV3.wrap_collection(context, formatted_refs)

    def delete_access_token(self, context, user_id, access_token_id):
        access_token = self.oauth_api.get_access_token(access_token_id)
        consumer_id = access_token['consumer_id']
        self.token_api.delete_tokens(user_id, consumer_id=consumer_id)
        return self.oauth_api.delete_access_token(
            user_id, access_token_id)

    def _format_token_entity(self, entity):

        formatted_entity = entity.copy()
        access_token_id = formatted_entity['id']
        user_id = ""
        if 'requested_roles' in entity:
            formatted_entity.pop('requested_roles')
        if 'access_secret' in entity:
            formatted_entity.pop('access_secret')
        if 'authorizing_user_id' in entity:
            user_id = formatted_entity['authorizing_user_id']

        url = ('/users/%(user_id)s/OS-OAUTH1/access_tokens/%(access_token_id)s'
               '/roles' % {'user_id': user_id,
                           'access_token_id': access_token_id})

        formatted_entity.setdefault('links', {})
        formatted_entity['links']['roles'] = (self.base_url(url))

        return formatted_entity


@dependency.requires('oauth_api')
class AccessTokenRolesV3(controller.V3Controller):
    collection_name = 'roles'
    member_name = 'role'

    def list_access_token_roles(self, context, user_id, access_token_id):
        access_token = self.oauth_api.get_access_token(access_token_id)
        if access_token['authorizing_user_id'] != user_id:
            raise exception.NotFound()
        roles = access_token['requested_roles']
        roles_refs = jsonutils.loads(roles)
        formatted_refs = ([self._format_role_entity(x) for x in roles_refs])
        return AccessTokenRolesV3.wrap_collection(context, formatted_refs)

    def get_access_token_role(self, context, user_id,
                              access_token_id, role_id):
        access_token = self.oauth_api.get_access_token(access_token_id)
        if access_token['authorizing_user_id'] != user_id:
            raise exception.Unauthorized(_('User IDs do not match'))
        roles = access_token['requested_roles']
        roles_dict = jsonutils.loads(roles)
        for role in roles_dict:
            if role['id'] == role_id:
                role = self._format_role_entity(role)
                return AccessTokenRolesV3.wrap_member(context, role)
        raise exception.RoleNotFound(_('Could not find role'))

    def _format_role_entity(self, entity):

        formatted_entity = entity.copy()
        if 'description' in entity:
            formatted_entity.pop('description')
        if 'enabled' in entity:
            formatted_entity.pop('enabled')
        return formatted_entity


@dependency.requires('oauth_api', 'token_api', 'identity_api',
                     'token_provider_api', 'assignment_api')
class OAuthControllerV3(controller.V3Controller):
    collection_name = 'not_used'
    member_name = 'not_used'

    def create_request_token(self, context):
        headers = context['headers']
        oauth_headers = oauth1.get_oauth_headers(headers)
        consumer_id = oauth_headers.get('oauth_consumer_key')
        requested_role_ids = headers.get('Requested-Role-Ids')
        requested_project_id = headers.get('Requested-Project-Id')
        if not consumer_id:
            raise exception.ValidationError(
                attribute='oauth_consumer_key', target='request')
        if not requested_role_ids:
            raise exception.ValidationError(
                attribute='requested_role_ids', target='request')
        if not requested_project_id:
            raise exception.ValidationError(
                attribute='requested_project_id', target='request')

        req_role_ids = requested_role_ids.split(',')
        consumer_ref = self.oauth_api._get_consumer(consumer_id)
        consumer = oauth1.Consumer(key=consumer_ref['id'],
                                   secret=consumer_ref['secret'])

        url = oauth1.rebuild_url(context['path'])
        oauth_request = oauth1.Request.from_request(
            http_method='POST',
            http_url=url,
            headers=context['headers'],
            query_string=context['query_string'],
            parameters={'requested_role_ids': requested_role_ids,
                        'requested_project_id': requested_project_id})
        oauth_server = oauth1.Server()
        oauth_server.add_signature_method(oauth1.SignatureMethod_HMAC_SHA1())
        params = oauth_server.verify_request(oauth_request,
                                             consumer,
                                             token=None)

        project_params = params['requested_project_id']
        if project_params != requested_project_id:
            msg = _('Non-oauth parameter - project, do not match')
            raise exception.Unauthorized(message=msg)

        roles_params = params['requested_role_ids']
        roles_params_list = roles_params.split(',')
        if roles_params_list != req_role_ids:
            msg = _('Non-oauth parameter - roles, do not match')
            raise exception.Unauthorized(message=msg)

        req_role_list = list()
        all_roles = self.identity_api.list_roles()
        for role in all_roles:
            for req_role in req_role_ids:
                if role['id'] == req_role:
                    req_role_list.append(role)

        if len(req_role_list) == 0:
            msg = _('could not find matching roles for provided role ids')
            raise exception.Unauthorized(message=msg)

        json_roles = jsonutils.dumps(req_role_list)
        request_token_duration = CONF.oauth1.request_token_duration
        token_ref = self.oauth_api.create_request_token(consumer_id,
                                                        json_roles,
                                                        requested_project_id,
                                                        request_token_duration)

        result = ('oauth_token=%(key)s&oauth_token_secret=%(secret)s'
                  % {'key': token_ref['id'],
                     'secret': token_ref['request_secret']})

        if CONF.oauth1.request_token_duration:
            expiry_bit = '&oauth_expires_at=%s' % token_ref['expires_at']
            result += expiry_bit

        headers = [('Content-Type', 'application/x-www-urlformencoded')]
        response = wsgi.render_response(result,
                                        status=(201, 'Created'),
                                        headers=headers)

        return response

    def create_access_token(self, context):
        headers = context['headers']
        oauth_headers = oauth1.get_oauth_headers(headers)
        consumer_id = oauth_headers.get('oauth_consumer_key')
        request_token_id = oauth_headers.get('oauth_token')
        oauth_verifier = oauth_headers.get('oauth_verifier')

        if not consumer_id:
            raise exception.ValidationError(
                attribute='oauth_consumer_key', target='request')
        if not request_token_id:
            raise exception.ValidationError(
                attribute='oauth_token', target='request')
        if not oauth_verifier:
            raise exception.ValidationError(
                attribute='oauth_verifier', target='request')

        consumer = self.oauth_api._get_consumer(consumer_id)
        req_token = self.oauth_api.get_request_token(
            request_token_id)

        expires_at = req_token['expires_at']
        if expires_at:
            now = timeutils.utcnow()
            expires = timeutils.normalize_time(
                timeutils.parse_isotime(expires_at))
            if now > expires:
                raise exception.Unauthorized(_('Request token is expired'))

        consumer_obj = oauth1.Consumer(key=consumer['id'],
                                       secret=consumer['secret'])
        req_token_obj = oauth1.Token(key=req_token['id'],
                                     secret=req_token['request_secret'])
        req_token_obj.set_verifier(oauth_verifier)

        url = oauth1.rebuild_url(context['path'])
        oauth_request = oauth1.Request.from_request(
            http_method='POST',
            http_url=url,
            headers=context['headers'],
            query_string=context['query_string'])
        oauth_server = oauth1.Server()
        oauth_server.add_signature_method(oauth1.SignatureMethod_HMAC_SHA1())
        params = oauth_server.verify_request(oauth_request,
                                             consumer_obj,
                                             token=req_token_obj)

        if len(params) != 0:
            msg = _('There should not be any non-oauth parameters')
            raise exception.Unauthorized(message=msg)

        if req_token['consumer_id'] != consumer_id:
            msg = _('provided consumer key does not match stored consumer key')
            raise exception.Unauthorized(message=msg)

        if req_token['verifier'] != oauth_verifier:
            msg = _('provided verifier does not match stored verifier')
            raise exception.Unauthorized(message=msg)

        if req_token['id'] != request_token_id:
            msg = _('provided request key does not match stored request key')
            raise exception.Unauthorized(message=msg)

        if not req_token.get('authorizing_user_id'):
            msg = _('Request Token does not have an authorizing user id')
            raise exception.Unauthorized(message=msg)

        access_token_duration = CONF.oauth1.access_token_duration
        token_ref = self.oauth_api.create_access_token(request_token_id,
                                                       access_token_duration)

        result = ('oauth_token=%(key)s&oauth_token_secret=%(secret)s'
                  % {'key': token_ref['id'],
                     'secret': token_ref['access_secret']})

        if CONF.oauth1.access_token_duration:
            expiry_bit = '&oauth_expires_at=%s' % (token_ref['expires_at'])
            result += expiry_bit

        headers = [('Content-Type', 'application/x-www-urlformencoded')]
        response = wsgi.render_response(result,
                                        status=(201, 'Created'),
                                        headers=headers)

        return response

    def authorize(self, context, request_token_id):
        """An authenticated user is going to authorize a request token.

        As a security precaution, the requested roles must match those in
        the request token. Because this is in a CLI-only world at the moment,
        there is not another easy way to make sure the user knows which roles
        are being requested before authorizing.
        """

        req_token = self.oauth_api.get_request_token(request_token_id)

        expires_at = req_token['expires_at']
        if expires_at:
            now = timeutils.utcnow()
            expires = timeutils.normalize_time(
                timeutils.parse_isotime(expires_at))
            if now > expires:
                raise exception.Unauthorized(_('Request token is expired'))

        req_roles = req_token['requested_roles']
        req_roles_list = jsonutils.loads(req_roles)

        req_set = set()
        for x in req_roles_list:
            req_set.add(x['id'])

        # verify the authorizing user has the roles
        user_token = self.token_api.get_token(token_id=context['token_id'])
        credentials = user_token['metadata'].copy()
        user_roles = credentials.get('roles')
        user_id = user_token['user'].get('id')
        cred_set = set(user_roles)

        if not cred_set.issuperset(req_set):
            msg = _('authorizing user does not have role required')
            raise exception.Unauthorized(message=msg)

        # verify the user has the project too
        req_project_id = req_token['requested_project_id']
        user_projects = self.assignment_api.list_user_projects(user_id)
        found = False
        for user_project in user_projects:
            if user_project['id'] == req_project_id:
                found = True
                break
        if not found:
            msg = _("User is not a member of the requested project")
            raise exception.Unauthorized(message=msg)

        # finally authorize the token
        authed_token = self.oauth_api.authorize_request_token(
            request_token_id, user_id)

        to_return = {'token': {'oauth_verifier': authed_token['verifier']}}
        return to_return
