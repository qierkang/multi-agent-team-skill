## 变更说明

<!-- 说明任务目标、影响路由和向后兼容性。 -->

## 验证证据

- [ ] `python3 scripts/health_check.py --deep`
- [ ] `PYTHONOPTIMIZE=1 python3 scripts/regression_check.py`
- [ ] `bash scripts/verify_assets.sh .`（如改动 README 或 assets）
- [ ] 没有绝对本机路径、密钥、客户信息或临时文件

## 影响与回滚

<!-- 说明对 templates、install、既有项目迁移或兼容性的影响；无影响请写“无”。 -->
