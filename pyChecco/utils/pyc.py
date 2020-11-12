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

# Parsing of the .pyc header is inspired by
# https://nedbatchelder.com/blog/200804/the_structure_of_pyc_files.html

import struct
import time
import marshal
from types import CodeType

from pyChecco.instrumentation.instruction_instrumentation import InstructionInstrumentation


class Pyc:
    """
    Class representing a compiled Python file in .pyc format
    """
    def __init__(self, file: str):
        self._file = file

        self._magic = None
        self._flags = None
        self._timestamp = None
        self._size = None
        self._code = None

        self._unpack_pyc()

    def _unpack_pyc(self):
        """
        Unpack a pyc file from version 3.6
        Format pyc file:
            - 4 bytes magic number
            - 4 bytes flags
            - 4 bytes compilation timestamp
            - 4 bytes size (of sourcecode)
            - rest: module code object
        :return magic number, flags, timestamp, size and module code object
        """
        f = open(self._file, "rb")

        self._magic = f.read(4)
        self._flags = f.read(4)
        self._timestamp = f.read(4)
        self._size = f.read(4)

        self._code = marshal.load(f)
        f.close()

    def get_path(self) -> str:
        return self._file

    def get_header_data(self):
        return self._magic, self._flags, self._timestamp, self._size

    def print_header(self):
        unix_time = struct.unpack("I", self._timestamp)[0]
        formatted_time = time.asctime(time.localtime(unix_time))
        formatted_size = struct.unpack("I", self._size)[0]
        print("\tFilename:     {}".format(self._file))
        print("\tMagic number: {}".format(self._magic))
        print("\tTimestamp:    {} ({})".format(unix_time, formatted_time))
        print("\tSource size:  {} bytes".format(formatted_size))

    def get_code_object(self):
        return self._code

    def set_code_object(self, code: CodeType):
        self._code = CodeType(
            code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_nlocals, code.co_stacksize,
            code.co_flags, code.co_code, code.co_consts, code.co_names, code.co_varnames, code.co_filename,
            code.co_name, code.co_firstlineno, code.co_lnotab, code.co_freevars, code.co_cellvars
        )

    def instrument(self, instrumenter: InstructionInstrumentation):
        instrumented_code = instrumenter.instrument_module(self._code)

        self.set_code_object(instrumented_code)

    def write(self, file):
        # Write the to a compiled Python file
        with open(file, "wb") as f:
            f.write(self._magic)
            f.write(self._flags)
            f.write(self._timestamp)
            f.write(self._size)
        f = open(file, "ab+")
        marshal.dump(self._code, f)

        return file

    def overwrite(self):
        # Write the to a compiled Python file
        with open(self._file, "wb") as f:
            f.write(self._magic)
            f.write(self._flags)
            f.write(self._timestamp)
            f.write(self._size)
        f = open(self._file, "ab+")
        marshal.dump(self._code, f)
        f.close()

        return self._file
