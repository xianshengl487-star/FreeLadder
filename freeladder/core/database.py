# path: freeladder/core/database.py
"""SQLite 数据库模块"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from .models import Node, TestResult, Protocol
from .paths import get_data_dir
from .config import get_config


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
            cfg = get_config()
            self._db_path = cfg.data_path / "freeladder.db"

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        self._init_tables()
        logger.info(f"数据库已打开: {self._db_path}")

    def _apply_pragmas(self):
        """应用性能优化 PRAGMA"""
        try:
            from freeladder.core.config import get_config
            cfg = get_config()
            enable_wal = cfg.performance.enable_db_wal
        except Exception:
            enable_wal = True

        if enable_wal:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")

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
        self._create_indexes()
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

        # 迁移旧格式 node_key (protocol://server:port -> protocol:sha256hash)
        self._migrate_node_keys()

    def _migrate_node_keys(self):
        """迁移旧格式 node_key

        旧格式: protocol://server:port (会把同一 server:port 的不同高级协议节点误判为同一个)
        新格式: protocol:sha256hash (基于 raw_uri 的 SHA256 哈希，精确区分)

        只处理高级协议 (vmess/vless/trojan/ss/ssr/hysteria/hysteria2/tuic)，
        普通协议 (http/socks5) 的 node_key 不变。
        """
        rows = self._conn.execute(
            "SELECT id, node_key, raw_uri, protocol, server, port FROM nodes"
        ).fetchall()

        if not rows:
            return

        advanced_prefixes = (
            "vmess:", "vless:", "trojan:", "ss:", "ssr:",
            "hysteria:", "hysteria2:", "tuic:",
        )

        migrated = 0
        for row in rows:
            old_key = row["node_key"] or ""
            # 只迁移高级协议节点（新 key 不含 "://"）
            if "://" not in old_key:
                continue
            if not any(old_key.lower().startswith(p) for p in
                       ("vmess://", "vless://", "trojan://", "ss://", "ssr://",
                        "hysteria://", "hysteria2://", "tuic://")):
                continue

            raw_uri = row["raw_uri"] or ""
            proto = row["protocol"] or "unknown"

            # 用与 Node.node_key 相同的算法重算
            if raw_uri and "://" in raw_uri:
                import hashlib
                normalized = raw_uri.split("#", 1)[0].strip()
                h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
                new_key = f"{proto}:{h}"
            else:
                # 没有 raw_uri，保留旧 key
                continue

            if new_key == old_key:
                continue

            # 检查新 key 是否已存在（可能同一条数据有两种 key）
            existing = self._conn.execute(
                "SELECT id FROM nodes WHERE node_key = ?", (new_key,)
            ).fetchone()

            if existing:
                # 新 key 已存在，删除旧 key 的记录（保留数据更完整的）
                self._conn.execute("DELETE FROM nodes WHERE id = ?", (row["id"],))
                logger.debug(f"迁移: 删除重复节点 {old_key} -> {new_key}")
            else:
                # 更新为新 key
                self._conn.execute(
                    "UPDATE nodes SET node_key = ? WHERE id = ?",
                    (new_key, row["id"])
                )
                logger.debug(f"迁移: {old_key} -> {new_key}")

            migrated += 1

        if migrated > 0:
            self._conn.commit()
            logger.info(f"数据库迁移: 重算了 {migrated} 个高级协议节点的 node_key")

    def _create_indexes(self):
        """创建性能索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_nodes_node_key ON nodes(node_key)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_alive ON nodes(alive)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_score ON nodes(score)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_protocol ON nodes(protocol)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_country ON nodes(country)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_last_checked ON nodes(last_checked)",
        ]
        for sql in indexes:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass

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

    def upsert_nodes_bulk(
        self,
        nodes: list[Node],
        batch_size: int = 500,
        on_progress=None,
        cancel_token=None,
    ) -> int:
        """高性能批量插入/更新节点

        一次性查询已有 node_key 集合，批量事务写入。
        每 batch_size 条 commit 一次，支持 cancel_token 和进度回调。

        Returns:
            新增节点数量
        """
        import json as json_mod

        if not nodes:
            return 0

        # 一次性获取所有已有 key
        existing_keys = {
            row[0] for row in self._conn.execute("SELECT node_key FROM nodes").fetchall()
        }

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        added_count = 0
        total = len(nodes)

        for batch_start in range(0, total, batch_size):
            if cancel_token and cancel_token.cancelled:
                break

            batch = nodes[batch_start:batch_start + batch_size]

            self._conn.execute("BEGIN")
            try:
                for node in batch:
                    if cancel_token and cancel_token.cancelled:
                        break

                    if not node.created_at:
                        node.created_at = now
                    node.updated_at = now

                    clash_proxy_json = json_mod.dumps(node.clash_proxy) if node.clash_proxy else None

                    is_new = node.node_key not in existing_keys

                    if is_new:
                        self._conn.execute("""
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
                        existing_keys.add(node.node_key)
                        added_count += 1
                    else:
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
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

            if on_progress:
                done = min(batch_start + batch_size, total)
                on_progress(done, total, f"已入库 {done}/{total}")

        logger.info(f"批量入库: 新增 {added_count} / 总计 {total} 个节点")
        return added_count

    def get_nodes_page(
        self,
        offset: int = 0,
        limit: int = 200,
        protocol: Optional[str] = None,
        country: Optional[str] = None,
        alive_only: bool = False,
        min_score: float = 0,
    ) -> list[Node]:
        """分页获取节点"""
        conditions = []
        params = []

        if protocol:
            conditions.append("protocol = ?")
            params.append(protocol)
        if country:
            conditions.append("LOWER(country) LIKE ?")
            params.append(f"%{country.lower()}%")
        if alive_only:
            conditions.append("alive = 1")
        if min_score > 0:
            conditions.append("score >= ?")
            params.append(min_score)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM nodes {where} ORDER BY score DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_node_count(
        self,
        protocol: Optional[str] = None,
        country: Optional[str] = None,
        alive_only: bool = False,
        min_score: float = 0,
    ) -> int:
        """获取节点总数（带筛选条件）"""
        conditions = []
        params = []

        if protocol:
            conditions.append("protocol = ?")
            params.append(protocol)
        if country:
            conditions.append("LOWER(country) LIKE ?")
            params.append(f"%{country.lower()}%")
        if alive_only:
            conditions.append("alive = 1")
        if min_score > 0:
            conditions.append("score >= ?")
            params.append(min_score)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) FROM nodes {where}"
        return self._conn.execute(sql, params).fetchone()[0]

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
