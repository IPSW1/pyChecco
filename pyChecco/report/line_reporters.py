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


import pycobertura

from jinja2 import Environment, PackageLoader
from collections import namedtuple
from pycobertura.utils import rangify
from tabulate import tabulate
from typing import List

from pyChecco.report.checked_pycobertura.templates import filters

env = Environment(loader=PackageLoader("pyChecco.report.checked_pycobertura", "templates"))
env.filters["line_status"] = filters.line_status

row_attributes_missed = "filename total_statements total_full total_partial total_misses total_gehalf " \
                        "line_rate missed_lines"
file_row_missed = namedtuple("FileRowMissed", row_attributes_missed)


class CheckedLineReporter(pycobertura.reporters.Reporter):
    def get_report_lines(self):
        lines = []

        for filename in self.cobertura.files():
            row = file_row_missed(
                filename,
                self.cobertura.total_statements(filename),
                self.cobertura.total_full(filename),
                self.cobertura.total_partial(filename),
                self.cobertura.total_gehalf(filename),
                self.cobertura.total_misses(filename),
                self.cobertura.line_rate(filename),
                self.cobertura.missed_lines(filename),
            )
            lines.append(row)

        footer = file_row_missed(
            "TOTAL",
            self.cobertura.total_statements(),
            self.cobertura.total_full(),
            self.cobertura.total_partial(),
            self.cobertura.total_gehalf(),
            self.cobertura.total_misses(),
            self.cobertura.line_rate(),
            [],  # dummy missed lines
        )
        lines.append(footer)

        return lines


class CheckedTextLineReporter(CheckedLineReporter, pycobertura.reporters.Reporter):
    def generate(self):
        lines = self.get_report_lines()

        formatted_lines = []
        for row in lines:
            formatted_row = self.format_row(row)
            formatted_lines.append(formatted_row)

        report = tabulate(
            formatted_lines, headers=["Filename", "Statements", "Full Cover", "Partial Cover", "GEHalf", "Miss",
                                      "Cover", "Missing"]
        )

        return report

    @staticmethod
    def format_row(row):
        filename, total_lines, total_full, total_partial, total_gehalf, total_misses, line_rate, missed_lines = row

        line_rate = "%.2f%%" % (line_rate * 100)

        formatted_missed_lines = []
        for line_start, line_stop in rangify(missed_lines):
            if line_start == line_stop:
                formatted_missed_lines.append("%s" % line_start)
            else:
                line_range = "%s-%s" % (line_start, line_stop)
                formatted_missed_lines.append(line_range)
        formatted_missed_lines = ", ".join(formatted_missed_lines)

        row = file_row_missed(
            filename, total_lines, total_full, total_partial, total_gehalf, total_misses, line_rate,
            formatted_missed_lines,
        )

        return row


class CheckedHtmlLineReporter(CheckedTextLineReporter):
    def __init__(self, *args, **kwargs):
        self.title = kwargs.pop("title", "pyChecco report")
        self.render_file_sources = kwargs.pop("render_file_sources", True)
        self.no_file_sources_message = kwargs.pop(
            "no_file_sources_message", "Rendering of source files was disabled."
        )
        super(CheckedHtmlLineReporter, self).__init__(*args, **kwargs)

    def get_source(self, filename):
        lines = self.cobertura.file_source(filename)
        return lines

    def generate(self):
        lines = self.get_report_lines()

        formatted_lines = []
        for row in lines:
            formatted_row = self.format_row(row)
            formatted_lines.append(formatted_row)

        sources = []
        if self.render_file_sources:
            for filename in self.cobertura.files():
                source = self.get_source(filename)
                sources.append((filename, source))

        template = env.get_template("html.jinja2")
        return template.render(
            title=self.title,
            lines=formatted_lines[:-1],
            footer=formatted_lines[-1],
            sources=sources,
            no_file_sources_message=self.no_file_sources_message,
        )


class CheckedCsvLineReporter(CheckedTextLineReporter):
    def generate(self) -> List[str]:
        lines = self.get_report_lines()

        formatted_lines = []
        for row in lines:
            formatted_row = self.format_row(row)
            formatted_lines.append(formatted_row)

        # Header
        report = ["Filename, Statements, Full, Partial, GEHalf, Missed, Covered\n"]

        for row in formatted_lines:
            report.append("{}, {}, {}, {}, {}, {}, {}\n".format(row[0], row[1], row[2], row[3], row[4], row[5], row[6]))

        return report
