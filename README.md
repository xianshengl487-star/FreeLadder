# FreeLadder

代理节点聚合、测试、评分与导出工具。

## 功能列表

- **订阅聚合**: 从多个订阅源自动爬取、解析、去重节点
- **协议解析**: 支持 HTTP, SOCKS5, VMess, VLESS, Trojan, SS, SSR, Hysteria, Hysteria2, TUIC
- **基础测试**: TCP 连通性、HTTP 代理、SOCKS5 代理检测
- **Mihomo 真实测试**: 通过 Mihomo 核心对高级协议进行真实延迟测试
- **评分系统**: 基于可用性、延迟、稳定性、新鲜度的综合评分 (0-100)
- **Clash 导出**: 生成可直接使用的 Clash/Mihomo YAML 配置
- **订阅导出**: Base64 编码的节点订阅
- **CLI 命令行**: init, update, test, list, export, web, gui, stats
- **Web API**: FastAPI 提供 RESTful 接口和简易 Dashboard
- **GUI 桌面应用**: customtkinter 构建的可视化管理界面
- **SQLite 存储**: 本地持久化节点数据，支持自动迁移
- **Windows 打包**: PyInstaller 一键打包为 EXE

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd FreeLadder

# 安装依赖
pip install -r requirements.txt
```

**Python 版本要求**: 3.11+

## 配置

```bash
# 复制示例配置
cp config.example.yaml config.yaml

# 编辑配置，添加订阅源
```

`config.yaml` 示例:

```yaml
app:
  name: FreeLadder
  log_level: INFO

scraper:
  sources:
    - https://example.com/sub1.txt
    - https://example.com/sub2.yaml
  request_timeout: 15
  max_workers: 20

tester:
  test_url: "https://www.gstatic.com/generate_204"
  timeout: 8
  prefer_mihomo: true
  tcp_fallback: true

mihomo:
  binary_path: ""  # 留空自动查找
```

## 配置 Mihomo

FreeLadder 通过 Mihomo 核心对 VMess、VLESS、Trojan 等高级协议进行真实延迟测试。

1. 从 [Mihomo Releases](https://github.com/MetaCubeX/mihomo/releases) 下载对应平台的二进制文件
2. 将 `mihomo.exe` (Windows) 或 `mihomo` (Linux/Mac) 放到项目的 `bin/` 目录
3. 或者在 `config.yaml` 的 `mihomo.binary_path` 中指定完整路径
4. 如果不配置 Mihomo，高级协议节点将使用 TCP fallback 测试（仅检测连通性）

## CLI 使用

```bash
# 初始化数据库和配置
python main.py init

# 从订阅源更新节点
python main.py update

# 测试所有节点
python main.py test

# 只测试新节点
python main.py test --new

# 列出所有节点
python main.py list

# 只列出可用节点
python main.py list --alive

# 导出 Clash 配置
python main.py export

# 导出全部节点（包括不可用的）
python main.py export --all

# 导出 Base64 订阅
python main.py export --sub

# 启动 Web API
python main.py web

# 启动 GUI
python main.py gui

# 查看统计信息
python main.py stats
```

## GUI 使用

```bash
python main.py gui
# 或
python run_gui.py
```

GUI 功能:
- 顶部状态栏显示节点总数、可用数、平均延迟
- 一键更新、测试、导出
- 按协议、国家、可用性、分数筛选
- 节点表格实时展示
- 日志输出区域

## Web API

```bash
python main.py web
# 或
python run_web.py
```

默认地址: http://127.0.0.1:8765

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Dashboard 页面 |
| `/nodes` | GET | 节点列表 JSON |
| `/nodes?alive=true` | GET | 可用节点 |
| `/stats` | GET | 统计信息 |
| `/clash` | GET | Clash YAML 配置 |
| `/sub` | GET | Base64 订阅 |
| `/update` | POST | 触发爬取更新 |
| `/test` | POST | 触发测试 |

## 导出 Clash 配置

```bash
# CLI 导出
python main.py export

# 或 Web API
curl http://127.0.0.1:8765/clash > clash.yaml
```

导出的配置包含:
- `proxies`: 代理节点列表
- `proxy-groups`: Auto (自动选择) + Proxy (手动选择)
- `rules`: 默认规则

## 打包 EXE

```bash
pip install pyinstaller
python tools/build_exe.py
```

输出: `dist/FreeLadder/FreeLadder.exe`

打包后请手动将 Mihomo 二进制文件放入 `dist/FreeLadder/bin/` 目录。

## 开发与测试

### 安装开发依赖

```bash
pip install -r requirements-dev.txt
```

### 语法检查

```bash
python -m compileall freeladder main.py run_gui.py run_web.py
```

### 单元测试

```bash
pytest -q
```

### Smoke Test

```bash
python tools/smoke_test.py
```

### 基础 CLI 验收

```bash
python main.py init
python main.py stats
python main.py update
python main.py test --new
python main.py export --all
```

> - 没有配置 `scraper.sources` 时，`update` 提示未配置订阅源是正常行为。
> - 没有 Mihomo 时，高级协议会根据配置走 TCP fallback。
> - Mihomo 二进制不要提交到仓库。
> - `config.yaml` 不要提交，应该基于 `config.example.yaml` 自行创建。

## 常见问题

### 找不到 Mihomo

- 确认已将 Mihomo 二进制文件放入 `bin/` 目录
- 或在 `config.yaml` 中配置 `mihomo.binary_path`
- Mihomo 不可用时，HTTP/SOCKS5 节点仍可正常测试
- 高级协议节点将使用 TCP fallback（仅检测连通性）

### 高级协议测试失败

- 确认 Mihomo 已正确配置并可运行
- 检查节点的 `clash_proxy` 字段是否完整
- 部分节点可能需要特定的 TLS 参数

### 没有可用节点

- 检查 `config.yaml` 的 `scraper.sources` 是否配置了订阅源
- 确认订阅源 URL 可访问
- 运行 `python main.py update` 重新爬取

### GUI 卡住

- 长时间无响应可能是网络问题
- 尝试减少 `tester.max_workers` 配置
- 重启应用

### Windows 防火墙提示

- Mihomo 启动时可能触发防火墙提示
- 这是正常现象，选择允许即可
- FreeLadder 仅监听 127.0.0.1，不会暴露到公网

## 合规说明

- 本工具仅用于代理配置管理和连通性测试
- 用户需要自行确保节点来源合法合规
- 不提供、不内置、不保证任何第三方节点服务
- 默认订阅源配置为空，由用户自行配置
- 请遵守当地法律法规

## 项目结构

```
FreeLadder/
├── freeladder/
│   ├── core/          # 核心模块：配置、模型、数据库、评分、去重
│   ├── scraper/       # 爬取模块：解析、源管理、爬虫
│   ├── tester/        # 测试模块：基础测试、Mihomo 管理、真实测试
│   ├── exporter/      # 导出模块：Clash YAML、Base64 订阅
│   ├── gui/           # GUI 模块：桌面应用界面
│   ├── web/           # Web 模块：FastAPI RESTful 接口
│   └── cli/           # CLI 模块：命令行入口
├── bin/               # Mihomo 二进制文件目录
├── data/              # SQLite 数据库存储
├── exports/           # 导出文件目录
├── tests/             # 单元测试
├── tools/             # 打包脚本、smoke test
├── main.py            # CLI 入口
├── run_gui.py         # GUI 启动入口
├── run_web.py         # Web API 启动入口
├── config.example.yaml
└── requirements.txt
```

## License

MIT
