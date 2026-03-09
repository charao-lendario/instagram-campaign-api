"""Constants for theme classification, stop words, and keyword mappings."""

STOP_WORDS_PT = {
    "a", "o", "e", "de", "da", "do", "em", "um", "uma", "que", "no", "na",
    "os", "as", "dos", "das", "para", "por", "com", "se", "mais", "muito",
    "mas", "ao", "aos", "tem", "sua", "seu", "seus", "suas", "ela", "ele",
    "nos", "das", "nao", "sim", "ja", "ou", "foi", "ser", "ter", "esta",
    "isso", "isto", "aqui", "ali", "la", "voce", "eu", "meu", "minha",
    "como", "bem", "so", "ate", "entre", "sobre", "todo", "toda", "este",
    "esta", "esse", "essa", "quando", "qual", "pode", "vai", "vou", "tem",
    "sao", "era", "eram", "tambem", "acho", "gente", "agora", "ainda",
    "depois", "antes", "sempre", "nunca", "tudo", "nada", "cada", "mesmo",
    "coisa", "coisas", "dia", "vez", "vezes", "ano", "anos", "pra", "pro",
    "uns", "umas", "pelo", "pela", "pelos", "pelas", "num", "numa",
    "vc", "tb", "ne", "haha", "kkk", "kkkk", "kkkkk", "rs", "rsrs",
    "obrigado", "obrigada", "bom", "boa", "vamos", "assim", "aquele",
    "aquela", "onde", "porque", "pois", "entao", "muita", "muitos",
    "muitas", "outro", "outra", "outros", "outras", "dele", "dela",
    "deles", "delas", "nessa", "nesse", "dessa", "desse", "disso",
    "nisso", "com", "sem", "contra", "desde", "durante", "perante",
    "sob", "sobre", "tras", "mediante",
}

THEME_KEYWORDS: dict[str, list[str]] = {
    "saude": [
        "saude", "hospital", "medico", "ubs", "vacina", "vacinacao", "sus",
        "atendimento", "remedio", "doenca", "pandemia", "covid", "posto",
        "enfermeiro", "emergencia", "clinica", "tratamento", "exame",
        "consulta", "medicamento", "farmacia", "pronto-socorro",
    ],
    "seguranca": [
        "seguranca", "policia", "violencia", "assalto", "crime", "roubo",
        "droga", "trafico", "arma", "bandido", "morte", "homicidio",
        "patrulha", "viatura", "delegacia", "guarda", "furto", "preso",
        "cadeia", "milicia", "operacao",
    ],
    "educacao": [
        "educacao", "escola", "professor", "aluno", "ensino", "universidade",
        "faculdade", "creche", "aula", "estudante", "enem", "vestibular",
        "merenda", "bolsa", "formacao", "pedagogia", "infantil",
    ],
    "economia": [
        "economia", "emprego", "salario", "imposto", "preco", "inflacao",
        "comercio", "empresa", "lucro", "divida", "renda", "pib",
        "mercado", "investimento", "orcamento", "gasto", "custo",
        "caro", "barato", "dinheiro", "conta",
    ],
    "infraestrutura": [
        "infraestrutura", "obra", "rua", "asfalto", "buraco", "transito",
        "onibus", "metro", "estrada", "ponte", "saneamento", "esgoto",
        "agua", "luz", "energia", "moradia", "habitacao", "construcao",
        "pavimentacao", "iluminacao", "transporte",
    ],
    "corrupcao": [
        "corrupcao", "corrupto", "desvio", "propina", "lavagem", "fraude",
        "roubar", "roubou", "ladrao", "mensalao", "petrolao", "lava-jato",
        "improbidade", "nepotismo", "peculato", "superfaturamento",
    ],
    "emprego": [
        "emprego", "desemprego", "trabalho", "vaga", "contratacao",
        "carteira", "clt", "informal", "autonomo", "freelancer",
        "demissao", "demitido", "salario", "renda", "capacitacao",
    ],
    "meio_ambiente": [
        "meio ambiente", "ambiental", "desmatamento", "queimada",
        "poluicao", "reciclagem", "sustentavel", "clima", "floresta",
        "rio", "nascente", "mangue", "fauna", "flora", "ecologia",
        "carbono", "emissao", "lixo", "coleta",
    ],
}

BIGRAM_TERMS: list[str] = [
    "meio ambiente",
    "pronto socorro",
    "bolsa familia",
    "minha casa",
    "saude publica",
    "seguranca publica",
    "transporte publico",
    "educacao publica",
    "energia solar",
    "lava jato",
]
