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


# The ideas for this file are taken from pycobertura (under MIT License), see:
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


from collections import namedtuple
from tabulate import tabulate

row_attributes = "filename total_instructions total_hits total_misses instruction_rate"
file_row = namedtuple("FileRowMissed", row_attributes)


class CheckedInstructionReporter:
    def __init__(self, project_coverage, packages_coverage, files_coverage):
        self.project_coverage = project_coverage
        self.packages_coverage = packages_coverage
        self.files_coverage = files_coverage

    def get_report_lines(self):
        lines = []

        for file in self.files_coverage:
            row = file_row(
                self.files_coverage[file].relative_path,
                self.total_instructions(file),
                self.covered_instructions(file),
                self.missed_instructions(file),
                self.instruction_rate(file),
            )
            lines.append(row)

        footer = file_row(
            "TOTAL",
            self.total_instructions(),
            self.covered_instructions(),
            self.missed_instructions(),
            self.instruction_rate(),
        )
        lines.append(footer)

        return lines

    def total_instructions(self, file=None):
        if file:
            return len(self.files_coverage[file].instructions)
        else:
            total = 0
            for file in self.files_coverage:
                total += len(self.files_coverage[file].instructions)
            return total

    def covered_instructions(self, file=None):
        if file:
            return len(self.files_coverage[file].covered_instructions)
        else:
            total_covered = 0
            for file in self.files_coverage:
                total_covered += len(self.files_coverage[file].covered_instructions)
            return total_covered

    def missed_instructions(self, file=None):
        if file:
            num_missed = len(self.files_coverage[file].instructions) - \
                         len(self.files_coverage[file].covered_instructions)
            return num_missed
        else:
            total_missed = 0
            for file in self.files_coverage:
                num_missed = len(self.files_coverage[file].instructions) - \
                             len(self.files_coverage[file].covered_instructions)
                total_missed += num_missed
            return total_missed

    def instruction_rate(self, file=None):
        if file:
            total = self.total_instructions(file)
            covered = self.covered_instructions(file)

            try:
                instruction_coverage = covered / total
            except ZeroDivisionError:
                instruction_coverage = 0

            return instruction_coverage
        else:
            total = self.total_instructions()
            covered = self.covered_instructions()

            try:
                instruction_coverage = covered / total
            except ZeroDivisionError:
                instruction_coverage = 0

            return instruction_coverage


class CheckedTextInstructionReporter(CheckedInstructionReporter):
    def generate(self):
        lines = self.get_report_lines()

        formatted_lines = []
        for row in lines:
            filename, total_instructions, total_hits, total_misses, instruction_rate = row
            instruction_rate = "%.2f%%" % (instruction_rate * 100)
            formatted_lines.append(file_row(filename, total_instructions, total_hits, total_misses, instruction_rate))

        report = tabulate(
            formatted_lines, headers=["Filename", "Instructions", "Hits", "Misses", "Instruction Rate"]
        )

        return report


class CheckedCsvInstructionReporter(CheckedInstructionReporter):
    def generate(self):
        lines = self.get_report_lines()

        formatted_lines = []
        for row in lines:
            filename, total_instructions, total_hits, total_misses, instruction_rate = row
            instruction_rate = "%.2f%%" % (instruction_rate * 100)
            formatted_lines.append(file_row(filename, total_instructions, total_hits, total_misses, instruction_rate))

        # Header
        report = ["Filename, Instructions, Hits, Misses, Covered\n"]

        for row in formatted_lines:
            report.append("{}, {}, {}, {}, {}\n".format(row[0], row[1], row[2], row[3], row[4]))

        return report
