-- Schéma Fisca AI RAG v1 : CGI 2026 (hors Livre 6 collectivités territoriales)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS cgi_articles (
    id SERIAL PRIMARY KEY,
    article_id TEXT UNIQUE NOT NULL,      -- ex: '72bis'
    article_num INT NOT NULL,             -- ex: 72 (pour tri/recherche numérique)
    article_suffix TEXT DEFAULT '',       -- 'bis' / 'ter' / 'quater' / ''
    page INT NOT NULL,
    livre_num TEXT, livre_titre TEXT,
    titre_num TEXT, titre_titre TEXT,
    chapitre_num TEXT, chapitre_titre TEXT,
    section_num TEXT, section_titre TEXT,
    ssection_num TEXT, ssection_titre TEXT,
    text TEXT NOT NULL,
    embedding vector(3072)                -- à ajuster selon gemini-embedding-001
);

CREATE INDEX IF NOT EXISTS idx_cgi_articles_embedding
    ON cgi_articles USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_cgi_articles_num ON cgi_articles (article_num);
CREATE INDEX IF NOT EXISTS idx_cgi_articles_livre ON cgi_articles (livre_num);

-- Renvois croisés entre articles (extraits automatiquement du texte)
CREATE TABLE IF NOT EXISTS article_refs (
    id SERIAL PRIMARY KEY,
    source_article_id TEXT NOT NULL REFERENCES cgi_articles(article_id),
    target_article_id TEXT NOT NULL REFERENCES cgi_articles(article_id),
    ref_type TEXT NOT NULL DEFAULT 'renvoi',  -- 'renvoi' | 'plage' | 'et_suivants'
    UNIQUE (source_article_id, target_article_id, ref_type)
);

CREATE INDEX IF NOT EXISTS idx_article_refs_source ON article_refs (source_article_id);
CREATE INDEX IF NOT EXISTS idx_article_refs_target ON article_refs (target_article_id);
