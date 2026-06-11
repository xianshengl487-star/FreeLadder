# path: freeladder/core/database.py
"""SQLite 数据库模块"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from .models import Node, TestResult, Protocol
from .paths import get_data_dir


class Database:
    """SQLite 数据库管理"""

    # nodes 表完整字段定义
    COLUMNS = [
        "id", "node_key", "raw_hash", "protocol", "server", "port", "name",
        "raw_uri", "clash_proxy", "country", "alive", "latency", "avg_latency",
        "score", "signal", "test_mode", "fail_count", "success_count",
        "last_error", "source", "created_at", "updated_at", "last_checked",
    ]

    # 需要自动迁移添加的字段及类型
    MIGRATION_COLUMNS = {
        "node_key": "TEXT",
        "raw_hash": "TEXT",
        "protocol": "TEXT",
        "server": "TEXT",
        "port": "INTEGER",
        "name": "TEXT",
        "raw_uri": "TEXT",
        "clash_proxy": "TEXT",
        "country": "TEXT",
        "alive": "INTEGER DEFAULT 0",
        "latency": "INTEGER",
        "avg_latency": "REAL",
        "score": "REAL DEFAULT 0",
        "signal": "TEXT",
        "test_mode": "TEXT",
        "fail_count": "INTEGER DEFAULT 0",
        "success_count": "INTEGER DEFAULT 0",
        "last_error": "TEXT",
        "source": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "last_checked": "TEXT",
    }

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = Path(db_path)
        else:
            self._db_path = get_data_dir() / "freeladder.db"

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()
        logger.info(f"数据库已打开: {self._db_path}")

    def _init_tables(self):
        """初始化表结构"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_key TEXT UNIQUE,
                raw_hash TEXT,
                protocol TEXT,
                server TEXT,
                port INTEGER,
                name TEXT,
                raw_uri TEXT,
                clash_proxy TEXT,
                country TEXT,
                alive INTEGER DEFAULT 0,
                latency INTEGER,
                avg_latency REAL,
                score REAL DEFAULT 0,
                signal TEXT,
                test_mode TEXT,
                fail_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_error TEXT,
                source TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_checked TEXT
            )
        """)
        self._migrate()
        self._conn.commit()

    def _migrate(self):
        """自动迁移：检查并添加缺失字段"""
        cursor = self._conn.execute("PRAGMA table_info(nodes)")
        existing = {row["name"] for row in cursor.fetchall()}

        for col_name, col_type in self.MIGRATION_COLUMNS.items():
            if col_name not in existing:
                try:
                    self._conn.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")
                    logger.info(f"数据库迁移: 添加字段 {col_name} ({col_type})")
                except sqlite3.OperationalError:
                    pass  # 字段已存在，忽略

    def _node_from_row(self, row: sqlite3.Row) -> Node:
        """从数据库行转换为 Node 对象"""
        data = dict(row)
        # 解析 clash_proxy JSON
        proxy_str = data.get("clash_proxy")
        if proxy_str:
            import json
            try:
                data["clash_proxy"] = json.loads(proxy_str)
            except (json.JSONDecodeError, TypeError):
                data["clash_proxy"] = None
        else:
            data["clash_proxy"] = None

        # 解析 boolean 字段
        data["alive"] = bool(data.get("alive", 0))

        # 解析 protocol 枚举
        proto_str = data.get("protocol", "unknown")
        try:
            data["protocol"] = Protocol(proto_str)
        except ValueError:
            data["protocol"] = Protocol.UNKNOWN

        return Node(**{k: v for k, v in data.items() if k in Node.model_fields})

    def upsert_node(self, node: Node) -> int:
        """插入或更新节点（按 node_key 去重）"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if not node.created_at:
            node.created_at = now
        node.updated_at = now

        import json
        clash_proxy_json = json.dumps(node.clash_proxy) if node.clash_proxy else None

        # 先尝试获取已有节点
        existing = self._conn.execute(
            "SELECT id, fail_count, success_count FROM nodes WHERE node_key = ?",
            (node.node_key,)
        ).fetchone()

        if existing:
            # 更新已有节点
            self._conn.execute("""
                UPDATE nodes SET
                    raw_hash = ?, protocol = ?, server = ?, port = ?, name = ?,
                    raw_uri = ?, clash_proxy = ?, country = ?, source = ?,
                    updated_at = ?
                WHERE node_key = ?
            """, (
                node.raw_hash, node.protocol.value, node.server, node.port,
                node.name, node.raw_uri, clash_proxy_json, node.country,
                node.source, node.updated_at, node.node_key
            ))
            node.id = existing["id"]
            return existing["id"]
        else:
            # 插入新节点
            cursor = self._conn.execute("""
                INSERT INTO nodes (
                    node_key, raw_hash, protocol, server, port, name,
                    raw_uri, clash_proxy, country, alive, latency, avg_latency,
                    score, signal, test_mode, fail_count, success_count,
                    last_error, source, created_at, updated_at, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.node_key, node.raw_hash, node.protocol.value, node.server,
                node.port, node.name, node.raw_uri, clash_proxy_json,
                node.country, int(node.alive), node.latency, node.avg_latency,
                node.score, node.signal, node.test_mode, node.fail_count,
                node.success_count, node.last_error, node.source,
                node.created_at, node.updated_at, node.last_checked
            ))
            node.id = cursor.lastrowid
            self._conn.commit()
            return cursor.lastrowid

    def upsert_nodes(self, nodes: list[Node]) -> int:
        """批量插入/更新节点，返回新增数量"""
        count = 0
        for node in nodes:
            existing = self.get_node_by_key(node.node_key)
            self.upsert_node(node)
            if existing is None:
                count += 1
        self._conn.commit()
        return count

    def get_node_by_key(self, node_key: str) -> Optional[Node]:
        """按 node_key 查询节点"""
        row = self._conn.execute(
            "SELECT * FROM nodes WHERE node_key = ?", (node_key,)
        ).fetchone()
        return self._node_from_row(row) if row else None

    def get_all_nodes(self) -> list[Node]:
        """获取全部节点"""
        rows = self._conn.execute(
            "SELECT * FROM nodes ORDER BY score DESC, id DESC"
        ).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_alive_nodes(self) -> list[Node]:
        """获取可用节点"""
        rows = self._conn.execute(
            "SELECT * FROM nodes WHERE alive = 1 ORDER BY score DESC"
        ).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_nodes_by_protocol(self, protocol: str) -> list[Node]:
        """按协议筛选"""
        rows = self._conn.execute(
            "SELECT * FROM nodes WHERE protocol = ? ORDER BY score DESC",
            (protocol,)
        ).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_nodes_by_country(self, country: str) -> list[Node]:
        """按国家筛选"""
        rows = self._conn.execute(
            "SELECT * FROM nodes WHERE country = ? ORDER BY score DESC",
            (country,)
        ).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_testable_nodes(self) -> list[Node]:
        """获取需要测试的节点：新节点或超过5分钟未测试的节点"""
        cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 300))
        rows = self._conn.execute("""
            SELECT * FROM nodes
            WHERE last_checked IS NULL OR last_checked < ?
            ORDER BY score ASC, fail_count DESC
        """, (cutoff,)).fetchall()
        return [self._node_from_row(r) for r in rows]

    def update_test_result(self, result: TestResult):
        """更新测试结果"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        row = self._conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (result.node_id,)
        ).fetchone()

        if not row:
            return

        node = self._node_from_row(row)
        node.alive = result.alive
        node.latency = result.latency
        node.test_mode = result.test_mode
        node.last_checked = result.tested_at

        if result.alive:
            node.success_count += 1
            node.fail_count = 0
            node.last_error = ""
        else:
            node.fail_count += 1
            node.last_error = result.error

        # 更新平均延迟
        if result.alive and result.latency is not None:
            if node.avg_latency is None:
                node.avg_latency = float(result.latency)
            else:
                # 指数移动平均
                node.avg_latency = node.avg_latency * 0.7 + result.latency * 0.3

        # 重新计算分数
        from .scoring import calculate_score, get_signal
        node.score = calculate_score(node)
        node.signal = get_signal(node.score)

        self._conn.execute("""
            UPDATE nodes SET
                alive = ?, latency = ?, avg_latency = ?, score = ?, signal = ?,
                test_mode = ?, fail_count = ?, success_count = ?, last_error = ?,
                last_checked = ?, updated_at = ?
            WHERE id = ?
        """, (
            int(node.alive), node.latency, node.avg_latency, node.score,
            node.signal, node.test_mode, node.fail_count, node.success_count,
            node.last_error, node.last_checked, now, node.id
        ))
        self._conn.commit()

    def delete_dead_nodes(self, max_fail_count: int = 10) -> int:
        """删除连续失败次数超过阈值的节点"""
        cursor = self._conn.execute(
            "DELETE FROM nodes WHERE fail_count >= ?", (max_fail_count,)
        )
        self._conn.commit()
        return cursor.rowcount

    def delete_node(self, node_id: int) -> bool:
        """删除单个节点"""
        cursor = self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        alive = self._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE alive = 1"
        ).fetchone()[0]

        # 按协议统计
        rows = self._conn.execute(
            "SELECT protocol, COUNT(*) as cnt FROM nodes GROUP BY protocol ORDER BY cnt DESC"
        ).fetchall()
        by_protocol = {row["protocol"]: row["cnt"] for row in rows}

        # 按国家统计
        rows = self._conn.execute(
            "SELECT country, COUNT(*) as cnt FROM nodes WHERE country != '' GROUP BY country ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        by_country = {row["country"]: row["cnt"] for row in rows}

        # 平均延迟
        avg_row = self._conn.execute(
            "SELECT AVG(latency) as avg_lat FROM nodes WHERE alive = 1 AND latency IS NOT NULL"
        ).fetchone()
        avg_latency = avg_row["avg_lat"] if avg_row and avg_row["avg_lat"] else 0

        # 平均分数
        avg_score_row = self._conn.execute(
            "SELECT AVG(score) as avg_score FROM nodes"
        ).fetchone()
        avg_score = avg_score_row["avg_score"] if avg_score_row and avg_score_row["avg_score"] else 0

        return {
            "total": total,
            "alive": alive,
            "dead": total - alive,
            "by_protocol": by_protocol,
            "by_country": by_country,
            "avg_latency": round(avg_latency, 1),
            "avg_score": round(avg_score, 1),
        }

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("数据库连接已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# 全局数据库实例
_db: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    """获取全局数据库实例"""
    global _db
    if _db is None:
        _db = Database(db_path)
    return _db
