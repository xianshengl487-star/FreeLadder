# 源情报引擎技术文档

## 架构概览

```
freeladder/source_intel/
├── __init__.py           # 包初始化
├── models.py             # 数据模型
├── engine.py             # 引擎总控
├── source_store.py       # 本地 JSON 存储
├── link_extractor.py     # 链接提取器
├── source_health.py      # 健康度评分
├── source_validator.py   # 源验证器
├── github_watcher.py     # GitHub 仓库监控
├── repo_scanner.py       # 仓库内容扫描
├── non_github_discovery.py  # 非 GitHub 源发现
├── rss_watcher.py        # RSS/Atom 监控
├── scheduler.py          # 后台调度器
├── cli.py                # CLI 命令
└── README.md             # 用户文档
```

## 数据流

```
Seed Repositories / Seed Sites / User Sources
        ↓
GitHubWatcher / NonGitHubDiscovery / RSSWatcher
        ↓
RepoScanner / HTMLScanner / RSSScanner
        ↓
LinkExtractor
        ↓
SourceValidator
        ↓
SourceHealth
        ↓
SourceStore
        ↓
scrape_builtin / one-click fetch
        ↓
nodes → parse → dedupe → test → score → group → export
```

## 配置系统

新增 `SourceIntelConfig` 配置模型:

```yaml
source_intel:
  enabled: true
  github_watch_enabled: true
  github_token: ""
  non_github_discovery_enabled: true
  rss_watch_enabled: true
  validate_before_enable: true
  require_user_confirm_for_new_sources: true
  auto_refresh_nodes: false
```

## 存储文件

- `data/source_intel.json` - 源记录
- `data/source_health.json` - 健康数据
- `data/repo_watch.json` - GitHub 仓库监控
- `data/non_github_sources.json` - 非 GitHub 源

## 安全边界

### 允许
- 读取用户配置的公开订阅源
- 读取用户启用的开源仓库 README/文件
- 使用 GitHub API/raw/jsDelivr 获取公开文件
- 使用 ETag/Last-Modified 做缓存
- 限流、失败缓存、健康度排序

### 禁止
- 扫描公网 IP
- 爆破订阅路径
- 猜测订阅 URL
- 绕过登录/付费墙/Cloudflare
- 抓取私有 Telegram 群
- 自动启用所有第三方源
- 无限递归爬取
- 使用浏览器自动化绕过限制

## 接口

### SourceIntelEngine

所有入口统一走 Engine:

```python
engine = SourceIntelEngine()

# 发现源
sources = engine.discover_github_sources()
sources = engine.discover_non_github_sources()

# 验证源
count = engine.validate_candidates()

# 管理源
engine.enable_source(source_id, user_confirmed=True)
engine.disable_source(source_id)

# 获取启用源 URL
urls = engine.get_enabled_source_urls()
```

### scrape_builtin 集成

`scrape_builtin()` 自动合并:
1. 硬编码内置源
2. source_intel 启用源

```python
from freeladder.scraper.scraper import scrape_builtin
nodes = scrape_builtin()
```

## 测试

```bash
# 运行源情报引擎测试
python -m pytest tests/source_intel/ -v

# 运行所有测试
python -m pytest tests/ -v
```

## GUI 集成

GUI 源情报中心功能:
- 显示本地源列表
- 显示 GitHub 仓库监控状态
- 显示候选源/已启用源/失败源
- 显示健康评分/最后检查时间/节点数量
- 支持验证/启用/禁用/刷新/清理 DEAD 源

## 性能考虑

- GitHub API 限流处理
- ETag 缓存减少请求
- 每轮限制仓库/站点数量
- 单源失败不影响全局
- 原子文件写入
