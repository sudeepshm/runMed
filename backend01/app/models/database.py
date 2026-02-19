"""
PharmaGuard — SQLite database setup and seeding (Module 3).

Creates tables for star allele definitions and CPIC recommendations,
and seeds them from the JSON reference files.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "pharmaguard.db"
STAR_ALLELE_JSON = DATA_DIR / "star_allele_definitions.json"
CPIC_JSON = DATA_DIR / "cpic_recommendations.json"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist and seed from JSON files."""
    conn = get_connection()
    try:
        _create_tables(conn)
        _seed_star_alleles(conn)
        _seed_cpic_recommendations(conn)
        conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    finally:
        conn.close()


# ── Table creation ────────────────────────────────────────────────────

def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS star_alleles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gene        TEXT NOT NULL,
            allele_name TEXT NOT NULL,
            function    TEXT,
            activity_score REAL,
            defining_variants TEXT,   -- JSON array of {rsid, ref, alt}
            description TEXT,
            UNIQUE(gene, allele_name)
        );

        CREATE TABLE IF NOT EXISTS phenotype_map (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gene        TEXT NOT NULL,
            phenotype   TEXT NOT NULL,
            min_score   REAL NOT NULL,
            max_score   REAL NOT NULL,
            label       TEXT,
            UNIQUE(gene, phenotype)
        );

        CREATE TABLE IF NOT EXISTS cpic_recommendations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gene        TEXT NOT NULL,
            phenotype   TEXT NOT NULL,
            drug        TEXT NOT NULL,
            risk_label  TEXT NOT NULL,
            severity    TEXT NOT NULL,
            recommendation TEXT,
            source      TEXT DEFAULT 'CPIC',
            UNIQUE(gene, phenotype, drug)
        );
    """)


# ── Seeding ───────────────────────────────────────────────────────────

def _seed_star_alleles(conn: sqlite3.Connection) -> None:
    """Load star allele definitions from JSON into SQLite."""
    if not STAR_ALLELE_JSON.exists():
        logger.warning("Star allele JSON not found: %s", STAR_ALLELE_JSON)
        return

    # Check if already seeded
    count = conn.execute("SELECT COUNT(*) FROM star_alleles").fetchone()[0]
    if count > 0:
        return

    with open(STAR_ALLELE_JSON, "r") as f:
        data = json.load(f)

    for gene, gene_data in data.items():
        # Insert alleles
        for allele_name, allele_info in gene_data["alleles"].items():
            conn.execute(
                """INSERT OR IGNORE INTO star_alleles
                   (gene, allele_name, function, activity_score, defining_variants, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    gene,
                    allele_name,
                    allele_info["name"],
                    allele_info["activity_score"],
                    json.dumps(allele_info["defining_variants"]),
                    allele_info["description"],
                ),
            )

        # Insert phenotype map
        for pheno, thresholds in gene_data.get("phenotype_map", {}).items():
            conn.execute(
                """INSERT OR IGNORE INTO phenotype_map
                   (gene, phenotype, min_score, max_score, label)
                   VALUES (?, ?, ?, ?, ?)""",
                (gene, pheno, thresholds["min_score"], thresholds["max_score"], thresholds["label"]),
            )

    logger.info("Seeded star allele definitions for %d genes", len(data))


def _seed_cpic_recommendations(conn: sqlite3.Connection) -> None:
    """Load CPIC recommendations from JSON into SQLite (if file exists)."""
    if not CPIC_JSON.exists():
        logger.info("CPIC JSON not found yet — will be seeded in Module 4.")
        return

    count = conn.execute("SELECT COUNT(*) FROM cpic_recommendations").fetchone()[0]
    if count > 0:
        return

    with open(CPIC_JSON, "r") as f:
        data = json.load(f)

    for rec in data:
        conn.execute(
            """INSERT OR IGNORE INTO cpic_recommendations
               (gene, phenotype, drug, risk_label, severity, recommendation, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                rec["gene"],
                rec["phenotype"],
                rec["drug"],
                rec["risk_label"],
                rec["severity"],
                rec["recommendation"],
                rec.get("source", "CPIC"),
            ),
        )

    logger.info("Seeded %d CPIC recommendations", len(data))


# ── Queries ───────────────────────────────────────────────────────────

def get_alleles_for_gene(gene: str) -> list[dict]:
    """Return all star alleles for a given gene."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM star_alleles WHERE gene = ? ORDER BY allele_name",
            (gene,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_phenotype_map(gene: str) -> list[dict]:
    """Return phenotype map for a gene."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM phenotype_map WHERE gene = ? ORDER BY min_score",
            (gene,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Auto-initialise on import ─────────────────────────────────────────
init_db()
