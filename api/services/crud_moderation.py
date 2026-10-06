"""
Tableau de bord des modérateurs RP : tout ce qui attend une décision, ce qui reste à suivre, et l'historique.

- À traiter : déclarations de guerre en attente, ajustements de population, fermes déclarées, pièges révélés à juger.
  Une demande ou un piège dont le modérateur est l'auteur y figure (propre = True) : un autre doit trancher.
- Suivi : guerres en cours (à clore une fois l'issue jouée), fermes à mettre en conformité (le joueur a la main),
  actions encore scellées (lecture tracée possible).
- Historique : décisions des modérateurs et lectures tracées, des plus récentes aux plus anciennes, reconstituées à
  partir des tables de chaque domaine (aucune table d'historique séparée à tenir à jour).

Les décisions passent par les routes de chaque domaine (guerres, population, fermes, actions) : ce module ne fait que lire.
"""
from sqlmodel import Session, select

from ..db import models, schemas
from . import crud_actions, crud_conflits, crud_fermes, crud_population
from .crud import get_ville_by_id

HISTORIQUE_MAX = 200  # entrées de l'historique renvoyées, des plus récentes aux plus anciennes


#region À traiter et suivi

def _a_traiter(db: Session, user: schemas.Users):
    guerres = db.exec(select(models.Guerres).where(models.Guerres.status == "en_attente").order_by(models.Guerres.declared_at)).all()
    ajustements = crud_population.ajustements_en_attente(db, user)
    fermes = db.exec(select(models.Fermes).where(models.Fermes.status == "en_attente").order_by(models.Fermes.created_at)).all()
    pieges = db.exec(
        select(models.ActionsSecretes)
        .where(models.ActionsSecretes.piege == True, models.ActionsSecretes.revealed_at.is_not(None))  # noqa: E712
        .where(models.ActionsSecretes.piege_verdict.is_(None))
        .order_by(models.ActionsSecretes.revealed_at)
    ).all()
    return {
        "guerres": [crud_conflits.guerre_infos(db, guerre) for guerre in guerres],
        "ajustements": [{**ajustement, "propre": (ajustement["demande_par"] or {}).get("id") == user.id} for ajustement in ajustements],
        "fermes": [crud_fermes.ferme_infos(db, ferme) for ferme in fermes],
        "pieges": [{**crud_actions.action_complete(db, action), "propre": crud_actions.est_auteur(db, user, action)} for action in pieges],
    }

def _suivi(db: Session):
    guerres = db.exec(select(models.Guerres).where(models.Guerres.status == "en_cours").order_by(models.Guerres.validated_at)).all()
    fermes = db.exec(select(models.Fermes).where(models.Fermes.status == "a_corriger").order_by(models.Fermes.decision_at)).all()
    scellees = db.exec(
        select(models.ActionsSecretes).where(models.ActionsSecretes.revealed_at.is_(None)).order_by(models.ActionsSecretes.created_at)
    ).all()
    return {
        "guerres": [crud_conflits.guerre_infos(db, guerre) for guerre in guerres],
        "fermes": [crud_fermes.ferme_infos(db, ferme) for ferme in fermes],
        # Existence seulement : le contenu se lit (et la lecture se trace) sur la page des actions secrètes
        "actions_scellees": [crud_actions.action_publique(db, action) | {"reveal_at": action.reveal_at} for action in scellees],
    }

#endregion
#region Historique

def _entree(categorie: str, date, titre: str, moderateur_id: int | None, db: Session, decision: str, lien: str | None = None, note: str | None = None):
    return {
        "categorie": categorie,
        "date": date,
        "titre": titre,
        "decision": decision,
        "note": note,
        "lien": lien,
        "moderateur": crud_conflits._user_summary(db, moderateur_id),
    }

def _historique_guerres(db: Session):
    decisions = {"validation": "Guerre validée", "refus": "Déclaration refusée", "fin": "Guerre terminée"}
    statement = select(models.GuerreEvenements, models.Guerres).where(
        models.GuerreEvenements.type.in_(tuple(decisions)), models.Guerres.id == models.GuerreEvenements.guerre_id
    )
    return [
        _entree("guerres", evenement.created_at, guerre.title, evenement.created_by, db, decisions[evenement.type],
                f"/guerre/{guerre.id}", evenement.description if evenement.type != "fin" else evenement.title)
        for evenement, guerre in db.exec(statement).all()
    ]

