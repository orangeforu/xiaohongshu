# AutoXHS — 小红书 AI 自动化内容创作平台

> 用 AI 高效做小红书情感赛道内容创作，12 个月冲刺 10 万粉丝。

## 赛道定位

情感分析 / 两性关系相处案例分享

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置 LLM API Key（编辑 config/settings.yaml 或设置环境变量）

# 3. 采集数据（需要已在浏览器登录小红书创作者后台）
python main.py crawl

# 4. 导入 & 分析
python main.py import
python main.py analyze

# 5. AI 生成内容
python main.py generate --topic "夫妻沟通技巧"
python main.py generate --topic "冷战背后的真相" --type relationship_tips --count 3

# 6. 批量生成（从选题文件）
python main.py batch-generate topics.txt
```

详细命令说明见 [CLAUDE.md](CLAUDE.md)。

## 项目结构

```
xiaohongshu/
├── main.py                     # CLI 入口
├── config/
│   ├── settings.yaml           # 全局配置（不提交 git）
│   ├── style_guide.md          # 内容风格指南
│   └── banned_words.txt        # 违禁词列表
├── data/
│   ├── posts/
│   │   └── all_posts.json      # 主数据集
│   ├── analytics/
│   │   └── profile.json        # 账号画像
│   ├── images/                 # 封面图片
│   └── generated/              # AI 生成内容
├── src/
│   ├── config.py               # 配置加载器
│   ├── analyzer/               # 分析模块
│   ├── generator/              # 生成模块
│   ├── scraper/                # 采集模块
│   └── publisher/              # 发布模块（待开发）
└── scripts/                    # 工具脚本
```

## 工作流

```
数据采集 → 数据导入 → 风格分析 → 账号画像
                                    ↓
                    选题 → 文案生成 → 质量审核 → 人工确认 → 发布
                                                    ↓
                                        数据反馈 → 策略优化
```

## 数据状态

| 指标 | 数值 |
|------|------|
| 总笔记数 | 28 篇 |
| 有正文 | 22 篇 |
| 有浏览数据 | 12 篇 |
| 总浏览量 | 757,349 |

> 6 篇创作者专属笔记缺失正文（需手动从 APP 端补充）。详见 CLAUDE.md 已知限制。

## 当前进度

- [x] 项目骨架搭建
- [x] 配置文件和风格指南
- [x] 数据采集模块（爬虫）
- [x] 数据导入模块
- [x] 风格分析模块
- [x] AI 文案生成模块（支持 Kimi / Claude）
- [x] 质量审核模块
- [ ] 封面图片生成
- [ ] 选题引擎
- [ ] 数据看板
- [ ] 发布调度

## 目标

| 时间 | 粉丝目标 | 发文量 |
|------|---------|--------|
| 起点 | 859 | 49 篇 |
| 3 个月 | 5,000 | 180+ 篇 |
| 6 个月 | 20,000 | 400+ 篇 |
| 12 个月 | 100,000 | 900+ 篇 |
