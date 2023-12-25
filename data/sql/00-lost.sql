create database lost;
\c lost;

create extension plpython3u;
create extension postgis;
create extension "uuid-ossp";

create function update_timestamp() returns trigger
    language plpgsql
    as $$
begin
    NEW.modified = current_timestamp;
    return NEW;
end;
$$;

create table shape (
    id         serial                              primary key,
    uri        text                                not null,
    geometries public.geometry(GeometryCollection) not null,
    created    timestamptz                         not null default current_timestamp,
    modified   timestamptz                         not null default current_timestamp,
    attrs      jsonb                               not null default '{}'::jsonb
);

create        index shape_geom_idx  on shape using gist(geometries);
create unique index shape_uri_idx   on shape using btree(uri);
create        index shape_attrs_idx on shape using gin(attrs);

create trigger update_shape_timestamp
    before update on shape
    for each row execute function update_timestamp();

create schema server;
set schema 'server';

create table mapping (
    id       serial       primary key,
    shape    integer      references public.shape(id) on delete set null,
    srv      text         not null,
    created  timestamptz  not null default current_timestamp,
    modified timestamptz  not null default current_timestamp,
    attrs    jsonb        not null default '{}'::jsonb
);

create index mapping_attrs_idx on mapping using gin(attrs);

create trigger update_mapping_timestamp
    before update on mapping
    for each row execute function public.update_timestamp();

create schema resolver;
set schema 'resolver';


create type feature_t as enum (
    'Area',
    'Building',
    'Floor',
    'Apartment',
    'Room',
    'Way',
    'Point'
);


create table feature (
    id             serial      primary key,
    type           feature_t,
    name           text        not null,
    parent         integer     references feature(id),
    vertical_range text,
    indoor         bool        default 't',
    shape          integer     references public.shape(id) on delete set null,
    control_points text[],
    created        timestamptz not null default current_timestamp,
    image          text,
    transform      text,
    attrs          jsonb       not null default '{}'::jsonb
);


create table control_point (
    id          serial primary key,
    coordinates public.geometry(point)
);


create table coordinate_transform (
    id            serial primary key,
    control_links jsonb  not null
);


create table raster_image (
    id             serial       primary key,
    name           text         not null,
    data           bytea        not null,
    uploaded       timestamptz  not null default current_timestamp,
    last_modified  timestamptz,
    width          integer      not null,
    height         integer      not null,
    size           integer      not null,
    file_name      text         not null
);


-- Given a feature id, lookup the feature's shape by recursively traversing the
-- tree of features up towards the root.
create or replace function find_shape(feature_id integer) returns integer as $$
begin
    return (
        with recursive parent as (
            select id, shape from feature
            union all
            select f.id as id, p.shape
                from feature as f, parent as p
                where f.parent = p.id)
            select shape from feature
            where feature.id = feature_id
            and shape is not null
        union all
            select parent.shape
            from feature, parent
            where
                feature.id = feature_id
                and feature.parent = parent.id
                and parent.shape is not null
        limit 1
    );
end;
$$ language plpgsql;


-- Compute the location uncertainty polygon for the given center point and
-- radius in meters. If radius is not null, a polygon approximating the
-- uncertainty circle with the given center and radius will be returned. If
-- radius is null, the center point itself will be returned without any
-- transformations.
create or replace function uncertainty_circle(center public.geometry(point), radius real) returns public.geometry as $$
begin
    if radius is null then
        return center;
    else
        -- Transform the center point to WebMercator so that we can create a
        -- buffer for with with a radius value in meters. Then transform the
        -- resulting polygon back to 4326
        return 
            public.ST_Transform(public.ST_Buffer(public.ST_Transform(center, 900913), radius), 4326);
    end if;
end;
$$ language plpgsql;


create function projective_transform(matrix double precision[][], coordinates double precision[]) returns double precision[] as $$
declare
    d double precision;
begin
    -- FIXME: Handle potential division by zero
    d := $1[3][1] * $2[1] + $1[3][2] * $2[2] + $1[3][3];
    return array [
        ($1[1][1] * $2[1] + $1[1][2] * $2[2] + $1[1][3]) / d,
        ($1[2][1] * $2[1] + $1[2][2] * $2[2] + $1[2][3]) / d
    ];
end;
$$ language plpgsql;


create role "lost-server" with login;
grant all on schema server to "lost-server";

create role "lost-resolver" with login;
grant all on schema resolver to "lost-resolver";

grant all on database lost                  to "lost-server";
grant all on all tables    in schema public to "lost-server";
grant all on all sequences in schema public to "lost-server";
grant all on all tables    in schema server to "lost-server";
grant all on all sequences in schema server to "lost-server";

grant all on database lost                  to "lost-resolver";
grant all on all tables    in schema public to "lost-resolver";
grant all on all sequences in schema public to "lost-resolver";
grant all on all tables    in schema resolver to "lost-resolver";
grant all on all sequences in schema resolver to "lost-resolver";
