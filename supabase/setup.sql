-- 117万分の1 競走馬版: 「みんなの結果」用のテーブルと関数
-- Supabase の SQL Editor に全部貼って、Run を押してください。何度実行しても大丈夫です。

create table if not exists public.plays (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  device     text not null check (char_length(device) between 16 and 64),   -- 端末ごとの合言葉(公開しない)
  run_id     text not null check (char_length(run_id) between 4 and 40),
  nick       text not null check (char_length(nick) between 1 and 12),
  horse      text not null check (char_length(horse) between 1 and 9),
  country    text not null check (char_length(country) between 1 and 20),
  breed      text not null check (char_length(breed) between 1 and 20),
  headline   text not null check (char_length(headline) between 1 and 20),
  sub        text not null default '' check (char_length(sub) <= 40),
  rarity     text not null check (rarity in ('g1','g2','g3','l','n')),
  p          double precision not null check (p > 0 and p <= 1),
  unique (device, run_id)
);
create index if not exists plays_created_idx on public.plays (created_at desc);
create index if not exists plays_p_idx on public.plays (p asc);

alter table public.plays enable row level security;
drop policy if exists "anyone can read" on public.plays;
create policy "anyone can read" on public.plays for select to anon, authenticated using (true);

-- 直接の書きこみは禁止。読めるのは公開してよい列だけ(device は読めない)
revoke all on table public.plays from anon, authenticated;
grant select (id, created_at, run_id, nick, horse, country, breed, headline, sub, rarity, p)
  on public.plays to anon, authenticated;

-- 結果を載せる(同じ結果をもう一度送ると、ニックネームと馬名だけ書き換わる)
create or replace function public.post_play(
  p_device text, p_run text, p_nick text, p_horse text, p_country text,
  p_breed text, p_headline text, p_sub text, p_rarity text, p_p double precision)
returns void language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from plays where device = p_device and created_at > now() - interval '10 minutes') >= 20 then
    raise exception 'rate_limited';
  end if;
  if (select count(*) from plays where created_at > now() - interval '1 minute') >= 300 then
    raise exception 'busy';
  end if;
  insert into plays (device, run_id, nick, horse, country, breed, headline, sub, rarity, p)
  values (p_device, p_run,
          regexp_replace(btrim(p_nick), '[[:cntrl:]]', '', 'g'),
          regexp_replace(btrim(p_horse), '[[:cntrl:]]', '', 'g'),
          p_country, p_breed, p_headline, coalesce(p_sub, ''), p_rarity, p_p)
  on conflict (device, run_id) do update set nick = excluded.nick, horse = excluded.horse;
end $$;

-- 集計(人数・頭数・レア度ごとの数)
create or replace function public.board_stats()
returns json language sql stable security definer set search_path = public as $$
  select json_build_object(
    'total', count(*), 'players', count(distinct device),
    'g1', count(*) filter (where rarity = 'g1'), 'g2', count(*) filter (where rarity = 'g2'),
    'g3', count(*) filter (where rarity = 'g3'), 'l',  count(*) filter (where rarity = 'l'),
    'n',  count(*) filter (where rarity = 'n'))
  from plays;
$$;

revoke all on function public.post_play(text,text,text,text,text,text,text,text,text,double precision) from public;
revoke all on function public.board_stats() from public;
grant execute on function public.post_play(text,text,text,text,text,text,text,text,text,double precision) to anon, authenticated;
grant execute on function public.board_stats() to anon, authenticated;
