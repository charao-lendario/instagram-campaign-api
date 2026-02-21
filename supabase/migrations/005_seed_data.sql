-- ============================================================================
-- Migration 005: Seed Data
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Initial seed data for the two monitored candidates.
-- Depends on: 002_create_tables.sql
-- PRD: CON-002 (exactly 2 profiles for MVP)
-- ============================================================================

-- Insert monitored candidates
-- Using ON CONFLICT to make this script idempotent (safe to re-run)
INSERT INTO candidates (username, display_name, is_active)
VALUES
    ('charlles.evangelista', 'Charlles Evangelista', TRUE),
    ('delegadasheila', 'Delegada Sheila', TRUE)
ON CONFLICT (username) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();
