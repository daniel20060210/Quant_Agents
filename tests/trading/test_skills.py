# tests/trading/test_skills.py
# 验证 SkillsManager 的读写行为
import pytest
from trading.skills import SkillsManager


@pytest.fixture
def skills_manager(tmp_path):
    """使用临时文件，避免污染真实 skills.md"""
    path = str(tmp_path / "skills.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 初始内容\n- 规则A\n")
    return SkillsManager(skills_path=path)


def test_read_returns_file_content(skills_manager):
    """read() 返回 skills.md 的完整内容。"""
    content = skills_manager.read()
    assert "初始内容" in content
    assert "规则A" in content


def test_write_overwrites_content(skills_manager):
    """write() 覆盖写入后，read() 返回新内容。"""
    new_content = "# 新内容\n- 规则B\n"
    skills_manager.write(new_content)
    assert skills_manager.read() == new_content


def test_write_then_read_roundtrip(skills_manager):
    """多次写入后，read() 始终返回最新内容。"""
    skills_manager.write("第一次")
    skills_manager.write("第二次")
    assert skills_manager.read() == "第二次"
