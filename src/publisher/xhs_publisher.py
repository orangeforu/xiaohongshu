"""
小红书发布模块
自动将 output/approved/ 中的内容发布到小红书

⚠️ 风险提示：
- 小红书对自动化发布有风控检测，过于频繁可能导致限流或封号
- 建议每天不超过 2 篇，间隔至少 30 分钟
- 首次使用建议加 --dry-run 预览
"""
import json
import sys
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
CREATOR_HOME = "https://creator.xiaohongshu.com/new/home"


class XhsPublisher:
    """小红书发布器"""

    def __init__(self, dry_run=False, daily_limit=2, min_interval_minutes=30):
        self.dry_run = dry_run
        self.daily_limit = daily_limit
        self.min_interval = timedelta(minutes=min_interval_minutes)
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.published_log = self.project_root / "output" / ".published_log.json"
        self.published_log.parent.mkdir(parents=True, exist_ok=True)

    def _load_log(self):
        """加载发布日志"""
        if self.published_log.exists():
            with open(self.published_log, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"entries": []}

    def _save_log(self, log):
        """保存发布日志"""
        with open(self.published_log, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _check_rate_limit(self):
        """检查发布频率限制"""
        log = self._load_log()
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for e in log["entries"] if e.get("date") == today)

        if today_count >= self.daily_limit:
            return False, f"今日已发布 {today_count} 篇，达到上限 {self.daily_limit} 篇"

        if log["entries"]:
            last_time = datetime.fromisoformat(log["entries"][-1]["time"])
            elapsed = datetime.now() - last_time
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                return False, f"距离上次发布仅 {elapsed.seconds // 60} 分钟，需间隔 {self.min_interval.seconds // 60} 分钟，还需等待 {wait.seconds // 60} 分钟"

        return True, "OK"

    def _get_chrome_profile_path(self):
        """查找 Chrome/Edge Profile 路径"""
        localappdata = os.environ.get("LOCALAPPDATA", "")
        for p in [
            os.path.join(localappdata, "Google", "Chrome", "User Data", "Default"),
            os.path.join(localappdata, "Google", "Chrome", "User Data", "Profile 1"),
            os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default"),
        ]:
            if os.path.exists(os.path.join(p, "Preferences")):
                return p
        return None

    def publish_from_dir(self, approved_dir=None):
        """从 approved 目录发布内容"""
        if approved_dir is None:
            approved_dir = self.project_root / "output" / "approved"
        approved_dir = Path(approved_dir)

        if not approved_dir.exists():
            print(f"[ERROR] 目录不存在: {approved_dir}")
            print("请先审核内容并放入 output/approved/ 目录")
            return

        # 获取待发布的文件夹（按创建时间排序）
        folders = [d for d in approved_dir.iterdir() if d.is_dir()]
        folders.sort(key=lambda d: d.stat().st_mtime)

        if not folders:
            print(f"[INFO] {approved_dir} 中没有待发布内容")
            return

        print(f"\n发现 {len(folders)} 篇待发布内容")
        for i, f in enumerate(folders, 1):
            print(f"  {i}. {f.name}")

        # 风控检查
        ok, msg = self._check_rate_limit()
        if not ok:
            print(f"\n[风控拦截] {msg}")
            return

        # 发布第一篇
        target = folders[0]
        self._publish_single(target)

    def _publish_single(self, folder_path):
        """发布单篇笔记"""
        content_path = folder_path / "content.md"
        images_dir = folder_path / "images"

        if not content_path.exists():
            print(f"[ERROR] 缺少 content.md: {folder_path}")
            return

        # 解析内容
        title, body, tags = self._parse_content(content_path)
        if not title or not body:
            print(f"[ERROR] 内容解析失败: {folder_path}")
            return

        # 查找封面图
        cover_image = None
        if images_dir.exists():
            for ext in ["png", "jpg", "jpeg"]:
                candidates = list(images_dir.glob(f"*.{ext}"))
                if candidates:
                    cover_image = candidates[0]
                    break

        print(f"\n{'='*50}")
        print(f"准备发布: {title[:40]}")
        print(f"  正文: {len(body)} 字")
        print(f"  标签: {tags}")
        print(f"  封面: {cover_image.name if cover_image else '无'}")
        print(f"{'='*50}")

        if self.dry_run:
            print("\n[DRY-RUN] 仅预览，未实际发布")
            print("如需发布，去掉 --dry-run 参数")
            return

        # 确认
        confirm = input("\n确认发布? (y/N): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        # 启动浏览器发布
        self._do_publish(title, body, tags, cover_image, folder_path)

    def _parse_content(self, content_path):
        """解析 content.md"""
        with open(content_path, "r", encoding="utf-8") as f:
            text = f.read()

        lines = text.splitlines()
        title = ""
        body_lines = []
        tags = []

        in_body = False
        for line in lines:
            line = line.strip()
            if line.startswith("# ") and not title:
                title = line[2:].strip()
                in_body = True
                continue
            if line.startswith("---"):
                continue
            if line.startswith("标签:") or line.startswith("Tags:"):
                tags = [t.strip() for t in line.split(":", 1)[1].split("#") if t.strip()]
                continue
            if in_body:
                body_lines.append(line)

        # 如果没用 markdown 标题，第一行当标题
        if not title and lines:
            title = lines[0].strip()
            body_lines = lines[1:]

        body = "\n".join(body_lines).strip()

        # 从正文提取 #标签
        if not tags:
            import re
            tags = re.findall(r"#([^#\s]+)", body)

        return title, body, tags

    def _do_publish(self, title, body, tags, cover_image, folder_path):
        """用 Playwright 执行发布"""
        chrome_profile = self._get_chrome_profile_path()
        if not chrome_profile:
            print("[ERROR] 未找到 Chrome/Edge Profile")
            return

        print("\n[1/4] 启动浏览器...")
        with sync_playwright() as pw:
            try:
                context = pw.chromium.launch_persistent_context(
                    chrome_profile,
                    headless=False,
                    viewport={"width": 1440, "height": 900},
                    locale="zh-CN",
                )
            except Exception as e:
                print(f"[ERROR] 启动失败: {e}")
                print("请关闭所有 Chrome/Edge 窗口后重试")
                return

            page = context.pages[0] if context.pages else context.new_page()

            # 检查登录
            print("[2/4] 检查登录...")
            page.goto(CREATOR_HOME, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            if "login" in page.url.lower():
                print("    未登录，请在浏览器窗口中扫码...")
                self._wait_for_login(page)

            # 进入发布页
            print("[3/4] 进入发布页...")
            page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # 上传图片
            if cover_image:
                print("[4/4] 上传图片...")
                try:
                    file_input = page.locator('input[type="file"]').first
                    file_input.set_input_files(str(cover_image))
                    time.sleep(3)
                    print("    图片上传完成")
                except Exception as e:
                    print(f"    [WARN] 图片上传失败: {e}")

            # 填写标题
            print("    填写标题...")
            try:
                title_input = page.locator('input[placeholder*="标题"]').first
                title_input.fill(title)
                time.sleep(1)
            except Exception as e:
                print(f"    [WARN] 标题填写失败: {e}")

            # 填写正文
            print("    填写正文...")
            try:
                # 尝试多种选择器
                for selector in ['[contenteditable="true"]', 'div[role="textbox"]', 'textarea']:
                    editor = page.locator(selector).first
                    if editor.is_visible():
                        editor.fill(body)
                        break
                time.sleep(1)
            except Exception as e:
                print(f"    [WARN] 正文填写失败: {e}")

            # 添加标签（在正文中追加 #标签）
            if tags:
                print(f"    添加标签...")
                try:
                    tag_text = " " + " ".join(f"#{t}" for t in tags)
                    for selector in ['[contenteditable="true"]', 'div[role="textbox"]', 'textarea']:
                        editor = page.locator(selector).first
                        if editor.is_visible():
                            current = editor.input_value() if hasattr(editor, 'input_value') else editor.inner_text()
                            editor.fill(current + tag_text)
                            break
                except Exception as e:
                    print(f"    [WARN] 标签添加失败: {e}")

            print("\n" + "="*50)
            print("  内容已填入发布页，请人工核对后点击发布")
            print("="*50)

            # 记录日志
            log = self._load_log()
            log["entries"].append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().isoformat(),
                "title": title,
                "folder": str(folder_path),
            })
            self._save_log(log)

            # 移动到 published
            published_dir = self.project_root / "output" / "published" / datetime.now().strftime("%Y-%m")
            published_dir.mkdir(parents=True, exist_ok=True)
            target = published_dir / folder_path.name
            folder_path.rename(target)
            print(f"\n  已移动到: {target}")

            context.close()

    def _wait_for_login(self, page, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            remaining = int(timeout - (time.time() - start))
            print(f"    等待登录... (剩余 {remaining//60}分{remaining%60}秒)")
            time.sleep(5)
            if "login" not in page.url.lower():
                print("    [OK] 登录成功！")
                return
        print("    [WARN] 超时")


def run_publisher(dry_run=False):
    publisher = XhsPublisher(dry_run=dry_run)
    publisher.publish_from_dir()
