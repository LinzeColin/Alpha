# Alpha 本地 App 入口

主要 `.app` 格式入口：

```text
/Users/linzezhang/Downloads/Alpha.app
/Users/linzezhang/Applications/Alpha.app
/Applications/Alpha.app
```

仓库内 App 源文件和生成包：

```text
outputs/applications/Alpha.applescript
outputs/applications/Alpha.app
```

兼容命令入口：

```text
outputs/applications/Alpha.command
outputs/applicatioins/Alpha.command
```

命令会启动 FastAPI 控制台：

```text
http://127.0.0.1:8000/dashboard
```

该 App 是由 `outputs/applications/Alpha.applescript` 生成的 AppleScript `.app`。
它会调用 `scripts/start_alpha_dashboard.sh`，在缺少 `.venv` 时创建虚拟环境，
启动 `uvicorn`，在 FastAPI 应用生命周期内启动 300 秒刷新一次的模拟交易智能体循环，
将控制台日志写入 `runtime/alpha_dashboard.log`，并在 macOS 上打开控制台 URL。

控制台自动循环状态可通过以下地址查看：

```text
http://127.0.0.1:8000/agent/loop/status
```

已验证的 App 安装状态：

```text
仓库、Downloads、用户 Applications、系统 Applications 中的 Alpha.app 均通过 plutil -lint。
open -n /Users/linzezhang/Downloads/Alpha.app 可启动控制台和应用托管的模拟交易循环。
```
