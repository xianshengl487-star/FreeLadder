# path: freeladder/cli/main.py
"""CLI 命令行入口

用法:
    python main.py init          初始化数据库和配置
    python main.py update        从订阅源爬取更新节点
    python main.py fetch         一键从内置免费源获取节点
    python main.py ip            检测公网 IP
    python main.py test          测试所有节点
    python main.py test --new    只测试新节点
    python main.py list          列出所有节点
    python main.py list --alive  只列出可用节点
    python main.py export        导出 Clash 配置
    python main.py export --all  导出全部节点
    python main.py export --sub  导出 base64 订阅
    python main.py web           启动 Web API
    python main.py gui           启动 GUI 桌面应用
    python main.py stats         显示统计信息
"""

import sys
import click

from freeladder.core.config import load_config, get_config
from freeladder.core.database import Database, get_db
from freeladder.core.logger import setup_logger


@click.group()
@click.option("--config", "-c", default=None, help="配置文件路径")
@click.pass_context
def cli(ctx, config):
    """FreeLadder - 代理节点聚合、测试与导出工具"""
    # 加载配置
    from pathlib import Path
    config_path = Path(config) if config else None
    load_config(config_path)
    cfg = get_config()

    # 初始化日志
    setup_logger(cfg.app.log_level)

    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg


@cli.command()
@click.pass_context
def init(ctx):
    """初始化数据库和配置文件"""
    from freeladder.core.paths import get_project_root
    cfg = ctx.obj["config"]

    # 检查配置文件
    root = get_project_root()
    config_file = root / "config.yaml"
    if config_file.exists():
        click.echo(f"✓ 配置文件已存在: {config_file}")
    else:
        click.echo(f"✓ 已创建配置文件: {config_file}")

    # 初始化数据库
    db = get_db()
    db.get_stats()  # 触发表创建
    click.echo(f"✓ 数据库已初始化: {db._db_path}")
    click.echo("")
    click.echo("初始化完成！请编辑 config.yaml 添加订阅源，然后执行:")
    click.echo("  python main.py update")


@cli.command()
@click.pass_context
def update(ctx):
    """从订阅源爬取并更新节点"""
    from freeladder.scraper import scrape_all

    db = get_db()
    cfg = ctx.obj["config"]

    if not cfg.scraper.sources:
        click.echo("⚠ 未配置订阅源，请编辑 config.yaml 的 scraper.sources")
        return

    click.echo(f"开始更新，共 {len(cfg.scraper.sources)} 个订阅源...")

    def on_progress(current, total, msg):
        click.echo(f"  [{current}/{total}] {msg}")

    nodes = scrape_all(on_progress=on_progress)

    if not nodes:
        click.echo("⚠ 未获取到任何节点")
        return

    count = db.upsert_nodes(nodes)
    click.echo(f"✓ 获取 {len(nodes)} 个节点，新增 {count} 个")


@cli.command()
@click.pass_context
def fetch(ctx):
    """一键从内置免费源获取节点

    使用预置的公开免费代理订阅源，无需手动配置。
    适合快速获取大量可用节点。
    """
    from freeladder.scraper.scraper import scrape_builtin

    db = get_db()

    click.echo("🔍 正在从内置免费源获取节点...")
    click.echo("   共 25 个订阅源，可能需要 1-2 分钟\n")

    def on_progress(current, total, msg):
        click.echo(f"  [{current}/{total}] {msg}")

    nodes = scrape_builtin(on_progress=on_progress)

    if not nodes:
        click.echo("\n⚠ 未获取到任何节点，可能网络不通或所有源均不可用")
        return

    count = db.upsert_nodes(nodes)
    click.echo(f"\n✓ 获取 {len(nodes)} 个节点，新增 {count} 个")
    click.echo("  可使用 'python main.py test' 测试节点连通性")


