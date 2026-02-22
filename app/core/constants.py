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
    # Artigos e preposicoes
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "em", "entre", "na", "nas", "no", "nos", "num", "numa", "nuns", "numas",
    "o", "os", "ou", "para", "pra", "pro", "pela", "pelas", "pelo", "pelos",
    "por", "sem", "sob",
    # Pronomes
    "aquela", "aquelas", "aquele", "aqueles", "aquilo", "dela", "delas",
    "dele", "deles", "ela", "elas", "ele", "eles", "eu", "essa", "essas",
    "esse", "esses", "esta", "estas", "este", "estes", "lhe", "lhes", "me",
    "meu", "minha", "meus", "minhas", "nossas", "nossos", "nossa", "nosso",
    "qual", "quais", "que", "quem", "se", "seu", "sua", "seus", "suas",
    "te", "ti", "tu", "tua", "tuas", "teu", "teus", "voce", "voces", "vos",
    "ninguem", "alguem", "algo", "nada", "tudo", "todos", "toda", "todo",
    "todas", "outro", "outra", "outros", "outras", "cada", "varios",
    # Verbos auxiliares e comuns (conjugacoes)
    "ser", "sou", "era", "foi", "sao", "somos", "foram", "seria", "sendo",
    "estar", "estou", "esta", "estao", "estava", "estamos", "estive",
    "ter", "tem", "tinha", "tenho", "temos", "teve", "tendo", "tiver",
    "fazer", "faz", "fez", "faco", "feito", "fazendo",
    "poder", "pode", "podia", "podem", "podemos",
    "ir", "vai", "vou", "vao", "vamos", "indo", "ido", "foram",
    "dar", "deu", "dou", "dando",
    "ver", "viu", "vejo",
    "saber", "sei", "sabe", "sabemos",
    "querer", "quer", "quero", "querem",
    "dizer", "disse", "diz", "dizendo",
    "ficar", "fica", "ficou", "ficam",
    "falar", "fala", "falou",
    "deixar", "deixa", "deixou",
    "colocar", "coloca",
    # Adverbios e conectivos
    "mais", "mas", "nem", "nao", "sim", "tambem", "ja", "ainda", "sempre",
    "nunca", "agora", "aqui", "ali", "la", "ca", "onde", "quando", "depois",
    "antes", "ate", "so", "apenas", "muito", "pouco", "bem", "mal",
    "demais", "bastante", "tanto", "tao", "assim", "entao", "pois",
    "porque", "porquem", "portanto", "contudo", "porem", "logo", "enfim",
    "mesmo", "ai", "ne", "tipo", "meio",
    # Palavras comuns sem valor analitico
    "dia", "dias", "vez", "vezes", "ano", "anos", "hoje", "ontem",
    "gente", "cara", "coisa", "coisas", "parte", "forma", "jeito",
    "isso", "isto", "ha", "for", "fora",
    "bom", "boa", "bons", "boas", "grande", "grandes",
    "novo", "nova", "novos", "novas",
    "primeiro", "segunda", "sobre",
    "caso", "foto", "video", "post",
    # Ruido de redes sociais
    "kk", "kkk", "kkkk", "kkkkk", "kkkkkk",
    "haha", "hahaha", "rs", "rsrs", "rsrsrs",
    "obg", "obrigado", "obrigada", "vlw",
    "sim", "nao", "ok", "tudo", "oi", "ola",
    # Verbos/formas informais
    "ta", "to", "pq", "tb", "tbm", "vc", "vcs",
    "mto", "mt", "dms", "td",
}


# ---------------------------------------------------------------------------
# Theme Keywords (9 categories from SCHEMA.md theme_category enum)
# Maps each theme to a list of Portuguese keywords for keyword-based matching.
# ---------------------------------------------------------------------------
THEME_KEYWORDS: dict[str, list[str]] = {
    "saude": [
        "saude", "hospital", "medico", "sus", "vacina", "remedio",
        "enfermeiro", "clinica", "atendimento", "posto", "ubs",
        "farmacia", "doenca", "pandemia", "leito", "mental",
        "medicamento", "tratamento", "exame", "consulta", "cura",
        "paciente", "emergencia", "urgencia", "internacao",
    ],
    "seguranca": [
        "seguranca", "policia", "violencia", "crime", "assalto",
        "roubo", "droga", "trafico", "guarda", "pm", "delegacia",
        "preso", "arma", "homicidio", "patrulha", "delegada",
        "justica", "lei", "prender", "bandido", "penal",
        "investigacao", "policial", "protecao", "feminicidio",
        "abuso", "denuncia", "vitima", "violencia", "combate",
    ],
    "educacao": [
        "educacao", "escola", "professor", "ensino", "aluno",
        "universidade", "creche", "aula", "estudante", "faculdade",
        "merenda", "alfabetizacao", "bolsa", "enem", "pedagogia",
        "crianca", "criancas", "filho", "filhos", "filha",
        "jovem", "jovens", "futuro", "aprender", "formacao",
        "infantil", "adolescente", "bebe",
    ],
    "economia": [
        "economia", "imposto", "salario", "preco", "inflacao",
        "comercio", "industria", "pib", "taxa", "renda",
        "cesta", "dinheiro", "custo", "mercado", "investimento",
        "pobre", "rico", "desigualdade", "fome", "miseria",
        "caro", "barato", "conta", "pagar", "divida",
    ],
    "infraestrutura": [
        "obra", "asfalto", "saneamento", "rua", "ponte",
        "transporte", "onibus", "estrada", "agua", "esgoto",
        "iluminacao", "pavimentacao", "buraco", "moradia", "habitacao",
        "bairro", "cidade", "comunidade", "periferia", "favela",
        "construcao", "reforma", "praca",
    ],
    "corrupcao": [
        "corrupcao", "roubo", "desvio", "propina", "lavagem",
        "fraude", "improbidade", "nepotismo", "superfaturamento",
        "licitacao", "corrupto", "mafia", "mentira", "vergonha",
        "ladrao", "politicagem", "mamata", "rouba", "safado",
    ],
    "emprego": [
        "emprego", "trabalho", "desemprego", "carteira", "vaga",
        "contratacao", "salario", "clt", "informal", "renda",
        "capacitacao", "curso", "profissional", "oportunidade", "demissao",
        "trabalhador", "trabalhadora", "empreendedor", "negocio",
    ],
    "meio_ambiente": [
        "ambiente", "lixo", "poluicao", "verde", "reciclagem",
        "desmatamento", "rio", "agua", "ecologia", "sustentabilidade",
        "queimada", "floresta", "clima", "parque", "saneamento",
        "animal", "animais", "bicho", "cachorro", "gato", "natureza",
    ],
    "outros": [],
}

# ---------------------------------------------------------------------------
# Labels PT-BR para nomes de temas (display no frontend)
# ---------------------------------------------------------------------------
THEME_LABELS_PT: dict[str, str] = {
    "saude": "Saúde",
    "seguranca": "Segurança",
    "educacao": "Educação",
    "economia": "Economia",
    "infraestrutura": "Infraestrutura",
    "corrupcao": "Corrupção",
    "emprego": "Emprego",
    "meio_ambiente": "Meio Ambiente",
    "outros": "Outros",
}
