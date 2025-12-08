"""
Repository pour la taxonomie de classification.
"""
from datetime import datetime
from typing import List, Dict

from sqlalchemy import func

from src.infrastructure.persistence.models import ClassificationTaxonomy, PageRecherche


def get_all_taxonomy(db, active_only: bool = True) -> List[ClassificationTaxonomy]:
    """Recupere toute la taxonomie."""
    with db.get_session() as session:
        query = session.query(ClassificationTaxonomy)
        if active_only:
            query = query.filter(ClassificationTaxonomy.is_active == True)
        return query.order_by(
            ClassificationTaxonomy.sort_order,
            ClassificationTaxonomy.category,
            ClassificationTaxonomy.subcategory
        ).all()


def get_taxonomy_by_category(db, category: str) -> List[ClassificationTaxonomy]:
    """Recupere les sous-categories d'une categorie."""
    with db.get_session() as session:
        return session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.category == category,
            ClassificationTaxonomy.is_active == True
        ).order_by(ClassificationTaxonomy.sort_order).all()


def get_taxonomy_categories(db, user_id=None) -> List[str]:
    """Recupere la liste unique des categories.

    Note: user_id accepte pour compatibilite mais ignore (taxonomie partagee).
    """
    with db.get_session() as session:
        results = session.query(ClassificationTaxonomy.category).filter(
            ClassificationTaxonomy.is_active == True
        ).distinct().order_by(ClassificationTaxonomy.category).all()
        return [r[0] for r in results]


def add_taxonomy_entry(
    db,
    category: str,
    subcategory: str,
    description: str = None,
    sort_order: int = 0
) -> int:
    """Ajoute une entree a la taxonomie."""
    with db.get_session() as session:
        entry = ClassificationTaxonomy(
            category=category,
            subcategory=subcategory,
            description=description,
            sort_order=sort_order,
            is_active=True
        )
        session.add(entry)
        session.flush()
        return entry.id


def update_taxonomy_entry(
    db,
    entry_id: int,
    category: str = None,
    subcategory: str = None,
    description: str = None,
    sort_order: int = None,
    is_active: bool = None
) -> bool:
    """Met a jour une entree de la taxonomie."""
    with db.get_session() as session:
        entry = session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.id == entry_id
        ).first()
        if not entry:
            return False

        if category is not None:
            entry.category = category
        if subcategory is not None:
            entry.subcategory = subcategory
        if description is not None:
            entry.description = description
        if sort_order is not None:
            entry.sort_order = sort_order
        if is_active is not None:
            entry.is_active = is_active

        return True


def delete_taxonomy_entry(db, entry_id: int) -> bool:
    """Supprime une entree de la taxonomie."""
    with db.get_session() as session:
        deleted = session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.id == entry_id
        ).delete()
        return deleted > 0


