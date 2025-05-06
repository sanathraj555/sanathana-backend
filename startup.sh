#!/bin/bash
gunicorn app:app -b 0.0.0.0:8000 --timeout 300 --log-level info --capture-output
