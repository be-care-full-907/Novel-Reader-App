@echo off
title Novel Scraper & Simultaneous Cleaner
cd /d "%~dp0"
echo =======================================================
echo          Starting Novel Scraper ^& Cleaner...
echo =======================================================
python scrape.py
pause
