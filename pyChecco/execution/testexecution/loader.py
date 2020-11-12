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


from types import ModuleType
from typing import Dict

from unittest.loader import TestLoader

from pyChecco.execution.executiontracer import ExecutionTracer
from pyChecco.execution.executiontrace import ExecutionTrace


class CustomTestLoader(TestLoader):
    def __init__(self, module_traces: Dict[str, ExecutionTrace]):
        super().__init__()
        self._module_traces = module_traces

    def _get_module_from_name(self, name) -> ModuleType:
        """
        In order to trace tests on the module level we need to know when modules are loaded.
        The private method of unittest.loader.TestLoader is overridden, but this is the minimal
        way here.

        :param name: Name of the module
        :return: The loaded module
        """
        ExecutionTracer.start_setup()
        ExecutionTracer.reset()
        ExecutionTracer.set_current_module(name)

        # Actual call to overridden method
        # noinspection PyUnresolvedReferences, PyProtectedMember
        module = super()._get_module_from_name(name)

        self._module_traces.update({name: ExecutionTracer.get_trace()})
        ExecutionTracer.end_setup()

        return module
