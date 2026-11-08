"""Local, rebuildable analytical store. Original CSV files are never modified."""
import hashlib
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data'
DB_PATH = ROOT / 'backend' / 'storage' / 'museum.duckdb'


def query(path, sql, params=()):
    with duckdb.connect(str(path), read_only=True) as con:
        result = con.execute(sql, params)
        columns = [column[0] for column in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]


def initialize(data_dir=DATA_DIR, db_path=DB_PATH):
    sources = []
    for suffix in ('FST', 'SECD'):
        matches = list(Path(data_dir).glob(f'*_{suffix}_TBL.csv'))
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {suffix} CSV in {data_dir}')
        sources.append(matches[0])
    fingerprint = hashlib.sha256(b'v1' + b''.join(p.read_bytes() for p in sources)).hexdigest()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute('CREATE TABLE IF NOT EXISTS source_version (fingerprint VARCHAR)')
        if con.execute('SELECT fingerprint FROM source_version').fetchone() == (fingerprint,):
            return
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute("""
                CREATE OR REPLACE TABLE visits AS
                SELECT CAST(P_YYYYMMDD AS DATE) AS date, FACL_NM AS facility,
                       CAST(TMZN AS INTEGER) AS hour,
                       CASE SEX_DIVS_CD WHEN 'FEMALE' THEN 'F' WHEN 'MALE' THEN 'M'
                            ELSE SEX_DIVS_CD END AS sex,
                       YY10_AGLV_ID AS age, CAST(VIST_POPL_CNT AS DECIMAL(18,2)) AS population
                FROM read_csv(?, header=true, all_varchar=true)
            """, [str(sources[0])])
            con.execute("""
                CREATE OR REPLACE TABLE relations AS
                SELECT CAST(strptime(P_YYYYMM, '%Y%m') AS DATE) AS month,
                       TRGT_BASE_FACL_NM AS base_facility,
                       TRGT_RLTV_FACL_NM AS related_facility,
                       SEX_DIVS_CD AS sex, YY10_AGLV_ID AS age,
                       CAST(VIST_POPL_CNT AS DECIMAL(18,2)) AS population
                FROM read_csv(?, header=true, all_varchar=true)
            """, [str(sources[1])])
            for table, dimensions in (
                ('visits', ['date', 'facility', 'hour', 'sex', 'age']),
                ('relations', ['month', 'base_facility', 'related_facility', 'sex', 'age']),
            ):
                nulls = ' OR '.join(f'{c} IS NULL' for c in dimensions + ['population'])
                invalid = con.execute(f"SELECT count(*) FROM {table} WHERE {nulls} OR population < 0 OR sex NOT IN ('F','M') OR age NOT IN ('20대','30대')").fetchone()[0]
                duplicates = con.execute(f"SELECT count(*) FROM (SELECT {','.join(dimensions)} FROM {table} GROUP BY ALL HAVING count(*) > 1)").fetchone()[0]
                if invalid or duplicates:
                    raise ValueError(f'{table}: invalid rows={invalid}, duplicate keys={duplicates}')
            if con.execute('SELECT count(*) FROM visits WHERE hour NOT BETWEEN 0 AND 23').fetchone()[0]:
                raise ValueError('Invalid hour')
            con.execute('DELETE FROM source_version')
            con.execute('INSERT INTO source_version VALUES (?)', [fingerprint])
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise


if __name__ == '__main__':
    initialize()
    print(f'Database ready: {DB_PATH}')
