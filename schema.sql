-- ============================================================
-- AI Supply Chain System — Stage 1 Database Schema
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query)
-- ============================================================

-- 1. USERS / PROFILES TABLE
-- Supabase Auth already creates an "auth.users" table for login.
-- This "profiles" table stores extra info linked to that auth user.
create table if not exists profiles (
    id uuid references auth.users on delete cascade primary key,
    full_name text not null,
    role text not null check (role in ('producer', 'merchant', 'customer')),
    region text,
    phone text,
    created_at timestamp with time zone default now()
);

-- 2. PRODUCTS TABLE (listings created by Producers)
create table if not exists products (
    id bigint generated always as identity primary key,
    producer_id uuid references profiles(id) on delete cascade,
    sector text not null,
    product_name text not null,
    quantity numeric not null,
    unit text default 'unit',
    price_birr numeric not null,
    quality_grade text check (quality_grade in ('A', 'B', 'C')),
    region text not null,
    description text,
    is_available boolean default true,
    created_at timestamp with time zone default now()
);

-- 3. ORDERS / TRANSACTIONS TABLE (simple version for Stage 1)
create table if not exists orders (
    id bigint generated always as identity primary key,
    product_id bigint references products(id) on delete cascade,
    buyer_id uuid references profiles(id) on delete cascade,
    quantity_ordered numeric not null,
    total_price_birr numeric not null,
    status text default 'pending' check (status in ('pending','confirmed','completed','cancelled')),
    created_at timestamp with time zone default now()
);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) — Required by Supabase for safety
-- ============================================================

alter table profiles enable row level security;
alter table products enable row level security;
alter table orders enable row level security;

-- Profiles: anyone logged in can read all profiles, but only edit their own
create policy "Public profiles are viewable by everyone"
on profiles for select using (true);

create policy "Users can insert their own profile"
on profiles for insert with check (auth.uid() = id);

create policy "Users can update their own profile"
on profiles for update using (auth.uid() = id);

-- Products: everyone can view, only the producer who owns it can edit/delete
create policy "Products are viewable by everyone"
on products for select using (true);

create policy "Producers can insert their own products"
on products for insert with check (auth.uid() = producer_id);

create policy "Producers can update their own products"
on products for update using (auth.uid() = producer_id);

create policy "Producers can delete their own products"
on products for delete using (auth.uid() = producer_id);

-- Orders: buyers can see their own orders, producers can see orders on their products
create policy "Buyers can view their own orders"
on orders for select using (auth.uid() = buyer_id);

create policy "Buyers can create orders"
on orders for insert with check (auth.uid() = buyer_id);

-- ============================================================
-- DONE. After running this, go to Authentication > Settings
-- and make sure "Email" provider is enabled for signup/login.
-- ============================================================
