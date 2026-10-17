import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from skills import file_utils


def test_duplicate_names_keep_each_download(tmp_path, monkeypatch):
    monkeypatch.setattr(
        file_utils, "extract_file_ids", lambda response: ["file_a", "file_b", "file_c"]
    )
    client = Mock()
    client.beta.files.retrieve_metadata.side_effect = [
        SimpleNamespace(filename=name) for name in ["report.txt", "report.txt", "report_2.txt"]
    ]
    client.beta.files.download.side_effect = [
        io.BytesIO(content) for content in [b"one", b"two", b"three"]
    ]
    results = file_utils.download_all_files(client, object(), str(tmp_path), prefix="run_")
    assert all(result["success"] for result in results)
    paths = [result["output_path"] for result in results]
    assert len(set(paths)) == 3
    assert [Path(path).read_bytes() for path in paths] == [b"one", b"two", b"three"]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "run_report.txt",
        "run_report_2.txt",
        "run_report_2_2.txt",
    ]
