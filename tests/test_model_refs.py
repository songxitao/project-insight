"""
Tests for model_refs.py — model/weight file reference scanning.
"""
import json
import pytest
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
    assert any(item['path'] == "weights/model.onnx" for item in result["model_refs"][0]["model_files"])


def test_pt_pth_safetensors_ref(tmp_project):
    """.pt / .pth / .safetensors 引用均可被提取"""
    (tmp_project / "config.yaml").write_text(
        'a: "model.pt"\nb: "checkpoint.pth"\nc: "weights.safetensors"\n',
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    model_paths = [item['path'] for entry in result["model_refs"] for item in entry.get("model_files", [])]
    assert "model.pt" in model_paths
    assert "checkpoint.pth" in model_paths
    assert "weights.safetensors" in model_paths


def test_from_pretrained_model_id(tmp_project):
    """from_pretrained('xxx') 可提取模型 ID"""
    (tmp_project / "train.py").write_text(
        'model = from_pretrained("bert-base-uncased")\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    model_ids = [item['id'] for item in result["model_refs"][0]["model_ids"]]
    assert model_ids == ["bert-base-uncased"]


def test_model_dir_assignment(tmp_project):
    """model_dir 赋值可提取目录路径"""
    (tmp_project / "config.yaml").write_text(
        "model_dir: /data/model/checkpoint\n", encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert len(result["model_refs"]) == 1
    dirs = result["model_refs"][0].get("model_dirs", [])
    dir_paths = [item['path'] for item in dirs]
    assert "/data/model/checkpoint" in dir_paths[0]


def test_skip_dirs_ignored(tmp_project):
    """跳过目录中的文件不参与模型引用扫描"""
    skip_dir = tmp_project / ".venv"
    skip_dir.mkdir(parents=True)
    (skip_dir / "config.yaml").write_text(
        'model: "model.onnx"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["model_refs"] == []


def test_isolated_extension_not_matched(tmp_project):
    """孤立扩展名如 \".bin\" 不应产生 model_files 条目"""
    (tmp_project / "config.json").write_text(
        '{"supported_extensions": [".bin", ".pt", ".pth"]}\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    # 这些是扩展名列举，不是模型引用，不应产生 model_files
    for entry in result["model_refs"]:
        assert len(entry.get("model_files", [])) == 0


def test_uppercase_extension_matched(tmp_project):
    """大写扩展名 \"MODEL.PT\" 应被捕获"""
    (tmp_project / "train.py").write_text(
        'model_path = "MODEL.PT"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    model_paths = []
    for entry in result["model_refs"]:
        model_paths.extend(item['path'] for item in entry.get("model_files", []))
    assert "MODEL.PT" in model_paths


def test_bare_filename_matched(tmp_project):
    """裸文件名 \"model.pt\"（无路径分隔符）应被捕获"""
    (tmp_project / "train.py").write_text(
        'model = "model.pt"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    model_paths = []
    for entry in result["model_refs"]:
        model_paths.extend(item['path'] for item in entry.get("model_files", []))
    assert "model.pt" in model_paths


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


def test_json_routing_extracts_model_path(tmp_project):
    """JSON 中的模型文件路径 value 应被提取"""
    (tmp_project / "config.json").write_text(
        json.dumps({"model": "models/quantized.onnx", "name": "test"}),
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    all_paths = []
    for entry in result["model_refs"]:
        all_paths.extend(item['path'] for item in entry.get("model_files", []))
    assert any("models/quantized.onnx" in p for p in all_paths)


def test_json_routing_ignores_non_model_strings(tmp_project):
    """JSON 中不以模型扩展名结尾的 string value 不产生 model_files"""
    (tmp_project / "config.json").write_text(
        json.dumps({"name": "bert-base", "version": "1.0", "description": "a model"}),
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    for entry in result["model_refs"]:
        assert len(entry.get("model_files", [])) == 0


def test_json_routing_ignores_keys(tmp_project):
    """JSON 的 key（即使以模型扩展名结尾）不产生 model_files"""
    (tmp_project / "config.json").write_text(
        json.dumps({"model.safetensors": "value", "model.pt": "other"}),
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    for entry in result["model_refs"]:
        assert len(entry.get("model_files", [])) == 0


def test_malformed_json_falls_back_to_regex(tmp_project):
    """非法 JSON 回退到正则路径，不崩溃"""
    (tmp_project / "config.json").write_text(
        '{malformed "model.pt" json}', encoding="utf-8"
    )
    # 不应抛出异常
    result = run(str(tmp_project))
    # 回退后正则仍能找到 model.pt
    all_paths = []
    for entry in result["model_refs"]:
        all_paths.extend(item['path'] for item in entry.get("model_files", []))
    assert any("model.pt" in p for p in all_paths)


def test_weight_map_explosion_regression(tmp_project):
    """含 200+ weight_map 条目的模型 index JSON 不产生爆炸"""
    weight_map = {}
    for i in range(200):
        weight_map[f"model.layers.{i}.weight"] = "model.safetensors-00001-of-00001.safetensors"
    content = json.dumps({"weight_map": weight_map}, indent=2)
    (tmp_project / "model.safetensors.index.json").write_text(content, encoding="utf-8")
    result = run(str(tmp_project))
    # 该文件应被显式跳过
    assert result["model_refs"] == []


def test_json_nested_string_value_extracted(tmp_project):
    """嵌套 JSON 结构中的 string value 应被提取"""
    (tmp_project / "config.json").write_text(
        json.dumps({
            "a": {"b": {"c": "nested/model.pt"}},
            "list": ["item1.onnx", "item2.txt"]
        }),
        encoding="utf-8",
    )
    result = run(str(tmp_project))
    all_paths = []
    for entry in result["model_refs"]:
        all_paths.extend(item['path'] for item in entry.get("model_files", []))
    assert "nested/model.pt" in all_paths
    assert "item1.onnx" in all_paths
    # item2.txt 不是模型扩展名，不应在结果中
    assert "item2.txt" not in all_paths
