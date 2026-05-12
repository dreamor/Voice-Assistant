"""
通用文件操作工具 - file_ops
跨平台文件读写、列表、搜索、删除
"""
import os
import logging
import shutil
from pathlib import Path

from voice_assistant.security.safe_guard import SecurityLevel

logger = logging.getLogger(__name__)

CURRENT_DIR = os.getcwd()


def _resolve_path(path: str) -> str:
    """解析路径，支持相对路径"""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(Path(CURRENT_DIR) / p)


def read_file(path: str, max_lines: int = 200) -> str:
    """读取文件内容"""
    resolved = _resolve_path(path)
    try:
        with open(resolved, encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append(f"\n... (共 {len(lines) + max_lines} 行，仅显示前 {max_lines} 行)")
        return ''.join(lines)
    except FileNotFoundError:
        return f"文件不存在: {path}"
    except UnicodeDecodeError:
        return f"无法读取二进制文件: {path}"
    except PermissionError:
        return f"没有权限读取: {path}"
    except Exception as e:
        return f"读取失败: {e}"


def write_file(path: str, content: str) -> str:
    """写入文件内容"""
    resolved = _resolve_path(path)
    try:
        os.makedirs(os.path.dirname(resolved) or '.', exist_ok=True)
        with open(resolved, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"已写入: {path}"
    except PermissionError:
        return f"没有权限写入: {path}"
    except Exception as e:
        return f"写入失败: {e}"


def delete_file(path: str) -> str:
    """删除文件（不可恢复）"""
    resolved = _resolve_path(path)
    try:
        os.remove(resolved)
        return f"已删除: {path}"
    except FileNotFoundError:
        return f"文件不存在: {path}"
    except PermissionError:
        return f"没有权限删除: {path}"
    except Exception as e:
        return f"删除失败: {e}"


def list_directory(path: str = ".") -> str:
    """列出目录内容"""
    resolved = _resolve_path(path)
    try:
        items = os.listdir(resolved)
        if not items:
            return f"目录为空: {path}"
        lines = []
        for item in sorted(items):
            full = os.path.join(resolved, item)
            prefix = "📁 " if os.path.isdir(full) else "📄 "
            size = ""
            if os.path.isfile(full):
                size = f" ({_format_size(os.path.getsize(full))})"
            lines.append(f"{prefix}{item}{size}")
        return '\n'.join(lines)
    except FileNotFoundError:
        return f"目录不存在: {path}"
    except PermissionError:
        return f"没有权限访问: {path}"
    except Exception as e:
        return f"列出失败: {e}"


def find_files(pattern: str, directory: str = ".") -> str:
    """搜索文件（支持 glob 模式和子字符串匹配）"""
    import fnmatch
    resolved_dir = _resolve_path(directory)
    try:
        matches = []
        # 支持多个模式（空格或逗号分隔）
        patterns = [p.strip().strip(',').lower() for p in pattern.replace(',', ' ').split() if p.strip()]
        for root, dirs, files in os.walk(resolved_dir):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                fname_lower = fname.lower()
                matched = any(
                    fnmatch.fnmatch(fname_lower, p) or p in fname_lower
                    for p in patterns
                )
                if matched:
                    rel_path = os.path.relpath(os.path.join(root, fname), resolved_dir)
                    matches.append(rel_path)
        if not matches:
            return f"未找到匹配 '{pattern}' 的文件"
        if len(matches) > 50:
            matches = matches[:50]
            matches.append(f"\n... (共 {len(matches) + 50} 个结果，仅显示前 50 个)")
        return '\n'.join(matches)
    except FileNotFoundError:
        return f"目录不存在: {directory}"
    except Exception as e:
        return f"搜索失败: {e}"


def _format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def delete_directory(path: str) -> str:
    """删除整个目录（不可恢复）"""
    resolved = _resolve_path(path)
    try:
        shutil.rmtree(resolved)
        return f"已删除目录: {path}"
    except FileNotFoundError:
        return f"目录不存在: {path}"
    except PermissionError:
        return f"没有权限删除: {path}"
    except Exception as e:
        return f"删除失败: {e}"