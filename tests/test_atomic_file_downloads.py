import io
from unittest.mock import Mock

import pytest

from skills import file_utils


@pytest.mark.parametrize("existing", [False, True])
def test_failed_read_does_not_create_or_truncate_destination(tmp_path, existing):
    destination = tmp_path / "report.txt"
    if existing:
        destination.write_bytes(b"keep")
    client = Mock()
    response = client.beta.files.download.return_value
    response.read.side_effect = OSError("interrupted download")
    result = file_utils.download_file(client, "file_example", str(destination))
    assert result["success"] is False
    assert destination.read_bytes() == b"keep" if existing else not destination.exists()
    assert list(tmp_path.iterdir()) == ([destination] if existing else [])
    response.close.assert_called_once()


def test_successful_download_replaces_destination(tmp_path):
    destination = tmp_path / "report.txt"
    destination.write_bytes(b"old")
    client = Mock()
    response = io.BytesIO(b"new content")
    client.beta.files.download.return_value = response
    result = file_utils.download_file(client, "file_example", str(destination))
    assert result["success"] is True
    assert result["size"] == 11
    assert result["overwritten"] is True
    assert destination.read_bytes() == b"new content"
    assert response.closed
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_replace_removes_temporary_file(tmp_path, monkeypatch):
    destination = tmp_path / "report.txt"
    destination.write_bytes(b"keep")
    client = Mock()
    client.beta.files.download.return_value = io.BytesIO(b"new")
    monkeypatch.setattr(file_utils.os, "replace", Mock(side_effect=OSError("cannot replace")))
    result = file_utils.download_file(client, "file_example", str(destination))
    assert result["success"] is False
    assert destination.read_bytes() == b"keep"
    assert list(tmp_path.iterdir()) == [destination]


def test_overwrite_false_does_not_download(tmp_path):
    destination = tmp_path / "report.txt"
    destination.write_bytes(b"keep")
    client = Mock()
    result = file_utils.download_file(client, "file_example", str(destination), overwrite=False)
    assert result["success"] is False
    client.beta.files.download.assert_not_called()
    assert destination.read_bytes() == b"keep"
