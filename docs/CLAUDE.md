# AutoXHS — 小红书 AI 自动化内容创作平台

## 项目概述

自动化的情感/两性关系领域小红书内容生成平台。目标：12 个月内达到 10 万粉丝。

**核心流程**：`crawl` → `import` → `analyze` → `generate` → `publish`

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置 LLM（选择一种）
# 方式 A: 编辑 config/settings.yaml
# 方式 B: 设置环境变量（推荐）
#   LLM_PROVIDER=openai
#   LLM_MODEL=kimi-k2.6
#   LLM_API_KEY=sk-xxx
#   LLM_BASE_URL=https://api.moonshot.cn/v1

# 3. 采集数据（需要已登录的 Chrome/Edge 浏览器）
python main.py crawl

# 4. 导入 & 分析
python main.py import
python main.py analyze

# 5. 生成内容
python main.py generate --topic "夫妻沟通技巧"
python main.py generate --topic "冷战背后的真相" --type relationship_tips --count 3
```

## 项目结构

```
xiaohongshu/
├── main.py                     # CLI 入口
├── config/
│   ├── settings.yaml           # 全局配置（不提交）
│   ├── style_guide.md          # 内容风格指南
│   └── banned_words.txt        # 违禁词列表
├── data/                       # 输入数据（只读）
│   ├── posts/
│   │   └── all_posts.json      # 主数据集（28 篇笔记）
│   └── analytics/
│       └── profile.json        # 账号画像
├── docs/                       # 参考文档
│   ├── PRD.md                  # 产品需求文档
│   ├── CLAUDE.md               # AI 助手指南（本文件）
│   └── reference/              # 手动撰写的参考笔记
│       ├── 婚姻时机_v1.md
│       ├── 婚姻时机_v2.md
│       └── 婚姻时机_发布版.md
├── output/                     # 产出物（按生命周期）
│   ├── drafts/                 # AI 生成草稿（待审核）
│   ├── approved/               # 审核通过（待发布）
│   │   └── 2026-05-08_标题/
│   │       ├── content.md      # 正文
│   │       └── images/         # 封面图
│   └── published/              # 已发布
│       └── 2026-05/
│           └── 2026-05-08_标题/
├── src/
│   ├── config.py               # 配置加载器
│   ├── analyzer/               # 分析模块
│   │   ├── post_parser.py      # 博文解析器
│   │   └── style_extractor.py  # 风格提取器
│   ├── generator/              # 生成模块
│   │   ├── text_gen.py         # LLM 文本生成
│   │   └── quality_check.py    # 质量审核
│   ├── scraper/                # 采集模块
│   │   └── xhs_crawler.py      # 小红书爬虫
│   └── publisher/              # 发布模块（待开发）
└── scripts/                    # 工具脚本（按需添加）
```

**目录设计原则**：
- `data/` = 输入（采集的数据），只读
- `output/` = 输出（生成的内容），按生命周期组织：drafts → approved → published
- `docs/` = 参考文档，人类可读
- `config/` = 配置，不提交 git
- 每篇笔记 = 一个文件夹，content.md + images/ 在一起

## 核心命令

| 命令 | 说明 |
|------|------|
| `python main.py crawl` | 从创作者后台采集笔记元数据 |
| `python main.py import` | 导入历史笔记到系统 |
| `python main.py analyze` | 分析笔记风格，生成账号画像 |
| `python main.py generate --topic "主题"` | AI 生成单篇笔记 |
| `python main.py batch-generate topics.txt` | 批量生成（从文件读取选题） |

## 内容类型

| 类型 | 占比 | 说明 |
|------|------|------|
| case_story | 40% | 真实案例故事 |
| relationship_tips | 30% | 关系技巧建议 |
| quotes_opinions | 15% | 观点金句 |
| hot_topics | 15% | 热点话题解读 |

## 已知技术限制

1. **创作者后台 API 仅返回元数据**（标题、浏览量、点赞数），不包含正文内容
2. **编辑器页面 404**：`creator.xiaohongshu.com/editor/{id}` 对创作者笔记不可用
3. **公开 explore 页面**仅对公开可见的笔记有效，创作者专属笔记返回 300031 错误
4. **虚拟滚动**：笔记管理页仅渲染可视区域约 5 个笔记的 DOM，无法一次性获取全部
5. **6 篇创作者专属笔记缺失正文**：需手动从手机 APP 端复制内容到 `data/posts/all_posts.json`
6. **Windows 控制台编码**：所有 Python 脚本需要 `sys.stdout.reconfigure(encoding='utf-8')`
7. **Playwright 进程残留**：运行前如有 Chrome/Edge 占用配置文件，需先 kill 残留进程
8. **Kimi API**：使用 `provider: openai` + `base_url: https://api.moonshot.cn/v1`

## 数据状态

- 总笔记：28 篇（12 篇创作者后台 + 16 篇公开主页）
- 有正文：22 篇
- 有浏览数据：12 篇
- 总浏览：757,349

## LLM 配置

支持两种 provider：

### OpenAI 兼容（Kimi / Moonshot）
```yaml
llm:
  provider: "openai"
  model: "kimi-k2.6"
  api_key: "sk-xxx"
  base_url: "https://api.moonshot.cn/v1"
```

### Anthropic Claude
```yaml
llm:
  provider: "claude"
  model: "claude-sonnet-4-6"
  api_key: "sk-ant-xxx"
```
