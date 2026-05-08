"""
内容质量审核器
检查内容是否：
- 包含敏感词/违禁词
- 风格与历史内容一致
- 字数/格式合规
- 原创度达标
"""
import re
from difflib import SequenceMatcher
from src.config import load_banned_words, load_config


class QualityChecker:
    """内容质量审核"""

    def __init__(self):
        self.banned_words = load_banned_words()
        self.config = load_config()
        self.existing_posts = self._load_existing_posts()

    def _load_existing_posts(self):
        """加载已有博文用于原创度对比"""
        try:
            from src.analyzer.post_parser import PostParser
            parser = PostParser()
            posts = parser.load_all_posts()
            # 只保留有正文的
            return [p for p in posts if p.title or p.content]
        except Exception:
            return []

    def _text_similarity(self, a, b):
        """计算两段文本的相似度 (0-1)"""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _jaccard_similarity(self, a, b):
        """基于字符集合的 Jaccard 相似度，对中文更敏感"""
        if not a or not b:
            return 0.0
        # 取 2-gram 作为特征
        def ngrams(text, n=2):
            text = text.strip()
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        set_a = ngrams(a)
        set_b = ngrams(b)
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.0

    def _check_originality(self, title, content):
        """检查与已有内容的原创度"""
        issues = []
        suggestions = []
        score = 1.0

        if not self.existing_posts:
            return score, issues, suggestions

        max_title_sim = 0.0
        max_content_sim = 0.0
        most_similar_title = ""

        for post in self.existing_posts:
            # 标题相似度
            t_sim = self._text_similarity(title, post.title)
            if t_sim > max_title_sim:
                max_title_sim = t_sim

            # 正文相似度（用 Jaccard，对局部抄袭更敏感）
            c_sim = self._jaccard_similarity(content, post.content)
            if c_sim > max_content_sim:
                max_content_sim = c_sim
                most_similar_title = post.title

        # 标题完全匹配或高相似
        if max_title_sim >= 0.8:
            issues.append(f"标题与已有笔记高度相似（{max_title_sim:.0%}），请修改")
            score -= 0.3
        elif max_title_sim >= 0.6:
            suggestions.append(f"标题与已有笔记较相似（{max_title_sim:.0%}），建议调整角度")
            score -= 0.1

        # 正文相似度
        if max_content_sim >= 0.5:
            issues.append(f"正文与《{most_similar_title[:20]}...》相似度过高（{max_content_sim:.0%}），需大幅改写")
            score -= 0.4
        elif max_content_sim >= 0.35:
            suggestions.append(f"正文与已有内容有重叠（{max_content_sim:.0%}），建议增加新案例或观点")
            score -= 0.15

        return score, issues, suggestions

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

        # 7. 原创度检查（与已有内容对比）
        orig_score, orig_issues, orig_suggestions = self._check_originality(title, content)
        score = max(0, score + orig_score - 1.0)  # orig_score 基准是 1.0
        issues.extend(orig_issues)
        suggestions.extend(orig_suggestions)

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
