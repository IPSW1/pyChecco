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
import time
import contextlib

from typing import List, Dict, Tuple
from unittest import TestSuite

from pyChecco.execution.testexecution.loader import CustomTestLoader
from pyChecco.execution.testexecution.testlistener import TestResult
from pyChecco.configuration import Configuration
from pyChecco.execution.executiontrace import ExecutionTrace, TracedAssertion
from pyChecco.execution.executiontracer import ExecutionTracer
from pyChecco.execution.testexecution.testlistener import TestListener
from pyChecco.slicer.dynamic_slicer import DynamicSlicer, SlicingCriterion
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.utils.exceptions import SlicingTimeoutException

import pyChecco.execution.testexecution.sample_suite as sampled_mod


class TestExecutor:
    def __init__(self, configuration: Configuration, tracer: ExecutionTracer):
        self._configuration = configuration
        self._tracer: ExecutionTracer = tracer

        self._module_traces: Dict[str, ExecutionTrace] = {}
        self.test_loader: CustomTestLoader = CustomTestLoader(self._module_traces)
        self._testsuite: TestSuite = self._discover_tests()

        self.sampled_tests = []
        self._load_sampled_tests()
        sampled_mod.sampled_tests = self.sampled_tests

        self._module_slices: Dict[str, List[UniqueInstruction]] = dict()
        self._known_code_objects = None
        self._num_testcases = self._testsuite.countTestCases()
        self._num_executed_testcases = 0
        self._num_successful_testcases = 0
        self._num_canceled_testcases = 0

        self._unique_assertions = set()
        self._num_found_assertions = 0
        self._num_sliced_assertions = 0
        self._num_aborted_assertion_slicing = 0

        self._full_execution_time: float = 0.0
        self._current_execution_start_time: Tuple[float, str] = (0.0, "")
        self._full_slicing_time: float = 0.0

    def execute_testsuite(self) -> TestListener:
        test_listener: TestListener = TestListener(self._configuration, self)
        # noinspection PyTypeChecker
        return self._testsuite.run(test_listener)

    def update_known_code_objects(self):
        self._known_code_objects = self._tracer.get_known_data().existing_code_objects

    def start_test(self, test_id: str) -> None:
        self._num_executed_testcases += 1
        self._current_execution_start_time = (time.process_time(), test_id)
        if self._configuration.debug_out:
            print("Executing test:", test_id)

    def cancel_test(self, test_id: str, result: TestResult) -> None:
        if self._configuration.debug_out:
            if result == TestResult.ERROR:
                print("Test error:", test_id)
                print("---------------------------------------------------------------------\n")
            elif result == TestResult.FAILURE:
                print("Test failed:", test_id)
                print("---------------------------------------------------------------------\n")
            elif result == TestResult.EXCEEDED_RUNTIME:
                self._num_canceled_testcases += 1
                print("Test exceeded maximum configured runtime:", test_id)
                print("---------------------------------------------------------------------\n")
            elif result == TestResult.UNEXPECTED_SUCCESS:
                self._num_canceled_testcases += 1
                print("Test was unexpected success:", test_id)
                print("---------------------------------------------------------------------\n")

    def stop_test(self, test_id: str):
        assert self._current_execution_start_time[1] == test_id, "Test cases not matching for time calculation"
        self._full_execution_time += time.process_time() - self._current_execution_start_time[0]
        self._current_execution_start_time = (0.0, "")

    def new_trace(self, trace: ExecutionTrace) -> None:
        """
        Should be called after the execution of a test case. This method immediately slices
        the given trace and adds new instructions to the overall coverage result.

        :param trace: Trace which should be sliced.
        """
        debug_output = self._configuration.debug_out

        self.update_known_code_objects()
        trace, module_offset = self.combine_trace(trace)

        # Progress output to see that something is happening
        self._num_successful_testcases += 1
        print("\rProcessing test case " + str(self._num_executed_testcases) + "/" + str(self._num_testcases), end="")

        self._unique_assertions.update(trace.unique_assertions)

        trace.print_trace(debug_output)

        for assertion in trace.traced_assertions:
            slicing_start_time = time.process_time()
            if debug_output:
                print("Assertion:", assertion.traced_assertion_call)
            try:
                slicing_criterion, trace_position = self._slicing_criterion_from_assertion(trace, assertion,
                                                                                           module_offset)
                slicer = DynamicSlicer(self._configuration, trace, self._known_code_objects)

                try:
                    self._num_found_assertions += 1
                    dynamic_slice = slicer.slice(trace, slicing_criterion, trace_position - 1,
                                                 debug_output=debug_output > 1)
                except SlicingTimeoutException:
                    self._num_aborted_assertion_slicing += 1
                    if debug_output:
                        print("\t -> Assertion exceeded maximum slicing threshold")
                    break
                if debug_output:
                    print("\t -> Assertion sliced successfully")
                module_instructions = DynamicSlicer.organize_by_module(dynamic_slice)

                for mod in module_instructions:
                    if mod not in self._module_slices:
                        self._module_slices[mod] = []
                    self._module_slices[mod].extend(module_instructions[mod])

                    if debug_output > 1:
                        print("------ Slice ------")
                        print("Module:", mod)
                        for instr in module_instructions[mod]:
                            print("\t", instr)

                self._num_sliced_assertions += 1
            except ValueError as e:
                print(e)
            finally:
                self._full_slicing_time += time.process_time() - slicing_start_time

        if debug_output:
            print("---------------------------------------------------------------------\n")

    def _slicing_criterion_from_assertion(self, trace: ExecutionTrace, traced_assertion: TracedAssertion,
                                          trace_position_offset: int) -> Tuple[SlicingCriterion, int]:
        trace_position = traced_assertion.trace_position_end + trace_position_offset
        traced_instr = trace.executed_instructions[trace_position]

        code_meta = self._known_code_objects.get(traced_instr.code_object_id)
        unique_instr = UniqueInstruction(traced_instr.file, traced_instr.name, traced_instr.argument,
                                         traced_instr.lineno, traced_instr.code_object_id, traced_instr.node_id,
                                         code_meta, traced_instr.offset)

        # We know the exact trace position and the slicer can handle this without having the occurrence.
        return SlicingCriterion(unique_instr, occurrence=-1), trace_position

    def _discover_tests(self) -> TestSuite:
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                return self.test_loader.discover(self._configuration.project_path, pattern=self._configuration.pattern)

    def combine_trace(self, trace: ExecutionTrace) -> Tuple[ExecutionTrace, int]:
        """
        Each test is in one or multiple packages which are loaded before the test
        is executed. So the trace of each test is prepended with the the trace for the
        packages(s) in which the test in placed.

        :return: A tuple including test traces combined with module imports and
        the length of the import trace.
        """
        num_added_instructions = 0

        trace_copy = ExecutionTrace()
        trace_copy.test_id = trace.test_id
        trace_copy.executed_instructions = trace.executed_instructions
        trace_copy.traced_assertions = trace.traced_assertions
        trace_copy.unique_assertions = trace.unique_assertions

        if len(trace.executed_instructions) > 0:
            test_path = trace_copy.executed_instructions[0].file[len(self._configuration.project_path):]
            test_module = test_path.replace(os.sep, ".")

            module_traces: List[Tuple[int, ExecutionTrace]] = []
            for key in self._module_traces.keys():
                if test_module.startswith(key):
                    module_depth = len(self._module_traces.get(key).module_name.split("."))
                    module_traces.append((module_depth, self._module_traces.get(key)))

            # Sort traces by depth of module in descending order
            module_traces.sort(key=lambda mod_trace: mod_trace[0], reverse=True)

            for module_trace in module_traces:
                trace_copy.executed_instructions[:0] = module_trace[1].executed_instructions
                num_added_instructions += len(module_trace[1].executed_instructions)

        return trace_copy, num_added_instructions

    def get_module_slices(self) -> Dict[str, List[UniqueInstruction]]:
        return self._module_slices

    def get_statistics(self) -> Tuple[int, int, int, int, int, int, int, float, float]:
        return self._num_testcases, self._num_successful_testcases, self._num_canceled_testcases, \
               len(self._unique_assertions), self._num_found_assertions, self._num_sliced_assertions, \
               self._num_aborted_assertion_slicing, self._full_execution_time, self._full_slicing_time

    def _load_sampled_tests(self):
        f = open(os.path.join(self._configuration.project_path, self._configuration.test_sample), 'r')

        for line in f:
            self.sampled_tests.append(line[:-1])
