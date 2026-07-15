import logging
from flask import Flask
from app.database import init_db
from app.routes import main_bp

def create_app():
    app = Flask(__name__)
    
    # Configure clean logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Initialize DB (creates tables if missing)
    app.logger.info("Initializing database...")
    init_db()
    
    # Register blueprints
    app.logger.info("Registering routes...")
    app.register_blueprint(main_bp)
    
    return app
