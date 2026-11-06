"""Drop root privileges after initializing the explicitly configured artifact dir."""
import os
from pathlib import Path
from .config import settings

if __name__ == "__main__":
    directory = Path(settings.publish_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(directory, 10001, 10001)
        os.setgid(10001)
        os.setuid(10001)
    # Render Free has no pre-deploy jobs or shell: apply the idempotent schema
    # from the service process over its private database connection.
    if settings.database_url or os.getenv("DATABASE_URL"):
        from .accounts import migrate
        try:
            migrate()
        except Exception:
            raise SystemExit("数据库迁移失败，服务未启动；请检查数据库连接和权限") from None
    os.execvp("uvicorn", ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "8000"), "--workers", "1", "--no-access-log"])
