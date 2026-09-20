# tgsearch115 插件项目规则

## 发版流程（必须遵守）

发布新版本时，**必须同时修改两处版本号**，缺一不可，否则 MoviePilot 不会提示更新：

### 1. 插件代码版本号
文件：`plugins.v2/tgsearch115/__init__.py`
字段：`plugin_version`（约第 252 行）
```python
plugin_version = "4.8.16"  # 改为新版本号
```

### 2. MoviePilot 市场清单（MP 实际比对这个）
文件：`package.v2.json`（仓库根目录）
需要改两处：
- `version` 字段（约第 6 行）：改为新版本号
- `history` 对象顶部（约第 10 行）：在最新版本条目**之前**插入新版本日志

```json
{
  "TgSearch115": {
    "version": "4.8.16",
    ...
    "history": {
      "v4.8.16": "本版本更新说明...",
      "v4.8.15": "上一版本说明...",
      ...
    }
  }
}
```

### 3. 提交并推送
```bash
git add plugins.v2/tgsearch115/__init__.py package.v2.json
git commit -m "vX.Y.Z: 简要说明"
git push origin main
```

## 关键提醒

- `package.v2.json` 的 `version` 是 MoviePilot 检测更新的**唯一**依据，只改 `__init__.py` 的 `plugin_version` 不会触发更新提示。
- 两个文件的版本号必须**完全一致**。
- `history` 新条目必须加在对象**顶部**（最新版本在最前）。
- `history` 的 key 带 `v` 前缀（如 `v4.8.16`），`version` 字段和 `plugin_version` **不带** `v` 前缀（如 `4.8.16`）。

## 代码风格

- Python 文件不添加注释，除非用户明确要求。
- 遵循现有代码的命名约定、库选择和模式。
