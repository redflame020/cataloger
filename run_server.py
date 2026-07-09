import uvicorn
from server import app
import sys

port = 8080
use_ssl = "--ssl" in sys.argv

other_args = [a for a in sys.argv[1:] if a != "--ssl"]
if other_args:
    try:
        port = int(other_args[0])
    except ValueError:
        pass

ssl_kwargs = {}
if use_ssl:
    ssl_kwargs = {
        "ssl_keyfile": "ssl/key.pem",
        "ssl_certfile": "ssl/cert.pem",
    }
    if port == 8080:
        port = 8443

uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", **ssl_kwargs)
