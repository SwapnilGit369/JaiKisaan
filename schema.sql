create extension if not exists pgcrypto;

create table if not exists farmers (
  id uuid primary key default gen_random_uuid(),
  mobile text unique not null,
  name text,
  village text default 'Khalghat',
  created_at timestamptz default now()
);

create table if not exists fields (
  id uuid primary key default gen_random_uuid(),
  farmer_id uuid not null references farmers(id) on delete cascade,
  name text not null,
  area_bigha numeric not null check (area_bigha > 0),
  soil_type text default 'Heavy Black Soil',
  created_at timestamptz default now()
);

create table if not exists crop_cycles (
  id uuid primary key default gen_random_uuid(),
  field_id uuid not null references fields(id) on delete cascade,
  crop text not null,
  variety text,
  sowing_date date not null,
  status text not null default 'active' check (status in ('active','harvested')),
  harvested_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists farm_events (
  id uuid primary key default gen_random_uuid(),
  crop_cycle_id uuid not null references crop_cycles(id) on delete cascade,
  event_type text not null,
  event_date date not null default current_date,
  note text,
  created_at timestamptz default now()
);

create table if not exists ai_chats (
  id uuid primary key default gen_random_uuid(),
  crop_cycle_id uuid references crop_cycles(id) on delete cascade,
  farmer_id uuid references farmers(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  message text not null,
  created_at timestamptz default now()
);

create index if not exists idx_fields_farmer on fields(farmer_id);
create index if not exists idx_crop_cycles_field on crop_cycles(field_id);
create index if not exists idx_crop_cycles_status on crop_cycles(status);
create index if not exists idx_events_cycle on farm_events(crop_cycle_id);
