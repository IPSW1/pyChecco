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

"""Provides custom exception types."""


class ConfigurationException(BaseException):
    """An exception type that's raised if the tool has no proper configuration."""


class InstructionNotFoundException(BaseException):
    """An exception type that is raised if no matching instruction is found for an attempted search."""


class UncertainStackEffectException(BaseException):
    """Raised if the simulation of the stack effect is not possible due to an instruction with special control flow."""


class TestTimeoutException(BaseException):
    """Raised if the execution of a single test took longer than the configured maximum duration."""


class SlicingTimeoutException(BaseException):
    """Raised if slicing of a single test took longer than the configured maximum duration."""
