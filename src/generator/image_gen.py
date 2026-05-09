"""
封面图生成器
支持三种模式：
- template_only: 用 PIL 生成精美文字封面（默认，无需 API）
- pollinations: AI 生成氛围背景 + PIL 文字叠加（免费，无需 API Key）
- dall-e: 调用 OpenAI DALL-E 生成（需配置 API Key）
"""
import os
import textwrap
import urllib.request
import urllib.parse
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
        if self.provider == "pollinations":
            return self._generate_pollinations(title, output_path, content_type)
        return self._generate_template(title, output_path, content_type)

    @staticmethod
    def _remove_emoji(text):
        """移除字符串中的 Emoji 字符（中文字体通常不支持）"""
        import re
        # 精确匹配已知 Emoji 范围，避免误删中文字符
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"   # 表情符号
            "\U0001F300-\U0001F5FF"   # 符号和象形文字
            "\U0001F680-\U0001F6FF"   # 交通和地图符号
            "\U0001F1E0-\U0001F1FF"   # 国旗
            "\U00002600-\U000026FF"   # 杂项符号
            "\U00002700-\U000027BF"   # 装饰符号
            "\U0001F900-\U0001F9FF"   # 补充符号
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U0000FE00-\U0000FE0F"   # 变体选择器
            "\U0001F3FB-\U0001F3FF"   # 肤色修饰符
            "]+",
            flags=re.UNICODE,
        )
        return emoji_pattern.sub("", text)

    def _generate_template(self, title, output_path, content_type):
        """用 PIL 生成精美模板封面"""
        import random

        # 过滤标题中的 Emoji，避免显示为方框
        title = self._remove_emoji(title)

        # ---- 配色方案（每套包含渐变起点/终点、文字色、强调色） ----
        palettes = [
            {  # 温柔粉
                "bg_start": (255, 228, 235),
                "bg_end": (252, 240, 245),
                "text": (120, 50, 70),
                "accent": (220, 120, 150),
                "card": (255, 255, 255),
            },
            {  # 奶油杏
                "bg_start": (255, 240, 220),
                "bg_end": (252, 248, 240),
                "text": (110, 80, 55),
                "accent": (220, 160, 100),
                "card": (255, 255, 255),
            },
            {  # 薰衣草紫
                "bg_start": (235, 225, 250),
                "bg_end": (245, 240, 255),
                "text": (90, 60, 110),
                "accent": (160, 120, 200),
                "card": (255, 255, 255),
            },
            {  # 薄荷绿
                "bg_start": (220, 245, 235),
                "bg_end": (235, 250, 245),
                "text": (50, 90, 80),
                "accent": (100, 180, 150),
                "card": (255, 255, 255),
            },
            {  # 暖雾蓝
                "bg_start": (225, 235, 250),
                "bg_end": (240, 245, 252),
                "text": (50, 70, 100),
                "accent": (100, 140, 200),
                "card": (255, 255, 255),
            },
            {  # 落日橘
                "bg_start": (255, 230, 210),
                "bg_end": (255, 245, 235),
                "text": (130, 70, 40),
                "accent": (230, 130, 80),
                "card": (255, 255, 255),
            },
        ]
        p = random.choice(palettes)

        # ---- 创建渐变背景 ----
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), p["bg_start"])
        self._draw_gradient(img, p["bg_start"], p["bg_end"])
        draw = ImageDraw.Draw(img)

        # ---- 装饰几何元素（随机小圆点） ----
        random.seed(title)  # 同标题每次装饰一致
        for _ in range(25):
            x = random.randint(0, self.WIDTH)
            y = random.randint(0, self.HEIGHT)
            r = random.randint(2, 6)
            alpha = random.randint(30, 80)
            color = self._with_alpha(p["accent"], alpha)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

        # ---- 顶部装饰色条 ----
        bar_height = 12
        draw.rectangle([0, 0, self.WIDTH, bar_height], fill=p["accent"])

        # ---- 白色内容卡片（带柔和阴影感） ----
        margin = 90
        card_margin = margin + 20
        card_radius = 50
        # 先画一层淡淡的"阴影"
        shadow_offset = 6
        shadow_color = (230, 230, 230)
        draw.rounded_rectangle(
            [card_margin + shadow_offset, card_margin + shadow_offset,
             self.WIDTH - card_margin + shadow_offset, self.HEIGHT - card_margin + shadow_offset],
            radius=card_radius,
            fill=shadow_color,
        )
        # 再画白色卡片
        draw.rounded_rectangle(
            [card_margin, card_margin,
             self.WIDTH - card_margin, self.HEIGHT - card_margin],
            radius=card_radius,
            fill=p["card"],
        )
        # 卡片内边框线
        inner_margin = card_margin + 10
        draw.rounded_rectangle(
            [inner_margin, inner_margin,
             self.WIDTH - inner_margin, self.HEIGHT - inner_margin],
            radius=card_radius - 10,
            outline=(245, 245, 245),
            width=2,
        )

        # ---- 角标标签（圆角反色标签） ----
        corner_labels = {
            "case_story": "真实故事",
            "relationship_tips": "干货必看",
            "quotes_opinions": "扎心真相",
            "hot_topics": "热点解读",
        }
        corner_text = corner_labels.get(content_type, "情感分享")

        # 加载字体
        title_font = self._load_font(size=80)
        corner_font = self._load_font(size=36)
        sub_font = self._load_font(size=30)
        quote_font = self._load_font(size=120)

        # 画角标标签背景
        tag_padding_x, tag_padding_y = 24, 12
        tag_bbox = draw.textbbox((0, 0), corner_text, font=corner_font)
        tag_w = tag_bbox[2] - tag_bbox[0] + tag_padding_x * 2
        tag_h = tag_bbox[3] - tag_bbox[1] + tag_padding_y * 2
        tag_x = card_margin + 50
        tag_y = card_margin + 50
        draw.rounded_rectangle(
            [tag_x, tag_y, tag_x + tag_w, tag_y + tag_h],
            radius=tag_h // 2,
            fill=p["accent"],
        )
        draw.text(
            (tag_x + tag_padding_x, tag_y + tag_padding_y - 2),
            corner_text,
            fill=(255, 255, 255),
            font=corner_font,
        )

        # ---- 大引号装饰（半透明，作为背景氛围） ----
        if quote_font:
            quote_color = self._with_alpha(p["accent"], 25)
            draw.text((card_margin + 40, card_margin + 120), "“", fill=quote_color, font=quote_font)

        # ---- 绘制标题（居中，自动换行，带阴影） ----
        max_width = self.WIDTH - card_margin * 2 - 100
        lines = self._wrap_text(title, title_font, max_width, draw)

        line_height = title_font.size + 24
        total_text_height = len(lines) * line_height
        start_y = (self.HEIGHT - total_text_height) // 2 - 20

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_w = bbox[2] - bbox[0]
            x = (self.WIDTH - text_w) // 2
            y = start_y + i * line_height

            # 文字阴影（偏移2px，更柔和）
            shadow_rgb = (
                max(0, p["text"][0] - 80),
                max(0, p["text"][1] - 80),
                max(0, p["text"][2] - 80),
            )
            draw.text((x + 2, y + 2), line, fill=shadow_rgb, font=title_font)
            # 主文字
            draw.text((x, y), line, fill=p["text"], font=title_font)

        # ---- 标题下方装饰线 + 小字 ----
        line_y = start_y + len(lines) * line_height + 40
        line_width = 120
        line_x = (self.WIDTH - line_width) // 2
        draw.line([(line_x, line_y), (line_x + line_width, line_y)], fill=p["accent"], width=3)

        sub_text = "百万粉丝情感博主 | 深夜陪伴"
        if sub_font:
            bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                ((self.WIDTH - text_w) // 2, line_y + 20),
                sub_text,
                fill=(160, 160, 160),
                font=sub_font,
            )

        # ---- 底部小字（反色条带） ----
        footer = "关注我，了解更多情感真相"
        if sub_font:
            footer_bbox = draw.textbbox((0, 0), footer, font=sub_font)
            footer_w = footer_bbox[2] - footer_bbox[0]
            footer_x = (self.WIDTH - footer_w) // 2
            footer_y = self.HEIGHT - card_margin - 70
            draw.text((footer_x, footer_y), footer, fill=(150, 150, 150), font=sub_font)

        # ---- 底部装饰色条 ----
        draw.rectangle([0, self.HEIGHT - bar_height, self.WIDTH, self.HEIGHT], fill=p["accent"])

        # ---- 保存 ----
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", quality=95)
        return output_path

    def _generate_pollinations(self, title, output_path, content_type):
        """Pollinations.ai 生成氛围背景 + PIL 文字叠加"""
        import random

        title_clean = self._remove_emoji(title)

        # 构建英文 prompt（Pollinations 对英文提示词理解更好）
        style_prompts = [
            "soft warm pastel pink background, elegant bokeh lights, abstract floral elements, dreamy romantic atmosphere, no text",
            "warm cream and lavender watercolor texture, soft glowing light, minimal aesthetic, cozy emotional feeling, no text",
            "soft mint green and peach gradient, delicate sparkles, minimal Japanese aesthetic, warm sunlight, emotional healing vibe, no text",
            "warm sunset orange and coral gradient, soft clouds, dreamy bokeh, romantic atmosphere, minimalist feminine design, no text",
            "soft rose gold and blush pink, abstract soft brush strokes, gentle light leaks, feminine elegant mood, no text",
            "pale lilac and warm white gradient, soft petals floating, ethereal dreamy atmosphere, minimal clean design, no text",
        ]
        prompt = random.choice(style_prompts)

        # 下载背景图
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={self.WIDTH}&height={self.HEIGHT}&seed={hash(title) % 10000}&nologo=true"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                bg_img = Image.open(resp).convert("RGB")
        except Exception as e:
            # 网络失败时 fallback 到 PIL 模板
            print(f"[警告] Pollinations 下载失败 ({e})，fallback 到 PIL 模板")
            return self._generate_template(title, output_path, content_type)

        # 确保尺寸正确
        bg_img = bg_img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(bg_img)

        # 加载字体
        title_font = self._load_font(size=88)
        tag_font = self._load_font(size=36)
        sub_font = self._load_font(size=30)

        # 标签（左上角深色圆角标签）
        corner_labels = {
            "case_story": "真实故事",
            "relationship_tips": "干货必看",
            "quotes_opinions": "扎心真相",
            "hot_topics": "热点解读",
        }
        tag = corner_labels.get(content_type, "情感分享")
        tb = draw.textbbox((0, 0), tag, font=tag_font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        pad_x, pad_y = 22, 10
        draw.rounded_rectangle(
            [60, 60, 60 + tw + pad_x * 2, 60 + th + pad_y * 2],
            radius=30,
            fill=(30, 30, 30, 200),
        )
        draw.text((60 + pad_x, 60 + pad_y - 2), tag, fill=(255, 255, 255), font=tag_font)

        # 标题换行
        max_w = self.WIDTH - 120
        lines = self._wrap_text(title_clean, title_font, max_w, draw)
        lh = title_font.size + 20
        tht = len(lines) * lh
        sy = (self.HEIGHT - tht) // 2 + 20

        for i, line in enumerate(lines):
            b = draw.textbbox((0, 0), line, font=title_font)
            tw = b[2] - b[0]
            x = (self.WIDTH - tw) // 2
            y = sy + i * lh
            self._draw_text_with_outline(draw, (x, y), line, title_font, fill=(40, 40, 40), outline_fill=(255, 255, 255), outline_width=4)

        # 底部小字
        sub = "百万粉丝情感博主 | 深夜陪伴"
        if sub_font:
            b = draw.textbbox((0, 0), sub, font=sub_font)
            tw = b[2] - b[0]
            self._draw_text_with_outline(draw, ((self.WIDTH - tw) // 2, self.HEIGHT - 120), sub, sub_font, fill=(60, 60, 60), outline_fill=(255, 255, 255), outline_width=2)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bg_img.save(output_path, "PNG", quality=95)
        return output_path

    @staticmethod
    def _draw_text_with_outline(draw, pos, text, font, fill, outline_fill, outline_width=3):
        """绘制带描边的文字"""
        x, y = pos
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_fill)
        draw.text((x, y), text, font=font, fill=fill)

    def _draw_gradient(self, img, color_start, color_end):
        """从上到下画线性渐变"""
        width, height = img.size
        pixels = img.load()
        for y in range(height):
            ratio = y / height
            r = int(color_start[0] + (color_end[0] - color_start[0]) * ratio)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * ratio)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
            for x in range(width):
                pixels[x, y] = (r, g, b)

    def _with_alpha(self, rgb, alpha):
        """RGB + alpha 转 RGBA 元组（用于直接绘制时混合到白底）"""
        # 简单 alpha 混合到白色背景
        r = int(rgb[0] * alpha / 255 + 255 * (1 - alpha / 255))
        g = int(rgb[1] * alpha / 255 + 255 * (1 - alpha / 255))
        b = int(rgb[2] * alpha / 255 + 255 * (1 - alpha / 255))
        return (r, g, b)

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
