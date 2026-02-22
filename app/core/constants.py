"""Application constants.

Contains stop words (PT-BR), theme keywords, and analysis thresholds.
"""

# ---------------------------------------------------------------------------
# VADER / LLM Thresholds
# ---------------------------------------------------------------------------
VADER_POSITIVE_THRESHOLD: float = 0.05
VADER_NEGATIVE_THRESHOLD: float = -0.05
LLM_CONFIDENCE_THRESHOLD: float = 0.7
LLM_AMBIGUOUS_MIN_LENGTH: int = 20

# ---------------------------------------------------------------------------
# Portuguese Stop Words (minimum 50)
# Common words filtered out of word cloud / text analysis
# ---------------------------------------------------------------------------
STOP_WORDS_PT: set[str] = {
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo",
    "as", "ate", "com", "como", "da", "das", "de", "dela", "delas",
    "dele", "deles", "depois", "do", "dos", "e", "ela", "elas", "ele",
    "eles", "em", "entre", "era", "essa", "essas", "esse", "esses",
    "esta", "estas", "este", "estes", "eu", "foi", "for", "foram",
    "ha", "isso", "isto", "ja", "lhe", "lhes", "mais", "mas", "me",
    "mesmo", "meu", "minha", "muito", "na", "nao", "nas", "nem",
    "no", "nos", "nossa", "nosso", "num", "numa", "nuns", "numas",
    "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por",
    "qual", "quando", "que", "quem", "sao", "se", "sem", "ser", "seu",
    "sua", "tambem", "te", "tem", "tinha", "tu", "tua", "tudo", "um",
    "uma", "umas", "uns", "vai", "voce", "voces", "vos",
}

# ---------------------------------------------------------------------------
# Theme Keywords (9 categories from SCHEMA.md theme_category enum)
# Maps each theme to a list of Portuguese keywords for keyword-based matching.
# ---------------------------------------------------------------------------
THEME_KEYWORDS: dict[str, list[str]] = {
    "saude": [
        "saude", "hospital", "medico", "sus", "vacina", "remedio",
        "enfermeiro", "clinica", "atendimento", "posto", "ubs",
        "farmacia", "doenca", "pandemia", "leito",
    ],
    "seguranca": [
        "seguranca", "policia", "violencia", "crime", "assalto",
        "roubo", "droga", "trafico", "guarda", "pm", "delegacia",
        "preso", "arma", "homicidio", "patrulha",
    ],
    "educacao": [
        "educacao", "escola", "professor", "ensino", "aluno",
        "universidade", "creche", "aula", "estudante", "faculdade",
        "merenda", "alfabetizacao", "bolsa", "enem", "pedagogia",
    ],
    "economia": [
        "economia", "imposto", "salario", "preco", "inflacao",
        "comercio", "industria", "pib", "taxa", "renda",
        "cesta", "dinheiro", "custo", "mercado", "investimento",
    ],
    "infraestrutura": [
        "obra", "asfalto", "saneamento", "rua", "ponte",
        "transporte", "onibus", "estrada", "agua", "esgoto",
        "iluminacao", "pavimentacao", "buraco", "moradia", "habitacao",
    ],
    "corrupcao": [
        "corrupcao", "roubo", "desvio", "propina", "lavagem",
        "fraude", "improbidade", "nepotismo", "superfaturamento",
        "licitacao", "corrupto", "caixa", "mafia", "investigacao", "denuncia",
    ],
    "emprego": [
        "emprego", "trabalho", "desemprego", "carteira", "vaga",
        "contratacao", "salario", "clt", "informal", "renda",
        "capacitacao", "curso", "profissional", "oportunidade", "demissao",
    ],
    "meio_ambiente": [
        "ambiente", "lixo", "poluicao", "verde", "reciclagem",
        "desmatamento", "rio", "agua", "ecologia", "sustentabilidade",
        "queimada", "floresta", "clima", "parque", "saneamento",
    ],
    "outros": [],
}
