-- Synthetic regression fixture: five tables, 23 columns, four physical FKs.
CREATE SCHEMA crm;
CREATE TABLE crm.company (
    id bigint PRIMARY KEY,
    name text NOT NULL,
    tax_id varchar(12),
    created_at timestamptz DEFAULT now()
);
CREATE TABLE crm.employee (
    id bigint PRIMARY KEY,
    manager_id bigint REFERENCES crm.employee(id),
    name text NOT NULL,
    email text,
    active boolean DEFAULT true
);
CREATE TABLE crm.deal (
    id bigint PRIMARY KEY,
    company_id bigint NOT NULL REFERENCES crm.company(id),
    owner_id bigint REFERENCES crm.employee(id),
    title text NOT NULL,
    amount numeric(12,2),
    status text NOT NULL
);
CREATE TABLE crm.activity (
    id bigint NOT NULL,
    deal_id bigint REFERENCES crm.deal(id),
    happened_at timestamptz NOT NULL,
    body text,
    PRIMARY KEY (id, happened_at)
) PARTITION BY RANGE (happened_at);
CREATE TABLE crm.activity_2000 PARTITION OF crm.activity
    FOR VALUES FROM ('2000-01-01') TO ('2001-01-01');
CREATE TABLE crm.note (
    id bigint PRIMARY KEY,
    company_id bigint,
    body text NOT NULL,
    created_at timestamptz DEFAULT now()
);
COMMENT ON COLUMN crm.note.company_id IS 'Логическая ссылка на компанию без FK';
