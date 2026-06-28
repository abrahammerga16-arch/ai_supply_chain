-- ============================================================
-- Stage 2 — Migration: Add Merchant Preference Fields
-- Run this in Supabase SQL Editor AFTER schema.sql (Stage 1)
-- This is additive — it does not break anything from Stage 1.
-- ============================================================

-- Add merchant-specific preference columns to profiles table.
-- These are only filled in when role = 'merchant' and are used
-- by the Smart Matching model to score compatibility.

alter table profiles add column if not exists preferred_sector text;
alter table profiles add column if not exists preferred_product text;
alter table profiles add column if not exists max_budget_birr numeric;
alter table profiles add column if not exists preferred_quality text;
alter table profiles add column if not exists needs_delivery boolean default false;
alter table profiles add column if not exists payment_method text;
alter table profiles add column if not exists years_in_business numeric default 1;
alter table profiles add column if not exists rating numeric default 4.0;
alter table profiles add column if not exists total_transactions numeric default 0;
alter table profiles add column if not exists return_rate numeric default 0.05;
alter table profiles add column if not exists is_verified boolean default true;

-- Also add a few producer-side fields used by the matching model
-- that weren't in the Stage 1 schema (defaults keep old rows valid)
alter table profiles add column if not exists years_experience numeric default 3;
alter table profiles add column if not exists delivery_available boolean default true;

-- ============================================================
-- DONE. After running this, merchants will see extra fields
-- on their profile/signup form to fill in their buying preferences.
-- ============================================================
