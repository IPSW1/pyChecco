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


from typing import Optional, List


class Configuration:
    """General configuration for the test generator."""

    def __init__(self, project_path: str, report_dir: str, debug_output: int = 0, line_coverage: bool = False,
                 instruction_coverage: bool = False, text_report: bool = False, csv_report: bool = False,
                 html_report: bool = False, debug_mode: bool = False, pattern: str = None, max_test_time: int = 60,
                 max_slice_time: int = 60, custom_assertions: Optional[List] = None,
                 source: Optional[str] = None, file: Optional[str] = None) -> None:
        """
        :param project_path: Path to the project for which the coverage is measured.
        :param line_coverage: Generate reports for line coverage.
        :param instruction_coverage: Generate reports for instruction coverage
        :param text_report: Generate coverage reports in textual form.
        :param csv_report: Generate coverage reports in csv format.
        :param html_report: Generate coverage reports in visual HTML representation (only possible when
         line coverage is enabled).
        :param debug_mode: Enables the debug mode.
            Some features might behave different when it is active.
        :param report_dir: Directory in which to put HTML and CSV reports
        :param pattern: Test discovery pattern for unittest module
        :param max_test_time: Maximum time (in seconds) for running single test cases
        :param max_slice_time: Maximum time (in seconds) for slicing single assertions
        :param max_slice_time: Maximum time (in seconds) for slicing single assertions
        :param source: Source code directory for coverage report
        :param file: Module code for coverage report
        """
        self.project_path = project_path
        self.debug_mode = debug_mode
        self.report_dir = report_dir

        # Coverage type
        self.line_coverage = line_coverage
        self.instruction_coverage = instruction_coverage

        # Report type
        self.text_report = text_report
        self.csv_report = csv_report
        self.html_report = html_report

        # unittest arguments
        self.pattern = pattern

        # Debug output for slicing (0: no output, 1: basic output, 2: detailed output)
        self.debug_out = debug_output

        # Maximum execution time for a single test case
        self.max_test_time = max_test_time

        # Maximum slicing time per assertion in seconds
        self.max_slicing_time = max_slice_time

        # Name of methods treated as assertions (one or multiple)
        self.custom_assertions = custom_assertions

        # Source code directory for coverage report
        self.source = source
        self.file = file
