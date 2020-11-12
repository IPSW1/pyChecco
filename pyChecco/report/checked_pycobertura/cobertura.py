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


# The ideas for this file are taken from pycobertura, see:
# https://github.com/aconrad/pycobertura
# Modifications were made to the file


# The MIT License (MIT)
#
# Copyright (c) 2014 SurveyMonkey Inc. and its affiliates
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import pycobertura

from pycobertura.utils import extrapolate_coverage


class CheckedCobertura(pycobertura.Cobertura):
    def line_statuses(self, filename):
        """
        Return a list of tuples `(lineno, status)` of all the lines found in the
        Cobertura report for the given file `filename` where `lineno` is the line
        number and `status` is coverage status of the line which can be either
        `full` (fully covered line), `partial` (partially covered line) or
        `miss` (line miss).
        """
        line_elements = self._get_lines_by_filename(filename)

        lines_w_status = []
        for line in line_elements:
            lineno = int(line.attrib["number"])
            status = "miss"
            if line.attrib["hits"] != "0":
                # At least a partially covered line
                status = "partial"
                if "full" in line.attrib and line.attrib["full"] == "1":
                    status = "full"
            lines_w_status.append((lineno, status))

        return lines_w_status

    def missed_lines(self, filename):
        """
        Return a list of extrapolated uncovered line numbers for the
        file `filename` according to `Cobertura.line_statuses`.
        """
        statuses = self.line_statuses(filename)
        statuses = extrapolate_coverage(statuses)
        return [lno for lno, status in statuses if status == "miss"]

    def total_full(self, filename: str = None):
        """
        Return the total number of fully covered statements for the
        file `filename`. If `filename` is not given, return the total
        number of fully covered statements for all files.
        """
        if filename is not None:
            statements = self.full_statements(filename)
            return len(statements)

        total = 0
        for filename in self.files():
            statements = self.full_statements(filename)
            total += len(statements)

        return total

    def full_statements(self, filename: str):
        """
        Return a list of fully covered line numbers found for the file `filename`.
        """
        el = self._get_class_element_by_filename(filename)
        lines = el.xpath("./lines/line[@full=1]")
        return [int(line.attrib["number"]) for line in lines]

    def total_partial(self, filename: str = None):
        """
        Return the total number of partially covered statements for the
        file `filename`. If `filename` is not given, return the total
        number of partially covered statements for all files.
        """
        if filename is not None:
            statements = self.partial_statements(filename)
            return len(statements)

        total = 0
        for filename in self.files():
            statements = self.partial_statements(filename)
            total += len(statements)

        return total

    def total_gehalf(self, filename: str = None):
        """
        Return the total number of partially covered statements for the
        file `filename`. If `filename` is not given, return the total
        number of partially covered statements for all files.
        """
        if filename is not None:
            statements = self.gehalf_statements(filename)
            return len(statements)

        total = 0
        for filename in self.files():
            statements = self.gehalf_statements(filename)
            total += len(statements)

        return total

    def partial_statements(self, filename: str):
        """
        Return a list of partially covered line numbers found for the file `filename`.
        """
        el = self._get_class_element_by_filename(filename)
        lines = el.xpath("./lines/line[@full=0]")
        return [int(line.attrib["number"]) for line in lines]

    def gehalf_statements(self, filename: str):
        """
        Return a list of partially covered line numbers found for the file `filename`.
        """
        el = self._get_class_element_by_filename(filename)
        lines = el.xpath("./lines/line[@gehalf=1]")
        return [int(line.attrib["number"]) for line in lines]
