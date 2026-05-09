"""
选题引擎
支持两种模式：
- fast: 本地模板生成（无需 LLM API）
- smart: LLM 驱动，结合历史爆款分析 + 风格指南

输出结构化选题，包含标题、内容类型、核心角度、故事引入点、目标痛点。
"""
import json
import random
from pathlib import Path
from difflib import SequenceMatcher
from src.config import load_config


class TopicEngine:
    """智能选题引擎"""

    # 情感赛道核心主题池（基于历史爆款数据优化）
    CORE_TOPICS = [
        # 高互动主题（优先）
        "旅行", "人品", "情绪价值", "分享欲", "恋爱脑", "分手", "失恋",
        "冷战", "沟通", "回应", "边界感", "安全感", "信任",
        # 常规主题
        "仪式感", "浪漫", "前任", "放下", "婚前", "婚后",
        "原生家庭", "独立", "依赖", "空间", "占有欲", "暧昧", "表白",
        "复合", "断联", "将就", "合适", "喜欢", "爱",
        "出轨", "忠诚", "陪伴", "倾听", "理解", "包容", "尊重",
        "彩礼", "见家长", "同居", "异地恋", "热恋期", "平淡期",
        "吵架", "低头", "认错",
    ]

    # 故事驱动型标题模板（按内容类型分组）
    TEMPLATES = {
        "case_story": [
            "闺蜜{action}后我才明白：{insight}",
            "那个{status}的人，后来都怎么样了？",
            "恋爱{time}，他用一件事让我彻底{feel}",
            "结婚{time}，{scene}让我彻底{feel}",
            "那个从不说'{word}'的人，其实最{result}",
            "她{action}后我才懂：{insight}",
            "恋爱{time}，{scene}是{topic}最好的试金石",
            "他{action}的那一刻，我才看清{topic}的真相",
        ],
        "relationship_tips": [
            "女生一定要知道的{n}个{topic}真相",
            "{topic}的{n}个细节，暴露了他{result}",
            "真正{adj}的人，不会在这{n}件事上{action}",
            "为什么你总是{problem}？答案藏在你{source}里",
            "{a} vs {b}，区别在这{n}个细节",
            "你以为{topic}是{wrong}，其实{right}",
            "聪明的女生，{scene}都会注意这{n}个{topic}细节",
        ],
        "quotes_opinions": [
            "好的{topic}，不是不{action}",
            "后来才发现：{insight}",
            "最{adj}的{topic}，往往藏在{scene}里",
            "关于{topic}，没人告诉你的{adj}真相",
            "不是所有{topic}，都值得你{action}",
        ],
        "hot_topics": [
            "从{hot_event}看{topic}：真相远比你想的复杂",
            "{hot_event}背后，藏着{n}个{topic}真相",
            "{hot_event}？其实{topic}才是核心",
            "为什么{hot_event}会引发这么多{topic}讨论？",
        ],
    }

    # 填充词库
    WORD_BANK = {
        "n": ["1", "2", "3", "4", "5"],
        "n2": ["1", "2", "3", "4"],
        "time": ["1个月", "3个月", "半年", "1年", "3年", "5年", "7年"],
        "adj": ["好", "糟", "甜", "累", "踏实", "不安", "幸福", "绝望", "清醒", "成熟"],
        "action": ["沟通", "冷战", "回应", "分享", "陪伴", "低头", "包容", "迁就", "吵架", "道歉"],
        "result": ["是不是真的爱你", "有多在乎你", "靠不靠谱", "值不值得嫁",
                   "有没有未来", "心里有没有你", "能不能走到最后", "是不是对的人"],
        "status": ["从不主动", "很少说爱", "看似冷漠", "总是很忙", "不善言辞",
                   "嘴硬心软", "大大咧咧", "敏感多疑", "一直迁就你", "从不道歉"],
        "wrong": ["不够爱", "不在乎", "变了心", "在敷衍", "想分手", "没时间", "性格不合"],
        "right": ["只是在用自己的方式爱你", "比你想象中更在意", "有说不出的压力",
                  "在等待你的回应", "怕打扰你", "已经在用行动证明", "只是不擅长表达"],
        "problem": ["遇到渣男", "感情不顺", "患得患失", "不被珍惜", "反复吵架", "越来越淡"],
        "source": ["原生家庭的这1个细节", "性格里的这个特质", "日常说的这句话",
                   "面对冲突的本能反应", "选择伴侣的底层逻辑", "他喝醉后的样子"],
        "scene": ["吵完架", "旅行", "生病", "见家长", "同居", "断联一周",
                  "他喝醉后", "你加班到深夜", "过年回家", "谈彩礼", "他失业后",
                  "你委屈的时候", "他遇到困难", "一起经历大事"],
        "insight": ["细节从来不会骗人", "真正爱你的人不会消失",
                    "感情里最怕的不是吵，而是懒得吵",
                    "安全感不是要的，是感受到的",
                    "两个人在一起，舒服比合适更重要",
                    "爱不是说出来，是做出来的",
                    "能低头的人，才是真正想走下去的人"],
        "feel": ["死心", "安心", "破防", "崩溃", "释然", "后悔", "庆幸", "清醒", "后悔没早点知道"],
        "a": ["喜欢你", "暧昧", "对你好", "迁就你", "陪你聊天"],
        "b": ["爱你", "认定你", "给你未来", "把你放心上", "为你改变"],
        "word": ["我爱你", "对不起", "晚安", "想你了", "辛苦了"],
        "hot_event": ["某明星分手", "某综艺情侣", "热门情感话题", "社会新闻"],
    }

    # 内容类型配比
    TYPE_RATIO = {
        "case_story": 0.40,
        "relationship_tips": 0.30,
        "quotes_opinions": 0.15,
        "hot_topics": 0.15,
    }

    def __init__(self, posts_path=None):
        self.config = load_config()
        self.posts_path = posts_path or Path(__file__).resolve().parent.parent.parent / "data" / "posts" / "all_posts.json"
        self.profile_path = Path(__file__).resolve().parent.parent.parent / "data" / "analytics" / "profile.json"
        self.style_guide_path = Path(__file__).resolve().parent.parent.parent / "config" / "style_guide.md"
        self.existing_titles = []
        self._load_posts()

    def _load_posts(self):
        """加载历史笔记标题"""
        if not self.posts_path.exists():
            return
        with open(self.posts_path, "r", encoding="utf-8") as f:
            posts = json.load(f)
        self.existing_titles = [p.get("title", "") for p in posts if p.get("title")]

    def analyze_historical_performance(self):
        """分析历史爆款数据，返回洞察报告"""
        if not self.posts_path.exists():
            return {
                "total_posts": 0,
                "posts_with_data": 0,
                "top_posts": [],
                "top_themes": [],
                "insights": ["暂无历史数据，将使用默认主题库生成选题"],
            }

        with open(self.posts_path, "r", encoding="utf-8") as f:
            posts = json.load(f)

        posts_with_views = [p for p in posts if p.get("views", 0) > 0]
        posts_sorted = sorted(posts_with_views, key=lambda p: p.get("views", 0), reverse=True)

        top_posts = []
        for p in posts_sorted[:10]:
            top_posts.append({
                "title": p.get("title", ""),
                "views": p.get("views", 0),
                "favorites": p.get("favorites", 0),
            })

        # 从标题中提取出现过的主题词
        all_titles_text = " ".join(p.get("title", "") for p in posts)
        matched_themes = [t for t in self.CORE_TOPICS if t in all_titles_text]

        # 爆款洞察
        insights = []
        if posts_with_views:
            avg_top = sum(p.get("views", 0) for p in posts_sorted[:5]) / min(5, len(posts_sorted))
            avg_all = sum(p.get("views", 0) for p in posts_with_views) / len(posts_with_views)
            if avg_all > 0:
                insights.append(f"头部内容平均浏览量是整体的 {avg_top / avg_all:.1f} 倍")

        if matched_themes:
            insights.append(f"历史标题高频主题: {', '.join(matched_themes[:8])}")

        insights.append("爆款多集中在旅行/人品/情绪价值/恋爱脑等故事型主题")
        insights.append("问答式、悬念式标题互动率高于陈述式")

        return {
            "total_posts": len(posts),
            "posts_with_data": len(posts_with_views),
            "top_posts": top_posts,
            "top_themes": list(set(matched_themes)),
            "insights": insights,
        }

    def _similarity(self, a, b):
        """计算两个标题的相似度"""
        return SequenceMatcher(None, a, b).ratio()

    def _is_duplicate(self, title, threshold=0.65):
        """检查是否与已有标题过于相似"""
        for existing in self.existing_titles:
            if self._similarity(title, existing) >= threshold:
                return True
        return False

    def _fill_template(self, template):
        """填充模板中的占位符"""
        result = template
        topic = random.choice(self.CORE_TOPICS)
        topic2 = random.choice([t for t in self.CORE_TOPICS if t != topic])
        result = result.replace("{topic}", topic)
        result = result.replace("{topic2}", topic2)

        for key, values in self.WORD_BANK.items():
            while f"{{{key}}}" in result:
                result = result.replace(f"{{{key}}}", random.choice(values), 1)

        return result

    def generate(self, count=30, mode="fast", content_type=None):
        """
        生成选题列表
        Args:
            count: 生成数量
            mode: "fast"(模板模式) 或 "smart"(LLM驱动)
            content_type: 指定类型(case_story/relationship_tips/quotes_opinions/hot_topics)，None则按配比生成
        """
        if mode == "smart":
            return self._generate_smart(count, content_type)
        return self._generate_fast(count, content_type)

    def _generate_fast(self, count, content_type=None):
        """快速模板模式（无需API）"""
        topics = []
        attempts = 0
        max_attempts = count * 30

        # 确定各类型数量
        if content_type:
            type_counts = {content_type: count}
        else:
            type_counts = {}
            remaining = count
            for t, ratio in self.TYPE_RATIO.items():
                c = int(count * ratio)
                type_counts[t] = c
                remaining -= c
            if remaining > 0:
                max_type = max(self.TYPE_RATIO, key=self.TYPE_RATIO.get)
                type_counts[max_type] += remaining

        for t, c in type_counts.items():
            templates = self.TEMPLATES.get(t, self.TEMPLATES["case_story"])
            generated = 0
            while generated < c and attempts < max_attempts:
                attempts += 1
                template = random.choice(templates)
                title = self._fill_template(template)

                if title in [tp["title"] for tp in topics] or self._is_duplicate(title):
                    continue

                title = title.strip("，。！？、")
                if len(title) < 10 or len(title) > 35:
                    continue

                topics.append({
                    "title": title,
                    "content_type": t,
                    "core_angle": "",
                    "story_hook": "",
                    "target_pain_point": "",
                })
                generated += 1

        random.shuffle(topics)
        return topics

    def _generate_smart(self, count, content_type=None):
        """LLM 智能选题模式（结合爆款分析）"""
        analysis = self.analyze_historical_performance()

        style_guide = ""
        if self.style_guide_path.exists():
            style_guide = self.style_guide_path.read_text(encoding="utf-8")[:1500]

        type_instruction = ""
        if content_type:
            type_instruction = f"所有选题必须是 {content_type} 类型。"
        else:
            type_instruction = (
                "按以下配比生成：case_story(案例故事) 40%, "
                "relationship_tips(关系技巧) 30%, quotes_opinions(观点金句) 15%, "
                "hot_topics(热点话题) 15%。"
            )

        prompt = f"""你是小红书情感赛道的内容策略专家，擅长基于数据洞察生成高互动选题。

## 历史爆款分析
{json.dumps(analysis, ensure_ascii=False, indent=2)}

## 风格指南
{style_guide}

## 任务
请生成 {count} 个小红书情感赛道选题。

要求：
1. {type_instruction}
2. 每个选题必须是故事驱动型，能用具体案例或场景引入（避免教科书式清单体）
3. 标题要引发情感共鸣和好奇心，适合18-35岁女性
4. 标题长度12-25字
5. 避免与已有标题过于相似
6. 每条选题需包含以下字段：
   - title: 标题
   - content_type: 内容类型
   - core_angle: 核心切入角度（1句话）
   - story_hook: 故事引入点（如"闺蜜谈3年男友不提结婚"）
   - target_pain_point: 目标读者痛点

## 输出格式
请严格按以下JSON数组格式返回，不要添加其他内容：
[
  {{
    "title": "...",
    "content_type": "case_story",
    "core_angle": "...",
    "story_hook": "...",
    "target_pain_point": "..."
  }},
  ...
]"""

        response = self._call_llm(prompt)
        topics = self._parse_llm_response(response)

        # 去重
        unique = []
        seen = set()
        for t in topics:
            title = t.get("title", "")
            if not title or title in seen or self._is_duplicate(title):
                continue
            seen.add(title)
            unique.append(t)

        # LLM 生成不足时，用模板模式补充
        if len(unique) < count:
            needed = count - len(unique)
            fast_topics = self._generate_fast(needed, content_type)
            for ft in fast_topics:
                if ft["title"] not in seen and not self._is_duplicate(ft["title"]):
                    seen.add(ft["title"])
                    unique.append(ft)
                    if len(unique) >= count:
                        break

        return unique[:count]

    def _call_llm(self, prompt):
        """调用LLM API"""
        api_key = self.config["llm"].get("api_key", "")
        if not api_key:
            print("[警告] 未配置LLM API Key，降级为模板模式")
            return "[]"

        provider = self.config["llm"].get("provider", "claude")
        model = self.config["llm"]["model"]
        max_tokens = self.config["llm"]["max_tokens"]
        temperature = self.config["llm"]["temperature"]

        try:
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
        except Exception as e:
            print(f"[错误] LLM调用失败: {e}")
            return "[]"

    def _parse_llm_response(self, response):
        """解析LLM返回的JSON数组"""
        start = response.find("[")
        end = response.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return []

    def save(self, topics, output_path=None):
        """
        保存选题到文件
        同时输出 JSON（结构化数据）和 TXT（人类可读）
        """
        if output_path is None:
            output_path = Path(__file__).resolve().parent.parent.parent / "topics.json"

        output_path = Path(output_path)
        json_path = output_path if str(output_path).endswith(".json") else output_path.with_suffix(".json")
        txt_path = json_path.with_suffix(".txt")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)

        with open(txt_path, "w", encoding="utf-8") as f:
            for i, t in enumerate(topics, 1):
                f.write(f"{i}. {t.get('title', '')}\n")
                if t.get("core_angle"):
                    f.write(f"   角度: {t['core_angle']}\n")
                if t.get("story_hook"):
                    f.write(f"   引入: {t['story_hook']}\n")
                if t.get("target_pain_point"):
                    f.write(f"   痛点: {t['target_pain_point']}\n")
                f.write(f"   类型: {t.get('content_type', '')}\n")
                f.write("\n")

        return json_path
