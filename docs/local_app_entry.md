# Alpha 本地应用入口

主要 `.app` 格式入口：

```text
/Users/linzezhang/Downloads/Alpha.app
/Users/linzezhang/Applications/Alpha.app
/Applications/Alpha.app
```

仓库内应用源文件和生成包：

```text
outputs/applications/Alpha.applescript
outputs/applications/Alpha.app
```

兼容命令入口：

```text
outputs/applications/Alpha.command
outputs/applications/Alpha.command
```

命令会启动 FastAPI 控制台：

```text
http://127.0.0.1:8000/dashboard
```

该应用是由 `outputs/applications/Alpha.applescript` 生成的 AppleScript `.app`。
它会调用 `scripts/start_alpha_dashboard.sh`，在缺少 `.venv` 时创建虚拟环境，
启动 `uvicorn`，在 FastAPI 应用生命周期内启动 300 秒刷新一次的模拟交易智能体循环，
同时启动 300 秒采样一次的自动运行维护，
将控制台日志写入 `runtime/alpha_dashboard.log`，并在 macOS 上打开控制台 URL。

控制台用户可见页面、按钮、状态、风险原因和本地命令摘要默认中文显示；API 字段名、
内部枚举、工单号、文件路径和股票代码保持机器可读格式。

控制台自动循环状态可通过以下地址查看：

```text
http://127.0.0.1:8000/agent/loop/status
```

已验证的本地应用安装状态：

```text
python scripts/verify_app_entry.py
仓库、Downloads、用户 Applications、系统 Applications 中的 Alpha.app 均通过 bundle 完整性检查。
安装副本与仓库 Alpha.app 的关键文件指纹一致。
AppleScript 和命令入口均指向当前仓库 scripts/start_alpha_dashboard.sh。
open -n /Users/linzezhang/Downloads/Alpha.app 可启动控制台和应用托管的模拟交易循环。
```
