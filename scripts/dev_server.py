#!/usr/bin/env python3
"""
Скрипт для запуска сервера разработки RentScout.

Этот скрипт запускает приложение в режиме разработки с автоматической перезагрузкой
при изменении файлов.
"""

import os
import sys
import subprocess
import argparse

def main():
    """Основная функция запуска сервера разработки."""
    parser = argparse.ArgumentParser(description='Запуск сервера разработки RentScout')
    parser.add_argument('--host', default='127.0.0.1', help='Хост для сервера (по умолчанию: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000, help='Порт для сервера (по умолчанию: 8000)')
    parser.add_argument('--reload', action='store_true', help='Включить автоматическую перезагрузку при изменении файлов')
    
    args = parser.parse_args()
    
    # Добавляем корневую директорию проекта в путь Python
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Подготавливаем аргументы для uvicorn
    uvicorn_args = [
        'uvicorn',
        'app.main:app',
        f'--host={args.host}',
        f'--port={args.port}',
    ]
    
    if args.reload:
        uvicorn_args.append('--reload')
        uvicorn_args.append(f'--reload-dir={project_root}/app')
    
    # Запускаем сервер
    print(f"Запуск сервера разработки RentScout на {args.host}:{args.port}")
    if args.reload:
        print("Автоматическая перезагрузка включена")
    
    try:
        subprocess.run(uvicorn_args, cwd=project_root)
    except KeyboardInterrupt:
        print("\nСервер остановлен")
    except Exception as e:
        print(f"Ошибка запуска сервера: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()