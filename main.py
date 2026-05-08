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
        topics = [line.strip() for line in f if line.strip()]

    print(f"从 {topics_file} 加载了 {len(topics)} 个选题")
    print(f"开始批量生成...\n")

    for topic in topics:
        cmd_generate(topic=topic, content_type=content_type)


def cmd_topics(count=30):
    """自动生成选题"""
    engine = TopicEngine()
    topics = engine.generate(count=count)
    output_path = engine.save(topics)

    print(f"\n已生成 {len(topics)} 个选题，保存到: {output_path}\n")
    print("=" * 50)
    for i, t in enumerate(topics[:10], 1):
        print(f"{i}. {t}")
    if len(topics) > 10:
        print(f"... 共 {len(topics)} 个，详见文件")
    print("=" * 50)
    print("\n使用方式:")
    print(f"  python main.py batch-generate {output_path}")


def main():
    args = sys.argv[1:]
    if not args:
        print("小红书 AI 自动化内容创作平台 - AutoXHS")
        print("\n用法: python main.py <命令> [参数]\n")
        print("命令:")
        print("  crawl [--max <数量>]      自动采集创作者后台笔记数据")
        print("  import                    导入历史博文")
        print("  analyze                   分析历史博文，生成账号画像")
        print("  generate [选项]           生成新内容")
        print("    --topic <主题>          指定生成主题")
        print("    --type <类型>           内容类型: case_story/relationship_tips/quotes_opinions/hot_topics")
        print("    --count <数量>          生成篇数")
        print("  batch-generate <文件>     批量生成（从选题文件读取）")
        print("  topics [--count <数量>]   自动生成选题")
        print("  publish [--dry-run]       发布 output/approved/ 中的内容")
        print()
        print("工作流:")
        print("  crawl → analyze → topics → generate → (人工审核) → publish")
        print()
        print("快速开始:")
        print("  1. python main.py crawl          # 自动从创作者后台采集所有笔记")
        print("  2. python main.py analyze        # 分析账号画像")
        print("  3. python main.py topics         # 生成选题")
        print("  4. python main.py generate --topic '你的选题'  # 生成内容")
        print("  5. # 人工审核后移动到 output/approved/")
        print("  6. python main.py publish        # 自动发布")
        return

    command = args[0]

    if command == "import":
        cmd_import()
    elif command == "analyze":
        cmd_analyze()
    elif command == "topics":
        count = 30
        i = 1
        while i < len(args):
            if args[i] == "--count" and i + 1 < len(args):
                count = int(args[i + 1])
                i += 2
            else:
                i += 1
        cmd_topics(count=count)
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
    else:
        print(f"未知命令: {command}")
        print("运行 python main.py 查看帮助")


if __name__ == "__main__":
    main()
