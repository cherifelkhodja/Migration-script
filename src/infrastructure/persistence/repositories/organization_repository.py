"""
Repository pour l'organisation des pages (tags, blacklist, favoris, collections, notes).
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy import func

from src.infrastructure.persistence.models import (
    Blacklist,
    Tag,
    PageTag,
    PageNote,
    Favorite,
    Collection,
    CollectionPage,
    SavedFilter,
    ScheduledScan,
)


# ============================================================================
# BLACKLIST
# ============================================================================

def add_to_blacklist(db, page_id: str, page_name: str = "", raison: str = "") -> bool:
    """Ajoute une page a la blacklist."""
    with db.get_session() as session:
        existing = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()
        if existing:
            return False
        entry = Blacklist(
            page_id=str(page_id),
            page_name=page_name,
            raison=raison,
            added_at=datetime.utcnow()
        )
        session.add(entry)
        return True


def remove_from_blacklist(db, page_id: str) -> bool:
    """Retire une page de la blacklist."""
    with db.get_session() as session:
        entry = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()
        if entry:
            session.delete(entry)
            return True
        return False


def get_blacklist(db) -> List[Dict]:
    """Recupere toute la blacklist."""
    with db.get_session() as session:
        entries = session.query(Blacklist).order_by(
            Blacklist.added_at.desc()
        ).all()
        return [
            {
                "page_id": e.page_id,
                "page_name": e.page_name,
                "raison": e.raison,
                "added_at": e.added_at
            }
            for e in entries
        ]


def is_in_blacklist(db, page_id: str) -> bool:
    """Verifie si une page est dans la blacklist."""
    with db.get_session() as session:
        return session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first() is not None


def get_blacklist_ids(db) -> set:
    """Recupere tous les page_id de la blacklist."""
    with db.get_session() as session:
        entries = session.query(Blacklist.page_id).all()
        return {e.page_id for e in entries}


def bulk_add_to_blacklist(db, page_ids: List[str], raison: str = "") -> int:
    """Ajoute plusieurs pages a la blacklist."""
    count = 0
    for pid in page_ids:
        if add_to_blacklist(db, pid, raison=raison):
            count += 1
    return count


# ============================================================================
# TAGS
# ============================================================================

def get_all_tags(db) -> List[Dict]:
    """Recupere tous les tags."""
    with db.get_session() as session:
        tags = session.query(Tag).order_by(Tag.name).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]


def create_tag(db, name: str, color: str = "#3B82F6") -> Optional[int]:
    """Cree un nouveau tag."""
    with db.get_session() as session:
        existing = session.query(Tag).filter(Tag.name == name).first()
        if existing:
            return None
        tag = Tag(name=name, color=color)
        session.add(tag)
        session.flush()
        return tag.id


def delete_tag(db, tag_id: int) -> bool:
    """Supprime un tag et ses associations."""
    with db.get_session() as session:
        session.query(PageTag).filter(PageTag.tag_id == tag_id).delete()
        deleted = session.query(Tag).filter(Tag.id == tag_id).delete()
        return deleted > 0


def add_tag_to_page(db, page_id: str, tag_id: int) -> bool:
    """Ajoute un tag a une page."""
    with db.get_session() as session:
        existing = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).first()
        if existing:
            return False
        pt = PageTag(page_id=page_id, tag_id=tag_id)
        session.add(pt)
        return True


def remove_tag_from_page(db, page_id: str, tag_id: int) -> bool:
    """Retire un tag d'une page."""
    with db.get_session() as session:
        deleted = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).delete()
        return deleted > 0


def get_page_tags(db, page_id: str) -> List[Dict]:
    """Recupere les tags d'une page."""
    with db.get_session() as session:
        results = session.query(Tag).join(
            PageTag, Tag.id == PageTag.tag_id
        ).filter(PageTag.page_id == page_id).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in results]


def get_pages_by_tag(db, tag_id: int) -> List[str]:
    """Recupere les page_ids ayant un tag specifique."""
    with db.get_session() as session:
        results = session.query(PageTag.page_id).filter(PageTag.tag_id == tag_id).all()
        return [r[0] for r in results]


def bulk_add_tag(db, tag_id: int, page_ids: List[str]) -> int:
    """Ajoute un tag a plusieurs pages."""
    count = 0
    for pid in page_ids:
        if add_tag_to_page(db, pid, tag_id):
            count += 1
    return count


# ============================================================================
# NOTES
# ============================================================================

def get_page_notes(db, page_id: str) -> List[Dict]:
    """Recupere les notes d'une page."""
    with db.get_session() as session:
        notes = session.query(PageNote).filter(
            PageNote.page_id == page_id
        ).order_by(PageNote.created_at.desc()).all()
        return [{
            "id": n.id,
            "content": n.content,
            "created_at": n.created_at,
            "updated_at": n.updated_at
        } for n in notes]


