#!/usr/bin/env python3
"""
小红书 AI 自动化内容创作平台 - CLI 入口
"""
import sys
import json
from pathlib import Path

# Windows 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config, get_data_dir, get_output_dir
from src.analyzer.post_parser import PostParser
from src.analyzer.style_extractor import StyleExtractor
from src.generator.text_gen import TextGenerator
from src.generator.quality_check import QualityChecker
from src.generator.topic_engine import TopicEngine
from src.generator.image_gen import ImageGenerator
from src.publisher.xhs_publisher import run_publisher


class NaturalLanguageRouter:
    """自然语言命令路由器"""

    # 命令关键词映射
    COMMAND_MAP = {
        "crawl": {"采集", "爬", "抓取", "crawl", "同步"},
        "import": {"导入", "import", "加载"},
        "analyze": {"分析", "画像", "analyze", "统计", "洞察"},
        "topics": {"选题", "题目", "topics", "出题", "想选题"},
        "generate": {"写", "生成", "创作", "generate", "来一篇", "帮我写", "写一篇"},
        "batch-generate": {"批量", "batch", "全部生成"},
        "publish": {"发布", "发文", "publish", "上传"},
        "chat": {"聊天", "对话", "chat", "交互", "助手"},
    }

    TYPE_MAP = {
        "case_story": {"案例", "故事", "case", "story"},
        "relationship_tips": {"技巧", "干货", "tips", "建议", "方法"},
        "quotes_opinions": {"观点", "金句", "quote", "opinion", "看法"},
        "hot_topics": {"热点", "hot", "话题", "热搜"},
    }

    def parse(self, text):
        """
        解析自然语言，返回 (command, kwargs)
        解析失败返回 (None, {})
        """
        import re

        text_lower = text.lower().strip()
        if not text_lower:
            return None, {}

        # 1. 识别命令
        command = self._detect_command(text_lower)
        if not command:
            return None, {}

        kwargs = {}

        # 2. 提取数字（数量）
        count = self._extract_number(text)
        if count is not None:
            kwargs["count"] = count

        # 3. 提取内容类型
        content_type = self._detect_content_type(text_lower)
        if content_type:
            kwargs["content_type"] = content_type

        # 4. 提取主题（生成命令专用）
        if command in ("generate", "batch-generate"):
            topic = self._extract_topic(text)
            if topic:
                kwargs["topic"] = topic

        # 5. 识别 smart 模式关键词
        if command == "topics" and ("智能" in text or "smart" in text_lower or "llm" in text_lower):
            kwargs["mode"] = "smart"

        return command, kwargs

    def _detect_command(self, text):
        # 优先检查复合命令（避免"批量生成"被"生成"抢先匹配）
        priority = ["batch-generate", "chat"]
        for cmd in priority:
            for kw in self.COMMAND_MAP[cmd]:
                if kw in text:
                    return cmd
        for cmd, keywords in self.COMMAND_MAP.items():
            if cmd in priority:
                continue
            for kw in keywords:
                if kw in text:
                    return cmd
        return None

    def _detect_content_type(self, text):
        for ctype, keywords in self.TYPE_MAP.items():
            for kw in keywords:
                if kw in text:
                    return ctype
        return None

    def _extract_number(self, text):
        import re
        # 匹配 "X篇" "X个" "写X" "生成X" 等模式
        patterns = [
            r'(\d+)\s*(?:篇|个|条|张)',
            r'(?:写|生成|来|产|出)\s*(\d+)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return int(m.group(1))
        return None

    def _extract_topic(self, text):
        import re

        # 优先匹配引号内容
        m = re.search(r'["""](.+?)["""]', text)
        if m:
            return m.group(1).strip()

        # 匹配 "关于/话题/主题" 后的内容
        for marker in ["关于", "话题", "主题", "题目", "写", "生成", "创作"]:
            if marker in text:
                idx = text.find(marker) + len(marker)
                rest = text[idx:].strip()
                # 去掉开头的数量词
                rest = re.sub(r'^\d+\s*(?:篇|个|条)?\s*', '', rest)
                # 去掉末尾的类型词（作为独立词匹配，避免误删子串如"沟通技巧"）
                for type_word in ["案例", "故事", "技巧", "干货", "观点", "金句", "热点"]:
                    rest = re.sub(rf'{type_word}\s*$', '', rest)
                # 去掉末尾的"的"
                rest = re.sub(r'的\s*$', '', rest)
                # 去掉末尾标点
                rest = re.sub(r'[，。！？,\.\!\?]+\s*$', '', rest)
                rest = rest.strip()
                if rest:
                    return rest

        # 兜底：去掉已知动词和数量，取剩余最长有意义的片段
        cleaned = text
        for keywords in self.COMMAND_MAP.values():
            for kw in keywords:
                cleaned = cleaned.replace(kw, '', 1)
        cleaned = re.sub(r'\d+\s*(?:篇|个|条)?', '', cleaned)
        cleaned = re.sub(r'[，。！？,\.\!\?]+.*$', '', cleaned)
        cleaned = cleaned.strip()
        if len(cleaned) >= 2:
            return cleaned

        return None


def _save_as_draft(post, cover_path, content_type):
    """将生成内容保存为 Markdown + 图片的草稿格式"""
    from datetime import datetime
    drafts_dir = get_output_dir("drafts")
    safe_title = "".join(c for c in post.get("title", "untitled") if c.isalnum() or c in " _-")[:30]
    folder_name = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_title}"
    draft_dir = drafts_dir / folder_name
    draft_dir.mkdir(parents=True, exist_ok=True)

    # 保存 content.md
    md_content = f"# {post.get('title', '')}\n\n"
    md_content += f"{post.get('content', '')}\n\n"
    md_content += f"---\n"
    md_content += f"标签: {' '.join(post.get('tags', []))}\n"
    md_content += f"封面文字: {post.get('cover_text', '')}\n"
    md_content += f"评论引导: {post.get('comment_prompt', '')}\n"
    md_content += f"类型: {content_type}\n"

    md_path = draft_dir / "content.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 复制封面图
    if cover_path and Path(cover_path).exists():
        images_dir = draft_dir / "images"
        images_dir.mkdir(exist_ok=True)
        import shutil
        shutil.copy(cover_path, images_dir / "cover.png")

    return draft_dir


