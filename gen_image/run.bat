@echo off
:: 设置 CMD 窗口使用 UTF-8 编码，防止中文乱码
chcp 65001 > nul

uv run main.py