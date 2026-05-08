"""
选题引擎
基于历史爆款 + 情感赛道模板，自动生成选题列表
"""
import json
import random
from pathlib import Path
from difflib import SequenceMatcher


class TopicEngine:
    """本地选题生成器（无需 LLM）"""

    # 情感赛道核心主题池（从已有爆款 + 行业高频提炼）
    CORE_TOPICS = [
        "冷战", "沟通", "分享欲", "回应", "边界感", "安全感", "信任",
        "恋爱脑", "清醒", "细节", "态度", "仪式感", "浪漫", "前任",
        "放下", "婚前", "婚后", "情绪价值", "吵架", "低头", "认错",
        "原生家庭", "独立", "依赖", "空间", "占有欲", "暧昧", "表白",
        "分手", "复合", "断联", "将就", "合适", "喜欢", "爱",
        "出轨", "忠诚", "陪伴", "倾听", "理解", "包容", "尊重",
        "彩礼", "见家长", "同居", "异地恋", "热恋期", "平淡期",
    ]

    # 选题公式模板
    TEMPLATES = [
        # 数字型
        "{n}个让{topic}越来越{adj}的{action}，第{n2}个最管用",
        "{topic}中最伤感情的{n}种行为，你中了几个？",
        "女生一定要知道的{n}个{topic}真相",
        "{topic}的{n}个细节，暴露了他{result}",
        # 悬念/反转型
        "那个{status}的人，其实{result}",
        "真正{adj}的人，不会在这{n}件事上{action}",
        "你以为{topic}是{wrong}，其实{right}",
        "为什么你总是{problem}？答案藏在你{source}里",
        # 场景型
        "{scene}后我才明白：{insight}",
        "当他{action}的时候，其实{result}",
        "{scene}，是{topic}最好的试金石",
        # 对比型
        "{a} vs {b}，区别在这{n}个细节",
        "{topic}和{topic2}，根本不是一回事",
        # 痛点型
        "结婚{n}年，他用一件事让我彻底{feel}",
        "{topic}的这{n}个瞬间，真的会让人{feel}",
        "那个{status}的女生，后来都怎么样了？",
    ]

    # 填充词库
    WORD_BANK = {
        "n": ["1", "2", "3", "4", "5"],
        "n2": ["1", "2", "3", "4"],
        "adj": ["好", "糟", "甜", "累", "踏实", "不安", "幸福", "绝望"],
        "action": ["沟通", "冷战", "回应", "分享", "陪伴", "低头", "包容", "迁就"],
        "result": ["是不是真的爱你", "有多在乎你", "靠不靠谱", "值不值得嫁",
                   "有没有未来", "心里有没有你", "能不能走到最后"],
        "status": ["从不主动", "很少说爱", "看似冷漠", "总是很忙", "不善言辞",
                   "嘴硬心软", "大大咧咧", "敏感多疑"],
        "wrong": ["不够爱", "不在乎", "变了心", "在敷衍", "想分手"],
        "right": [ "只是在用自己的方式爱你", "比你想象中更在意", "有说不出的压力",
                   "在等待你的回应", "怕打扰你"],
        "problem": ["遇到渣男", "感情不顺", "患得患失", "不被珍惜", "反复吵架"],
        "source": ["原生家庭的这1个细节", "性格里的这个特质", "日常说的这句话",
                   "面对冲突的本能反应", "选择伴侣的底层逻辑"],
        "scene": ["吵完架", "旅行", "生病", "见家长", "同居", "断联一周",
                  "他喝醉后", "你加班到深夜", "过年回家", "谈彩礼"],
        "insight": [ "细节从来不会骗人", "真正爱你的人不会消失",
                     "感情里最怕的不是吵，而是懒得吵",
                     "安全感不是要的，是感受到的",
                     "两个人在一起，舒服比合适更重要"],
        "feel": ["死心", "安心", "破防", "崩溃", "释然", "后悔", "庆幸"],
        "a": ["喜欢你", "暧昧", "对你好", "迁就你", "陪你聊天"],
        "b": ["爱你", "认定你", "给你未来", "把你放心上", "为你改变"],
    }

    def __init__(self, posts_path=None):
        self.posts_path = posts_path or Path(__file__).resolve().parent.parent.parent / "data" / "posts" / "all_posts.json"
        self.existing_titles = []
        self._load_posts()

    def _load_posts(self):
        """加载历史笔记标题"""
        if not self.posts_path.exists():
            return
        with open(self.posts_path, "r", encoding="utf-8") as f:
            posts = json.load(f)
        self.existing_titles = [p.get("title", "") for p in posts if p.get("title")]

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
        """填充模板"""
        result = template
        # 先选两个相关主题
        topic, topic2 = random.sample(self.CORE_TOPICS, 2)
        result = result.replace("{topic}", topic)
        result = result.replace("{topic2}", topic2)

        for key, values in self.WORD_BANK.items():
            if f"{{{key}}}" in result:
                result = result.replace(f"{{{key}}}", random.choice(values), 1)
        return result

    def generate(self, count=30):
        """生成选题列表"""
        topics = []
        attempts = 0
        max_attempts = count * 10

        while len(topics) < count and attempts < max_attempts:
            attempts += 1
            template = random.choice(self.TEMPLATES)
            title = self._fill_template(template)

            # 去重
            if title in topics or self._is_duplicate(title):
                continue

            # 清理多余标点
            title = title.strip("，。！？、")
            if len(title) < 10 or len(title) > 35:
                continue

            topics.append(title)

        return topics

    def generate_from_hot(self, hot_titles, count=10):
        """基于近期热点标题生成衍生选题"""
        derived = []
        for hot in hot_titles[:5]:
            # 提取关键词并替换
            for topic in self.CORE_TOPICS:
                if topic in hot:
                    # 生成几个变体
                    variants = [
                        f"从{hot}看{topic}：真相远比你想的复杂",
                        f"{hot}背后，藏着{n}个{topic}真相",
                        f"{hot}？其实{topic}才是核心",
                    ]
                    for v in variants:
                        v = v.replace("{n}", random.choice(self.WORD_BANK["n"]))
                        if not self._is_duplicate(v) and v not in derived:
                            derived.append(v)
                    break
        return derived[:count]

    def save(self, topics, output_path=None):
        """保存选题到文件"""
        if output_path is None:
            output_path = Path(__file__).resolve().parent.parent.parent / "topics.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            for t in topics:
                f.write(t + "\n")
        return output_path
