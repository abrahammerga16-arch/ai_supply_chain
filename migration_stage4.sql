-- ============================================================
-- Stage 4 — Migration: Add Fraud Detection Fields
-- Run this in Supabase SQL Editor AFTER schema.sql and migration_stage2.sql
-- This is additive — it does not break anything from earlier stages.
-- ============================================================

-- Add fraud-scoring columns to the orders table.
-- These are filled in automatically by the AI fraud model
-- every time an order is placed.

alter table orders add column if not exists fraud_risk_level text default 'Unknown';
alter table orders add column if not exists fraud_probability numeric default 0;

-- ============================================================
-- DONE. After running this, every new order will be tagged
-- with a Low/Medium/High fraud risk level automatically.
-- ============================================================
