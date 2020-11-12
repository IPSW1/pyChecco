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


"""pyChecco is a code coverage measurement tool for checked coverage in Python.

This module provides the main entry location for the program execution from the command
line.
"""
import argparse
import sys
from typing import List

from pyChecco.configuration import Configuration
from pyChecco.checked_coverage import CheckedCoverage


def _create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("pyChecco checked coverage")

    # Show path as required and not optional
    required_arguments = parser.add_argument_group("required arguments")
    required_arguments.add_argument("-p", "--path", required=True, help="Path to project")

    # Replicates standard behavior, but shows optional arguments below required arguments
    optional_arguments = parser.add_argument_group("optional arguments")
    optional_arguments.add_argument("-o", "--output", default="pyChecco-report", help="Output directory for reports")
    optional_arguments.add_argument("-d", "--debug", type=int, default=0, help="Debug level (0: no debug, "
                                                                               "1: minimal debug, 2: detailed")
    optional_arguments.add_argument("--max-test-time", type=int, default=60,
                                    help="Maximum time (in seconds) for running single test cases")
    optional_arguments.add_argument("--max-slice-time", type=int, default=60,
                                    help="Maximum time (in seconds) for slicing single assertions")
    # unittest parameters
    optional_arguments.add_argument("--pattern", default="test*.py",
                                    help="Custom test discovery pattern for unittest module")
    # assertion detection parameter
    optional_arguments.add_argument("--custom-assertions", nargs="+",
                                    help="Name of methods treated as assertions (one or multiple)")

    # Coverage types
    coverage_types = parser.add_argument_group("coverage types")
    coverage_types.add_argument("--instruction", action='store_true', default=False,
                                help="Generate instruction coverage reports (default if no coverage type is given)")
    coverage_types.add_argument("--line", action='store_true', default=False, help="Generate line coverage reports")

    # Report types
    report_types = parser.add_argument_group("report types")
    report_types.add_argument("--text", action='store_true', default=False, help="Generate report in textual form")
    report_types.add_argument("--csv", action='store_true', default=False, help="Generate report in csv format")
    report_types.add_argument("--html", action='store_true', default=False,
                              help="Generate coverage reports in visual HTML representation (only possible when "
                                   "line coverage is enabled)")

    optional_arguments.add_argument("--source", help="Source code directory for coverage report")
    optional_arguments.add_argument("--file", help="Module code for coverage report")

    return parser


def main(argv: List[str] = None):
    """
    Main entry point of the pyChecco checked coverage library.

    :param argv: List of command-line arguments.
    """
    if argv is None:
        argv = sys.argv
    if len(argv) <= 1:
        argv.append("--help")

    parser = _create_argument_parser()
    args = parser.parse_args()

    # Determine coverage type(s)
    if not args.line and not args.instruction:
        line_coverage = False
        instruction_coverage = True
    else:
        line_coverage = args.line
        instruction_coverage = args.instruction

    # Determine report type(s)
    if not line_coverage and args.html:
        raise ValueError("Generation of HTML reports is only possible when line coverage is enabled.")

    # Start main execution
    configuration = Configuration(project_path=args.path, report_dir=args.output, debug_output=args.debug,
                                  line_coverage=line_coverage, instruction_coverage=instruction_coverage,
                                  text_report=args.text, csv_report=args.csv, html_report=args.html,
                                  pattern=args.pattern, max_test_time=args.max_test_time,
                                  max_slice_time=args.max_slice_time, custom_assertions=args.custom_assertions,
                                  source=args.source, file=args.file)
    checked_coverage = CheckedCoverage(configuration)
    checked_coverage.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
