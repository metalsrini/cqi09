#!/usr/bin/env python3
"""
Run Web Portal
============

Standalone script to run the CQI-9 Compliance Analysis System web portal.
"""

import os
import sys
from web_portal.app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5555))
    app.run(host='0.0.0.0', port=port, debug=True) 