def cmd_import():
    """导入历史博文"""
    parser = PostParser()
    posts = parser.load_all_posts()
    summary = parser.export_summary(posts)
    print(f"\n已加载 {summary['total_posts']} 篇历史博文")
    if summary["total_posts"] > 0:
        print(f"  平均标题长度: {summary['avg_title_length']:.0f} 字")
        print(f"  平均正文长度: {summary['avg_content_length']:.0f} 字")
        print(f"  热门标签 TOP10:")
        for tag, count in list(summary["top_tags"].items())[:10]:
            print(f"    #{tag}: {count}次")
    else:
        print("\n未找到历史博文。请将博文放入 data/posts/ 目录，支持以下格式:")
        print("  - JSON 文件: 每篇博文一个 JSON 对象")
        print("  - Markdown 文件: 用 ## 标题分隔")


def cmd_analyze():
    """分析历史博文，生成账号画像"""
    parser = PostParser()
    posts = parser.load_all_posts()

    if not posts:
        print("错误: 未找到历史博文，请先导入")
        return

    print(f"\n开始分析 {len(posts)} 篇博文...")

    extractor = StyleExtractor(posts)
    profile = extractor.extract_all()

    # 保存分析结果
    analytics_dir = get_data_dir("analytics")
    output_path = analytics_dir / "profile.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print(f"\n=== 账号画像摘要 ===")
    print(f"标题模式:")
    tp = profile["title_patterns"]
    print(f"  含数字标题占比: {tp.get('ratio_number', 0):.0%}")
    print(f"  含问号标题占比: {tp.get('ratio_question', 0):.0%}")
    print(f"  平均标题长度: {tp.get('avg_length', 0):.0f} 字")

    print(f"\n内容长度:")
    ls = profile["length_stats"]
    print(f"  平均: {ls['avg']}字, 最短: {ls['min']}字, 最长: {ls['max']}字")

    print(f"\nEmoji 使用:")
    eu = profile["emoji_usage"]
    print(f"  平均每篇: {eu['avg_per_post']:.1f}个")
    print(f"  最常用: {list(eu['top_emojis'].keys())[:5]}")

    print(f"\n情感倾向:")
    sen = profile["sentiment"]
    print(f"  基调: {sen['tone']}")
    print(f"  正向: {sen['positive']}, 中性: {sen['neutral']}, 负面: {sen['negative']}")

    print(f"\n互动模式:")
    eng = profile.get("engagement_patterns", {})
    if eng:
        print(f"  头部内容平均互动: {eng.get('avg_engagement_top', 0):.0f}")
        print(f"  全部平均互动: {eng.get('avg_engagement_all', 0):.0f}")

    print(f"\n详细画像已保存到: {output_path}")