@cli.command()
@click.pass_context
def ip(ctx):
    """检测公网 IP 地址"""
    from freeladder.core.builtin_sources import detect_public_ip

    click.echo("🔍 正在检测公网 IP...")
    public_ip = detect_public_ip()
    click.echo(f"  公网 IP: {public_ip}")


@cli.command()
@click.option("--new", is_flag=True, help="只测试新节点")
@click.option("--alive", is_flag=True, help="只测试存活节点")
@click.pass_context
def test(ctx, new, alive):
    """测试节点连通性和延迟"""
    from freeladder.tester import TestService

    db = get_db()
    service = TestService(db)

    def on_progress(current, total, msg):
        click.echo(f"\r  [{current}/{total}] {msg}", nl=False)

    click.echo("开始测试节点...")

    if new:
        results = service.test_new(on_progress=on_progress)
    elif alive:
        results = service.test_alive(on_progress=on_progress)
    else:
        results = service.test_all(on_progress=on_progress)

    click.echo("")
    if results:
        alive_count = sum(1 for r in results if r.alive)
        click.echo(f"✓ 测试完成: {alive_count}/{len(results)} 可用")
    else:
        click.echo("没有节点需要测试")


@cli.command()
@click.option("--alive", is_flag=True, help="只显示可用节点")
@click.option("--protocol", "-p", default=None, help="按协议筛选")
@click.option("--limit", "-n", default=50, help="显示数量")
@click.pass_context
def list(ctx, alive, protocol, limit):
    """列出节点"""
    db = get_db()

    if alive:
        nodes = db.get_alive_nodes()
    elif protocol:
        nodes = db.get_nodes_by_protocol(protocol)
    else:
        nodes = db.get_all_nodes()

    nodes = nodes[:limit]

    if not nodes:
        click.echo("没有节点")
        return

    # 表头
    click.echo(f"{'#':>4}  {'协议':<10}  {'服务器':<20}  {'端口':>6}  {'国家':<6}  {'延迟':>8}  {'分数':>6}  {'信号':<10}  {'测试方式':<10}")
    click.echo("-" * 100)

    for i, node in enumerate(nodes, 1):
        latency_str = f"{node.latency}ms" if node.latency else "-"
        signal_str = node.signal or "-"
        test_mode = node.test_mode or "-"
        country = node.country or "-"

        click.echo(
            f"{i:>4}  {node.protocol.value:<10}  {node.server:<20}  {node.port:>6}  "
            f"{country:<6}  {latency_str:>8}  {node.score:>6.1f}  {signal_str:<10}  {test_mode:<10}"
        )

    click.echo(f"\n共 {len(nodes)} 个节点")


@cli.command()
@click.option("--all", "export_all", is_flag=True, help="导出全部节点（包括不可用）")
@click.option("--sub", is_flag=True, help="导出 base64 订阅")
@click.option("--min-score", default=0, help="最低分数")
@click.option("--max", "max_nodes", default=500, help="最大节点数")
@click.pass_context
def export(ctx, export_all, sub, min_score, max_nodes):
    """导出节点配置"""
    from freeladder.exporter import export_clash_yaml, export_subscription
    from freeladder.core.models import ExportOptions

    db = get_db()
    options = ExportOptions(
        alive_only=not export_all,
        min_score=min_score,
        max_nodes=max_nodes,
    )

    if sub:
        path = export_subscription(options=options, db=db)
        if path:
            click.echo(f"✓ 订阅已导出: {path}")
        else:
            click.echo("⚠ 导出失败：没有可用节点")
    else:
        path = export_clash_yaml(options=options, db=db)
        if path:
            click.echo(f"✓ Clash 配置已导出: {path}")
        else:
            click.echo("⚠ 导出失败：没有可用节点")


