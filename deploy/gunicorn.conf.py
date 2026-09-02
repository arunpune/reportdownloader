"""
Gunicorn server configuration for the Test Report Portal.

This file is used when the Flask application is deployed
using Gunicorn on a production or Linux server.

It controls:
- The network address and port used by the web server
- The number of worker processes
- Request timeout duration
- Access and error logging

This configuration is not required when running the
prototype locally using `python run.py`.
"""



bind = "0.0.0.0:5000"
workers = 3
timeout = 120
accesslog = "-"
errorlog = "-"
