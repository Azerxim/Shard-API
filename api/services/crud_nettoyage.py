"""
Cohérence des données quand une entité disparaît.

Les fonctions de détachement modifient la session sans valider : l'appelant supprime l'entité puis fait le commit.
Ce module ne dépend que des modèles (crud, crud_conflits et crud_personnages peuvent l'importer).

- Civilisation : alliances (le chef de file est remplacé, ou l'alliance dissoute), invitations, guerres, civilisations
  dirigées, livres, résidences des personnages.
- Religion : guerres de religion.
- Ville / quartier : religions, magasins, résidences des personnages.
- Journal : messages signés par des personnages.
- Utilisateur : adhésions, comptes liés, sessions, personnages ; refusé tant qu'il est fondateur.

Guerres : une déclaration non validée dont un chef de camp disparaît est retirée ; une guerre commencée reste archivée
(nom de l'entité conservé dans entity_title). En cours, un autre engagé du camp prend la tête, sinon la guerre se termine.
"""
import datetime as dt

from sqlmodel import Session, select

from ..db import models


def _all(db: Session, model, *conditions):
    return db.exec(select(model).where(*conditions)).all()


#region Personnages

def vider_residence(db: Session, residence: str, ID: int):
    # Un personnage qui perd sa civilisation perd aussi sa ville et son quartier (et la ville son quartier)
    column = getattr(models.Personnages, f"{residence}_id")
    for personnage in _all(db, models.Personnages, column == ID):
        if residence == "civilisation":
            personnage.civilisation_id = None
        if residence in ("civilisation", "ville"):
            personnage.ville_id = None
        personnage.quartier_id = None
        db.add(personnage)

def supprimer_liens_journal(db: Session, journalID: int):
    for link in _all(db, models.PersonnageMessages, models.PersonnageMessages.journal_id == journalID):
        db.delete(link)

def supprimer_personnages_utilisateur(db: Session, userID: int):
    for personnage in _all(db, models.Personnages, models.Personnages.user_id == userID):
        for link in _all(db, models.PersonnageMessages, models.PersonnageMessages.personnage_id == personnage.id):
            db.delete(link)
        db.delete(personnage)

#endregion
#region Alliances

def _dissoudre_alliance(db: Session, allianceID: int):
    for invitation in _all(db, models.AllianceInvitations, models.AllianceInvitations.alliance_id == allianceID):
        db.delete(invitation)
    for belligerant in _all(db, models.GuerreBelligerants, models.GuerreBelligerants.alliance_id == allianceID):
        belligerant.alliance_id = None
        db.add(belligerant)
    alliance = db.get(models.Alliances, allianceID)
    if alliance:
        db.delete(alliance)

def retirer_civilisation_des_alliances(db: Session, civilisationID: int):
    for invitation in _all(db, models.AllianceInvitations, models.AllianceInvitations.civilisation_id == civilisationID):
        db.delete(invitation)
    for membre in _all(db, models.AllianceMembres, models.AllianceMembres.civilisation_id == civilisationID):
        allianceID, was_chef = membre.alliance_id, membre.role == "Chef de file"
        db.delete(membre)
        if not was_chef:
            continue
        # Nouveau chef de file : le membre le plus ancien, à défaut l'observateur le plus ancien
        restants = [m for m in _all(db, models.AllianceMembres, models.AllianceMembres.alliance_id == allianceID) if m.id != membre.id]
        restants.sort(key=lambda m: ({"Membre": 0, "Observateur": 1}.get(m.role, 2), m.joined_at))
        if restants:
            restants[0].role = "Chef de file"
            db.add(restants[0])
        else:
            _dissoudre_alliance(db, allianceID)

#endregion
#region Guerres

def _retirer_declaration(db: Session, guerre: models.Guerres):
    for belligerant in _all(db, models.GuerreBelligerants, models.GuerreBelligerants.guerre_id == guerre.id):
        db.delete(belligerant)
    for evenement in _all(db, models.GuerreEvenements, models.GuerreEvenements.guerre_id == guerre.id):
        db.delete(evenement)
    for zone in _all(db, models.Cartographie, models.Cartographie.type == "guerre", models.Cartographie.type_id == guerre.id):
        db.delete(zone)
    db.delete(guerre)

def retirer_des_guerres(db: Session, entity_type: str, entity_id: int, title: str | None):
    statement = (models.GuerreBelligerants.entity_type == entity_type, models.GuerreBelligerants.entity_id == entity_id)
    for belligerant in _all(db, models.GuerreBelligerants, *statement):
        guerre = db.get(models.Guerres, belligerant.guerre_id)
        if not guerre:
            db.delete(belligerant)
            continue

        if guerre.status in ("en_attente", "refusee"):
            # Jamais validée : rien à archiver
            if belligerant.is_leader:
                _retirer_declaration(db, guerre)
            else:
                db.delete(belligerant)
            continue

        if belligerant.status != "engage":
            # Appel aux armes resté sans réponse
            db.delete(belligerant)
            continue

        belligerant.entity_title = belligerant.entity_title or title
        db.add(belligerant)
        if guerre.status != "en_cours" or not belligerant.is_leader:
            continue

        # Chef de camp disparu pendant la guerre : relève par un autre engagé du camp, sinon fin de la guerre
        relève = [
            b for b in _all(db, models.GuerreBelligerants, models.GuerreBelligerants.guerre_id == guerre.id)
            if b.id != belligerant.id and b.camp == belligerant.camp and b.status == "engage"
            and not (b.entity_type == entity_type and b.entity_id == entity_id)
        ]
        if relève:
            relève.sort(key=lambda b: b.joined_at)
            belligerant.is_leader = False
            relève[0].is_leader = True
            db.add(relève[0])
        else:
            vainqueurs = "défenseurs" if belligerant.camp == "attaquant" else "attaquants"
            guerre.status = "terminee"
            guerre.issue = f"Victoire des {vainqueurs} : {title or 'le camp adverse'} a disparu"
            guerre.date_fin = dt.date.today()
            guerre.ended_at = dt.datetime.now()
            db.add(guerre)
            db.add(models.GuerreEvenements(guerre_id=guerre.id, type="fin", title=guerre.issue, is_auto=True))

