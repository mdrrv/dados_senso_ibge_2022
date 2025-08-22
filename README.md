# Projeto Censo IBGE 2022 - Automação e Banco de Dados

![IBGE Logo](https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/IBGE_logo.svg/2560px-IBGE_logo.svg.png)

---

## 🚀 Visão Geral
Este projeto automatiza a coleta dos dados do Censo 2022 do IBGE, organiza e filtra as informações por município e estado, e armazena tudo em um banco de dados PostgreSQL para análises avançadas e visualizações.

---

## ✨ Funcionalidades
- **Coleta automática** dos dados do Censo 2022 via API do IBGE/SIDRA
- **Processamento paralelo** dos municípios de cada estado
- **Filtragem inteligente** para manter apenas dados relevantes (população por sexo e idade, sem faixas agregadas ou totais indesejados)
- **Armazenamento incremental**: a cada estado processado, os dados já são inseridos no banco
- **Exportação dos dados** para CSV
- **Configuração flexível** via arquivo `.env`
- **Logs detalhados** para acompanhamento do processamento

---

## 🗂️ Estrutura do Projeto
```
code/
  censo_2022.py         # Script principal de coleta e inserção
  .env                  # Configurações de caminhos e banco

data/
  output_files/         # CSVs gerados
```

---

## ⚙️ Como Funciona
1. **Configuração**: Edite o arquivo `.env` com os dados do seu banco e caminhos de saída.
2. **Execução**: Rode o script principal:
   ```powershell
   python code/censo_2022.py
   ```
3. **Processamento**: O script coleta os dados de cada estado, filtra, salva em CSV e insere no banco.
4. **Banco de Dados**: Antes de iniciar, o script verifica e limpa a tabela no banco, garantindo dados sempre atualizados.

---

## 💡 Exemplo de Uso
```powershell
python code/censo_2022.py
```

---

## 🔑 Variáveis de Ambiente (.env)
```env
OUTPUT_FILES_PATH=...           # Pasta de saída dos arquivos CSV
DB_HOST=...                     # Host do banco PostgreSQL
DB_PORT=...                     # Porta do banco
DB_USER=...                     # Usuário
DB_PASSWORD=...                 # Senha
DB_NAME=...                     # Nome do banco
DB_SCHEMA=...                   # Schema do banco
DB_TABLE=...                    # Nome da tabela
```

---

## 📊 Visualização dos Dados
- Os dados podem ser consultados diretamente no banco PostgreSQL
- Os arquivos CSV gerados ficam em `data/output_files/`
- Recomenda-se o uso de ferramentas como Power BI, Metabase ou Grafana para visualização

---

## 🛠️ Requisitos
- Python 3.10+
- Bibliotecas: `pandas`, `requests`, `sqlalchemy`, `python-dotenv`
- Banco de dados PostgreSQL

---

## 📄 Licença
Projeto livre para uso acadêmico e pessoal.

---

## 👤 Autor
**Vinicius Madureira**

[LinkedIn](https://www.linkedin.com/in/madureirav/) | [GitHub](https://github.com/mdrrv)

---

> **Dica:** Para personalizar filtros, faixas etárias ou variáveis, edite o script `censo_2022.py` conforme sua necessidade!

