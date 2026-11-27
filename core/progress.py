def progress_bar(percent: float, width: int = 16) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(width * percent / 100)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {percent:.1f}%"
