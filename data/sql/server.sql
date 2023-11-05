create database lost;
\c lost;

create extension plpython3u;
create extension postgis;
create extension "uuid-ossp";

create function public.update_timestamp() returns trigger
    language plpgsql
    as $$
begin
    NEW.modified = now();
    return NEW;
end;
$$;

create table shape (
    id         serial                       primary key,
    uri        text                         not null,
    geometries geometry(GeometryCollection) not null,
    created    timestamptz                  default now() not null,
    modified   timestamptz                  default now() not null,
    attrs      jsonb                        not null default '{}'::jsonb
);

create        index shape_geom_idx  on shape using gist(geometries);
create unique index shape_uri_idx   on shape using btree(uri);
create        index shape_attrs_idx on shape using gin(attrs);

create trigger update_shape_timestamp
    before update on shape
    for each row execute function public.update_timestamp();


create table mapping (
    id       serial       primary key,
    shape    integer      references shape(id) on delete set null,
    srv      text         not null,
    created  timestamptz  default now() not null,
    modified timestamptz  default now() not null,
    attrs    jsonb        not null default '{}'::jsonb
);

create index mapping_attrs_idx on shape using gin(attrs);

create trigger update_mapping_timestamp
    before update on mapping
    for each row execute function public.update_timestamp();


revoke all on schema public from public;
grant usage on schema public to public;

create role "lost-server"   with login;
create role "lost-resolver" with login;

grant all on database lost                  to "lost-server";
grant all on all tables    in schema public to "lost-server";
grant all on all sequences in schema public to "lost-server";

grant all on database lost                  to "lost-resolver";
grant all on all tables    in schema public to "lost-resolver";
grant all on all sequences in schema public to "lost-resolver";