def _historique_population(db: Session):
    decisions = {"accepte": "Ajustement accepté", "refuse": "Ajustement refusé", "retire": "Ajustement retiré"}
    statement = select(models.PopulationAjustements).where(
        models.PopulationAjustements.decision_at.is_not(None), models.PopulationAjustements.moderateur_id.is_not(None)
    )
    entrees = []
    for ajustement in db.exec(statement).all():
        db_ville = get_ville_by_id(db, ajustement.ville_id) if ajustement.ville_id else None
        titre = f"{db_ville.title if db_ville else 'Ville disparue'} ({'+' if ajustement.ecart > 0 else '−'}{abs(ajustement.ecart)})"
        lien = f"/civilisation/{db_ville.civilisation_id}/ville/{db_ville.id}#population" if db_ville else None
        note = ajustement.decision_note or ajustement.motif
        entrees.append(_entree("population", ajustement.decision_at, titre, ajustement.moderateur_id, db,
                               decisions.get(ajustement.status, ajustement.status), lien, note))
    return entrees

def _historique_fermes(db: Session):
    decisions = {"validee": "Ferme validée", "a_corriger": "Mise en conformité demandée"}
    statement = select(models.Fermes).where(models.Fermes.decision_at.is_not(None))
    return [
        _entree("fermes", ferme.decision_at, ferme.title, ferme.moderateur_id, db,
                decisions.get(ferme.status, "Ferme modifiée depuis la décision"), f"/fermes#ferme-{ferme.id}", ferme.decision_note)
        for ferme in db.exec(statement).all()
    ]

def _historique_actions(db: Session):
    entrees = []
    actions = {action.id: action for action in db.exec(select(models.ActionsSecretes)).all()}
    for action in actions.values():
        code = crud_actions.code_action(action)
        # Une action scellée ne montre que son code ; révélée, son titre
        titre = f"{code} · {action.title}" if action.revealed_at else code
        lien = f"/actions-secretes#{code}"
        if action.reveal_mode == "moderateur":
            entrees.append(_entree("actions", action.revealed_at, titre, action.revealed_by, db, "Action révélée par la modération", lien, action.reveal_motif))
        if action.piege_verdict:
            decision = "Piège jugé mortel" if action.piege_verdict == "mortel" else "Piège réduit à une blessure"
            entrees.append(_entree("actions", action.piege_decision_at, titre, action.piege_moderateur_id, db, decision, lien, action.piege_note))
    for lecture in db.exec(select(models.ActionSecreteLectures)).all():
        action = actions.get(lecture.action_id)
        if not action:
            continue
        code = crud_actions.code_action(action)
        titre = f"{code} · {action.title}" if action.revealed_at else code
        entrees.append(_entree("actions", lecture.read_at, titre, lecture.user_id, db, f"Lecture tracée ({lecture.role})", f"/actions-secretes#{code}"))
    return entrees

def _historique_chroniques(db: Session):
    return [
        _entree("chroniques", fait.created_at, fait.title, fait.created_by, db, "Fait inscrit dans les chroniques", "/chroniques")
        for fait in db.exec(select(models.ChroniquesFaits)).all()
    ]

def historique(db: Session, limite: int = HISTORIQUE_MAX):
    entrees = (
        _historique_guerres(db) + _historique_population(db) + _historique_fermes(db)
        + _historique_actions(db) + _historique_chroniques(db)
    )
    entrees = [entree for entree in entrees if entree["date"] is not None]
    entrees.sort(key=lambda entree: entree["date"], reverse=True)
    return entrees[:limite]

#endregion

def tableau(db: Session, user: schemas.Users):
    # { a_traiter: { guerres, ajustements, fermes, pieges }, suivi: { guerres, fermes, actions_scellees }, historique }
    crud_conflits._require_moderateur(user)
    return {"a_traiter": _a_traiter(db, user), "suivi": _suivi(db), "historique": historique(db)}
