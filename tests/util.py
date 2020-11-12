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


import py_compile
import importlib.util

# noinspection PyProtectedMember
from bytecode import Instr, BasicBlock
from types import CodeType
from typing import List

from pyChecco.configuration import Configuration
from pyChecco.instrumentation.instruction_instrumentation import InstructionInstrumentation
from pyChecco.execution.executiontrace import ExecutionTrace
from pyChecco.execution.executiontracer import ExecutionTracer
from pyChecco.execution.testexecution.testexecutor import TestExecutor
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.slicer.dynamic_slicer import DynamicSlicer, SlicingCriterion, DynamicSlice
from pyChecco.utils.pyc import Pyc

dummy_code_object = CodeType(0, 0, 0, 0, 0, 0, bytes(), (), (), (), "", "", 0, bytes())


def compare(dynamic_slice: List[UniqueInstruction], expected_slice: List[Instr]):
    expected_copy = expected_slice.copy()
    slice_copy = dynamic_slice.copy()

    for unique_instr in dynamic_slice:
        if isinstance(unique_instr.arg, BasicBlock) or isinstance(unique_instr.arg, CodeType) or \
                isinstance(unique_instr.arg, tuple):
            # Don't distinguish arguments for basic blocks, code objects and tuples
            jump_instr = _contains_name_argtype(expected_copy, unique_instr)
            try:
                expected_copy.remove(jump_instr)
                slice_copy.remove(unique_instr)
            except ValueError:
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg)
        else:
            found_instr = _contains_name_arg(expected_slice, unique_instr)
            if found_instr:
                try:
                    expected_copy.remove(found_instr)
                    slice_copy.remove(unique_instr)
                except ValueError:
                    msg = str(found_instr) + " not in expected slice\n"
                    msg += "Remaining in expected: " + str(expected_copy) + "\n"
                    msg += "Remaining in computed: " + str(slice_copy)
                    raise ValueError(msg)
            else:
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg)

    if len(expected_copy) != 0:
        raise ValueError("Expected slice has remaining instructions:", expected_copy)
    if len(slice_copy) != 0:
        raise ValueError("Real slice has remaining instructions:", slice_copy)

    return True


def _contains_name_arg(instr_list: List[Instr], unique_instr: UniqueInstruction):
    for instr in instr_list:
        if instr.name == unique_instr.name:
            if isinstance(unique_instr.arg, BasicBlock) or isinstance(unique_instr.arg, CodeType):
                # Instruction is a jump to a basic block
                return instr
            elif isinstance(unique_instr.arg, tuple) and isinstance(instr.arg, tuple):
                for elem in unique_instr.arg:
                    if elem not in instr.arg:
                        break
                return instr
            elif instr.arg == unique_instr.arg:
                return instr
    return None


def _contains_name_argtype(instr_list: List[Instr], unique_instr: UniqueInstruction):
    for instr in instr_list:
        if instr.name == unique_instr.name:
            if isinstance(instr.arg, type(unique_instr.arg)):
                return instr
    return None


def slice_function_at_return(function_code: CodeType, test_name: str = None,
                             debug_output: bool = False) -> DynamicSlice:
    # Setup
    configuration = Configuration("", "")
    tracer = ExecutionTracer(configuration)
    instrumentation = InstructionInstrumentation(tracer)

    # Instrument and call example function
    instr_function = instrumentation.instrument_code_recursive(function_code, -1)
    tracer.reset()
    tracer.set_current_test(test_name)
    exec(instr_function)

    # Slice
    trace = tracer.get_trace()
    known_code_objects = tracer.get_known_data().existing_code_objects
    dynamic_slicer = DynamicSlicer(configuration, trace, known_code_objects)

    # Slicing criterion at foo
    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(last_traced_instr.file, last_traced_instr.name,
                                            lineno=last_traced_instr.lineno,
                                            code_object_id=last_traced_instr.code_object_id,
                                            node_id=last_traced_instr.node_id,
                                            code_meta=known_code_objects.get(last_traced_instr.code_object_id),
                                            offset=last_traced_instr.offset)
    slicing_criterion = SlicingCriterion(slicing_instruction)
    dynamic_slice = dynamic_slicer.slice(trace, slicing_criterion, len(trace.executed_instructions) - 2, debug_output)

    return dynamic_slice


def slice_module_at_return(module_file: str, debug_output: bool = False) -> DynamicSlice:
    compiled_file = py_compile.compile(module_file)

    pyc_file = Pyc(compiled_file)
    module_code = pyc_file.get_code_object()

    # Setup
    configuration = Configuration("", "")
    tracer = ExecutionTracer(configuration)
    instrumentation = InstructionInstrumentation(tracer)

    # Instrument and call module
    instr_module = instrumentation.instrument_module(module_code)
    pyc_file.set_code_object(instr_module)
    pyc_file.overwrite()
    tracer.reset()
    tracer.set_current_test(instr_module.co_name)

    spec = importlib.util.spec_from_file_location(module_file[:-3], module_file)
    example_module = importlib.util.module_from_spec(spec)
    # noinspection PyUnresolvedReferences
    spec.loader.exec_module(example_module)

    # Slice
    trace = tracer.get_trace()
    known_code_objects = tracer.get_known_data().existing_code_objects
    dynamic_slicer = DynamicSlicer(configuration, trace, known_code_objects)

    # Slicing criterion at foo
    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(last_traced_instr.file, last_traced_instr.name,
                                            lineno=last_traced_instr.lineno,
                                            code_object_id=last_traced_instr.code_object_id,
                                            node_id=last_traced_instr.node_id,
                                            code_meta=known_code_objects.get(last_traced_instr.code_object_id),
                                            offset=last_traced_instr.offset)
    slicing_criterion = SlicingCriterion(slicing_instruction, global_variables={("result", last_traced_instr.file)})
    dynamic_slice = dynamic_slicer.slice(trace, slicing_criterion, len(trace.executed_instructions) - 2, debug_output)

    py_compile.compile(module_file, cfile=compiled_file)

    return dynamic_slice


def trace_call(module_dir: str, module_file: str, pattern: str, custom_assertions: List = None) -> ExecutionTrace:
    compiled_file = py_compile.compile(module_file)

    pyc_file = Pyc(compiled_file)
    module_code = pyc_file.get_code_object()

    # Setup
    configuration = Configuration(module_dir, "", pattern=pattern, custom_assertions=custom_assertions)
    tracer = ExecutionTracer(configuration)
    instrumentation = InstructionInstrumentation(tracer)

    # Instrument and call module
    instr_module = instrumentation.instrument_module(module_code)
    pyc_file.set_code_object(instr_module)
    pyc_file.overwrite()

    test_executor = TestExecutor(configuration, tracer)
    test_executor.execute_testsuite()

    # Get trace
    trace = test_executor.get_current_trace()

    py_compile.compile(module_file, cfile=compiled_file)

    return trace


def instrument_module(module_file: str):
    compiled_file = py_compile.compile(module_file)

    pyc_file = Pyc(compiled_file)
    module_code = pyc_file.get_code_object()

    # Setup
    configuration = Configuration("", "")
    tracer = ExecutionTracer(configuration)
    instrumentation = InstructionInstrumentation(tracer)

    # Instrument and call module
    instr_module = instrumentation.instrument_module(module_code)
    pyc_file.set_code_object(instr_module)
    pyc_file.overwrite()


def compile_module(module_file: str) -> str:
    return py_compile.compile(module_file)
