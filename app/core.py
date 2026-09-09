from __future__ import annotations

import itertools
import json
import os
import random
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pyJianYingDraft as draft
from pymediainfo import MediaInfo


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.json"
INDEX_PATH = ROOT / "config" / "asset_index.json"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
TOKEN_SPLIT = re.compile(r"[\s,，、;；_\-—.（）()\[\]【】]+")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
DOMAIN_KEYWORDS = [
    "黄精", "肉苁蓉", "原料", "配料表", "配料", "检测", "报告", "工厂", "产地",
    "产品", "包装", "冲泡", "食用", "办公室", "家庭", "送礼", "中年", "男性", "女性",
    "手持", "特写", "切片", "倒水", "杯子", "仓库", "生产", "质检", "生活",
]
RISK_TERMS = [
    "治疗", "治愈", "根治", "抗癌", "降血压", "降血糖", "壮阳", "提高性功能",
    "药到病除", "百分百有效", "立即见效", "医生推荐", "专家推荐", "无副作用",
]


@dataclass
class Asset:
    path: str
    kind: str
    duration: float
    width: int
    height: int
    tags: list[str]
    size: int = 0
    mtime_ns: int = 0


def detect_jianying_exe() -> str:
    candidates: list[Path] = []
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\JianyingPro"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            uninstall, _ = winreg.QueryValueEx(key, "UninstallString")
            install_root = Path(str(uninstall).strip('"')).parent
            candidates.append(install_root / "JianyingPro.exe")
            version_dirs = sorted((p for p in install_root.iterdir() if p.is_dir()), reverse=True)
            candidates.extend(p / "JianyingPro.exe" for p in version_dirs)
    except Exception:
        pass
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates.extend([
        local / "JianyingPro" / "Apps" / "JianyingPro.exe",
        program_files / "JianyingPro" / "JianyingPro.exe",
    ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def detect_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    candidates = [
        Path(found) if found else None,
        ROOT / "tools" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return ""


def default_settings() -> dict[str, Any]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return {
        "draft_folder": str(local / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"),
        "asset_folder": str(ROOT / "素材库"),
        "task_folder": str(ROOT / "文案"),
        "ffmpeg": detect_ffmpeg(),
        "jianying_exe": detect_jianying_exe(),
        "draft_prefix": "自动剪辑_",
        "max_variants": 12,
        "default_image_duration": 3.0,
        "seed": 20260909,
    }


def load_settings() -> dict[str, Any]:
    settings = default_settings()
    if CONFIG_PATH.exists():
        settings.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
    if not settings.get("jianying_exe") or not Path(settings["jianying_exe"]).exists():
        settings["jianying_exe"] = detect_jianying_exe()
    if not settings.get("ffmpeg") or not Path(settings["ffmpeg"]).exists():
        settings["ffmpeg"] = detect_ffmpeg()
    Path(settings["asset_folder"]).mkdir(parents=True, exist_ok=True)
    Path(settings["task_folder"]).mkdir(parents=True, exist_ok=True)
    (ROOT / "任务").mkdir(parents=True, exist_ok=True)
    (ROOT / "日志").mkdir(parents=True, exist_ok=True)
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def _tags_for(path: Path, root: Path) -> list[str]:
    values: list[str] = []
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        relative_parts = path.parts
    for part in relative_parts:
        values.extend(TOKEN_SPLIT.split(Path(part).stem.lower()))
    sidecar = path.with_suffix(path.suffix + ".tags.txt")
    if sidecar.exists():
        values.extend(TOKEN_SPLIT.split(sidecar.read_text(encoding="utf-8-sig").lower()))
    return sorted({v.strip() for v in values if v.strip()})


def _probe(path: Path, default_image_duration: float) -> tuple[float, int, int]:
    if path.suffix.lower() in IMAGE_EXTS:
        try:
            from PIL import Image

            with Image.open(path) as image:
                if path.suffix.lower() == ".gif":
                    duration_ms = 0
                    for frame in range(getattr(image, "n_frames", 1)):
                        image.seek(frame)
                        duration_ms += int(image.info.get("duration", 100))
                    return max(0.1, duration_ms / 1000.0), int(image.width), int(image.height)
                return default_image_duration, int(image.width), int(image.height)
        except Exception:
            return default_image_duration, 0, 0
    try:
        info = MediaInfo.parse(str(path))
        for track in info.tracks:
            if track.track_type == "Video":
                duration = float(track.duration or 0) / 1000.0
                return duration, int(track.width or 0), int(track.height or 0)
        for track in info.tracks:
            if track.track_type == "Audio":
                return float(track.duration or 0) / 1000.0, 0, 0
    except Exception:
        pass
    return 0.0, 0, 0


def scan_assets(settings: dict[str, Any] | None = None) -> list[Asset]:
    settings = settings or load_settings()
    root = Path(settings["asset_folder"])
    root.mkdir(parents=True, exist_ok=True)
    previous: dict[str, Asset] = {}
    if INDEX_PATH.exists():
        try:
            old_data = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
            if old_data.get("root") == str(root.resolve()):
                previous = {item["path"]: Asset(**item) for item in old_data.get("assets", [])}
        except Exception:
            previous = {}
    assets: list[Asset] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.endswith(".tags.txt"):
            continue
        ext = path.suffix.lower()
        if ext not in VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS:
            continue
        resolved = str(path.resolve())
        stat = path.stat()
        kind = "video" if ext in VIDEO_EXTS else "image" if ext in IMAGE_EXTS else "audio"
        cached = previous.get(resolved)
        if cached and cached.size == stat.st_size and cached.mtime_ns == stat.st_mtime_ns:
            cached.tags = _tags_for(path, root)
            assets.append(cached)
            continue
        duration, width, height = _probe(path, float(settings["default_image_duration"]))
        assets.append(Asset(resolved, kind, round(duration, 3), width, height, _tags_for(path, root), stat.st_size, stat.st_mtime_ns))
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps({"root": str(root.resolve()), "generated_at": datetime.now().isoformat(timespec="seconds"), "assets": [asdict(a) for a in assets]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return assets


def load_asset_index(settings: dict[str, Any] | None = None, refresh: bool = False) -> list[Asset]:
    if refresh or not INDEX_PATH.exists():
        return scan_assets(settings)
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
    return [Asset(**item) for item in data.get("assets", []) if Path(item["path"]).exists()]


def _keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [x.lower() for x in TOKEN_SPLIT.split(value) if x]
    return [str(x).strip().lower() for x in value if str(x).strip()]


def choose_asset(scene: dict[str, Any], assets: list[Asset], used: dict[str, int], rng: random.Random) -> Asset | None:
    explicit = scene.get("asset")
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = ROOT / "素材库" / path
        if not path.exists():
            raise FileNotFoundError(f"指定素材不存在：{path}")
        for asset in assets:
            if Path(asset.path).resolve() == path.resolve():
                return asset
        duration, width, height = _probe(path, 3.0)
        kind = "video" if path.suffix.lower() in VIDEO_EXTS else "image"
        return Asset(str(path.resolve()), kind, duration, width, height, _tags_for(path, ROOT / "素材库"))

    words = _keywords(scene.get("keywords"))
    visual = [a for a in assets if a.kind in {"video", "image"}]
    if not visual:
        return None
    scored: list[tuple[float, float, Asset]] = []
    for asset in visual:
        haystack = " ".join(asset.tags + [asset.path.lower()])
        keyword_score = sum(3.0 for word in words if word in asset.tags) + sum(1.0 for word in words if word in haystack)
        reuse_penalty = used.get(asset.path, 0) * 2.5
        vertical_bonus = 0.5 if asset.height > asset.width else 0.0
        scored.append((keyword_score - reuse_penalty + vertical_bonus, rng.random(), asset))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def _variant_scenes(task: dict[str, Any]) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    hooks = task.get("hooks") or [None]
    ctas = task.get("ctas") or [None]
    body = list(task.get("segments") or [])
    for index, (hook, cta) in enumerate(itertools.product(hooks, ctas), start=1):
        scenes: list[dict[str, Any]] = []
        if hook:
            scenes.append({"role": "hook", "text": hook["text"] if isinstance(hook, dict) else str(hook), "duration": hook.get("duration", 3.0) if isinstance(hook, dict) else 3.0, "keywords": hook.get("keywords", []) if isinstance(hook, dict) else []})
        scenes.extend(body)
        if cta:
            scenes.append({"role": "cta", "text": cta["text"] if isinstance(cta, dict) else str(cta), "duration": cta.get("duration", 3.0) if isinstance(cta, dict) else 3.0, "keywords": cta.get("keywords", []) if isinstance(cta, dict) else []})
        yield f"V{index:02d}", scenes


def _safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")[:80] or "未命名"


def _seconds(value: Any, default: float = 3.0) -> float:
    seconds = float(value if value is not None else default)
    return max(0.5, seconds)


def scan_compliance(task: dict[str, Any]) -> list[str]:
    pieces: list[str] = []
    for key in ("hooks", "segments", "ctas"):
        for item in task.get(key) or []:
            pieces.append(item.get("text", "") if isinstance(item, dict) else str(item))
    whole = "\n".join(pieces)
    return [term for term in RISK_TERMS if term in whole]


def create_task_from_text(project_name: str, body: str, hooks: str = "", ctas: str = "", persona: str = "口播讲解型") -> Path:
    project_name = _safe_name(project_name)
    persona_tags = {
        "口播讲解型": ["人物", "产品"],
        "家庭关怀型": ["家庭", "生活", "产品"],
        "工厂纪实型": ["工厂", "原料", "生产", "检测"],
        "主播问答型": ["人物", "手持", "产品"],
        "对比测评型": ["产品", "配料表", "特写"],
    }
    base_tags = persona_tags.get(persona, ["产品"])

    def scene(text: str, role: str) -> dict[str, Any]:
        cleaned = text.strip()
        found = [word for word in DOMAIN_KEYWORDS if word in cleaned]
        duration = min(6.5, max(2.5, len(cleaned) / 4.2))
        return {"role": role, "text": cleaned, "duration": round(duration, 1), "keywords": list(dict.fromkeys(found + base_tags))[:6]}

    hook_lines = [line.strip() for line in hooks.splitlines() if line.strip()]
    cta_lines = [line.strip() for line in ctas.splitlines() if line.strip()]
    body_lines = [line.strip() for line in SENTENCE_SPLIT.split(body) if line.strip()]
    if not body_lines:
        raise ValueError("正文不能为空")
    task = {
        "project_name": project_name,
        "persona": persona,
        "resolution": [1080, 1920],
        "fps": 30,
        "max_variants": 12,
        "subtitle_size": 10,
        "hooks": [scene(line, "hook") for line in hook_lines],
        "segments": [scene(line, "body") for line in body_lines],
        "ctas": [scene(line, "cta") for line in cta_lines],
    }
    warnings = scan_compliance(task)
    if warnings:
        task["compliance_warnings"] = warnings
    output = ROOT / "文案" / f"{project_name}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def generate_drafts(task_path: str | Path, settings: dict[str, Any] | None = None, refresh_assets: bool = True) -> list[dict[str, Any]]:
    settings = settings or load_settings()
    task = json.loads(Path(task_path).read_text(encoding="utf-8-sig"))
    assets = load_asset_index(settings, refresh=refresh_assets)
    requires_auto_match = any(not isinstance(scene, dict) or not scene.get("asset") for scene in task.get("segments") or [])
    requires_auto_match = requires_auto_match or any(not isinstance(scene, dict) or not scene.get("asset") for scene in (task.get("hooks") or []))
    requires_auto_match = requires_auto_match or any(not isinstance(scene, dict) or not scene.get("asset") for scene in (task.get("ctas") or []))
    if requires_auto_match and not any(asset.kind in {"video", "image"} for asset in assets):
        raise ValueError("素材库中没有可用的视频或图片。请先放入素材并点击“扫描素材库”。")
    warnings = scan_compliance(task)
    width, height = task.get("resolution", [1080, 1920])
    project = _safe_name(task.get("project_name", Path(task_path).stem))
    prefix = settings.get("draft_prefix", "自动剪辑_")
    batch_id = datetime.now().strftime("%m%d_%H%M%S")
    draft_root = Path(settings["draft_folder"])
    draft_root.mkdir(parents=True, exist_ok=True)
    folder = draft.DraftFolder(str(draft_root))
    max_variants = int(task.get("max_variants", settings.get("max_variants", 12)))
    rng = random.Random(int(task.get("seed", settings.get("seed", 20260909))))
    results: list[dict[str, Any]] = []

    for variant_id, scenes in itertools.islice(_variant_scenes(task), max_variants):
        if not scenes:
            raise ValueError("任务中没有可生成的镜头段落")
        draft_name = _safe_name(f"{prefix}{project}_{batch_id}_{variant_id}")
        script = folder.create_draft(draft_name, int(width), int(height), fps=int(task.get("fps", 30)), allow_replace=False)
        script.append_tracks([
            draft.TrackSpec(draft.TrackType.audio, "voice"),
            draft.TrackSpec(draft.TrackType.audio, "bgm"),
            draft.TrackSpec(draft.TrackType.video, "main_video"),
            draft.TrackSpec(draft.TrackType.text, "caption"),
        ])
        used: dict[str, int] = {}
        cursor = 0.0
        decisions: list[dict[str, Any]] = []
        for scene in scenes:
            requested = _seconds(scene.get("duration"), 3.0)
            asset = choose_asset(scene, assets, used, rng)
            actual = requested
            if asset:
                material = draft.VideoMaterial(asset.path)
                material_seconds = material.duration / 1_000_000.0
                actual = min(requested, max(0.1, material_seconds - 0.01))
                segment = draft.VideoSegment(material, draft.trange(f"{cursor:.3f}s", f"{actual:.3f}s"), volume=0.0)
                segment.add_background_filling("blur", 0.0625)
                script.add_segment(segment, "main_video")
                used[asset.path] = used.get(asset.path, 0) + 1
            text_value = str(scene.get("text", "")).strip()
            if text_value:
                style = draft.TextStyle(size=float(task.get("subtitle_size", 10.0)), bold=True, color=(1.0, 1.0, 1.0), auto_wrapping=True, max_line_width=0.82)
                border = draft.TextBorder(alpha=1.0, color=(0.05, 0.05, 0.05), width=42.0)
                caption = draft.TextSegment(text_value, draft.trange(f"{cursor:.3f}s", f"{actual:.3f}s"), style=style, border=border, clip_settings=draft.ClipSettings(transform_y=-0.72))
                script.add_segment(caption, "caption")
            decisions.append({"role": scene.get("role", "body"), "text": text_value, "requested_duration": requested, "actual_duration": round(actual, 3), "asset": asset.path if asset else None})
            cursor += actual

        voiceover = task.get("voiceover")
        if voiceover:
            voice_path = Path(voiceover)
            if not voice_path.is_absolute():
                voice_path = Path(task_path).parent / voice_path
            script.add_segment(draft.AudioSegment(str(voice_path.resolve()), draft.trange("0s", f"{cursor:.3f}s")), "voice")
        bgm = task.get("bgm")
        if bgm:
            bgm_path = Path(bgm)
            if not bgm_path.is_absolute():
                bgm_path = ROOT / "素材库" / bgm_path
            bgm_segment = draft.AudioSegment(str(bgm_path.resolve()), draft.trange("0s", f"{cursor:.3f}s"), volume=float(task.get("bgm_volume", 0.18)))
            bgm_segment.add_fade("0.5s", "0.8s")
            script.add_segment(bgm_segment, "bgm")
        script.save()
        results.append({"draft": draft_name, "path": str(draft_root / draft_name), "duration": round(cursor, 3), "decisions": decisions})

    report_path = ROOT / "任务" / f"{project}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"task": str(Path(task_path).resolve()), "compliance_warnings": warnings, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def diagnose(settings: dict[str, Any] | None = None) -> list[tuple[str, bool, str]]:
    settings = settings or load_settings()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("剪映草稿目录", Path(settings["draft_folder"]).exists(), settings["draft_folder"]))
    checks.append(("素材库", Path(settings["asset_folder"]).exists(), settings["asset_folder"]))
    checks.append(("FFmpeg（当前版本非必需）", bool(settings.get("ffmpeg")) and Path(settings["ffmpeg"]).exists(), settings.get("ffmpeg") or "未找到"))
    checks.append(("剪映程序", bool(settings.get("jianying_exe")) and Path(settings["jianying_exe"]).exists(), settings.get("jianying_exe") or "未找到"))
    try:
        import tkinter  # noqa: F401

        checks.append(("桌面界面", True, "Tkinter 可用"))
    except Exception as exc:
        checks.append(("桌面界面", False, str(exc)))
    try:
        from importlib.metadata import version

        checks.append(("剪映草稿引擎", True, f"pyJianYingDraft {version('pyJianYingDraft')}"))
    except Exception as exc:
        checks.append(("剪映草稿引擎", False, str(exc)))
    return checks
