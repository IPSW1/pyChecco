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
import sys
import unittest

from pyChecco.cli import main

path_sep = os.path.sep
project_path = os.path.dirname(os.path.abspath("."))
example_project_path = path_sep.join([project_path, "tests", "integration", "example_project"])


class IntegrationTest(unittest.TestCase):
    def test_project(self):
        sys.argv = ['script', '-d', '0', '-p', example_project_path, '--line', '--instruction', '--text', '--csv',
                    '--html']
        main()

        self.assertTrue(os.path.exists(path_sep.join([example_project_path, "pychecco_stat.txt"])))
        os.remove(path_sep.join([example_project_path, "pychecco_stat.txt"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path,
                                                      "pyChecco-report",
                                                      "checked_coverage.xml"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "checked_coverage.xml"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path,
                                                      "pyChecco-report",
                                                      "instruction_coverage.txt"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "instruction_coverage.txt"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path,
                                                      "pyChecco-report",
                                                      "instruction_coverage.csv"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "instruction_coverage.csv"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path,
                                                      "pyChecco-report",
                                                      "line_coverage.txt"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "line_coverage.txt"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path, "pyChecco-report", "line_coverage.csv"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "line_coverage.csv"]))

        self.assertTrue(os.path.exists(path_sep.join([example_project_path, "pyChecco-report", "line_coverage.html"])))
        os.remove(path_sep.join([example_project_path, "pyChecco-report", "line_coverage.html"]))
