from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from anthropic.types.beta import (
    BetaBashCodeExecutionToolResultBlock,
    BetaCodeExecutionToolResultBlock,
)

from skills import file_utils


def result_block(python: bool, file_ids: list[str]):
    stem = "code_execution" if python else "bash_code_execution"
    model = BetaCodeExecutionToolResultBlock if python else BetaBashCodeExecutionToolResultBlock
    return model.model_validate(
        {
            "type": f"{stem}_tool_result",
            "tool_use_id": "tool_example",
            "content": {
                "type": f"{stem}_result",
                "return_code": 0,
                "stdout": "",
                "stderr": "",
                "content": [{"type": f"{stem}_output", "file_id": fid} for fid in file_ids],
            },
        }
    )


@pytest.mark.parametrize("python", [True, False])
def test_file_ids_from_sdk_execution_results(python):
    response = SimpleNamespace(content=[result_block(python, ["file_a", "file_b"])])
    assert file_utils.extract_file_ids(response) == ["file_a", "file_b"]


def test_mixed_results_preserve_order_and_remove_duplicates():
    response = SimpleNamespace(
        content=[
            result_block(True, ["file_a", "file_b"]),
            result_block(False, ["file_b", "file_c"]),
        ]
    )
    assert file_utils.extract_file_ids(response) == ["file_a", "file_b", "file_c"]


def test_download_helper_receives_python_file_ids(tmp_path, monkeypatch):
    response = SimpleNamespace(content=[result_block(True, ["file_a"])])
    client = Mock()
    client.beta.files.retrieve_metadata.return_value = SimpleNamespace(filename="report.txt")
    download = Mock(return_value={"success": True})
    monkeypatch.setattr(file_utils, "download_file", download)
    assert file_utils.download_all_files(client, response, str(tmp_path)) == [{"success": True}]
    download.assert_called_once_with(client, "file_a", str(tmp_path / "report.txt"), overwrite=True)