def init_default_taxonomy(db) -> int:
    """Initialise la taxonomie par defaut si vide."""
    with db.get_session() as session:
        count = session.query(ClassificationTaxonomy).count()
        if count > 0:
            return 0

    default_taxonomy = [
        ("Mode & Accessoires", "Vetements Femme", "Robes, tops, bas, lingerie, manteaux"),
        ("Mode & Accessoires", "Vetements Homme", "Costumes, casual, sportswear, sous-vetements"),
        ("Mode & Accessoires", "Mode Enfant & Bebe", "Vetements fille/garcon, layette, chaussures enfant"),
        ("Mode & Accessoires", "Chaussures", "Sneakers, ville, bottes, sandales, sport"),
        ("Mode & Accessoires", "Maroquinerie & Bagagerie", "Sacs a main, valises, sacs a dos, portefeuilles"),
        ("Mode & Accessoires", "Accessoires de mode", "Chapeaux, echarpes, ceintures, gants, cravates"),
        ("Mode & Accessoires", "Bijoux & Joaillerie", "Montres, bagues, colliers, bijoux fantaisie"),
        ("High-Tech & Electronique", "Telephonie", "Smartphones, reconditionne, coques, chargeurs"),
        ("High-Tech & Electronique", "Informatique", "Ordinateurs portables, PC fixes, tablettes, moniteurs"),
        ("High-Tech & Electronique", "Composants & Peripheriques", "Cartes graphiques, disques durs, claviers/souris"),
        ("High-Tech & Electronique", "Image & Son", "Televiseurs, videoprojecteurs, enceintes, casques audio"),
        ("High-Tech & Electronique", "Photo & Video", "Appareils photo, objectifs, drones, cameras sport"),
        ("High-Tech & Electronique", "Gaming", "Consoles (PS5/Xbox/Switch), jeux video, accessoires gaming"),
        ("High-Tech & Electronique", "Maison Connectee", "Assistants vocaux, securite, eclairage connecte"),
        ("Maison, Jardin & Bricolage", "Mobilier", "Canapes, lits, tables, chaises, rangements"),
        ("Maison, Jardin & Bricolage", "Decoration & Linge", "Luminaires, tapis, rideaux, linge de lit"),
        ("Maison, Jardin & Bricolage", "Cuisine & Art de la table", "Ustensiles, poeles/casseroles, vaisselle"),
        ("Maison, Jardin & Bricolage", "Gros Electromenager", "Lave-linge, frigo, four, lave-vaisselle"),
        ("Maison, Jardin & Bricolage", "Petit Electromenager", "Aspirateurs, cafetieres, robots cuisine"),
        ("Maison, Jardin & Bricolage", "Bricolage & Outillage", "Outillage electroportatif, plomberie, electricite"),
        ("Maison, Jardin & Bricolage", "Jardin & Piscine", "Mobilier de jardin, barbecues, tondeuses, piscines"),
        ("Beaute, Sante & Bien-etre", "Maquillage", "Teint, yeux, levres, ongles"),
        ("Beaute, Sante & Bien-etre", "Soins Visage & Corps", "Cremes, serums, nettoyants, solaires"),
        ("Beaute, Sante & Bien-etre", "Capillaire", "Shampoings, colorations, lisseurs/seche-cheveux"),
        ("Beaute, Sante & Bien-etre", "Parfums", "Femme, Homme, Enfant, bougies parfumees"),
        ("Beaute, Sante & Bien-etre", "Sante & Parapharmacie", "Premiers secours, vitamines, hygiene dentaire"),
        ("Beaute, Sante & Bien-etre", "Bien-etre & Naturel", "Huiles essentielles, CBD, complements alimentaires"),
        ("Sports & Loisirs", "Vetements & Chaussures de Sport", "Running, fitness, maillots, thermique"),
        ("Sports & Loisirs", "Materiel de Fitness", "Musculation, tapis de course, yoga"),
        ("Sports & Loisirs", "Sports d'Exterieur", "Randonnee, camping, escalade, ski"),
        ("Sports & Loisirs", "Cycles & Glisse", "Velos, trottinettes, skate, surf"),
        ("Sports & Loisirs", "Nutrition Sportive", "Proteines, barres energetiques, boissons"),
        ("Culture, Jeux & Divertissement", "Livres & Presse", "Romans, BD/Manga, scolaire, ebooks"),
        ("Culture, Jeux & Divertissement", "Jeux & Jouets", "Jeux de societe, poupees, construction, educatif"),
        ("Alimentation & Boissons", "Epicerie Salee & Sucree", "Conserves, pates, chocolats, biscuits"),
        ("Alimentation & Boissons", "Boissons & Cave", "Vins, spiritueux, bieres, sodas, cafe/the"),
        ("Animaux", "Chiens", "Croquettes, laisses, couchages, jouets"),
        ("Animaux", "Chats", "Arbres a chat, litiere, nourriture"),
        ("Auto, Moto & Industrie", "Pieces Auto/Moto", "Pneus, batteries, pieces mecaniques, huiles"),
        ("Auto, Moto & Industrie", "Equipement & Accessoires", "Casques moto, nettoyage, audio embarque"),
        ("Divers & Specialise", "Cadeaux & Gadgets", "Box mensuelles, gadgets humoristiques"),
        ("Divers & Specialise", "Services", "Billetterie, voyage, impression photo, formations"),
        ("Divers & Specialise", "Generaliste", "Marketplaces vendant de tout sans dominante"),
    ]

    added = 0
    for i, (cat, subcat, desc) in enumerate(default_taxonomy):
        add_taxonomy_entry(db, cat, subcat, desc, sort_order=i)
        added += 1

    return added


