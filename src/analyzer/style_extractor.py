"""
风格提取器
从历史博文中提取：
- 语言风格特征
- 标题模式
- 内容结构
- 常用词汇
- 情感倾向
"""
import re
from collections import Counter


class StyleExtractor:
    """从历史博文中提取风格特征"""

    def __init__(self, posts):
        self.posts = posts

    def extract_all(self):
        """提取全部风格特征"""
        return {
            "title_patterns": self._analyze_titles(),
            "content_structure": self._analyze_structure(),
            "vocabulary": self._analyze_vocabulary(),
            "emoji_usage": self._analyze_emoji(),
            "sentiment": self._analyze_sentiment(),
            "length_stats": self._analyze_length(),
            "engagement_patterns": self._analyze_engagement(),
        }

    def _analyze_titles(self):
        """分析标题模式"""
        patterns = {
            "has_number": 0,        # 含数字
            "has_question": 0,      # 含问号
            "has_ellipsis": 0,      # 含省略号
            "has_quote": 0,         # 含引号
            "avg_length": 0,
            "common_words": [],
        }

        titles = [p.title for p in self.posts if p.title]
        if not titles:
            return patterns

        word_counter = Counter()
        for title in titles:
            if re.search(r"\d+", title):
                patterns["has_number"] += 1
            if "？" in title or "?" in title:
                patterns["has_question"] += 1
            if "..." in title or "……" in title:
                patterns["has_ellipsis"] += 1
            if '"' in title or '"' in title or "'" in title:
                patterns["has_quote"] += 1

            # 分词（简单按字分割）
            word_counter.update(list(title))

        patterns["avg_length"] = sum(len(t) for t in titles) / len(titles)
        # 过滤掉停用字，取最高频的词
        stop_chars = set("的了一是在不有就人和我以到了他说她你")
        common = [w for w, _ in word_counter.most_common(50)
                  if w not in stop_chars and len(w.strip()) > 0]
        patterns["common_words"] = common[:20]

        total = len(titles)
        patterns["ratio_number"] = patterns["has_number"] / total
        patterns["ratio_question"] = patterns["has_question"] / total

        return patterns

    def _analyze_structure(self):
        """分析内容结构"""
        structures = {
            "avg_paragraphs": 0,
            "avg_paragraph_length": 0,
            "has_emoji_list": 0,
            "has_numbered_list": 0,
            "avg_emoji_count": 0,
            "common_structures": [],
        }

        contents = [p.content for p in self.posts if p.content]
        if not contents:
            return structures

        total_emoji = 0
        for content in contents:
            paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
            structures["avg_paragraphs"] += len(paragraphs)
            structures["avg_paragraph_length"] += sum(len(p) for p in paragraphs)

            if re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]|1[.、]", content):
                structures["has_numbered_list"] += 1
            if re.search(r"[✅⭐💡👉👇🔥]", content):
                structures["has_emoji_list"] += 1

            emoji_count = len(re.findall(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]", content))
            total_emoji += emoji_count

        n = len(contents)
        structures["avg_paragraphs"] /= n
        structures["avg_paragraph_length"] /= sum(len(c) for c in contents)
        structures["avg_emoji_count"] = total_emoji / n

        return structures

    def _analyze_vocabulary(self):
        """分析常用词汇"""
        all_text = " ".join(p.content for p in self.posts if p.content)
        # 简单按词频统计（中文按字）
        char_counter = Counter(all_text)

        # 过滤常见停用字
        stop_chars = set(" \n\t的了一是在不有就人和我以到了他说她你我了着过能会可以没有这个什么这样那么因为所以但是还是虽然如果已经吧啊呢吗哦")
        result = {char: count for char, count in char_counter.most_common(100)
                  if char not in stop_chars}
        return dict(list(result.items())[:50])

    def _analyze_emoji(self):
        """分析emoji使用模式"""
        emoji_pattern = re.compile(
            r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]"
        )
        emoji_counter = Counter()
        total = 0
        for post in self.posts:
            text = post.content + (post.title or "")
            emojis = emoji_pattern.findall(text)
            emoji_counter.update(emojis)
            total += len(emojis)

        return {
            "total_count": total,
            "avg_per_post": total / len(self.posts) if self.posts else 0,
            "top_emojis": dict(emoji_counter.most_common(15)),
        }

    def _analyze_sentiment(self):
        """分析情感倾向（简化版）"""
        positive_words = ["爱", "喜欢", "幸福", "甜蜜", "开心", "快乐", "温暖", "感动", "美好", "浪漫", "贴心", "温柔", "关心", "在乎"]
        negative_words = ["难过", "伤心", "生气", "失望", "痛苦", "冷漠", "忽视", "伤害", "委屈", "孤独"]
        neutral_words = ["关系", "感情", "相处", "沟通", "理解", "包容", "尊重", "信任", "陪伴"]

        pos_count = 0
        neg_count = 0
        neu_count = 0
        all_text = "".join(p.content for p in self.posts if p.content)

        for word in positive_words:
            pos_count += all_text.count(word)
        for word in negative_words:
            neg_count += all_text.count(word)
        for word in neutral_words:
            neu_count += all_text.count(word)

        total = pos_count + neg_count + neu_count
        return {
            "positive": round(pos_count / total, 2) if total else 0,
            "negative": round(neg_count / total, 2) if total else 0,
            "neutral": round(neu_count / total, 2) if total else 0,
            "tone": "温暖治愈" if (pos_count + neu_count) > neg_count * 2 else "冷静分析",
        }

    def _analyze_length(self):
        """分析内容长度统计"""
        lengths = [len(p.content) for p in self.posts if p.content]
        if not lengths:
            return {"avg": 0, "min": 0, "max": 0}
        return {
            "avg": round(sum(lengths) / len(lengths)),
            "min": min(lengths),
            "max": max(lengths),
        }

    def _analyze_engagement(self):
        """分析互动模式"""
        if not self.posts:
            return {}

        # 找出高互动内容的共同特征
        sorted_posts = sorted(self.posts, key=lambda p: p.total_engagement, reverse=True)
        top_20 = sorted_posts[:max(int(len(sorted_posts) * 0.2), 1)]

        return {
            "avg_engagement_top": sum(p.total_engagement for p in top_20) / len(top_20),
            "avg_engagement_all": sum(p.total_engagement for p in self.posts) / len(self.posts),
            "top_content_features": {
                "common_titles": [p.title for p in top_20[:5]],
                "common_tags": list(set(tag for p in top_20 for tag in p.tags))[:10],
            },
        }
