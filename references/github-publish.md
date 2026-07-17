# GitHub 公开发布清单

本清单用于将本 Skill 从工作区独立发布为公开仓库；不应在父工作区根目录直接初始化新的 Git 仓库。

## 发布门禁

1. 运行 `python3 scripts/health_check.py --deep` 与 `PYTHONOPTIMIZE=1 python3 scripts/regression_check.py`。
2. 运行 `bash scripts/verify_assets.sh .`，确认 Social Preview 小于 1 MiB、图片不缺失且 README 不断链。
3. 检查无 `.env`、密钥、令牌、本机绝对路径、`__pycache__`、`.DS_Store` 和测试临时目录。
4. 确认 `LICENSE`、`CONTRIBUTING.md`、`CHANGELOG.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、Issue 模板与 CI 均存在。
5. 首次推送前不要伪造 Star History 链接、CI 徽章或不存在的演示数据。

## 推荐 GitHub About

- **Description**：Reusable multi-agent team orchestration skill for safe project routing, fresh-context reviews, external task ledgers, and deterministic verification.
- **Topics**：`multi-agent`、`ai-agents`、`agent-orchestration`、`codex`、`claude-code`、`developer-tools`、`ai-coding`、`workflow-automation`、`skills`。
- **Social Preview**：上传 `assets/social-preview.png`。

## 隔离发布

```bash
STAGING="$(mktemp -d)"
rsync -a --exclude '.git' --exclude '.DS_Store' --exclude '__pycache__' --exclude 'tmp' \
  "<skill-dir>/" "$STAGING/"
cd "$STAGING"
git init -b main
git add -A
git commit -m "feat: initial public release"
# 确认远端仓库名后，再使用 gh repo create / git remote add / git push。
```

> GitHub Actions 首次推送如因 token 缺少 `workflow` scope 被拒，应先授权该 scope，再重新推送；不要删除 CI 来规避质量门禁。
