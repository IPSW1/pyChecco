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
import pkgutil

from dis import Instruction
from typing import Tuple, List, Set, Dict
from lxml import etree
from coverage.parser import PythonParser
from pycobertura.filesystem import filesystem_factory

from pyChecco.configuration import Configuration
from pyChecco.execution.executiontracer import KnownData
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.report.checked_pycobertura.cobertura import CheckedCobertura
from pyChecco.report.line_reporters import CheckedTextLineReporter, CheckedHtmlLineReporter, \
    CheckedCsvLineReporter
from pyChecco.report.instruction_reporters import CheckedTextInstructionReporter, CheckedCsvInstructionReporter


class FileData:
    def __init__(self, absolute_path: str, relative_path: str, package: str):
        self.absolute_path = absolute_path
        self.relative_path = relative_path
        self.package = package


class ProjectInstructionData:
    def __init__(self):
        self.total_instructions = 0
        self.total_covered_instructions = 0


class ProjectLineData:
    def __init__(self):
        self.total_lines = 0
        self.total_fully_covered = 0
        self.total_partially_covered = 0
        self.total_gt_half_covered = 0


class PackageInstructionData:
    def __init__(self, name: str):
        self.name = name
        self.total_instructions = 0
        self.total_covered_instructions = 0


class PackageLineData:
    def __init__(self, name: str):
        self.name = name
        self.total_lines = 0
        self.total_fully_covered = 0
        self.total_partially_covered = 0
        self.total_gt_half_covered = 0


class FileInstructionData:
    def __init__(self, absolute_path: str, relative_path: str, package: str, instructions: List[Instruction] = None,
                 covered_instructions: List[UniqueInstruction] = None):
        # File info
        self.absolute_path = absolute_path
        self.relative_path = relative_path
        self.package = package
        # Instruction info
        self.instructions = instructions
        self.covered_instructions = covered_instructions


class FileLineData:
    def __init__(self, absolute_path: str, relative_path: str, package: str, source_statements: Set[int] = None,
                 fully_covered_statements: Set[int] = None, partially_covered_statements: Set[int] = None,
                 gehalf_covered_lines: Set[int] = None):
        # File info
        self.absolute_path = absolute_path
        self.relative_path = relative_path
        self.package = package
        # Line info
        self.lines = source_statements
        self.fully_covered_lines = fully_covered_statements
        self.partially_covered_lines = partially_covered_statements
        self.gehalf_covered_lines = gehalf_covered_lines


