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


# Idea and structure are taken from the Pynguin project, see:
# https://github.com/se2p/pynguin
# Modifications were made in various parts.

#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


"""Provides capabilities to track branch distances."""
import inspect
import unittest
import ctypes

from types import MethodType, FunctionType, BuiltinFunctionType, BuiltinMethodType
from typing import Union
# noinspection PyProtectedMember
from bytecode import CellVar, FreeVar

from pyChecco.configuration import Configuration
from pyChecco.execution.executiontrace import ExecutionTrace, TracedAssertion
from pyChecco.execution.codeobjectmetadata import CodeObjectMetaData
from pyChecco.slicer.instruction import MEMORY_USE_INSTRUCTIONS
from pyChecco.utils.opcodes import *

immutable_types = [int, float, complex, str, tuple, frozenset, bytes]

testcase_mod = unittest.TestCase.__module__
testcase_cls = unittest.TestCase.__qualname__


class KnownData:
    """Contains known code objects."""

    def __init__(self) -> None:
        # Maps all known ids of Code Objects to meta information
        self.existing_code_objects = dict()
        self.file_code_objects = dict()


class ExecutionTracer:
    """Tracks instructions during execution.
    The results are stored in an execution trace."""

    _configuration: Configuration = None
    _current_test: str = None
    _setup: bool = False
    _known_data = KnownData()
    _import_trace = ExecutionTrace()
    _trace: ExecutionTrace = None
    _known_object_addresses = set()
    _current_assertion: TracedAssertion = None
    _assertion_stack_counter = 0

    def __init__(self, configuration: Configuration) -> None:
        ExecutionTracer._init_trace()
        ExecutionTracer._configuration = configuration

    def get_known_data(self) -> KnownData:
        """Provide known data."""
        return self._known_data

    @staticmethod
    def reset() -> None:
        """Resets everything. Should be called before execution a test suite.
        Clears all data, so we can handle a reload of the SUT."""
        ExecutionTracer._import_trace = ExecutionTrace(ExecutionTracer._setup)
        ExecutionTracer._current_assertion = None
        ExecutionTracer._assertion_stack_counter = 0
        ExecutionTracer._known_object_addresses = set()

        ExecutionTracer._init_trace()

    @staticmethod
    def _init_trace() -> None:
        """Create a new trace that only contains the trace data from the import."""
        new_trace = ExecutionTrace()
        ExecutionTracer._trace = new_trace

    @staticmethod
    def get_trace() -> ExecutionTrace:
        """Get the trace with the current information."""

        # Finished last found assertion
        if ExecutionTracer._current_assertion:
            ExecutionTracer._trace.end_assertion()

        return ExecutionTracer._trace

    @staticmethod
    def clear_trace() -> None:
        """Clear trace."""
        ExecutionTracer._init_trace()

    @staticmethod
    def set_current_test(test_id: str) -> None:
        ExecutionTracer._current_test = test_id
        ExecutionTracer._trace.test_id = test_id

    @staticmethod
    def set_current_module(module_name: str) -> None:
        ExecutionTracer._trace.module = True
        ExecutionTracer._trace.module_name = module_name

    @staticmethod
    def start_setup() -> None:
        ExecutionTracer._setup = True

    @staticmethod
    def end_setup() -> None:
        ExecutionTracer._setup = False

    @staticmethod
    def get_current_test() -> str:
        return ExecutionTracer._current_test

    def register_code_object(self, meta: CodeObjectMetaData) -> int:
        """Declare that a code object exists.
        :returns the id of the code object, which can be used to identify the object
        during instrumentation."""
        code_object_id = len(self._known_data.existing_code_objects)
        self._known_data.existing_code_objects[code_object_id] = meta
        if meta.filename not in self._known_data.file_code_objects:
            self._known_data.file_code_objects[meta.filename] = []
        self._known_data.file_code_objects[meta.filename].append(code_object_id)

        return code_object_id

    @staticmethod
    def track_generic(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int) -> None:
        ExecutionTracer._trace.add_instruction(module, code_object_id, node_id, op, lineno, offset)

    @staticmethod
    def track_memory_access(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int,
                            arg: Union[str, CellVar, FreeVar], arg_address: int, arg_type: type) -> None:
        if not arg:
            if op != IMPORT_NAME:  # IMPORT_NAMEs may not have an argument
                raise ValueError("A memory access instruction must have an argument")
        if isinstance(arg, CellVar) or isinstance(arg, FreeVar):
            arg = arg.name

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        # Determine if this is a definition of a completely new object (required later during slicing).
        object_creation = False
        if arg_address and arg_address not in ExecutionTracer._known_object_addresses:
            object_creation = True
            ExecutionTracer._known_object_addresses.add(arg_address)

        ExecutionTracer._trace.add_memory_instruction(module, code_object_id, node_id, op, lineno, offset,
                                                      arg, arg_address, mutable_type, object_creation)

    @staticmethod
    def track_attribute_access(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int,
                               attr_name: str, src_address: int, arg_address: int, arg_type: type) -> None:
        if op in MEMORY_USE_INSTRUCTIONS and arg_type in [MethodType, FunctionType]:
            custom_assertions = ExecutionTracer._configuration.custom_assertions
            trace = ExecutionTracer._trace

            if custom_assertions and attr_name in custom_assertions:
                if ExecutionTracer._current_assertion:
                    # Start of a new assertion, but old not finished -> end old here
                    trace.end_assertion()
                ExecutionTracer._current_assertion = trace.start_assertion(code_object_id, node_id, lineno)
            elif attr_name.startswith("assert") and attr_name in dir(unittest.TestCase):
                # Standard detection method
                # The loaded method is reconstructed from memory to check if it is indeed a method of the
                # unittest TestCase (and not, for example, a custom method with the same name)
                # noinspection PyTypeChecker
                source_object = ctypes.cast(src_address, ctypes.py_object).value
                if hasattr(source_object, "__module__") and source_object.__module__ == testcase_mod and \
                        hasattr(source_object, "__qualname__") and source_object.__qualname__.startswith(testcase_cls):
                    if ExecutionTracer._current_assertion:
                        # Start of a new assertion, but old not finished -> end old here
                        trace.end_assertion()
                    ExecutionTracer._current_assertion = trace.start_assertion(code_object_id, node_id, lineno)

        # Different built-in methods and functions often have the same address when accessed sequentially.
        # The address is not recorded in such cases.
        if arg_type is BuiltinMethodType or arg_type is BuiltinFunctionType:
            arg_address = None

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        ExecutionTracer._trace.add_attribute_instruction(module, code_object_id, node_id, op, lineno, offset,
                                                         attr_name, src_address, arg_address, mutable_type)

    @staticmethod
    def track_jump(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int, target_id: int) \
            -> None:
        ExecutionTracer._trace.add_jump_instruction(module, code_object_id, node_id, op, lineno, offset, target_id)

    @staticmethod
    def track_call(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int, arg: int) -> None:
        ExecutionTracer._trace.add_call_instruction(module, code_object_id, node_id, op, lineno, offset, arg)

        # Update current assertion
        # It is either finished already or we use the last call instruction in this line
        if ExecutionTracer._current_assertion:
            current_assertion = ExecutionTracer._current_assertion
            if current_assertion.code_object_id == code_object_id and current_assertion.node_id == node_id and \
                    current_assertion.lineno == lineno:
                current_assertion.traced_assertion_call = ExecutionTracer._trace.executed_instructions[-1]
                current_assertion.trace_position_end = len(ExecutionTracer._trace.executed_instructions) - 1

    @staticmethod
    def track_return(module: str, code_object_id: int, node_id: int, op: int, lineno: int, offset: int) -> None:
        ExecutionTracer._trace.add_return_instruction(module, code_object_id, node_id, op, lineno, offset)

    @staticmethod
    def attribute_lookup(ob, attribute: str) -> int:
        # Check the dictionary of classes making up the MRO (_PyType_Lookup)
        # The attribute must be a data descriptor to be prioritized here

        for cls in type(ob).__mro__:
            if attribute in cls.__dict__:
                # Class in the MRO hierarchy has attribute
                if inspect.isdatadescriptor(cls.__dict__.get(attribute)):
                    # Class has attribute and attribute is a data descriptor
                    return id(cls)

        # This would lead to an infinite recursion and thus a crash of the program
        if attribute == "__getattr__" or attribute == "__getitem__":
            return -1
        # Check if the dictionary of the object on which lookup is performed
        if hasattr(ob, "__dict__") and ob.__dict__:
            if attribute in ob.__dict__:
                return id(ob)
        if hasattr(ob, "__slots__") and ob.__slots__:
            if attribute in ob.__slots__:
                return id(ob)

        # Check if attribute in MRO hierarchy (no need for data descriptor)
        for cls in type(ob).__mro__:
            if attribute in cls.__dict__:
                return id(cls)

        return -1
