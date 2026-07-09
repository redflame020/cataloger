import uvicorn
from server import app
import sys
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
