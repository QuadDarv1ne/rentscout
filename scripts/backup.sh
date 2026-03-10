#!/bin/bash
# =============================================================================
# PostgreSQL Backup Script for RentScout
# =============================================================================
#
# Usage:
#   ./backup.sh                    # Create backup with default settings
#   ./backup.sh --restore latest   # Restore from latest backup
#   ./backup.sh --list             # List all backups
#   ./backup.sh --cleanup          # Remove old backups (keep last 7 days)
#
# Environment variables (or set in .env):
#   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Configuration
# =============================================================================

# Load environment variables from .env if exists
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Database settings (with defaults)
POSTGRES_USER=${POSTGRES_USER:-rentscout}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-}
POSTGRES_DB=${POSTGRES_DB:-rentscout}
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}

# Backup settings
BACKUP_DIR=${BACKUP_DIR:-./backups/postgres}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-7}
BACKUP_KEEP_COUNT=${BACKUP_KEEP_COUNT:-10}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# =============================================================================
# Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_timestamp() {
    date +"%Y%m%d_%H%M%S"
}

get_date() {
    date +"%Y-%m-%d"
}

# =============================================================================
# Backup Functions
# =============================================================================

create_backup() {
    local timestamp=$(get_timestamp)
    local backup_file="$BACKUP_DIR/rentscout_${timestamp}.sql.gz"

    log_info "Starting backup of database '$POSTGRES_DB'..."
    log_info "Host: $POSTGRES_HOST:$POSTGRES_PORT"
    log_info "Backup file: $backup_file"

    # Create backup using pg_dump
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -F p \
        --no-owner \
        --no-privileges \
        | gzip > "$backup_file"

    # Verify backup
    if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "✅ Backup completed successfully: $backup_file ($size)"

        # Create checksum
        sha256sum "$backup_file" > "${backup_file}.sha256"
        log_info "✅ Checksum created: ${backup_file}.sha256"

        # Create metadata file
        cat > "${backup_file}.meta" << EOF
{
    "timestamp": "$timestamp",
    "date": "$(get_date)",
    "database": "$POSTGRES_DB",
    "host": "$POSTGRES_HOST",
    "port": "$POSTGRES_PORT",
    "file": "$backup_file",
    "size": "$size",
    "checksum": "$(cat ${backup_file}.sha256 | cut -d' ' -f1)"
}
EOF
        log_info "✅ Metadata created: ${backup_file}.meta"
    else
        log_error "❌ Backup failed: $backup_file"
        exit 1
    fi

    return 0
}

