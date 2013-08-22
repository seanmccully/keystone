# Copyright 2013 IBM Corp.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.


from keystone.common import sql
from keystone import test


class CallbackMonitor:
    def __init__(self, expect_called=True, raise_=False):
        self.expect_called = expect_called
        self.called = False
        self._complete = False
        self._raise = raise_

    def call_this(self):
        if self._complete:
            return

        if not self.expect_called:
            raise Exception("Did not expect callback.")

        if self.called:
            raise Exception("Callback already called.")

        self.called = True

        if self._raise:
            raise Exception("When called, raises.")

    def check(self):
        if self.expect_called:
            if not self.called:
                raise Exception("Expected function to be called.")
        self._complete = True


class TestGlobalEngine(test.TestCase):

    def tearDown(self):
        sql.set_global_engine(None)
        super(TestGlobalEngine, self).tearDown()

    def test_notify_on_set(self):
        # If call sql.set_global_engine(), notify callbacks get called.

        cb_mon = CallbackMonitor()

        sql.register_global_engine_callback(cb_mon.call_this)
        fake_engine = object()
        sql.set_global_engine(fake_engine)

        cb_mon.check()

    def test_multi_notify(self):
        # You can also set multiple notify callbacks and they each get called.

        cb_mon1 = CallbackMonitor()
        cb_mon2 = CallbackMonitor()

        sql.register_global_engine_callback(cb_mon1.call_this)
        sql.register_global_engine_callback(cb_mon2.call_this)

        fake_engine = object()
        sql.set_global_engine(fake_engine)

        cb_mon1.check()
        cb_mon2.check()

    def test_notify_once(self):
        # After a callback is called, it's not called again if set global
        # engine again.

        cb_mon = CallbackMonitor()

        sql.register_global_engine_callback(cb_mon.call_this)
        fake_engine = object()
        sql.set_global_engine(fake_engine)

        fake_engine = object()
        # Note that cb_mon.call_this would raise if it's called again.
        sql.set_global_engine(fake_engine)

        cb_mon.check()

    def test_set_same_engine(self):
        # If you set the global engine to the same engine, callbacks don't get
        # called.

        fake_engine = object()

        sql.set_global_engine(fake_engine)

        cb_mon = CallbackMonitor(expect_called=False)
        sql.register_global_engine_callback(cb_mon.call_this)

        # Note that cb_mon.call_this would raise if it's called.
        sql.set_global_engine(fake_engine)

        cb_mon.check()

    def test_notify_register_same(self):
        # If you register the same callback twice, only gets called once.
        cb_mon = CallbackMonitor()

        sql.register_global_engine_callback(cb_mon.call_this)
        sql.register_global_engine_callback(cb_mon.call_this)

        fake_engine = object()
        # Note that cb_mon.call_this would raise if it's called twice.
        sql.set_global_engine(fake_engine)

        cb_mon.check()

    def test_callback_throws(self):
        # If a callback function raises,
        # a) the caller doesn't know about it,
        # b) other callbacks are still called

        cb_mon1 = CallbackMonitor(raise_=True)
        cb_mon2 = CallbackMonitor()

        sql.register_global_engine_callback(cb_mon1.call_this)
        sql.register_global_engine_callback(cb_mon2.call_this)

        fake_engine = object()
        sql.set_global_engine(fake_engine)

        cb_mon1.check()
        cb_mon2.check()


class TestBase(test.TestCase):

    def tearDown(self):
        sql.set_global_engine(None)
        super(TestBase, self).tearDown()

    def test_get_engine_global(self):
        # If call get_engine() twice, get the same global engine.
        base = sql.Base()
        engine1 = base.get_engine()
        self.assertIsNotNone(engine1)
        engine2 = base.get_engine()
        self.assertIs(engine1, engine2)

    def test_get_engine_not_global(self):
        # If call get_engine() twice, once with allow_global_engine=True
        # and once with allow_global_engine=False, get different engines.
        base = sql.Base()
        engine1 = base.get_engine()
        engine2 = base.get_engine(allow_global_engine=False)
        self.assertIsNot(engine1, engine2)

    def test_get_session(self):
        # autocommit and expire_on_commit flags to get_session() are passed on
        # to the session created.

        base = sql.Base()
        session = base.get_session(autocommit=False, expire_on_commit=True)

        self.assertFalse(session.autocommit)
        self.assertTrue(session.expire_on_commit)

    def test_get_session_invalidated(self):
        # If clear the global engine, a new engine is used for get_session().
        base = sql.Base()
        session1 = base.get_session()
        sql.set_global_engine(None)
        session2 = base.get_session()
        self.assertIsNot(session1.bind, session2.bind)
