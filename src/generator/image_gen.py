"""
封面图生成器
支持两种模式：
- template_only: 用 PIL 生成文字封面（无需 API）
- dall-e: 调用 OpenAI DALL-E 生成
"""
import os
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class ImageGenerator:
    """封面图生成器"""

    # 小红书封面比例 3:4
    WIDTH = 1080
    HEIGHT = 1440

    # 暖色调背景池
    BACKGROUNDS = [
        (245, 230, 233),  # 浅粉
        (253, 246, 227),  # 米白
        (232, 224, 245),  # 浅紫
        (252, 232, 213),  # 暖橙
        (230, 245, 233),  # 薄荷绿
        (245, 238, 230),  # 暖杏
    ]

    # 文字颜色池（与背景搭配的深色系）
    TEXT_COLORS = [
        (80, 50, 55),     # 深褐红
        (60, 60, 70),     # 深灰蓝
        (70, 50, 80),     # 深紫
        (90, 60, 40),     # 深棕
        (50, 70, 60),     # 深绿灰
        (80, 70, 50),     # 深驼
    ]

    def __init__(self):
        self.config = self._load_config()
        self.provider = self.config.get("image", {}).get("provider", "template_only")
        self.font_path = self._find_font()

    def _load_config(self):
        from src.config import load_config
        return load_config()

    def _find_font(self):
        """查找可用的中文字体"""
        candidates = [
            "/c/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/c/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",  # macOS
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def generate_cover(self, title, output_path, content_type="case_story"):
        """
        生成封面图
        Args:
            title: 封面标题
            output_path: 保存路径
            content_type: 内容类型（影响角标风格）
        Returns:
            Path: 生成的图片路径
        """
        if self.provider == "dall-e":
            return self._generate_dalle(title, output_path)
        return self._generate_template(title, output_path, content_type)

    def _generate_template(self, title, output_path, content_type):
        """用 PIL 生成模板封面"""
        import random

        # 随机选择配色
        bg_color = random.choice(self.BACKGROUNDS)
        text_color = random.choice(self.TEXT_COLORS)

        # 创建画布
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = ImageDraw.Draw(img)

        # 画装饰元素（简单的圆角矩形边框）
        margin = 80
        border_color = (
            min(255, text_color[0] + 120),
            min(255, text_color[1] + 120),
            min(255, text_color[2] + 120),
        )
        draw.rounded_rectangle(
            [margin, margin, self.WIDTH - margin, self.HEIGHT - margin],
            radius=40,
            outline=border_color,
            width=4,
        )

        # 角标文字
        corner_labels = {
            "case_story": "真实故事",
            "relationship_tips": "干货必看",
            "quotes_opinions": "扎心真相",
            "hot_topics": "热点解读",
        }
        corner_text = corner_labels.get(content_type, "情感分享")

        # 加载字体
        title_font = self._load_font(size=72)
        corner_font = self._load_font(size=40)
        sub_font = self._load_font(size=32)

        # 绘制角标（左上角）
        corner_x, corner_y = margin + 40, margin + 40
        draw.text((corner_x, corner_y), corner_text, fill=text_color, font=corner_font)

        # 绘制标题（居中，自动换行）
        max_width = self.WIDTH - margin * 2 - 80  # 留边距
        lines = self._wrap_text(title, title_font, max_width, draw)

        # 计算起始 Y 位置（垂直居中偏上）
        line_height = title_font.size + 20
        total_text_height = len(lines) * line_height
        start_y = (self.HEIGHT - total_text_height) // 2 - 50

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_w = bbox[2] - bbox[0]
            x = (self.WIDTH - text_w) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, fill=text_color, font=title_font)

        # 底部小字
        footer = "关注我，了解更多情感真相"
        if sub_font:
            bbox = draw.textbbox((0, 0), footer, font=sub_font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                ((self.WIDTH - text_w) // 2, self.HEIGHT - margin - 60),
                footer,
                fill=text_color,
                font=sub_font,
            )

        # 保存
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        return output_path

    def _load_font(self, size=40):
        """加载字体"""
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _wrap_text(self, text, font, max_width, draw):
        """按宽度自动换行"""
        if not font:
            return textwrap.wrap(text, width=12)

        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_w = bbox[2] - bbox[0]
            if text_w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)

        if not lines:
            lines = [text]
        return lines

    def _generate_dalle(self, title, output_path):
        """调用 DALL-E 生成封面"""
        config = self.config.get("image", {})
        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("未配置 DALL-E API Key，请使用 template_only 模式")

        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = (
            f"Create a Xiaohongshu (Little Red Book) style cover image. "
            f"Theme: {title}. "
            f"Style: warm, soft tones, emotional atmosphere, minimalistic, elegant. "
            f"No text in the image. Aspect ratio 3:4."
        )

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",
            quality="standard",
            n=1,
        )

        import requests
        image_url = response.data[0].url
        r = requests.get(image_url)
        r.raise_for_status()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(r.content)
        return output_path