def cmd_generate(topic=None, count=1, content_type="case_story"):
    """生成新内容"""
    config = load_config()

    # 加载风格指南
    style_guide_path = Path(__file__).resolve().parent / "config" / "style_guide.md"
    style_guide = ""
    if style_guide_path.exists():
        style_guide = style_guide_path.read_text(encoding="utf-8")

    # 尝试加载画像
    profile_path = get_data_dir("analytics") / "profile.json"
    profile = ""
    if profile_path.exists():
        profile = profile_path.read_text(encoding="utf-8")

    generator = TextGenerator(style_guide=style_guide, profile=profile)
    checker = QualityChecker()
    image_gen = ImageGenerator()
    gen_dir = get_data_dir("generated")

    if not topic:
        print("请指定生成主题，例如:")
        print("  python main.py generate --topic '夫妻沟通技巧'")
        print("  python main.py generate --topic '冷战背后的真相' --type relationship_tips")
        return

    for i in range(count):
        print(f"\n{'='*50}")
        print(f"正在生成第 {i+1} 篇...")

        post = generator.generate_post(topic, content_type)
        result = checker.check(post)

        print(f"\n标题: {post.get('title', '')}")
        print(f"\n正文:\n{post.get('content', '')}")
        print(f"\n标签: {' '.join(post.get('tags', []))}")
        print(f"\n封面文字: {post.get('cover_text', '')}")
        print(f"\n评论引导: {post.get('comment_prompt', '')}")

        print(f"\n--- 审核结果 ---")
        print(f"评分: {result['score']}")
        print(f"通过: {'是' if result['passed'] else '否'}")
        if result["issues"]:
            print(f"问题: {'; '.join(result['issues'])}")
        if result["suggestions"]:
            print(f"建议: {'; '.join(result['suggestions'])}")

        # 保存到待审核目录
        from src.analyzer.post_parser import XhsPost
        from datetime import datetime
        new_post = XhsPost(
            title=post.get("title", ""),
            content=post.get("content", ""),
            tags=post.get("tags", []),
            publish_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        parser = PostParser()
        filepath = parser.save_post(new_post, f"generated_{i+1}.json", target_dir=gen_dir)
        print(f"\n已保存到: {filepath}")

        # 生成封面图
        cover_path = gen_dir / f"generated_{i+1}_cover.png"
        try:
            image_gen.generate_cover(
                title=post.get("title", ""),
                output_path=cover_path,
                content_type=content_type,
            )
            print(f"封面图已保存到: {cover_path}")
        except Exception as e:
            print(f"[警告] 封面图生成失败: {e}")
            cover_path = None

        # 保存为草稿格式（便于人工审核和发布）
        draft_dir = _save_as_draft(post, cover_path, content_type)
        print(f"草稿已保存到: {draft_dir}")


def cmd_batch_generate(topics_file, content_type="case_story"):
    """批量生成内容"""
    topics_path = Path(topics_file)
    if not topics_path.exists():
        print(f"错误: 找不到选题文件 {topics_file}")
        print("请先创建选题文件，每行一个主题")
        return

    with open(topics_path, "r", encoding="utf-8") as f:
        topics = []
        for line in f:
            line = line.strip()
            # 只提取编号标题行（如 "1. 标题内容"），忽略元数据行
            if line and line[0].isdigit() and ". " in line:
                topics.append(line.split(". ", 1)[1].strip())

    print(f"从 {topics_file} 加载了 {len(topics)} 个选题")
    print(f"开始批量生成...\n")

    for topic in topics:
        cmd_generate(topic=topic, content_type=content_type)


def cmd_topics(count=30, mode="fast", content_type=None):
    """自动生成选题"""
    engine = TopicEngine()

    # 展示历史数据洞察
    analysis = engine.analyze_historical_performance()
    if analysis["total_posts"] > 0:
        print("\n=== 历史数据洞察 ===")
        print(f"总笔记: {analysis['total_posts']} 篇")
        print(f"有浏览数据: {analysis['posts_with_data']} 篇")
        if analysis["top_posts"]:
            print("头部爆款 TOP3:")
            for i, p in enumerate(analysis["top_posts"][:3], 1):
                print(f"  {i}. {p['title'][:32]}... (浏览:{p['views']:,})")
        for insight in analysis["insights"]:
            print(f"  • {insight}")
        print()

    print(f"正在生成 {count} 个选题 [模式: {mode}]...")
    topics = engine.generate(count=count, mode=mode, content_type=content_type)
    output_path = engine.save(topics)

    print(f"\n已生成 {len(topics)} 个选题\n")
    print("=" * 60)
    for i, t in enumerate(topics[:10], 1):
        print(f"{i}. [{t.get('content_type', '')}] {t.get('title', '')}")
        if t.get("story_hook"):
            print(f"   引入: {t['story_hook']}")
    if len(topics) > 10:
        print(f"... 共 {len(topics)} 个，详见 {output_path}")
    print("=" * 60)

    print(f"\n保存位置:")
    print(f"  JSON: {output_path}")
    print(f"  TXT:  {output_path.with_suffix('.txt')}")
    print("\n使用方式:")
    print(f"  python main.py batch-generate {output_path.with_suffix('.txt')}")


def _execute_command(command, kwargs):
    """根据解析结果执行对应命令"""
    if command == "crawl":
        from src.scraper import run_collector
        max_posts = kwargs.get("count", 100)
        run_collector(max_posts=max_posts)
    elif command == "import":
        cmd_import()
    elif command == "analyze":
        cmd_analyze()
    elif command == "topics":
        cmd_topics(
            count=kwargs.get("count", 30),
            mode=kwargs.get("mode", "fast"),
            content_type=kwargs.get("content_type"),
        )
    elif command == "generate":
        topic = kwargs.get("topic")
        if not topic:
            print("请告诉我你想写什么主题，例如：")
            print('  python main.py 写一篇关于"冷战"的案例')
            return
        cmd_generate(
            topic=topic,
            count=kwargs.get("count", 1),
            content_type=kwargs.get("content_type", "case_story"),
        )
    elif command == "batch-generate":
        topics_file = kwargs.get("topic", "topics.txt")
        cmd_batch_generate(topics_file, kwargs.get("content_type", "case_story"))
    elif command == "publish":
        run_publisher(dry_run=False)
    elif command == "chat":
        cmd_chat()
    else:
        print(f"未知命令: {command}")


def cmd_chat():
    """交互式对话模式"""
    print("\n" + "=" * 50)
    print("  AutoXHS 交互助手")
    print("=" * 50)
    print("你可以用自然语言输入命令，例如：")
    print('  "采集数据" / "分析账号" / "生成30个选题"')
    print('  "写一篇关于冷战的案例故事" / "发布"')
    print('输入 "帮助" 查看示例，输入 "退出" 结束对话\n')

    router = NaturalLanguageRouter()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("退出", "quit", "exit", "q", "bye"):
            print("再见！")
            break

        if user_input.lower() in ("帮助", "help", "h", "?"):
            _print_chat_help()
            continue

        command, kwargs = router.parse(user_input)
        if command:
            _execute_command(command, kwargs)
        else:
            print("没听懂，试试这些：")
            print('  "采集数据" / "分析" / "生成20个选题"')
            print('  "写一篇关于沟通的干货" / "发布"')


def _print_chat_help():
    """打印交互模式帮助"""
    print("\n--- 自然语言命令示例 ---")
    print("数据相关:")
    print('  "采集数据" / "爬取笔记" / "同步后台数据"')
    print('  "导入历史博文" / "分析账号画像"')
    print("\n选题相关:")
    print('  "生成30个选题" / "给我20个题目"')
    print('  "智能生成10个选题" / "出5个案例故事题目"')
    print("\n内容生成:")
    print('  "写一篇关于冷战的案例"')
    print('  "生成3篇沟通技巧的干货"')
    print('  "来一篇关于情绪价值的观点文"')
    print('  "批量生成"')
    print("\n发布:")
    print('  "发布" / "发文"')
    print("\n其他:")
    print('  "帮助" / "退出"')
    print("-" * 30)


KNOWN_COMMANDS = {"crawl", "import", "analyze", "generate", "batch-generate", "topics", "publish", "chat"}


def _print_help():
    print("小红书 AI 自动化内容创作平台 - AutoXHS")
    print("\n=== 自然语言命令（推荐）===")
    print('  python main.py 采集                # 采集后台数据')
    print('  python main.py 分析                # 分析账号画像')
    print('  python main.py 生成30个选题        # 生成选题')
    print('  python main.py 写一篇关于冷战的案例   # 单篇生成')
    print('  python main.py 生成3篇沟通技巧的干货  # 多篇生成')
    print('  python main.py 批量生成             # 批量从topics.txt生成')
    print('  python main.py 发布                # 发布已审核内容')
    print('  python main.py chat                # 进入交互对话模式')
    print("\n=== 传统命令 ===")
    print("  crawl [--max <数量>]      自动采集创作者后台笔记数据")
    print("  import                    导入历史博文")
    print("  analyze                   分析历史博文，生成账号画像")
    print("  generate [选项]           生成新内容")
    print("    --topic <主题>          指定生成主题")
    print("    --type <类型>           内容类型: case_story/relationship_tips/quotes_opinions/hot_topics")
    print("    --count <数量>          生成篇数")
    print("  batch-generate <文件>     批量生成（从选题文件读取）")
    print("  topics [选项]             自动生成选题")
    print("    --count <数量>          生成数量 (默认30)")
    print("    --mode <模式>           fast(模板,默认) / smart(LLM驱动)")
    print("    --type <类型>           指定内容类型")
    print("  publish [--dry-run]       发布 output/approved/ 中的内容")
    print("\n工作流: 采集 → 分析 → 选题 → 生成 → (人工审核) → 发布")


def main():
    args = sys.argv[1:]
    if not args:
        _print_help()
        return

    command = args[0]

    # 已知命令走原有解析逻辑
    if command in KNOWN_COMMANDS:
        if command == "import":
            cmd_import()
        elif command == "analyze":
            cmd_analyze()
        elif command == "topics":
            count = 30
            mode = "fast"
            content_type = None
            i = 1
            while i < len(args):
                if args[i] == "--count" and i + 1 < len(args):
                    count = int(args[i + 1])
                    i += 2
                elif args[i] == "--mode" and i + 1 < len(args):
                    mode = args[i + 1]
                    i += 2
                elif args[i] == "--type" and i + 1 < len(args):
                    content_type = args[i + 1]
                    i += 2
                else:
                    i += 1
            cmd_topics(count=count, mode=mode, content_type=content_type)
        elif command == "publish":
            dry_run = "--dry-run" in args
            run_publisher(dry_run=dry_run)
        elif command == "generate":
            topic = None
            count = 1
            content_type = "case_story"
            i = 1
            while i < len(args):
                if args[i] == "--topic" and i + 1 < len(args):
                    topic = args[i + 1]
                    i += 2
                elif args[i] == "--type" and i + 1 < len(args):
                    content_type = args[i + 1]
                    i += 2
                elif args[i] == "--count" and i + 1 < len(args):
                    count = int(args[i + 1])
                    i += 2
                else:
                    i += 1
            cmd_generate(topic=topic, count=count, content_type=content_type)
        elif command == "batch-generate":
            if len(args) < 2:
                print("用法: python main.py batch-generate <选题文件>")
                return
            cmd_batch_generate(args[1])
        elif command == "crawl":
            from src.scraper import run_collector
            max_posts = 100
            i = 1
            while i < len(args):
                if args[i] == "--max" and i + 1 < len(args):
                    max_posts = int(args[i + 1])
                    i += 2
                else:
                    i += 1
            run_collector(max_posts=max_posts)
        elif command == "chat":
            cmd_chat()
        return

    # 未知命令尝试自然语言解析
    router = NaturalLanguageRouter()
    full_text = " ".join(args)
    parsed_cmd, kwargs = router.parse(full_text)

    if parsed_cmd:
        _execute_command(parsed_cmd, kwargs)
    else:
        print(f"没听懂: {' '.join(args)}")
        print()
        print("你可以这样输入:")
        print('  python main.py 采集')
        print('  python main.py 分析')
        print('  python main.py 生成30个选题')
        print('  python main.py 写一篇关于冷战的案例')
        print('  python main.py 发布')
        print()
        print('或者进入交互模式: python main.py chat')
        print('也支持传统命令，运行 python main.py 查看完整帮助')


if __name__ == "__main__":
    main()
