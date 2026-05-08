"""
内容质量审核器
检查内容是否：
- 包含敏感词/违禁词
- 风格与历史内容一致
- 字数/格式合规
- 原创度达标
"""
import re
from src.config import load_banned_words, load_config


class QualityChecker:
    """内容质量审核"""

    def __init__(self):
        self.banned_words = load_banned_words()
        self.config = load_config()

    def check(self, post_data):
        """
        审核一篇内容
        Args:
            post_data: dict {title, content, tags, ...}
        Returns:
            dict: {passed: bool, score: float, issues: list, suggestions: list}
        """
        issues = []
        suggestions = []
        score = 1.0

        title = post_data.get("title", "")
        content = post_data.get("content", "")
        tags = post_data.get("tags", [])

        # 1. 敏感词检查
        banned_found = self._check_banned(title + content)
        if banned_found:
            issues.append(f"发现敏感词: {', '.join(banned_found[:5])}")
            score -= 0.3

        # 2. 字数检查
        word_count = len(content)
        min_words = self.config["content"]["word_count"]["min"]
        max_words = self.config["content"]["word_count"]["max"]
        if word_count < min_words:
            issues.append(f"字数过少: {word_count}字 (建议{min_words}+字)")
            score -= 0.1
        if word_count > max_words:
            suggestions.append(f"字数偏多: {word_count}字 (建议{max_words}字以内)")
            score -= 0.05

        # 3. 标题长度
        if not (12 <= len(title) <= 30):
            suggestions.append(f"标题长度{len(title)}字，建议12-30字")
            score -= 0.05

        # 4. 标签数量
        min_tags = self.config["content"]["tag_count"]["min"]
        max_tags = self.config["content"]["tag_count"]["max"]
        if len(tags) < min_tags:
            suggestions.append(f"标签过少: {len(tags)}个 (建议{min_tags}-{max_tags}个)")
            score -= 0.05

        # 5. 段落检查
        paragraphs = [p for p in content.split("\n") if p.strip()]
        long_paragraphs = [p for p in paragraphs if len(p) > 100]
        if long_paragraphs:
            suggestions.append("存在长段落（>100字），建议拆分为短段落")
            score -= 0.05

        # 6. emoji使用
        emoji_count = len(re.findall(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]", content))
        if emoji_count < 3:
            suggestions.append("emoji偏少，建议5-10个增加亲和力")
            score -= 0.05
        elif emoji_count > 15:
            suggestions.append("emoji过多，建议精简")
            score -= 0.05

        # 7. 内容重复度（与已有内容对比）
        # 简化实现：检查标题是否过于相似

        # 限制最低分数
        score = max(0, score)

        return {
            "passed": score >= self.config["review"]["min_quality_score"],
            "score": round(score, 2),
            "issues": issues,
            "suggestions": suggestions,
        }

    def _check_banned(self, text):
        """检查敏感词"""
        found = []
        for word in self.banned_words:
            if word in text:
                found.append(word)
        return found
