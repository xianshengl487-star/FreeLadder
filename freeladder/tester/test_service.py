# path: freeladder/tester/test_service.py
"""统一测试服务入口

根据协议类型自动选择测试方式:
- HTTP/SOCKS5: 基础测试
- VMess/VLESS/Trojan/Hysteria/TUIC/SS: Mihomo 真实测试
- Mihomo 不可用时可降级为 TCP fallback
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import Database, get_db
from freeladder.core.models import Node, TestResult, ADVANCED_PROTOCOLS
from freeladder.core.scoring import calculate_score, get_signal
from .basic_tester import basic_test_node
from .mihomo_tester import mihomo_test_nodes


class TestService:
    """统一测试服务"""

    def __init__(self, db: Optional[Database] = None):
        self._config = get_config()
        self._db = db or get_db()

    def test_all(
        self,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[TestResult]:
        """测试全部节点"""
        nodes = self._db.get_all_nodes()
        if not nodes:
            logger.warning("数据库中没有节点，请先执行 update")
            return []
        return self._test_nodes(nodes, on_progress)

    def test_new(
        self,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[TestResult]:
        """只测试新节点（未测试过的）"""
        nodes = self._db.get_testable_nodes()
        # 只取未测试过的
        nodes = [n for n in nodes if n.last_checked is None]
        if not nodes:
            logger.info("没有新节点需要测试")
            return []
        logger.info(f"发现 {len(nodes)} 个新节点需要测试")
        return self._test_nodes(nodes, on_progress)

    def test_alive(
        self,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[TestResult]:
        """只测试已存活的节点"""
        nodes = self._db.get_alive_nodes()
        if not nodes:
            logger.info("没有存活节点需要测试")
            return []
        logger.info(f"准备重新测试 {len(nodes)} 个存活节点")
        return self._test_nodes(nodes, on_progress)

    def _test_nodes(
        self,
        nodes: list[Node],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[TestResult]:
        """对节点列表执行测试"""
        if not nodes:
            return []

        total = len(nodes)
        logger.info(f"开始测试 {total} 个节点")

        # 分离高级协议和基础协议节点
        advanced_nodes = [n for n in nodes if n.protocol in ADVANCED_PROTOCOLS]
        basic_nodes = [n for n in nodes if n.protocol not in ADVANCED_PROTOCOLS]

        all_results: list[TestResult] = []
        tested_count = 0

        # 测试基础协议节点 (HTTP/SOCKS5)
        if basic_nodes:
            logger.info(f"基础协议测试: {len(basic_nodes)} 个节点")
            basic_results = self._test_basic_nodes(basic_nodes, on_progress, tested_count, total)
            all_results.extend(basic_results)
            tested_count += len(basic_nodes)

        # 测试高级协议节点 (VMess/VLESS/Trojan 等)
        if advanced_nodes:
            logger.info(f"高级协议测试: {len(advanced_nodes)} 个节点")

            if self._config.tester.prefer_mihomo:
                # 优先使用 Mihomo
                mihomo_results = mihomo_test_nodes(advanced_nodes, on_progress)
                all_results.extend(mihomo_results)
                tested_count += len(advanced_nodes)

                # 检查哪些失败了，如果有 tcp_fallback 配置则降级
                if self._config.tester.tcp_fallback:
                    failed_nodes = []
                    mihomo_result_map = {r.node_key: r for r in mihomo_results}
                    for node in advanced_nodes:
                        r = mihomo_result_map.get(node.node_key)
                        if r and not r.alive and r.error == "Mihomo 不可用":
                            failed_nodes.append(node)

                    if failed_nodes:
                        logger.info(f"降级 TCP fallback: {len(failed_nodes)} 个节点")
                        fallback_results = self._test_basic_nodes(
                            failed_nodes, on_progress, tested_count, total
                        )
                        all_results.extend(fallback_results)
            else:
                # 全部使用基础测试
                basic_results = self._test_basic_nodes(advanced_nodes, on_progress, tested_count, total)
                all_results.extend(basic_results)

        # 写入数据库
        self._save_results(all_results)

        alive_count = sum(1 for r in all_results if r.alive)
        logger.info(f"测试完成: {alive_count}/{len(all_results)} 可用")

        return all_results

    def _test_basic_nodes(
        self,
        nodes: list[Node],
        on_progress: Optional[Callable],
        offset: int,
        total: int,
    ) -> list[TestResult]:
        """并发测试基础协议节点"""
        results: list[TestResult] = []
        max_workers = self._config.tester.max_workers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_node = {}
            for node in nodes:
                future = executor.submit(basic_test_node, node)
                future_to_node[future] = node

            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(TestResult(
                        node_id=node.id,
                        node_key=node.node_key,
                        alive=False,
                        error=f"测试异常: {e}",
                        test_mode="basic",
                    ))

                if on_progress:
                    current = offset + len(results)
                    status = "✓" if results[-1].alive else "✗"
                    on_progress(current, total, f"{node.node_key} {status}")

        return results

    def _save_results(self, results: list[TestResult]):
        """将测试结果写入数据库"""
        for result in results:
            try:
                self._db.update_test_result(result)
            except Exception as e:
                logger.error(f"保存测试结果失败 {result.node_key}: {e}")
        logger.info(f"已保存 {len(results)} 条测试结果到数据库")