#endregion
#region Lieux et entités

def detacher_quartier(db: Session, quartierID: int):
    vider_residence(db, "quartier", quartierID)

def detacher_ville(db: Session, villeID: int):
    for link in _all(db, models.VillesReligions, models.VillesReligions.ville_id == villeID):
        db.delete(link)
    for magasin in _all(db, models.CommerceMagasins, models.CommerceMagasins.ville_id == villeID):
        magasin.ville_id = None
        db.add(magasin)
    vider_residence(db, "ville", villeID)

def detacher_religion(db: Session, religionID: int, title: str | None):
    retirer_des_guerres(db, "religion", religionID, title)

def detacher_civilisation(db: Session, civilisationID: int, title: str | None):
    retirer_civilisation_des_alliances(db, civilisationID)
    retirer_des_guerres(db, "civilisation", civilisationID, title)
    vider_residence(db, "civilisation", civilisationID)
    for dirigee in _all(db, models.Civilisations, models.Civilisations.dirigeante_civilisation_id == civilisationID):
        dirigee.is_civilisation_dirigeante = True
        dirigee.dirigeante_civilisation_id = 0
        db.add(dirigee)
    for livre in _all(db, models.Livres, models.Livres.civilisation_id == civilisationID):
        livre.civilisation_id = None
        db.add(livre)

#endregion
#region Utilisateurs

MEMBERSHIPS = (
    (models.CivilisationMembers, "civilisation_id", models.Civilisations, "la civilisation"),
    (models.ReligionMembers, "religion_id", models.Religions, "la religion"),
    (models.CommerceMembers, "commerce_id", models.Commerces, "le commerce"),
)

def fondations_utilisateur(db: Session, userID: int):
    # « la civilisation X », « le commerce Y »… dont l'utilisateur est encore fondateur
    result = []
    for member_model, fk, entity_model, label in MEMBERSHIPS:
        for member in _all(db, member_model, member_model.user_id == userID, member_model.role == "Fondateur"):
            entity = db.get(entity_model, getattr(member, fk))
            if entity:
                result.append(f"{label} {entity.title}")
    return result

def detacher_utilisateur(db: Session, user: models.Users):
    for member_model, _fk, _entity, _label in MEMBERSHIPS:
        for member in _all(db, member_model, member_model.user_id == user.id):
            db.delete(member)
    for model, column in ((models.UserPlatforms, models.UserPlatforms.user_id), (models.OAuthStates, models.OAuthStates.user_id)):
        for row in _all(db, model, column == user.id):
            db.delete(row)
    for session in _all(db, models.ActiveSession, models.ActiveSession.username == user.username):
        db.delete(session)
    supprimer_personnages_utilisateur(db, user.id)

    # Écrits et archives conservés, sans auteur
    for model, attribute in (
        (models.Journaux, "user_id"), (models.Livres, "user_id"), (models.AllianceInvitations, "created_by"),
        (models.Guerres, "declared_by"), (models.Guerres, "moderator_id"), (models.PersonnageMessages, "linked_by"),
    ):
        for row in _all(db, model, getattr(model, attribute) == user.id):
            setattr(row, attribute, None)
            db.add(row)

#endregion
#region Références déjà orphelines (démarrage)

def nettoyer_references_orphelines(db: Session):
    # Rattrape les suppressions faites avant ce module ; renvoie le nombre de corrections par catégorie
    counts = {"personnages": 0, "messages": 0, "alliances": 0, "belligerants": 0}
    exists = lambda model, ID: ID is not None and db.get(model, ID) is not None

    for personnage in _all(db, models.Personnages):
        before = (personnage.civilisation_id, personnage.ville_id, personnage.quartier_id)
        if personnage.quartier_id and not exists(models.Quartiers, personnage.quartier_id):
            personnage.quartier_id = None
        if personnage.ville_id and not exists(models.Villes, personnage.ville_id):
            personnage.ville_id = personnage.quartier_id = None
        if personnage.civilisation_id and not exists(models.Civilisations, personnage.civilisation_id):
            personnage.civilisation_id = personnage.ville_id = personnage.quartier_id = None
        if before != (personnage.civilisation_id, personnage.ville_id, personnage.quartier_id):
            db.add(personnage)
            counts["personnages"] += 1

    for link in _all(db, models.PersonnageMessages):
        if not exists(models.Personnages, link.personnage_id) or not exists(models.Journaux, link.journal_id):
            db.delete(link)
            counts["messages"] += 1

    civilisations = {m.civilisation_id for m in _all(db, models.AllianceMembres)} | {i.civilisation_id for i in _all(db, models.AllianceInvitations)}
    for civilisationID in civilisations:
        if not exists(models.Civilisations, civilisationID):
            retirer_civilisation_des_alliances(db, civilisationID)
            counts["alliances"] += 1

    entity_models = {"civilisation": models.Civilisations, "religion": models.Religions}
    orphelins = {
        (b.entity_type, b.entity_id) for b in _all(db, models.GuerreBelligerants)
        if b.entity_type in entity_models and not b.entity_title and not exists(entity_models[b.entity_type], b.entity_id)
    }
    for entity_type, entity_id in orphelins:
        retirer_des_guerres(db, entity_type, entity_id, None)
        counts["belligerants"] += 1

    if any(counts.values()):
        db.commit()
    return counts

#endregion
