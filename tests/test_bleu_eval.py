"""Exercise the evaluator with real tokenization and no network downloads."""

import runpy
from pathlib import Path

import pytest

nltk = pytest.importorskip("nltk", minversion="3.9")

EVALUATOR = (
    Path(__file__).resolve().parents[1]
    / "capabilities/summarization/evaluation/custom_evals/bleu_eval.py"
)


@pytest.fixture(params=[False, True], ids=["clean-data-directory", "punkt-tab-installed"])
def evaluator(request, monkeypatch, tmp_path):
    monkeypatch.setattr(nltk.data, "path", [str(tmp_path)])
    nltk.tokenize._get_punkt_tokenizer.cache_clear()

    def install_punkt_tab():
        language_dir = tmp_path / "tokenizers" / "punkt_tab" / "english"
        language_dir.mkdir(parents=True, exist_ok=True)
        nltk.tokenize.punkt.save_punkt_params(
            nltk.tokenize.punkt.PunktParameters(), dir=str(language_dir)
        )

    if request.param:
        install_punkt_tab()

    def download(resource, *, quiet):
        # Install minimal valid data only if the evaluator requests the modern resource.
        if resource == "punkt_tab":
            install_punkt_tab()
        return True

    monkeypatch.setattr(nltk, "download", download)
    try:
        yield runpy.run_path(str(EVALUATOR))
    finally:
        nltk.tokenize._get_punkt_tokenizer.cache_clear()


@pytest.mark.parametrize(
    "output, threshold, expected_pass, expected_score",
    [
        ("the cat is sitting on the mat", 0.3, True, 1.0),
        ("THE CAT IS SITTING ON THE MAT", 1.1, False, 1.0),
        ("rain falls over distant mountains every winter", 0.3, False, 0.0),
    ],
)
def test_bleu_assertion_bootstraps_tokenizer_data(
    evaluator, output, threshold, expected_pass, expected_score
):
    result = evaluator["get_assert"](
        output,
        {"vars": {"ground_truth": "the cat is sitting on the mat"}},
        threshold=threshold,
    )

    assert result["pass"] is expected_pass
    assert result["score"] == pytest.approx(expected_score)
