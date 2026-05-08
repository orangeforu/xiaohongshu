"""
正文生成器
使用 LLM 生成小红书博文正文
"""
import json
from pathlib import Path
from src.config import load_config, get_data_dir


class TextGenerator:
    """AI 文本生成器"""

    def __init__(self, style_guide=None, profile=None):
        self.config = load_config()
        self.style_guide = style_guide
        self.profile = profile

    def generate_post(self, topic, content_type="case_story"):
        """
        生成一篇完整的博文

        Args:
            topic: 选题主题
            content_type: 内容类型 (case_story/relationship_tips/quotes_opinions/hot_topics)

        Returns:
            dict: {title, content, tags, cover_text, comment_prompt}
        """
        prompt = self._build_prompt(topic, content_type)
        response = self._call_llm(prompt)
        return self._parse_response(response)

    def generate_titles(self, topic, n=5):
        """生成多个标题选项"""
        prompt = f"""你是小红书情感赛道爆款标题专家。请为以下主题生成{n}个爆款标题。

主题: {topic}

要求:
1. 使用爆款标题公式（数字型/悬念型/痛点型/对比型/场景型/反常识型）
2. 标题长度15-25字
3. 要能引发情感共鸣和好奇心
4. 不要使用夸张、低俗或引战的表达
5. 适合两性关系/情感分析赛道

直接返回标题列表，每行一个，不要编号。"""
        response = self._call_llm(prompt)
        titles = [t.strip() for t in response.strip().split("\n") if t.strip()]
        return titles[:n]

    def generate_tags(self, topic, title, content, count=12):
        """生成话题标签"""
        prompt = f"""你是小红书话题标签专家。请为以下内容生成{count}个话题标签。

主题: {topic}
标题: {title}
内容摘要: {content[:200]}...

要求:
1. 混合热门标签和精准长尾标签
2. 标签格式: #标签名
3. 围绕两性关系、情感分析、恋爱技巧
4. 包含3-5个高流量热门标签
5. 包含5-8个精准细分标签
6. 包含2-3个场景化标签

直接返回标签列表，每行一个。"""
        response = self._call_llm(prompt)
        tags = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("#"):
                tags.append(line)
            elif line:
                tags.append(f"#{line}")
        return tags[:count]

    def generate_cover_text(self, title, content_type="case_story"):
        """生成封面文字"""
        templates = {
            "case_story": ["真实故事", "读者来信", "情感案例"],
            "relationship_tips": ["干货", "必看", "建议收藏"],
            "quotes_opinions": ["扎心", "真相", "真相了"],
            "hot_topics": ["热点解读", "最新", "刚刚"],
        }
        prefix = templates.get(content_type, [""])[0]
        # 从标题提取核心关键词（前10字左右）
        core = title[:12]
        return f"{prefix}\n{core}" if prefix else core

    def _build_prompt(self, topic, content_type):
        """构建生成prompt"""
        type_instructions = {
            "case_story": """
- 以真实案例故事为主线
- 开头用一个具体场景或对话引入
- 正文讲述案例细节，分析问题本质
- 给出1-3条可操作的建议
- 结尾用共鸣金句 + 互动引导
""",
            "relationship_tips": """
- 以实用技巧/建议为主线
- 开头说明为什么这个话题重要
- 分点列出技巧（3-5点），每点配一个小案例
- 结尾总结 + 鼓励
""",
            "quotes_opinions": """
- 以一个观点/金句为主线
- 短文300-500字
- 以观点为主，辅以简短案例
- 要有反常识/有洞察力的观点
""",
            "hot_topics": """
- 结合热点事件进行情感角度解读
- 简述热点 + 专业分析 + 读者启发
- 要有趣味性和深度
""",
        }

        style_context = ""
        if self.style_guide:
            style_context = f"\n参考风格指南:\n{self.style_guide[:1000]}\n"

        profile_context = ""
        if self.profile:
            profile_context = f"\n账号画像: 情感分析/两性关系赛道，温暖亲切的人设，目标受众18-35岁女性\n"

        prompt = f"""你是小红书情感赛道爆款内容创作者。请根据以下信息生成一篇小红书博文。

主题: {topic}
内容类型: {content_type}

写作要求:
{type_instructions.get(content_type, "")}
- 字数{self.config["content"]["word_count"]["min"]}-{self.config["content"]["word_count"]["max"]}字
- 适当使用emoji，每篇5-10个
- 短段落（2-4行），空行分隔
- 语言温暖亲切，像和闺蜜聊天
- 使用第一人称+第二人称
- 至少包含1-2句可摘抄的金句
- 不要使用违禁词和敏感词
{style_context}
{profile_context}

请严格按以下JSON格式返回（不要添加其他内容）:
{{
  "title": "标题",
  "content": "正文内容",
  "tags": ["标签1", "标签2", ...],
  "cover_text": "封面文字",
  "comment_prompt": "评论区互动引导话术",
  "self_score": 质量自评分(0-1之间的小数)
}}"""
        return prompt

    def _call_llm(self, prompt):
        """调用LLM API"""
        api_key = self.config["llm"].get("api_key", "")
        if not api_key:
            print("[警告] 未配置LLM API Key，返回模拟响应。请在 config/settings.yaml 中配置")
            return self._mock_response(prompt)

        provider = self.config["llm"].get("provider", "claude")
        model = self.config["llm"]["model"]
        max_tokens = self.config["llm"]["max_tokens"]
        temperature = self.config["llm"]["temperature"]

        if provider == "openai":
            from openai import OpenAI
            kwargs = {}
            base_url = self.config["llm"].get("base_url", "")
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(api_key=api_key, **kwargs)
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

    def _parse_response(self, response):
        """解析LLM响应"""
        # 尝试提取JSON
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(response[start:end])
                return data
            except json.JSONDecodeError:
                pass

        # 解析失败，返回原始文本
        return {
            "title": "AI 生成内容",
            "content": response,
            "tags": ["#情感", "#两性关系"],
            "cover_text": "",
            "comment_prompt": "你有什么想说的？",
        }

    def _mock_response(self, prompt):
        """模拟响应（无API key时使用）"""
        return json.dumps({
            "title": "请先配置LLM API Key",
            "content": "请在 config/settings.yaml 中配置 Claude API Key，或设置环境变量 ANTHROPIC_API_KEY。配置完成后即可开始生成内容。",
            "tags": ["#AI创作", "#配置指南"],
            "cover_text": "配置指南",
            "comment_prompt": "有问题欢迎交流~",
            "self_score": 0.5,
        }, ensure_ascii=False)
