"""
历史博文解析器
支持从多种格式导入历史博文：
- JSON (从创作者后台导出)
- Markdown (手动整理)
- 纯文本
"""
import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class XhsPost:
    """小红书博文数据结构"""
    title: str
    content: str
    tags: list[str]
    publish_date: str = ""
    likes: int = 0
    favorites: int = 0
    comments: int = 0
    views: int = 0
    images: list[str] = None
    content_type: str = ""  # case_story / relationship_tips / quotes_opinions / hot_topics
    note_id: str = ""  # 小红书笔记ID

    def to_dict(self):
        return asdict(self)

    @property
    def total_engagement(self):
        return self.likes + self.favorites + self.comments


class PostParser:
    """博文解析器"""

    def __init__(self, posts_dir=None):
        from src.config import get_data_dir
        self.posts_dir = Path(posts_dir) if posts_dir else get_data_dir("posts")
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def load_all_posts(self) -> list[XhsPost]:
        """加载所有历史博文"""
        posts = []

        # 从 JSON 文件加载
        for json_file in self.posts_dir.glob("*.json"):
            posts.extend(self._load_json(json_file))

        # 从 Markdown 文件加载
        for md_file in self.posts_dir.glob("*.md"):
            posts.extend(self._load_markdown(md_file))

        return posts

    def save_post(self, post: XhsPost, filename=None, target_dir=None):
        """保存单篇博文为 JSON"""
        if not filename:
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_dir = Path(target_dir) if target_dir else self.posts_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(post.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    def save_batch(self, posts: list[XhsPost], batch_name="import"):
        """批量保存博文"""
        batch_dir = self.posts_dir / batch_name
        batch_dir.mkdir(exist_ok=True)
        for i, post in enumerate(posts):
            self.save_post(post, f"{i+1:03d}.json")
        print(f"已保存 {len(posts)} 篇博文到 {batch_dir}")

    def _load_json(self, filepath) -> list[XhsPost]:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [self._make_post(item) for item in data]
        return [self._make_post(data)]

    def _make_post(self, item: dict) -> XhsPost:
        # 字段名映射兼容
        if "publish_time" in item and "publish_date" not in item:
            item["publish_date"] = item.pop("publish_time")
        if "desc" in item and "content" not in item:
            item["content"] = item.pop("desc")
        # 移除多余字段
        for k in ["type", "status", "xsec_token", "display_title", "corner"]:
            item.pop(k, None)
        return XhsPost(**item)

    def _load_markdown(self, filepath) -> list[XhsPost]:
        """从 Markdown 格式解析博文"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        posts = []
        # 按 --- 分隔多篇博文
        blocks = re.split(r"\n---\n", content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            post = XhsPost(title="", content="", tags=[])

            # 解析标题 (## 标题)
            title_match = re.search(r"^##\s+(.+)$", block, re.MULTILINE)
            if title_match:
                post.title = title_match.group(1).strip()

            # 解析标签 (#标签 或 #标签#)
            tags = re.findall(r"#([^#\s]+)", block)
            post.tags = list(set(tags))

            # 正文：去掉标题行和标签后的内容
            body = re.sub(r"^##\s+.+$", "", block, flags=re.MULTILINE).strip()
            body = re.sub(r"#\w+", "", body).strip()
            post.content = body

            if post.title and post.content:
                posts.append(post)

        return posts

    def export_summary(self, posts=None):
        """导出博文统计摘要"""
        if not posts:
            posts = self.load_all_posts()

        summary = {
            "total_posts": len(posts),
            "avg_title_length": sum(len(p.title) for p in posts) / len(posts) if posts else 0,
            "avg_content_length": sum(len(p.content) for p in posts) / len(posts) if posts else 0,
            "total_tags": sum(len(p.tags) for p in posts),
            "top_tags": self._get_top_tags(posts),
            "posts_by_type": self._count_by_type(posts),
        }
        return summary

    def _get_top_tags(self, posts, n=20):
        from collections import Counter
        tag_counter = Counter()
        for post in posts:
            tag_counter.update(post.tags)
        return dict(tag_counter.most_common(n))

    def _count_by_type(self, posts):
        from collections import Counter
        type_counter = Counter()
        for post in posts:
            if post.content_type:
                type_counter[post.content_type] += 1
        return dict(type_counter)
