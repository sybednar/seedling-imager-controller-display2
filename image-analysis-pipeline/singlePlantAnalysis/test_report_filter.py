import json
import os

from analysis.utils.report_utils import experiment_display_name, filter_experiments


def _make_experiment(analysis, folder, meta_name=None, with_data=True):
    exp = analysis / folder
    plant = exp / "cam_1" / "plant_1" / "Results_1"
    plant.mkdir(parents=True)
    if with_data:
        (plant / "PostProcess_Hour.csv").write_text("Hour\n0\n")
    if meta_name is not None:
        (plant / "metadata.json").write_text(json.dumps({"Experiment": meta_name}))
    return str(exp)


def test_filter_experiments(tmp_path):
    a = _make_experiment(tmp_path, "WT", meta_name="WT")
    b = _make_experiment(tmp_path, "col_dot_0")  # no metadata -> decoded folder name
    c = _make_experiment(tmp_path, "mut_folder", meta_name="mutant")
    exps = [a, b, c]

    assert experiment_display_name(b) == "col.0"
    assert experiment_display_name(c) == "mutant"

    assert filter_experiments(exps, {}) == exps                              # key missing -> all
    assert filter_experiments(exps, {"selectedExperiments": None}) == exps   # null -> all
    assert filter_experiments(exps, {"selectedExperiments": ["WT", "mutant"]}) == [a, c]
    assert filter_experiments(exps, {"selectedExperiments": ["mut_folder"]}) == [c]  # folder name also matches
    assert filter_experiments(exps, {"selectedExperiments": ["nope"]}) == []
    assert filter_experiments(exps, {"selectedExperiments": []}) == []


def test_experiments_without_data_are_skipped(tmp_path, capsys):
    good = _make_experiment(tmp_path, "good")
    empty = _make_experiment(tmp_path, "empty", with_data=False)
    (tmp_path / "bare" / "cam_1" / "plant_1").mkdir(parents=True)  # no Results folder
    bare = str(tmp_path / "bare")
    exps = [good, empty, bare]

    assert filter_experiments(exps, {}) == [good]
    assert filter_experiments(exps, {"selectedExperiments": ["empty", "good"]}) == [good]
    assert filter_experiments(exps, {"selectedExperiments": ["empty"]}) == []
    capsys.readouterr()
    filter_experiments(exps, {}, verbose=True)
    out = capsys.readouterr().out
    assert "empty" in out and "bare" in out and "good" not in out
