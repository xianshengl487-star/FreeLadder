# path: tests/test_gui_no_full_render.py
"""测试 GUI 不全量渲染

验证:
- GUI 刷新路径使用 get_nodes_page 而非 get_all_nodes
- _refresh_list 使用分页
- _apply_filter 使用分页
- _render_table 限制 max_render_rows
"""

import ast
import pytest
from pathlib import Path


class TestGuiNoFullRender:
    def test_refresh_list_uses_get_nodes_page(self):
        """_refresh_list 必须使用 get_nodes_page 分页加载"""
        app_path = Path(__file__).parent.parent / "freeladder" / "gui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Find _refresh_list method
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_refresh_list":
                method_source = ast.get_source_segment(content, node)
                assert method_source is not None
                assert "get_nodes_page" in method_source, "_refresh_list must use get_nodes_page"
                assert "get_all_nodes" not in method_source, "_refresh_list must NOT use get_all_nodes"
                return
        pytest.fail("_refresh_list method not found in app.py")

    def test_apply_filter_uses_get_nodes_page(self):
        """_apply_filter 必须使用 get_nodes_page 分页加载"""
        app_path = Path(__file__).parent.parent / "freeladder" / "gui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_apply_filter":
                method_source = ast.get_source_segment(content, node)
                assert method_source is not None
                assert "get_nodes_page" in method_source, "_apply_filter must use get_nodes_page"
                assert "get_all_nodes" not in method_source, "_apply_filter must NOT use get_all_nodes"
                return
        pytest.fail("_apply_filter method not found in app.py")

    def test_render_table_limits_max_rows(self):
        """_render_table 必须限制最大渲染行数"""
        app_path = Path(__file__).parent.parent / "freeladder" / "gui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_render_table":
                method_source = ast.get_source_segment(content, node)
                assert method_source is not None
                assert "max_render" in method_source, "_render_table must check max_render_rows"
                return
        pytest.fail("_render_table method not found in app.py")

    def test_no_get_all_nodes_in_refresh_path(self):
        """整个 app.py 的刷新路径中不能出现 get_all_nodes"""
        app_path = Path(__file__).parent.parent / "freeladder" / "gui" / "app.py"
        content = app_path.read_text(encoding="utf-8")

        # get_all_nodes should not be called anywhere in the refresh path
        # It's ok if the method exists, but it shouldn't be called in _refresh_list, _apply_filter
        tree = ast.parse(content)
        refresh_methods = {"_refresh_list", "_apply_filter"}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in refresh_methods:
                method_source = ast.get_source_segment(content, node)
                assert method_source is not None
                assert "get_all_nodes" not in method_source, \
                    f"{node.name} must NOT call get_all_nodes"
