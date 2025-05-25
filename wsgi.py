"""
WSGI Entry Point
===============

This file serves as the entry point for the WSGI server.
"""

from web_app import app

# This is the WSGI entry point
application = app

if __name__ == "__main__":
    application.run() 