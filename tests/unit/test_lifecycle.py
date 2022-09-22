# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
from craft_cli import EmitterMode, emit
from craft_providers.bases.buildd import BuilddBaseAlias

from rockcraft import lifecycle


@pytest.fixture
def mock_project():
    with patch("rockcraft.project") as _mock_project:
        _mock_project.name = "test-name"
        _mock_project.build_base = "ubuntu:20.04"
        yield _mock_project


@pytest.fixture()
def mock_provider(mocker, mock_instance, fake_provider):
    _mock_provider = Mock(wraps=fake_provider)
    mocker.patch(
        "rockcraft.lifecycle.providers.get_provider", return_value=_mock_provider
    )
    yield _mock_provider


@pytest.mark.parametrize(
    "emit_mode,verbosity",
    [
        (EmitterMode.VERBOSE, ["--verbosity=verbose"]),
        (EmitterMode.QUIET, ["--verbosity=quiet"]),
        (EmitterMode.DEBUG, ["--verbosity=debug"]),
        (EmitterMode.TRACE, ["--verbosity=trace"]),
        (EmitterMode.BRIEF, ["--verbosity=brief"]),
    ],
)
def test_lifecycle_run_in_provider(
    mock_instance, mock_provider, mock_project, mocker, emit_mode, verbosity
):
    # mock provider calls
    mock_base_configuration = Mock()
    mock_get_base_configuration = mocker.patch(
        "rockcraft.lifecycle.get_base_configuration",
        return_value=mock_base_configuration,
    )
    mock_get_instance_name = mocker.patch(
        "rockcraft.lifecycle.get_instance_name", return_value="test-instance-name"
    )
    mock_capture_logs_from_instance = mocker.patch(
        "rockcraft.lifecycle.capture_logs_from_instance"
    )

    # set emitter mode
    emit.set_mode(emit_mode)

    lifecycle.run_in_provider(
        project=mock_project,
        command_name="test",
        parsed_args=argparse.Namespace(),
    )

    mock_provider.ensure_provider_is_available.assert_called_once()
    mock_get_instance_name.assert_called_once_with(
        project_name="test-name",
        project_path=Path().absolute(),
    )
    mock_get_base_configuration.assert_called_once_with(
        alias=BuilddBaseAlias.FOCAL,
        project_name="test-name",
        project_path=Path().absolute(),
    )
    mock_provider.launched_environment.assert_called_once_with(
        project_name="test-name",
        project_path=ANY,
        base_configuration=mock_base_configuration,
        build_base="ubuntu:20.04",
        instance_name="test-instance-name",
    )
    mock_instance.execute_run.assert_called_once_with(
        ["rockcraft", "test"] + verbosity,
        check=True,
        cwd=Path("/root/project"),
    )
    mock_capture_logs_from_instance.assert_called_once_with(mock_instance)
