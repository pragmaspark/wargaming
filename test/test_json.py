import main

from pathlib import Path


def test_json_load():
    _json = main.Json(Path(".resource/test.json"))
    _json.load_json()
    result = {"hosts": {"EU-CLUSTER": {
      "title": "Eu cluster discription",
      "host": "localhost",
      "user": "user"
    }}}
    assert result == _json.content


def test_json_transform(mocker):

    def mock_vcs(self):
        return {"type": "git", "branch": "00", "rev": "00"}

    def _pass(self):
        pass

    mocker.patch('main.UserUnit.get_vcs_status', mock_vcs)
    mocker.patch('main.UserUnit._set_ssh', _pass)
    mocker.patch('main.UserUnit._set_shell', _pass)

    _json = main.Json(Path(".resource/test.json"))
    _json.load_json()
    unit = main.json2inventory(_json.content)[0]
    main.modification_json(_json, unit)

    result = {"hosts": {"EU-CLUSTER": {
      "title": "Eu cluster discription",
      "host": "localhost",
      "user": "user",
      "vcs": {"type": "git", "branch": "00", "rev": "00"}
    }}}

    assert result == _json.content
