FreeLadder Windows Portable

使用方法：
1. 解压整个 FreeLadder 文件夹
2. 双击 START.bat 或 FreeLadder.exe
3. 第一次运行会自动创建 config.yaml
4. 编辑 config.yaml 添加自己的订阅源
5. 如果要使用高级协议测试或 Browser Sandbox，请放入 mihomo.exe
6. 如果要使用内置隔离浏览器，请确保 ms-playwright/chromium 存在

目录说明：
- config.yaml：用户配置
- data/：数据库
- exports/：导出配置
- logs/：日志
- bin/：mihomo.exe 目录
- ms-playwright/：Playwright Chromium 浏览器目录
- tools/：辅助工具脚本

注意：
- 本软件不会修改系统代理
- Browser Sandbox 只影响它自己启动的 Chromium
- 不内置任何节点源
- 请确保节点来源合法合规
