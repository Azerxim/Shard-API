"""
Postes de gouvernement et élections RP.

Postes
- Le gouvernement d'une civilisation, et celui de chacune de ses villes, a des postes (« Roi », « Bourgmestre »),
  chacun occupé par un personnage résident de la civilisation (un administrateur du site y nomme n'importe quel personnage). Un seul poste par civilisation ou par ville est le
  représentant : son titulaire vote au nom de la civilisation (alliances) ou de la ville (religions).
- Fondateur et Admins de la civilisation (ou administrateur du site) gèrent les postes, ceux de ses villes compris.

Scrutins
- Ouverts par le fondateur ou un admin de la civilisation, de la religion, ou de la civilisation chef de file d'une
  alliance ; sans validation. Annulables par eux tant qu'ils ne sont pas clos.
- Qui vote (corps) : civilisation, ses personnages résidents ; alliance, une voix par civilisation membre (pas les
  observateurs), donnée par son représentant ; religion, au choix à l'ouverture, ses fidèles (foi du personnage) ou
  une voix par ville où elle a la plus forte influence, donnée par le représentant de la ville. Seuls les personnages
  vivants votent ou se présentent ; un joueur vote avec chacun de ses personnages.
- Candidats : les personnages liés (résidents, fidèles, résidents des civilisations membres), présentés par leur
  joueur (ou un administrateur du site) jusqu'à l'ouverture du vote.
- Vote entre deux heures réelles. Secret : on retient qui a voté et le nombre de voix de chaque candidat, jamais le
  lien entre les deux. Public : chaque bulletin est conservé avec le nom du votant. Dans les deux cas, voix et
  bulletins ne sont montrés qu'au dépouillement.
- Deux tours : sans majorité absolue des suffrages exprimés, les deux premiers (ex aequo compris) s'affrontent au second
  tour, aussi long que le premier. À un tour, ou au second, le plus de voix l'emporte ; à égalité, personne n'est élu.
- À la clôture, l'élu prend le poste mis en jeu (civilisation seulement), et le résultat daté en RP entre dans les
  chroniques.
- Aucune tâche planifiée : chaque lecture fait avancer le scrutin (ouverture du vote, second tour, dépouillement), et
  les notifications de chaque étape ne partent qu'une fois.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from . import crud_conflits, crud_lignees, crud_notifications, crud_personnages
from .crud import get_civilisation_by_id, get_religion_by_id, get_ville_by_id

ENTITES = ("civilisation", "religion", "alliance")
CORPS = {"personnages": "personnage", "villes": "ville", "civilisations": "civilisation"}
MODES = ("secret", "public")
TITLE_MAX = 120
POSTE_MAX = 60
PROGRAMME_MAX = 2000
DUREE_MAX = dt.timedelta(days=30)
DUREE_MIN = dt.timedelta(minutes=10)
LIENS = {"civilisation": "/civilisation/{}", "religion": "/religion/{}", "alliance": "/alliance/{}"}
ARTICLES = {"civilisation": "la civilisation", "religion": "la religion", "alliance": "l'alliance"}


#region Entités et droits

def _entite(db: Session, entity_type: str, entity_id: int):
    if entity_type == "civilisation":
        return get_civilisation_by_id(db, entity_id)
    if entity_type == "religion":
        return get_religion_by_id(db, entity_id)
    if entity_type == "alliance":
        return crud_conflits.get_alliance(db, entity_id)
    return None

def _require_entite(db: Session, entity_type: str, entity_id: int):
    if entity_type not in ENTITES:
        raise HTTPException(status_code=400, detail="Un scrutin se tient dans une civilisation, une religion ou une alliance")
    entite = _entite(db, entity_type, entity_id)
    if not entite:
        raise HTTPException(status_code=404, detail=f"{ARTICLES[entity_type].capitalize()} n'existe pas")
    return entite

def peut_organiser(db: Session, user: schemas.Users | None, entity_type: str, entity_id: int) -> bool:
    # Fondateur ou Admin de la civilisation, de la religion, ou de la civilisation chef de file de l'alliance
    if entity_type == "alliance":
        chef = crud_conflits._alliance_chef(db, entity_id)
        return bool(chef) and crud_conflits.can_manage_entity(db, user, "civilisation", chef.civilisation_id)
    return crud_conflits.can_manage_entity(db, user, entity_type, entity_id)

def _organisateurs(db: Session, entity_type: str, entity_id: int) -> set[int]:
    if entity_type == "alliance":
        chef = crud_conflits._alliance_chef(db, entity_id)
        return crud_notifications.gestionnaires(db, "civilisation", chef.civilisation_id) if chef else set()
    return crud_notifications.gestionnaires(db, entity_type, entity_id)

def _civilisation_du_poste(db: Session, entity_type: str, entity_id: int):
    # Civilisation dont relève un poste : la sienne, ou celle de la ville
    if entity_type == "civilisation":
        return get_civilisation_by_id(db, entity_id)
    if entity_type == "ville":
        ville = get_ville_by_id(db, entity_id)
        return get_civilisation_by_id(db, ville.civilisation_id) if ville and ville.civilisation_id else None
    return None

#endregion
#region Postes

def _poste_infos(db: Session, poste: models.GouvernementPostes):
    personnage = crud_personnages.get_personnage(db, poste.personnage_id) if poste.personnage_id else None
    return {
        "id": poste.id,
        "entity_type": poste.entity_type,
        "entity_id": poste.entity_id,
        "title": poste.title,
        "is_representant": poste.is_representant,
        "ordre": poste.ordre,
        "personnage": crud_lignees.personnage_resume(personnage),
    }

def _postes(db: Session, entity_type: str, entity_id: int):
    statement = select(models.GouvernementPostes).where(models.GouvernementPostes.entity_type == entity_type, models.GouvernementPostes.entity_id == entity_id)
    return sorted(db.exec(statement).all(), key=lambda p: (p.ordre, p.id))

def list_postes(db: Session, entity_type: str, entity_id: int):
    return [_poste_infos(db, poste) for poste in _postes(db, entity_type, entity_id)]

def postes_du_personnage(db: Session, personnageID: int):
    # Rôles d'un personnage : ses postes, avec la civilisation ou la ville qu'il gouverne (fiche du personnage)
    result = []
    for poste in db.exec(select(models.GouvernementPostes).where(models.GouvernementPostes.personnage_id == personnageID)).all():
        if poste.entity_type == "ville":
            ville = get_ville_by_id(db, poste.entity_id)
            lieu = {"type": "ville", "id": ville.id, "title": ville.title, "lien": f"/civilisation/{ville.civilisation_id}/ville/{ville.id}"} if ville else None
        else:
            civilisation = get_civilisation_by_id(db, poste.entity_id)
            lieu = {"type": "civilisation", "id": civilisation.id, "title": civilisation.title, "lien": f"/civilisation/{civilisation.id}"} if civilisation else None
        if lieu:
            result.append({"id": poste.id, "title": poste.title, "is_representant": poste.is_representant, "lieu": lieu})
    return result

def _representant(db: Session, entity_type: str, entity_id: int) -> models.Personnages | None:
    poste = next((p for p in _postes(db, entity_type, entity_id) if p.is_representant), None)
    personnage = crud_personnages.get_personnage(db, poste.personnage_id) if poste and poste.personnage_id else None
    return personnage if personnage and personnage.status == "vivant" else None

def _require_gestion_postes(db: Session, user: schemas.Users, entity_type: str, entity_id: int):
    if entity_type not in ("civilisation", "ville"):
        raise HTTPException(status_code=400, detail="Les postes appartiennent au gouvernement d'une civilisation ou d'une ville")
    civilisation = _civilisation_du_poste(db, entity_type, entity_id)
    if not civilisation:
        raise HTTPException(status_code=404, detail="Cette civilisation ou cette ville n'existe pas")
    if not crud_conflits.can_manage_entity(db, user, "civilisation", civilisation.id):
        raise HTTPException(status_code=403, detail="Seuls le fondateur et les admins de la civilisation gèrent son gouvernement")
    return civilisation

def _verifier_titulaire(db: Session, user: schemas.Users, civilisation, personnageID: int | None):
    if personnageID is None:
        return
    personnage = crud_personnages.get_personnage(db, personnageID)
    if not personnage:
        raise HTTPException(status_code=404, detail="Ce personnage n'existe pas")
    if personnage.civilisation_id != civilisation.id and not user.is_admin:
        raise HTTPException(status_code=400, detail=f"{personnage.name} doit résider dans {civilisation.title} pour y occuper un poste")

def _seul_representant(db: Session, poste: models.GouvernementPostes):
    for autre in _postes(db, poste.entity_type, poste.entity_id):
        if autre.id != poste.id and autre.is_representant:
            autre.is_representant = False
            db.add(autre)

def _titre_poste(title: str | None) -> str:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Donnez un nom au poste")
    if len(title) > POSTE_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom d'un poste ne dépasse pas {POSTE_MAX} caractères")
    return title

def create_poste(db: Session, user: schemas.Users, body: schemas.PosteCreate):
    civilisation = _require_gestion_postes(db, user, body.entity_type, body.entity_id)
    _verifier_titulaire(db, user, civilisation, body.personnage_id)
    existants = _postes(db, body.entity_type, body.entity_id)
    poste = models.GouvernementPostes(
        entity_type=body.entity_type, entity_id=body.entity_id, title=_titre_poste(body.title), personnage_id=body.personnage_id,
        # Le premier poste représente d'office : un gouvernement a toujours qui vote en son nom
        is_representant=bool(body.is_representant) or not any(p.is_representant for p in existants),
        ordre=max((p.ordre for p in existants), default=-1) + 1,
    )
    db.add(poste)
    db.commit()
    db.refresh(poste)
    if poste.is_representant:
        _seul_representant(db, poste)
        db.commit()
    return _poste_infos(db, poste)

def _require_poste(db: Session, ID: int) -> models.GouvernementPostes:
    poste = db.get(models.GouvernementPostes, ID)
    if not poste:
        raise HTTPException(status_code=404, detail="Ce poste n'existe pas")
    return poste

def update_poste(db: Session, user: schemas.Users, ID: int, body: schemas.PosteUpdate):
    poste = _require_poste(db, ID)
    civilisation = _require_gestion_postes(db, user, poste.entity_type, poste.entity_id)
    data = body.model_dump(exclude_unset=True)
    if "title" in data:
        poste.title = _titre_poste(data["title"])
    if "personnage_id" in data:
        _verifier_titulaire(db, user, civilisation, data["personnage_id"])
        poste.personnage_id = data["personnage_id"]
    if data.get("ordre") is not None:
        poste.ordre = data["ordre"]
    if data.get("is_representant"):
        poste.is_representant = True
        _seul_representant(db, poste)
    db.add(poste)
    db.commit()
    db.refresh(poste)
    return _poste_infos(db, poste)

def delete_poste(db: Session, user: schemas.Users, ID: int):
    poste = _require_poste(db, ID)
    _require_gestion_postes(db, user, poste.entity_type, poste.entity_id)
    if any(s.status == "ouvert" for s in db.exec(select(models.Scrutins).where(models.Scrutins.poste_id == poste.id)).all()):
        raise HTTPException(status_code=400, detail="Ce poste est mis en jeu par un scrutin en cours : annulez-le d'abord")
    for scrutin in db.exec(select(models.Scrutins).where(models.Scrutins.poste_id == poste.id)).all():
        scrutin.poste_id = None
        db.add(scrutin)
    representant = poste.is_representant
    entity = (poste.entity_type, poste.entity_id)
    db.delete(poste)
    db.commit()
    # Le représentant disparu : le premier poste restant le remplace
    restants = _postes(db, *entity)
    if representant and restants:
        restants[0].is_representant = True
        db.add(restants[0])
        db.commit()
    return True

#endregion
#region Corps électoral

def _vivants(db: Session, *conditions):
    return db.exec(select(models.Personnages).where(models.Personnages.status == "vivant", *conditions)).all()

def _civilisations_membres(db: Session, allianceID: int):
    # Les observateurs ne votent pas
    return [m.civilisation_id for m in crud_conflits._alliance_membres(db, allianceID) if m.role != "Observateur"]

def _villes_majoritaires(db: Session, religionID: int):
    # Villes où la religion a la plus forte influence (seule en tête : une égalité ne donne la ville à personne)
    villes = []
    presences = db.exec(select(models.VillesReligions).where(models.VillesReligions.religion_id == religionID)).all()
    for presence in presences:
        autres = db.exec(select(models.VillesReligions).where(models.VillesReligions.ville_id == presence.ville_id)).all()
        influence = presence.influence or 0
        if influence > 0 and all((a.influence or 0) < influence for a in autres if a.religion_id != religionID):
            ville = get_ville_by_id(db, presence.ville_id)
            if ville:
                villes.append(ville)
    return villes

def personnages_lies(db: Session, entity_type: str, entity_id: int):
    # Personnages vivants qui peuvent se présenter : résidents, fidèles, résidents des civilisations membres
    if entity_type == "civilisation":
        return _vivants(db, models.Personnages.civilisation_id == entity_id)
    if entity_type == "religion":
        return _vivants(db, models.Personnages.religion_id == entity_id)
    membres = _civilisations_membres(db, entity_id)
    return _vivants(db, models.Personnages.civilisation_id.in_(membres)) if membres else []

def votants(db: Session, scrutin: models.Scrutins):
    # [{ type, id, title, personnage }] : chaque voix et le personnage qui la donne (None : personne pour voter)
    if scrutin.corps == "personnages":
        return [{"type": "personnage", "id": p.id, "title": p.name, "personnage": p} for p in personnages_lies(db, scrutin.entity_type, scrutin.entity_id)]
    if scrutin.corps == "civilisations":
        result = []
        for civilisationID in _civilisations_membres(db, scrutin.entity_id):
            civilisation = get_civilisation_by_id(db, civilisationID)
            if civilisation:
                result.append({"type": "civilisation", "id": civilisation.id, "title": civilisation.title, "personnage": _representant(db, "civilisation", civilisation.id)})
        return result
    return [{"type": "ville", "id": v.id, "title": v.title, "personnage": _representant(db, "ville", v.id)} for v in _villes_majoritaires(db, scrutin.entity_id)]

def _joueurs_votants(db: Session, scrutin: models.Scrutins) -> set[int]:
    return {v["personnage"].user_id for v in votants(db, scrutin) if v["personnage"] and v["personnage"].user_id}

#endregion
#region Déroulement

def _candidats(db: Session, scrutinID: int):
    return sorted(db.exec(select(models.ScrutinCandidats).where(models.ScrutinCandidats.scrutin_id == scrutinID)).all(), key=lambda c: c.created_at)

def _fin_du_vote(scrutin: models.Scrutins) -> dt.datetime:
    return scrutin.tour2_fin if scrutin.tour == 2 and scrutin.tour2_fin else scrutin.vote_fin

def phase(scrutin: models.Scrutins, maintenant: dt.datetime | None = None) -> str:
    # annule, clos, candidatures, vote ou second_tour
    maintenant = maintenant or dt.datetime.now()
    if scrutin.status != "ouvert":
        return scrutin.status
    if maintenant < scrutin.vote_debut:
        return "candidatures"
    return "second_tour" if scrutin.tour == 2 else "vote"

def _lien(scrutin: models.Scrutins) -> str:
    return f"/election/{scrutin.id}"

def _notifier(db: Session, scrutin: models.Scrutins, destinataires, title: str, text: str | None = None, sauf: int | None = None):
    crud_notifications.notifier(db, destinataires, "election", title, text, _lien(scrutin), sauf=sauf)

def _cloturer(db: Session, scrutin: models.Scrutins, resultat: str, elu: models.ScrutinCandidats | None = None):
    scrutin.status = "clos"
    scrutin.resultat = resultat
    scrutin.elu_id = elu.id if elu else None
    scrutin.closed_at = dt.datetime.now()
    db.add(scrutin)
    # L'élu prend le poste mis en jeu, s'il réside toujours dans la civilisation
    poste = db.get(models.GouvernementPostes, scrutin.poste_id) if scrutin.poste_id else None
    personnage = crud_personnages.get_personnage(db, elu.personnage_id) if elu and elu.personnage_id else None
    civilisation = _civilisation_du_poste(db, poste.entity_type, poste.entity_id) if poste else None
    if poste and personnage and civilisation and personnage.civilisation_id == civilisation.id:
        poste.personnage_id = personnage.id
        db.add(poste)
    db.commit()
    candidats = {c.user_id for c in _candidats(db, scrutin.id)}
    destinataires = _joueurs_votants(db, scrutin) | candidats | _organisateurs(db, scrutin.entity_type, scrutin.entity_id)
    textes = {
        "elu": f"{elu.nom} est élu{' au poste de ' + scrutin.poste_title if scrutin.poste_title else ''}." if elu else None,
        "egalite": "Égalité : personne n'est élu.",
        "sans_candidat": "Aucun candidat ne s'est présenté.",
        "sans_suffrage": "Personne n'a voté.",
    }
    _notifier(db, scrutin, destinataires, f"Résultat : {scrutin.title}", textes[resultat])

def _en_tete(candidats, voix):
    meilleur = max((voix(c) for c in candidats), default=0)
    return [c for c in candidats if voix(c) == meilleur], meilleur

def _depouiller(db: Session, scrutin: models.Scrutins):
    candidats = _candidats(db, scrutin.id)
    if scrutin.tour == 2:
        finalistes = [c for c in candidats if c.au_second_tour]
        tete, meilleur = _en_tete(finalistes, lambda c: c.voix_second_tour)
        if meilleur == 0:
            return _cloturer(db, scrutin, "sans_suffrage")
        return _cloturer(db, scrutin, "elu", tete[0]) if len(tete) == 1 else _cloturer(db, scrutin, "egalite")

    exprimes = sum(c.voix for c in candidats)
    if exprimes == 0:
        return _cloturer(db, scrutin, "sans_suffrage")
    tete, meilleur = _en_tete(candidats, lambda c: c.voix)
    if not scrutin.deux_tours:
        return _cloturer(db, scrutin, "elu", tete[0]) if len(tete) == 1 else _cloturer(db, scrutin, "egalite")
    if len(tete) == 1 and meilleur * 2 > exprimes:
        return _cloturer(db, scrutin, "elu", tete[0])

    # Second tour : les deux premiers, ex aequo compris
    finalistes = tete if len(tete) >= 2 else tete + _en_tete([c for c in candidats if c not in tete], lambda c: c.voix)[0]
    finalistes = [c for c in finalistes if c.voix > 0] or finalistes
    for candidat in finalistes:
        candidat.au_second_tour = True
        db.add(candidat)
    scrutin.tour = 2
    scrutin.tour2_fin = scrutin.vote_fin + (scrutin.vote_fin - scrutin.vote_debut)
    scrutin.etape_annoncee = "tour2"
    db.add(scrutin)
    db.commit()
    noms = " et ".join(c.nom for c in finalistes)
    _notifier(db, scrutin, _joueurs_votants(db, scrutin) | {c.user_id for c in candidats},
              f"Second tour : {scrutin.title}", f"Pas de majorité absolue : {noms} s'affrontent au second tour.")

def avancer(db: Session, scrutin: models.Scrutins, maintenant: dt.datetime | None = None):
    # Fait passer le scrutin aux étapes dont l'heure est venue ; sans effet s'il n'y a rien à faire
    maintenant = maintenant or dt.datetime.now()
    if scrutin.status != "ouvert" or maintenant < scrutin.vote_debut:
        return scrutin
    if not _candidats(db, scrutin.id):
        _cloturer(db, scrutin, "sans_candidat")
        return scrutin
    if scrutin.etape_annoncee is None:
        scrutin.etape_annoncee = "vote"
        db.add(scrutin)
        db.commit()
        _notifier(db, scrutin, _joueurs_votants(db, scrutin), f"Le vote est ouvert : {scrutin.title}", f"Jusqu'au {_heure(scrutin.vote_fin)}.")
    if scrutin.tour == 1 and maintenant >= scrutin.vote_fin:
        _depouiller(db, scrutin)
    if scrutin.status == "ouvert" and scrutin.tour == 2 and maintenant >= scrutin.tour2_fin:
        _depouiller(db, scrutin)
    return scrutin

def _heure(moment: dt.datetime) -> str:
    return moment.strftime("%d/%m/%Y à %H h %M")

#endregion
#region Lecture

def _entite_resume(db: Session, scrutin: models.Scrutins):
    entite = _entite(db, scrutin.entity_type, scrutin.entity_id)
    return {
        "type": scrutin.entity_type,
        "id": scrutin.entity_id,
        "title": entite.title if entite else scrutin.entity_title,
        "is_public": entite.is_public is not False if entite else False,
        "lien": LIENS[scrutin.entity_type].format(scrutin.entity_id) if entite else None,
    }

def _a_vote(db: Session, scrutin: models.Scrutins, votant_type: str, votant_id: int) -> bool:
    statement = select(models.ScrutinVotants).where(
        models.ScrutinVotants.scrutin_id == scrutin.id, models.ScrutinVotants.tour == scrutin.tour,
        models.ScrutinVotants.votant_type == votant_type, models.ScrutinVotants.votant_id == votant_id,
    )
    return db.exec(statement).first() is not None

def _participation(db: Session, scrutin: models.Scrutins, tour: int) -> int:
    return len(db.exec(select(models.ScrutinVotants).where(models.ScrutinVotants.scrutin_id == scrutin.id, models.ScrutinVotants.tour == tour)).all())

def _candidat_infos(db: Session, candidat: models.ScrutinCandidats, clos: bool):
    personnage = crud_personnages.get_personnage(db, candidat.personnage_id) if candidat.personnage_id else None
    infos = {
        "id": candidat.id,
        "nom": candidat.nom,
        "programme": candidat.programme,
        "user_id": candidat.user_id,
        "personnage": crud_lignees.personnage_resume(personnage),
        "au_second_tour": candidat.au_second_tour,
    }
    if clos:
        infos.update({"voix": candidat.voix, "voix_second_tour": candidat.voix_second_tour})
    return infos

def scrutin_resume(db: Session, scrutin: models.Scrutins):
    elu = db.get(models.ScrutinCandidats, scrutin.elu_id) if scrutin.elu_id else None
    return {
        "id": scrutin.id,
        "title": scrutin.title,
        "entite": _entite_resume(db, scrutin),
        "corps": scrutin.corps,
        "mode": scrutin.mode,
        "deux_tours": scrutin.deux_tours,
        "poste": {"id": scrutin.poste_id, "title": scrutin.poste_title} if scrutin.poste_title else None,
        "vote_debut": scrutin.vote_debut,
        "vote_fin": scrutin.vote_fin,
        "tour": scrutin.tour,
        "tour2_fin": scrutin.tour2_fin,
        "phase": phase(scrutin),
        "resultat": scrutin.resultat,
        "elu": {"id": elu.id, "nom": elu.nom, "personnage_id": elu.personnage_id} if elu else None,
        "date_rp": scrutin.date_rp,
        "candidats_count": len(_candidats(db, scrutin.id)),
        "created_at": scrutin.created_at,
        "closed_at": scrutin.closed_at,
    }

def _require_scrutin(db: Session, ID: int) -> models.Scrutins:
    scrutin = db.get(models.Scrutins, ID)
    if not scrutin:
        raise HTTPException(status_code=404, detail="Ce scrutin n'existe pas")
    return avancer(db, scrutin)

def read_scrutin(db: Session, user: schemas.Users | None, ID: int):
    scrutin = _require_scrutin(db, ID)
    clos = scrutin.status == "clos"
    candidats = _candidats(db, scrutin.id)
    corps = votants(db, scrutin)
    en_vote = phase(scrutin) in ("vote", "second_tour")
    # Voix que le joueur donne : ses personnages votants, ou ceux qui représentent une civilisation ou une ville
    mes_voix = [
        {"type": v["type"], "id": v["id"], "title": v["title"], "personnage": crud_lignees.personnage_resume(v["personnage"]),
         "a_vote": _a_vote(db, scrutin, v["type"], v["id"])}
        for v in corps if user and v["personnage"] and v["personnage"].user_id == user.id
    ] if scrutin.status == "ouvert" else []
    deja = {c.personnage_id for c in candidats}
    mes_candidats_possibles = [
        crud_lignees.personnage_resume(p) for p in personnages_lies(db, scrutin.entity_type, scrutin.entity_id)
        if user and (p.user_id == user.id or user.is_admin) and p.id not in deja
    ] if phase(scrutin) == "candidatures" else []
    bulletins = []
    if clos and scrutin.mode == "public":
        statement = select(models.ScrutinBulletins).where(models.ScrutinBulletins.scrutin_id == scrutin.id)
        bulletins = [{"tour": b.tour, "candidat_id": b.candidat_id, "votant_type": b.votant_type, "votant_id": b.votant_id, "votant_title": b.votant_title}
                     for b in db.exec(statement).all()]
    return {
        **scrutin_resume(db, scrutin),
        "description": scrutin.description,
        "candidats": [_candidat_infos(db, c, clos) for c in candidats],
        "votants_count": len(corps),
        "votants_sans_representant": [v["title"] for v in corps if not v["personnage"]] if scrutin.corps != "personnages" else [],
        "participation": {"tour1": _participation(db, scrutin, 1), "tour2": _participation(db, scrutin, 2)},
        "mes_voix": mes_voix,
        "a_voter": en_vote and any(not v["a_vote"] for v in mes_voix),
        "mes_candidats_possibles": mes_candidats_possibles,
        "peut_organiser": peut_organiser(db, user, scrutin.entity_type, scrutin.entity_id),
        "bulletins": bulletins,
        "created_by_user": crud_conflits._user_summary(db, scrutin.created_by),
    }

def list_scrutins(db: Session, entity_type: str | None = None, entity_id: int | None = None):
    # Ceux d'une entité, ou ceux de toutes les entités publiques ; en cours d'abord, puis les plus récents
    statement = select(models.Scrutins)
    if entity_type:
        statement = statement.where(models.Scrutins.entity_type == entity_type, models.Scrutins.entity_id == entity_id)
    resumes = [scrutin_resume(db, avancer(db, s)) for s in db.exec(statement).all()]
    if not entity_type:
        resumes = [r for r in resumes if r["entite"]["is_public"]]
    ordre = {"vote": 0, "second_tour": 0, "candidatures": 1, "clos": 2, "annule": 3}
    return sorted(resumes, key=lambda r: (ordre.get(r["phase"], 4), -(r["closed_at"] or r["vote_debut"]).timestamp()))

def mes_votes(db: Session, user: schemas.Users):
    # Scrutins où le joueur a encore une voix à donner (accueil et profil : « actions en attente »)
    result = []
    for scrutin in db.exec(select(models.Scrutins).where(models.Scrutins.status == "ouvert")).all():
        avancer(db, scrutin)
        if phase(scrutin) not in ("vote", "second_tour"):
            continue
        restantes = [v for v in votants(db, scrutin) if v["personnage"] and v["personnage"].user_id == user.id and not _a_vote(db, scrutin, v["type"], v["id"])]
        if restantes:
            result.append({**scrutin_resume(db, scrutin), "voix_restantes": len(restantes), "fin": _fin_du_vote(scrutin)})
    return result

#endregion
#region Écriture

def _naive(moment: dt.datetime) -> dt.datetime:
    # Heures de saisie (datetime-local) : sans fuseau ; une heure avec fuseau est ramenée à l'heure du serveur
    return moment.astimezone().replace(tzinfo=None) if moment.tzinfo else moment

def create_scrutin(db: Session, user: schemas.Users, body: schemas.ScrutinCreate):
    entite = _require_entite(db, body.entity_type, body.entity_id)
    if not peut_organiser(db, user, body.entity_type, body.entity_id):
        raise HTTPException(status_code=403, detail=f"Seuls le fondateur et les admins de {ARTICLES[body.entity_type]} ouvrent un scrutin")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Donnez un titre au scrutin")
    if len(title) > TITLE_MAX:
        raise HTTPException(status_code=400, detail=f"Le titre ne dépasse pas {TITLE_MAX} caractères")

    corps = {"civilisation": "personnages", "alliance": "civilisations"}.get(body.entity_type) or body.corps
    if body.entity_type == "religion" and corps not in ("personnages", "villes"):
        raise HTTPException(status_code=400, detail="Choisissez qui vote : les fidèles, ou les villes où la religion est majoritaire")
    mode = body.mode or "secret"
    if mode not in MODES:
        raise HTTPException(status_code=400, detail="Mode de vote inconnu : secret ou public")

    debut, fin = _naive(body.vote_debut), _naive(body.vote_fin)
    if debut <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="Le vote s'ouvre plus tard : les candidatures se déposent d'ici là")
    if fin - debut < DUREE_MIN:
        raise HTTPException(status_code=400, detail="Le vote dure au moins dix minutes")
    if fin - debut > DUREE_MAX:
        raise HTTPException(status_code=400, detail="Le vote dure trente jours au plus")

    poste = None
    if body.poste_id is not None:
        if body.entity_type != "civilisation":
            raise HTTPException(status_code=400, detail="Seule une civilisation met en jeu un poste de son gouvernement")
        poste = _require_poste(db, body.poste_id)
        civilisation = _civilisation_du_poste(db, poste.entity_type, poste.entity_id)
        if not civilisation or civilisation.id != entite.id:
            raise HTTPException(status_code=400, detail="Ce poste n'appartient pas au gouvernement de la civilisation ni de ses villes")
        if db.exec(select(models.Scrutins).where(models.Scrutins.poste_id == poste.id, models.Scrutins.status == "ouvert")).first():
            raise HTTPException(status_code=400, detail="Un scrutin en cours met déjà ce poste en jeu")

    scrutin = models.Scrutins(
        title=title, description=(body.description or "").strip() or None, entity_type=body.entity_type, entity_id=entite.id,
        entity_title=entite.title, corps=corps, mode=mode, deux_tours=bool(body.deux_tours), poste_id=poste.id if poste else None,
        poste_title=_titre_complet(db, poste) if poste else None, vote_debut=debut, vote_fin=fin, date_rp=body.date_rp, created_by=user.id,
    )
    db.add(scrutin)
    db.commit()
    db.refresh(scrutin)
    joueurs = {p.user_id for p in personnages_lies(db, scrutin.entity_type, scrutin.entity_id)} | _joueurs_votants(db, scrutin)
    _notifier(db, scrutin, joueurs, f"Scrutin ouvert : {scrutin.title}", f"Candidatures jusqu'au {_heure(debut)}, vote jusqu'au {_heure(fin)}.", sauf=user.id)
    return read_scrutin(db, user, scrutin.id)

def _titre_complet(db: Session, poste: models.GouvernementPostes) -> str:
    # « Bourgmestre de Valcourt » pour un poste de ville, le titre seul pour la civilisation
    if poste.entity_type == "ville":
        ville = get_ville_by_id(db, poste.entity_id)
        return f"{poste.title} de {ville.title}" if ville else poste.title
    return poste.title

def annuler_scrutin(db: Session, user: schemas.Users, ID: int):
    scrutin = _require_scrutin(db, ID)
    if not peut_organiser(db, user, scrutin.entity_type, scrutin.entity_id):
        raise HTTPException(status_code=403, detail="Seuls ceux qui peuvent ouvrir le scrutin l'annulent")
    if scrutin.status != "ouvert":
        raise HTTPException(status_code=400, detail="Ce scrutin est déjà clos")
    scrutin.status = "annule"
    scrutin.closed_at = dt.datetime.now()
    db.add(scrutin)
    db.commit()
    _notifier(db, scrutin, {c.user_id for c in _candidats(db, scrutin.id)} | _joueurs_votants(db, scrutin), f"Scrutin annulé : {scrutin.title}", sauf=user.id)
    return read_scrutin(db, user, scrutin.id)

def candidater(db: Session, user: schemas.Users, ID: int, body: schemas.CandidatureCreate):
    scrutin = _require_scrutin(db, ID)
    if phase(scrutin) != "candidatures":
        raise HTTPException(status_code=400, detail="Les candidatures sont closes : le vote est ouvert")
    personnage = crud_personnages.get_personnage(db, body.personnage_id)
    if not personnage or not crud_personnages.can_manage(user, personnage):
        raise HTTPException(status_code=403, detail="Vous ne présentez que vos propres personnages")
    if personnage.id not in {p.id for p in personnages_lies(db, scrutin.entity_type, scrutin.entity_id)}:
        raise HTTPException(status_code=400, detail=f"{personnage.name} n'est pas lié à {scrutin.entity_title} : il ne peut pas s'y présenter")
    if any(c.personnage_id == personnage.id for c in _candidats(db, scrutin.id)):
        raise HTTPException(status_code=400, detail=f"{personnage.name} est déjà candidat")
    programme = (body.programme or "").strip() or None
    if programme and len(programme) > PROGRAMME_MAX:
        raise HTTPException(status_code=400, detail=f"Le programme ne dépasse pas {PROGRAMME_MAX} caractères")
    # user_id : le joueur du personnage, même présenté par un administrateur (notifications, retrait)
    db.add(models.ScrutinCandidats(scrutin_id=scrutin.id, personnage_id=personnage.id, nom=personnage.name, programme=programme, user_id=personnage.user_id or user.id))
    db.commit()
    return read_scrutin(db, user, scrutin.id)

def retirer_candidature(db: Session, user: schemas.Users, ID: int, candidatID: int):
    scrutin = _require_scrutin(db, ID)
    candidat = db.get(models.ScrutinCandidats, candidatID)
    if not candidat or candidat.scrutin_id != scrutin.id:
        raise HTTPException(status_code=404, detail="Cette candidature n'existe pas")
    if not (candidat.user_id == user.id or peut_organiser(db, user, scrutin.entity_type, scrutin.entity_id)):
        raise HTTPException(status_code=403, detail="Seuls le candidat et les organisateurs retirent une candidature")
    if phase(scrutin) != "candidatures":
        raise HTTPException(status_code=400, detail="Le vote est ouvert : les candidatures ne changent plus")
    db.delete(candidat)
    db.commit()
    return read_scrutin(db, user, scrutin.id)

def voter(db: Session, user: schemas.Users, ID: int, body: schemas.VoteCreate):
    scrutin = _require_scrutin(db, ID)
    if phase(scrutin) not in ("vote", "second_tour"):
        raise HTTPException(status_code=400, detail="Le vote n'est pas ouvert" if scrutin.status == "ouvert" else "Ce scrutin est clos")
    votant = next((v for v in votants(db, scrutin) if v["type"] == body.votant_type and v["id"] == body.votant_id), None)
    if not votant:
        raise HTTPException(status_code=400, detail="Cette voix ne compte pas dans ce scrutin")
    if not votant["personnage"] or votant["personnage"].user_id != user.id:
        raise HTTPException(status_code=403, detail="Seul le joueur du personnage votant donne cette voix")
    if _a_vote(db, scrutin, votant["type"], votant["id"]):
        raise HTTPException(status_code=400, detail=f"{votant['title']} a déjà voté")
    candidat = db.get(models.ScrutinCandidats, body.candidat_id)
    if not candidat or candidat.scrutin_id != scrutin.id or (scrutin.tour == 2 and not candidat.au_second_tour):
        raise HTTPException(status_code=400, detail="Ce candidat ne se présente pas à ce tour")

    db.add(models.ScrutinVotants(scrutin_id=scrutin.id, tour=scrutin.tour, votant_type=votant["type"], votant_id=votant["id"],
                                 personnage_id=votant["personnage"].id, user_id=user.id))
    if scrutin.tour == 2:
        candidat.voix_second_tour += 1
    else:
        candidat.voix += 1
    db.add(candidat)
    if scrutin.mode == "public":
        qui = votant["title"] if votant["type"] == "personnage" else f"{votant['title']} (par {votant['personnage'].name})"
        db.add(models.ScrutinBulletins(scrutin_id=scrutin.id, tour=scrutin.tour, candidat_id=candidat.id,
                                       votant_type=votant["type"], votant_id=votant["id"], votant_title=qui))
    db.commit()
    return read_scrutin(db, user, scrutin.id)

#endregion
#region Chroniques

def entrees_chroniques(db: Session):
    # Pour crud_chroniques : résultats des scrutins clos d'entités publiques, datés en RP
    entrees = []
    for scrutin in db.exec(select(models.Scrutins).where(models.Scrutins.status == "clos", models.Scrutins.resultat == "elu")).all():
        entite = _entite(db, scrutin.entity_type, scrutin.entity_id)
        elu = db.get(models.ScrutinCandidats, scrutin.elu_id) if scrutin.elu_id else None
        if not scrutin.date_rp or not entite or entite.is_public is False or not elu:
            continue
        poste = f" : {elu.nom}, {scrutin.poste_title}" if scrutin.poste_title else f" : {elu.nom} élu"
        entrees.append({"id": f"election-{scrutin.id}", "date": scrutin.closed_at or scrutin.created_at, "date_rp": scrutin.date_rp,
                        "title": f"{scrutin.title}{poste}", "description": entite.title, "lien": _lien(scrutin)})
    return entrees

#endregion
