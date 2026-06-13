# Alpha 中文显示补丁备份

本目录记录本地提交 0072653 Localize Alpha dashboard display 的远程备份。

由于本机 git push origin main 失败，错误为 could not read Username for https://github.com: Device not configured，且 SSH push 失败为 Permission denied publickey，本轮先用 GitHub connector 将完整 patch 备份到远程。

补丁文件：outputs/patches/0072653-localize-alpha-dashboard-display.patch.gz.b64

还原方式：

```bash
base64 -d outputs/patches/0072653-localize-alpha-dashboard-display.patch.gz.b64 | gunzip > /tmp/0072653-localize-alpha-dashboard-display.patch
git am /tmp/0072653-localize-alpha-dashboard-display.patch
```

本轮验证：

```text
.venv/bin/python -m pytest tests/test_dashboard_state.py -q -> 4 passed
.venv/bin/python -m pytest tests -q -> 21 passed
git diff --check -> passed
Browser -> 中文 dashboard 可见，点击 运行模拟交易周期 成功，控制台错误为空
```
