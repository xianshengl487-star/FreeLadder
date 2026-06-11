# path: freeladder/source_intel/cli.py
"""源情报引擎 CLI 命令

用法:
    freeladder source-intel list               列出所有源
    freeladder source-intel list --enabled     列出已启用源
    freeladder source-intel list --candidates  列出候选源
    freeladder source-intel scan-github        扫描 GitHub 仓库
    freeladder source-intel scan-web           扫描非 GitHub 网页
    freeladder source-intel scan-rss           扫描 RSS/Atom
    freeladder source-intel validate           验证所有候选源
    freeladder source-intel validate --source-id <id>  验证指定源
    freeladder source-intel enable <id>        启用源
    freeladder source-intel disable <id>       禁用源
    freeladder source-intel health             查看健康评分
    freeladder source-intel refresh            刷新所有源
    freeladder source-intel export-health      导出健康报告
"""

import json

import click

from freeladder.core.config import get_config


@click.group("source-intel")
def source_intel_group():
    """源情报引擎 - 管理第三方公开源"""
    pass


@source_intel_group.command("list")
@click.option("--enabled", is_flag=True, help="只显示已启用源")
@click.option("--candidates", is_flag=True, help="只显示候选源")
@click.option("--json-output", "json_out", is_flag=True, help="JSON 输出")
@click.pass_context
def list_sources(ctx, enabled, candidates, json_out):
    """列出所有源"""
    from freeladder.source_intel.engine import SourceIntelEngine

    engine = SourceIntelEngine()

    if enabled:
        sources = engine.store.list_enabled()
    elif candidates:
        sources = engine.store.list_candidates()
    else:
        sources = engine.store.load_sources()

    if json_out:
        click.echo(json.dumps([s.model_dump() for s in sources], ensure_ascii=False, indent=2))
        return

    if not sources:
        click.echo("没有源")
        return

    click.echo(f"{'状态':<10} {'名称':<30} {'类型':<12} {'节点数':>6} {'健康度':>6} {'失败':>4} {'来源'}")
    click.echo("-" * 100)

    for s in sources:
        status_str = s.status.value
        name_str = s.name[:28]
        kind_str = s.kind.value
        nodes_str = str(s.last_node_count)
        health_str = f"{s.quality_score:.1f}"
        fail_str = str(s.fail_count)
        source_str = s.discovered_from[:20] if s.discovered_from else "-"

        click.echo(
            f"{status_str:<10} {name_str:<30} {kind_str:<12} "
            f"{nodes_str:>6} {health_str:>6} {fail_str:>4} {source_str}"
        )

    click.echo(f"\n共 {len(sources)} 个源")


@source_intel_group.command("scan-github")
@click.pass_context
def scan_github(ctx):
    """扫描 GitHub 仓库"""
    from freeladder.source_intel.engine import SourceIntelEngine

    click.echo("🔍 正在扫描 GitHub 仓库...")
    engine = SourceIntelEngine()

    def on_progress(current, total, msg):
        click.echo(f"  [{current}/{total}] {msg}")

    sources = engine.discover_github_sources(on_progress=on_progress)
    click.echo(f"\n✓ 发现 {len(sources)} 个候选源")


@source_intel_group.command("scan-web")
@click.pass_context
def scan_web(ctx):
    """扫描非 GitHub 网页"""
    from freeladder.source_intel.engine import SourceIntelEngine

    click.echo("⚠ 非 GitHub 源发现需要用户配置站点列表")
    click.echo("  请在 config.yaml 的 source_intel.non_github_sites 中添加站点")
    engine = SourceIntelEngine()
    sources = engine.discover_non_github_sources()
    click.echo(f"✓ 发现 {len(sources)} 个候选源")


@source_intel_group.command("scan-rss")
@click.pass_context
def scan_rss(ctx):
    """扫描 RSS/Atom"""
    from freeladder.source_intel.engine import SourceIntelEngine

    click.echo("⚠ RSS 源发现需要用户配置 feed 列表")
    engine = SourceIntelEngine()
    sources = engine._discover_rss_sources()
    click.echo(f"✓ 发现 {len(sources)} 个候选源")


@source_intel_group.command("validate")
@click.option("--source-id", default=None, help="指定源 ID")
@click.pass_context
def validate(ctx, source_id):
    """验证候选源"""
    from freeladder.source_intel.engine import SourceIntelEngine

    engine = SourceIntelEngine()

    if source_id:
        source = engine.store.get(source_id)
        if not source:
            click.echo(f"✗ 未找到源: {source_id}")
            return

        result = engine._validator.validate(source)
        if result["valid"]:
            click.echo(f"✓ 验证通过: {source.name}")
            click.echo(f"  节点数: {result['node_count']}")
            click.echo(f"  协议分布: {result['protocol_stats']}")
        else:
            click.echo(f"✗ 验证失败: {result['error']}")
    else:
        click.echo("正在验证所有候选源...")
        count = engine.validate_candidates()
        click.echo(f"✓ 验证完成: {count} 个源通过")


