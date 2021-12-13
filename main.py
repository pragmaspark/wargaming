import argparse
import json
import logging
import sys
from abc import abstractmethod
from pathlib import Path
from subprocess import PIPE
from subprocess import Popen
from typing import Protocol


__log = logging.getLogger(__name__)
logger_format_string = "%(asctime)-15s %(process)d %(levelname)-8s %(message)s"
logging.basicConfig(level=logging.DEBUG, format=logger_format_string, stream=sys.stdout)


class NotVCS(Exception):
    pass


class ManyVCS(Exception):
    pass


class Json:
    def __init__(self, path):
        self.path = path
        self.content = dict()

    def load_json(self):
        """Load json content from file by path."""
        with open(self.path, "rb") as f:
            self.content = json.loads(f.read())

    def dump_json(self):
        """Dump content to json file by path."""
        # _path = self.path.parent / (self.path.name + ".test.json") if TEST else self.path
        _path = self.path
        with open(_path, "w") as f:
            f.write(json.dumps(self.content, indent=2, sort_keys=True))

    def rotate_json(self):
        """Save old json version."""
        _path = self.path.parent / (self.path.name + ".old")
        from shutil import copyfile

        copyfile(self.path, _path)


class VCS(Protocol):
    @abstractmethod
    def branch(self):
        raise NotImplementedError

    @abstractmethod
    def refs(self):
        raise NotImplementedError

    @abstractmethod
    def type(self):
        raise NotImplementedError


class Git(VCS):
    def __init__(self):
        self.__path = vcs_path()
        self.__branch = ""
        self.__refs = ""
        self.__type = "git"

    def branch(self):
        with open(self.__path / ".git" / "HEAD") as f:
            line = f.readline().strip()
        _branch = ""
        ref_prefix = "ref: "
        if line.startswith(ref_prefix):
            self.__branch = line[len(ref_prefix):]
            _branch = line[len(ref_prefix) + len("refs/heads/"):]
        else:
            self.__branch = line
            _branch = line
        return _branch

    def refs(self):
        if self.__branch.startswith("refs/heads/"):
            with open(self.__path / ".git" / self.__branch) as f:
                self.__refs = f.readline().strip()
        else:
            self.__refs = self.__branch
        return self.__refs

    def type(self):
        return self.__type


class SVN(VCS):
    def __init__(self):
        self.__path = vcs_path()
        self.__branch = ""
        self.__refs = ""
        self.__type = "svn"

    def branch(self):
        command = ["svn", "info", "--show-item", "relative-url"]
        with Popen(command, stdout=PIPE, stderr=PIPE, cwd=self.__path, universal_newlines=True) as proc:
            out, _err = proc.communicate()
            proc.wait()
            out = out.strip()
        return out

    def refs(self):
        command = ["svn", "info", "--show-item", "revision"]
        with Popen(command, stdout=PIPE, stderr=PIPE, cwd=self.__path, universal_newlines=True) as proc:
            out, _err = proc.communicate()
            proc.wait()
            out = out.strip()
        return out

    def type(self):
        return self.__type


def vcs_path() -> Path:
    return Path.home() / "bw"


def extract_port(endpoint: str) -> (str, int):
    """Extract host and port from string"""
    _split = endpoint.split(":")
    host = _split[0]
    port = int(_split[1]) if len(_split) > 1 else 22
    return host, port


