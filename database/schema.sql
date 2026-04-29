CREATE TABLE IF NOT EXISTS organizations (
    bin VARCHAR(12) PRIMARY KEY,
    name TEXT,
    is_customer BOOLEAN DEFAULT FALSE,
    is_supplier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO organizations (bin) VALUES 
('000740001307'), ('020240002363'), ('020440003656'), ('030440003698'), 
('050740004819'), ('051040005150'), ('100140011059'), ('120940001946'), 
('140340016539'), ('150540000186'), ('171041003124'), ('210240019348'), 
('210240033968'), ('210941010761'), ('230740013340'), ('231040023028'), 
('780140000023'), ('900640000128'), ('940740000911'), ('940940000384'), 
('960440000220'), ('970940001378'), ('971040001050'), ('980440001034'), 
('981140001551'), ('990340005977'), ('990740002243')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS contracts (
    contract_id_sys VARCHAR(128) PRIMARY KEY,
    customer_bin VARCHAR(12) REFERENCES organizations(bin),
    supplier_bin VARCHAR(12),
    contract_sum NUMERIC,
    sign_date DATE,
    description TEXT,
    trade_method_id INTEGER,
    status_id INTEGER,
    fin_year INTEGER,
    source_url TEXT,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lots (
    id BIGINT PRIMARY KEY,
    lotNumber TEXT,
    refLotStatusId INTEGER,
    lastUpdateDate TIMESTAMPTZ,
    unionLots INTEGER,
    count NUMERIC,
    amount NUMERIC,
    nameRu TEXT,
    nameKz TEXT,
    descriptionRu TEXT,
    descriptionKz TEXT,
    customerId INTEGER,
    customerBin VARCHAR(12),
    customerNameRu TEXT,
    customerNameKz TEXT,
    trdBuyNumberAnno TEXT,
    trdBuyId BIGINT,
    dumping INTEGER,
    refTradeMethodsId INTEGER,
    refBuyTradeMethodsId INTEGER,
    psdSign INTEGER,
    consultingServices INTEGER,
    pointList INTEGER[],
    enstruList INTEGER[],
    plnPointKatoList TEXT[],
    singlOrgSign INTEGER,
    isLightIndustry INTEGER,
    isConstructionWork INTEGER,
    disablePersonId INTEGER,
    isDeleted INTEGER,
    systemId INTEGER,
    indexDate TIMESTAMPTZ,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trade_methods (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS contract_statuses (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY,
    code VARCHAR(50),
    name TEXT
);

CREATE TABLE IF NOT EXISTS enstru_catalog (
    code VARCHAR(50) PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS subjects (
    bin VARCHAR(12) PRIMARY KEY,
    pid INTEGER,
    iin VARCHAR(20),
    inn VARCHAR(20),
    unp VARCHAR(20),
    name TEXT,
    name_ru TEXT,
    name_kz TEXT,
    full_name TEXT,
    full_name_ru TEXT,
    full_name_kz TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    customer BOOLEAN DEFAULT FALSE,
    organizer BOOLEAN DEFAULT FALSE,
    supplier BOOLEAN DEFAULT FALSE,
    type_supplier INTEGER,
    country_code VARCHAR(10),
    kato_list TEXT,
    last_update_date TIMESTAMPTZ,
    address TEXT,
    kato_code VARCHAR(50),
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS announcements (
    id BIGINT PRIMARY KEY,
    numberAnno TEXT,
    nameRu TEXT,
    nameKz TEXT,
    totalSum NUMERIC,
    countLots INTEGER,
    refTradeMethodsId INTEGER,
    refSubjectTypeId INTEGER,
    customerBin VARCHAR(12),
    customerPid INTEGER,
    customerNameKz TEXT,
    customerNameRu TEXT,
    orgBin VARCHAR(12),
    orgPid INTEGER,
    orgNameKz TEXT,
    orgNameRu TEXT,
    refBuyStatusId INTEGER,
    startDate TIMESTAMPTZ,
    repeatStartDate TIMESTAMPTZ,
    repeatEndDate TIMESTAMPTZ,
    endDate TIMESTAMPTZ,
    publishDate TIMESTAMPTZ,
    itogiDatePublic TIMESTAMPTZ,
    refTypeTradeId INTEGER,
    disablePersonId INTEGER,
    discusStartDate TIMESTAMPTZ,
    discusEndDate TIMESTAMPTZ,
    idSupplier INTEGER,
    biinSupplier TEXT,
    parentId BIGINT,
    singlOrgSign INTEGER,
    isLightIndustry INTEGER,
    isConstructionWork INTEGER,
    refSpecPurchaseTypeId INTEGER,
    lastUpdateDate TIMESTAMPTZ,
    finYear INTEGER[],
    kato TEXT[],
    systemId INTEGER,
    indexDate TIMESTAMPTZ,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS sync_meta (
    entity VARCHAR(50) PRIMARY KEY,
    last_update_date TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