def add_page_note(db, page_id: str, content: str) -> int:
    """Ajoute une note a une page."""
    with db.get_session() as session:
        note = PageNote(page_id=page_id, content=content)
        session.add(note)
        session.flush()
        return note.id


def update_page_note(db, note_id: int, content: str) -> bool:
    """Met a jour une note."""
    with db.get_session() as session:
        note = session.query(PageNote).filter(PageNote.id == note_id).first()
        if note:
            note.content = content
            note.updated_at = datetime.utcnow()
            return True
        return False


def delete_page_note(db, note_id: int) -> bool:
    """Supprime une note."""
    with db.get_session() as session:
        deleted = session.query(PageNote).filter(PageNote.id == note_id).delete()
        return deleted > 0


# ============================================================================
# FAVORITES
# ============================================================================

def get_favorites(db) -> List[str]:
    """Recupere tous les page_ids favoris."""
    with db.get_session() as session:
        favs = session.query(Favorite.page_id).order_by(Favorite.added_at.desc()).all()
        return [f[0] for f in favs]


def is_favorite(db, page_id: str) -> bool:
    """Verifie si une page est en favori."""
    with db.get_session() as session:
        return session.query(Favorite).filter(Favorite.page_id == page_id).first() is not None


def add_favorite(db, page_id: str) -> bool:
    """Ajoute une page aux favoris."""
    with db.get_session() as session:
        existing = session.query(Favorite).filter(Favorite.page_id == page_id).first()
        if existing:
            return False
        fav = Favorite(page_id=page_id)
        session.add(fav)
        return True


def remove_favorite(db, page_id: str) -> bool:
    """Retire une page des favoris."""
    with db.get_session() as session:
        deleted = session.query(Favorite).filter(Favorite.page_id == page_id).delete()
        return deleted > 0


def toggle_favorite(db, page_id: str) -> bool:
    """Bascule le statut favori. Retourne True si maintenant favori."""
    if is_favorite(db, page_id):
        remove_favorite(db, page_id)
        return False
    else:
        add_favorite(db, page_id)
        return True


def bulk_add_to_favorites(db, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages aux favoris."""
    count = 0
    for pid in page_ids:
        if add_favorite(db, pid):
            count += 1
    return count


# ============================================================================
# COLLECTIONS
# ============================================================================

def get_collections(db) -> List[Dict]:
    """Recupere toutes les collections avec le nombre de pages."""
    with db.get_session() as session:
        collections = session.query(Collection).order_by(Collection.name).all()
        result = []
        for c in collections:
            count = session.query(func.count(CollectionPage.id)).filter(
                CollectionPage.collection_id == c.id
            ).scalar()
            result.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "color": c.color,
                "icon": c.icon,
                "page_count": count or 0,
                "created_at": c.created_at
            })
        return result


def create_collection(
    db,
    name: str,
    description: str = "",
    color: str = "#6366F1",
    icon: str = "📁"
) -> int:
    """Cree une nouvelle collection."""
    with db.get_session() as session:
        coll = Collection(name=name, description=description, color=color, icon=icon)
        session.add(coll)
        session.flush()
        return coll.id


def update_collection(
    db,
    collection_id: int,
    name: str = None,
    description: str = None,
    color: str = None,
    icon: str = None
) -> bool:
    """Met a jour une collection."""
    with db.get_session() as session:
        coll = session.query(Collection).filter(Collection.id == collection_id).first()
        if not coll:
            return False
        if name is not None:
            coll.name = name
        if description is not None:
            coll.description = description
        if color is not None:
            coll.color = color
        if icon is not None:
            coll.icon = icon
        return True


def delete_collection(db, collection_id: int) -> bool:
    """Supprime une collection et ses associations."""
    with db.get_session() as session:
        session.query(CollectionPage).filter(CollectionPage.collection_id == collection_id).delete()
        deleted = session.query(Collection).filter(Collection.id == collection_id).delete()
        return deleted > 0


def add_page_to_collection(db, collection_id: int, page_id: str) -> bool:
    """Ajoute une page a une collection."""
    with db.get_session() as session:
        existing = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).first()
        if existing:
            return False
        cp = CollectionPage(collection_id=collection_id, page_id=page_id)
        session.add(cp)
        return True


def remove_page_from_collection(db, collection_id: int, page_id: str) -> bool:
    """Retire une page d'une collection."""
    with db.get_session() as session:
        deleted = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).delete()
        return deleted > 0


