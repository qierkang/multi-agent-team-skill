# 正式视觉资产

本目录只存放可公开展示的静态资产；角色 TOML、项目协作块、文档骨架和报告骨架仍只属于 `templates/`。

| 用途 | 正式文件 | README 引用位置 |
|---|---|---|
| GitHub Social Preview | `social-preview.png`（1280×640，小于 1 MiB） | 中文 / 英文 README 顶部 |
| 中文团队编排图 | `architecture/zh-CN/team-orchestration-overview.png` | 根 README |
| 中文安全升级图 | `architecture/zh-CN/safe-existing-skill-upgrade.png` | 根 README |
| English orchestration overview | `architecture/en/team-orchestration-overview.png` | `docs/README_en.md` |
| English safe upgrade flow | `architecture/en/safe-existing-skill-upgrade.png` | `docs/README_en.md` |

## 维护规则

1. 最终视觉图必须使用 `image_gen` 生成；不得以 Mermaid、HTML 截图或脚本绘制图替代正式资产。
2. 新增、替换或删除图片时，同步更新 `asset-manifest.json`、README 引用与对应提示词文件。
3. 发布前运行 `bash scripts/verify_assets.sh .`；它会验证图片存在性、Social Preview 尺寸和 README 引用完整性。
4. `social-preview.png` 用于 GitHub 仓库设置上传；README 使用带 `?v=` 的 URL 规避 GitHub 图片缓存。
