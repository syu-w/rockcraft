# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import typing
from dataclasses import dataclass
from pathlib import Path

import pytest
from craft_parts.errors import OsReleaseVersionIdError
from craft_parts.utils.os_utils import OsRelease

from rockcraft import plugins
from rockcraft.parts import PartsLifecycle
from rockcraft.plugins.python_plugin import SITECUSTOMIZE_TEMPLATE
from rockcraft.project import Project
from tests.util import ubuntu_only

pytestmark = ubuntu_only

# Extract the possible "base" values from the Literal annotation.
ALL_BASES = typing.get_args(typing.get_type_hints(Project)["base"])

BARE_BASES = {"bare"}
UBUNTU_BASES = set(ALL_BASES) - BARE_BASES


@pytest.fixture(autouse=True)
def setup_python_test(monkeypatch):
    # Keep craft-parts from trying to refresh apt's cache, so that we can run
    # this test as regular users.
    monkeypatch.setenv("CRAFT_PARTS_PACKAGE_REFRESH", "0")
    plugins.register()


def run_lifecycle(base: str, work_dir: Path) -> None:
    source = Path(__file__).parent / "python_source"

    parts = {
        "my-part": {
            "plugin": "python",
            "source": str(source),
            "stage-packages": ["python3-venv"],
        }
    }

    lifecycle = PartsLifecycle(
        all_parts=parts,
        work_dir=work_dir,
        part_names=None,
        base_layer_dir=Path("unused"),
        base_layer_hash=b"deadbeef",
        base=base,
    )

    lifecycle.run("stage")


@dataclass
class ExpectedValues:
    """Expected venv Python values for a given Ubuntu host."""

    symlinks: typing.List[str]
    symlink_target: str
    version_dir: str


# A mapping from host Ubuntu to expected Python values; We need this mapping
# because these integration tests run on the host machine as the "build base".
RELEASE_TO_VALUES = {
    "22.04": ExpectedValues(
        symlinks=["python", "python3", "python3.10"],
        symlink_target="../usr/bin/python3.10",
        version_dir="python3.10",
    ),
    "20.04": ExpectedValues(
        symlinks=["python", "python3"],
        symlink_target="../usr/bin/python3.8",
        version_dir="python3.8",
    ),
}

try:
    # The instance of `ExpectedValues` for the current host running the tests
    VALUES_FOR_HOST = RELEASE_TO_VALUES[OsRelease().version_id()]
except OsReleaseVersionIdError:
    # not running on Ubuntu; pass because the tests will be skipped.
    pass


@pytest.mark.parametrize("base", tuple(UBUNTU_BASES))
def test_python_plugin_ubuntu(base, tmp_path):

    work_dir = tmp_path / "work"

    run_lifecycle(base, work_dir)

    bin_dir = work_dir / "stage/bin"

    # Ubuntu base: the Python symlinks in bin/ must *not* exist, because of the
    # usrmerge handling
    assert list(bin_dir.glob("python*")) == []

    # Check the shebang in the "hello" script
    expected_shebang = "#!/bin/python3"
    hello = bin_dir / "hello"
    assert hello.read_text().startswith(expected_shebang)

    # Check the extra sitecustomize.py module that we add
    expected_text = SITECUSTOMIZE_TEMPLATE.replace("EOF", "")

    version_dir = VALUES_FOR_HOST.version_dir
    sitecustom = work_dir / f"stage/usr/lib/{version_dir}/sitecustomize.py"
    assert sitecustom.read_text().strip() == expected_text.strip()

    # Check that the pyvenv.cfg file was removed, as it's not necessary with the
    # sitecustomize.py module.
    pyvenv_cfg = work_dir / "stage/pyvenv.cfg"
    assert not pyvenv_cfg.is_file()


def test_python_plugin_bare(tmp_path):
    work_dir = tmp_path / "work"

    run_lifecycle("bare", work_dir)

    bin_dir = work_dir / "stage/bin"

    # Bare base: the Python symlinks in bin/ *must* exist, and "python3" must
    # point to the "concrete" part-provided python binary
    assert sorted(bin_dir.glob("python*")) == [
        bin_dir / i for i in VALUES_FOR_HOST.symlinks
    ]
    # (Python 3.8 does not have Path.readlink())
    assert os.readlink(bin_dir / "python3") == VALUES_FOR_HOST.symlink_target

    # Check the shebang in the "hello" script
    expected_shebang = "#!/bin/python3"
    hello = bin_dir / "hello"
    assert hello.read_text().startswith(expected_shebang)

    # Check the extra sitecustomize.py module that we add
    expected_text = SITECUSTOMIZE_TEMPLATE.replace("EOF", "")

    version_dir = VALUES_FOR_HOST.version_dir
    sitecustom = work_dir / f"stage/usr/lib/{version_dir}/sitecustomize.py"
    assert sitecustom.read_text().strip() == expected_text.strip()

    # Check that the pyvenv.cfg file was removed, as it's not necessary with the
    # sitecustomize.py module.
    pyvenv_cfg = work_dir / "stage/pyvenv.cfg"
    assert not pyvenv_cfg.is_file()