@source_intel_group.command("enable")
@click.argument("source_id")
@click.option("--yes", is_flag=True, help="跳过确认")
@click.pass_context
def enable_source(ctx, source_id, yes):
    """启用源"""
    from freeladder.source_intel.engine import SourceIntelEngine

    engine = SourceIntelEngine()
    source = engine.store.get(source_id)

    if not source:
        click.echo(f"✗ 未找到源: {source_id}")
        return

    click.echo(f"即将启用源: {source.name}")
    click.echo(f"  URL: {source.url}")
    click.echo(f"  类型: {source.kind.value}")
    click.echo(f"  节点数: {source.last_node_count}")
    click.echo(f"  协议分布: {source.protocol_stats}")
    click.echo(f"  健康度: {source.quality_score:.1f}")
    click.echo("")
    click.echo("⚠ 风险提示: 第三方公开源稳定性和安全性不可保证")

    if not yes:
        confirm = click.confirm("确认启用？")
        if not confirm:
            click.echo("已取消")
            return

    if engine.enable_source(source_id, user_confirmed=True):
        click.echo(f"✓ 已启用: {source.name}")
    else:
        click.echo(f"✗ 启用失败")


@source_intel_group.command("disable")
@click.argument("source_id")
@click.pass_context
def disable_source(ctx, source_id):
    """禁用源"""
    from freeladder.source_intel.engine import SourceIntelEngine

    engine = SourceIntelEngine()
    if engine.disable_source(source_id):
        click.echo(f"✓ 已禁用: {source_id}")
    else:
        click.echo(f"✗ 禁用失败: {source_id}")


@source_intel_group.command("health")
@click.option("--json-output", "json_out", is_flag=True, help="JSON 输出")
@click.pass_context
def health(ctx, json_out):
    """查看源健康评分"""
    from freeladder.source_intel.engine import SourceIntelEngine
    from freeladder.source_intel.source_health import SourceHealth

    engine = SourceIntelEngine()
    health_calc = SourceHealth()
    sources = engine.store.load_sources()
    ranked = health_calc.rank_sources(sources)

    if json_out:
        click.echo(json.dumps([s.model_dump() for s in ranked], ensure_ascii=False, indent=2))
        return

    if not ranked:
        click.echo("没有源")
        return

    click.echo(f"{'健康度':>6} {'状态':<10} {'名称':<30} {'成功':>4} {'失败':>4} {'最后成功'}")
    click.echo("-" * 90)

    for s in ranked:
        score_str = f"{s.quality_score:.1f}"
        status_str = s.status.value
        name_str = s.name[:28]
        success_str = str(s.success_count)
        fail_str = str(s.fail_count)
        last_success = s.last_success[:16] if s.last_success else "-"

        click.echo(
            f"{score_str:>6} {status_str:<10} {name_str:<30} "
            f"{success_str:>4} {fail_str:>4} {last_success}"
        )


@source_intel_group.command("refresh")
@click.pass_context
def refresh(ctx):
    """刷新所有源"""
    from freeladder.source_intel.engine import SourceIntelEngine

    click.echo("🔄 正在刷新源情报...")
    engine = SourceIntelEngine()

    def on_progress(current, total, msg):
        click.echo(f"  [{current}/{total}] {msg}")

    results = engine.refresh_sources(on_progress=on_progress)
    click.echo(f"\n✓ 刷新完成:")
    click.echo(f"  GitHub: {results['github']} 个候选")
    click.echo(f"  非 GitHub: {results['non_github']} 个候选")
    click.echo(f"  RSS: {results['rss']} 个候选")
    click.echo(f"  验证通过: {results['validated']} 个")


@source_intel_group.command("export-health")
@click.option("--output", "-o", default="source_health_report.json", help="输出文件")
@click.pass_context
def export_health(ctx, output):
    """导出源健康报告"""
    from freeladder.source_intel.engine import SourceIntelEngine
    from freeladder.source_intel.source_health import SourceHealth

    engine = SourceIntelEngine()
    health_calc = SourceHealth()
    sources = engine.store.load_sources()
    ranked = health_calc.rank_sources(sources)

    report = {
        "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "total_sources": len(ranked),
        "sources": [s.model_dump() for s in ranked],
    }

    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    click.echo(f"✓ 健康报告已导出: {output}")
