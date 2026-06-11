# path: freeladder/web/api.py
"""FastAPI Web API 模块

提供:
- GET /           简易 Dashboard
- GET /nodes      节点列表 JSON
- GET /stats      统计信息
- GET /clash      Clash YAML 配置
- GET /sub        Base64 订阅
- POST /update    触发爬取更新
- POST /test      触发测试
"""

import threading
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import get_db
from freeladder.core.models import ExportOptions


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="FreeLadder",
        description="代理节点聚合、测试与导出工具",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def index():
        """简易 Dashboard"""
        db = get_db()
        stats = db.get_stats()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>FreeLadder</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
                h1 {{ color: #333; }}
                .stat {{ display: inline-block; margin: 10px 20px 10px 0; padding: 15px 25px; background: #f5f5f5; border-radius: 8px; }}
                .stat .num {{ font-size: 28px; font-weight: bold; color: #2196F3; }}
                .stat .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
                .btn {{ display: inline-block; margin: 5px 8px 5px 0; padding: 10px 20px; background: #2196F3; color: white; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 14px; }}
                .btn:hover {{ background: #1976D2; }}
                .btn.green {{ background: #4CAF50; }}
                .btn.green:hover {{ background: #388E3C; }}
                .btn.orange {{ background: #FF9800; }}
                .btn.orange:hover {{ background: #F57C00; }}
                #log {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; margin-top: 20px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 13px; white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            <h1>🌐 FreeLadder</h1>
            <div>
                <div class="stat"><div class="num">{stats['total']}</div><div class="label">节点总数</div></div>
                <div class="stat"><div class="num">{stats['alive']}</div><div class="label">可用节点</div></div>
                <div class="stat"><div class="num">{stats['avg_latency']}</div><div class="label">平均延迟 (ms)</div></div>
                <div class="stat"><div class="num">{stats['avg_score']}</div><div class="label">平均分数</div></div>
            </div>
            <div style="margin-top: 20px;">
                <button class="btn green" onclick="doAction('/update')">更新节点</button>
                <button class="btn orange" onclick="doAction('/test')">测试节点</button>
                <a class="btn" href="/clash" target="_blank">导出 Clash</a>
                <a class="btn" href="/sub" target="_blank">导出订阅</a>
            </div>
            <div id="log">就绪</div>
            <script>
                async function doAction(url) {{
                    document.getElementById('log').textContent = '执行中: ' + url + ' ...';
                    try {{
                        const resp = await fetch(url, {{ method: 'POST' }});
                        const data = await resp.json();
                        document.getElementById('log').textContent = JSON.stringify(data, null, 2);
                    }} catch(e) {{
                        document.getElementById('log').textContent = '错误: ' + e.message;
                    }}
                }}
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    @app.get("/nodes")
    def get_nodes(
        alive: Optional[bool] = Query(None, description="只返回可用节点"),
        protocol: Optional[str] = Query(None, description="按协议筛选"),
        country: Optional[str] = Query(None, description="按国家筛选"),
        limit: int = Query(500, description="最大返回数"),
    ):
        """获取节点列表"""
        db = get_db()

        if alive:
            nodes = db.get_alive_nodes()
        elif protocol:
            nodes = db.get_nodes_by_protocol(protocol)
        elif country:
            nodes = db.get_nodes_by_country(country)
        else:
            nodes = db.get_all_nodes()

        nodes = nodes[:limit]
        return {
            "total": len(nodes),
            "nodes": [n.to_dict() for n in nodes],
        }

    @app.get("/stats")
    def get_stats():
        """获取统计信息"""
        db = get_db()
        return db.get_stats()

    @app.get("/clash")
    def get_clash_config(
        alive: bool = Query(True, description="只导出可用节点"),
        min_score: float = Query(0, description="最低分数"),
    ):
        """导出 Clash YAML 配置"""
        from freeladder.exporter.clash_exporter import _build_clash_config

        db = get_db()
        if alive:
            nodes = db.get_alive_nodes()
        else:
            nodes = db.get_all_nodes()

        if min_score > 0:
            nodes = [n for n in nodes if n.score >= min_score]

        nodes.sort(key=lambda n: n.score, reverse=True)
        nodes = nodes[:500]

        if not nodes:
            return JSONResponse({"error": "没有可用节点"}, status_code=404)

        import yaml
        config = _build_clash_config(nodes)
        yaml_str = yaml.dump(config, default_flow_style=False, allow_unicode=True)
        return PlainTextResponse(content=yaml_str, media_type="text/yaml")

    @app.get("/sub")
    def get_subscription(
        alive: bool = Query(True, description="只导出可用节点"),
    ):
        """导出 Base64 订阅"""
        from freeladder.exporter.subscription_exporter import get_subscription_string

        db = get_db()
        if alive:
            nodes = db.get_alive_nodes()
        else:
            nodes = db.get_all_nodes()

        nodes.sort(key=lambda n: n.score, reverse=True)
        nodes = nodes[:500]

        if not nodes:
            return JSONResponse({"error": "没有可用节点"}, status_code=404)

        sub_str = get_subscription_string(nodes)
        return PlainTextResponse(content=sub_str, media_type="text/plain")

    @app.post("/update")
    def trigger_update():
        """触发爬取更新（后台线程）"""
        from freeladder.scraper import scrape_all

        def _do_update():
            try:
                nodes = scrape_all()
                db = get_db()
                count = db.upsert_nodes(nodes)
                logger.info(f"Web API 更新完成: {len(nodes)} 节点, 新增 {count}")
            except Exception as e:
                logger.error(f"Web API 更新失败: {e}")

        thread = threading.Thread(target=_do_update, daemon=True)
        thread.start()
        return {"status": "started", "message": "更新任务已启动（后台执行）"}

    @app.post("/test")
    def trigger_test():
        """触发测试（后台线程）"""
        from freeladder.tester import TestService

        def _do_test():
            try:
                service = TestService()
                results = service.test_all()
                logger.info(f"Web API 测试完成: {len(results)} 个结果")
            except Exception as e:
                logger.error(f"Web API 测试失败: {e}")

        thread = threading.Thread(target=_do_test, daemon=True)
        thread.start()
        return {"status": "started", "message": "测试任务已启动（后台执行）"}

    return app
