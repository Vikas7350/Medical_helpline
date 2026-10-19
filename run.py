"""Application entrypoint for running the Multilingual AI Medical Helpline."""

import os
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    port = int(os.getenv("PORT", str(settings.PORT)))
    host = os.getenv("HOST", settings.HOST)

    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.ENVIRONMENT} (DEBUG={settings.DEBUG})")
    print(f"Listening on: http://{host}:{port}")
    print(f"Dashboard:    http://{host}:{port}/")
    print(f"Health Check: http://{host}:{port}/health")
    print(f"API Docs:     http://{host}:{port}/docs")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_keep_alive=65,
    )
