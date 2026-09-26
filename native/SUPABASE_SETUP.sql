-- Run once in your own Supabase project's SQL Editor as a project administrator.
-- Never put a service_role key into the desktop client.
create table if not exists public.user_favorites (
    user_id uuid not null references auth.users(id) on delete cascade,
    match_id text not null,
    created_at timestamptz not null default now(),
    primary key (user_id, match_id)
);

alter table public.user_favorites enable row level security;
revoke all on public.user_favorites from anon;
grant select, insert, delete on public.user_favorites to authenticated;

drop policy if exists "read own favorites" on public.user_favorites;
create policy "read own favorites" on public.user_favorites
    for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "add own favorites" on public.user_favorites;
create policy "add own favorites" on public.user_favorites
    for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "remove own favorites" on public.user_favorites;
create policy "remove own favorites" on public.user_favorites
    for delete to authenticated using ((select auth.uid()) = user_id);
