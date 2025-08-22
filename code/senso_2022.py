# Autor: Vinicius Madureira
# Projeto: Censo IBGE 2022 - Automação e Banco de Dados
# Última atualização: 21/08/2025

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Configurações de saída e carregamento de variáveis de ambiente

# Carregar variáveis de ambiente (.env) para ler caminhos e credenciais
load_dotenv()

# Diretório base deste arquivo (dois níveis acima de ``code``)
BASE_DIR = Path(__file__).resolve().parents[1]

# Determina a pasta de saída com base em OUTPUT_FILES_PATH ou 'data/output'
output_path_env = os.getenv("OUTPUT_FILES_PATH")
if output_path_env:
    OUTPUT_DIR = Path(output_path_env)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
else:
    OUTPUT_DIR = BASE_DIR / "data" / "output"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Funções utilitárias

def get_city_ids(estado: str) -> dict:
    """
    Obtém códigos e metadados de todos os municípios de um estado,
    tratando casos em que microrregião/mesorregião são nulos.
    """
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado}/municipios"
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        return {}
    cidades = response.json()
    metadata = {}
    for cidade in cidades:
        id_ = str(cidade.get('id'))
        micror = cidade.get('microrregiao') or {}
        mesor = micror.get('mesorregiao') or {}
        uf_info = mesor.get('UF') or {}
        reg = uf_info.get('regiao') or {}
        metadata[id_] = {
            "cidade_nome": cidade.get("nome", ""),
            "microrregiao": micror.get("nome", ""),
            "mesorregiao": mesor.get("nome", ""),
            "uf": uf_info.get("sigla", ""),
            "uf_nome": uf_info.get("nome", ""),
            "regiao": reg.get("nome", ""),
            "regiao_sigla": reg.get("sigla", ""),
        }
    return metadata

def get_data_by_municipio(id_municipio: str, metadata: dict) -> pd.DataFrame | None:
    """
    Consulta a tabela 9514 (sexo x idade) para um município, removendo totais
    e faixas agregadas, e insere metadados do município.
    """
    url = (
        f"https://apisidra.ibge.gov.br/values/"
        f"t/9514/n6/{id_municipio}/v/allxp/p/all/c2/allxt/"
        f"c287/all/c286/113635"
    )
    response = requests.get(url, timeout=60)
    time.sleep(1.5)
    if response.status_code != 200:
        return None
    data = response.json()
    if not data or len(data) < 2:
        return None

    cols = data[0]
    df = pd.DataFrame(data[1:], columns=cols)

    # Debug: mostrar as primeiras linhas antes dos filtros
    print(f"Pré-filtro município {id_municipio}:", df.head())

    # Descartar linhas agregadas (D1N == 'Município')
    if 'D1N' in df.columns:
        df = df[df['D1N'] != 'Município']

    # Renomear colunas relevantes
    df = df.rename(columns={
        'D3C': 'Ano',
        'D4N': 'Sexo',
        'D5N': 'Idade',
        'V': 'Pessoas',
    })
    if 'Pessoas' in df.columns:
        df['Pessoas'] = df['Pessoas'].replace('-', '0')
        df['Pessoas'] = pd.to_numeric(df['Pessoas'], errors='coerce').astype('Int64')

    # Inserir metadados (nome correto, micro, meso, UF, etc.)
    meta = metadata.get(id_municipio, {})
    for key, value in meta.items():
        df[key] = value
    df['cidade_nome'] = meta.get('cidade_nome', '')

    # Filtrar fora apenas faixas agregadas (mantém 'Total')
    faixa_pat = re.compile(r"\d+\s+a\s+\d+\s+anos|Menos\s+de|ou\s+mais", flags=re.I)
    if 'Idade' in df.columns:
        df = df[~df['Idade'].str.contains(faixa_pat, na=False)]

    # Debug: mostrar as primeiras linhas após os filtros
    print(f"Pós-filtro município {id_municipio}:", df.head())
    print(f"Linhas restantes: {len(df)}")

    # Selecionar apenas as colunas finais
    final_cols = [
        'cidade_nome', 'microrregiao', 'mesorregiao', 'uf', 'uf_nome',
        'regiao', 'regiao_sigla', 'Ano', 'Sexo', 'Idade', 'Pessoas'
    ]
    df = df[[c for c in final_cols if c in df.columns]]
    if df.empty:
        print(f"⚠️ DataFrame vazio para município {id_municipio}")
        return None
    return df

