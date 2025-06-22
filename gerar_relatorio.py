<<<<<<< HEAD
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# --- CONFIGURAÇÃO ---
DB_FILENAME = 'geladeira.db'
OUTPUT_FILENAME = f"Relatorio_Debug_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

print("-" * 60)
print("Gerador de Relatórios SmartBox (Modo de Diagnóstico)")
print("-" * 60)

if not os.path.exists(DB_FILENAME):
    print(f"ERRO: Base de dados '{DB_FILENAME}' não encontrada.")
    exit()

engine = create_engine(f'sqlite:///{DB_FILENAME}')
print(f"Lendo a base de dados '{DB_FILENAME}'...")

try:
    with engine.connect() as connection:
        # --- CONSULTAS SQL ---
        query_vendas = text("SELECT * FROM sale WHERE status = 'paid';")
        query_estoque = text("SELECT * FROM inventory;")
        query_kpis = text("SELECT SUM(price_at_sale) AS faturamento, SUM(cost_at_sale) AS custo FROM sale WHERE status = 'paid';")

        print("\n[DEBUG] Executando consulta de KPIs...")
        kpi_result = connection.execute(query_kpis).fetchone()
        print(f"[DEBUG] Resultado da consulta de KPIs: {kpi_result}")
        
        # Processamento dos KPIs
        faturamento = kpi_result.faturamento or 0
        custo = kpi_result.custo or 0
        
        kpi_data = {
            'Indicador': ['Faturamento Total', 'Custo Total', 'Lucro Bruto'],
            'Valor': [faturamento, custo, faturamento - custo]
        }
        df_kpi = pd.DataFrame(kpi_data)
        
        print("\n[DEBUG] DataFrame de KPIs a ser escrito no Excel:")
        print(df_kpi)
        print("-" * 30)

        # Processamento das Vendas
        print("\n[DEBUG] Lendo a tabela de vendas (sale)...")
        df_vendas = pd.read_sql_query(query_vendas, connection)
        print(f"[DEBUG] Encontradas {len(df_vendas)} vendas com status 'paid'.")
        if not df_vendas.empty:
            print(df_vendas.head()) # Mostra as primeiras 5 linhas
        print("-" * 30)
        
        # Processamento do Estoque
        print("\n[DEBUG] Lendo a tabela de estoque (inventory)...")
        df_estoque = pd.read_sql_query(query_estoque, connection)
        print(f"[DEBUG] Encontrados {len(df_estoque)} itens no estoque.")
        if not df_estoque.empty:
            print(df_estoque.head())
        print("-" * 30)

        # --- CRIAÇÃO DO FICHEIRO EXCEL ---
        print(f"\nCriando o ficheiro Excel: {OUTPUT_FILENAME}")
        with pd.ExcelWriter(OUTPUT_FILENAME, engine='openpyxl') as writer:
            df_kpi.to_excel(writer, sheet_name='Resumo KPIs', index=False)
            df_vendas.to_excel(writer, sheet_name='Dados de Vendas', index=False)
            df_estoque.to_excel(writer, sheet_name='Dados de Estoque', index=False)

    print("\n" + "="*60)
    print(f"SUCESSO! Relatório de diagnóstico '{OUTPUT_FILENAME}' gerado.")
    print("Por favor, verifique a saída do terminal acima e o ficheiro Excel.")
    print("="*60)

except Exception as e:
    print("\n" + "="*60)
    print("OCORREU UM ERRO:")
    print(e)
    print("="*60)

=======
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# --- CONFIGURAÇÃO ---
DB_FILENAME = 'geladeira.db'
OUTPUT_FILENAME = f"Relatorio_Debug_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

print("-" * 60)
print("Gerador de Relatórios SmartBox (Modo de Diagnóstico)")
print("-" * 60)

if not os.path.exists(DB_FILENAME):
    print(f"ERRO: Base de dados '{DB_FILENAME}' não encontrada.")
    exit()

engine = create_engine(f'sqlite:///{DB_FILENAME}')
print(f"Lendo a base de dados '{DB_FILENAME}'...")

try:
    with engine.connect() as connection:
        # --- CONSULTAS SQL ---
        query_vendas = text("SELECT * FROM sale WHERE status = 'paid';")
        query_estoque = text("SELECT * FROM inventory;")
        query_kpis = text("SELECT SUM(price_at_sale) AS faturamento, SUM(cost_at_sale) AS custo FROM sale WHERE status = 'paid';")

        print("\n[DEBUG] Executando consulta de KPIs...")
        kpi_result = connection.execute(query_kpis).fetchone()
        print(f"[DEBUG] Resultado da consulta de KPIs: {kpi_result}")
        
        # Processamento dos KPIs
        faturamento = kpi_result.faturamento or 0
        custo = kpi_result.custo or 0
        
        kpi_data = {
            'Indicador': ['Faturamento Total', 'Custo Total', 'Lucro Bruto'],
            'Valor': [faturamento, custo, faturamento - custo]
        }
        df_kpi = pd.DataFrame(kpi_data)
        
        print("\n[DEBUG] DataFrame de KPIs a ser escrito no Excel:")
        print(df_kpi)
        print("-" * 30)

        # Processamento das Vendas
        print("\n[DEBUG] Lendo a tabela de vendas (sale)...")
        df_vendas = pd.read_sql_query(query_vendas, connection)
        print(f"[DEBUG] Encontradas {len(df_vendas)} vendas com status 'paid'.")
        if not df_vendas.empty:
            print(df_vendas.head()) # Mostra as primeiras 5 linhas
        print("-" * 30)
        
        # Processamento do Estoque
        print("\n[DEBUG] Lendo a tabela de estoque (inventory)...")
        df_estoque = pd.read_sql_query(query_estoque, connection)
        print(f"[DEBUG] Encontrados {len(df_estoque)} itens no estoque.")
        if not df_estoque.empty:
            print(df_estoque.head())
        print("-" * 30)

        # --- CRIAÇÃO DO FICHEIRO EXCEL ---
        print(f"\nCriando o ficheiro Excel: {OUTPUT_FILENAME}")
        with pd.ExcelWriter(OUTPUT_FILENAME, engine='openpyxl') as writer:
            df_kpi.to_excel(writer, sheet_name='Resumo KPIs', index=False)
            df_vendas.to_excel(writer, sheet_name='Dados de Vendas', index=False)
            df_estoque.to_excel(writer, sheet_name='Dados de Estoque', index=False)

    print("\n" + "="*60)
    print(f"SUCESSO! Relatório de diagnóstico '{OUTPUT_FILENAME}' gerado.")
    print("Por favor, verifique a saída do terminal acima e o ficheiro Excel.")
    print("="*60)

except Exception as e:
    print("\n" + "="*60)
    print("OCORREU UM ERRO:")
    print(e)
    print("="*60)

>>>>>>> b6f96c40fa2a4f4dffc7bf586851bdfd4374a577