@cli.command()
@click.pass_context
def stats(ctx):
    """显示统计信息"""
    db = get_db()
    info = db.get_stats()

    click.echo("═══════════════════════════════════")
    click.echo("         FreeLadder 统计信息")
    click.echo("═══════════════════════════════════")
    click.echo(f"  节点总数:   {info['total']}")
    click.echo(f"  可用节点:   {info['alive']}")
    click.echo(f"  不可用节点: {info['dead']}")
    click.echo(f"  平均延迟:   {info['avg_latency']}ms")
    click.echo(f"  平均分数:   {info['avg_score']}")

    if info["by_protocol"]:
        click.echo("\n  协议分布:")
        for proto, count in info["by_protocol"].items():
            click.echo(f"    {proto:<12} {count}")

    if info["by_country"]:
        click.echo("\n  国家分布 (前10):")
        for country, count in info["by_country"].items():
            click.echo(f"    {country:<12} {count}")

    click.echo("")


@cli.command()
@click.pass_context
def web(ctx):
    """启动 Web API 服务"""
    import uvicorn
    from freeladder.web.api import create_app

    cfg = ctx.obj["config"]
    app = create_app()

    click.echo(f"启动 Web API: http://{cfg.web.host}:{cfg.web.port}")
    uvicorn.run(app, host=cfg.web.host, port=cfg.web.port, log_level="info")


@cli.command()
@click.pass_context
def gui(ctx):
    """启动 GUI 桌面应用"""
    from freeladder.gui.app import FreeLadderApp

    app = FreeLadderApp()
    app.mainloop()


@cli.command()
@click.option("--node-id", required=True, type=int, help="节点 ID")
@click.option("--url", default=None, help="初始打开的 URL")
@click.pass_context
def browse(ctx, node_id, url):
    """用指定节点打开隔离浏览器"""
    import asyncio
    from freeladder.browser import BrowserSession

    db = get_db()
    nodes = db.get_all_nodes()
    node = None
    for n in nodes:
        if n.id == node_id:
            node = n
            break

    if not node:
        click.echo(f"✗ 未找到节点 ID={node_id}")
        return

    if not node.clash_proxy:
        click.echo(f"✗ 节点 {node_id} 没有 clash_proxy 数据，无法启动浏览器")
        return

    click.echo(f"正在为节点 {node_id} ({node.protocol.value}://{node.server}:{node.port}) 启动浏览器...")

    async def _run():
        session = BrowserSession(node, url)
        result = await session.start()

        if result["status"] == "error":
            click.echo(f"✗ 启动失败: {result.get('error', '未知错误')}")
            return

        click.echo(f"✓ 浏览器已启动")
        click.echo(f"  Browser ID: {result['browser_id']}")
        click.echo(f"  Proxy: {result['proxy']}")
        if result.get("profile"):
            click.echo(f"  Profile: {result['profile']}")
        if result.get("url"):
            click.echo(f"  URL: {result['url']}")

        try:
            await session.wait_closed()
        except KeyboardInterrupt:
            pass
        finally:
            await session.close()
            click.echo("✓ 浏览器和代理已关闭")

    asyncio.run(_run())


@cli.command()
@click.pass_context
def browser_api(ctx):
    """启动浏览器控制 API"""
    import uvicorn
    from freeladder.browser.control_api import create_browser_api, _get_or_create_token

    cfg = ctx.obj["config"]
    if not cfg.browser.enabled:
        click.echo("✗ 浏览器功能未启用，请在 config.yaml 中设置 browser.enabled: true")
        return

    app = create_browser_api()
    token = _get_or_create_token()
    host = cfg.browser.control_api_host
    port = cfg.browser.control_api_port

    click.echo(f"Browser Control API:")
    click.echo(f"  URL:   http://{host}:{port}")
    click.echo(f"  Token: {token}")
    click.echo(f"  Docs:  http://{host}:{port}/docs")
    click.echo(f"")
    click.echo(f"Example:")
    click.echo(f'  curl -H "Authorization: Bearer {token}" http://{host}:{port}/browser/status')

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


# 注册源情报引擎 CLI 命令
try:
    from freeladder.source_intel.cli import source_intel_group
    cli.add_command(source_intel_group)
except ImportError:
    pass


def main():
    """CLI 入口"""
    cli(obj={})
