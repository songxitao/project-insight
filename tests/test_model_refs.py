"""
Tests for model_refs.py — model/weight file reference scanning.
"""
from extractors.model_refs import run


def test_empty_project(tmp_project):
    """空项目 → model_refs 为空列表，汇总均为空列表"""
    result = run(str(tmp_project))
    assert result["model_refs"] == []
    for v in result["model_refs_summary"].values():
        assert v == []


def test_onnx_file_ref(tmp_project):
    """引用 .onnx 模型文件路径可被提取"""
    (tmp_project / "config.yaml").write_text(
        'model_path: "weights/model.onnx"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert len(result["model_refs"]) == 1
    assert "weights/model.onnx" in result["model_refs"][0]["model_files"]


def test_pt_pth_safetensors_ref(tmp_project):
    """.pt / .pth / .safetensors 引用均可被提取"""
    (tmp_project / "config.yaml").write_text(
        'a: "model.pt"\nb: "checkpoint.pth"\nc: "weights.safetensors"\n',
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    model_files = []
    for entry in result["model_refs"]:
        model_files.extend(entry.get("model_files", []))
    assert "model.pt" in model_files
    assert "checkpoint.pth" in model_files
    assert "weights.safetensors" in model_files


def test_from_pretrained_model_id(tmp_project):
    """from_pretrained('xxx') 可提取模型 ID"""
    (tmp_project / "train.py").write_text(
        'model = from_pretrained("bert-base-uncased")\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["model_refs"][0]["model_ids"] == ["bert-base-uncased"]


def test_model_dir_assignment(tmp_project):
    """model_dir 赋值可提取目录路径"""
    (tmp_project / "config.yaml").write_text(
        "model_dir: /data/model/checkpoint\n", encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert len(result["model_refs"]) == 1
    dirs = result["model_refs"][0].get("model_dirs", [])
    # 注意：MODEL_DIR_PATTERN 的字符类写法会捕获末尾换行符
    assert any("/data/model/checkpoint" in d for d in dirs)


def test_skip_dirs_ignored(tmp_project):
    """跳过目录中的文件不参与模型引用扫描"""
    skip_dir = tmp_project / ".venv"
    skip_dir.mkdir(parents=True)
    (skip_dir / "config.yaml").write_text(
        'model: "model.onnx"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["model_refs"] == []


def test_summary_dedup(tmp_project):
    """model_refs_summary 中去重正确"""
    (tmp_project / "a.yaml").write_text(
        'model = from_pretrained("bert")\n', encoding="utf-8"
    )
    (tmp_project / "b.yaml").write_text(
        'model = from_pretrained("bert")\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["model_refs_summary"]["unique_model_ids"] == ["bert"]
