# This file is part of pyChecco.
# Copyright (C) 2020 Marco Reichenberger
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import signal
import unittest

from enum import Enum
from typing import Dict

from pyChecco.configuration import Configuration
from pyChecco.execution.executiontracer import ExecutionTracer
from pyChecco.utils.exceptions import TestTimeoutException


class TestResult(Enum):
    SUCCESS = 1
    ERROR = 2
    FAILURE = 3
    UNEXPECTED_SUCCESS = 5
    EXCEEDED_RUNTIME = 4


class TestListener(unittest.TestResult):
    def __init__(self, configuration: Configuration, executor):
        self._configuration = configuration

        unittest.TestResult.__init__(self)
        self._executed_tests: Dict[str, TestResult] = dict()
        self._executor = executor
        self.buffer = True  # omit standard output

    def startTest(self, test: unittest.case.TestCase) -> None:
        self._executor.start_test(test.id())
        self.buffer = True

        signal.alarm(self._configuration.max_test_time)
        try:
            ExecutionTracer.reset()
            ExecutionTracer.set_current_test(test.id())

            unittest.TestResult.startTest(self, test)
            self._executed_tests[test.id()] = TestResult.SUCCESS
        except TestTimeoutException:
            self._executed_tests[test.id()] = TestResult.EXCEEDED_RUNTIME

    def stopTest(self, test: unittest.case.TestCase) -> None:
        signal.alarm(0)
        unittest.TestResult.stopTest(self, test)
        self._executor.stop_test(test.id())

        if self._executed_tests[test.id()] == TestResult.SUCCESS:
            self._executor.new_trace(ExecutionTracer.get_trace())
        else:
            self._executor.cancel_test(test.id(), self._executed_tests[test.id()])

    def addError(self, test: unittest.case.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)
        if self._configuration.debug_out > 0:
            # noinspection PyUnresolvedReferences
            print(self._exc_info_to_string(err, test))
        self._executed_tests[test.id()] = TestResult.ERROR

    def addFailure(self, test: unittest.case.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)
        if self._configuration.debug_out > 0:
            # noinspection PyUnresolvedReferences
            print(self._exc_info_to_string(err, test))
        self._executed_tests[test.id()] = TestResult.FAILURE

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        unittest.TestResult.addUnexpectedSuccess(self, test)
        self._executed_tests[test.id()] = TestResult.UNEXPECTED_SUCCESS

    def get_executed_tests(self) -> Dict[str, TestResult]:
        return self._executed_tests


# noinspection PyUnusedLocal
def timeout_handler(signum, frame):
    raise TestTimeoutException


signal.signal(signal.SIGALRM, timeout_handler)