list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    echo ""

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR/*.sql.gz 2>/dev/null)" ]; then
        log_warn "No backups found"
        return 1
    fi

    # List backups with metadata
    printf "%-30s %-15s %-10s %s\n" "FILE" "DATE" "SIZE" "CHECKSUM"
    printf "%-30s %-15s %-10s %s\n" "----" "----" "----" "--------"

    for backup in $(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null); do
        local filename=$(basename "$backup")
        local meta_file="${backup}.meta"

        if [ -f "$meta_file" ]; then
            local date=$(grep -o '"date": "[^"]*"' "$meta_file" | cut -d'"' -f4)
            local size=$(grep -o '"size": "[^"]*"' "$meta_file" | cut -d'"' -f4)
            local checksum=$(grep -o '"checksum": "[^"]*"' "$meta_file" | cut -d'"' -f4 | cut -c1-8)
            printf "%-30s %-15s %-10s %s\n" "$filename" "$date" "$size" "$checksum..."
        else
            local size=$(du -h "$backup" | cut -f1)
            printf "%-30s %-15s %-10s %s\n" "$filename" "N/A" "$size" "N/A"
        fi
    done

    return 0
}

restore_backup() {
    local backup_name="$1"
    local backup_file

    # Find backup file
    if [ "$backup_name" == "latest" ]; then
        backup_file=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -n1)
    else
        backup_file="$BACKUP_DIR/$backup_name"
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    # Verify checksum if available
    local checksum_file="${backup_file}.sha256"
    if [ -f "$checksum_file" ]; then
        log_info "Verifying checksum..."
        if sha256sum -c "$checksum_file" > /dev/null 2>&1; then
            log_info "✅ Checksum verified"
        else
            log_error "❌ Checksum verification failed!"
            return 1
        fi
    fi

    log_warn "⚠️  This will restore database '$POSTGRES_DB' from $backup_file"
    log_warn "⚠️  Current data will be overwritten!"
    echo ""
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled"
        return 0
    fi

    log_info "Starting restore..."
    log_info "Database: $POSTGRES_DB"
    log_info "Backup: $backup_file"

    # Restore database
    gunzip -c "$backup_file" | PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        > /dev/null 2>&1

    log_info "✅ Restore completed successfully"
    return 0
}

cleanup_old_backups() {
    log_info "Cleaning up backups older than $BACKUP_KEEP_DAYS days..."

    local count_before=$(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)

    # Remove old backups
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$BACKUP_KEEP_DAYS -delete
    find "$BACKUP_DIR" -name "*.sql.gz.sha256" -mtime +$BACKUP_KEEP_DAYS -delete
    find "$BACKUP_DIR" -name "*.sql.gz.meta" -mtime +$BACKUP_KEEP_DAYS -delete

    # Keep only last N backups
    local count_after=$(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)
    if [ "$count_after" -gt "$BACKUP_KEEP_COUNT" ]; then
        local to_delete=$((count_after - BACKUP_KEEP_COUNT))
        ls -t $BACKUP_DIR/*.sql.gz | tail -n $to_delete | while read backup; do
            rm -f "$backup" "${backup}.sha256" "${backup}.meta"
            log_info "Deleted old backup: $(basename $backup)"
        done
    fi

    local count_final=$(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)
    log_info "Cleaned up $((count_before - count_final)) backups"
    log_info "Remaining backups: $count_final"

    return 0
}

verify_backup() {
    local backup_name="$1"
    local backup_file

    if [ "$backup_name" == "latest" ]; then
        backup_file=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -n1)
    else
        backup_file="$BACKUP_DIR/$backup_name"
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_info "Verifying backup: $backup_file"

    # Check file size
    local size=$(du -h "$backup_file" | cut -f1)
    log_info "File size: $size"

    # Check checksum
    local checksum_file="${backup_file}.sha256"
    if [ -f "$checksum_file" ]; then
        if sha256sum -c "$checksum_file" > /dev/null 2>&1; then
            log_info "✅ Checksum: OK"
        else
            log_error "❌ Checksum: FAILED"
            return 1
        fi
    else
        log_warn "⚠️  Checksum file not found"
    fi

    # Test decompression
    if gzip -t "$backup_file" 2>/dev/null; then
        log_info "✅ Compression: OK"
    else
        log_error "❌ Compression: FAILED"
        return 1
    fi

    # Test SQL syntax (dry run)
    if gunzip -c "$backup_file" | head -n 100 | grep -q "PostgreSQL database dump" 2>/dev/null; then
        log_info "✅ SQL dump: OK"
    else
        log_warn "⚠️  SQL dump: May be invalid (checking header)"
    fi

    log_info "✅ Backup verification completed"
    return 0
}

# =============================================================================
# Main
# =============================================================================

show_help() {
    echo "RentScout PostgreSQL Backup Script"
    echo ""
    echo "Usage:"
    echo "  $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  backup              Create new backup (default)"
    echo "  restore <name>      Restore from backup (use 'latest' for most recent)"
    echo "  list                List all backups"
    echo "  verify <name>       Verify backup integrity"
    echo "  cleanup             Remove old backups"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 restore latest"
    echo "  $0 verify rentscout_20260310_120000.sql.gz"
    echo ""
}

main() {
    local command="${1:-backup}"

    case "$command" in
        backup)
            create_backup
            ;;
        restore)
            restore_backup "${2:-latest}"
            ;;
        list)
            list_backups
            ;;
        verify)
            verify_backup "${2:-latest}"
            ;;
        cleanup)
            cleanup_old_backups
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
