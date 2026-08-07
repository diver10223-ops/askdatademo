CREATE DATABASE IF NOT EXISTS askdata_poc;

CREATE TABLE IF NOT EXISTS askdata_poc.dws_loan_aggr_wide
(
    stat_dt Date,
    org_name LowCardinality(String),
    loan_cur Decimal(18, 2),
    loan_last Decimal(18, 2),
    retail_cur Decimal(18, 2),
    retail_last Decimal(18, 2),
    corporate_cur Decimal(18, 2),
    corporate_last Decimal(18, 2)
)
ENGINE = MergeTree
ORDER BY (stat_dt, org_name);

CREATE TABLE IF NOT EXISTS askdata_poc.dwd_loan_detail
(
    loan_id String,
    customer_id String,
    customer_name String,
    id_no String,
    phone String,
    org_name LowCardinality(String),
    loan_type LowCardinality(String),
    loan_amount Decimal(18, 2),
    loan_balance Decimal(18, 2),
    interest_rate Decimal(8, 4),
    issue_date Date,
    maturity_date Date,
    loan_status LowCardinality(String),
    stat_dt Date
)
ENGINE = MergeTree
ORDER BY (stat_dt, org_name, loan_id);

TRUNCATE TABLE askdata_poc.dws_loan_aggr_wide;
INSERT INTO askdata_poc.dws_loan_aggr_wide VALUES
('2026-03-31','全行',128600.00,112300.00,71600.00,63800.00,57000.00,48500.00),
('2026-03-31','北京分行',38600.00,33100.00,22100.00,19600.00,16500.00,13500.00),
('2026-03-31','上海分行',34200.00,30900.00,18100.00,16700.00,16100.00,14200.00),
('2026-02-28','全行',119800.00,106700.00,67400.00,60100.00,52400.00,46600.00);

TRUNCATE TABLE askdata_poc.dwd_loan_detail;
INSERT INTO askdata_poc.dwd_loan_detail VALUES
('LN2026030001','C000001','张明','110101199001011234','13800138001','北京分行','零售消费贷',500000.00,438000.00,3.8500,'2026-01-15','2029-01-15','正常','2026-03-31'),
('LN2026030002','C000002','李华','310101198802024567','13900139002','上海分行','零售经营贷',800000.00,760000.00,4.1000,'2026-02-01','2028-02-01','正常','2026-03-31'),
('LN2026030003','C000003','华星科技有限公司','91310000MA1K12345X','021-60000003','上海分行','对公流动资金贷',12000000.00,10600000.00,3.4500,'2025-10-20','2027-10-20','正常','2026-03-31'),
('LN2026030004','C000004','京华商贸有限公司','91110108MA0012345Y','010-80000004','北京分行','对公经营贷',8000000.00,7200000.00,3.6000,'2025-11-12','2027-11-12','正常','2026-03-31');

CREATE USER IF NOT EXISTS poc_reader IDENTIFIED WITH sha256_password BY 'askdata_poc_demo';
GRANT SELECT ON askdata_poc.* TO poc_reader;
