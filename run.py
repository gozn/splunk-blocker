import sys
import os

# Insert project root to sys.path so configs and app can be imported properly
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Run the server on port 6666
    app.logger.info("Initializing Splunk Webhook Server on port 6666...")
    app.run(host='0.0.0.0', port=6666, debug=False)
