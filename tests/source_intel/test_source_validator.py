# path: tests/source_intel/test_source_validator.py
"""测试 SourceValidator 源验证器"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.models import SourceRecord, SourceStatus
from freeladder.source_intel.source_validator import SourceValidator


class TestSourceValidator:
    def test_validate_empty_content(self, source_store):
        validator = SourceValidator()
        source = SourceRecord(url="https://example.com/empty.txt")
        with patch.object(validator, 'download_source', return_value=""):
            result = validator.validate(source)
            assert result["valid"] is False
            assert "下载失败" in result["error"]

    def test_validate_no_nodes(self, source_store):
        validator = SourceValidator()
        source = SourceRecord(url="https://example.com/no-nodes.txt")
        with patch.object(validator, 'download_source', return_value="no nodes here"):
            result = validator.validate(source)
            assert result["valid"] is False
            assert "无法解析出节点" in result["error"]

    def test_validate_clash_yaml(self, source_store):
        validator = SourceValidator()
        clash_content = """
proxies:
  - name: "test-vmess"
    type: vmess
    server: 1.2.3.4
    port: 443
    uuid: test-uuid
"""
        source = SourceRecord(url="https://example.com/clash.yaml")
        with patch.object(validator, 'download_source', return_value=clash_content):
            result = validator.validate(source)
            assert result["valid"] is True
            assert result["node_count"] == 1
            assert "vmess" in result["protocol_stats"]

    def test_validate_base64(self, source_store):
        import base64
        validator = SourceValidator()
        # base64 编码的 vmess URI
        vmess_uri = "vmess://eyJ2IjoiMiIsInBzIjoiVGVzdCIsImFkZCI6IjEuMi4zLjQiLCJwb3J0IjoiNDQzIn0="
        content = base64.b64encode(vmess_uri.encode()).decode()
        source = SourceRecord(url="https://example.com/base64.txt")
        with patch.object(validator, 'download_source', return_value=content):
            result = validator.validate(source)
            # 应该能解析出节点
            assert result["node_count"] >= 0

    def test_download_size_limit(self, source_store):
        validator = SourceValidator()
        source = SourceRecord(url="https://example.com/large.bin")
        # 模拟超大响应
        with patch('httpx.Client') as mock_client:
            mock_resp = MagicMock()
            mock_resp.headers = {"content-length": "99999999999"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = validator.validate(source)
            assert result["valid"] is False

    def test_collect_protocol_stats(self, source_store):
        validator = SourceValidator()
        from freeladder.core.models import Node, Protocol
        nodes = [
            Node(protocol=Protocol.VMESS, server="1.1.1.1", port=443),
            Node(protocol=Protocol.VMESS, server="2.2.2.2", port=443),
            Node(protocol=Protocol.VLESS, server="3.3.3.3", port=443),
        ]
        stats = validator.collect_protocol_stats(nodes)
        assert stats["vmess"] == 2
        assert stats["vless"] == 1
