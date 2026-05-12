#!/usr/bin/env python3
"""
环境检查脚本
验证 Voice Assistant 运行环境是否满足要求

用法:
    python scripts/check_env.py
    # 或
    python -m voice_assistant.check_env
"""
import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))


def check_python_version():
    """检查 Python 版本"""
    print("\n" + "=" * 50)
    print("  Python 版本")
    print("=" * 50)

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version >= (3, 10):
        print(f"  ✓ Python {version_str}")
        return True
    else:
        print(f"  ✗ Python {version_str} (需要 >= 3.10)")
        return False


def check_config_files():
    """检查配置文件"""
    print("\n" + "=" * 50)
    print("  配置文件")
    print("=" * 50)

    project_root = Path(__file__).parent.parent
    all_ok = True

    # 检查 config.yaml
    config_yaml = project_root / "config.yaml"
    if config_yaml.exists():
        print(f"  ✓ config.yaml")
    else:
        print(f"  ✗ config.yaml 缺失")
        all_ok = False

    # 检查 .env
    env_file = project_root / ".env"
    if env_file.exists():
        print(f"  ✓ .env")
    else:
        print(f"  ⚠ .env 缺失（可选，用于环境变量）")

    # 检查热词配置
    hotwords_file = project_root / "config" / "hotwords.json"
    if hotwords_file.exists():
        print(f"  ✓ config/hotwords.json")
    else:
        print(f"  ⚠ config/hotwords.json 缺失（热词功能不可用）")

    return all_ok


def check_api_keys():
    """检查 API 密钥"""
    print("\n" + "=" * 50)
    print("  API 密钥")
    print("=" * 50)

    import os

    # 尝试加载 .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    all_ok = True

    # DashScope API Key (用于 ASR 和 LLM)
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    if dashscope_key:
        print(f"  ✓ DASHSCOPE_API_KEY: {'*' * 8}{dashscope_key[-4:]}")
    else:
        # 检查旧的分离式 API Key
        asr_key = os.getenv("ASR_API_KEY")
        llm_key = os.getenv("LLM_API_KEY")
        if asr_key:
            print(f"  ✓ ASR_API_KEY: {'*' * 8}{asr_key[-4:]}")
        else:
            print(f"  ⚠ ASR_API_KEY 未设置")
        
        if llm_key:
            print(f"  ✓ LLM_API_KEY: {'*' * 8}{llm_key[-4:]}")
        else:
            print(f"  ⚠ LLM_API_KEY 未设置")
        
        if not asr_key and not llm_key:
            print(f"  ✗ 请设置 DASHSCOPE_API_KEY 或 ASR_API_KEY/LLM_API_KEY")
            all_ok = False

    return all_ok


def check_audio_devices():
    """检查音频设备"""
    print("\n" + "=" * 50)
    print("  音频设备")
    print("=" * 50)

    try:
        import sounddevice as sd
        devices = sd.query_devices()

        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        output_devices = [d for d in devices if d['max_output_channels'] > 0]

        print(f"  输入设备: {len(input_devices)} 个")
        for d in input_devices[:3]:
            print(f"    • {d['name']}")

        if len(input_devices) > 3:
            print(f"    ... 还有 {len(input_devices) - 3} 个")

        print(f"  输出设备: {len(output_devices)} 个")
        for d in output_devices[:3]:
            print(f"    • {d['name']}")

        if len(output_devices) > 3:
            print(f"    ... 还有 {len(output_devices) - 3} 个")

        return len(input_devices) > 0 and len(output_devices) > 0

    except ImportError:
        print("  ✗ sounddevice 未安装")
        return False
    except Exception as e:
        print(f"  ✗ 检查音频设备失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("  Voice Assistant 环境检查")
    print("=" * 50)

    results = []

    # 1. Python 版本
    results.append(("Python 版本", check_python_version()))

    # 2. 配置文件
    results.append(("配置文件", check_config_files()))

    # 3. API 密钥
    results.append(("API 密钥", check_api_keys()))

    # 4. 依赖
    print("\n" + "=" * 50)
    print("  Python 依赖")
    print("=" * 50)

    try:
        from voice_assistant.core.dependencies import check_dependencies
        from voice_assistant.config import config

        manager = check_dependencies(config, verbose=True)
        results.append(("Python 依赖", not manager.has_blocking_errors()))
    except Exception as e:
        print(f"  ✗ 依赖检查失败: {e}")
        results.append(("Python 依赖", False))

    # 5. 音频设备
    results.append(("音频设备", check_audio_devices()))

    # 汇总
    print("\n" + "=" * 50)
    print("  检查汇总")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n✅ 环境检查通过，可以启动 Voice Assistant\n")
        return 0
    else:
        print("\n❌ 环境检查未通过，请修复上述问题\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
