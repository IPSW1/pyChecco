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
import re
import sys
import time
import compileall

from typing import Tuple, List, Dict
from datetime import datetime

from pyChecco.configuration import Configuration
from pyChecco.execution.executiontracer import ExecutionTracer
from pyChecco.instrumentation.instruction_instrumentation import InstructionInstrumentation
from pyChecco.execution.testexecution.testexecutor import TestExecutor
from pyChecco.execution.testexecution.testlistener import TestListener
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.report.coverage import CoverageCalculator
from pyChecco.utils.pyc import Pyc

sys.pycache_prefix = None


class CheckedCoverage:
    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration
        sys.path.append(configuration.project_path)

    def run(self) -> None:
        """
        Main routine which does performs all steps:
        - Compiling the project
        - Instrumenting files in the project (offline instrumentation)
        - Executing the testsuite
        - Dynamic slicing on the execution traces
        - Generating reports
        - Recompiling project to "reset" files
        """
        complete_start_time = time.process_time()

        try:
            tracer = ExecutionTracer(self._configuration)

            # Compile project to get bytecode for instrumentation
            print("Compiling files in path {}...".format(self._configuration.project_path))
            compilation_start_time = time.process_time()
            self.compile_project()
            compilation_time = time.process_time() - compilation_start_time

            print()

            # Perform tracing instrumentation
            print("Instrumenting files in path {}...".format(self._configuration.project_path))
            instrumentation_start_time = time.process_time()
            self.instrument_files(tracer)
            instrumentation_time = time.process_time() - instrumentation_start_time

            print("\n")

            # Execute the testsuite of the project
            print("Execute testsuite and perform slicing...")
            executor, result = self.execute_testsuite(tracer)

            # Get slicing result (organized by included instructions per module)
            dynamic_slices = executor.get_module_slices()

            print("\n")

            # Generate coverage reports
            print("Generating reports...")
            reporting_start_time = time.process_time()
            self.generate_reports(tracer, dynamic_slices)
            reporting_time = time.process_time() - reporting_start_time

            print()

        # noinspection PyBroadException
        except BaseException as e:
            raise e

        finally:
            # Re-compile the project after analysis to remove instrumentation
            print("Recompiling project...")
            recompilation_start_time = time.process_time()
            self.compile_project()
            recompilation_time = time.process_time() - recompilation_start_time

        complete_time = time.process_time() - complete_start_time

        self.slicing_statistics_output(result, executor, complete_time, compilation_time, instrumentation_time,
                                       reporting_time, recompilation_time)

    def compile_project(self) -> None:
        # Compile all files in project directory (exclude all in venv directory for now)
        compileall.compile_dir(self._configuration.project_path, rx=re.compile(r'[/\\]venv[/\\]'),
                               force=True, quiet=True)

    def instrument_files(self, tracer: ExecutionTracer) -> None:
        instrumenter = InstructionInstrumentation(tracer)

        # Instrument all .pyc files (and hacky exclude venv for now)
        num_instrumented = 0
        for root, dirs, files in os.walk(self._configuration.project_path):
            for file in files:
                if file.endswith(".pyc") and "/venv/" not in root:
                    path = os.path.join(root, file)

                    # Instrument and write back
                    pyc_file = Pyc(path)
                    pyc_file.instrument(instrumenter)
                    if num_instrumented > 100:
                        print()
                        num_instrumented = 0
                    print(".", end="")
                    num_instrumented += 1

                    pyc_file.overwrite()

    def execute_testsuite(self, tracer: ExecutionTracer) -> Tuple[TestExecutor, TestListener]:
        executor = TestExecutor(self._configuration, tracer)

        test_result: TestListener = executor.execute_testsuite()

        return executor, test_result

    def generate_reports(self, tracer: ExecutionTracer, module_slices: Dict[str, List[UniqueInstruction]]) -> None:
        cov = CoverageCalculator(self._configuration, tracer.get_known_data())

        if self._configuration.line_coverage:
            proj_line_cov, pack_line_cov, file_line_cov = cov.calculate_line_coverage(module_slices)
            cobertura_xml = cov.generate_coberture_xml(proj_line_cov, pack_line_cov, file_line_cov)

            if not self._configuration.text_report and not self._configuration.csv_report and \
                    not self._configuration.html_report:
                cov.print_line_text_report(cobertura_xml)

            if self._configuration.text_report:
                cov.generate_line_text_report(cobertura_xml)
            if self._configuration.csv_report:
                cov.generate_line_csv_report(cobertura_xml)
            if self._configuration.html_report:
                cov.generate_line_html_report(cobertura_xml)

        if self._configuration.instruction_coverage:
            proj_instr_cov, pack_instr_cov, file_instr_cov = cov.calculate_instruction_coverage(module_slices)

            if not self._configuration.text_report and not self._configuration.csv_report:
                cov.print_instruction_text_report(proj_instr_cov, pack_instr_cov, file_instr_cov)

            if self._configuration.text_report:
                cov.generate_instruction_text_report(proj_instr_cov, pack_instr_cov, file_instr_cov)
            if self._configuration.csv_report:
                cov.generate_instruction_csv_report(proj_instr_cov, pack_instr_cov, file_instr_cov)

    def slicing_statistics_output(self, result: TestListener, executor: TestExecutor, complete_time: float,
                                  compilation_time: float, instrumentation_time: float, reporting_time: float,
                                  recompilation_time: float):
        statistics = executor.get_statistics()
        stat_output = "Statistics:\n-----\n"
        stat_output += "Overall\n" + \
                       "\t# found tests: " + str(statistics[0]) + "\n" + \
                       "\t# tests executed without error: " + str(statistics[1]) + "\n" + \
                       "\t# tests resulting in expected failure: " + str(len(result.expectedFailures)) + "\n"
        stat_output += "Test Errors and Failures\n" + \
                       "\t# tests exceeding max runtime: " + str(statistics[2]) + "\n" + \
                       "\t# tests resulting in error: " + str(len(result.errors)) + "\n" + \
                       "\t# tests resulting in failure: " + str(len(result.failures)) + "\n" + \
                       "\t# tests resulting in unexpected success: " + str(len(result.unexpectedSuccesses)) + "\n"
        stat_output += "Slicing\n" + \
                       "\t# found assertions: " + str(statistics[3]) + "\n" + \
                       "\t# assertion calls: " + str(statistics[4]) + "\n" + \
                       "\t# sliced assertion calls: " + str(statistics[5]) + "\n" + \
                       "\t# canceled assertion slicing (exceeded runtime): " + str(statistics[6]) + "\n"
        stat_output += "Runtime: " + "{:.2f}s".format(complete_time) + "\n" + \
                       "\tCompilation: " + "{:.2f}s".format(compilation_time) + "\n" + \
                       "\tInstrumentation: " + "{:.2f}s".format(instrumentation_time) + "\n" + \
                       "\tExecution: " + "{:.2f}s".format(statistics[7]) + "\n" + \
                       "\tSlicing: " + "{:.2f}s".format(statistics[8]) + "\n" + \
                       "\tReporting: " + "{:.2f}s".format(reporting_time) + "\n" + \
                       "\tRecompilation: " + "{:.2f}s".format(recompilation_time) + "\n\n"

        now = datetime.now()
        stat_output += "Finished: " + now.strftime("%d.%m.%Y %H:%M:%S")

        if self._configuration.debug_out > 0:
            print(stat_output)

        # Write to file
        output_file = os.path.join(self._configuration.project_path, "pychecco_stat.txt")
        with open(output_file, "w") as stat_file:
            stat_file.write(stat_output)