def coletar_estados(estados: list[str]) -> None:
    """
    Percorre todos os estados, coleta dados por município, salva um CSV
    consolidado e, se configurado, insere no PostgreSQL.
    """
    all_results: list[pd.DataFrame] = []

    # Antes de rodar os estados, verificar e limpar a tabela no banco
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_schema = os.getenv("DB_SCHEMA")
    db_table = os.getenv("DB_TABLE")
    if all([db_user, db_password, db_host, db_port, db_name, db_table]):
        try:
            db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            engine = create_engine(db_url)
            with engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {db_schema}"))
                table_exists = conn.execute(text(f"SELECT to_regclass('{db_schema}.{db_table}')")).scalar()
                if table_exists:
                    conn.execute(text(f"TRUNCATE TABLE {db_schema}.{db_table} RESTART IDENTITY CASCADE"))
        except Exception as e:
            print(f"⚠️ Erro ao preparar tabela no banco: {e}")

    for estado in estados:
        print(f"✔️ Estado em execução: {estado}")
        metadata_dict = get_city_ids(estado)
        ids = list(metadata_dict.keys())
        resultados: list[pd.DataFrame] = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_id = {
                executor.submit(get_data_by_municipio, id_mun, metadata_dict): id_mun
                for id_mun in ids
            }
            for future in as_completed(future_to_id):
                result = future.result()
                if result is not None:
                    resultados.append(result)
                else:
                    print(f"⚠️ Falha ao coletar município {future_to_id[future]} do estado {estado}.")

        if resultados:
            df_estado = pd.concat(resultados, ignore_index=True)
            all_results.append(df_estado)

            # Armazenar no banco após cada estado
            if all([db_user, db_password, db_host, db_port, db_name, db_table]):
                try:
                    df_estado.to_sql(db_table, engine, schema=db_schema, if_exists='append', index=False)
                    print(f"✅ Dados do estado {estado} inseridos na tabela {db_schema}.{db_table} do banco {db_name}.")
                except Exception as e:
                    print(f"⚠️ Erro ao inserir dados do estado {estado} no banco: {e}")
            else:
                print(f"ℹ️ Variáveis de conexão com o banco não estão completas para o estado {estado}; apenas o CSV será gerado.")
        else:
            print(f"⚠️ Nenhum dado coletado para o estado {estado}.")

    if all_results:
        df_total = pd.concat(all_results, ignore_index=True)
        out_path = OUTPUT_DIR / "censo_2022_municipio_sexo_idade.csv"

        # Exportar CSV
        df_total.to_csv(out_path, index=False, encoding='utf-8')
        print(f"✅ Dados consolidados salvos em {out_path}.")

        # Variáveis de banco (PostgreSQL)
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        db_schema = os.getenv("DB_SCHEMA")
        db_table = os.getenv("DB_TABLE")

        # Inserir no banco se todas as credenciais estiverem presentes
        if all([db_user, db_password, db_host, db_port, db_name, db_table]):
            try:
                db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                engine = create_engine(db_url)
                # Criar schema se não existir
                with engine.begin() as conn:
                    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {db_schema}"))
                # Inserir/atualizar tabela
                df_total.to_sql(db_table, engine, schema=db_schema,
                                if_exists='replace', index=False)
                print(f"✅ Dados inseridos na tabela {db_schema}.{db_table} do banco {db_name}.")
            except Exception as e:
                print(f"⚠️ Erro ao inserir dados no banco: {e}")
        else:
            print("ℹ️ Variáveis de conexão com o banco não estão completas; "
                  "apenas o CSV foi gerado.")
    else:
        print("⚠️ Nenhum dado foi coletado para quaisquer estados.")

if __name__ == "__main__":
    estados_brasil = [
        'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT',
        'MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS',
        'RO','RR','SC','SP','SE','TO'
    ]
    coletar_estados(estados_brasil)