def build_taxonomy_prompt(db) -> str:
    """Construit le prompt de taxonomie a partir de la base de donnees."""
    taxonomy = get_all_taxonomy(db, active_only=True)

    if not taxonomy:
        return ""

    categories = {}
    for entry in taxonomy:
        if entry.category not in categories:
            categories[entry.category] = []
        categories[entry.category].append(entry)

    lines = []
    for i, (cat_name, entries) in enumerate(categories.items(), 1):
        lines.append(f"\n{i}. {cat_name}")
        for entry in entries:
            desc = f": {entry.description}" if entry.description else ""
            lines.append(f"   - {entry.subcategory}{desc}")

    return "\n".join(lines)


# ============================================================================
# CLASSIFICATION DES PAGES
# ============================================================================

def get_unclassified_pages(db, limit: int = 100, with_website_only: bool = True) -> List[PageRecherche]:
    """Recupere les pages non classifiees."""
    with db.get_session() as session:
        query = session.query(PageRecherche).filter(
            (PageRecherche.thematique == None) | (PageRecherche.thematique == "")
        )
        if with_website_only:
            query = query.filter(
                PageRecherche.lien_site != None,
                PageRecherche.lien_site != ""
            )
        return query.order_by(PageRecherche.created_at.desc()).limit(limit).all()


def get_pages_for_classification(db, page_ids: List[str] = None, limit: int = 100) -> List[Dict]:
    """Recupere les pages a classifier avec leurs URLs."""
    with db.get_session() as session:
        query = session.query(PageRecherche)

        if page_ids:
            query = query.filter(PageRecherche.page_id.in_(page_ids))
        else:
            query = query.filter(
                (PageRecherche.thematique == None) | (PageRecherche.thematique == ""),
                PageRecherche.lien_site != None,
                PageRecherche.lien_site != ""
            )

        pages = query.limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "url": p.lien_site,
                "cms": p.cms
            }
            for p in pages
        ]


def update_page_classification(
    db,
    page_id: str,
    category: str,
    subcategory: str,
    confidence: float
) -> bool:
    """Met a jour la classification d'une page."""
    with db.get_session() as session:
        page = session.query(PageRecherche).filter(
            PageRecherche.page_id == page_id
        ).first()

        if not page:
            return False

        page.thematique = category
        page.subcategory = subcategory
        page.classification_confidence = confidence
        page.classified_at = datetime.utcnow()

        return True


def update_pages_classification_batch(db, classifications: List[Dict]) -> int:
    """Met a jour plusieurs classifications en batch."""
    updated = 0
    with db.get_session() as session:
        for c in classifications:
            page = session.query(PageRecherche).filter(
                PageRecherche.page_id == c["page_id"]
            ).first()

            if page:
                page.thematique = c.get("category", "")
                page.subcategory = c.get("subcategory", "")
                page.classification_confidence = c.get("confidence", 0.0)
                page.classified_at = datetime.utcnow()
                updated += 1

    return updated


def get_classification_stats(db) -> Dict:
    """Statistiques de classification."""
    with db.get_session() as session:
        total = session.query(func.count(PageRecherche.id)).scalar() or 0

        classified = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.thematique != None,
            PageRecherche.thematique != ""
        ).scalar() or 0

        unclassified = total - classified

        top_categories = session.query(
            PageRecherche.thematique,
            func.count(PageRecherche.id).label('count')
        ).filter(
            PageRecherche.thematique != None,
            PageRecherche.thematique != ""
        ).group_by(
            PageRecherche.thematique
        ).order_by(
            func.count(PageRecherche.id).desc()
        ).limit(10).all()

        return {
            "total": total,
            "classified": classified,
            "unclassified": unclassified,
            "classification_rate": round(classified / total * 100, 1) if total > 0 else 0,
            "top_categories": [{"category": c, "count": n} for c, n in top_categories]
        }
