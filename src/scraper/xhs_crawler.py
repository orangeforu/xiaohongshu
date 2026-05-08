"""
小红书创作者后台 - 数据采集

方案：先设置 API 响应拦截器，然后导航到笔记管理页，
拦截自动触发的 creator/note/user/posted API 响应。
"""
import json
import re
import sys
import time
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')


CREATOR_HOME = "https://creator.xiaohongshu.com/new/home"
CREATOR_NOTES = "https://creator.xiaohongshu.com/new/note-manager"
NOTE_LIST_API = "creator/note/user/posted"


def _get_chrome_profile_path():
    localappdata = os.environ.get("LOCALAPPDATA", "")
    for p in [
        os.path.join(localappdata, "Google", "Chrome", "User Data", "Default"),
        os.path.join(localappdata, "Google", "Chrome", "User Data", "Profile 1"),
        os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default"),
    ]:
        if os.path.exists(os.path.join(p, "Preferences")):
            return p
    return None


def run_collector(max_posts=100):
    project_root = Path(__file__).resolve().parent.parent
    posts_dir = project_root / "data" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  小红书创作者后台 - 数据采集")
    print("=" * 60)

    chrome_profile = _get_chrome_profile_path()
    if not chrome_profile:
        print("\n[ERROR] 未找到 Chrome/Edge Profile")
        return

    print(f"\n[1/3] 启动浏览器")

    with sync_playwright() as pw:
        try:
            context = pw.chromium.launch_persistent_context(
                chrome_profile,
                headless=False,
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
            )
        except Exception as e:
            print(f"\n[ERROR] 启动失败: {e}")
            print("请关闭所有 Chrome/Edge 窗口后重试")
            return

        page = context.pages[0] if context.pages else context.new_page()

        # 登录检查
        print("[2/3] 检查登录...")
        page.goto(CREATOR_HOME, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        if "login" in page.url.lower():
            print("    未登录，请在浏览器窗口中扫码...")
            _wait_for_login(page)

        # 采集笔记列表
        print("\n[3/3] 采集笔记数据...")

        # 创建新页面，确保拦截器干净
        page2 = context.new_page()

        # 先设置拦截器，再导航
        api_responses = []

        def on_response(response):
            if NOTE_LIST_API in response.url:
                try:
                    data = response.json()
                    api_responses.append(data)
                    print(f"    [拦截] {response.url.split('?')[0]}")
                except:
                    pass

        page2.on("response", on_response)

        # 导航触发 API 请求
        print("    正在导航到笔记管理页...")
        page2.goto(CREATOR_NOTES, wait_until="networkidle", timeout=30000)
        time.sleep(5)

        # 滚动触发懒加载
        print("    滚动加载更多数据...")
        for i in range(5):
            page2.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

        time.sleep(3)

        all_notes = []
        if api_responses:
            print(f"    共拦截到 {len(api_responses)} 个 API 响应")
            all_notes = _parse_notes_from_responses(api_responses)

        if not all_notes:
            print("    未拦截到 API 数据，尝试 JS fetch...")
            all_notes = _fetch_via_js_fetch(page2)

        if not all_notes:
            print("\n[ERROR] 获取失败")
            context.close()
            return

        print(f"\n    [OK] 获取到 {len(all_notes)} 篇笔记")
        for i, n in enumerate(all_notes):
            print(f"      {i+1}. [{n['note_id'][:10]}...] {n['title'][:40]} "
                  f"(浏览:{n['views']}, 赞:{n['likes']}, 藏:{n['favorites']})")

        # 获取正文和标签
        print(f"\n    正在获取笔记正文和标签...")
        all_notes = _fetch_content_from_editor(page2, all_notes, max_posts)

        # 保存
        print(f"\n    [保存] 写入 {posts_dir} ...")
        _save_posts(all_notes, posts_dir)
        context.close()

    print("\n" + "=" * 60)
    print("  采集完成！")
    print("=" * 60)

    with_content = sum(1 for p in all_notes if p.get("content"))
    with_tags = sum(1 for p in all_notes if p.get("tags"))
    print(f"\n  笔记总数: {len(all_notes)}")
    print(f"  总浏览: {sum(p.get('views', 0) for p in all_notes)}")
    print(f"  总点赞: {sum(p.get('likes', 0) for p in all_notes)}")
    print(f"  总收藏: {sum(p.get('favorites', 0) for p in all_notes)}")
    print(f"  总评论: {sum(p.get('comments', 0) for p in all_notes)}")
    print(f"  含正文: {with_content}/{len(all_notes)}")
    print(f"  含标签: {with_tags}/{len(all_notes)}")
    print(f"\n  下一步: python main.py analyze")


def _wait_for_login(page, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        remaining = int(timeout - (time.time() - start))
        print(f"    等待登录... (剩余 {remaining//60}分{remaining%60}秒)")
        time.sleep(5)
        if "login" not in page.url.lower():
            print("    [OK] 登录成功！")
            return
    print("    [WARN] 超时")


def _fetch_all_notes(page, max_posts):
    """
    拦截笔记管理页加载时自动触发的 API 响应。
    诊断脚本已验证此方法能获取到数据。
    """
    # 先设置拦截器
    api_responses = []

    def on_response(response):
        if NOTE_LIST_API in response.url:
            try:
                data = response.json()
                api_responses.append(data)
                print(f"    [拦截] URL: {response.url[:80]}")
            except:
                pass

    page.on("response", on_response)

    # 关键：先刷新页面（清除旧状态），再导航触发新请求
    print("    正在导航到笔记管理页，触发 API 请求...")

    # 方案A：直接导航到 note-manager
    page.goto(CREATOR_NOTES, wait_until="networkidle", timeout=30000)
    time.sleep(5)

    # 滚动触发更多请求
    for i in range(5):
        page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(2)

    time.sleep(3)

    if api_responses:
        print(f"    共拦截到 {len(api_responses)} 个 API 响应")
        notes = _parse_notes_from_responses(api_responses)
        if notes:
            print(f"    [OK] 解析到 {len(notes)} 篇笔记")
            return notes[:max_posts]

    # 方案B：从首页导航，可能也会触发
    print("    方案A 未获取到数据，尝试从首页触发...")
    page.goto(CREATOR_HOME, wait_until="networkidle", timeout=30000)
    time.sleep(5)

    if api_responses:
        notes = _parse_notes_from_responses(api_responses)
        if notes:
            print(f"    [OK] 解析到 {len(notes)} 篇笔记")
            return notes[:max_posts]

    # 方案C：用 JS 在页面中直接调用 fetch
    print("    方案B 也未获取到数据，尝试 JS fetch...")
    notes = _fetch_via_js_fetch(page)
    if notes:
        print(f"    [OK] JS fetch 获取到 {len(notes)} 篇笔记")
        return notes[:max_posts]

    return []


def _parse_notes_from_responses(responses):
    """从多个 API 响应中解析笔记"""
    all_notes = []
    for data in responses:
        notes = _parse_single_response(data)
        all_notes.extend(notes)

    # 去重
    seen = set()
    unique = []
    for n in all_notes:
        if n["note_id"] not in seen:
            seen.add(n["note_id"])
            unique.append(n)
    return unique


def _parse_single_response(data):
    """解析单个 API 响应"""
    notes = []
    data_obj = data.get("data", {})
    if not data_obj:
        return []

    items = data_obj.get("notes") or data_obj.get("list") or data_obj.get("items")
    if not items or not isinstance(items, list):
        return []

    for item in items:
        note = {
            "note_id": str(item.get("note_id") or item.get("id", "")),
            "title": (item.get("title") or item.get("display_title", "")).strip(),
            "desc": item.get("desc", ""),
            "type": item.get("type", ""),
            "status": item.get("status", ""),
            "likes": int(item.get("liked_count") or 0),
            "favorites": int(item.get("collected_count") or 0),
            "comments": int(item.get("comment_count") or 0),
            "views": int(item.get("view_count") or 0),
            "publish_time": item.get("create_time") or item.get("time") or item.get("update_time", ""),
            "tags": [],
            "images": [],
            "content": "",
        }

        if "interact_info" in item:
            ii = item["interact_info"]
            note["likes"] = int(ii.get("liked_count", note["likes"]))
            note["favorites"] = int(ii.get("collected_count", note["favorites"]))
            note["comments"] = int(ii.get("comment_count", note["comments"]))

        if note["note_id"]:
            notes.append(note)

    return notes


def _fetch_via_js_fetch(page):
    """用 JS 在页面上下文中调用 fetch API"""
    notes = []
    page_num = 0

    while page_num < 20:
        js_code = f"""
        (async () => {{
            try {{
                const url = '/api/galaxy/v2/creator/note/user/posted?tab=0&page={page_num}';
                const resp = await fetch(url, {{
                    method: 'GET',
                    credentials: 'include',
                }});
                const text = await resp.text();
                return {{ status: resp.status, body: text }};
            }} catch (e) {{
                return {{ error: e.message }};
            }}
        }})()
        """

        try:
            result = page.evaluate(js_code)

            if "error" in result:
                print(f"      JS 错误: {result['error']}")
                break

            if result.get("status") != 200:
                print(f"      HTTP {result.get('status')}, body: {result.get('body', '')[:200]}")
                break

            data = json.loads(result["body"])
            parsed = _parse_single_response(data)

            if not parsed:
                break

            notes.extend(parsed)
            print(f"      第 {page_num + 1} 页: {len(parsed)} 篇")

            data_obj = data.get("data", {})
            if not data_obj.get("has_more", False):
                break

        except Exception as e:
            print(f"      执行错误: {e}")
            break

        page_num += 1
        time.sleep(1)

    return notes


def _fetch_content_from_editor(page, notes, max_posts):
    """通过编辑页获取正文和标签"""
    total = len(notes)

    for i, note in enumerate(notes[:max_posts]):
        note_id = note.get("note_id", "")
        title = note.get("title", "")[:40]

        print(f"    [{i+1}/{total}] {title}")

        if not note_id:
            print(f"    [{i+1}/{total}] 跳过 (无ID)")
            continue

        try:
            edit_url = f"https://creator.xiaohongshu.com/editor/{note_id}"
            page.goto(edit_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            content = _extract_editor_content(page)

            if content and content.get("text"):
                note["content"] = content["text"]
                note["tags"] = content.get("tags", [])
                if content.get("title"):
                    note["title"] = content["title"]
                print(f"    [{i+1}/{total}] OK ✓ ({len(content['text'])}字, {len(content.get('tags', []))}标签)")
            else:
                print(f"    [{i+1}/{total}] 无正文")

        except Exception as e:
            print(f"    [{i+1}/{total}] 失败: {e}")

    return notes


def _extract_editor_content(page):
    """从笔记编辑页提取内容"""
    result = {"text": "", "tags": [], "title": ""}

    try:
        el = page.query_selector('input[placeholder*="标题"]')
        if el:
            result["title"] = el.input_value()

        for selector in ['[contenteditable="true"]', 'div[role="textbox"]', 'textarea']:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if len(text) > 10:
                    result["text"] = text
                    break

        for selector in ['[class*="tag"]', '[class*="topic"]']:
            for el in page.query_selector_all(selector):
                t = el.inner_text().strip()
                if t and len(t) < 30:
                    tag = t if t.startswith("#") else f"#{t}"
                    if tag not in result["tags"]:
                        result["tags"].append(tag)
            if result["tags"]:
                break

        if not result["tags"] and result["text"]:
            for t in re.findall(r"#([^#\s]+)", result["text"]):
                tag = f"#{t}"
                if tag not in result["tags"]:
                    result["tags"].append(tag)

    except Exception:
        pass

    return result


def _save_posts(posts, posts_dir):
    for f in posts_dir.glob("*.json"):
        f.unlink()
    for i, post in enumerate(posts):
        filepath = posts_dir / f"{i+1:03d}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(post, f, ensure_ascii=False, indent=2)
    combined_path = posts_dir / "all_posts.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()
    run_collector(max_posts=args.max)