class UserUnit:
    def __init__(self, cluster, host, user):
        self.cluster = cluster
        self.hostname = host
        self.username = user
        self.password = user

        import paramiko

        self.ssh_client = paramiko.SSHClient()
        self.ssh_shell = ""

        self._set_ssh()
        self._set_shell()

    def __str__(self):
        return f"{self.username}@{self.hostname}@{self.cluster}"

    def __repr__(self):
        return f"{self.username}@{self.hostname}@{self.cluster}"

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ssh_client.close()

    def _set_ssh(self):
        """Setup ssh client."""
        import paramiko

        host, port = extract_port(self.hostname)
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(host, port=port, username=self.username, password=self.password)

    def _set_shell(self):
        """Init shell for user."""
        p_out = self.ssh_client.exec_command("$PSVersionTable.PSVersion")[1]
        if len(p_out.readlines()) > 1:
            self.ssh_shell = "powershell"

        p_out = self.ssh_client.exec_command("python --version")[1]
        if p_out.readline().startswith("Python 3."):
            self.ssh_shell = "python"

        if self.ssh_shell == "":
            self.ssh_shell = "sh"

    def get_vcs_status(self) -> dict:
        """
        Get VCS status from a remote host.
        If the remote host have a python. A script will be copy to the remote and exec.
        If the remote host have hot the python. The scrip will try use remote shell exec.

        :return: Dictionary with structure: {"type": "git", "branch": "00", "rev": "00"}
        """
        result = dict()

        if self.ssh_shell == "python":
            sftp = self.ssh_client.open_sftp()
            sftp.put(__file__, "/tmp/main.py")
            sftp.close()

            callback = self.ssh_client.exec_command("python3 /tmp/main.py --remote")
            if callback[2].read() == "":
                vcs_info = callback[1].readline()

                result = json.loads(vcs_info)

        elif self.ssh_shell == "sh":
            raise NotImplementedError("sh extract wot work")

        return result


def json2inventory(_json: dict) -> list[UserUnit]:
    """Convert host's units from json loads to UserUnit class"""
    inventory = []
    try:
        for cluster, value in _json["hosts"].items():
            if type(value) == dict:
                inventory.append(UserUnit(cluster, value["host"], value["user"]))
            if type(value) == list:
                for unit in value:
                    inventory.append(UserUnit(cluster, unit["host"], unit["user"]))
    except KeyError as e:
        __log.error(f"Json has invalid structure. Not found key: ({e})")

    __log.debug(inventory)
    return inventory


def detect_vcs() -> VCS:
    path = Path.home() / "bw"
    vcs_present = []

    in_dir = list(map(lambda file: file.name, path.iterdir()))
    if ".git" in in_dir:
        vcs_present.append("git")
    if ".svn" in in_dir:
        vcs_present.append("svn")

    if len(vcs_present) > 1:
        raise ManyVCS("Found more then 1 vcs")
    elif len(vcs_present) < 1:
        raise NotVCS("No one vcs is found")

    _vcs = ""
    if vcs_present[0] == "git":
        _vcs = Git()
    elif vcs_present[0] == "svn":
        _vcs = SVN()
    return _vcs


def get_vcs_info(_vcs: VCS) -> str:
    # transform information to valid json string
    info = f'{{"type": "{_vcs.type()}", "branch": "{_vcs.branch()}", "rev": "{_vcs.refs()}"}}'
    return info


def modification_json(_json: Json, _unit: UserUnit):
    new_json = _json.content
    _vcs = _unit.get_vcs_status()

    if type(new_json["hosts"]) == dict:
        new_json["hosts"][_unit.cluster]["vcs"] = _vcs
        _json.content = new_json
    if type(new_json["hosts"]) == list:
        for idx, val in enumerate(new_json["hosts"][_unit.cluster]):
            if _unit.hostname == val["host"] and _unit.username == val["user"]:
                new_json["hosts"][_unit.cluster][idx]["vcs"] = _vcs
                _json.content = new_json


def run_remote():
    """
    This code run on remote host!

    :return: print(vcs). Print valid json vcs status
    """
    vcs = detect_vcs()
    print(get_vcs_info(vcs))


def run(json_path: str):
    _json = Json(Path(json_path))
    _json.load_json()
    inventory = json2inventory(_json.content)

    for _unit in inventory:
        modification_json(_json, _unit)

    _json.rotate_json()
    _json.dump_json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract vcs info and dump in json file")
    parser.add_argument("--json", dest="json", metavar='JSON_PATH', type=str, help="path to json file")
    parser.add_argument("--remote", dest="remote", action="store_true", help="run on a remote host")
    args = parser.parse_args()

    if args.remote:
        run_remote()
    else:
        if args.json:
            run(args.json)
        else:
            print("Json path empty")
