"""
Тесты для CLI утилиты.
"""

import pytest
from click.testing import CliRunner
from app.cli import cli


@pytest.fixture
def runner():
    """Фикстура CLI runner."""
    return CliRunner()


class TestCLI:
    """Тесты основной CLI."""

    def test_cli_help(self, runner):
        """Тест help команды."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'RentScout CLI' in result.output
        assert 'status' in result.output
        assert 'cache' in result.output
        assert 'db' in result.output
        assert 'parser' in result.output
        assert 'config' in result.output
        assert 'users' in result.output

    def test_cli_verbose_flag(self, runner):
        """Тест флага verbose."""
        result = runner.invoke(cli, ['--verbose', 'status', 'services'])
        assert result.exit_code == 0

    def test_cli_json_output(self, runner):
        """Тест JSON вывода."""
        result = runner.invoke(cli, ['--json-output', 'status', 'services'])
        assert result.exit_code == 0
        import json
        # Проверяем что вывод валидный JSON
        data = json.loads(result.output)
        assert 'services' in data


class TestStatusCommands:
    """Тесты команд статуса."""

    def test_status_services(self, runner):
        """Тест статуса сервисов."""
        result = runner.invoke(cli, ['status', 'services'])
        assert result.exit_code == 0
        assert 'RentScout Status Report' in result.output
        assert 'Overall' in result.output

    def test_status_services_json(self, runner):
        """Тест статуса сервисов в JSON."""
        result = runner.invoke(cli, ['--json-output', 'status', 'services'])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert 'services' in data
        assert 'timestamp' in data


class TestCacheCommands:
    """Тесты команд кеша."""

    def test_cache_clear(self, runner):
        """Тест очистки кеша."""
        result = runner.invoke(cli, ['cache', 'clear'])
        assert result.exit_code == 0
        assert 'Cache cleared' in result.output or '"status": "success"' in result.output

    def test_cache_clear_pattern(self, runner):
        """Тест очистки кеша с паттерном."""
        result = runner.invoke(cli, ['cache', 'clear', '--pattern', 'test:*'])
        assert result.exit_code == 0

    def test_cache_stats(self, runner):
        """Тест статистики кеша."""
        result = runner.invoke(cli, ['cache', 'stats'])
        assert result.exit_code == 0
        assert 'Cache Statistics' in result.output or '"hit_rate"' in result.output

    def test_cache_get(self, runner):
        """Тест получения значения из кеша."""
        result = runner.invoke(cli, ['cache', 'get', 'test_key'])
        assert result.exit_code == 0
        assert 'test_key' in result.output


class TestDBCommands:
    """Тесты команд базы данных."""

    def test_db_migrate(self, runner):
        """Тест миграций."""
        result = runner.invoke(cli, ['db', 'migrate'])
        assert result.exit_code == 0
        assert 'Migrations applied' in result.output or '"migrations_applied"' in result.output

    def test_db_stats(self, runner):
        """Тест статистики БД."""
        result = runner.invoke(cli, ['db', 'stats'])
        assert result.exit_code == 0
        assert 'Database Statistics' in result.output or '"total_properties"' in result.output

    def test_db_recent(self, runner):
        """Тест последних записей."""
        result = runner.invoke(cli, ['db', 'recent'])
        assert result.exit_code == 0
        assert 'Recent' in result.output or '"records"' in result.output

    def test_db_recent_limit(self, runner):
        """Тест лимита записей."""
        result = runner.invoke(cli, ['db', 'recent', '--limit', '5'])
        assert result.exit_code == 0


class TestParserCommands:
    """Тесты команд парсеров."""

    def test_parser_test(self, runner):
        """Тест тестирования парсера."""
        result = runner.invoke(cli, ['parser', 'test', 'avito'])
        assert result.exit_code == 0
        assert 'Parser Test' in result.output or '"parser"' in result.output

    def test_parser_test_city(self, runner):
        """Тест парсера с городом."""
        result = runner.invoke(cli, ['parser', 'test', 'cian', '--city', 'Санкт-Петербург'])
        assert result.exit_code == 0
        assert 'Санкт-Петербург' in result.output or '"city"' in result.output

    def test_parser_list(self, runner):
        """Тест списка парсеров."""
        result = runner.invoke(cli, ['parser', 'list'])
        assert result.exit_code == 0
        assert 'Available Parsers' in result.output or '"avito"' in result.output


class TestConfigCommands:
    """Тесты команд конфигурации."""

    def test_config_show(self, runner):
        """Тест показа конфигурации."""
        result = runner.invoke(cli, ['config', 'show'])
        assert result.exit_code == 0
        assert 'Configuration' in result.output or '"app_name"' in result.output

    def test_config_validate(self, runner):
        """Тест проверки конфигурации."""
        result = runner.invoke(cli, ['config', 'validate'])
        assert result.exit_code == 0
        assert 'valid' in result.output.lower() or '"valid"' in result.output


class TestUsersCommands:
    """Тесты команд пользователей."""

    def test_users_list(self, runner):
        """Тест списка пользователей."""
        result = runner.invoke(cli, ['users', 'list'])
        assert result.exit_code == 0
        assert 'Users' in result.output or '"users"' in result.output

    def test_users_list_limit(self, runner):
        """Тест лимита пользователей."""
        result = runner.invoke(cli, ['users', 'list', '--limit', '5'])
        assert result.exit_code == 0

    def test_users_get(self, runner):
        """Тест получения пользователя."""
        result = runner.invoke(cli, ['users', 'get', '123'])
        assert result.exit_code == 0
        assert '123' in result.output or '"id": 123' in result.output


class TestCLIIntegration:
    """Интеграционные тесты CLI."""

    def test_full_workflow(self, runner):
        """Тест полного workflow."""
        # Status check
        result = runner.invoke(cli, ['status', 'services'])
        assert result.exit_code == 0
        
        # Cache stats
        result = runner.invoke(cli, ['cache', 'stats'])
        assert result.exit_code == 0
        
        # DB stats
        result = runner.invoke(cli, ['db', 'stats'])
        assert result.exit_code == 0
        
        # Config validate
        result = runner.invoke(cli, ['config', 'validate'])
        assert result.exit_code == 0

    def test_json_output_all_commands(self, runner):
        """Тест JSON вывода для всех команд."""
        commands = [
            ['--json-output', 'status', 'services'],
            ['--json-output', 'cache', 'stats'],
            ['--json-output', 'db', 'stats'],
            ['--json-output', 'config', 'show'],
        ]
        
        import json
        
        for cmd in commands:
            result = runner.invoke(cli, cmd)
            assert result.exit_code == 0, f"Command {cmd} failed: {result.output}"
            # Проверяем что вывод валидный JSON
            try:
                data = json.loads(result.output)
                assert isinstance(data, (dict, list))
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON output for {cmd}: {result.output}")
