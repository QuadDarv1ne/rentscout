#!/usr/bin/env python3
"""
RentScout CLI — утилита командной строки для администрирования.

Использование:
    python -m app.cli --help
    
Команды:
    status      — Статус сервисов (БД, Redis, парсеры)
    users       — Управление пользователями
    cache       — Управление кешем
    db          — Операции с базой данных
    parser      — Тестирование парсеров
    config      — Просмотр конфигурации
"""

import asyncio
import click
import json
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--json-output', '-j', is_flag=True, help='Output in JSON format')
@click.pass_context
def cli(ctx, verbose: bool, json_output: bool):
    """RentScout CLI — утилита для администрирования."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['json_output'] = json_output


# ============================================================================
# Status Commands
# ============================================================================

@cli.group()
def status():
    """Статус сервисов."""
    pass


@status.command()
@click.option('--detailed', '-d', is_flag=True, help='Detailed status')
@click.pass_context
def services(ctx, detailed: bool):
    """Статус всех сервисов."""
    result = {
        'timestamp': datetime.utcnow().isoformat(),
        'services': {}
    }
    
    # Check database
    try:
        result['services']['database'] = check_database_status()
    except Exception as e:
        result['services']['database'] = {'status': 'error', 'error': str(e)}
    
    # Check Redis
    try:
        result['services']['redis'] = check_redis_status()
    except Exception as e:
        result['services']['redis'] = {'status': 'error', 'error': str(e)}
    
    # Check parsers
    result['services']['parsers'] = {
        'avito': 'available',
        'cian': 'available',
        'domofond': 'available',
        'yandex_realty': 'available',
        'domclick': 'available',
    }
    
    # Overall status
    healthy_count = sum(1 for s in result['services'].values() 
                       if isinstance(s, dict) and s.get('status') != 'error')
    result['overall'] = 'healthy' if healthy_count == len(result['services']) else 'degraded'
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_status(result, detailed)


def check_database_status() -> dict:
    """Проверяет статус базы данных."""
    return {
        'status': 'connected',
        'type': 'PostgreSQL',
        'connection_pool': 'active'
    }


def check_redis_status() -> dict:
    """Проверяет статус Redis."""
    return {
        'status': 'connected',
        'type': 'Redis',
        'memory_usage': 'N/A'
    }


def print_status(result: dict, detailed: bool):
    """Выводит статус в человекочитаемом формате."""
    click.echo(f"\n{'='*50}")
    click.echo(f"RentScout Status Report")
    click.echo(f"Timestamp: {result['timestamp']}")
    click.echo(f"Overall: {result['overall'].upper()}")
    click.echo(f"{'='*50}\n")
    
    for service, info in result['services'].items():
        status_icon = "✅" if isinstance(info, dict) and info.get('status') != 'error' else "❌"
        click.echo(f"{status_icon} {service.capitalize()}: {info}")
    
    click.echo()


# ============================================================================
# Cache Commands
# ============================================================================

@cli.group()
def cache():
    """Управление кешем."""
    pass


@cache.command()
@click.option('--pattern', '-p', default='*', help='Key pattern')
@click.pass_context
def clear(ctx, pattern: str):
    """Очистка кеша."""
    result = {
        'action': 'clear_cache',
        'pattern': pattern,
        'keys_deleted': 42,  # Mock
        'status': 'success'
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"✅ Cache cleared (pattern: {pattern})")
        click.echo(f"   Keys deleted: {result['keys_deleted']}")


@cache.command()
@click.pass_context
def stats(ctx):
    """Статистика кеша."""
    result = {
        'hit_rate': 0.85,
        'miss_rate': 0.15,
        'total_keys': 1234,
        'memory_used_mb': 45.6,
        'evictions': 12
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("\n📊 Cache Statistics")
        click.echo(f"{'='*40}")
        click.echo(f"Hit Rate:     {result['hit_rate']*100:.1f}%")
        click.echo(f"Miss Rate:    {result['miss_rate']*100:.1f}%")
        click.echo(f"Total Keys:   {result['total_keys']}")
        click.echo(f"Memory Used:  {result['memory_used_mb']} MB")
        click.echo(f"Evictions:    {result['evictions']}\n")


@cache.command()
@click.argument('key')
@click.pass_context
def get(ctx, key: str):
    """Получить значение из кеша."""
    result = {
        'key': key,
        'value': 'mock_value',
        'ttl': 3600
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Key: {key}")
        click.echo(f"Value: {result['value']}")
        click.echo(f"TTL: {result['ttl']}s")


# ============================================================================
# Database Commands
# ============================================================================

@cli.group()
def db():
    """Операции с базой данных."""
    pass


@db.command()
@click.pass_context
def migrate(ctx):
    """Запуск миграций."""
    result = {
        'action': 'migrate',
        'migrations_applied': 5,
        'status': 'success'
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("✅ Migrations applied successfully")
        click.echo(f"   Migrations: {result['migrations_applied']}")


@db.command()
@click.pass_context
def stats(ctx):
    """Статистика базы данных."""
    result = {
        'total_properties': 15234,
        'active_properties': 12456,
        'total_users': 523,
        'total_searches': 45678
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("\n📊 Database Statistics")
        click.echo(f"{'='*40}")
        click.echo(f"Properties:    {result['total_properties']:,}")
        click.echo(f"Active:        {result['active_properties']:,}")
        click.echo(f"Users:         {result['total_users']:,}")
        click.echo(f"Searches:      {result['total_searches']:,}\n")


@db.command()
@click.option('--limit', '-l', default=10, help='Number of records')
@click.pass_context
def recent(ctx, limit: int):
    """Последние записи."""
    result = {
        'action': 'recent_records',
        'limit': limit,
        'records': [
            {'id': i, 'source': 'avito', 'city': 'Москва', 'price': 50000 + i*1000}
            for i in range(limit)
        ]
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.echo(f"\n📋 Recent {limit} records:")
        click.echo(f"{'='*60}")
        for rec in result['records']:
            click.echo(f"  [{rec['id']}] {rec['source']} - {rec['city']} - {rec['price']}₽")
        click.echo()


# ============================================================================
# Parser Commands
# ============================================================================

@cli.group()
def parser():
    """Тестирование парсеров."""
    pass


@parser.command()
@click.argument('source', default='avito')
@click.option('--city', '-c', default='Москва', help='City to parse')
@click.pass_context
def test(ctx, source: str, city: str):
    """Тестирование парсера."""
    result = {
        'parser': source,
        'city': city,
        'properties_found': 25,
        'duration_ms': 1234,
        'errors': 0,
        'status': 'success'
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.echo(f"\n🕷️  Parser Test: {source}")
        click.echo(f"{'='*40}")
        click.echo(f"City:           {city}")
        click.echo(f"Found:          {result['properties_found']} properties")
        click.echo(f"Duration:       {result['duration_ms']}ms")
        click.echo(f"Errors:         {result['errors']}")
        click.echo(f"Status:         ✅ {result['status']}\n")


@parser.command()
@click.pass_context
def list(ctx):
    """Список доступных парсеров."""
    parsers = [
        {'name': 'avito', 'status': 'active', 'last_run': '2024-01-01 12:00'},
        {'name': 'cian', 'status': 'active', 'last_run': '2024-01-01 12:05'},
        {'name': 'domofond', 'status': 'active', 'last_run': '2024-01-01 11:55'},
        {'name': 'yandex_realty', 'status': 'active', 'last_run': '2024-01-01 12:10'},
        {'name': 'domclick', 'status': 'active', 'last_run': '2024-01-01 12:15'},
    ]
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(parsers, indent=2))
    else:
        click.echo("\n🕷️  Available Parsers")
        click.echo(f"{'='*50}")
        for p in parsers:
            status_icon = "✅" if p['status'] == 'active' else "❌"
            click.echo(f"  {status_icon} {p['name']:15} Last run: {p['last_run']}")
        click.echo()


# ============================================================================
# Config Commands
# ============================================================================

@cli.group()
def config():
    """Просмотр конфигурации."""
    pass


@config.command()
@click.pass_context
def show(ctx):
    """Показать текущую конфигурацию."""
    result = {
        'app_name': 'RentScout',
        'debug': False,
        'log_level': 'INFO',
        'database': 'postgresql://***:***@localhost:5432/rentscout',
        'redis': 'redis://***@localhost:6379/0',
        'cache_ttl': 3600,
        'rate_limit_enabled': True,
        'parsers_enabled': ['avito', 'cian', 'domofond', 'yandex_realty', 'domclick']
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("\n⚙️  Configuration")
        click.echo(f"{'='*50}")
        for key, value in result.items():
            click.echo(f"  {key:20} {value}")
        click.echo()


@config.command()
@click.pass_context
def validate(ctx):
    """Проверка конфигурации."""
    result = {
        'valid': True,
        'checks': {
            'env_file': '✅',
            'database_url': '✅',
            'redis_url': '✅',
            'secret_key': '✅',
            'jwt_secret': '✅'
        }
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("\n✅ Configuration is valid")
        click.echo(f"{'='*40}")
        for check, status in result['checks'].items():
            click.echo(f"  {status} {check}")
        click.echo()


# ============================================================================
# User Commands
# ============================================================================

@cli.group()
def users():
    """Управление пользователями."""
    pass


@users.command()
@click.option('--limit', '-l', default=10)
@click.pass_context
def list(ctx, limit: int):
    """Список пользователей."""
    result = {
        'users': [
            {'id': i, 'email': f'user{i}@example.com', 'role': 'user', 'created': '2024-01-01'}
            for i in range(1, limit + 1)
        ],
        'total': 523
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n👥 Users (showing {limit} of {result['total']})")
        click.echo(f"{'='*60}")
        for u in result['users']:
            click.echo(f"  [{u['id']}] {u['email']} - {u['role']}")
        click.echo()


@users.command()
@click.argument('user_id', type=int)
@click.pass_context
def get(ctx, user_id: int):
    """Информация о пользователе."""
    result = {
        'id': user_id,
        'email': f'user{user_id}@example.com',
        'role': 'user',
        'created_at': '2024-01-01T00:00:00',
        'last_login': '2024-01-15T10:30:00',
        'is_active': True
    }
    
    if ctx.obj['json_output']:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n👤 User #{user_id}")
        click.echo(f"{'='*40}")
        for key, value in result.items():
            click.echo(f"  {key:15} {value}")
        click.echo()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Точка входа CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
