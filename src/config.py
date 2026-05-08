"""配置加载器"""
import os
import yaml
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_config():
    """加载配置文件"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 从环境变量覆盖敏感配置
    if api_key := os.environ.get("ANTHROPIC_API_KEY"):
        config["llm"]["api_key"] = api_key
    if api_key := os.environ.get("OPENAI_API_KEY"):
        config["image"]["api_key"] = api_key

    return config


def load_banned_words():
    """加载敏感词库"""
    word_file = CONFIG_PATH.parent / "banned_words.txt"
    words = []
    with open(word_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line)
    return words


def get_data_dir(subdir=None):
    """获取数据目录路径"""
    data_dir = PROJECT_ROOT / "data"
    if subdir:
        data_dir = data_dir / subdir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
