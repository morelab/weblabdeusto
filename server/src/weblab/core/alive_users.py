#!/usr/bin/env python
#-*-*- encoding: utf-8 -*-*-
#
# Copyright (C) 2005-2009 University of Deusto
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# This software consists of contributions made by many individuals, 
# listed below:
#
# Author: Pablo Orduña <pablo@ordunya.com>
#



import time
import threading

import voodoo.sessions.manager as SessionManager
import weblab.core.processor as UserProcessor

USER_PROCESSING_TIME_BETWEEN_CHECKS = 'core_time_between_checks'
DEFAULT_TIME_BETWEEN_CHECKS         = 2 # seconds

ALIVE_USERS_SESSION_POOL = "core_alive_users_session_pool_id"
DEFAULT_ALIVE_USERS_SESSION_POOL = "AliveUsersSessionPool"

class AliveUsersCollection(object):
    """
    AliveUsersCollection tracks the list of users who are not answering and
    whose session has expired. If a user's account has expired and s/he 
    calls "send_command", send_command will first check that the user's 
    account has not expired before acting, so it's not a big problem.

    But, if a user's browser crashes, or the user has problems with the 
    network or whatever, normally no one would check this user's session
    status, which is a problem since this user may have resource to be
    disposed.

    So, this class manages those cases. It only has three methods:
        - add_user: adds a session_id
        - remove_user: removes a session_id
        - check_expired_users: checks and removes the users whose 
            session has expired

    The first two methods manage the sessions which actively are alive.

    The last method finds expired sessions, removes them from the alive 
    list and returns them. To do so, it checks all the alive sessions and
    removes those expired. Since this may become into blocking more often
    than required, and the operation may become too heavy, we use a config
    variable which checks that in each UPS the check_expired_users isn't 
    called more often than a certain amount of time.

    This is checked per UPS server, not in the global memory, since placing
    it in global memory would actually create some blocking which wouldn't 
    be desired. This way, the amount of calls to global memory is reduced 
    to "once in a certain amount of time" + when adding/removing an alive
    user.
    """
    def __init__(self, locator, cfg_manager, session_type, session_manager, db_manager, commands_store):
        # This is an optimization. It shouldn't be stored in the SessionManager
        # since the value itself doesn't matter. The important thing is that
        # each UPS doesn't lock too often the global session in the 
        # SessionManager.
        self._latest_check      = 0
        self._latest_check_lock = threading.RLock()

        self._locator         = locator
        self._cfg_manager     = cfg_manager
        self._session_manager = session_manager
        self._db_manager      = db_manager
        self._commands_store  = commands_store

        self._set_min_time_between_checks()

        self._time_module     = time

        pool = cfg_manager.get_value(ALIVE_USERS_SESSION_POOL, DEFAULT_ALIVE_USERS_SESSION_POOL)
        # timeout = None: don't expire! Ever!
        self._users_session_manager = SessionManager.SessionManager(cfg_manager, session_type, pool, timeout = None )

        self._experiments_server_session_id = self._users_session_manager.create_session()
        self._users_session_manager.modify_session(
                self._experiments_server_session_id,
                [
                    # session_id,
                ]
            )
    
    def _set_min_time_between_checks(self):
        self._min_time_between_checks = self._cfg_manager.get_value( USER_PROCESSING_TIME_BETWEEN_CHECKS, DEFAULT_TIME_BETWEEN_CHECKS )

    def _time_between_checkes_finished(self):
        result = False

        self._latest_check_lock.acquire()
        try:
            cur_time = self._time_module.time()
            if cur_time - self._latest_check > self._min_time_between_checks:
                self._latest_check = cur_time
                result = True
        finally:
            self._latest_check_lock.release()

        if result:
            self._set_min_time_between_checks()
            return True
        else:
            return False

    def add_user(self, session_id):
        session_ids = self._users_session_manager.get_session_locking(
                self._experiments_server_session_id
            )
        try:
            if session_ids.count(session_id) == 0:
                session_ids.append(session_id)
        finally:
            self._users_session_manager.modify_session_unlocking(
                    self._experiments_server_session_id,
                    session_ids
                )

    def remove_user(self, session_id):
        session_ids = self._users_session_manager.get_session_locking(
                self._experiments_server_session_id
            )
        try:
            if session_ids.count(session_id) > 0:
                session_ids.remove(session_id)
        finally:
            self._users_session_manager.modify_session_unlocking(
                    self._experiments_server_session_id,
                    session_ids
                )

    def _find_expired_session_ids(self, session_ids):
        expired_session_ids = []

        for session_id in session_ids:
            # Do not lock. If the user is doing something, the method
            # would get locked here. And if the user is doing something,
            # the information is stored in a transactional way, so it 
            # shouldn't be a problem. Anyway, it would be nice that
            # after the "poll" method the UPS modified the (updated) 
            # session without unlocking.
            session = self._session_manager.get_session(session_id)
            coordinator = None # It's not used in is_expired
            user_processor = UserProcessor.UserProcessor( self._locator, session, self._cfg_manager, coordinator, self._db_manager, self._commands_store)
            if user_processor.is_expired():
                expired_session_ids.append(session_id)

        return expired_session_ids

    def check_expired_users(self):
        """ 
        This method will remove from the alive list and return all the sessions 
        that have been expired. Although the method could be heavy since it 
        needs to check all the sessions in the database, its impact is reduced 
        since this process is only executed once in a customized time (so if 
        this method is called many times it almost doesn't get locked).
        """
        if self._time_between_checkes_finished():
            session_ids = self._users_session_manager.get_session_locking(
                    self._experiments_server_session_id
                )
            try:
                    expired_session_ids = self._find_expired_session_ids(session_ids)

                    for expired_session_id in expired_session_ids:
                        session_ids.remove(expired_session_id)
            finally:
                self._users_session_manager.modify_session_unlocking(
                        self._experiments_server_session_id,
                        session_ids
                    )
            return expired_session_ids
        return []
