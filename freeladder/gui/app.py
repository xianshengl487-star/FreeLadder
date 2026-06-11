# path: freeladder/gui/app.py
"""FreeLadder GUI 桌面应用

使用 customtkinter 构建，包含:
- 顶部状态栏
- 操作按钮区（含停止按钮）
- 筛选区
- 节点表格（分页）
- 日志输出区

性能优化:
- 爬取 + 入库均在后台线程，GUI 主线程不阻塞
- 表格分页渲染，限制最大渲染行数
- 进度回调节流，避免消息队列溢出
- CancelToken 支持取消任务
"""

import os
import sys
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import get_db
from freeladder.core.models import Node
from freeladder.core.cancel_token import CancelToken
from .worker import WorkerThread


class FreeLadderApp(ctk.CTk):
    """FreeLadder 主窗口"""

    def __init__(self):
        super().__init__()

        self.title("FreeLadder - 代理节点管理工具")
        self.geometry("1100x750")
        self.minsize(900, 600)

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 初始化
        self._config = get_config()
        self._db = get_db()
        self._worker = WorkerThread()
        self._web_process: Optional[subprocess.Popen] = None
        self._nodes: list[Node] = []

        # 分页状态
        self._page = 0
        self._page_size = self._config.gui.table_page_size
        self._total_count = 0

        # 进度节流
        self._last_progress_time = 0.0

        # 构建 UI
        self._build_ui()

        # 初始加载
        self.after(500, self._refresh_list)

    def _build_ui(self):
        """构建界面"""
        # 主容器
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ── 顶部状态栏 ──
        self._build_status_bar(main_frame)

        # ── 操作按钮区 ──
        self._build_action_bar(main_frame)

        # ── 筛选区 ──
        self._build_filter_bar(main_frame)

        # ── 节点表格 ──
        self._build_node_table(main_frame)

        # ── 日志输出区 ──
        self._build_log_area(main_frame)

    def _build_status_bar(self, parent):
        """顶部状态栏"""
        status_frame = ctk.CTkFrame(parent, height=60)
        status_frame.pack(fill="x", pady=(0, 8))
        status_frame.pack_propagate(False)

        self._lbl_total = ctk.CTkLabel(status_frame, text="节点总数: 0", font=("Arial", 14, "bold"))
        self._lbl_total.pack(side="left", padx=15, pady=10)

        self._lbl_alive = ctk.CTkLabel(status_frame, text="可用: 0", font=("Arial", 14), text_color="#4CAF50")
        self._lbl_alive.pack(side="left", padx=15, pady=10)

        self._lbl_latency = ctk.CTkLabel(status_frame, text="平均延迟: -ms", font=("Arial", 14))
        self._lbl_latency.pack(side="left", padx=15, pady=10)

        self._lbl_page = ctk.CTkLabel(status_frame, text="", font=("Arial", 12), text_color="#999")
        self._lbl_page.pack(side="left", padx=15, pady=10)

        self._lbl_status = ctk.CTkLabel(status_frame, text="就绪", font=("Arial", 12), text_color="#999")
        self._lbl_status.pack(side="right", padx=15, pady=10)

    def _build_action_bar(self, parent):
        """操作按钮区"""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(btn_frame, text="🚀 一键获取", width=110, command=self._do_fetch,
                      fg_color="#4CAF50", hover_color="#388E3C").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="⛔ 停止", width=70, command=self._do_cancel,
                      fg_color="#F44336", hover_color="#D32F2F").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="🔄 更新节点", width=110, command=self._do_update).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="⚡ 测试节点", width=110, command=self._do_test).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="🌐 检测IP", width=80, command=self._do_detect_ip).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="📋 导出 Clash", width=120, command=self._do_export_clash).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="📦 导出订阅", width=120, command=self._do_export_sub).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="📂 打开目录", width=100, command=self._open_export_dir).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="🌐 启动 Web", width=100, command=self._toggle_web).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="🔄 刷新", width=70, command=self._refresh_list).pack(side="left", padx=4)

    def _build_filter_bar(self, parent):
        """筛选区"""
        filter_frame = ctk.CTkFrame(parent, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(filter_frame, text="协议:").pack(side="left", padx=(10, 4))
        self._filter_protocol = ctk.CTkComboBox(
            filter_frame, width=100,
            values=["全部", "http", "socks5", "vmess", "vless", "trojan", "ss", "hysteria2", "tuic"],
            command=self._on_filter_change,
        )
        self._filter_protocol.set("全部")
        self._filter_protocol.pack(side="left", padx=4)

        ctk.CTkLabel(filter_frame, text="国家:").pack(side="left", padx=(10, 4))
        self._filter_country = ctk.CTkEntry(filter_frame, width=80, placeholder_text="全部")
        self._filter_country.pack(side="left", padx=4)

        self._filter_alive = ctk.CTkCheckBox(filter_frame, text="只看可用", command=self._on_filter_change)
        self._filter_alive.pack(side="left", padx=10)

        ctk.CTkLabel(filter_frame, text="最低分:").pack(side="left", padx=(10, 4))
        self._filter_min_score = ctk.CTkSlider(filter_frame, from_=0, to=100, width=120, command=self._on_filter_change)
        self._filter_min_score.set(0)
        self._filter_min_score.pack(side="left", padx=4)

        ctk.CTkButton(filter_frame, text="筛选", width=60, command=self._apply_filter).pack(side="left", padx=10)

        # 分页按钮
        ctk.CTkButton(filter_frame, text="◀ 上一页", width=80, command=self._prev_page).pack(side="right", padx=4)
        self._lbl_page_info = ctk.CTkLabel(filter_frame, text="第 1 页", font=("Arial", 12))
        self._lbl_page_info.pack(side="right", padx=8)
        ctk.CTkButton(filter_frame, text="下一页 ▶", width=80, command=self._next_page).pack(side="right", padx=4)

    def _build_node_table(self, parent):
        """节点表格"""
        table_frame = ctk.CTkFrame(parent)
        table_frame.pack(fill="both", expand=True, pady=(0, 8))

        # 表头
        headers = ["#", "协议", "服务器", "端口", "国家", "延迟", "分数", "信号", "测试方式", "更新时间"]
        self._col_widths = [40, 70, 180, 60, 60, 70, 60, 80, 80, 130]

        header_frame = ctk.CTkFrame(table_frame, fg_color="#333", height=30)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        for i, (header, width) in enumerate(zip(headers, self._col_widths)):
            label = ctk.CTkLabel(header_frame, text=header, width=width, font=("Arial", 12, "bold"), anchor="w")
            label.pack(side="left", padx=2)

        # 表格内容 - 使用滚动框架
        self._table_scroll = ctk.CTkScrollableFrame(table_frame)
        self._table_scroll.pack(fill="both", expand=True)

    def _build_log_area(self, parent):
        """日志输出区"""
        log_frame = ctk.CTkFrame(parent, height=120)
        log_frame.pack(fill="x")
        log_frame.pack_propagate(False)

        ctk.CTkLabel(log_frame, text="日志:", anchor="w", font=("Arial", 11)).pack(fill="x", padx=10, pady=(5, 0))

        self._log_text = ctk.CTkTextbox(log_frame, height=85, font=("Consolas", 11), fg_color="#1e1e1e")
        self._log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _log(self, msg: str):
        """追加日志"""
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")

    def _set_status(self, msg: str):
        """更新状态栏"""
        self._lbl_status.configure(text=msg)

    def _refresh_status(self):
        """刷新状态栏统计"""
        stats = self._db.get_stats()
        self._lbl_total.configure(text=f"节点总数: {stats['total']}")
        self._lbl_alive.configure(text=f"可用: {stats['alive']}")
        self._lbl_latency.configure(text=f"平均延迟: {stats['avg_latency']}ms")
        self._total_count = stats["total"]

    def _refresh_list(self):
        """刷新节点列表（分页加载）"""
        try:
            max_render = self._config.gui.max_render_rows
            offset = self._page * self._page_size
            self._nodes = self._db.get_nodes_page(offset=offset, limit=self._page_size)
            self._total_count = self._db.get_node_count()

            self._render_table(self._nodes)
            self._refresh_status()
            self._update_page_info()

            if self._total_count > max_render:
                self._log(f"已加载第 {self._page + 1} 页（{len(self._nodes)} 条），共 {self._total_count} 个节点。请使用筛选或分页查看更多。")
            else:
                self._log(f"已加载 {len(self._nodes)} 个节点")
        except Exception as e:
            self._log(f"刷新失败: {e}")

    def _update_page_info(self):
        """更新分页信息"""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        self._lbl_page_info.configure(text=f"第 {self._page + 1}/{total_pages} 页")
        self._lbl_page.configure(text=f"显示 {self._page * self._page_size + 1}-{min((self._page + 1) * self._page_size, self._total_count)} / {self._total_count}")

    def _prev_page(self):
        """上一页"""
        if self._page > 0:
            self._page -= 1
            self._refresh_list()

    def _next_page(self):
        """下一页"""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1:
            self._page += 1
            self._refresh_list()

    def _render_table(self, nodes: list[Node]):
        """渲染节点表格"""
        # 清空旧内容
        for widget in self._table_scroll.winfo_children():
            widget.destroy()

        max_render = self._config.gui.max_render_rows
        render_nodes = nodes[:max_render]

        for i, node in enumerate(render_nodes, 1):
            row_frame = ctk.CTkFrame(self._table_scroll, fg_color="transparent", height=28)
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            global_idx = self._page * self._page_size + i
            values = [
                str(global_idx),
                node.protocol.value,
                node.server,
                str(node.port),
                node.country or "-",
                f"{node.latency}ms" if node.latency else "-",
                f"{node.score:.1f}",
                node.signal or "-",
                node.test_mode or "-",
                node.last_checked[:16] if node.last_checked else "-",
            ]

            for val, width in zip(values, self._col_widths):
                color = "#4CAF50" if node.alive else "#F44336" if node.latency else "#999"
                fg = color if val in (node.protocol.value, node.signal) else None
                label = ctk.CTkLabel(
                    row_frame, text=val, width=width, anchor="w",
                    font=("Arial", 11),
                    text_color=fg or ("white" if i % 2 == 0 else "#ccc"),
                )
                label.pack(side="left", padx=2)

    def _on_filter_change(self, *args):
        """筛选条件变化"""
        pass  # 延迟加载

    def _apply_filter(self):
        """应用筛选（分页）"""
        max_render = self._config.gui.max_render_rows

        protocol = self._filter_protocol.get()
        if protocol == "全部":
            protocol = None

        country = self._filter_country.get().strip() or None
        alive_only = self._filter_alive.get()
        min_score = self._filter_min_score.get()

        self._total_count = self._db.get_node_count(
            protocol=protocol, country=country,
            alive_only=alive_only, min_score=min_score,
        )
        self._nodes = self._db.get_nodes_page(
            offset=0, limit=self._page_size,
            protocol=protocol, country=country,
            alive_only=alive_only, min_score=min_score,
        )
        self._page = 0
        self._render_table(self._nodes)
        self._update_page_info()

        if self._total_count > max_render:
            self._log(f"筛选结果: {self._total_count} 个节点（显示前 {len(self._nodes)} 个）")
        else:
            self._log(f"筛选结果: {len(self._nodes)} 个节点")

    def _throttled_log(self, msg: str):
        """节流日志：间隔不低于 progress_update_interval_ms"""
        now = time.time()
        interval = self._config.gui.progress_update_interval_ms / 1000.0
        if now - self._last_progress_time < interval:
            return
        self._last_progress_time = now
        self.after(0, lambda m=msg: self._log(m))

    # ── 后台任务 ──

    def _fetch_builtin_and_save(self, on_progress=None, cancel_token=None):
        """后台线程: 爬取 + 入库（不经过 GUI 主线程）"""
        from freeladder.scraper.scraper import scrape_builtin

        nodes = scrape_builtin(on_progress=on_progress, cancel_token=cancel_token)
        if cancel_token and cancel_token.cancelled:
            return {"total": 0, "added": 0, "cancelled": True}

        added = self._db.upsert_nodes_bulk(
            nodes, batch_size=500,
            on_progress=on_progress,
            cancel_token=cancel_token,
        )
        return {"total": len(nodes), "added": added, "cancelled": False}

    def _do_fetch(self):
        """一键从内置免费源获取节点（爬取+入库均在后台）"""
        if self._worker.is_running:
            self._log("⚠ 已有任务在运行")
            return

        # 检查内置源是否启用
        if not self._config.scraper.builtin_enabled:
            self._log("⚠ 内置源已禁用，请在 config.yaml 中设置 builtin_enabled: true")
            return

        self._set_status("获取中...")
        self._log("🚀 从内置免费源获取节点（后台爬取 + 入库）...")
        self._last_progress_time = 0

        def _on_progress(current, total, msg):
            self._throttled_log(f"  [{current}/{total}] {msg}")

        def _on_done(result):
            def _update():
                if result and not result.get("cancelled"):
                    self._log(f"✓ 获取完成: 共 {result['total']} 个节点，新增 {result['added']} 个")
                elif result and result.get("cancelled"):
                    self._log("⚠ 获取已取消")
                else:
                    self._log("⚠ 获取失败")
                self._page = 0
                self._refresh_list()
                self._set_status("就绪")
            self.after(0, _update)

        self._worker.start(self._fetch_builtin_and_save, on_progress=_on_progress, on_done=_on_done)

    def _do_cancel(self):
        """停止当前任务"""
        if not self._worker.is_running:
            self._log("⚠ 没有正在运行的任务")
            return
        self._worker.stop()
        self._log("⛔ 已请求停止当前任务")
        self._set_status("正在停止...")

    def _do_update(self):
        """爬取更新"""
        if self._worker.is_running:
            self._log("⚠ 已有任务在运行")
            return

        self._set_status("更新中...")
        self._log("开始更新节点...")
        self._last_progress_time = 0

        def _on_progress(current, total, msg):
            self._throttled_log(f"  [{current}/{total}] {msg}")

        def _on_done(result):
            nodes = result if result else []
            def _update():
                if nodes:
                    self._db.upsert_nodes(nodes)
                self._page = 0
                self._refresh_list()
                self._set_status("更新完成")
            self.after(0, _update)

        from freeladder.scraper import scrape_all
        self._worker.start(scrape_all, on_progress=_on_progress, on_done=_on_done)

    def _do_detect_ip(self):
        """检测公网 IP"""
        if self._worker.is_running:
            self._log("⚠ 已有任务在运行")
            return

        self._log("🔍 正在检测公网 IP...")

        def _on_done(result):
            def _update():
                ip_str = result if result else "检测失败"
                self._log(f"  公网 IP: {ip_str}")
            self.after(0, _update)

        from freeladder.core.builtin_sources import detect_public_ip
        self._worker.start(detect_public_ip, on_done=_on_done)

    def _do_test(self):
        """测试节点"""
        if self._worker.is_running:
            self._log("⚠ 已有任务在运行")
            return

        self._set_status("测试中...")
        self._log("开始测试节点...")
        self._last_progress_time = 0

        def _on_progress(current, total, msg):
            self._throttled_log(f"  [{current}/{total}] {msg}")

        def _on_done(result):
            def _update():
                self._refresh_list()
                self._set_status("测试完成")
            self.after(0, _update)

        from freeladder.tester import TestService
        service = TestService(self._db)
        self._worker.start(service.test_all, on_progress=_on_progress, on_done=_on_done)

    def _do_export_clash(self):
        """导出 Clash 配置"""
        try:
            from freeladder.exporter import export_clash_yaml
            path = export_clash_yaml(db=self._db)
            if path:
                self._log(f"✓ Clash 配置已导出: {path}")
            else:
                self._log("⚠ 导出失败：没有可用节点")
        except Exception as e:
            self._log(f"✗ 导出失败: {e}")

    def _do_export_sub(self):
        """导出订阅"""
        try:
            from freeladder.exporter import export_subscription
            path = export_subscription(db=self._db)
            if path:
                self._log(f"✓ 订阅已导出: {path}")
            else:
                self._log("⚠ 导出失败：没有可用节点")
        except Exception as e:
            self._log(f"✗ 导出失败: {e}")

    def _open_export_dir(self):
        """打开导出目录"""
        export_dir = self._config.export_path
        if sys.platform == "win32":
            os.startfile(str(export_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(export_dir)])
        else:
            subprocess.run(["xdg-open", str(export_dir)])

    def _toggle_web(self):
        """启动/停止 Web API"""
        if self._web_process and self._web_process.poll() is None:
            # 停止
            self._web_process.terminate()
            self._web_process = None
            self._log("Web API 已停止")
        else:
            # 启动
            try:
                import uvicorn
                from freeladder.web.api import create_app
                app = create_app()

                import threading
                def _run():
                    uvicorn.run(app, host=self._config.web.host, port=self._config.web.port, log_level="warning")

                thread = threading.Thread(target=_run, daemon=True)
                thread.start()
                url = f"http://{self._config.web.host}:{self._config.web.port}"
                self._log(f"✓ Web API 已启动: {url}")
                webbrowser.open(url)
            except Exception as e:
                self._log(f"✗ Web API 启动失败: {e}")

    def on_closing(self):
        """关闭窗口时清理"""
        if self._worker.is_running:
            self._worker.stop()
        if self._web_process:
            self._web_process.terminate()
        self._db.close()
        self.destroy()
