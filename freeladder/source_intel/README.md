# 源情报引擎 (Source Intelligence Engine)

## 简介

源情报引擎是 FreeLadder 的第三方公开源发现、验证、评分和管理系统。

**核心理念:**
```
可发现 → 可验证 → 可评分 → 可候选 → 用户确认 → 可启用 → 可禁用 → 可持续维护
```

## 与硬编码内置源的区别

| 特性 | 硬编码内置源 | 源情报引擎 |
|------|------------|-----------|
| 来源 | 固定 25 个 URL | 动态发现 GitHub/非 GitHub 源 |
| 更新 | 手动更新代码 | 自动监控仓库变化 |
| 验证 | 无 | 验证能否解析出节点 |
| 健康度 | 无 | 基于成功率/新鲜度/协议多样性评分 |
| 用户控制 | 全部启用 | 默认 disabled，需用户确认启用 |

## GitHub 源监控原理

1. 监控 8 个种子仓库的 README、候选文件、releases
2. 使用 ETag/Last-Modified 做条件请求，304 时跳过
3. 从内容中提取候选订阅链接
4. 验证链接能否解析出节点
5. 记录源健康度

## 非 GitHub 公开源发现原理

- 默认关闭，需用户配置站点列表
- 只扫描用户明确指定的公开网页
- 不递归深爬，不绕过反爬
- 所有发现的源默认 disabled

## 为什么第三方源默认 disabled

- 第三方公开源稳定性和安全性不可保证
- 用户应自行评估风险后再启用
- 避免未经验证的源影响节点质量

## 如何验证源

```bash
freeladder source-intel validate              # 验证所有候选源
freeladder source-intel validate --source-id <id>  # 验证指定源
```

## 如何启用源

```bash
freeladder source-intel enable <id>           # 需确认
freeladder source-intel enable <id> --yes     # 跳过确认（仅单个源）
```

## 如何禁用源

```bash
freeladder source-intel disable <id>
```

## 如何查看健康评分

```bash
freeladder source-intel health
freeladder source-intel health --json-output
```

## 配置 GitHub token

在 `config.yaml` 中设置:
```yaml
source_intel:
  github_token: "ghp_xxxxxxxxxxxx"
```

- 无 token 时使用匿名 API（有速率限制）
- token 不会写入日志

## 为什么不会自动关注仓库

- GitHub 账号 Watch 功能默认完全关闭
- 需要用户配置 token 并显式启用
- GUI/CLI 都会弹窗确认

## 失败缓存逻辑

- 单源请求失败后进入失败缓存
- 缓存时间: 60 分钟（可配置）
- 缓存期内跳过该源
- 连续失败 5 次标记 DEAD

## 健康评分逻辑

```
quality_score =
    0.35 * success_rate
  + 0.20 * freshness_score
  + 0.20 * node_count_score
  + 0.15 * protocol_diversity_score
  + 0.10 * stability_score
  - failure_penalty
```

## CLI 使用示例

```bash
# 列出所有源
freeladder source-intel list

# 只看候选源
freeladder source-intel list --candidates

# 扫描 GitHub 仓库
freeladder source-intel scan-github

# 验证候选源
freeladder source-intel validate

# 启用源
freeladder source-intel enable <id>

# 查看健康评分
freeladder source-intel health

# 导出健康报告
freeladder source-intel export-health
```

## 常见错误排查

**Q: GitHub API 限流**
A: 配置 `github_token` 提高速率限制

**Q: 源验证失败**
A: 检查 URL 是否可访问，是否需要代理

**Q: 源被标记 DEAD**
A: 连续失败 5 次自动标记，可手动重新验证
