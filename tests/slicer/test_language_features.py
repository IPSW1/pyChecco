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
import unittest

# noinspection PyProtectedMember
from bytecode import Instr, BasicBlock, Compare, FreeVar, CellVar

from tests.util import compare, slice_function_at_return, slice_module_at_return, dummy_code_object

path_sep = os.path.sep
example_modules_directory = "example_modules/"
example_modules_path = path_sep.join(__file__.split(path_sep)[:-1]) + path_sep + example_modules_directory


class IntegrationTestLanguageFeatures(unittest.TestCase):
    def test_simple_loop(self):
        def func():
            result = 0
            for i in range(0, 3):
                result += i
            return result

        return_block = BasicBlock([
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE")
        ])
        loop_header = BasicBlock([
            Instr("FOR_ITER", arg=return_block),
        ])
        loop_block = BasicBlock([
            # result += i
            Instr("STORE_FAST", arg="i"),
            Instr("LOAD_FAST", arg="result"),
            Instr("LOAD_FAST", arg="i"),
            Instr("INPLACE_ADD"),
            Instr("STORE_FAST", arg="result"),
            Instr("JUMP_ABSOLUTE", arg=loop_header),
        ])
        loop_setup = BasicBlock([
            # for i in range(0, 3):
            Instr("LOAD_GLOBAL", arg="range"),
            Instr("LOAD_CONST", arg=0),
            Instr("LOAD_CONST", arg=3),
            Instr("CALL_FUNCTION", arg=2),
            Instr("GET_ITER"),
        ])
        init_block = BasicBlock([
            Instr("LOAD_CONST", arg=0),
            Instr("STORE_FAST", arg="result"),
        ])

        expected_instructions = []
        expected_instructions.extend(init_block)
        expected_instructions.extend(loop_setup)
        expected_instructions.extend(loop_header)
        expected_instructions.extend(loop_block)
        expected_instructions.extend(return_block)

        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_simple_loop")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_call_without_arguments(self):
        module_block = BasicBlock([
            # def callee():
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="callee"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="callee"),
            # result = callee()
            Instr("LOAD_NAME", arg="callee"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="result"),
            # return result
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])
        callee_block = BasicBlock([
            Instr("LOAD_CONST", arg=0),
            Instr("RETURN_VALUE")
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        expected_instructions.extend(callee_block)

        module_file = "simple_call.py"
        module_path = example_modules_path + module_file
        dynamic_slice = slice_module_at_return(module_path)
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_call_with_arguments(self):
        # Call with two arguments, one of which is used in the callee

        module_block = BasicBlock([
            # def callee():
            Instr("LOAD_NAME", arg="int"),
            Instr("LOAD_NAME", arg="int"),
            Instr("LOAD_CONST", arg=('a', 'b')),
            Instr("BUILD_CONST_KEY_MAP", arg=2),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="callee"),
            Instr("MAKE_FUNCTION", arg=4),
            Instr("STORE_NAME", arg="callee"),
            # foo = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_NAME", arg="foo"),
            # bar = 2
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_NAME", arg="bar"),

            # result = callee()
            Instr("LOAD_NAME", arg="callee"),
            Instr("LOAD_NAME", arg="foo"),
            Instr("LOAD_NAME", arg="bar"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="result"),
            # return result
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])
        callee_block = BasicBlock([
            # return a
            Instr("LOAD_FAST", arg="a"),
            Instr("RETURN_VALUE")
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        expected_instructions.extend(callee_block)

        module_file = "simple_call_arg.py"
        module_path = example_modules_path + module_file
        dynamic_slice = slice_module_at_return(module_path)
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_generators(self):
        # YIELD_VALUE and YIELD_FROM
        abc_generator = BasicBlock([
            # a = "a"
            Instr("LOAD_CONST", arg="a"),
            Instr("STORE_FAST", arg="a"),
            # yield a
            Instr("LOAD_FAST", arg="a"),
            Instr("YIELD_VALUE"),
        ])

        abc_xyz_generator = BasicBlock([
            # x = "x"
            Instr("LOAD_CONST", arg="x"),
            Instr("STORE_FAST", arg="x"),

            # yield from abc_generator()
            Instr("LOAD_GLOBAL", arg="abc_generator"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("GET_YIELD_FROM_ITER"),
            Instr("LOAD_CONST", arg=None),
            Instr("YIELD_FROM"),
            # yield x
            Instr("LOAD_FAST", arg="x"),
            Instr("YIELD_VALUE"),
        ])

        end_block = BasicBlock([
            # return result
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])
        loop_block = BasicBlock([
            Instr("STORE_NAME", arg="letter"),
        ])
        loop_header = BasicBlock([
            Instr("FOR_ITER", arg=end_block),
        ])
        loop_if_true_block = BasicBlock([
            Instr("LOAD_NAME", arg="result"),
            Instr("LOAD_NAME", arg="letter"),
            Instr("INPLACE_ADD"),
            Instr("STORE_NAME", arg="result"),
            Instr("JUMP_ABSOLUTE", arg=loop_header),
        ])
        loop_if_x_block = BasicBlock([
            Instr("LOAD_NAME", arg="letter"),
            Instr("LOAD_CONST", arg="x"),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_TRUE", arg=loop_if_true_block),
        ])
        loop_if_a_block = BasicBlock([
            Instr("LOAD_NAME", arg="letter"),
            Instr("LOAD_CONST", arg="a"),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_FALSE", arg=loop_header)
        ])
        module_block = BasicBlock([
            # def abc_generator():
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="abc_generator"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="abc_generator"),
            # def abc_xyz_generator():
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="abc_xyz_generator"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="abc_xyz_generator"),
            # generator = abc_xyz_generator()
            Instr("LOAD_NAME", arg="abc_xyz_generator"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="generator"),
            # result = ""
            Instr("LOAD_CONST", arg=""),
            Instr("STORE_NAME", arg="result"),
            # for letter in generator:
            Instr("LOAD_NAME", arg="generator"),
            Instr("GET_ITER"),
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        expected_instructions.extend(loop_header)
        expected_instructions.extend(loop_block)
        expected_instructions.extend(loop_if_x_block)
        expected_instructions.extend(loop_if_a_block)
        expected_instructions.extend(loop_if_true_block)
        expected_instructions.extend(end_block)
        expected_instructions.extend(abc_xyz_generator)
        expected_instructions.extend(abc_generator)

        module_file = "generator.py"
        module_path = example_modules_path + module_file
        dynamic_slice = slice_module_at_return(module_path)
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_with_extended_arg(self):
        def func():
            p = [1, 2, 3, 4, 5, 6]
            # noinspection PyUnusedLocal
            unused = p
            q, r, *s, t = p  # With extended argument

            result = q, r
            return result

        module_block = BasicBlock([
            # p = [1, 2, 3, 4, 5, 6]
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_CONST", arg=2),
            Instr("LOAD_CONST", arg=3),
            Instr("LOAD_CONST", arg=4),
            Instr("LOAD_CONST", arg=5),
            Instr("LOAD_CONST", arg=6),
            Instr("BUILD_LIST", arg=6),
            Instr("STORE_FAST", arg="p"),
            # q, r, *s, t = p
            Instr("LOAD_FAST", arg="p"),
            # Instr("EXTENDED_ARG", arg=1),  # EXTENDED_ARG can not be in a slice
            Instr("UNPACK_EX", arg=258),
            Instr("STORE_FAST", arg="q"),
            Instr("STORE_FAST", arg="r"),

            # result = q
            Instr("LOAD_FAST", arg="q"),
            Instr("LOAD_FAST", arg="r"),
            Instr("BUILD_TUPLE", arg=2),
            Instr("STORE_FAST", arg="result"),
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_with_extended_arg")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_nested_class(self):
        def func():
            # STORE_DEREF, LOAD_CLOSURE, LOAD_CLASSDEREF
            x = []

            class NestedClass:
                y = x

            class_attr = NestedClass.y

            result = class_attr
            return result

        freevar_x = FreeVar("x")
        cellvar_x = CellVar("x")
        function_block = BasicBlock([
            # x = []
            Instr("BUILD_LIST", arg=0),
            Instr("STORE_DEREF", arg=cellvar_x),

            # class NestedClass:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CLOSURE", arg=cellvar_x),
            Instr("BUILD_TUPLE", arg=1),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="NestedClass"),
            Instr("MAKE_FUNCTION", arg=8),
            Instr("LOAD_CONST", arg="NestedClass"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_FAST", arg="NestedClass"),

            # class_attr = NestedClass.y
            Instr("LOAD_FAST", arg="NestedClass"),
            Instr("LOAD_ATTR", arg="y"),
            Instr("STORE_FAST", arg="class_attr"),

            # result = class_attr
            Instr("LOAD_FAST", arg="class_attr"),
            Instr("STORE_FAST", arg="result"),

            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        nested_class_block = BasicBlock([
            # y = x
            Instr("LOAD_CLASSDEREF", arg=freevar_x),
            Instr("STORE_NAME", arg="y"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(function_block)
        expected_instructions.extend(nested_class_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_nested_class")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_nested_class_2(self):
        # Critical test to ensure that the attributes converted to variables
        # are taken from the correct scope.

        def func():
            # STORE_DEREF, LOAD_CLOSURE, LOAD_CLASSDEREF
            x1 = [1]
            x2 = [2]

            class Bar:
                foo = x1  # included!

                class Foo:
                    foo = x2  # NOT included
                    y = x2  # included

                y = Foo.y  # NOT included

            class_attr = Bar.foo
            class_attr2 = Bar.Foo.y

            result = class_attr + class_attr2
            return result

        freevar_x1 = FreeVar("x1")
        cellvar_x1 = CellVar("x1")
        freevar_x2 = FreeVar("x2")
        cellvar_x2 = CellVar("x2")
        function_block = BasicBlock([
            # x1 = [1]
            Instr("LOAD_CONST", arg=1),
            Instr("BUILD_LIST", arg=1),
            Instr("STORE_DEREF", arg=cellvar_x1),
            # x2 = [2]
            Instr("LOAD_CONST", arg=2),
            Instr("BUILD_LIST", arg=1),
            Instr("STORE_DEREF", arg=cellvar_x2),

            # class Bar:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CLOSURE", arg=cellvar_x1),
            Instr("LOAD_CLOSURE", arg=freevar_x2),
            Instr("BUILD_TUPLE", arg=2),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Bar"),
            Instr("MAKE_FUNCTION", arg=8),
            Instr("LOAD_CONST", arg="Bar"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_FAST", arg="Bar"),

            # class_attr = Bar.y
            Instr("LOAD_FAST", arg="Bar"),
            Instr("LOAD_ATTR", arg="foo"),
            Instr("STORE_FAST", arg="class_attr"),

            # class_attr2 = Bar.Foo.y
            Instr("LOAD_FAST", arg="Bar"),
            Instr("LOAD_ATTR", arg="Foo"),
            Instr("LOAD_ATTR", arg="y"),
            Instr("STORE_FAST", arg="class_attr2"),

            # result = class_attr + class_attr2
            Instr("LOAD_FAST", arg="class_attr"),
            Instr("LOAD_FAST", arg="class_attr2"),
            Instr("BINARY_ADD"),
            Instr("STORE_FAST", arg="result"),

            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        bar_block = BasicBlock([
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CLOSURE", arg=cellvar_x2),
            Instr("BUILD_TUPLE", arg=1),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=8),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),

            # foo = x1
            Instr("LOAD_CLASSDEREF", arg=freevar_x1),
            Instr("STORE_NAME", arg="foo"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ])

        foo_block = BasicBlock([
            # y = x2
            Instr("LOAD_CLASSDEREF", arg=freevar_x2),
            Instr("STORE_NAME", arg="y"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(function_block)
        expected_instructions.extend(foo_block)
        expected_instructions.extend(bar_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_nested_class_2")
        self.assertEqual(func(), [1, 2])
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_lambda(self):
        def func():
            x = lambda a: a + 10

            result = x(1)
            return result

        function_block = BasicBlock([
            # x = lambda a: a + 10
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="IntegrationTestLanguageFeatures.test_lambda.<locals>.func.<locals>.<lambda>"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_FAST", arg="x"),

            # result = x(1)
            Instr("LOAD_FAST", arg="x"),
            Instr("LOAD_CONST", arg=1),
            Instr("CALL_FUNCTION", arg=1),
            Instr("STORE_FAST", arg="result"),
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        lambda_block = BasicBlock([
            # lambda a: a + 10
            Instr("LOAD_FAST", arg="a"),
            Instr("LOAD_CONST", arg=10),
            Instr("BINARY_ADD"),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(function_block)
        expected_instructions.extend(lambda_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_lambda")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_builtin_addresses(self):
        def func():
            test_dict = {1: "one", 2: "two"}
            # noinspection PyListCreation
            test_list = [1, 2]

            test_list.append(3)

            result = test_dict.get(1)
            return result

        function_block = BasicBlock([
            # test_dict = {1: "one", 2: "two"}
            Instr("LOAD_CONST", arg="one"),
            Instr("LOAD_CONST", arg="two"),
            Instr("LOAD_CONST", arg=(1, 2)),
            Instr("BUILD_CONST_KEY_MAP", arg=2),
            Instr("STORE_FAST", arg="test_dict"),

            # result = test_dict.get(1)
            Instr("LOAD_FAST", arg="test_dict"),
            Instr("LOAD_METHOD", arg="get"),
            Instr("LOAD_CONST", arg=1),
            Instr("CALL_METHOD", arg=1),
            Instr("STORE_FAST", arg="result"),
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(function_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_builtin_addresses")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_data_dependency_immutable_attribute(self):
        # Explicit attribute dependency of immutable type
        module_block = BasicBlock([
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),

            # result = ob.attr2
            Instr("LOAD_NAME", arg="ob"),
            Instr("LOAD_ATTR", arg="attr2"),
            Instr("STORE_NAME", arg="result"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])
        class_attr_block = BasicBlock([
            # attr2 = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_NAME", arg="attr2"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        expected_instructions.extend(class_attr_block)

        module_file = "immutable_attribute_dependency.py"
        module_path = example_modules_path + module_file
        dynamic_slice = slice_module_at_return(module_path)
        self.assertEqual(len(expected_instructions), len(dynamic_slice.sliced_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_object_modification_call(self):
        def func():
            class NestedClass:
                def __init__(self):
                    self.x = 1

                def inc_x(self):
                    self.x = self.x + 1

            ob = NestedClass()
            ob.inc_x()

            result = ob.x
            return result

        function_block = BasicBlock([
            # class NestedClass:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="NestedClass"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="NestedClass"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_FAST", arg="NestedClass"),

            # ob = NestedClass()
            Instr("LOAD_FAST", arg="NestedClass"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("STORE_FAST", arg="ob"),

            # ob.inc_x()
            Instr("LOAD_FAST", arg="ob"),
            Instr("LOAD_METHOD", arg="inc_x"),
            Instr("CALL_METHOD", arg=0),

            # result = ob.x
            Instr("LOAD_FAST", arg="ob"),
            Instr("LOAD_ATTR", arg="x"),
            Instr("STORE_FAST", arg="result"),

            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])

        nested_class_block = BasicBlock([
            # Definition of dunder methods are wrongly excluded, since these are not explicitly loaded
            # def __init__(self):
            # Instr("LOAD_CONST", arg=dummy_code_object),
            # Instr("LOAD_CONST", arg="IntegrationTestLanguageFeatures.test_object_modification_call.<locals>."
            #                         "func.<locals>.NestedClass.__init__"),
            # Instr("MAKE_FUNCTION", arg=0),
            # Instr("STORE_NAME", arg="__init__"),

            # def inc_x(self):
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="IntegrationTestLanguageFeatures.test_object_modification_call.<locals>."
                                    "func.<locals>.NestedClass.inc_x"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="inc_x"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ])

        init_block = BasicBlock([
            # self.x = 1
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_FAST", arg="self"),
            Instr("STORE_ATTR", arg="x"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ])

        inc_x_block = BasicBlock([
            # self.x = self.x + 1
            Instr("LOAD_FAST", arg="self"),
            Instr("LOAD_ATTR", arg="x"),
            Instr("LOAD_CONST", arg=1),
            Instr("BINARY_ADD"),
            Instr("LOAD_FAST", arg="self"),
            Instr("STORE_ATTR", arg="x"),

            # This "None return" is not included, because the return value is not used
            # Instr("LOAD_CONST", arg=None),
            # Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(function_block)
        expected_instructions.extend(nested_class_block)
        expected_instructions.extend(init_block)
        expected_instructions.extend(inc_x_block)
        dynamic_slice = slice_function_at_return(func.__code__, test_name="test_object_modification_call")
        self.assertEqual(len(dynamic_slice.sliced_instructions), len(expected_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))

    def test_closures(self):
        # Closure function

        freevar_foo = FreeVar("foo")
        cellvar_foo = CellVar("foo")
        module_block = BasicBlock([
            # def outer_function(foo):
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="outer_function"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="outer_function"),

            # inner = outer_function('a')
            Instr("LOAD_NAME", arg="outer_function"),
            Instr("LOAD_CONST", arg="a"),
            Instr("CALL_FUNCTION", arg=1),
            Instr("STORE_NAME", arg="inner"),

            # result = inner("abc")
            Instr("LOAD_NAME", arg="inner"),
            Instr("LOAD_CONST", arg="abc"),
            Instr("CALL_FUNCTION", arg=1),
            Instr("STORE_NAME", arg="result"),

            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE")
        ])
        outer_function_block = BasicBlock([
            # def inner_function(bar):
            Instr("LOAD_CLOSURE", arg=cellvar_foo),
            Instr("BUILD_TUPLE", arg=1),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="outer_function.<locals>.inner_function"),
            Instr("MAKE_FUNCTION", arg=8),
            Instr("STORE_FAST", arg="inner_function"),

            # return inner
            Instr("LOAD_FAST", arg="inner_function"),
            Instr("RETURN_VALUE"),
        ])
        inner_function_block = BasicBlock([
            # return foo in bar
            Instr("LOAD_DEREF", arg=freevar_foo),
            Instr("LOAD_FAST", arg="bar"),
            Instr("COMPARE_OP", arg=Compare.IN),
            Instr("RETURN_VALUE"),
        ])

        expected_instructions = []
        expected_instructions.extend(module_block)
        expected_instructions.extend(outer_function_block)
        expected_instructions.extend(inner_function_block)

        module_file = "closure.py"
        module_path = example_modules_path + module_file
        dynamic_slice = slice_module_at_return(module_path)
        self.assertEqual(len(expected_instructions), len(dynamic_slice.sliced_instructions))
        self.assertTrue(compare(dynamic_slice.sliced_instructions, expected_instructions))
