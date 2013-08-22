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

import uuid

from keystone import test

from keystone.common.sql import nova
from keystone.common.sql import util as sql_util
from keystone import config
from keystone.contrib.ec2.backends import sql as ec2_sql
from keystone import identity
from keystone.identity.backends import sql as identity_sql


CONF = config.CONF
DEFAULT_DOMAIN_ID = CONF.identity.default_domain_id


FIXTURE = {
    'users': [
        {'id': 'user1', 'name': 'uname1', 'password': 'acc1'},
        {'id': 'user4', 'name': 'uname4', 'password': 'acc1'},
        {'id': 'user2', 'name': 'uname2', 'password': 'acc2'},
        {'id': 'user3', 'name': 'uname3', 'password': 'acc3'},
    ],
    'roles': ['role1', 'role2', 'role3'],
    'role_user_tenant_list': [
        {'user_id': 'user1', 'role': 'role1', 'tenant_id': 'proj1'},
        {'user_id': 'user1', 'role': 'role2', 'tenant_id': 'proj1'},
        {'user_id': 'user4', 'role': 'role1', 'tenant_id': 'proj4'},
        {'user_id': 'user2', 'role': 'role1', 'tenant_id': 'proj1'},
        {'user_id': 'user2', 'role': 'role1', 'tenant_id': 'proj2'},
        {'user_id': 'user2', 'role': 'role2', 'tenant_id': 'proj2'},
        {'user_id': 'user3', 'role': 'role3', 'tenant_id': 'proj1'},
    ],
    'user_tenant_list': [
        {'tenant_id': 'proj1', 'user_id': 'user1'},
        {'tenant_id': 'proj4', 'user_id': 'user4'},
        {'tenant_id': 'proj1', 'user_id': 'user2'},
        {'tenant_id': 'proj2', 'user_id': 'user2'},
        {'tenant_id': 'proj1', 'user_id': 'user3'},
    ],
    'ec2_credentials': [
        {'access_key': 'acc1', 'secret_key': 'sec1', 'user_id': 'user1'},
        {'access_key': 'acc4', 'secret_key': 'sec4', 'user_id': 'user4'},
        {'access_key': 'acc2', 'secret_key': 'sec2', 'user_id': 'user2'},
        {'access_key': 'acc3', 'secret_key': 'sec3', 'user_id': 'user3'},
    ],
    'tenants': [
        {'description': 'desc1', 'id': 'proj1', 'name': 'pname1'},
        {'description': 'desc4', 'id': 'proj4', 'name': 'pname4'},
        {'description': 'desc2', 'id': 'proj2', 'name': 'pname2'},
    ],
}


class MigrateNovaAuth(test.TestCase):
    def setUp(self):
        super(MigrateNovaAuth, self).setUp()
        self.config([test.etcdir('keystone.conf.sample'),
                     test.testsdir('test_overrides.conf'),
                     test.testsdir('backend_sql.conf'),
                     test.testsdir('backend_sql_disk.conf')])
        sql_util.setup_test_database()
        self.identity_man = identity.Manager()
        self.identity_api = identity_sql.Identity()
        self.ec2_api = ec2_sql.Ec2()

    def tearDown(self):
        sql_util.teardown_test_database()
        super(MigrateNovaAuth, self).tearDown()

    def _create_role(self, role_name):
        role_id = uuid.uuid4().hex
        role_dict = {'id': role_id, 'name': role_name}
        self.identity_api.create_role(role_id, role_dict)

    def test_import(self):
        self._create_role('role1')

        nova.import_auth(FIXTURE)

        users = {}
        for user in ['user1', 'user2', 'user3', 'user4']:
            users[user] = self.identity_api.get_user_by_name(
                user, DEFAULT_DOMAIN_ID)

        tenants = {}
        for tenant in ['proj1', 'proj2', 'proj4']:
            tenants[tenant] = self.identity_api.get_project_by_name(
                tenant, DEFAULT_DOMAIN_ID)

        membership_map = {
            'user1': ['proj1'],
            'user2': ['proj1', 'proj2'],
            'user3': ['proj1'],
            'user4': ['proj4'],
        }

        for (old_user, old_projects) in membership_map.iteritems():
            user = users[old_user]
            membership = self.identity_api.get_projects_for_user(user['id'])
            expected = [tenants[t]['id'] for t in old_projects]
            self.assertEqual(set(expected), set(membership))
            for tenant_id in membership:
                password = None
                for _user in FIXTURE['users']:
                    if _user['id'] == old_user:
                        password = _user['password']
                self.identity_man.authenticate({}, user['id'],
                                               tenant_id, password)

        for ec2_cred in FIXTURE['ec2_credentials']:
            user_id = users[ec2_cred['user_id']]['id']
            for tenant_id in self.identity_api.get_projects_for_user(user_id):
                access = '%s:%s' % (tenant_id, ec2_cred['access_key'])
                cred = self.ec2_api.get_credential(access)
                actual = cred['secret']
                expected = ec2_cred['secret_key']
                self.assertEqual(expected, actual)

        roles = self.identity_api.list_roles()
        role_names = set([role['name'] for role in roles])
        self.assertEqual(role_names, set(['role2', 'role1', 'role3',
                                          CONF.member_role_name]))

        assignment_map = {
            'user1': {'proj1': ['role1', 'role2']},
            'user2': {'proj1': ['role1'], 'proj2': ['role1', 'role2']},
            'user3': {'proj1': ['role3']},
            'user4': {'proj4': ['role1']},
        }

        for (old_user, old_project_map) in assignment_map.iteritems():
            tenant_names = ['proj1', 'proj2', 'proj4']
            for tenant_name in tenant_names:
                user = users[old_user]
                tenant = tenants[tenant_name]
                roles = self.identity_api.get_roles_for_user_and_project(
                    user['id'], tenant['id'])
                actual = [self.identity_api.get_role(role_id)['name']
                          for role_id in roles]
                if CONF.member_role_name in actual:
                    actual.remove(CONF.member_role_name)
                expected = old_project_map.get(tenant_name, [])
                self.assertEqual(set(actual), set(expected))