class CoverageCalculator:
    def __init__(self, configuration: Configuration, known_data: KnownData):
        self._configuration = configuration
        self.known_data = known_data

        self.files: Dict[str, FileData] = {}
        self.find_files_and_modules()

    def find_files_and_modules(self):
        packages = []

        # Find all packages in project
        for importer, modname, ispkg in pkgutil.walk_packages(path=[self._configuration.project_path]):
            if ispkg:
                packages.append(modname)

        for root, dirs, files in os.walk(self._configuration.project_path):
            source_path = None
            file_name = self._configuration.file

            if self._configuration.source:
                source_path = os.path.join(self._configuration.project_path, self._configuration.source)

            if (not source_path or root.startswith(source_path)) and "/venv/" not in root:
                for file in files:
                    if (not file_name or file == file_name) and file.endswith(".py") and "/venv/" not in root:
                        absolute_path = os.path.join(root, file)
                        relative_path = os.path.join(root[len(self._configuration.project_path):], file)
                        package = self._find_module_package(relative_path, packages)

                        if relative_path not in self.files:
                            file_coverage = FileData(absolute_path, relative_path, package)
                            self.files[absolute_path] = file_coverage

    def calculate_instruction_coverage(self, file_slices: Dict[str, List[UniqueInstruction]]):
        file_instruction_coverage = {}
        package_instruction_coverage = {}
        project_instruction_coverage = ProjectInstructionData()

        for file in self.files:
            # Update specific file data
            instructions = self._get_file_instructions(file)
            covered_instructions = []
            if file in file_slices:
                covered_instructions = self._get_covered_instructions(file_slices[file])

            file_instruction_data = FileInstructionData(file, self.files[file].relative_path, self.files[file].package)
            file_instruction_data.instructions = instructions
            file_instruction_data.covered_instructions = covered_instructions

            file_instruction_coverage[file] = file_instruction_data

            # Update complete package data
            file_package = self.files[file].package
            if file_package not in package_instruction_coverage:
                package_instruction_coverage[file_package] = PackageInstructionData(file_package)
            package_instruction_coverage[file_package].total_instructions += len(instructions)
            package_instruction_coverage[file_package].total_covered_instructions += len(covered_instructions)

            # Update project data
            project_instruction_coverage.total_instructions += len(instructions)
            project_instruction_coverage.total_covered_instructions += len(covered_instructions)

        return project_instruction_coverage, package_instruction_coverage, file_instruction_coverage

    def calculate_line_coverage(self, file_slices: Dict[str, List[UniqueInstruction]]):
        file_line_coverage = {}
        package_line_coverage = {}
        project_line_coverage = ProjectLineData()

        for file in self.files:
            executable_lines = self._get_file_lines(file)

            # Calculate how many instructions each line has
            line_instructions = self._count_line_instructions(file)

            # Calculate how many instructions per line are covered, if any
            covered_line_instructions = {}
            if file in file_slices:
                covered_line_instructions = self._count_covered_line_instructions(file_slices[file])

            fully_covered = set()
            partially_covered = set()
            gehalf_covered = set()
            # Check if lines are fully or only partially covered
            for line in covered_line_instructions:
                if covered_line_instructions[line] == line_instructions[line]:
                    fully_covered.add(line)
                else:
                    partially_covered.add(line)

                # For coverage calculation, we consider a line covered if more than half of its instructions
                # are covered
                if covered_line_instructions[line] * 2 >= line_instructions[line]:
                    gehalf_covered.add(line)

            # Update file data
            file_line_data = FileLineData(file, self.files[file].relative_path, self.files[file].package)
            file_line_data.lines = executable_lines
            file_line_data.fully_covered_lines = fully_covered
            file_line_data.partially_covered_lines = partially_covered
            file_line_data.gehalf_covered_lines = gehalf_covered

            file_line_coverage[file] = file_line_data

            # Update package data
            # Update complete package data
            file_package = self.files[file].package
            if file_package not in package_line_coverage:
                package_line_coverage[file_package] = PackageLineData(file_package)
            package_line_coverage[file_package].total_lines += len(executable_lines)
            package_line_coverage[file_package].total_fully_covered += len(fully_covered)
            package_line_coverage[file_package].total_partially_covered += len(partially_covered)
            package_line_coverage[file_package].total_gt_half_covered += len(gehalf_covered)

            # Update project data
            project_line_coverage.total_lines += len(executable_lines)
            project_line_coverage.total_fully_covered += len(fully_covered)
            project_line_coverage.total_partially_covered += len(partially_covered)
            project_line_coverage.total_gt_half_covered += len(gehalf_covered)

        return project_line_coverage, package_line_coverage, file_line_coverage

    def generate_coberture_xml(self, project_line_coverage: ProjectLineData,
                               package_line_coverage: Dict[str, PackageLineData],
                               file_line_coverage: Dict[str, FileLineData]):
        try:
            proj_coverage = project_line_coverage.total_gt_half_covered / project_line_coverage.total_lines
        except ZeroDivisionError:
            proj_coverage = 0
        xcoverage, xpackages = self._prepare_xml(self._configuration.project_path, proj_coverage)

        # Write package elements
        for package in package_line_coverage:
            xpackage = etree.SubElement(xpackages, 'package')
            xpackage.set('name', package)

            covered_package_lines = package_line_coverage[package].total_gt_half_covered
            try:
                package_coverage = covered_package_lines / package_line_coverage[package].total_lines
            except ZeroDivisionError:
                package_coverage = 0
            xpackage.set('line-rate', "{:.2f}".format(package_coverage))
            etree.SubElement(xpackage, 'classes')

        for file in file_line_coverage:
            # Find package/classes element
            xclasses = xpackages.xpath("./package[@name='%s']/classes" % file_line_coverage[file].package)[0]

            xmodule = etree.SubElement(xclasses, 'class')
            xmodule.set('filename', file_line_coverage[file].relative_path)
            xmodule.set('name', file_line_coverage[file].relative_path)

            covered_file_lines = len(file_line_coverage[file].gehalf_covered_lines)
            try:
                line_coverage = covered_file_lines / len(file_line_coverage[file].lines)
            except ZeroDivisionError:
                line_coverage = 0

            xmodule.set('line-rate', "{:.2f}".format(line_coverage))

            lines = etree.SubElement(xmodule, 'lines')

            for line in file_line_coverage[file].lines:
                line_element = etree.SubElement(lines, 'line')
                line_element.set('number', str(line))
                if line in file_line_coverage[file].fully_covered_lines:  # line fully covered
                    line_element.set('hits', '1')
                    line_element.set('full', '1')
                elif line in file_line_coverage[file].partially_covered_lines:  # line partially covered
                    line_element.set('hits', '1')
                    line_element.set('full', '0')
                else:
                    line_element.set('hits', '0')

                if line in file_line_coverage[file].gehalf_covered_lines:
                    line_element.set('gehalf', '1')
                else:
                    line_element.set('gehalf', '0')
        # Create output directory
        output_path = os.path.join(self._configuration.project_path, self._configuration.report_dir)
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        # Write to file
        output_file = os.path.join(output_path, "checked_coverage.xml")
        with open(output_file, "wb") as xml_file:
            xml_file.write(etree.tostring(xcoverage, encoding='utf-8', xml_declaration=True, pretty_print=True))

        return output_file

    def generate_line_html_report(self, cobertura_xml: str):
        cobertura_filesystem = filesystem_factory(source=self._configuration.project_path)
        cobertura = CheckedCobertura(cobertura_xml, filesystem=cobertura_filesystem)
        html_reporter = CheckedHtmlLineReporter(cobertura)
        html_report = html_reporter.generate()

        output_path = self._make_output_directory()

        output_file = os.path.join(output_path, "line_coverage.html")
        with open(output_file, "w") as html_file:
            html_file.write(html_report)

    def generate_line_csv_report(self, cobertura_xml: str):
        cobertura_filesystem = filesystem_factory(source=self._configuration.project_path)
        cobertura = CheckedCobertura(cobertura_xml, filesystem=cobertura_filesystem)
        csv_reporter = CheckedCsvLineReporter(cobertura)
        csv_report = csv_reporter.generate()

        output_path = self._make_output_directory()

        output_file = os.path.join(output_path, "line_coverage.csv")
        with open(output_file, "w") as csv_file:
            csv_file.writelines(csv_report)

    def generate_line_text_report(self, cobertura_xml: str):
        cobertura_filesystem = filesystem_factory(source=self._configuration.project_path)
        cobertura = CheckedCobertura(cobertura_xml, filesystem=cobertura_filesystem)
        text_reporter = CheckedTextLineReporter(cobertura)
        text_report = text_reporter.generate()

        output_path = self._make_output_directory()

        output_file = os.path.join(output_path, "line_coverage.txt")
        with open(output_file, "w") as text_file:
            text_file.write(text_report)

    def print_line_text_report(self, cobertura_xml: str):
        cobertura_filesystem = filesystem_factory(source=self._configuration.project_path)
        cobertura = CheckedCobertura(cobertura_xml, filesystem=cobertura_filesystem)
        text_reporter = CheckedTextLineReporter(cobertura)
        text_report = text_reporter.generate()

        print(text_report)

    def generate_instruction_text_report(self, project_coverage, packages_coverage, files_coverage):
        text_reporter = CheckedTextInstructionReporter(project_coverage, packages_coverage, files_coverage)
        text_report = text_reporter.generate()

        output_path = self._make_output_directory()

        output_file = os.path.join(output_path, "instruction_coverage.txt")
        with open(output_file, "w") as text_file:
            text_file.write(text_report)

    def generate_instruction_csv_report(self, project_coverage, packages_coverage, files_coverage):
        csv_reporter = CheckedCsvInstructionReporter(project_coverage, packages_coverage, files_coverage)
        csv_report = csv_reporter.generate()

        output_path = self._make_output_directory()

        output_file = os.path.join(output_path, "instruction_coverage.csv")
        with open(output_file, "w") as csv_file:
            csv_file.writelines(csv_report)

    def _get_file_instructions(self, file: str) -> List[Instruction]:
        file_instructions = []

        file_code_objects = self.known_data.file_code_objects[file]
        for code_object_id in file_code_objects:
            file_instructions.extend(self.known_data.existing_code_objects[code_object_id].disassembly)

        return file_instructions

    def _make_output_directory(self) -> str:
        output_path = os.path.join(self._configuration.project_path, self._configuration.report_dir)
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        return output_path

    @staticmethod
    def print_instruction_text_report(project_coverage, packages_coverage, files_coverage):
        text_reporter = CheckedTextInstructionReporter(project_coverage, packages_coverage, files_coverage)
        text_report = text_reporter.generate()

        print(text_report)

    @staticmethod
    def _get_covered_instructions(file_slice: List[UniqueInstruction]) -> List[UniqueInstruction]:
        # Remove duplicates
        covered_instructions = list(set(file_slice))

        return covered_instructions

    def _count_line_instructions(self, file: str) -> Dict[int, int]:
        line_count = dict()

        file_code_objects = self.known_data.file_code_objects[file]
        for code_object_id in file_code_objects:
            instructions = self.known_data.existing_code_objects[code_object_id].disassembly

            current_line = -1

            for instruction in instructions:
                if instruction.starts_line:
                    current_line = instruction.starts_line

                if current_line not in line_count:
                    line_count[current_line] = 0

                line_count[current_line] = line_count[current_line] + 1

        return line_count

    @staticmethod
    def _count_covered_line_instructions(file_slice: List[UniqueInstruction]) -> Dict[int, int]:
        line_count = dict()
        covered_instructions = list(set(file_slice))

        for instruction in covered_instructions:
            if instruction.lineno not in line_count:
                line_count[instruction.lineno] = 0
            line_count[instruction.lineno] = line_count[instruction.lineno] + 1

        return line_count

    @staticmethod
    def _find_module_package(module_path: str, packages: List[str]):
        module_package = ""

        for package in packages:
            package_dir = package.replace(".", os.sep)
            if module_path.startswith(package_dir) and len(package_dir) > len(module_package):
                module_package = package

        return module_package

    @staticmethod
    def _get_file_lines(file: str) -> Set[int]:
        parser = PythonParser(filename=file)
        parser.parse_source()

        return parser.raw_statements

    @staticmethod
    def _prepare_xml(project_path: str, project_line_coverage: float) -> Tuple[etree.Element, etree.Element]:
        coverage = etree.Element('coverage')
        coverage.set('line-rate', "{:.2f}".format(project_line_coverage))
        sources = etree.SubElement(coverage, 'sources')
        project_source = etree.SubElement(sources, 'source')
        project_source.text = project_path

        packages = etree.SubElement(coverage, 'packages')

        return coverage, packages
