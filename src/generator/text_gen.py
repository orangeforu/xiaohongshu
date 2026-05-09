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
- 像闺蜜讲自己的真实经历，不是讲别人的故事
- 开头用一个生活化的瞬间场景抓住人（比如半夜哭醒、看到手机备注、听到厨房的声音）
- 正文用细节和情绪流动让人代入，有画面感、有心跳感
- 严禁理性分析框架：不要写"误区一/二/三"、"核心原因"、"本质"、"机制"
- 不要总结归纳，不要像专家讲课
- 结尾只用一句戳心的话+一个互动提问，不要给"建议123"
""",
            "relationship_tips": """
- 分享自己或身边人的真实经历中悟出的小心得
- 用具体的生活场景带出方法，不要列"第一/第二/第三"
- 每段都要有画面感，让人能看到自己
- 严禁专家口吻：不要写"你要知道"、"研究表明"
- 结尾用一个亲身经历的小收尾+提问，不要总结"以上几点"
""",
            "quotes_opinions": """
- 像深夜闺蜜聊天时突然说出的一句戳心话
- 从一个真实的生活碎片出发，引出那个让你突然想通了的瞬间
- 不要写议论文，不要讲道理
- 300-500字，情绪密度要高
""",
            "hot_topics": """
- 从一个热点事件里找到"这就是我"的情感共鸣点
- 用个人视角聊感受，不是写新闻评论
- 有情绪、有态度、有代入感
""",
        }

        style_context = ""
        if self.style_guide:
            style_context = f"\n参考风格指南:\n{self.style_guide[:1000]}\n"

        profile_context = ""
        if self.profile:
            profile_context = f"\n账号画像: 情感分析/两性关系赛道，像闺蜜一样真实亲切的人设，目标受众18-35岁女性\n"

        prompt = f"""你是拥有百万粉丝的小红书情感博主，也是一位深谙人性的"情感疗愈师"和"AI内容操盘手"。
你结合了陈西西的"流程化爆款能力"与璐璐同学Eva的"用户思维变现逻辑"。
你的文字极具穿透力，擅长捕捉女性用户在恋爱、婚姻、自我成长中的隐秘痛点，能用最温柔的语气说出最清醒的建议。
你深知，做情感号的本质不是"说教"，而是"陪伴"和"唤醒"。

主题: {topic}
内容类型: {content_type}
目标受众: 18-35岁女性，有情感困扰/恋爱关系问题
核心痛点: 在情感中感到委屈、不被理解、害怕失去

平台调性要求（必须严格遵守）:
- 小红书是女性注意力红利场，用户寻求"变得更好"的生活灵感和情感共鸣
- 用户心态是"我被触动了"、"这就是我！"
- 信任来源是：真实感与共鸣。像"闺蜜"一样聊天，素颜出镜、分享个人经历
- 内容强调氛围感和情绪感染力，走心文案
- 每段都要有画面感或情绪点，让人能"看到自己"

【标题设计要求】
从以下角度构思最佳标题（最终只输出一个最佳标题）：
- 情绪宣泄型：直接替用户说出心里话，如"真的，别再为他找借口了！"
- 认知反差型：颠覆常规认知，如"好的感情，其实都需要一点'心狠'"
- 场景代入型：描绘具体扎心场景，如"那个深夜，我删光了他所有的联系方式"
- 人群点名型：精准圈定人群，如"建议所有'讨好型人格'的女生立刻停止内耗"
- 标题中必须包含1-2个Emoji，增强视觉吸引力

【正文结构：情绪三明治】

第一层：痛点共鸣（钩子）
- 不要讲大道理，直接描述一个具体的、扎心的场景或心理活动
- 使用第二人称"你"，让用户觉得"这就是在说我"
- 像闺蜜深夜聊天一样开场

第二层：深度剖析与反转（干货/观点）
- 指出问题的根源（通常是用户的思维误区），给予"当头一棒"的清醒建议
- 提供2-3个具体的心理建设方法或行动指南
- 语言温柔而坚定，避免说教，多用"其实"、"听我说"、"真相是"等连接词
- 去AI化处理：禁止使用"首先、其次、最后"，改用口语化的逻辑连接
- 禁止模棱两可的建议（如"多沟通"），必须给出具体怎么沟通的话术或方法

第三层：治愈与行动（结尾）
- 给予情绪价值，告诉用户"你值得更好的"
- 自然地引导用户互动或领取资料

【风格语气】
- 闺蜜感：像和最好的朋友打电话，语气亲切、自然、带一点点"恨铁不成钢"的急切
- 口语化：多用短句、感叹词（如"天呐"、"真的"、"听劝"）
- 情绪化：适当使用反问句和排比句增强气势

【格式排版】
- 全文多用空行，避免大段文字
- 关键金句、扎心语录要加粗（用**包围），方便用户截图
- 合理使用Emoji（💔, ✨, 🌟, 🛑, 💡）调节阅读节奏，每篇5-10个

【约束条件】
- 严禁理性分析框架：不要出现"误区"、"本质"、"机制"、"逻辑"、"研究表明"等词汇
- 严禁专家口吻：不要出现"你要知道"、"综上所述"、"总而言之"
- 禁止给出模棱两可的建议，必须给出具体的话术或方法
- 必须包含至少一句可以被用户截图发朋友圈的金句（加粗）
- 字数控制在500-700字之间
- 像经历过这些事的"过来人闺蜜"在分享，不是专家在讲课
{type_instructions.get(content_type, "")}
- 不要使用违禁词和敏感词
{style_context}
{profile_context}

请严格按以下JSON格式返回（不要添加其他内容）:
{{
  "title": "标题（含Emoji）",
  "content": "正文内容（遵循情绪三明治结构，多空行，关键句加粗）",
  "tags": ["标签1", "标签2", ...],
  "cover_text": "封面文字",
  "comment_prompt": "评论区互动引导话术（包含变现钩子，如'扣1领资料'）",
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
