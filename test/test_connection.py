import os
from time import sleep

from paramiko.ssh_exception import AuthenticationException
import pytest

import main


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return os.path.join(str(pytestconfig.rootdir), ".resource", "docker-compose.yml")


@pytest.fixture(scope="session")
def ssh_service(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("openssh-server", 2222)
    sleep(10)
    return f"{docker_ip}:{port}"


@pytest.fixture(scope="session")
def ssh_python_service(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    port = docker_services.port_for("openssh-server-python", 2222)
    sleep(10)
    return f"{docker_ip}:{port}"


def test_connect(ssh_service):
    try:
        main.UserUnit("test", ssh_service, "user")
    except AuthenticationException:
        assert False, "Can't connect to user"


def test_false_connect(ssh_service):
    try:
        main.UserUnit("test", ssh_service, "nonuser")
    except AuthenticationException:
        return
    assert False, "Can connect to nonuser! Something wrong"


def test_empty_git(ssh_python_service):
    try:
        unit = main.UserUnit("test", ssh_python_service, "user")
        assert unit.ssh_shell == "python"
        unit.get_vcs_status()
    except AuthenticationException as e:
        assert False, "Can't connect to user"

