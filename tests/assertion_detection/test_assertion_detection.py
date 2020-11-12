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


import os
import unittest

from tests.util import trace_call

path_sep = os.path.sep
example_modules_directory = "example_modules/"
example_modules_path = path_sep.join(__file__.split(path_sep)[:-1]) + path_sep + example_modules_directory


class AssertionDetection(unittest.TestCase):
    def test_single_assertion(self):
        module_file = "metatest_basic.py"
        module_path = example_modules_path + module_file
        trace = trace_call(example_modules_path, module_path, pattern="metatest_basic.py")

        self.assertEqual(trace.test_id, "metatest_basic.MetaTestCase.test_foo")
        self.assertEqual(len(trace.traced_assertions), 1)
        self.assertEqual(trace.traced_assertions[0].traced_assertion_call.lineno, 27)

    def test_multiple_assertions(self):
        module_file = "metatest_multiple.py"
        module_path = example_modules_path + module_file
        trace = trace_call(example_modules_path, module_path, pattern="metatest_multiple.py")

        self.assertEqual(len(trace.traced_assertions), 3)
        self.assertEqual(trace.traced_assertions[0].traced_assertion_call.lineno, 27)
        self.assertEqual(trace.traced_assertions[1].traced_assertion_call.lineno, 28)
        self.assertEqual(trace.traced_assertions[2].traced_assertion_call.lineno, 29)

    def test_loop_assertions(self):
        module_file = "metatest_loop.py"
        module_path = example_modules_path + module_file
        trace = trace_call(example_modules_path, module_path, pattern="metatest_loop.py")

        self.assertEqual(len(trace.traced_assertions), 5)
        for assertion in trace.traced_assertions:
            self.assertEqual(assertion.traced_assertion_call.lineno, 24)

    def test_custom_assertion_specified(self):
        module_file = "metatest_custom.py"
        module_path = example_modules_path + module_file
        trace = trace_call(example_modules_path, module_path, pattern="metatest_custom.py",
                           custom_assertions=["assert_custom"])

        self.assertEqual(len(trace.traced_assertions), 1)

    # For lexical assertions this also works!
    def test_custom_assertion_unspecified(self):
        module_file = "metatest_custom.py"
        module_path = example_modules_path + module_file
        trace = trace_call(example_modules_path, module_path, pattern="metatest_custom.py")

        self.assertEqual(len(trace.traced_assertions), 1)