def get_collection_pages(db, collection_id: int) -> List[str]:
    """Recupere les page_ids d'une collection."""
    with db.get_session() as session:
        results = session.query(CollectionPage.page_id).filter(
            CollectionPage.collection_id == collection_id
        ).order_by(CollectionPage.added_at.desc()).all()
        return [r[0] for r in results]


def get_page_collections(db, page_id: str) -> List[Dict]:
    """Recupere les collections d'une page."""
    with db.get_session() as session:
        results = session.query(Collection).join(
            CollectionPage, Collection.id == CollectionPage.collection_id
        ).filter(CollectionPage.page_id == page_id).all()
        return [{
            "id": c.id,
            "name": c.name,
            "color": c.color,
            "icon": c.icon
        } for c in results]


def bulk_add_to_collection(db, collection_id: int, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages a une collection."""
    count = 0
    for pid in page_ids:
        if add_page_to_collection(db, collection_id, pid):
            count += 1
    return count


# ============================================================================
# SAVED FILTERS
# ============================================================================

def get_saved_filters(db, filter_type: str = None) -> List[Dict]:
    """Recupere les filtres sauvegardes."""
    with db.get_session() as session:
        query = session.query(SavedFilter)
        if filter_type:
            query = query.filter(SavedFilter.filter_type == filter_type)
        filters = query.order_by(SavedFilter.name).all()
        return [{
            "id": f.id,
            "name": f.name,
            "filter_type": f.filter_type,
            "filter_data": f.filter_data,
            "created_at": f.created_at
        } for f in filters]


def save_filter(
    db,
    name: str,
    filter_type: str,
    filter_data: str
) -> int:
    """Sauvegarde un filtre."""
    with db.get_session() as session:
        sf = SavedFilter(name=name, filter_type=filter_type, filter_data=filter_data)
        session.add(sf)
        session.flush()
        return sf.id


def delete_saved_filter(db, filter_id: int) -> bool:
    """Supprime un filtre sauvegarde."""
    with db.get_session() as session:
        deleted = session.query(SavedFilter).filter(SavedFilter.id == filter_id).delete()
        return deleted > 0


# ============================================================================
# SCHEDULED SCANS
# ============================================================================

def get_scheduled_scans(db, active_only: bool = False) -> List[Dict]:
    """Recupere les scans programmes."""
    with db.get_session() as session:
        query = session.query(ScheduledScan)
        if active_only:
            query = query.filter(ScheduledScan.is_active == True)
        scans = query.order_by(ScheduledScan.next_run).all()
        return [{
            "id": s.id,
            "name": s.name,
            "keywords": s.keywords,
            "countries": s.countries,
            "languages": getattr(s, 'languages', 'fr'),
            "frequency": s.frequency,
            "is_active": s.is_active,
            "last_run": s.last_run,
            "next_run": s.next_run,
            "created_at": s.created_at
        } for s in scans]


def create_scheduled_scan(
    db,
    name: str,
    keywords: str,
    countries: str = "FR",
    languages: str = "fr",
    frequency: str = "daily",
    next_run: datetime = None
) -> int:
    """Cree un scan programme."""
    with db.get_session() as session:
        scan = ScheduledScan(
            name=name,
            keywords=keywords,
            countries=countries,
            languages=languages,
            frequency=frequency,
            is_active=True,
            next_run=next_run or datetime.utcnow()
        )
        session.add(scan)
        session.flush()
        return scan.id


def update_scheduled_scan(
    db,
    scan_id: int,
    name: str = None,
    keywords: str = None,
    countries: str = None,
    languages: str = None,
    frequency: str = None,
    is_active: bool = None,
    next_run: datetime = None
) -> bool:
    """Met a jour un scan programme."""
    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False
        if name is not None:
            scan.name = name
        if keywords is not None:
            scan.keywords = keywords
        if countries is not None:
            scan.countries = countries
        if languages is not None:
            scan.languages = languages
        if frequency is not None:
            scan.frequency = frequency
        if is_active is not None:
            scan.is_active = is_active
        if next_run is not None:
            scan.next_run = next_run
        return True


def delete_scheduled_scan(db, scan_id: int) -> bool:
    """Supprime un scan programme."""
    with db.get_session() as session:
        deleted = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).delete()
        return deleted > 0


def mark_scan_executed(db, scan_id: int) -> bool:
    """Marque un scan comme execute."""
    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False
        scan.last_run = datetime.utcnow()
        # Calculer la prochaine execution selon la frequence
        if scan.frequency == "hourly":
            scan.next_run = datetime.utcnow() + timedelta(hours=1)
        elif scan.frequency == "daily":
            scan.next_run = datetime.utcnow() + timedelta(days=1)
        elif scan.frequency == "weekly":
            scan.next_run = datetime.utcnow() + timedelta(weeks=1)
        return True
