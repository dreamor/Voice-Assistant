"""
通用文件高级操作工具 - file_advanced_ops
文件内容搜索、移动/重命名、复制、压缩/解压、文件信息
"""
import logging
import os
import platform
import re
import shutil
import subprocess
import zipfile

logger = logging.getLogger(__name__)


def _resolve_path(path: str) -> str:
    """解析路径（支持 ~ 和相对路径）"""
    return os.path.abspath(os.path.expanduser(path))


_PATTERN_MAX_LEN = 200
_FILE_EXT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def search_in_files(pattern: str, directory: str = ".", file_ext: str = "") -> str:
    """在文件内容中搜索关键词（字面量匹配，非正则）"""
    if not pattern:
        return "搜索关键词不能为空"
    if len(pattern) > _PATTERN_MAX_LEN:
        return f"搜索关键词过长（>{_PATTERN_MAX_LEN} 字符）"
    if file_ext and not _FILE_EXT_RE.match(file_ext):
        return "文件扩展名仅允许字母数字下划线"

    directory = _resolve_path(directory)
    if not os.path.isdir(directory):
        return f"目录不存在: {directory}"

    try:
        if platform.system() == "Windows":
            cmd = ["findstr", "/s", "/i", "/n", "/l", "/c:" + pattern]
            target = os.path.join(directory, f"*.{file_ext}" if file_ext else "*.*")
            cmd.append(target)
        else:
            cmd = ["grep", "-r", "-n", "-i", "-F", "--"]
            if file_ext:
                cmd[6:6] = ["--include", f"*.{file_ext}"]
            cmd.extend(["--max-count=50", pattern, directory])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if not output:
            return f"未找到匹配「{pattern}」的内容"

        lines = output.split("\n")[:50]
        if len(output.split("\n")) > 50:
            lines.append("... (结果过多，仅显示前 50 行)")
        return "搜索结果:\n" + "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "搜索超时"
    except FileNotFoundError:
        return "findstr 不可用" if platform.system() == "Windows" else "grep 不可用"
    except OSError as e:
        return f"搜索失败: {e}"


def move_file(source: str, destination: str) -> str:
    """移动或重命名文件/目录"""
    src = _resolve_path(source)
    dst = _resolve_path(destination)
    if not os.path.exists(src):
        return f"源路径不存在: {source}"
    try:
        shutil.move(src, dst)
        return f"已移动: {source} → {destination}"
    except (OSError, shutil.Error) as e:
        return f"移动失败: {e}"


def copy_file(source: str, destination: str) -> str:
    """复制文件"""
    src = _resolve_path(source)
    dst = _resolve_path(destination)
    if not os.path.exists(src):
        return f"源文件不存在: {source}"
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return f"已复制: {source} → {destination}"
    except (OSError, shutil.Error) as e:
        return f"复制失败: {e}"


def compress_files(source: str, output: str = "") -> str:
    """压缩文件或目录为 zip"""
    src = _resolve_path(source)
    if not os.path.exists(src):
        return f"源路径不存在: {source}"
    if not output:
        output = src + ".zip"
    else:
        output = _resolve_path(output)
    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(src):
                base = os.path.basename(src)
                for root, dirs, files in os.walk(src):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.join(base, os.path.relpath(full, src))
                        zf.write(full, arc)
            else:
                zf.write(src, os.path.basename(src))
        size_kb = os.path.getsize(output) / 1024
        return f"已压缩: {output} ({size_kb:.1f} KB)"
    except (OSError, zipfile.BadZipFile) as e:
        return f"压缩失败: {e}"


def decompress_file(zip_path: str, output_dir: str = "") -> str:
    """解压 zip 文件"""
    src = _resolve_path(zip_path)
    if not os.path.exists(src):
        return f"文件不存在: {zip_path}"
    if not zipfile.is_zipfile(src):
        return f"不是有效的 zip 文件: {zip_path}"
    if not output_dir:
        output_dir = os.path.dirname(src)
    else:
        output_dir = _resolve_path(output_dir)
    try:
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(output_dir)
            count = len(zf.namelist())
        return f"已解压 {count} 个文件到: {output_dir}"
    except (OSError, zipfile.BadZipFile) as e:
        return f"解压失败: {e}"


def get_file_info(path: str) -> str:
    """获取文件元信息（大小、修改时间、权限等）"""
    full = _resolve_path(path)
    if not os.path.exists(full):
        return f"文件不存在: {path}"
    try:
        stat = os.stat(full)
        size = stat.st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"

        import time
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime))
        ftype = "目录" if os.path.isdir(full) else "文件"
        lines = [
            f"路径: {full}",
            f"类型: {ftype}",
            f"大小: {size_str}",
            f"修改时间: {mtime}",
            f"创建时间: {ctime}",
            f"权限: {oct(stat.st_mode)[-3:]}",
        ]
        if os.path.isfile(full):
            ext = os.path.splitext(full)[1]
            if ext:
                lines.append(f"扩展名: {ext}")
        return "\n".join(lines)
    except OSError as e:
        return f"获取文件信息失败: {e}"
