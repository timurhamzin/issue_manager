import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()


if __name__ == "__main__":
    debug = (os.getenv('ENV_TYPE') == 'development')
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=debug)
