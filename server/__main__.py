import uvicorn

from server.api import create_app
from server.config import Settings

settings = Settings.environment()  # Public modes / non-loopback hosts fail before listening.
uvicorn.run(create_app(settings), host=settings.host, port=8017, access_log=False)
